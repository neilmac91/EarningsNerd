"""Completed filing reads release slots before asynchronous dependency cleanup."""

import asyncio
from datetime import date

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import Company, Filing, FilingContentCache, FinancialFact
from app.routers import filings
from app.services.filing_amendment_service import expand_amendment_forms
from app.utils.datetimes import utcnow
from main import app


@pytest.mark.asyncio
@pytest.mark.parametrize("path,payload_kind", [
    ("/api/filings/company/CACHED?filing_types=10-K,10-Q", "list"),
    ("/api/filings/1", "filing"),
    ("/api/filings/recent/latest", "list"),
    ("/api/filings/1/content", "content"),
    ("/api/filings/1/content", "empty_content"),
    ("/api/filings/1/fundamentals", "facts"),
    ("/api/filings/1/fundamentals", "empty_facts"),
    ("/api/filings/999", "missing"),
    ("/api/filings/999/content", "missing"),
    ("/api/filings/999/fundamentals", "missing"),
])
async def test_cached_filings_burst_exceeding_pool_finishes_without_upstream(
    monkeypatch, tmp_path, path, payload_kind
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cached-filings.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=0.05,
    )
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    FilingContentCache.__table__.create(engine)
    FinancialFact.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    accession = "0000000001-26-000001"
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture",
                          history_backfilled_at=utcnow())
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number=accession,
                        filing_type="10-K", filing_date=utcnow(),
                        sec_url="https://example.test/filing/", document_url="https://example.test/filing.htm")
        db.add(filing)
        db.flush()
        if payload_kind == "content":
            db.add(FilingContentCache(filing_id=filing.id, markdown_content="# Synthetic filing"))
        if payload_kind == "facts":
            db.add(FinancialFact(
                company_id=company.id, filing_id=filing.id, concept="revenue", unit="USD",
                period_end=date(2025, 12, 31), fiscal_year=2025, fiscal_period="FY", value=123,
                form="10-K", accession=accession, reconciled=True,
            ))
        db.commit()

    async def unexpected_upstream(*_args, **_kwargs):
        pytest.fail("Cached filing burst must not request SEC data")

    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(filings, "_filings_synced_at", {})
    monkeypatch.setattr(filings.sec_edgar_service, "get_filings", unexpected_upstream)
    filings._mark_filings_synced("CACHED", expand_amendment_forms(["10-K", "10-Q"]))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(*[client.get(path) for _ in range(8)])
        assert [response.status_code for response in responses] == [404 if payload_kind == "missing" else 200] * 8
        for response in responses:
            payload = response.json()
            if payload_kind == "list":
                assert [row["accession_number"] for row in payload] == [accession]
            elif payload_kind == "filing":
                assert payload["accession_number"] == accession
            elif payload_kind in ("content", "empty_content"):
                assert payload == {
                    "filing_id": 1, "has_content": payload_kind == "content",
                    "markdown_content": "# Synthetic filing" if payload_kind == "content" else None,
                }
            elif payload_kind in ("facts", "empty_facts"):
                concepts = [{"concept": "revenue", "unit": "USD", "points": [{
                    "period_end": "2025-12-31", "fiscal_year": 2025, "fiscal_period": "FY",
                    "value": 123.0, "unit": "USD", "form": "10-K", "accession": accession,
                    "reconciled": True,
                }]}] if payload_kind == "facts" else []
                assert payload == {"ticker": "CACHED", "company_name": "Cached fixture", "concepts": concepts}
            else:
                assert payload == {"detail": "Filing not found"}
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
