"""Controlled non-destructive database migration script for MahaSeva AI.

Safely adds missing columns, indexes, and tables without losing existing records.
"""

import json
from pathlib import Path
from sqlalchemy import inspect, text

from backend.database import Base, engine
from backend.models import (
    AdminUser,
    CollectionRun,
    ConfiguredSource,
    SchemeApplicationWindow,
    SchemeCandidate,
    SchemeChange,
    SchemeSourceVersion,
    VerificationAudit,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_migration() -> None:
    print("Starting non-destructive database migration for MahaSeva AI...")

    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_tables = inspector.get_table_names()
        print(f"Existing tables in database: {existing_tables}")

        # Check and add missing columns to scheme_candidates
        if "scheme_candidates" in existing_tables:
            columns = [col["name"] for col in inspector.get_columns("scheme_candidates")]
            print(f"Existing columns in scheme_candidates: {len(columns)}")

            columns_to_add = {
                "brief_description": "TEXT NULL",
                "benefits": "TEXT NULL",
                "eligibility": "TEXT NULL",
                "documents_required": "TEXT NULL",
                "application_process": "TEXT NULL",
                "official_apply_url": "VARCHAR(2048) NULL",
                "last_reviewed_at": "DATETIME NULL",
                "reviewed_by": "VARCHAR(100) NULL",
                # New fields for deadline monitoring and scheme discovery
                "title_mr": "VARCHAR(1000) NULL",
                "category": "VARCHAR(200) NOT NULL DEFAULT 'General'",
                "target_beneficiaries": "TEXT NULL",
                "application_mode": "VARCHAR(50) NOT NULL DEFAULT 'online'",
                "current_window_status": "VARCHAR(50) NOT NULL DEFAULT 'no_deadline_published'",
                "application_start_date": "VARCHAR(50) NULL",
                "application_deadline": "VARCHAR(50) NULL",
                "closing_time": "VARCHAR(50) NULL",
                "date_verification_status": "VARCHAR(50) NOT NULL DEFAULT 'unverified'",
                "is_recently_announced": "BOOLEAN NOT NULL DEFAULT 0",
                "is_recently_updated": "BOOLEAN NOT NULL DEFAULT 0",
                "announced_date": "VARCHAR(50) NULL",
                "effective_date": "VARCHAR(50) NULL",
                "official_notification_url": "VARCHAR(2048) NULL",
                "last_checked_at": "DATETIME NULL",
            }

            for col_name, col_def in columns_to_add.items():
                if col_name not in columns:
                    print(f"Adding column `{col_name}` to `scheme_candidates`...")
                    conn.execute(text(f"ALTER TABLE `scheme_candidates` ADD COLUMN `{col_name}` {col_def}"))
                    conn.commit()

            # Add missing indexes if needed
            indexes = [idx["name"] for idx in inspector.get_indexes("scheme_candidates")]
            if "idx_candidate_dept" not in indexes:
                try:
                    conn.execute(text("CREATE INDEX idx_candidate_dept ON scheme_candidates (department(255))"))
                    conn.commit()
                except Exception as e:
                    print(f"Notice (dept index): {e}")

            if "idx_candidate_status" not in indexes:
                try:
                    conn.execute(text("CREATE INDEX idx_candidate_status ON scheme_candidates (verification_status)"))
                    conn.commit()
                except Exception as e:
                    print(f"Notice (status index): {e}")

            if "idx_candidate_window_status" not in indexes:
                try:
                    conn.execute(text("CREATE INDEX idx_candidate_window_status ON scheme_candidates (current_window_status)"))
                    conn.commit()
                except Exception as e:
                    print(f"Notice (window status index): {e}")

        # Check and add missing columns to configured_sources
        if "configured_sources" in existing_tables:
            src_columns = [col["name"] for col in inspector.get_columns("configured_sources")]
            src_columns_to_add = {
                "department": "VARCHAR(500) NULL",
                "source_category": "VARCHAR(100) NULL DEFAULT 'Departmental Portal'",
                "monitoring_frequency_hours": "INT NOT NULL DEFAULT 24",
                "crawl_depth": "INT NOT NULL DEFAULT 2",
                "max_pages": "INT NOT NULL DEFAULT 50",
                "priority": "VARCHAR(50) NOT NULL DEFAULT 'medium'",
                "verification_required": "BOOLEAN NOT NULL DEFAULT 1",
                "last_success_at": "DATETIME NULL",
                "last_changed_at": "DATETIME NULL",
                "last_error": "TEXT NULL",
            }
            for col_name, col_def in src_columns_to_add.items():
                if col_name not in src_columns:
                    print(f"Adding column `{col_name}` to `configured_sources`...")
                    conn.execute(text(f"ALTER TABLE `configured_sources` ADD COLUMN `{col_name}` {col_def}"))
                    conn.commit()

    # Create new tables if not present
    print("Creating new metadata tables if not present...")
    Base.metadata.create_all(bind=engine)

    # Populate initial configured sources from sites.json if needed
    sites_json_path = PROJECT_ROOT / "sites.json"
    if sites_json_path.exists():
        with engine.begin() as conn:
            existing_count = conn.execute(text("SELECT COUNT(*) FROM configured_sources")).scalar()
            if existing_count == 0:
                print("Populating initial configured sources from sites.json...")
                data = json.loads(sites_json_path.read_text(encoding="utf-8"))
                for site in data.get("sites", []):
                    conn.execute(
                        text(
                            "INSERT INTO configured_sources ("
                            "name, department, source_category, start_urls, allowed_domains, provider_hint, "
                            "is_active, monitoring_frequency_hours, priority, crawl_depth, max_pages, verification_required) "
                            "VALUES (:name, :dept, :cat, :start_urls, :allowed_domains, :provider_hint, 1, 24, 'high', 2, 50, 1)"
                        ),
                        {
                            "name": site["name"],
                            "dept": site.get("name", "Maharashtra Government"),
                            "cat": "Departmental Scheme Directory",
                            "start_urls": ";".join(site.get("start_urls", [])),
                            "allowed_domains": ";".join(site.get("allowed_domains", [])),
                            "provider_hint": site.get("provider_hint", "state"),
                        },
                    )
                print("Configured sources initialized.")

    # Populate scheme categories and categories heuristic for existing scheme_candidates
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE scheme_candidates SET category = 'Agriculture' "
                "WHERE (title LIKE '%कृषी%' OR title LIKE '%shetkari%' OR title LIKE '%farmer%' OR department LIKE '%Rural%') "
                "AND (category IS NULL OR category = 'General')"
            )
        )
        conn.execute(
            text(
                "UPDATE scheme_candidates SET category = 'Social Justice & Welfare' "
                "WHERE (department LIKE '%Social%' OR title LIKE '%मागास%' OR title LIKE '%Divyang%') "
                "AND (category IS NULL OR category = 'General')"
            )
        )
        conn.execute(
            text(
                "UPDATE scheme_candidates SET category = 'Urban Development' "
                "WHERE department LIKE '%Urban%' AND (category IS NULL OR category = 'General')"
            )
        )
        conn.execute(
            text(
                "UPDATE scheme_candidates SET category = 'Co-operation & Textiles' "
                "WHERE department LIKE '%Co-operation%' AND (category IS NULL OR category = 'General')"
            )
        )

    # Verify counts
    with engine.connect() as conn:
        cand_count = conn.execute(text("SELECT COUNT(*) FROM scheme_candidates")).scalar()
        tables_now = inspect(conn).get_table_names()
        print(f"Migration completed successfully. Tables now: {tables_now}")
        print(f"scheme_candidates preserved: {cand_count} rows.")


if __name__ == "__main__":
    run_migration()
