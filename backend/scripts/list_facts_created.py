#!/usr/bin/env python3
"""List ``financial_fact`` rows created inside a time window (read-only review aid).

Written for the W3-9 review: the first production run of ``audit_reconciliation_flags.py --apply``
(2026-09-08, before its flags-only mode existed) also inserted 78 fact rows through the normal
backfill path, and the founder needs to see exactly which rows those are. Prints one JSON line
per row (ticker, accession, form, concept, period, unit, value, source, reconciled, is_latest,
created_at), oldest first, then one summary line with the row count. Nothing is written: no
commit, no job-ledger heartbeat.

Timestamps are ISO 8601; a trailing ``Z`` or an offset is accepted, a naive value is read as UTC.

Founder command (the DB is only reachable from Cloud Run — see docs/DEPLOYMENT.md):
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args="scripts/list_facts_created.py,--since,2026-09-08T05:25:00Z,--until,2026-09-08T05:40:00Z" --wait

Local usage:
  python scripts/list_facts_created.py --since 2026-09-08T05:25:00Z --until 2026-09-08T05:40:00Z
  python scripts/list_facts_created.py --since 2026-09-08 --limit 50
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

# Make the backend root importable as `app.*` when run directly (see retention_purge.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def parse_utc(value: str) -> datetime:
    """ISO 8601 → aware UTC datetime; ``Z`` accepted, a naive value is taken as UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _main(*, since: datetime, until: datetime | None, limit: int | None) -> int:
    from app.database import SessionLocal
    from app.models import Company, FinancialFact
    from app.utils.datetimes import ensure_utc, iso_z

    db = SessionLocal()
    try:
        query = (
            db.query(FinancialFact, Company.ticker)
            .join(Company, FinancialFact.company_id == Company.id)
            .filter(FinancialFact.created_at >= since)
        )
        if until is not None:
            query = query.filter(FinancialFact.created_at < until)
        query = query.order_by(FinancialFact.created_at.asc(), FinancialFact.id.asc())
        if limit:
            query = query.limit(limit)
        count = 0
        for fact, ticker in query.all():
            # SQLite hands back a naive UTC value, PostgreSQL an aware one in the session's zone;
            # both print as the ``Z`` form the docstring promises.
            created = (
                ensure_utc(fact.created_at).astimezone(timezone.utc)
                if fact.created_at is not None else None
            )
            print(json.dumps({
                "id": fact.id,
                "ticker": ticker,
                "accession": fact.accession,
                "form": fact.form,
                "concept": fact.concept,
                "fiscal_year": fact.fiscal_year,
                "fiscal_period": fact.fiscal_period,
                "period_end": fact.period_end.isoformat() if fact.period_end else None,
                "unit": fact.unit,
                "value": float(fact.value),
                "source": fact.source,
                "reconciled": bool(fact.reconciled),
                "is_latest": bool(fact.is_latest),
                "created_at": iso_z(created) if created else None,
            }, sort_keys=True))
            count += 1
        print(json.dumps({
            "rows": count,
            "since": iso_z(since),
            "until": iso_z(until) if until else None,
            "limit": limit,
        }, sort_keys=True))
        return count
    finally:
        db.rollback()  # read-only: never leave a transaction open, never commit
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="List financial_fact rows created in a time window (read-only)."
    )
    parser.add_argument("--since", required=True, type=parse_utc, help="Inclusive ISO 8601 start.")
    parser.add_argument("--until", type=parse_utc, default=None, help="Exclusive ISO 8601 end.")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to print.")
    args = parser.parse_args()
    _main(since=args.since, until=args.until, limit=args.limit)
