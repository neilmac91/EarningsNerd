"""Search names the filing a pick lands on (2026-10 design critique, homepage 1d).

Each result carries ``latest_filing``: the newest stored filing of the forms the company's filings
list serves that still stands (not superseded), with whether its summary is ready. The listbox's
second line is the filing identity strip, so the visitor picks the right company already knowing
which filing they will land on. DB-only: the rows the filings list already serves, no SEC call.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.models import Company, Filing, Summary
from app.services.edgar.compat import SECEdgarServiceCompat, sec_edgar_service
from app.services.latest_filing_service import company_list_forms
from main import app

CIK = "0000320193"
TICKERS = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}


def _at(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=timezone.utc)


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


def _purge(db) -> None:
    company = db.query(Company).filter(Company.cik.in_([CIK, CIK.lstrip("0")])).first()
    if company is not None:
        filing_ids = [f.id for f in db.query(Filing).filter(Filing.company_id == company.id).all()]
        if filing_ids:
            db.query(Summary).filter(Summary.filing_id.in_(filing_ids)).delete(synchronize_session=False)
            db.query(Filing).filter(Filing.id.in_(filing_ids)).delete(synchronize_session=False)
        db.delete(company)
    db.commit()


@pytest.fixture(autouse=True)
def clean_rows(db):
    db.rollback()
    _purge(db)
    yield
    db.rollback()
    _purge(db)


@pytest.fixture(autouse=True)
def fixture_tickers(monkeypatch):
    async def fake_tickers():
        return TICKERS

    async def fake_quote(ticker):
        return None

    monkeypatch.setattr(sec_edgar_service, "_get_cached_tickers", fake_tickers)
    SECEdgarServiceCompat._primary_map = None
    SECEdgarServiceCompat._primary_map_built_at = None
    import app.routers.companies as companies_router

    monkeypatch.setattr(companies_router, "_get_stock_quote_with_timeout", fake_quote)
    monkeypatch.setattr(companies_router, "get_stock_quote", fake_quote)


def _seed(db, rows: list[tuple[str, str, str | None, str | None]], summaries: dict[int, str] | None = None) -> dict[int, int]:
    """Filings as (form, filed, period end, superseded_by); summaries by row index."""
    company = Company(cik=CIK, ticker="AAPL", name="Apple Inc.", exchange="Nasdaq")
    db.add(company)
    db.flush()
    ids: dict[int, int] = {}
    for i, (form, filed, period, superseded_by) in enumerate(rows):
        filing = Filing(
            company_id=company.id,
            accession_number=f"0000320193-26-{i:06d}",
            filing_type=form,
            filing_date=_at(filed),
            period_end_date=_at(period) if period else None,
            superseded_by_accession=superseded_by,
            sec_url=f"https://www.sec.gov/Archives/edgar/data/320193/00003201932600000{i}/",
            document_url=f"https://www.sec.gov/Archives/edgar/data/320193/00003201932600000{i}/doc.htm",
        )
        db.add(filing)
        db.flush()
        ids[i] = filing.id
    for i, body in (summaries or {}).items():
        db.add(Summary(filing_id=ids[i], business_overview=body))
    db.commit()
    return ids


def _search(client) -> dict:
    resp = client.get("/api/companies/search", params={"q": "aapl"})
    assert resp.status_code == 200
    rows = [r for r in resp.json() if r["ticker"] == "AAPL"]
    assert len(rows) == 1
    return rows[0]


def test_names_the_newest_standing_filing_and_its_summary_readiness(client, db):
    ids = _seed(
        db,
        [("10-K", "2025-10-31", "2025-09-27", None), ("10-Q", "2026-01-30", "2025-12-27", None)],
        summaries={1: "Apple designs devices."},
    )
    latest = _search(client)["latest_filing"]
    assert latest == {
        "id": ids[1],
        "filing_type": "10-Q",
        "filing_date": latest["filing_date"],
        "report_date": latest["report_date"],
        "summary_ready": True,
    }
    # The filings list's own serialization, so the client formats both the same way.
    assert latest["filing_date"].startswith("2026-01-30")
    assert latest["report_date"].startswith("2025-12-27")


def test_a_placeholder_summary_is_not_ready(client, db):
    _seed(db, [("10-Q", "2026-01-30", "2025-12-27", None)], summaries={0: "Generating summary..."})
    assert _search(client)["latest_filing"]["summary_ready"] is False


def test_skips_superseded_filings_and_forms_the_list_does_not_serve(client, db):
    ids = _seed(
        db,
        [
            ("10-K", "2025-10-31", "2025-09-27", None),
            ("10-Q", "2026-01-30", "2025-12-27", "0000320193-26-000009"),  # superseded by an amendment
            ("8-K", "2026-02-02", "2026-02-01", None),  # not in the company list's forms
        ],
    )
    latest = _search(client)["latest_filing"]
    assert latest["id"] == ids[0]
    assert latest["filing_type"] == "10-K"
    assert latest["summary_ready"] is False


def test_absent_when_no_filing_is_stored(client, db):
    assert _search(client)["latest_filing"] is None


def test_the_list_and_the_search_share_one_form_set(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    domestic = company_list_forms()
    assert "10-K" in domestic and "10-Q/A" in domestic and "20-F" not in domestic
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    assert {"20-F", "6-K", "40-F"} <= set(company_list_forms())
