"""E100: each writer of a new filing row hands the ORM aware UTC dates.

SEC listings give bare dates (``2026-01-15``). Parsed naive and bound to the ``DateTime(timezone=True)``
columns, they are read by PostgreSQL in the session's ``TimeZone``, so a filing dated the 15th is stored as
UTC midnight, which the digest window counts on (``filing_scan_service._window_start``), only while that
setting is UTC. SQLite drops the zone either way, so each case reads the values the writer handed the ORM as
the row was inserted (``before_insert`` on ``Filing``), not the row read back. The history backfill and the
company list's background refresh write through ``upsert_filings``.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing

FILED = datetime(2026, 1, 15, tzinfo=timezone.utc)
PERIOD_END = datetime(2025, 12, 31, tzinfo=timezone.utc)


def _listing(accession: str) -> dict:
    """One row of an SEC listing, as ``sec_edgar_service.get_filings`` returns it."""
    return {
        "accession_number": accession,
        "filing_type": "10-K",
        "filing_date": "2026-01-15",
        "report_date": "2025-12-31",
        "sec_url": f"https://sec.example/{accession}/",
        "document_url": f"https://sec.example/{accession}/a.htm",
    }


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'filing-dates.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(**{**database.SessionLocal.kw, "bind": engine})
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def inserted():
    """The (filing_date, period_end_date) each new Filing row carries as it is inserted."""
    seen: list[tuple[datetime, datetime]] = []

    def record(mapper, connection, target):
        seen.append((target.filing_date, target.period_end_date))

    event.listen(Filing, "before_insert", record)
    yield seen
    event.remove(Filing, "before_insert", record)


def _company(sessions) -> tuple[int, str]:
    with sessions() as db:
        company = Company(cik="1", ticker="EHUND", name="E100 Corp")
        db.add(company)
        db.commit()
        return company.id, company.ticker


def _assert_aware_utc(inserted) -> None:
    assert inserted == [(FILED, PERIOD_END)]  # a naive value never equals an aware one
    assert all(value.utcoffset() == timedelta(0) for value in inserted[0])


def test_the_scan_upsert_writes_aware_utc_dates(sessions, inserted):
    from app.services.filing_scan_service import upsert_filings

    company_id, _ = _company(sessions)
    with sessions() as db:
        upsert_filings(db, db.get(Company, company_id), [_listing("e100-scan")])
    _assert_aware_utc(inserted)


def test_the_scan_upsert_skips_a_row_it_cannot_date(sessions, inserted):
    """A listing row with no filing date (EdgarTools gives ``None`` for one it cannot parse) is skipped, as a
    malformed one is, and the rest of its batch is written. It used to raise ``TypeError`` past the skip and end
    the scan's run, before any later company."""
    from app.services.filing_scan_service import upsert_filings

    company_id, _ = _company(sessions)
    undated = {**_listing("e100-undated"), "filing_date": None}
    with sessions() as db:
        written = upsert_filings(db, db.get(Company, company_id), [undated, _listing("e100-dated")])
        assert [filing.accession_number for filing in written] == ["e100-dated"]
    _assert_aware_utc(inserted)


def test_the_live_listing_writes_aware_utc_dates(sessions, inserted, monkeypatch):
    from app.services import filing_list_service

    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    company_id, ticker = _company(sessions)
    with sessions() as db:
        filing_list_service.persist_live_filings(
            db, ticker, ["10-K"], company_id, [_listing("e100-list")], None, lambda filing: filing,
        )
    _assert_aware_utc(inserted)


def test_precompute_writes_aware_utc_dates(sessions, inserted, monkeypatch):
    from app.services.edgar.compat import sec_edgar_service
    from app.services.precompute_service import precompute_one

    _, ticker = _company(sessions)
    monkeypatch.setattr(sec_edgar_service, "get_filings", AsyncMock(return_value=[_listing("e100-precompute")]))
    monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", AsyncMock())
    result = asyncio.run(precompute_one(ticker, "10-K"))
    assert result["filing_id"] is not None
    _assert_aware_utc(inserted)
