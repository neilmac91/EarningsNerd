#!/usr/bin/env python3
"""Preview missing committed-universe Company identities; --apply writes, never generates AI.

Run from backend: python scripts/seed_universe_companies.py [--apply] [--limit 100]
Production writes require the founder's explicit job trigger. Run SIC backfill afterwards.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main(*, apply: bool = False, limit: int | None = None) -> None:
    from app.services.job_run_service import track_job
    from app.services.universe_seed_service import seed_universe_companies

    with track_job("universe-company-seed", dry_run=not apply) as attempt:
        stats = await seed_universe_companies(apply=apply, limit=limit)
        attempt.record(stats)
        print(json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write missing Company rows (default previews).")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    asyncio.run(main(apply=args.apply, limit=args.limit))
