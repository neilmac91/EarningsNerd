"""Read retained invoice-payment observations; never call Stripe or extrapolate ARR.

Run from backend: python scripts/billing_revenue_report.py --since 2026-09-01 --until 2026-10-01
The interval is [since, until), in UTC for date-only arguments. --test-mode excludes live data.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.services.billing_revenue_service import payment_report  # noqa: E402


def _date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=_date, required=True)
    parser.add_argument("--until", type=_date, required=True)
    parser.add_argument("--test-mode", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        report = payment_report(db, args.since, args.until, livemode=not args.test_mode)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
