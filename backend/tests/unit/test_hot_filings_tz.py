"""Regression tests for hot_filings timezone handling.

filing_date is DateTime(timezone=True), so Postgres returns tz-aware datetimes while SQLite
returns naive ones. The scoring loop computes ``now - filing.filing_date`` with the aware
``utcnow()``; mixing awareness raised "can't subtract offset-naive and offset-aware datetimes"
(500 on GET /api/hot_filings). ``_to_aware_utc`` normalizes both sides to aware UTC. These
tests pin the fix.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.hot_filings import HotFilingsService, _to_aware_utc


def _make_filing(filing_date):
    company = SimpleNamespace(ticker="AAPL", name="Apple Inc.")
    # company_id=None keeps the secondary search/velocity queries (and the FMP/
    # Finnhub network calls) skipped, so the real scoring loop runs unmocked.
    return SimpleNamespace(
        id=1,
        company_id=None,
        company=company,
        filing_type="10-K",
        filing_date=filing_date,
    )


def _stub_db(filings):
    db = MagicMock()
    (
        db.query.return_value
        .options.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = filings
    return db


def test_to_aware_utc_passes_aware_through():
    aware = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    assert _to_aware_utc(aware) == datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    assert _to_aware_utc(aware).tzinfo is not None


def test_to_aware_utc_attaches_utc_to_naive():
    naive = datetime(2026, 6, 18, 12, 0)
    assert _to_aware_utc(naive) == datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    assert _to_aware_utc(naive).tzinfo is timezone.utc


def test_calculate_hot_filings_with_tz_aware_filing_date_does_not_crash():
    svc = HotFilingsService()
    svc._fmp_client = None
    svc._news_client = None

    aware_date = datetime.now(timezone.utc) - timedelta(hours=12)
    db = _stub_db([_make_filing(aware_date)])

    records = asyncio.run(svc._calculate_hot_filings(db, limit=10))

    assert len(records) == 1
    # Recent (12h old) filing must earn a positive recency-driven buzz score.
    assert records[0].buzz_score > 0
