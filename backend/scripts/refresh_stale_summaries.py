#!/usr/bin/env python3
"""Drain version-stale summaries in place as a bounded Cloud Run job (the D4 drain).

The admin ``POST /api/admin/summaries/refresh-stale`` endpoint regenerates at most ten rows per
synchronous request; a corpus-sized backlog belongs in a job. This script runs the same shared
drain (``app.services.summary_refresh.drain_stale``): stale rows (missing or behind
``SUMMARY_SCHEMA_VERSION``/``SUMMARY_PROMPT_VERSION``) are regenerated IN PLACE through the ONE
orchestrator with ``force_regenerate=True``, so ``summaries.id`` and saved-summary bookmarks survive
and the pipeline's keep-better gate refuses downgrades. Every execution persists honest counts in
``earningsnerd_job_runs`` (job ``refresh-stale``); a run with any failed regeneration is recorded as
failed. Nothing regenerates unless ``--execute`` is given.

Run it on the pregenerate job image (it carries the generator credential and the database):

  gcloud run jobs execute earningsnerd-pregenerate --region us-west1 \
      --args=scripts/refresh_stale_summaries.py                       # dry run: staleness breakdown, no model call
  gcloud run jobs execute earningsnerd-pregenerate --region us-west1 \
      --args=scripts/refresh_stale_summaries.py,--execute,--limit,30,--max-seconds,1200

Repeat bounded executions until ``stale_total`` reaches zero; rows the keep-better gate keeps stay
stale and may be re-selected (random order). Each generation is paid provider spend.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from typing import List, Optional

# Make the backend root importable as `app.*` when run directly (see filing_scan.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 30
DEFAULT_MAX_SECONDS = 1200.0  # well inside the pregenerate job's task timeout


async def _run(*, execute: bool, limit: int, max_seconds: float, filing_type: Optional[str],
               schema_version_lt: Optional[int]) -> dict:
    from app.database import SessionLocal
    from app.services.summary_refresh import drain_stale, stale_breakdown

    with SessionLocal() as db:
        report = {"dry_run": not execute, **stale_breakdown(db, schema_version_lt=schema_version_lt, filing_type=filing_type)}
    if execute:
        # No session is held across generations; the drain opens its own short-lived ones.
        report.update(await drain_stale(
            SessionLocal, limit=limit, max_seconds=max_seconds, schema_version_lt=schema_version_lt,
            filing_type=filing_type,
        ))
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true",
                        help="regenerate stale rows (paid); without it the run only reports the staleness breakdown")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"rows to regenerate this execution (default {DEFAULT_LIMIT})")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS,
                        help=f"stop before a generation that would start after this many seconds (default {DEFAULT_MAX_SECONDS:g})")
    parser.add_argument("--filing-type", default=None, help="optional form filter, e.g. 10-K")
    parser.add_argument("--schema-version-lt", type=int, default=None,
                        help="refresh rows whose schema_version is NULL or below this (default: stale vs current schema+prompt)")
    args = parser.parse_args(argv)
    from app.services.job_run_service import JobRunFailed, track_job
    from app.services.summary_refresh import check_schema_threshold

    try:
        check_schema_threshold(args.schema_version_lt)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        with track_job("refresh-stale", dry_run=not args.execute) as attempt:
            report = asyncio.run(_run(execute=args.execute, limit=max(0, args.limit), max_seconds=args.max_seconds,
                                      filing_type=args.filing_type, schema_version_lt=args.schema_version_lt))
            counters = {key: report[key] for key in ("summaries_total", "stale_total") if key in report}
            counters.update({key: report[key] for key in ("attempted", "updated", "kept_by_gate", "failed", "deferred")
                             if key in report})
            attempt.record(counters)
            print(json.dumps(report, sort_keys=True))
    except JobRunFailed as exc:
        logger.error("refresh-stale: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    from app.services import ai_metrics

    ai_metrics.set_trigger("job")  # Cloud Run job spend, separable from user traffic in the ai_call log
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
