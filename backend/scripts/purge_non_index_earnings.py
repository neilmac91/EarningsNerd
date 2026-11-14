#!/usr/bin/env python3
"""One-time purge: delete earnings_events rows outside the S&P 500 / Nasdaq 100 universe that nobody watches.

When the calendar index filter (``CALENDAR_INDEX_FILTER_ENABLED``) is turned on, the serve path
already hides non-member tickers and daily ingest stops storing them, a watched company's aside — but
the table still holds the thousands of long-tail rows accumulated before the filter existed. This
script removes them so the DB is lean and holds what the refresh keeps storing: the index plus every
watched company (a reader's dashboard and earnings-day alerts read those rows). Run it once at
rollout, before (or just after) flipping the flag.

Membership comes from the committed app/data/index_membership.json via index_membership_service.
HARD SAFETY: if that list is missing/short (< SANITY_FLOOR), the script REFUSES to run — purging
"non-members" against an empty set would delete the entire calendar.

Usage:
    # Dry run (default) — prints counts + a sample of what would be deleted, changes nothing
    python scripts/purge_non_index_earnings.py

    # Apply
    python scripts/purge_non_index_earnings.py --execute
"""
import argparse
import logging
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import EarningsEvent
from app.services import earnings_calendar_service, index_membership_service

logger = logging.getLogger(__name__)


def purge(session, *, dry_run: bool = True, members=None) -> dict:
    """Delete EarningsEvent rows whose ticker is neither in the index universe nor on a watchlist.

    Returns ``{"total": n, "deleted": n, "kept": n}`` (``deleted`` is the would-delete count on a dry
    run). Mutates/commits only when ``dry_run=False``. Raises ValueError if the member set is too
    small to be trustworthy — never deletes against an unhealthy list.
    """
    if members is None:
        members = index_membership_service.member_tickers()
    if len(members) < index_membership_service.SANITY_FLOOR:
        raise ValueError(
            f"member set has {len(members)} < {index_membership_service.SANITY_FLOOR} tickers; "
            "refusing to purge (this would delete most/all of the calendar). Fix "
            "index_membership.json first."
        )

    # What the refresh keeps storing with the filter on (earnings_calendar_service._admitted_tickers),
    # compared in one spelling: an event's ticker is Alpha Vantage's (BRK.B), a company's is SEC's (BRK-B).
    kept_tickers = (
        frozenset(index_membership_service.normalize_ticker(t) for t in members)
        | earnings_calendar_service.watched_tickers(session)
    )
    outside = index_membership_service.canonical_ticker_sql(EarningsEvent.ticker).notin_(kept_tickers)
    total = session.query(EarningsEvent).count()
    to_delete = session.query(EarningsEvent).filter(outside).count()
    kept = total - to_delete
    sample = [
        t for (t,) in session.query(EarningsEvent.ticker)
        .filter(outside)
        .distinct()
        .order_by(EarningsEvent.ticker.asc())
        .limit(40)
        .all()
    ]
    logger.info(
        "earnings_events: total=%d  kept=%d  to delete=%d  (members in universe: %d, kept tickers with the watched: %d)",
        total, kept, to_delete, len(members), len(kept_tickers),
    )
    logger.info("sample tickers to delete (outside the index, unwatched): %s", ", ".join(sample) or "-")

    if dry_run:
        logger.info("Dry run complete. Run with --execute to delete %d rows.", to_delete)
        return {"total": total, "deleted": to_delete, "kept": kept}

    deleted = session.query(EarningsEvent).filter(outside).delete(synchronize_session=False)
    session.commit()
    logger.info("Purge applied: deleted %d rows outside the index that nobody watches, kept %d.", deleted, kept)
    return {"total": total, "deleted": int(deleted or 0), "kept": kept}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete earnings rows outside the S&P 500 / Nasdaq 100 universe."
    )
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete (default is dry run).")
    args = parser.parse_args()

    dry_run = not args.execute
    logger.info("Running in %s mode", "DRY RUN" if dry_run else "EXECUTE")

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        purge(session, dry_run=dry_run)
        return 0
    except ValueError as exc:
        logger.error("Aborting: %s", exc)
        return 2
    except Exception:
        logger.exception("Purge failed; rolling back")
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
