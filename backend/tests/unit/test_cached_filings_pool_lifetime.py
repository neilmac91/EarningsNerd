"""Completed filing reads release slots before asynchronous dependency cleanup."""

import asyncio
import time
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import Company, Filing, FilingContentCache, FinancialFact, Summary, SummaryGenerationProgress
from app.routers import filings
from app.services import filing_list_service
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
    ("/api/summaries/filing/1/what-changed", "what_changed"),
    ("/api/summaries/filing/999/what-changed", "missing"),
    ("/api/summaries/filing/1", "summary"),
    ("/api/summaries/filing/999", "no_summary"),
    ("/api/summaries/filing/1/progress", "progress_completed"),
    ("/api/summaries/filing/1/progress", "progress_stalled"),
    ("/api/summaries/filing/999/progress", "progress_pending"),
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
    Summary.__table__.create(engine)
    SummaryGenerationProgress.__table__.create(engine)
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
        if payload_kind in ("summary", "progress_completed"):
            db.add(Summary(filing_id=filing.id, business_overview="## Overview", raw_summary={}))
        if payload_kind == "progress_stalled":
            stalled_at = utcnow() - timedelta(hours=1)
            db.add(SummaryGenerationProgress(filing_id=filing.id, stage="analyzing",
                                             started_at=stalled_at, updated_at=stalled_at))
        db.commit()

    async def unexpected_upstream(*_args, **_kwargs):
        pytest.fail("Cached filing burst must not request SEC data")

    request_sessions: list[Session] = []

    class RequestSession(Session):
        """Records, at each close, whether the session still held a transaction (a pooled connection)."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.open_at_close: list[bool] = []
            request_sessions.append(self)

        def close(self) -> None:
            self.open_at_close.append(self.in_transaction())
            super().close()

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    monkeypatch.setattr(filings.sec_edgar_service, "get_filings", unexpected_upstream)
    filing_list_service._mark_filings_synced("CACHED", expand_amendment_forms(["10-K", "10-Q"]))
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
                    "reconciled": True, "provenance": {
                        "version": 1, "method": "reported", "validation": "passed",
                        "reasons": [], "formula": None, "inputs": [],
                        "calculation_version": None, "filed_at": None,
                        "source_url": "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/",
                    },
                }]}] if payload_kind == "facts" else []
                assert payload == {"ticker": "CACHED", "company_name": "Cached fixture", "concepts": concepts}
            elif payload_kind == "what_changed":
                # The change report: lookup, report and release in one unit off the event loop.
                assert payload["has_prior"] is False and payload["prior_filing"] is None
                assert payload["section_changes"] is None  # ENABLE_SECTION_CHANGES is off
            elif payload_kind == "summary":
                # The Trace-to-Source read: lookups, enrichment and release in one unit off the event loop.
                assert (payload["id"], payload["filing_id"], payload["business_overview"]) == (1, 1, "## Overview")
            elif payload_kind == "no_summary":
                assert (payload["id"], payload["filing_id"], payload["raw_summary"]) == (0, 999, None)
            elif payload_kind == "progress_completed":
                assert payload == {"stage": "completed", "elapsedSeconds": 0}
            elif payload_kind == "progress_stalled":
                # The heartbeat's write (an orphaned row becomes a retryable error) is in the same unit.
                assert (payload["stage"], payload["error"]) == (
                    "error", "Generation stalled and was abandoned. Please retry.")
            elif payload_kind == "progress_pending":
                assert payload == {"stage": "pending", "elapsedSeconds": 0}
            else:
                assert payload == {"detail": "Filing not found"}
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [session.open_at_close[-1:] for session in request_sessions] == [[False]] * 8
        if payload_kind == "progress_stalled":
            with sessions() as db:
                assert db.get(SummaryGenerationProgress, 1).stage == "error"
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_what_changed_burst_beyond_the_pool_waits_in_the_threadpool_not_on_the_loop(monkeypatch, tmp_path):
    """The what-changed route holds a connection through CPU work (the wording diff). Six
    concurrent readers on four slots must queue for a slot off the event loop: with the lookup on
    the loop, the fifth reader blocked the loop for the whole pool timeout and answered 500 while
    the first four could not finish."""
    from app.services import change_report_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'what-changed.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000002", ticker="BURST", name="Burst fixture", history_backfilled_at=utcnow())
        db.add(company)
        db.flush()
        db.add(Filing(company_id=company.id, accession_number="0000000002-26-000001", filing_type="10-K",
                      filing_date=utcnow(), sec_url="https://example.test/burst/", document_url="https://example.test/burst.htm"))
        db.commit()

    def slow_report(db, filing, *, section_access):
        time.sleep(0.15)  # the largest corpus pair's diff
        return {"has_prior": False, "section_changes": None, "filing_id": filing.id}

    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(change_report_service, "build_change_report", slow_report)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(*[client.get("/api/summaries/filing/1/what-changed") for _ in range(6)])
        assert [response.status_code for response in responses] == [200] * 6
        assert all(response.json()["filing_id"] == 1 for response in responses)
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
