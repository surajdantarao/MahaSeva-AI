"""Robust CSV candidate import module for MahaSeva AI.

Safely imports scheme candidates from CSV into MySQL, preserving existing verified
statuses, extracting application dates, calculating deadline states via the status engine,
tracking detected changes, and managing application windows.
"""

import csv
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urldefrag, urlparse

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.database import Base, SessionLocal, engine
from backend.date_extractor import (
    extract_application_mode,
    extract_dates_and_deadlines,
    extract_scheme_category,
)
from backend.models import (
    SchemeApplicationWindow,
    SchemeCandidate,
    SchemeChange,
    SchemeSourceVersion,
    VerificationAudit,
)
from backend.status_engine import calculate_window_status

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "output" / "schemes_candidates.csv"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def sha256_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    clean_url, _ = urldefrag(url.strip())
    parsed = urlparse(clean_url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return clean_url
    return ""


def import_candidates(csv_file_path: Path | None = None) -> Dict[str, int]:
    target_path = csv_file_path or CSV_PATH
    if not target_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {target_path}")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    stats = {
        "total_rows": 0,
        "inserted": 0,
        "skipped": 0,
        "updated": 0,
        "rejected": 0,
        "failed": 0,
    }

    with target_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required = {"title", "department", "source_url", "text"}
        fieldnames = set(reader.fieldnames or [])
        missing = required - fieldnames
        if missing:
            raise ValueError(f"CSV missing mandatory columns: {sorted(missing)}")

        with SessionLocal() as session:
            try:
                for row_idx, row in enumerate(reader, start=2):
                    stats["total_rows"] += 1

                    title = clean(row.get("title"))
                    department = clean(row.get("department"))
                    raw_url = clean(row.get("source_url"))
                    source_url = normalize_url(raw_url)
                    raw_text = clean(row.get("text"))

                    # Basic sanity checks
                    if not title or not department or not source_url or len(raw_text) < 20:
                        stats["rejected"] += 1
                        continue

                    source_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
                    content_hash = clean(row.get("content_sha256"))
                    if len(content_hash) != 64:
                        content_hash = sha256_text(raw_text)

                    # Extract dates, application mode, and category
                    date_info = extract_dates_and_deadlines(raw_text)
                    app_mode = extract_application_mode(raw_text)
                    category = extract_scheme_category(title, raw_text, department)

                    start_date = date_info["start_date"]
                    deadline_date = date_info["deadline_date"]
                    closing_time = date_info["closing_time"]
                    date_status = date_info["date_verification_status"]

                    calc_status, _ = calculate_window_status(
                        start_date_str=start_date,
                        deadline_date_str=deadline_date,
                        closing_time_str=closing_time,
                        date_verification_status=date_status,
                    )

                    # Check if candidate with this source URL already exists
                    existing = session.scalar(
                        select(SchemeCandidate).where(
                            SchemeCandidate.source_url_sha256 == source_hash
                        )
                    )

                    if existing:
                        # If content hash is identical, update status if date engine recalculation differs
                        if existing.content_sha256 == content_hash:
                            if existing.current_window_status != calc_status and calc_status != "no_deadline_published":
                                existing.current_window_status = calc_status
                            stats["skipped"] += 1
                            continue

                        # Content has changed on official website
                        prev_deadline = existing.application_deadline
                        change_type = "content_modified"
                        if date_info["is_extension"] or (deadline_date and deadline_date != prev_deadline):
                            change_type = "deadline_extension"

                        # Log scheme change
                        scheme_change = SchemeChange(
                            scheme_id=existing.id,
                            change_type=change_type,
                            field_name="application_deadline" if change_type == "deadline_extension" else "text",
                            previous_value=str(prev_deadline) if change_type == "deadline_extension" else existing.content_sha256,
                            new_value=str(deadline_date) if change_type == "deadline_extension" else content_hash,
                            evidence_text=date_info.get("evidence", "")[:1000],
                            source_url=source_url,
                            review_status="pending_review",
                        )
                        session.add(scheme_change)

                        # Record historical version
                        version_record = SchemeSourceVersion(
                            source_url=source_url,
                            source_url_sha256=source_hash,
                            content_sha256=content_hash,
                            http_status=200,
                            content_excerpt=raw_text[:500],
                            detected_changes_count=1,
                        )
                        session.add(version_record)

                        if existing.verification_status == "verified":
                            # Never downgrade an administrator's verified record to pending_review!
                            # Flag it as needs_update so administrators can review recent changes.
                            existing.verification_status = "needs_update"
                            existing.notes = (
                                f"{existing.notes}\n[Automated Import {datetime.now(timezone.utc).date()}]: "
                                f"Official content updated. Change type: {change_type}."
                            )
                            audit = VerificationAudit(
                                candidate_id=existing.id,
                                reviewer_username="system_import",
                                action="content_updated",
                                previous_status="verified",
                                new_status="needs_update",
                                notes=f"Official source content changed. Detected change: {change_type}.",
                            )
                            session.add(audit)
                        else:
                            existing.notes = (
                                f"{existing.notes}\n[Automated Import]: Source content refreshed ({change_type})."
                            )

                        existing.text = raw_text
                        existing.content_sha256 = content_hash
                        existing.retrieved_at_utc = clean(row.get("retrieved_at_utc"))
                        existing.is_recently_updated = True
                        if deadline_date:
                            existing.application_deadline = deadline_date
                        if start_date:
                            existing.application_start_date = start_date
                        existing.current_window_status = calc_status
                        existing.last_checked_at = datetime.now(timezone.utc)
                        stats["updated"] += 1
                        continue

                    # New candidate record
                    new_candidate = SchemeCandidate(
                        title=title,
                        department=department,
                        category=category,
                        application_mode=app_mode,
                        source_url=source_url,
                        source_url_sha256=source_hash,
                        source_type=clean(row.get("source_type")) or "html",
                        retrieved_at_utc=clean(row.get("retrieved_at_utc")),
                        content_sha256=content_hash,
                        text=raw_text,
                        pdf_urls=clean(row.get("pdf_urls")),
                        provider_classification=(
                            clean(row.get("provider_classification")) or "unverified"
                        ),
                        verification_status="pending_review",
                        notes=clean(row.get("notes")),
                        current_window_status=calc_status,
                        application_start_date=start_date,
                        application_deadline=deadline_date,
                        closing_time=closing_time,
                        date_verification_status=date_status,
                        is_recently_announced=True,
                        last_checked_at=datetime.now(timezone.utc),
                    )
                    session.add(new_candidate)
                    session.flush()  # to get new_candidate.id

                    # Create initial application window if dates exist
                    if deadline_date or start_date:
                        window = SchemeApplicationWindow(
                            scheme_id=new_candidate.id,
                            window_name="General Round",
                            start_date=start_date,
                            deadline_date=deadline_date,
                            closing_time=closing_time,
                            window_status=calc_status,
                            date_verification_status=date_status,
                            official_source_url=source_url,
                            notes=date_info.get("evidence", ""),
                        )
                        session.add(window)

                    stats["inserted"] += 1

                session.commit()

            except Exception as exc:
                session.rollback()
                stats["failed"] += 1
                raise exc

    print("================ IMPORT SUMMARY ================")
    print(f"Total CSV rows evaluated: {stats['total_rows']}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Skipped (unchanged): {stats['skipped']}")
    print(f"Updated (content modified): {stats['updated']}")
    print(f"Rejected (malformed): {stats['rejected']}")
    print(f"Failures: {stats['failed']}")
    print(f"Preserved original CSV: {target_path}")
    print("================================================")
    return stats


if __name__ == "__main__":
    try:
        import_candidates()
    except (OSError, ValueError, SQLAlchemyError) as exc:
        raise SystemExit(f"Import failed: {exc}") from exc
