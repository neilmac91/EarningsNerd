#!/usr/bin/env python3
"""Reconcile private feedback screenshots hourly using durable database manifests.

Usage: python scripts/feedback_media_cleanup.py [--dry-run] [--batch-size 100] [--verify-storage]
No bucket listing, schema changes, or user content in output. A failed deletion or overdue
backlog fails the job after its counters are recorded, making monitoring actionable.
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def _main(*, dry_run: bool, batch_size: int, verify_storage: bool = False) -> None:
    from app.config import settings
    from app.database import SessionLocal
    from app.services.feedback_media_cleanup_service import run_feedback_media_cleanup, verify_feedback_media_storage
    from app.services.feedback_storage_worker_service import BoundedFeedbackStorage
    from app.services.job_run_service import JobRunFailed, track_job

    job_name = "feedback-media-storage-probe" if verify_storage else "feedback-media-cleanup"
    with track_job(job_name, dry_run=dry_run) as attempt:
        storage = None if dry_run else BoundedFeedbackStorage(settings.FEEDBACK_MEDIA_BUCKET)
        stats = verify_feedback_media_storage(SessionLocal, storage) if verify_storage else run_feedback_media_cleanup(
            SessionLocal, storage, dry_run=dry_run, batch_size=batch_size,
        )
        attempt.record(stats)
        logger.info("Feedback media cleanup complete: %s", stats)
        if not dry_run and stats.get("overdue"):
            raise JobRunFailed("feedback-media-cleanup: overdue objects; see persisted counters")
    # Emitted only after track_job has committed a successful scheduled cleanup. The log metric
    # deliberately excludes probes and dry runs, which must not conceal a stopped hourly schedule.
    if not dry_run and not verify_storage:
        logger.info("Feedback media scheduled cleanup succeeded")


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Reconcile private feedback screenshots.")
    parser.add_argument("--dry-run", action="store_true", help="Count eligible objects without changing anything.")
    parser.add_argument("--batch-size", type=int, default=100, help="Maximum objects attempted (default 100).")
    parser.add_argument("--verify-storage", action="store_true", help="Probe create/read/delete using a durable synthetic manifest.")
    args = parser.parse_args()
    if args.dry_run and args.verify_storage:
        parser.error("--verify-storage writes synthetic data and cannot be combined with --dry-run")
    _main(dry_run=args.dry_run, batch_size=args.batch_size, verify_storage=args.verify_storage)
