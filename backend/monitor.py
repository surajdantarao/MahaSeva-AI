"""Automated Scheme Discovery & Source Monitoring for MahaSeva AI.

Executes monitoring checks against registered official Maharashtra Government portals,
detects content changes via content hashes, tracks run statistics in MySQL, and updates
review queues without disrupting the main FastAPI web server.
"""

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from sqlalchemy import select

from backend.database import SessionLocal
from backend.import_csv import import_candidates
from backend.models import CollectionRun, ConfiguredSource
from backend.scheduler import execute_monitoring_cycle, recalculate_all_deadlines

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MONITOR] %(levelname)s: %(message)s",
)
log = logging.getLogger("mahaseva.monitor")


def run_monitoring_sync(trigger_crawler: bool = False) -> Dict[str, int]:
    """Execute source monitoring pass and candidate synchronization.

    Maintains exact backward compatibility while incorporating deadline recalculation.
    """
    log.info("Initiating candidate monitoring & sync run...")
    with SessionLocal() as session:
        run_record = CollectionRun(
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        session.add(run_record)
        session.commit()
        session.refresh(run_record)

        try:
            if trigger_crawler:
                log.info("Executing collector.py crawler subprocess...")
                python_exe = sys.executable
                collector_script = PROJECT_ROOT / "collector.py"
                proc = subprocess.run(
                    [python_exe, str(collector_script)],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if proc.returncode != 0:
                    log.warning(f"Collector completed with warning/error: {proc.stderr[:300]}")

            # Recalculate deadline statuses first
            deadline_updates = recalculate_all_deadlines()

            # Sync CSV outputs into database with date extraction & change tracking
            stats = import_candidates()

            # Update configured sources last_crawled_at
            active_sources = session.scalars(
                select(ConfiguredSource).where(ConfiguredSource.is_active == True)
            ).all()
            for s in active_sources:
                s.last_crawled_at = datetime.now(timezone.utc)
                s.last_success_at = datetime.now(timezone.utc)

            run_record.status = "completed"
            run_record.finished_at = datetime.now(timezone.utc)
            run_record.total_candidates = stats.get("total_rows", 0)
            run_record.new_candidates = stats.get("inserted", 0)
            run_record.updated_candidates = stats.get("updated", 0)
            run_record.errors_count = stats.get("failed", 0)
            run_record.log_summary = (
                f"Completed successfully. Total evaluated: {stats.get('total_rows')}, "
                f"New: {stats.get('inserted')}, Updated: {stats.get('updated')}, "
                f"Skipped: {stats.get('skipped')}, Deadlines recalculated: {deadline_updates}"
            )
            session.commit()
            log.info("Monitoring run completed successfully.")
            return stats

        except Exception as exc:
            run_record.status = "failed"
            run_record.finished_at = datetime.now(timezone.utc)
            run_record.errors_count = 1
            run_record.log_summary = f"Monitoring run failed: {str(exc)}"
            session.commit()
            log.error(f"Monitoring run failed: {exc}", exc_info=True)
            raise exc


def main():
    parser = argparse.ArgumentParser(description="MahaSeva AI Source Monitoring & Sync")
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Execute collector.py before syncing candidates",
    )
    parser.add_argument(
        "--recalculate-deadlines",
        action="store_true",
        help="Run deadline recalculation for all existing schemes",
    )
    args = parser.parse_args()

    if args.recalculate_deadlines:
        count = recalculate_all_deadlines()
        print(f"Recalculated deadlines for {count} schemes.")
    else:
        stats = run_monitoring_sync(trigger_crawler=args.crawl)
        print("\nResult:", stats)


if __name__ == "__main__":
    main()
