"""Completed cached filing reads release slots before asynchronous dependency cleanup."""

import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import Company, Filing
from app.routers import filings
from app.services.filing_amendment_service import expand_amendment_forms
from app.utils.datetimes import utcnow
from main import app


@pytest.mark.asyncio
async def test_cached_filings_burst_exceeding_pool_finishes_without_upstream(monkeypatch, tmp_path):
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
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture",
                          history_backfilled_at=utcnow())
        db.add(company)
        db.flush()
        db.add(Filing(company_id=company.id, accession_number="0000000001-26-000001",
                      filing_type="10-K", filing_date=utcnow(),
                      sec_url="https://example.test/filing/", document_url="https://example.test/filing.htm"))
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
            responses = await asyncio.gather(*[
                client.get("/api/filings/company/CACHED?filing_types=10-K,10-Q") for _ in range(8)
            ])
        assert [response.status_code for response in responses] == [200] * 8
        assert all([row["accession_number"] for row in response.json()] == ["0000000001-26-000001"]
                   for response in responses)
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
