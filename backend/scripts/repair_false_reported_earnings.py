#!/usr/bin/env python3
"""Repair earnings_events rows falsely flipped to ``reported`` by unguarded 2.02 8-K hits.

Before ``is_probable_earnings_release`` existed (2026-07), ANY 8-K carrying Item 2.02 flipped or
created ``reported`` rows: pre-announcements (BIIB filed one 2026-07-01; real earnings 7/29),
TSLA's quarterly delivery numbers, royalty-trust distribution notices. This script re-classifies
every ``edgar_8k`` reported row in a date window using the same guard the engine now applies, so
repair and engine cannot drift:

  prior_event_date present -> re-run the guard against the pre-flip date:
      pass -> KEEP    (genuine flip: timing corroborates an earnings release)
      fail -> RESTORE (false flip: put the estimate back on prior_event_date)
  prior_event_date NULL    -> gap-only check (MIN_GAP <= event_date - fiscal_period_end <= MAX_GAP):
      pass -> KEEP    (genuine flip whose estimate already matched the filed date exactly)
      fail -> DELETE  (insert-path creation with no earnings-timing corroboration)

Restored rows go back to a plain provider estimate; the next Alpha Vantage pass refreshes them.
No earnings_alert_log cleanup is needed — its dedup key includes event_date, so a corrected date
re-alerts naturally and deletes cascade at the DB level.

Usage:
    # Dry run (default) — prints per-row classification, changes nothing
    python scripts/repair_false_reported_earnings.py --from 2026-06-28 --to 2026-07-04

    # Apply
    python scripts/repair_false_reported_earnings.py --from 2026-06-28 --to 2026-07-04 --execute

    # Single ticker only
    python scripts/repair_false_reported_earnings.py --from 2026-06-28 --to 2026-07-04 --ticker BIIB --execute
"""
import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import EarningsEvent
from app.models.earnings import (
    CONFIDENCE_MEDIUM,
    SOURCE_ALPHA_VANTAGE,
    SOURCE_EDGAR_8K,
    STATUS_ESTIMATED,
    STATUS_REPORTED,
)
from app.services.earnings_calendar_service import (
    EARNINGS_RELEASE_MAX_GAP_DAYS,
    EARNINGS_RELEASE_MIN_GAP_DAYS,
    is_probable_earnings_release,
)

logger = logging.getLogger(__name__)


def classify(ev: EarningsEvent) -> str:
    """keep | restore | delete for one edgar_8k reported row (see module docstring)."""
    filed = ev.event_date  # the flip set event_date to the 8-K's filing date
    if ev.prior_event_date is not None:
        return (
            "keep"
            if is_probable_earnings_release(
                filed, fiscal_period_end=ev.fiscal_period_end, event_date=ev.prior_event_date
            )
            else "restore"
        )
    gap = (filed - ev.fiscal_period_end).days
    return "keep" if EARNINGS_RELEASE_MIN_GAP_DAYS <= gap <= EARNINGS_RELEASE_MAX_GAP_DAYS else "delete"


def repair(
    session,
    from_date: date,
    to_date: date,
    *,
    dry_run: bool = True,
    ticker: str | None = None,
) -> dict[str, int]:
    """Re-classify edgar_8k reported rows with event_date in [from_date, to_date].

    Returns ``{"keep": n, "restore": n, "delete": n}``. Mutates/commits only when
    ``dry_run=False``; a dry run is strictly read-only.
    """
    q = session.query(EarningsEvent).filter(
        EarningsEvent.status == STATUS_REPORTED,
        EarningsEvent.source == SOURCE_EDGAR_8K,
        EarningsEvent.event_date >= from_date,
        EarningsEvent.event_date <= to_date,
    )
    if ticker:
        q = q.filter(EarningsEvent.ticker == ticker.upper())
    rows = q.order_by(EarningsEvent.event_date.asc(), EarningsEvent.ticker.asc()).all()

    counts = {"keep": 0, "restore": 0, "delete": 0}
    logger.info("Found %s edgar_8k reported rows in [%s, %s]", len(rows), from_date, to_date)
    for ev in rows:
        action = classify(ev)
        counts[action] += 1
        gap = (ev.event_date - ev.fiscal_period_end).days
        delta = (
            f"{abs((ev.event_date - ev.prior_event_date).days)}d"
            if ev.prior_event_date is not None
            else "-"
        )
        logger.info(
            "  %-6s fpe=%s event=%s prior=%s gap=%sd delta=%s -> %s",
            ev.ticker, ev.fiscal_period_end, ev.event_date, ev.prior_event_date,
            gap, delta, action.upper(),
        )
        if dry_run or action == "keep":
            continue
        if action == "restore":
            ev.event_date = ev.prior_event_date
            ev.status = STATUS_ESTIMATED
            ev.confidence = CONFIDENCE_MEDIUM
            ev.source = SOURCE_ALPHA_VANTAGE
            ev.accession_number = None
            ev.reported_at = None
            ev.prior_event_date = None
            ev.date_changed_at = None
        else:  # delete
            session.delete(ev)

    if dry_run:
        logger.info("Dry run complete: %s. Run with --execute to apply.", counts)
    else:
        session.commit()
        logger.info("Repair applied: %s", counts)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair earnings rows falsely flipped to reported by unguarded 2.02 8-Ks."
    )
    parser.add_argument("--from", dest="from_date", type=date.fromisoformat, required=True,
                        help="Window start (YYYY-MM-DD), inclusive, on event_date.")
    parser.add_argument("--to", dest="to_date", type=date.fromisoformat, required=True,
                        help="Window end (YYYY-MM-DD), inclusive, on event_date.")
    parser.add_argument("--ticker", type=str, default=None, help="Only repair a specific ticker.")
    parser.add_argument("--execute", action="store_true",
                        help="Actually apply the repair (default is dry run).")
    args = parser.parse_args()
    if args.from_date > args.to_date:
        parser.error("--from must be on or before --to")

    dry_run = not args.execute
    logger.info("Running in %s mode", "DRY RUN" if dry_run else "EXECUTE")

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        repair(session, args.from_date, args.to_date, dry_run=dry_run, ticker=args.ticker)
        return 0
    except Exception:
        logger.exception("Repair failed; rolling back")
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    import os

    # basicConfig lives here, not at module level, so importing this module in tests doesn't
    # reconfigure the root logger as an import side-effect.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    sys.exit(main())
