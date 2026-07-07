#!/usr/bin/env python3
"""Repair ``companies.ticker`` to the canonical primary listing per CIK (data-quality plan P0-1).

The pre-P0-1 search handler overwrote ``Company.ticker`` with the LAST SEC ticker-file entry
per CIK — preferred classes sort last, so e.g. JPMorgan persisted as ``JPM-PM`` and the site
served the preferred share's $17 quote as JPMorgan's stock price. This script recomputes the
primary (FIRST file-order) ticker per CIK from SEC's ``company_tickers.json`` — fetched once
through the edgar service layer — and reports/repairs every mismatched row.

HARD SEQUENCING (plan constraint 1): run only AFTER the P0-1 search-fix deploy is live —
an un-fixed /search would re-corrupt repaired rows on the next query.

Usage:
  python scripts/repair_ticker_by_cik.py           # dry run (default): report only, write nothing
  python scripts/repair_ticker_by_cik.py --apply   # write the repairs

Requirements (runs in prod / CI against Cloud SQL, e.g. via the ops workflow):
  - DATABASE_URL pointing at the target database
  - network access to www.sec.gov (paced by the shared SEC rate limiter)
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_primary_map(tickers_data: Dict[str, Any]) -> Dict[str, str]:
    """CIK (leading zeros stripped) -> primary ticker = FIRST file-order entry per CIK.

    Python dicts preserve the SEC file's insertion order; the common/primary listing appears
    first, preferred/secondary classes at higher indices (live-verified across all ~1,471
    multi-ticker CIKs — plan P0-1)."""
    primary: Dict[str, str] = {}
    for entry in tickers_data.values():
        if not isinstance(entry, dict):
            continue
        cik = str(entry.get("cik_str", "")).strip().lstrip("0") or "0"
        ticker = (entry.get("ticker") or "").strip()
        if cik and ticker and cik not in primary:
            primary[cik] = ticker
    return primary


def compute_changes(
    rows: List[Any], primary: Dict[str, str]
) -> Tuple[List[Tuple[Any, str]], List[Any]]:
    """(changes, not_in_file): rows whose ticker differs from their CIK's primary, and rows
    whose CIK is absent from the SEC file (delisted etc. — always left unchanged). CIKs match
    in both zero-padded and stripped forms (defensive; write paths store zero-padded)."""
    changes: List[Tuple[Any, str]] = []
    not_in_file: List[Any] = []
    for row in rows:
        cik_stripped = str(row.cik or "").strip().lstrip("0") or "0"
        target = primary.get(cik_stripped)
        if target is None:
            not_in_file.append(row)
        elif (row.ticker or "") != target:
            changes.append((row, target))
    return changes, not_in_file


async def _fetch_tickers() -> Dict[str, Any]:
    from app.services.edgar.compat import sec_edgar_service

    return await sec_edgar_service._get_cached_tickers()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Repair companies.ticker to the canonical primary listing per CIK."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the repairs. Default is a dry run that reports and writes NOTHING.",
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("SKIP_REDIS_INIT", "true")

    tickers_data = asyncio.run(_fetch_tickers())
    primary = build_primary_map(tickers_data)
    print(f"SEC ticker file: {len(tickers_data)} entries, {len(primary)} distinct CIKs")

    from app.database import SessionLocal
    from app.models import Company

    db = SessionLocal()
    try:
        rows = db.query(Company).order_by(Company.id).all()
        changes, not_in_file = compute_changes(rows, primary)
        unchanged = len(rows) - len(changes) - len(not_in_file)

        print(f"\ncompanies rows: {len(rows)} total | {unchanged} already canonical | "
              f"{len(changes)} to repair | {len(not_in_file)} not in SEC file (left unchanged)")

        if changes:
            print("\nRepairs (old -> new):")
            for row, target in changes:
                print(f"  id={row.id} cik={row.cik} {row.ticker!r} -> {target!r}  ({row.name})")

        if not_in_file:
            print("\nNot in SEC file (delisted/unknown — unchanged):")
            for row in not_in_file:
                print(f"  id={row.id} cik={row.cik} ticker={row.ticker!r}  ({row.name})")

        # Collision check: two DB rows converging on the same ticker would shadow each other in
        # every ticker-keyed lookup. Report loudly; never auto-resolve.
        new_ticker_by_id = {row.id: target for row, target in changes}
        post_repair = Counter(
            new_ticker_by_id.get(row.id, row.ticker) for row in rows
        )
        collisions = {t: n for t, n in post_repair.items() if t and n > 1}
        if collisions:
            print(f"\nWARNING — post-repair ticker collisions (rows sharing one ticker): {collisions}")

        if not args.apply:
            print("\nDRY RUN — nothing written. Re-run with --apply to write the repairs above.")
            return 0

        for row, target in changes:
            row.ticker = target
        db.commit()
        print(f"\nAPPLIED — {len(changes)} row(s) repaired.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
