"""Interim safeguards 1+2 (data-quality plan Part 3): company miss-paths are CIK-first.

A ticker lookup can miss while the CIK already has a row — the stored ticker was overwritten to
a preferred share class (e.g. JPMorgan persisted as JPM-PM). Pre-fix, all three miss-path sites
(`companies.get_company`, `filings.get_company_filings`, `precompute.precompute_one`)
blind-inserted a second row for the same CIK and the unique constraint surfaced as an HTTP 500
on routine page views. These tests pin the fixed behavior: reuse-by-CIK (one row, 200, no ticker
rewrite — canonicalization is P0-1's job), and the SAVEPOINT + re-query race path with its
`company_upsert_conflict` structured log line (interim safeguard 2).
"""

import logging

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Company
from app.services import precompute_service
from app.services.company_resolution import resolve_or_create_company_by_cik
from app.services.edgar.compat import sec_edgar_service
from main import app

JPM_CIK = "0000019617"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def seeded_jpm(db):
    """A JPMorgan row persisted under a preferred-class ticker — the corrupted prod state."""
    db.query(Company).filter(Company.cik == JPM_CIK).delete()
    db.commit()
    company = Company(cik=JPM_CIK, ticker="JPM-PM", name="JPMORGAN CHASE & CO")
    db.add(company)
    db.commit()
    db.refresh(company)
    yield company
    db.query(Company).filter(Company.cik == JPM_CIK).delete()
    db.commit()


def _jpm_sec_results():
    return [
        {"cik": JPM_CIK, "ticker": "JPM", "name": "JPMORGAN CHASE & CO", "exchange": None}
    ]


def test_get_company_reuses_existing_cik_row(client, db, seeded_jpm, monkeypatch):
    """GET /api/companies/JPM with the row stored as JPM-PM: 200 + reuse, never a 500 insert."""

    async def fake_search(query):
        return _jpm_sec_results()

    async def fake_quote(ticker):
        return None

    monkeypatch.setattr(sec_edgar_service, "search_company", fake_search)
    import app.routers.companies as companies_router

    monkeypatch.setattr(companies_router, "get_stock_quote", fake_quote)

    resp = client.get("/api/companies/JPM")
    assert resp.status_code == 200
    assert resp.json()["cik"] == JPM_CIK
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


def test_get_company_filings_reuses_existing_cik_row(client, db, seeded_jpm, monkeypatch):
    """GET /api/filings/company/JPM with the row stored as JPM-PM: 200 + reuse, single row."""

    async def fake_search(query):
        return _jpm_sec_results()

    async def fake_get_filings(cik, filing_types=None, limit=None):
        return []

    monkeypatch.setattr(sec_edgar_service, "search_company", fake_search)
    monkeypatch.setattr(sec_edgar_service, "get_filings", fake_get_filings)

    resp = client.get("/api/filings/company/JPM")
    assert resp.status_code == 200
    assert resp.json() == []
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


@pytest.mark.asyncio
async def test_precompute_reuses_existing_cik_row(db, seeded_jpm, monkeypatch):
    """precompute_one on a ticker-miss resolves the existing CIK row instead of inserting."""

    async def fake_search(query):
        return _jpm_sec_results()

    async def fake_get_filings(cik, filing_types=None, limit=None):
        return []

    monkeypatch.setattr(sec_edgar_service, "search_company", fake_search)
    monkeypatch.setattr(sec_edgar_service, "get_filings", fake_get_filings)

    result = await precompute_service.precompute_one("JPM", "10-K")
    assert result["status"] == "no_filings"
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


def test_integrity_race_reuses_row_and_logs(db, seeded_jpm, caplog, monkeypatch):
    """The concurrent-insert race: initial lookup misses, insert clashes on unique-CIK, the
    SAVEPOINT confines the failure, the re-query returns the winner, and the structured
    `company_upsert_conflict` line (cik + path) is emitted for the log-based alert."""
    real_query = db.query
    state = {"missed": False}

    def flaky_query(*args, **kwargs):
        # First Company lookup misses, simulating the race window between check and insert.
        if not state["missed"] and args and args[0] is Company:
            state["missed"] = True

            class _Miss:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return _Miss()
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db, "query", flaky_query)

    with caplog.at_level(logging.WARNING):
        company = resolve_or_create_company_by_cik(
            db, cik=JPM_CIK, ticker="JPM", name="JPMORGAN CHASE & CO", path="test.race"
        )

    assert company.id == seeded_jpm.id
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "company_upsert_conflict" in m and JPM_CIK in m and "test.race" in m for m in messages
    )
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


def test_cik_forms_matching_is_padding_insensitive(db, seeded_jpm):
    """Defensive hardening: a stripped-form CIK resolves the padded-form row (no duplicate)."""
    company = resolve_or_create_company_by_cik(
        db, cik="19617", ticker="JPM", name="JPMORGAN CHASE & CO", path="test.padding"
    )
    assert company.id == seeded_jpm.id
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1
