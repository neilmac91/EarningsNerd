#!/usr/bin/env python3
"""
Reset a single filing's generated summary (per-filing, NOT reset-all).

Deletes ONE filing's ``Summary`` row (and its ``SummaryGenerationProgress``) so the lazy
regeneration path rebuilds it with the CURRENT prompts on the next view. XBRL data and the
filing content cache are KEPT (unchanged by a prompt edit), so regeneration stays fast and does
not re-fetch from SEC. This is the targeted counterpart to the admin ``/summaries/reset-all``
endpoint — used by the data-quality remediation to regenerate exactly the JPM 10-K after the
P0-4 bank-prompt carve-out deploy, without clearing every summary.

FK-safe: a Summary pinned by a ``saved_summaries`` bookmark is SKIPPED by default (deleting it
would violate the Postgres FK and orphan the bookmark). Pass ``--include-saved`` to drop the
bookmark too. Dry-run is the DEFAULT; nothing is written without ``--execute``.

Usage:
    # Dry run (default) — report what would be reset
    python scripts/reset_filing_summary.py --ticker JPM --form 10-K

    # Actually delete JPM's 10-K summary so it regenerates on next view
    python scripts/reset_filing_summary.py --ticker JPM --form 10-K --execute
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Company, Filing, SavedSummary, Summary, SummaryGenerationProgress

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def find_summaries(session, ticker: str, form: str):
    """Return (summary_id, filing_id) rows for a ticker's filings of one form that HAVE a summary."""
    q = (
        session.query(Summary.id, Summary.filing_id)
        .join(Filing, Filing.id == Summary.filing_id)
        .join(Company, Company.id == Filing.company_id)
        .filter(Company.ticker == ticker.upper())
    )
    if form:
        q = q.filter(Filing.filing_type == form)
    return q.all()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Reset a single filing's summary (per-filing).")
    parser.add_argument("--ticker", required=True, help="Company ticker, e.g. JPM")
    parser.add_argument("--form", default="10-K", help="Filing form (default: 10-K). Blank = all forms.")
    parser.add_argument("--execute", action="store_true", help="Apply (default is a dry run).")
    parser.add_argument(
        "--include-saved",
        action="store_true",
        help="Also drop saved_summaries bookmarks pinning the matched summaries (else they are skipped).",
    )
    args = parser.parse_args(argv)

    session = SessionLocal()
    try:
        rows = find_summaries(session, args.ticker, args.form)
        if not rows:
            logger.info("No summary rows matched ticker=%s form=%s — nothing to reset.", args.ticker, args.form)
            return 0

        summary_ids = [sid for (sid, _fid) in rows]
        filing_ids = sorted({fid for (_sid, fid) in rows})

        pinned = {
            sid
            for (sid,) in session.query(SavedSummary.summary_id)
            .filter(SavedSummary.summary_id.in_(summary_ids))
            .all()
        }
        to_delete = [sid for sid in summary_ids if args.include_saved or sid not in pinned]
        skipped = [sid for sid in summary_ids if not args.include_saved and sid in pinned]

        logger.info(
            "ticker=%s form=%s — matched %d summary row(s) across filing(s) %s; will delete %d, skip %d saved.",
            args.ticker, args.form, len(summary_ids), filing_ids, len(to_delete), len(skipped),
        )
        if skipped:
            logger.info("Skipped (saved/pinned) summary ids: %s (pass --include-saved to reset).", skipped)

        if not args.execute:
            logger.info("DRY RUN — nothing written. Re-run with --execute to apply.")
            return 0
        if not to_delete:
            logger.info("Nothing to delete (all matched summaries are pinned). No changes.")
            return 0

        if args.include_saved:
            session.query(SavedSummary).filter(SavedSummary.summary_id.in_(to_delete)).delete(
                synchronize_session=False
            )
        # Clear progress ONLY for filings whose summary is actually being deleted — a skipped
        # (pinned) summary keeps its Summary row, so its progress must be kept too, else it is left
        # in an inconsistent state (mirrors admin reset_all's delete_filing_ids). XBRL + content
        # cache are intentionally kept so regeneration stays fast.
        to_delete_set = set(to_delete)
        filing_ids_to_delete = {fid for (sid, fid) in rows if sid in to_delete_set}
        session.query(SummaryGenerationProgress).filter(
            SummaryGenerationProgress.filing_id.in_(filing_ids_to_delete)
        ).delete(synchronize_session=False)
        session.query(Summary).filter(Summary.id.in_(to_delete)).delete(synchronize_session=False)
        session.commit()
        logger.info(
            "APPLIED — deleted %d summary row(s) for ticker=%s form=%s. They regenerate lazily on next view.",
            len(to_delete), args.ticker, args.form,
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
