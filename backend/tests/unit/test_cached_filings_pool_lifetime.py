"""Gate for lessons/ops-release-cached-filing-reads-before-yield.md: a request's pooled connection
goes back to the pool before its async route yields to the dependency's finalizer.

One rule, two halves in this one module:

- Behaviour: an eight-request burst against a four-slot pool, per listed route, must answer every
  request without a pool timeout, with no transaction left for the finalizer and no checkout on the
  event-loop thread; a six-reader what-changed burst
  with a slow wording diff must wait for its slots in the thread pool, not on the loop; the
  analysis stream must release its connection before its body streams, alone and in a burst; the
  generate stream's Pro force branch must read nothing its commit expired, so its one checkout is
  in the thread pool; each auth session route (logout signed in, with only the refresh cookie and
  with a dead one, logout-all, refresh, and a password login with the right password and a wrong
  one, which also holds no connection while it hashes), each watchlist route and its refusals, each analysis route
  and a refusal of each, the waitlist join and verification, the contact form and the feedback
  submit, the usage and subscription-status reads, Stripe checkout and the billing portal, the
  company lookup, search and trending list (eight racers for one new company's row included), the
  saved-summary routes, the upcoming calendar, the account routes (the profile edit, the alert
  preferences, the bell, the data export and the account deletion), the Copilot ask stream (a Pro
  and a Free question, a missing filing and the admission's three refusals), the summary exports (the PDF
  and the CSV, a Free reader's 403, and a missing summary's and filing's 404), the admin feedback triage and
  filing and summary maintenance routes (their 404s, and the bulk routes' dry and real runs) and the admin
  invite routes (the list, mint with and without mail, revoke and re-send, their 404s and 409s, and the
  re-send's 503 with invitation mail closed) must answer an eight-request burst with no checkout on the
  loop and nothing left for the finalizer; and the join, the contact form, the feedback submit and the
  invite mint and re-send must send their mails, the analysis and summary exports render, Stripe checkout and the
  portal make their Stripe calls, and the account deletion its Stripe cancellation and PostHog flush,
  with no connection out.
- Structure: an AST ratchet over every ``async def`` under ``app/routers/`` that receives a session
  fails, above that route's ceiling, a session call on the loop in the route's own body, the session
  handed to a call there, a ``with`` it enters there, or a call there of a nested unit that uses it,
  so a route the burst does not list cannot add one unseen in a form the ratchet counts. Its gaps are
  under its section below.
"""

import ast
import asyncio
import threading
import time
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IllegalStateChangeError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import (
    Company, EarningsEvent, Filing, FilingContentCache, FinancialFact, NotableFiling, Summary,
    SummaryGenerationProgress, WaitlistSignup,
)
from app.models.earnings import STATUS_REPORTED
from app.routers import companies, filings, notable_filings, reporting_this_week, watchlist
from app.services import filing_list_service, notable_filings_service, reporting_this_week_service
from app.services.filing_amendment_service import expand_amendment_forms
from app.services.rate_limiter import RateLimiter
from app.utils.datetimes import utcnow
from main import app

# Exercise existing collection behavior with an explicitly published synthetic operator notice.
pytestmark = pytest.mark.usefixtures("collection_ready")


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
    ("/api/companies/CACHED/peers", "peers"),
    ("/api/companies/NOSUCH/peers", "missing_company"),
    ("/api/waitlist/stats", "waitlist_stats"),
    ("/api/waitlist/status/reader@example.com", "waitlist_status"),
    ("/api/waitlist/status/nobody@example.com", "waitlist_missing"),
    ("/api/notable_filings", "notable"),
    ("/api/reporting_this_week", "reporting"),
])
async def test_cached_filings_burst_exceeding_pool_finishes_without_upstream(
    monkeypatch, tmp_path, path, payload_kind
):
    # Readers beyond the four slots queue for one inside their worker thread, so the timeout must
    # outlast four units of work under a loaded CI host. An on-loop checkout still fails at any
    # timeout: it blocks the loop for the whole wait, so the four holders' finalizers never run.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cached-filings.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    FilingContentCache.__table__.create(engine)
    FinancialFact.__table__.create(engine)
    Summary.__table__.create(engine)
    SummaryGenerationProgress.__table__.create(engine)
    WaitlistSignup.__table__.create(engine)
    NotableFiling.__table__.create(engine)
    EarningsEvent.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    accession = "0000000001-26-000001"
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture",
                          history_backfilled_at=utcnow())
        db.add(company)
        db.flush()
        company_id = company.id
        filing = Filing(company_id=company.id, accession_number=accession,
                        filing_type="10-K", filing_date=utcnow(),
                        sec_url="https://example.test/filing/", document_url="https://example.test/filing.htm")
        db.add(filing)
        db.flush()
        if payload_kind == "content":
            db.add(FilingContentCache(filing_id=filing.id, markdown_content="# Synthetic filing"))
        if payload_kind in ("facts", "peers"):
            db.add(FinancialFact(
                company_id=company.id, filing_id=filing.id, concept="revenue", unit="USD",
                period_end=date(2025, 12, 31), fiscal_year=2025, fiscal_period="FY", value=123,
                form="10-K", accession=accession, reconciled=True,
            ))
        if payload_kind in ("summary", "progress_completed", "notable"):
            db.add(Summary(filing_id=filing.id, business_overview="## Overview", raw_summary={}))
        if payload_kind == "notable":
            # A 10-K candidate from the stored company, whose filing above holds a summary to open.
            db.add(NotableFiling(accession_number=accession, ticker="CACHED", cik="0000000001",
                                 company_name="Cached fixture", form="10-K", reason="annual_report", score=55,
                                 filed_date=notable_filings_service.today_eastern(),
                                 sec_url="https://example.test/filing/"))
        if payload_kind == "reporting":
            # The stored company's report this week, already out, so the strip shows it on any weekday.
            monday, _ = reporting_this_week_service.current_market_week()
            db.add(EarningsEvent(ticker="CACHED", company_name="Cached fixture", event_date=monday,
                                 fiscal_period_end=monday - timedelta(days=30), event_time="amc",
                                 status=STATUS_REPORTED, anticipation_score=100))
        if payload_kind == "progress_stalled":
            stalled_at = utcnow() - timedelta(hours=1)
            db.add(SummaryGenerationProgress(filing_id=filing.id, stage="analyzing",
                                             started_at=stalled_at, updated_at=stalled_at))
        if payload_kind.startswith("waitlist"):
            # A reader one referral up the list, and the friend that referral brought in.
            db.add(WaitlistSignup(email="reader@example.com", referral_code="READER01",
                                  position=7, priority_score=1))
            db.add(WaitlistSignup(email="friend@example.com", referral_code="FRIEND01",
                                  referred_by="READER01", position=8))
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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    monkeypatch.setattr(filings.sec_edgar_service, "get_filings", unexpected_upstream)
    # The status read's per-IP limiter is process-wide; each burst starts with a fresh window.
    monkeypatch.setattr(watchlist, "WAITLIST_STATUS_LIMITER", RateLimiter(limit=100, window_seconds=60))
    if payload_kind == "notable":
        from app.config import settings

        # The feed on, one company enough to serve it, and a cache that never holds, so each of the
        # eight requests reads.
        reader = notable_filings_service.NotableFilingsService()
        reader._cache_ttl = timedelta(0)
        monkeypatch.setattr(notable_filings, "notable_filings_service", reader)
        monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
        monkeypatch.setattr(notable_filings_service, "MIN_COMPANIES", 1)
    if payload_kind == "reporting":
        from app.config import settings

        # One company enough to serve the strip, no index filter, and a cache that never holds, so
        # each of the eight requests reads.
        strip = reporting_this_week_service.ReportingThisWeekService()
        strip._cache_ttl = timedelta(0)
        monkeypatch.setattr(reporting_this_week, "reporting_this_week_service", strip)
        monkeypatch.setattr(reporting_this_week_service, "MIN_COMPANIES", 1)
        monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", False)
    filing_list_service._mark_filings_synced("CACHED", expand_amendment_forms(["10-K", "10-Q"]), company_id)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(*[client.get(path) for _ in range(8)])
        not_found = payload_kind in ("missing", "missing_company", "waitlist_missing")
        assert [response.status_code for response in responses] == [404 if not_found else 200] * 8
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
            elif payload_kind == "peers":
                # The peer ranking: one read and the release in one unit off the event loop.
                assert (payload["ticker"], payload["concept"], payload["peer_count"]) == ("CACHED", "revenue", 1)
                assert (payload["subject"]["value"], payload["subject"]["rank"]) == (123.0, 1)
            elif payload_kind == "missing_company":
                assert payload == {"detail": "Company not found"}
            elif payload_kind == "waitlist_stats":
                assert payload == {"total_signups": 2}
            elif payload_kind == "waitlist_status":
                assert payload == {"position": 2, "referrals_count": 1, "positions_gained": 5}
            elif payload_kind == "waitlist_missing":
                assert payload == {"detail": "Email not found on the waitlist."}
            elif payload_kind == "notable":
                # The feed: its window and summary reads and the release in one unit off the event loop.
                assert [(row["ticker"], row["form"]) for row in payload["filings"]] == [("CACHED", "10-K")]
            elif payload_kind == "reporting":
                # The strip: its week's read and the release in one unit off the event loop.
                assert payload["status"] == "ok"
                assert [(row["ticker"], row["time"]) for row in payload["companies"]] == [("CACHED", "amc")]
            else:
                assert payload == {"detail": "Filing not found"}
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [session.open_at_close[-1:] for session in request_sessions] == [[False]] * 8
        # Every listed route runs its unit in the thread pool and releases it before yielding, so
        # none of their checkouts happens on the loop.
        assert len(loop_checkouts) >= 8
        assert loop_checkouts == [False] * len(loop_checkouts)
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


@pytest.mark.asyncio
async def test_analysis_stream_releases_its_connection_before_the_body_streams(monkeypatch, tmp_path):
    """The analysis stream's admission (the company lookup, the cap check and, at the cap, the
    cached-range read) runs in the thread pool and releases the request session before the response
    streams. The dependency's finalizer runs only once the stream ends, so a transaction left open
    there held a pooled connection for the whole narrative: at the cap the cached-range read opened
    one after the cap check, a single stream streamed with its slot still out, and the fifth of
    eight concurrent streams on four slots blocked the loop for the pool timeout."""
    from types import SimpleNamespace

    from app import dependencies
    from app.routers import analysis as analysis_router

    engine = create_engine(
        f"sqlite:///{tmp_path / 'analysis-stream.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    Company.__table__.create(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(Company(cik="0000000003", ticker="STREAM", name="Stream fixture"))
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))

    def at_cap(user, db):
        db.query(Company.id).first()  # the cap check reads, as the real one does
        return False, 100, 100

    def cached_range(db, company_id, mode, start_period, end_period):
        # The read that left its transaction open for the stream: at the cap, after the cap check.
        db.query(Company.id).filter(Company.id == company_id).first()
        return True

    out_while_streaming: list[int] = []

    async def narrative(**kwargs):
        out_while_streaming.append(engine.pool.checkedout())
        await asyncio.sleep(0.2)  # the other streams arrive while this one is writing
        yield {"type": "complete", "kind": "analysis", "cached": True, "usage": {}}

    pro = SimpleNamespace(id=42, is_pro=True, subscription=None)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {dependencies._resolve_current_user: lambda: pro})
    monkeypatch.setattr(analysis_router, "STREAM_LIMITER", RateLimiter(limit=100, window_seconds=60))
    monkeypatch.setattr(analysis_router, "check_analysis_limit", at_cap)
    monkeypatch.setattr(analysis_router.trend_analysis_service, "has_cached_analysis", cached_range)
    monkeypatch.setattr(analysis_router.trend_analysis_service, "stream_trend_narrative", narrative)
    monkeypatch.setattr(analysis_router, "_emit_analysis_cost_best_effort", lambda *_a, **_k: None)
    body = {"mode": "annual", "start_period": "FY2021", "end_period": "FY2023"}
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            alone = await client.post("/api/analysis/STREAM/stream", json=body)
            assert alone.status_code == 200 and "data: " in alone.text
            # No connection was out while the one stream wrote; its finalizer found nothing open.
            assert out_while_streaming == [0]
            assert [session.open_at_close[-1:] for session in request_sessions] == [[False]]

            burst = await asyncio.gather(*[client.post("/api/analysis/STREAM/stream", json=body) for _ in range(8)])
        assert [response.status_code for response in burst] == [200] * 8
        assert all("data: " in response.text for response in burst)
        assert engine.pool.checkedout() == 0
        assert [session.open_at_close[-1:] for session in request_sessions] == [[False]] * 9
        # The admission waited for its slot in the thread pool, never on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_force_regeneration_refreshes_no_expired_row_on_the_loop(monkeypatch, tmp_path):
    """The Pro force branch of the generate stream commits (it clears the progress row; the XBRL
    snapshot stays, P11), and the commit expires the request's user and filing. The route read the user's id and
    the filing's type and ticker after that commit, so each refreshed its row with a fresh checkout
    on the event loop, which freezes the loop for the pool timeout once the pool is full. The route
    now reads them before the commit, so the force path checks out once, for the auth lookup, in the
    thread pool: the route's queries and the Pro gate's subscription read reuse that connection, and
    the generation snapshot finds the subscription already loaded."""
    from app.models import Subscription, User
    from app.routers import auth
    from app.routers import summaries as summaries_router

    engine = create_engine(
        f"sqlite:///{tmp_path / 'force-regeneration.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    for model in (User, Subscription, Company, Filing, FilingContentCache, Summary, SummaryGenerationProgress):
        model.__table__.create(engine)
    with sessionmaker(bind=engine)() as db:
        user = User(email="force-pro@example.com", is_active=True, is_pro=True)
        company = Company(cik="0000000004", ticker="FORCE", name="Force fixture")
        db.add_all([user, company])
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000004-26-000001", filing_type="10-K",
                        filing_date=utcnow(), xbrl_data={"revenue": 1},
                        sec_url="https://example.test/force/", document_url="https://example.test/force.htm")
        db.add(filing)
        db.flush()
        db.add(Summary(filing_id=filing.id, business_overview="# Summary\n\nStored analysis the filing page shows.",
                       raw_summary={}))
        db.add(SummaryGenerationProgress(filing_id=filing.id, stage="completed",
                                         started_at=utcnow(), updated_at=utcnow()))
        db.commit()
        user_id, filing_id = user.id, filing.id

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))

    pipeline_calls: list[dict[str, Any]] = []

    async def pipeline(**kwargs):
        pipeline_calls.append(kwargs)
        yield {"type": "complete", "summary": "# Summary\n\nRegenerated."}

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    monkeypatch.setattr(summaries_router, "stream_filing_summary", pipeline)
    monkeypatch.setattr(summaries_router, "SUMMARY_LIMITER", RateLimiter(limit=100, window_seconds=60))
    token = auth.create_access_token({"sub": "force-pro@example.com"})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            response = await client.post(f"/api/summaries/filing/{filing_id}/generate-stream?force=true")
        # The request's own checkouts, before this test reads the database on the loop below.
        request_checkouts = list(loop_checkouts)
        assert response.status_code == 200 and "Regenerated." in response.text
        assert engine.pool.checkedout() == 0
        # One checkout, the auth lookup's, in the thread pool.
        assert request_checkouts == [False]
        # The force branch ran: its commit cleared the progress row and kept the XBRL snapshot, which
        # the run replaces only with fresh XBRL (refresh_xbrl).
        with sessionmaker(bind=engine)() as db:
            assert db.query(SummaryGenerationProgress).count() == 0
            assert db.get(Filing, filing_id).xbrl_data == {"revenue": 1}
        # The pipeline was handed the snapshots taken before that commit.
        [call] = pipeline_calls
        assert (call["user_id"], call["force_regenerate"], call["current_user"].is_pro) == (user_id, True, True)
        assert call["refresh_xbrl"] is True
        assert (call["telemetry_ctx"]["filing_type"], call["telemetry_ctx"]["ticker"]) == ("10-K", "FORCE")
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("path,case", [
    ("/api/auth/logout", "logout_signed_in"),
    ("/api/auth/logout", "logout_cookie_only"),
    ("/api/auth/logout", "logout_dead_cookie"),
    ("/api/auth/logout-all", "logout_all"),
    ("/api/auth/refresh", "refresh"),
])
async def test_auth_session_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, path, case):
    """The logout, logout-all and refresh routes run their session work in the thread pool and
    release the session before they return. On the loop, a revoke that found no live token kept its
    read transaction, the audit write read its row back after its commit, and the refresh read the
    user its rotation had expired, so each held a connection for the dependency's finalizer. Of eight
    requests on four slots, the dead-cookie logout and the refresh answered 500 from the fifth on; the
    signed-in logout and logout-all left their transactions to the finalizer; and the cookie-only
    logout checked out on the loop."""
    from app.config import settings
    from app.models import AuditLog, RefreshToken, User
    from app.routers import auth
    from app.services import refresh_token_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-sessions.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    for model in (User, RefreshToken, AuditLog):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        user = User(email="session-reader@example.com", is_active=True)
        db.add(user)
        db.flush()
        owner_id = user.id
        raw_tokens = [refresh_token_service.create_refresh_token(db, user)[1] for _ in range(8)]
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    bearer = auth.create_access_token({"sub": "session-reader@example.com"})

    def headers(i: int) -> dict[str, str]:
        sent = {}
        if case in ("logout_signed_in", "logout_all"):
            sent["Authorization"] = f"Bearer {bearer}"
        if case == "logout_dead_cookie":
            # A token the server never issued: like a second logout's, the revoke finds no live token
            # and commits nothing.
            sent["Cookie"] = f"{settings.REFRESH_COOKIE_NAME}=never-issued-{i}"
        elif case != "logout_all":
            sent["Cookie"] = f"{settings.REFRESH_COOKIE_NAME}={raw_tokens[i]}"
        return sent

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        # A client per request, so no request picks up another's rotated cookie.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(path, headers=headers(i))

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        assert [response.status_code for response in responses] == [200] * 8
        payloads = [response.json() for response in responses]
        if case == "logout_all":
            assert {payload["status"] for payload in payloads} == {"success"}
            assert sum(payload["sessions_revoked"] for payload in payloads) == 8
        elif case == "refresh":
            assert all(payload["access_token"] and payload["token_type"] == "bearer" for payload in payloads)
        else:
            assert payloads == [{"status": "success"}] * 8
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        # Every checkout waited in the thread pool, none on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        with sessions() as db:
            tokens = db.query(RefreshToken).order_by(RefreshToken.id).all()
            originals, minted = tokens[:8], tokens[8:]
            logouts = db.query(AuditLog).filter(AuditLog.action == "logout").count()
            logged = {(row.user_id, row.user_email) for row in db.query(AuditLog).filter(AuditLog.action == "logout")}
        if case == "logout_dead_cookie":
            assert [token.revoked_at for token in originals] == [None] * 8 and logouts == 0
        else:
            assert all(token.revoked_at is not None for token in originals)
            # Every logout that ends a session writes its row, a cookie-only one under its token's user (E137),
            # the account the tokens belong to and never a token's own id.
            assert logouts == (0 if case == "refresh" else 8)
            assert logged == (set() if case == "refresh" else {(str(owner_id), "session-reader@example.com")})
        if case == "refresh":
            # Each live token was rotated once, into a token of its own, and each response carries the
            # cookie for the token that replaced the one its request sent.
            assert len(minted) == 8
            assert sorted(token.replaced_by_id for token in originals) == [token.id for token in minted]
            hash_by_id = {token.id: token.token_hash for token in minted}
            assert [
                refresh_token_service._hash_token(response.cookies[settings.REFRESH_COOKIE_NAME])
                for response in responses
            ] == [hash_by_id[token.replaced_by_id] for token in originals]
        else:
            assert minted == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["right_password", "wrong_password", "locked_out"])
async def test_password_login_releases_its_connection_before_bcrypt_and_off_the_loop(
    monkeypatch, tmp_path, outcome,
):
    """The login runs its lockout peek and account read as one unit in the thread pool, releases the
    session before bcrypt, and runs its writes (the session, or the failure's count and audit row) as a
    second unit released before it returns. On the loop it kept its connection checked out across
    bcrypt, and each of its reads and writes checked out there (E121). A locked-out account's login
    answers 429 from the first unit, which releases its session on that path too, with no bcrypt."""
    from app.models import AuditLog, LoginAttempt, RefreshToken, User
    from app.routers import auth
    from app.services import login_lockout

    engine = create_engine(
        f"sqlite:///{tmp_path / 'login.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    for model in (User, RefreshToken, AuditLog, LoginAttempt):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    password = "Sup3rSecretPassw0rd"  # gitleaks:allow - test fixture, not a credential
    emails = [f"login-{i}@example.com" for i in range(9)]
    with sessions() as db:
        hashed = auth.get_password_hash(password)
        db.add_all(User(email=email, is_active=True, hashed_password=hashed) for email in emails)
        if outcome == "locked_out":
            db.add_all(
                LoginAttempt(
                    email_hash=login_lockout._email_hash(email),
                    failed_count=login_lockout.LOCKOUT_THRESHOLD,
                    locked_until=utcnow() + timedelta(seconds=login_lockout.LOCKOUT_SECONDS),
                )
                for email in emails
            )
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    held_during_bcrypt: list[int] = []
    verify = auth.verify_password

    def verify_and_count(plain: str, hashed: str) -> bool:
        held_during_bcrypt.append(engine.pool.checkedout())
        return verify(plain, hashed)

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "LOGIN_LIMITER", RateLimiter(limit=100, window_seconds=60))
    monkeypatch.setattr(auth, "verify_password", verify_and_count)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    sent = "not-the-password" if outcome == "wrong_password" else password  # gitleaks:allow

    async def send(email: str) -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/auth/login", json={"email": email, "password": sent})

    try:
        # One login alone first: no connection is checked out while it hashes.
        responses = [await send(emails[0])]
        assert held_during_bcrypt == ([] if outcome == "locked_out" else [0])
        responses += await asyncio.gather(*[send(email) for email in emails[1:]])
        status = {"right_password": 200, "wrong_password": 401, "locked_out": 429}[outcome]
        assert [response.status_code for response in responses] == [status] * 9
        assert engine.pool.checkedout() == 0
        # Each login released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 9
        # Every checkout waited in the thread pool, none on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        with sessions() as db:
            stamped = db.query(User).filter(User.last_login_at.is_not(None)).count()
            tokens = db.query(RefreshToken).count()
            counted = db.query(LoginAttempt).count()
            audits = sorted(action for (action,) in db.query(AuditLog.action))
        if outcome == "right_password":
            assert (stamped, tokens, counted, audits) == (9, 9, 0, ["login_success"] * 9)
        elif outcome == "wrong_password":
            assert (stamped, tokens, counted, audits) == (0, 0, 9, ["login_failed"] * 9)
        else:  # the lockout rows it found, and nothing written
            assert (stamped, tokens, counted, audits) == (0, 0, 9, [])
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_refresh_keeps_its_rotation_when_the_early_release_fails(monkeypatch, tmp_path, caplog):
    """The refresh releases its session inside its unit, after the rotation has committed. A close
    whose rollback fails there (a connection that dropped after the unit's last statement) must not
    turn the response into a 500: the old token is already rotated away, so a reader who never
    receives the new cookie refreshes with the old one next, and the replay sweep signs them out
    everywhere. The first close drops the real DBAPI connection before it runs, so its rollback
    fails as a dropped connection's does. SQLAlchemy reads that as a disconnect: it invalidates the
    connection and returns its slot, the session lets go of its transaction, the release logs the
    failure, and the route answers with the rotated cookie."""
    from app.config import settings
    from app.models import AuditLog, RefreshToken, User
    from app.services import refresh_token_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'refresh-release.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    for model in (User, RefreshToken, AuditLog):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        user = User(email="dropped-close@example.com", is_active=True)
        db.add(user)
        db.flush()
        raw_token = refresh_token_service.create_refresh_token(db, user)[1]
        db.commit()

    at_close: list[tuple[bool, int]] = []

    class DroppedCloseSession(Session):
        """Records, at each close, whether the session held a transaction and how many slots were out.
        The first close drops its DBAPI connection first, as a server that went away would."""

        def close(self) -> None:
            at_close.append((self.in_transaction(), engine.pool.checkedout()))
            if len(at_close) == 1 and self.in_transaction():
                self.connection().connection.dbapi_connection.close()
            super().close()

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=DroppedCloseSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/refresh", headers={"Cookie": f"{settings.REFRESH_COOKIE_NAME}={raw_token}"},
            )
        assert response.status_code == 200 and response.json()["token_type"] == "bearer"
        # The unit's close held the user read's transaction and one slot; by the finalizer's close
        # the dropped connection had been invalidated and its slot returned.
        assert at_close == [(True, 1), (False, 0)]
        [logged] = [record for record in caplog.records
                    if "Releasing the request session failed" in record.getMessage()]
        assert logged.exc_info[1].connection_invalidated
        assert engine.pool.checkedout() == 0
        with sessions() as db:
            original, replacement = db.query(RefreshToken).order_by(RefreshToken.id).all()
        # The reader holds the rotated token, so the next refresh is no replay.
        assert original.revoked_at is not None and original.replaced_by_id == replacement.id
        assert refresh_token_service._hash_token(
            response.cookies[settings.REFRESH_COOKIE_NAME]) == replacement.token_hash
    finally:
        engine.dispose()


_WATCHLIST_STATUS = {
    "add_missing": 404, "add_duplicate": 400, "remove_missing": 404, "remove_unwatched": 404,
    "enable_capped": 403, "enable_unresolvable": 404,
}
# Each reader's watch row for CACHED after the burst, by case: its earnings_alert flag, or no row.
_WATCHLIST_ROW_AFTER = {
    "list": False, "insights": False, "add": False, "add_duplicate": False, "alert_tickers": True,
    "enable": True, "disable": False,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,case", [
    ("GET", "/api/watchlist/", "list"),
    ("GET", "/api/watchlist/insights", "insights"),
    ("POST", "/api/watchlist/CACHED", "add"),
    ("POST", "/api/watchlist/NOSUCH", "add_missing"),
    ("POST", "/api/watchlist/CACHED", "add_duplicate"),
    ("DELETE", "/api/watchlist/CACHED", "remove"),
    ("DELETE", "/api/watchlist/NOSUCH", "remove_missing"),
    ("DELETE", "/api/watchlist/CACHED", "remove_unwatched"),
    ("GET", "/api/watchlist/earnings-alerts", "alert_tickers"),
    ("POST", "/api/watchlist/CACHED/earnings-alert", "enable"),
    ("POST", "/api/watchlist/CACHED/earnings-alert", "enable_capped"),
    ("POST", "/api/watchlist/NOSUCH/earnings-alert", "enable_unresolvable"),
    ("DELETE", "/api/watchlist/CACHED/earnings-alert", "disable"),
])
async def test_watchlist_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, path, case):
    """Each watchlist route runs its session work, its payload and the release in one thread-pool
    unit, its refusals included, so eight readers on four slots leave nothing for the finalizer and
    make no checkout on the loop."""
    from app.models import User, Watchlist
    from app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'watchlist-routes.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture",
                          history_backfilled_at=utcnow())
        db.add(company)
        # Three companies each reader already has an alert on, for the cap case (Free allows 3).
        capped = [Company(cik=f"{i + 2:010d}", ticker=f"CAP{i}", name=f"Capped {i}") for i in range(3)]
        db.add_all(capped)
        db.flush()
        db.add(Filing(company_id=company.id, accession_number="0000000001-26-000001",
                      filing_type="10-K", filing_date=utcnow(),
                      sec_url="https://example.test/filing/", document_url="https://example.test/filing.htm"))
        for i in range(8):
            reader = User(email=f"watch-reader-{i}@example.com", is_active=True)
            db.add(reader)
            db.flush()
            if case in ("list", "insights", "add_duplicate", "remove", "alert_tickers", "disable"):
                db.add(Watchlist(user_id=reader.id, company_id=company.id,
                                 earnings_alert=case in ("alert_tickers", "disable")))
            if case == "enable_capped":
                db.add_all(Watchlist(user_id=reader.id, company_id=other.id, earnings_alert=True)
                           for other in capped)
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # A statement on the loop blocks it even on a connection the thread pool checked out (the auth
    # lookup's, which the route's session keeps).
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"watch-reader-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.request(method, path)

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        assert [response.status_code for response in responses] == [_WATCHLIST_STATUS.get(case, 200)] * 8
        payloads = [response.json() for response in responses]
        if case == "list":
            assert [[row["company"]["ticker"] for row in payload] for payload in payloads] == [["CACHED"]] * 8
        elif case == "insights":
            assert [
                [(row["company"]["ticker"], row["total_filings"], row["latest_filing"]["summary_status"])
                 for row in payload]
                for payload in payloads
            ] == [[("CACHED", 1, "missing")]] * 8
        elif case == "add":
            # The payload reads the company row the commit expired, inside the unit.
            assert [(payload["company"]["ticker"], payload["created_at"] is not None)
                    for payload in payloads] == [("CACHED", True)] * 8
        elif case in ("add_missing", "remove_missing"):
            assert payloads == [{"detail": "Company not found"}] * 8
        elif case == "add_duplicate":
            assert payloads == [{"detail": "Company already in watchlist"}] * 8
        elif case == "remove":
            assert payloads == [{"status": "success"}] * 8
        elif case == "remove_unwatched":
            assert payloads == [{"detail": "Company not in watchlist"}] * 8
        elif case == "alert_tickers":
            assert payloads == [{"tickers": ["CACHED"]}] * 8
        elif case == "enable":
            assert payloads == [{"status": "enabled", "ticker": "CACHED"}] * 8
        elif case == "enable_capped":
            # The cap check reads the user's plan, a lazy load of its subscription, inside the unit.
            assert payloads == [{
                "detail": "Free includes earnings alerts for 3 companies. Upgrade to Pro for more.",
                "code": "earnings_alert_limit",
            }] * 8
        elif case == "enable_unresolvable":
            assert payloads == [{"detail": "We can't set an alert for NOSUCH yet."}] * 8
        else:
            assert payloads == [{"status": "disabled", "ticker": "CACHED"}] * 8
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        # Every checkout, the auth lookup's included, waited in the thread pool, and every statement
        # ran there: none on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        with sessions() as db:
            rows = (db.query(Watchlist.user_id, Watchlist.earnings_alert)
                    .filter(Watchlist.company_id == 1).order_by(Watchlist.user_id).all())
        # Each write landed once per reader, and each refusal wrote nothing.
        assert [tuple(row) for row in rows] == (
            [(user_id, _WATCHLIST_ROW_AFTER[case]) for user_id in range(1, 9)]
            if case in _WATCHLIST_ROW_AFTER else []
        )
    finally:
        engine.dispose()


_WAITLIST_STATUS = {"join_bad_referral": 400, "verify_missing": 404}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "join", "join_referred", "join_existing", "join_bad_referral", "verify", "verify_missing",
])
async def test_waitlist_writes_release_their_connection_off_the_loop(monkeypatch, tmp_path, case):
    """The waitlist join and the email verification run their session work in thread-pool units, the
    join's refusals included, so eight joiners on four slots leave nothing for the finalizer and
    make no checkout on the loop. The join releases before its mails go out (its own case below)."""
    from app.services import turnstile, waitlist_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'waitlist-writes.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    WaitlistSignup.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for i in range(8):
            # A referrer per joiner, so no two joins credit one row.
            db.add(WaitlistSignup(email=f"referrer-{i}@example.com", referral_code=f"refcode{i}",
                                  position=i + 1, priority_score=0))
            if case in ("join_existing", "verify"):
                db.add(WaitlistSignup(email=f"joiner-{i}@example.com", referral_code=f"joincod{i}",
                                      position=i + 9, priority_score=0))
        db.commit()

    sent: dict[str, list[str]] = {"welcome": [], "referral": []}

    async def welcome(**kwargs: Any) -> None:
        sent["welcome"].append(kwargs["to_email"])

    async def referral(**kwargs: Any) -> None:
        sent["referral"].append(kwargs["to_email"])

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # A statement on the loop blocks it even on a connection the thread pool checked out (the auth
    # lookup's, which the route's session keeps).
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(watchlist, "send_waitlist_welcome_email", welcome)
    monkeypatch.setattr(watchlist, "send_referral_success_email", referral)
    # The join's per-IP limiter is process-wide; each burst starts with a fresh window.
    monkeypatch.setattr(watchlist, "WAITLIST_JOIN_LIMITER", RateLimiter(limit=100, window_seconds=3600))
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        email = f"joiner-{i}@example.com"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            if case.startswith("verify"):
                token = waitlist_service.create_verification_token(email, f"joincod{i}")
                return await client.post(f"/api/waitlist/verify/{token}")
            body = {"email": email}
            if case == "join_referred":
                body["referral_code"] = f"refcode{i}"
            elif case == "join_bad_referral":
                body["referral_code"] = f"nosuch{i}"
            return await client.post("/api/waitlist/join", json=body)

    joiners = [f"joiner-{i}@example.com" for i in range(8)]
    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        assert [response.status_code for response in responses] == [_WAITLIST_STATUS.get(case, 200)] * 8
        payloads = [response.json() for response in responses]
        if case in ("join", "join_referred"):
            assert [(payload["success"], payload["email_sent"]) for payload in payloads] == [(True, True)] * 8
        elif case == "join_existing":
            assert [(payload["error"], payload["referral_code"]) for payload in payloads] == [
                ("already_registered", f"joincod{i}") for i in range(8)]
        elif case == "join_bad_referral":
            assert payloads == [{
                "success": False, "error": "invalid_referral", "message": "Referral code not recognized.",
            }] * 8
        elif case == "verify":
            assert payloads == [{"success": True, "message": "Email verified."}] * 8
        else:
            assert payloads == [{"detail": "Waitlist entry not found."}] * 8
        assert engine.pool.checkedout() == 0
        # Each unit released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        # Every checkout waited in the thread pool, and every statement ran there: none on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert sorted(sent["welcome"]) == (joiners if case in ("join", "join_referred") else [])
        assert sorted(sent["referral"]) == (
            [f"referrer-{i}@example.com" for i in range(8)] if case == "join_referred" else [])
        with sessions() as db:
            rows = {row.email: row for row in db.query(WaitlistSignup).all()}
            if case in ("join", "join_referred"):
                assert [rows[email].welcome_email_sent for email in joiners] == [True] * 8
            if case == "join_referred":
                assert [rows[f"referrer-{i}@example.com"].priority_score for i in range(8)] == [1] * 8
            if case == "join_bad_referral":
                assert sorted(rows) == [f"referrer-{i}@example.com" for i in range(8)]
            if case == "verify":
                assert [rows[email].email_verified for email in joiners] == [True] * 8
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("welcome_fails", [False, True])
async def test_waitlist_join_holds_no_connection_while_its_mails_send(monkeypatch, tmp_path, welcome_fails):
    """The join copies what its mails need, releases its session, and only then sends: no pool slot
    waits on the mail provider. The welcome flag is its own unit after the send, and a failed send
    writes nothing."""
    from app.services import turnstile

    engine = create_engine(
        f"sqlite:///{tmp_path / 'waitlist-sends.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    WaitlistSignup.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()

    held: dict[str, int] = {}

    async def welcome(**kwargs: Any) -> None:
        held["welcome"] = engine.pool.checkedout()
        if welcome_fails:
            raise RuntimeError("mail provider down")

    async def referral(**kwargs: Any) -> None:
        held["referral"] = engine.pool.checkedout()

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(watchlist, "send_waitlist_welcome_email", welcome)
    monkeypatch.setattr(watchlist, "send_referral_success_email", referral)
    monkeypatch.setattr(watchlist, "WAITLIST_JOIN_LIMITER", RateLimiter(limit=100, window_seconds=3600))
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/waitlist/join", json={"email": "joiner@example.com", "referral_code": "refcode0"},
            )
        assert response.status_code == 200
        assert (response.json()["success"], response.json()["email_sent"]) == (True, not welcome_fails)
        # Neither send held a connection: the join's unit had released the session before the first.
        assert held == {"welcome": 0, "referral": 0}
        assert engine.pool.checkedout() == 0
        with sessions() as db:
            rows = {row.email: row for row in db.query(WaitlistSignup).all()}
        assert rows["joiner@example.com"].welcome_email_sent is (not welcome_fails)
        assert rows["referrer@example.com"].priority_score == 1
    finally:
        engine.dispose()


def _submit_fixture(monkeypatch, tmp_path, send_email):
    """A four-slot pool with eight active users, the contact form and the feedback submit wired to it
    with ``send_email`` as their mail sender, and fresh limiters. Returns the engine, a session factory,
    the request sessions as they open, and whether each checkout and each statement ran on the loop."""
    from app.models import User
    from app.routers import auth, contact, feedback
    from app.services import turnstile

    engine = create_engine(
        f"sqlite:///{tmp_path / 'submits.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all(User(email=f"submitter-{i}@example.com", is_active=True) for i in range(8))
        db.commit()

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

    loop_thread = threading.get_ident()
    on_loop: dict[str, list[bool]] = {"checkouts": [], "statements": []}
    event.listen(engine, "checkout", lambda *_: on_loop["checkouts"].append(threading.get_ident() == loop_thread))
    # A statement on the loop blocks it even on a connection the thread pool checked out (the feedback
    # submit's auth lookup's, which the route's session keeps).
    event.listen(engine, "before_cursor_execute",
                 lambda *_: on_loop["statements"].append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")
    monkeypatch.setattr(contact.settings, "RESEND_FROM_EMAIL", "Ops <ops@example.com>")
    monkeypatch.setattr(contact.settings, "CONTACT_NOTIFICATION_EMAIL", "ops@example.com")
    monkeypatch.setattr(feedback.settings, "FEEDBACK_NOTIFICATION_EMAIL", "ops@example.com")
    monkeypatch.setattr(contact, "send_email", send_email)
    monkeypatch.setattr(feedback, "send_email", send_email)
    # Each route's limiter is process-wide; each burst starts with a fresh window.
    monkeypatch.setattr(contact, "CONTACT_LIMITER", RateLimiter(limit=100, window_seconds=3600))
    monkeypatch.setattr(feedback, "FEEDBACK_LIMITER", RateLimiter(limit=100, window_seconds=3600))
    return engine, sessions, request_sessions, on_loop


async def _submit(transport: httpx.ASGITransport, route: str, i: int) -> httpx.Response:
    """One contact form message from submitter ``i``, or one feedback report signed in as them."""
    from app.routers import auth

    if route == "contact":
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/contact/", json={
                "name": f"Submitter {i}", "email": f"submitter-{i}@example.com",
                "message": "Does the summary include segment data?",
            })
    token = auth.create_access_token({"sub": f"submitter-{i}@example.com"})
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"Authorization": f"Bearer {token}"}) as client:
        return await client.post("/api/feedback/", json={"type": "bug", "message": "Charts fail to load"})


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["contact", "feedback"])
async def test_contact_and_feedback_submits_release_their_connection_off_the_loop(monkeypatch, tmp_path, route):
    """The contact form and the feedback submit each insert their row and build their response in one
    thread-pool unit, released before their mails go out, so eight submissions on four slots, each mail
    taking 0.3 s, answer 8x201 with no checkout or statement on the loop and nothing left for the
    finalizer. Holding the connection across the mails, as both did, answered the contact form's
    burst 4x201 then 4x500, and left every feedback report's transaction for the finalizer (E144)."""
    from app.models import ContactSubmission
    from app.models.feedback import Feedback

    async def slow_send(*args: Any, **kwargs: Any) -> dict:
        await asyncio.sleep(0.3)
        return {"id": "msg_test"}

    engine, sessions, request_sessions, on_loop = _submit_fixture(monkeypatch, tmp_path, slow_send)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        responses = await asyncio.gather(*[_submit(transport, route, i) for i in range(8)])
        assert [response.status_code for response in responses] == [201] * 8
        assert sorted(response.json()["id"] for response in responses) == list(range(1, 9))
        assert engine.pool.checkedout() == 0
        # Each unit released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        # Every checkout, the feedback submit's auth lookup's included, waited in the thread pool, and
        # every statement ran there: none on the loop.
        assert on_loop["checkouts"] and on_loop["checkouts"] == [False] * len(on_loop["checkouts"])
        assert on_loop["statements"] and on_loop["statements"] == [False] * len(on_loop["statements"])
        with sessions() as db:
            assert db.query(ContactSubmission if route == "contact" else Feedback).count() == 8
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["contact", "feedback"])
async def test_contact_and_feedback_submits_hold_no_connection_while_their_mails_send(monkeypatch, tmp_path, route):
    """Each submit releases its session before its first mail, so no pool slot waits on the mail
    provider: the contact form's notice to the team and its confirmation to the sender, and the
    feedback submit's notice to the team."""
    held: list[tuple[str, int]] = []
    engine, _, _, _ = _submit_fixture(monkeypatch, tmp_path, None)

    async def send(to: list[str], subject: str, html: str, *args: Any, **kwargs: Any) -> dict:
        held.append((to[0], engine.pool.checkedout()))
        return {"id": "msg_test"}

    from app.routers import contact, feedback

    monkeypatch.setattr(contact, "send_email", send)
    monkeypatch.setattr(feedback, "send_email", send)
    try:
        response = await _submit(httpx.ASGITransport(app=app, raise_app_exceptions=False), route, 0)
        assert response.status_code == 201
        assert held == (
            [("ops@example.com", 0), ("submitter-0@example.com", 0)] if route == "contact"
            else [("ops@example.com", 0)]
        )
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("path,case", [
    ("/api/subscriptions/usage", "usage"),
    ("/api/subscriptions/usage", "usage_pro"),
    ("/api/subscriptions/subscription", "status"),
    ("/api/subscriptions/subscription", "status_row"),
])
async def test_subscription_reads_release_their_connection_off_the_loop(monkeypatch, tmp_path, path, case):
    """The usage and subscription-status routes read their counts, the reader's subscription row and the plan
    the entitlements derive from it, and build their payload, in one thread-pool unit, so eight readers on four
    slots, with and without a subscription row, each get their own payload, leave nothing for the finalizer and
    make no checkout, statement or release on the loop (E144)."""
    from app.config import settings
    from app.models import Subscription, User, UserUsage
    from app.routers import auth
    from app.services.entitlements import get_entitlements
    from app.services.subscription_service import get_current_month

    engine = create_engine(
        f"sqlite:///{tmp_path / 'subscription-reads.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with_row = case in ("usage_pro", "status_row")
    month = get_current_month()
    with sessions() as db:
        for i in range(8):
            # Every mirror stays False, so with a row only the row can make the reader Pro: a plan read
            # after the release falls back to the mirror without raising, and only the payload shows it.
            reader = User(email=f"subscriber-{i}@example.com", is_active=True, is_pro=False,
                          stripe_customer_id=f"cus_{i}", copilot_free_taste_used=i % 3)
            db.add(reader)
            db.flush()
            # Counts of the reader's own, so a payload built from another reader's row fails.
            db.add(UserUsage(user_id=reader.id, month=month, summary_count=i, qa_count=10 + i, analysis_count=20 + i))
            if with_row:
                db.add(Subscription(user_id=reader.id, plan="pro", status="active", stripe_customer_id=f"cus_{i}",
                                    stripe_subscription_id=f"sub_{i}"))
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # A statement on the loop blocks it even on a connection the thread pool checked out (the auth
    # lookup's, which the route's session keeps).
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    # A release on the loop (the session's close after the unit) runs its rollback and checkin there,
    # and neither is a checkout or a statement.
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"subscriber-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.get(path)

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        assert [response.status_code for response in responses] == [200] * 8
        payloads = [response.json() for response in responses]
        if path.endswith("/usage"):
            # Each reader's own counts and the limits of the plan the reader's subscription row gives,
            # a lazy load inside the unit (a transient user's mirror names the plan the row should).
            plan = get_entitlements(User(is_pro=with_row))
            assert payloads == [{
                "summaries_used": i, "summaries_limit": plan.monthly_summary_limit, "is_pro": with_row,
                "month": month, "qa_used": 10 + i, "qa_limit": settings.COPILOT_MONTHLY_QUESTION_CAP,
                "copilot_free_taste_used": i % 3, "copilot_free_taste_total": plan.copilot_free_taste,
                "analysis_used": 20 + i, "analysis_limit": settings.ANALYSIS_MONTHLY_CAP,
            } for i in range(8)]
        else:
            assert [(payload["plan"], payload["stripe_customer_id"], payload["status"]) for payload in payloads] == [
                ("pro" if with_row else "free", f"cus_{i}", "active" if with_row else None) for i in range(8)]
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        # Every checkout, the auth lookup's included, waited in the thread pool, and every statement
        # and every release ran there: none on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
    finally:
        engine.dispose()


def _billing_fixture(monkeypatch, tmp_path, *, with_customer: bool, rival: bool = False):
    """A four-slot pool with eight verified readers (each with a Stripe customer, or none), checkout and
    the billing portal wired to it, and every Stripe call they make faked as a blocking 0.3 s call, as
    the synchronous SDK is. With ``rival``, another checkout of the account stores its customer while
    this one creates its own (E166). Returns the engine, a session factory, the request sessions as they
    open, what ran on the loop (checkouts, statements, checkins), each Stripe call with the connections
    checked out while it ran and whether it ran on the loop, and each call's last keyword arguments."""
    from types import SimpleNamespace

    import stripe

    from app.config import settings
    from app.models import User
    from app.routers import auth
    from app.services import legal_readiness_service

    # Keep the dormant Stripe path's pool and ownership regressions under the launch hold.
    monkeypatch.setattr(legal_readiness_service, "is_checkout_available", lambda: True)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'billing.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all(User(email=f"payer-{i}@example.com", is_active=True, email_verified=True,
                        stripe_customer_id=f"cus_{i}" if with_customer else None) for i in range(8))
        db.commit()

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

    loop_thread = threading.get_ident()
    on_loop: dict[str, list[bool]] = {"checkouts": [], "statements": [], "checkins": []}
    event.listen(engine, "checkout", lambda *_: on_loop["checkouts"].append(threading.get_ident() == loop_thread))
    event.listen(engine, "before_cursor_execute",
                 lambda *_: on_loop["statements"].append(threading.get_ident() == loop_thread))
    # A release on the loop runs its rollback and checkin there, and neither is a checkout or a statement.
    event.listen(engine, "checkin", lambda *_: on_loop["checkins"].append(threading.get_ident() == loop_thread))

    stripe_calls: list[tuple[str, int, bool]] = []
    stripe_kwargs: dict[str, dict[str, Any]] = {}

    def slow(name: str, result):
        def call(*args: Any, **kwargs: Any):
            stripe_calls.append((name, engine.pool.checkedout(), threading.get_ident() == loop_thread))
            stripe_kwargs[name] = kwargs
            time.sleep(0.3)
            return result(*args, **kwargs)
        return call

    def created_customer(*args: Any, **kwargs: Any) -> SimpleNamespace:
        payer = kwargs["email"].split("-")[1].split("@")[0]
        if rival:
            with sessions() as other:
                other.query(User).filter(User.email == kwargs["email"]).update(
                    {User.stripe_customer_id: f"cus_rival_{payer}"})
                other.commit()
        return SimpleNamespace(id=f"cus_{payer}")

    monkeypatch.setattr(stripe.Customer, "create", slow("Customer.create", created_customer))
    monkeypatch.setattr(stripe.Customer, "retrieve", slow("Customer.retrieve", lambda cid: SimpleNamespace(id=cid)))
    monkeypatch.setattr(stripe.checkout.Session, "create",
                        slow("checkout.Session.create", lambda **_: SimpleNamespace(url="https://checkout.stripe.test/s")))
    monkeypatch.setattr(stripe.billing_portal.Session, "create",
                        slow("billing_portal.Session.create", lambda **_: SimpleNamespace(url="https://portal.stripe.test/s")))
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    monkeypatch.setattr(settings, "PRO_TRIAL_DAYS", 7)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    return engine, sessions, request_sessions, on_loop, stripe_calls, stripe_kwargs


async def _bill(transport: httpx.ASGITransport, route: str, i: int) -> httpx.Response:
    """One monthly checkout, or one billing-portal session, signed in as payer ``i``."""
    from app.routers import auth

    token = auth.create_access_token({"sub": f"payer-{i}@example.com"})
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"Authorization": f"Bearer {token}"}) as client:
        if route == "checkout":
            return await client.post("/api/subscriptions/create-checkout-session", params={"price_id": "monthly"})
        return await client.post("/api/subscriptions/create-portal-session")


@pytest.mark.asyncio
@pytest.mark.parametrize("route,with_customer", [("checkout", False), ("checkout", True), ("portal", True)],
                         ids=["checkout-new-customer", "checkout-stored-customer", "portal"])
async def test_checkout_and_portal_release_their_connection_before_stripe(monkeypatch, tmp_path, route, with_customer):
    """Checkout reads what it needs in one thread-pool unit and releases it before any Stripe call, a new
    customer's claim and the trial's row check after the customer step are units of their own, and the
    billing portal releases before its one call; every Stripe call runs off the loop (on the Stripe threads, which
    test_stripe_threads_allowlist.py holds, E170). Eight payers on four slots, each Stripe call taking 0.3 s, so
    answer 8x200 with no checkout, statement or release on the loop, nothing left for the finalizer,
    and each new customer stored on its own payer (E144)."""
    from app.models import User

    engine, sessions, request_sessions, on_loop, stripe_calls, _ = _billing_fixture(
        monkeypatch, tmp_path, with_customer=with_customer)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        responses = await asyncio.gather(*[_bill(transport, route, i) for i in range(8)])
        assert [response.status_code for response in responses] == [200] * 8
        assert engine.pool.checkedout() == 0
        # Each unit released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        assert on_loop["checkouts"] and on_loop["checkouts"] == [False] * len(on_loop["checkouts"])
        assert on_loop["statements"] and on_loop["statements"] == [False] * len(on_loop["statements"])
        assert on_loop["checkins"] and on_loop["checkins"] == [False] * len(on_loop["checkins"])
        assert stripe_calls and [on for _, _, on in stripe_calls] == [False] * len(stripe_calls)
        with sessions() as db:
            assert [customer for (customer,) in db.query(User.stripe_customer_id).order_by(User.id)] == [
                f"cus_{i}" for i in range(8)]
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("route,with_customer,rival,calls", [
    ("checkout", False, False, ["Customer.create", "checkout.Session.create"]),
    # Another checkout stored its customer first, so this one retrieves that customer (E166).
    ("checkout", False, True, ["Customer.create", "Customer.retrieve", "checkout.Session.create"]),
    ("checkout", True, False, ["Customer.retrieve", "checkout.Session.create"]),
    ("portal", True, False, ["billing_portal.Session.create"]),
], ids=["checkout-new-customer", "checkout-lost-claim", "checkout-stored-customer", "portal"])
async def test_checkout_and_portal_hold_no_connection_while_stripe_answers(
        monkeypatch, tmp_path, route, with_customer, rival, calls):
    """One checkout, or one portal session: every Stripe call runs off the loop with no connection
    checked out, the losing checkout's retrieve of the customer stored first included, and each session
    names the payer's customer (and checkout the payer, whom the webhook binds the subscription to)."""
    from app.models import User

    engine, sessions, _, _, stripe_calls, stripe_kwargs = _billing_fixture(
        monkeypatch, tmp_path, with_customer=with_customer, rival=rival)
    try:
        response = await _bill(httpx.ASGITransport(app=app, raise_app_exceptions=False), route, 0)
        assert response.status_code == 200, response.text
        assert stripe_calls == [(name, 0, False) for name in calls]
        assert engine.pool.checkedout() == 0
        customer = "cus_rival_0" if rival else "cus_0"
        if route == "checkout":
            with sessions() as db:
                payer = db.query(User.id).filter(User.email == "payer-0@example.com").scalar()
            sent = stripe_kwargs["checkout.Session.create"]
            assert (sent["customer"], sent["metadata"]["user_id"]) == (customer, str(payer))
        else:
            assert stripe_kwargs["billing_portal.Session.create"]["customer"] == customer
    finally:
        engine.dispose()


def _analysis_fixture(tmp_path, name: str, *, pro: bool, synced: bool = True):
    """A four-slot pool over one company with two fiscal years of revenue and net income, eight
    readers (Pro or Free), and a saved annual analysis whose snapshot matches the current facts.
    Unless ``synced``, the company's companyfacts were never synced, so coverage syncs them."""
    from app.models import TrendAnalysis, User
    from app.services import trend_analysis_service

    engine = create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture",
                          history_backfilled_at=utcnow(), facts_synced_at=utcnow() if synced else None)
        db.add(company)
        db.flush()
        for year, revenue, net_income in ((2024, 100, 10), (2025, 120, 15)):
            for concept, value in (("revenue", revenue), ("net_income", net_income)):
                db.add(FinancialFact(
                    company_id=company.id, concept=concept, unit="USD", period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31), fiscal_year=year, fiscal_period="FY", value=value,
                    form="10-K", accession=f"0000000001-{year % 100:02d}-000001", reconciled=True,
                ))
        for i in range(8):
            db.add(User(email=f"analysis-reader-{i}@example.com", is_active=True, is_pro=pro))
        db.flush()
        saved = trend_analysis_service.build_dataset(db, company, "annual", "FY2024", "FY2025")
        fingerprint = trend_analysis_service.dataset_fingerprint(saved)
        db.add(TrendAnalysis(
            company_id=company.id, mode="annual", period_key=saved["period_key"],
            prompt_version=trend_analysis_service.PROMPT_VERSION, dataset_fingerprint=fingerprint,
            dataset_json={**saved, "snapshot_id": fingerprint}, narrative_md="## Narrative",
        ))
        db.commit()
    return engine, sessions


def _patch_analysis_edges(monkeypatch, *, workbook, render) -> None:
    """Fakes for everything past the request session: the companyfacts sync, the two renders, the
    narrative presentation check (the saved row carries none), and the per-user limiters."""
    from app.routers import analysis
    from app.services import excel_export_service
    from app.services.export_service import export_service
    from app.services.trend_analysis import presentation

    async def synced(_company_id: int) -> dict:
        return {"synced": True}

    monkeypatch.setattr(analysis, "_ingest_with_own_session", synced)
    monkeypatch.setattr(excel_export_service, "build_analysis_workbook", workbook)
    monkeypatch.setattr(export_service, "export_analysis_pdf", render)
    monkeypatch.setattr(presentation, "presentation_is_current", lambda _dataset: True)
    for limiter in ("COVERAGE_LIMITER", "DATASET_LIMITER", "XLSX_LIMITER"):
        monkeypatch.setattr(analysis, limiter, RateLimiter(limit=100, window_seconds=60))


_ANALYSIS_RANGE = {"mode": "annual", "start_period": "FY2024", "end_period": "FY2025"}
_ANALYSIS_STATUS = {
    "coverage_missing": 404, "dataset_missing": 404, "dataset_bad_range": 400, "xlsx_stale": 409,
    "pdf_missing": 404, "pdf_free": 403,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body,case", [
    ("GET", "/api/analysis/CACHED/coverage", None, "coverage"),
    ("GET", "/api/analysis/CACHED/coverage", None, "coverage_handoff"),
    ("GET", "/api/analysis/CACHED/coverage", None, "coverage_sync"),
    ("GET", "/api/analysis/NOSUCH/coverage", None, "coverage_missing"),
    ("POST", "/api/analysis/CACHED/dataset", _ANALYSIS_RANGE, "dataset"),
    ("POST", "/api/analysis/NOSUCH/dataset", _ANALYSIS_RANGE, "dataset_missing"),
    ("POST", "/api/analysis/CACHED/dataset", {**_ANALYSIS_RANGE, "mode": "quarterly"}, "dataset_bad_range"),
    ("POST", "/api/analysis/CACHED/export/xlsx", _ANALYSIS_RANGE, "xlsx"),
    ("POST", "/api/analysis/CACHED/export/xlsx", {**_ANALYSIS_RANGE, "snapshot_id": "0" * 64}, "xlsx_stale"),
    ("GET", "/api/analysis/export/1/pdf", None, "pdf"),
    ("GET", "/api/analysis/export/999/pdf", None, "pdf_missing"),
    ("GET", "/api/analysis/export/1/pdf", None, "pdf_free"),
])
async def test_analysis_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, path, body, case):
    """Each analysis route runs its session work in thread-pool units and releases before it
    awaits anything else (the companyfacts sync, a render), a refusal of each included, so eight Pro
    readers on four slots (Free for the PDF's plan refusal) leave nothing for the finalizer and run
    no checkout or statement on the loop. ``coverage_handoff`` is a first touch in durable mode: the
    sync outlasts the wait, the route cancels it, hands it to the queue and reads what exists. In
    ``coverage_sync`` the route runs ``ingest_companyfacts_by_id`` itself, on the fixture's sessions and
    with only its SEC fetch faked: one request leads it, the others follow, and its sessions keep off
    the loop too (E129)."""
    from app.config import settings
    from app.routers import analysis, auth
    from app.services import facts_service

    engine, sessions = _analysis_fixture(tmp_path, "analysis-routes.db", pro=case != "pdf_free",
                                         synced=case != "coverage_sync")
    sec_fetches: list[str] = []

    async def render(_analysis, _company) -> bytes:
        return b"%PDF-test"

    async def sec_fetch(cik: str) -> dict:
        sec_fetches.append(cik)
        return {"facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [{
            "val": 100, "start": "2024-01-01", "end": "2024-12-31", "accn": "0000000001-24-000001",
            "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01",
        }]}}}}}

    _patch_analysis_edges(monkeypatch, workbook=lambda _dataset: b"xlsx-test", render=render)
    handoffs: list[tuple] = []
    if case == "coverage_handoff":
        async def slow_sync(_company_id: int) -> dict:
            await asyncio.sleep(10)  # outlasts the wait; the route cancels it at the handoff
            return {"synced": True}

        async def enqueue(kind: str, payload: dict, **kwargs: Any) -> None:
            handoffs.append((kind, payload, kwargs))

        monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
        monkeypatch.setattr(analysis, "COVERAGE_SYNC_WAIT_SECONDS", 0.05)
        monkeypatch.setattr(analysis, "_ingest_with_own_session", slow_sync)
        monkeypatch.setattr(analysis, "enqueue_task", enqueue)
    facts_service._inflight_syncs.clear()  # the process-wide claim table; cleared again after
    if case == "coverage_sync":
        from app.services.facts import ingest

        async def sync(company_id: int) -> dict:
            # In place of the route's SessionLocal binding, so the request-session tally below
            # counts the eight requests' sessions while the engine's listeners see the sync's too.
            return await facts_service.ingest_companyfacts_by_id(company_id, session_factory=sessions)

        monkeypatch.setattr(analysis, "_ingest_with_own_session", sync)
        monkeypatch.setattr(ingest, "_fetch_companyfacts_async", sec_fetch)

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"analysis-reader-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.request(method, path, json=body)

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        assert [response.status_code for response in responses] == [_ANALYSIS_STATUS.get(case, 200)] * 8
        if case in ("coverage", "coverage_handoff", "coverage_sync"):
            handed_off = case == "coverage_handoff"
            assert [
                (payload["ticker"], payload["supported"], payload["syncing"], payload["synced_at"] is not None,
                 [period["key"] for period in payload["annual"]])
                for payload in (response.json() for response in responses)
            ] == [("CACHED", True, handed_off, not handed_off, ["FY2024", "FY2025"])] * 8
            assert handoffs == [(
                "companyfacts", {"company_id": 1}, {"dedupe_key": "companyfacts:1", "dedupe_seconds": 60},
            )] * (8 if handed_off else 0)
        elif case in ("coverage_missing", "dataset_missing"):
            assert [response.json() for response in responses] == [{"detail": "Company not found"}] * 8
        elif case == "dataset":
            assert [response.json()["period_key"] for response in responses] == ["FY2024..FY2025"] * 8
        elif case == "dataset_bad_range":
            assert [response.json() for response in responses] == [
                {"detail": "Invalid quarterly period key: 'FY2024' (expected e.g. '2024Q2')"}] * 8
        elif case == "xlsx":
            assert [(response.content, response.headers["content-disposition"]) for response in responses] == [
                (b"xlsx-test", 'attachment; filename="CACHED_FY2024-FY2025_annual-metrics.xlsx"')] * 8
        elif case == "xlsx_stale":
            assert [response.json() for response in responses] == [
                {"detail": "The financial data changed. Refresh the analysis before exporting."}] * 8
        elif case == "pdf":
            assert [(response.content, response.headers["content-disposition"]) for response in responses] == [
                (b"%PDF-test", 'attachment; filename="CACHED_multi_period_annual_FY2024-FY2025.pdf"')] * 8
        elif case == "pdf_missing":
            assert [response.json() for response in responses] == [{"detail": "Analysis not found"}] * 8
        else:
            assert [response.json() for response in responses] == [
                {"detail": "PDF export is a Pro feature. Upgrade to Pro to access this feature."}] * 8
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        # Every checkout and every statement ran in the thread pool, none on the loop.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        if case == "coverage_sync":
            assert sec_fetches == ["0000000001"]  # one leader fetched; the others followed it
            with sessions() as db:
                assert db.get(Company, 1).facts_synced_at is not None
    finally:
        facts_service._inflight_syncs.clear()
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("export", ["xlsx", "pdf"])
async def test_analysis_exports_hold_no_connection_while_they_render(monkeypatch, tmp_path, export):
    """The exports finish their reads and checks, release the session, and only then render: no
    pool slot waits on the workbook build or the PDF render."""
    from app.routers import auth

    engine, _ = _analysis_fixture(tmp_path, "analysis-render.db", pro=True)
    held: dict[str, int] = {}

    def workbook(_dataset) -> bytes:
        held["xlsx"] = engine.pool.checkedout()
        return b"xlsx-test"

    async def render(_analysis, _company) -> bytes:
        held["pdf"] = engine.pool.checkedout()
        return b"%PDF-test"

    _patch_analysis_edges(monkeypatch, workbook=workbook, render=render)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    token = auth.create_access_token({"sub": "analysis-reader-0@example.com"})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            if export == "xlsx":
                response = await client.post("/api/analysis/CACHED/export/xlsx", json=_ANALYSIS_RANGE)
            else:
                response = await client.get("/api/analysis/export/1/pdf")
        assert response.status_code == 200
        # The render ran with no connection out: the route's unit had released the session.
        assert held == {export: 0}
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


_NEW_COMPANY = {"cik": "0000000009", "ticker": "NEWCO", "name": "New Co", "exchange": "NYSE"}


@pytest.mark.asyncio
@pytest.mark.parametrize("path,case", [
    ("/api/companies/CACHED", "lookup_stored"),
    ("/api/companies/NEWCO", "lookup_new"),
    ("/api/companies/NOSUCH", "lookup_missing"),
    ("/api/companies/search?q=cached", "search_stored"),
    ("/api/companies/search?q=newco", "search_new"),
    ("/api/companies/trending", "trending"),
])
async def test_company_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, path, case):
    """The company lookup, the search and the trending list run their session work in thread-pool
    units, each released before the route's next SEC or Yahoo await, so eight readers on four slots
    leave nothing for the finalizer and make no checkout, statement or release on the loop. Eight
    lookups, or eight searches, of one new company race for its row: one inserts it and the rest serve
    it, whichever racers lose through the search's conflict recovery or the resolver's (whether any
    loses depends on timing; the ratchet holds where the recovery runs)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'company-routes.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    Summary.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000001-26-000001", filing_type="10-K",
                        filing_date=utcnow(), sec_url="https://example.test/filing/",
                        document_url="https://example.test/filing.htm")
        db.add(filing)
        db.commit()
        company_id, filing_id = company.id, filing.id

    async def resolve_ticker(ticker: str) -> dict[str, Any] | None:
        return dict(_NEW_COMPANY) if ticker == "NEWCO" else None

    async def search_company(query: str) -> list[dict[str, Any]]:
        if query == "cached":
            return [{"cik": "0000000001", "ticker": "CACHED", "name": "Cached fixture", "exchange": None}]
        return [dict(_NEW_COMPANY)]

    async def primary_ticker_for_cik(cik: str) -> str:
        return {"0000000001": "CACHED", "0000000009": "NEWCO"}[cik]

    async def no_quote(_ticker: str) -> None:
        return None

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    # A release on the loop runs its rollback and checkin there, and neither is a checkout or a statement.
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(companies.sec_edgar_service, "resolve_ticker", resolve_ticker)
    monkeypatch.setattr(companies.sec_edgar_service, "search_company", search_company)
    monkeypatch.setattr(companies.sec_edgar_service, "primary_ticker_for_cik", primary_ticker_for_cik)
    monkeypatch.setattr(companies, "get_stock_quote", no_quote)
    monkeypatch.setattr(companies, "_get_stock_quote_with_timeout", no_quote)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(*[client.get(path) for _ in range(8)])
        # Every checkout waited in the thread pool, and every statement and release ran there: none on
        # the loop (read before this test's own lookup below, which runs on the loop).
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # Each unit released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        assert [response.status_code for response in responses] == [404 if case == "lookup_missing" else 200] * 8
        payloads = [response.json() for response in responses]
        unquoted = {"stock_quote": None, "coverage_status": None, "coverage_reason": None}
        cached = {"id": company_id, "cik": "0000000001", "ticker": "CACHED", "name": "Cached fixture",
                  "exchange": None, **unquoted}
        if case == "lookup_missing":
            assert payloads == [{"detail": "Company not found"}] * 8
        elif case in ("lookup_new", "search_new"):
            with sessions() as db:
                [stored_id] = [row.id for row in db.query(Company).filter(Company.cik == _NEW_COMPANY["cik"])]
            new = {"id": stored_id, **_NEW_COMPANY, **unquoted, "latest_filing": None}
            assert payloads == [[new] if case == "search_new" else new] * 8
        elif case == "search_stored":
            # The search's snapshot names the filing the company page leads with, read in the same unit.
            assert [[(row["id"], row["latest_filing"]["id"]) for row in payload] for payload in payloads] == [
                [(company_id, filing_id)]] * 8
        else:
            assert payloads == ([{**cached, "latest_filing": None}] if case == "lookup_stored"
                                else [[{**cached, "latest_filing": None}]]) * 8
    finally:
        engine.dispose()


_SAVED_STATUS = {"save_missing": 404, "update_missing": 404, "delete_missing": 404}
# Each failing case's service call, made to raise after its first query: the unit's release in its finally
# still returns the connection, so the route answers 500 with nothing left for the finalizer.
_SAVED_UNIT_FAILS = {
    "save_fails": "save_summary", "list_fails": "list_saved_summaries", "status_fails": "saved_summary_status",
    "update_fails": "update_saved_summary_notes", "delete_fails": "delete_saved_summary",
}
# Each reader's library after the burst, by case: the notes of its one row, or no row.
_SAVED_NOTES_AFTER = {
    "save": [None], "save_existing": ["Renoted"], "save_missing": [], "list": ["Kept"], "status": ["Kept"],
    "update": ["Edited"], "update_missing": ["Kept"], "delete": [], "delete_missing": ["Kept"],
    **{case: ["Kept"] for case in _SAVED_UNIT_FAILS},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,case", [
    ("POST", "/api/saved-summaries/", "save"),
    ("POST", "/api/saved-summaries/", "save_existing"),
    ("POST", "/api/saved-summaries/", "save_missing"),
    ("GET", "/api/saved-summaries/", "list"),
    ("GET", "/api/saved-summaries/status/{summary_id}", "status"),
    ("PUT", "/api/saved-summaries/{saved_id}", "update"),
    ("PUT", "/api/saved-summaries/999999", "update_missing"),
    ("DELETE", "/api/saved-summaries/{saved_id}", "delete"),
    ("DELETE", "/api/saved-summaries/999999", "delete_missing"),
    ("POST", "/api/saved-summaries/", "save_fails"),
    ("GET", "/api/saved-summaries/", "list_fails"),
    ("GET", "/api/saved-summaries/status/{summary_id}", "status_fails"),
    ("PUT", "/api/saved-summaries/{saved_id}", "update_fails"),
    ("DELETE", "/api/saved-summaries/{saved_id}", "delete_fails"),
])
async def test_saved_summary_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, path, case):
    """Each saved-summary route runs its session work, its payload and the release in one thread-pool
    unit, its refusals and its failures included, so eight readers on four slots leave nothing for the
    finalizer and make no checkout, statement or release on the loop. The status route is a sync route,
    which FastAPI runs in the thread pool, and it releases its own connection as well."""
    from app.models import SavedSummary, User
    from app.routers import auth
    from app.services import saved_summary_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'saved-summary-routes.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    saved_ids: list[int] = []
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000001-26-000001", filing_type="10-K",
                        filing_date=utcnow(), sec_url="https://example.test/filing/",
                        document_url="https://example.test/filing.htm")
        db.add(filing)
        db.flush()
        summary = Summary(filing_id=filing.id, business_overview="Overview")
        db.add(summary)
        db.flush()
        summary_id = summary.id
        for i in range(8):
            reader = User(email=f"saved-reader-{i}@example.com", is_active=True)
            db.add(reader)
            db.flush()
            if case not in ("save", "save_missing"):
                row = SavedSummary(user_id=reader.id, summary_id=summary_id, notes="Kept")
                db.add(row)
                db.flush()
                saved_ids.append(row.id)
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # A statement on the loop blocks it even on a connection the thread pool checked out (the auth
    # lookup's, which the route's session keeps).
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    # A release on the loop runs its rollback and checkin there, and neither is a checkout or a statement.
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    if case in _SAVED_UNIT_FAILS:
        def fails_after_its_first_query(db: Session, *_args: Any, **_kwargs: Any) -> None:
            db.query(SavedSummary.id).first()
            raise RuntimeError("the unit failed after its first query")

        monkeypatch.setattr(saved_summary_service, _SAVED_UNIT_FAILS[case], fails_after_its_first_query)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    body = {"summary_id": 999999 if case == "save_missing" else summary_id}
    if case == "save_existing":
        body["notes"] = "Renoted"

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"saved-reader-{i}@example.com"})
        target = path.format(summary_id=summary_id, saved_id=saved_ids[i] if saved_ids else 0)
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            if method == "POST":
                return await client.post(target, json=body)
            if method == "PUT":
                return await client.put(target, params={"notes": "Edited"})
            return await client.request(method, target)

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        # Every checkout, the auth lookup's included, waited in the thread pool, and every statement and
        # release ran there: none on the loop (read before this test's own reads below).
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        assert [response.status_code for response in responses] == [
            500 if case in _SAVED_UNIT_FAILS else _SAVED_STATUS.get(case, 200)] * 8
        payloads = [response.json() for response in responses]
        if case in _SAVED_UNIT_FAILS:
            assert [payload["type"] for payload in payloads] == ["internal_server_error"] * 8
        elif case in ("save", "save_existing", "update"):
            notes = {"save": None, "save_existing": "Renoted", "update": "Edited"}[case]
            # Each payload reads the summary, filing and company rows, and a new row's created_at, inside
            # the unit.
            assert [(payload["summary_id"], payload["notes"], payload["company"]["ticker"],
                     payload["created_at"] is not None) for payload in payloads] == [
                (summary_id, notes, "CACHED", True)] * 8
        elif case == "save_missing":
            assert payloads == [{"detail": "Summary not found"}] * 8
        elif case == "list":
            assert [[(row["summary_id"], row["notes"]) for row in payload] for payload in payloads] == [
                [(summary_id, "Kept")]] * 8
        elif case == "status":
            assert payloads == [{"is_saved": True}] * 8
        elif case == "delete":
            assert payloads == [{"status": "success"}] * 8
        else:
            assert payloads == [{"detail": "Saved summary not found"}] * 8
        with sessions() as db:
            rows = db.query(SavedSummary.user_id, SavedSummary.notes).order_by(SavedSummary.user_id).all()
        # Each write landed once per reader, and each refusal wrote nothing.
        assert [tuple(row) for row in rows] == [
            (user_id, notes) for user_id in range(1, 9) for notes in _SAVED_NOTES_AFTER[case]
        ]
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["watching", "unwatched", "fails"])
async def test_upcoming_calendar_releases_its_connection_off_the_loop(monkeypatch, tmp_path, case):
    """The dashboard's upcoming calendar reads its rows and releases its session in one thread-pool
    unit, for a reader who watches a reporting company, one who watches nothing and a read that fails
    after its first query, so eight readers on four slots leave nothing for the finalizer and make no
    checkout, statement or release on the loop."""
    from app.models import EarningsEvent, User, Watchlist
    from app.routers import auth
    from app.services import calendar_service
    from app.services.earnings_calendar_service import today_eastern

    engine = create_engine(
        f"sqlite:///{tmp_path / 'upcoming-calendar.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    reporting_day = today_eastern() + timedelta(days=1)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture")
        db.add(company)
        db.flush()
        db.add(EarningsEvent(ticker="CACHED", company_name="Cached fixture", event_date=reporting_day,
                             fiscal_period_end=reporting_day - timedelta(days=30), event_time="amc"))
        for i in range(8):
            reader = User(email=f"calendar-reader-{i}@example.com", is_active=True)
            db.add(reader)
            db.flush()
            if case == "watching":
                db.add(Watchlist(user_id=reader.id, company_id=company.id))
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    if case == "fails":
        def fails_after_its_first_query(db: Session, *_args: Any, **_kwargs: Any) -> None:
            db.query(Watchlist.id).first()
            raise RuntimeError("the unit failed after its first query")

        monkeypatch.setattr(calendar_service, "upcoming_for_user", fails_after_its_first_query)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"calendar-reader-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.get("/api/dashboard/calendar/upcoming")

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # The unit released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        if case == "fails":
            assert [(response.status_code, response.json()["type"]) for response in responses] == [
                (500, "internal_server_error")] * 8
        else:
            events = [{"ticker": "CACHED", "company_name": "Cached fixture", "earnings_date": reporting_day.isoformat(),
                       "time": "amc", "eps_estimated": None, "revenue_estimated": None}] if case == "watching" else []
            assert [(response.status_code, response.json()) for response in responses] == [
                (200, {"events": events})] * 8
    finally:
        engine.dispose()


# Each failing case's service call, made to raise after its first query: the unit's release in its finally
# still returns the connection, so the route answers 500 with nothing left for the finalizer.
_ACCOUNT_UNIT_FAILS = {
    "profile_fails": ("app.services.user_account_service", "apply_profile_update"),
    "prefs_fails": ("app.routers.users", "get_or_create_preferences"),
    "prefs_update_fails": ("app.routers.users", "apply_preference_update"),
    "bell_fails": ("app.services.user_notification_feed_service", "recent_notifications"),
    "seen_fails": ("app.services.user_notification_feed_service", "mark_seen"),
}
_PREFS_DEFAULTS = {
    "notify_10k": True, "notify_10q": True, "notify_8k": False, "notify_20f": True, "notify_6k": False,
    "channel": "email", "digest": "daily", "realtime": False, "realtime_available": False, "eightk_available": False,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,case", [
    ("PATCH", "/api/users/me", "profile"),
    ("GET", "/api/users/me/notification-preferences", "prefs"),
    ("GET", "/api/users/me/notification-preferences", "prefs_first"),
    ("GET", "/api/users/me/notification-preferences", "prefs_pro"),
    ("PUT", "/api/users/me/notification-preferences", "prefs_update"),
    ("PUT", "/api/users/me/notification-preferences", "prefs_refused"),
    ("GET", "/api/users/me/notifications", "bell"),
    ("POST", "/api/users/me/notifications/seen", "seen"),
    ("PATCH", "/api/users/me", "profile_fails"),
    ("GET", "/api/users/me/notification-preferences", "prefs_fails"),
    ("PUT", "/api/users/me/notification-preferences", "prefs_update_fails"),
    ("GET", "/api/users/me/notifications", "bell_fails"),
    ("POST", "/api/users/me/notifications/seen", "seen_fails"),
])
async def test_account_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, path, case):
    """The profile edit, the alert preferences and the bell run their session work, their payload and the
    release in one thread-pool unit, a refusal and their failures included, so eight readers on four
    slots leave nothing for the finalizer and make no checkout, statement or release on the loop. The
    plan behind the preferences' Pro toggles reads the account's subscription row, inside the unit too: in
    the ``prefs_pro`` case only that row grants Pro (``is_pro`` is False), so a plan resolved after the
    release, which falls back to the mirror, answers Free."""
    import importlib

    from app.models import NotificationLog, NotificationPreferences, Subscription, User
    from app.routers import auth

    # A first read, an update and a mark each check a connection out twice (the row's reload after the
    # commit), so readers queued for a slot wait longer than the other bursts' do on a loaded host. An
    # on-loop checkout or statement still fails the loop assertions below at any timeout.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'account-routes.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000001-26-000001", filing_type="10-K",
                        filing_date=utcnow(), sec_url="https://example.test/filing/",
                        document_url="https://example.test/filing.htm")
        db.add(filing)
        db.flush()
        for i in range(8):
            reader = User(email=f"account-reader-{i}@example.com", is_active=True, full_name="Original")
            db.add(reader)
            db.flush()
            if case != "prefs_first":
                db.add(NotificationPreferences(user_id=reader.id))
            if case == "prefs_pro":
                db.add(Subscription(user_id=reader.id, plan="pro", status="active"))
            db.add(NotificationLog(user_id=reader.id, filing_id=filing.id, channel="email", status="sent"))
        db.commit()

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # A statement on the loop blocks it even on a connection the thread pool checked out (the auth lookup's,
    # which the route's session keeps), and a lazy load (the account's subscription row) is one too.
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    # A release on the loop runs its rollback and checkin there, and neither is a checkout or a statement.
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    if case in _ACCOUNT_UNIT_FAILS:
        def fails_after_its_first_query(db: Session, *_args: Any, **_kwargs: Any) -> None:
            db.query(User.id).first()
            raise RuntimeError("the unit failed after its first query")

        module, name = _ACCOUNT_UNIT_FAILS[case]
        monkeypatch.setattr(importlib.import_module(module), name, fails_after_its_first_query)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"account-reader-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            if method == "PATCH":
                return await client.patch(path, json={"full_name": "Renamed"})
            if method == "PUT":
                # A Free account's realtime toggle is coerced off by its plan.
                body = {"channel": "carrier-pigeon"} if case == "prefs_refused" else {"notify_10q": False, "realtime": True}
                return await client.put(path, json=body)
            return await client.request(method, path)

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        # Every checkout, the auth lookup's included, waited in the thread pool, and every statement and
        # release ran there: none on the loop (read before this test's own reads below).
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        failing = case in _ACCOUNT_UNIT_FAILS
        assert [response.status_code for response in responses] == [
            500 if failing else 400 if case == "prefs_refused" else 200] * 8
        payloads = [response.json() for response in responses]
        if failing:
            assert [payload["type"] for payload in payloads] == ["internal_server_error"] * 8
        elif case == "profile":
            assert payloads == [{"id": i + 1, "email": f"account-reader-{i}@example.com", "full_name": "Renamed",
                                 "is_pro": False} for i in range(8)]
        elif case in ("prefs", "prefs_first"):
            assert payloads == [_PREFS_DEFAULTS] * 8
        elif case == "prefs_pro":
            assert payloads == [{**_PREFS_DEFAULTS, "realtime_available": True, "eightk_available": True}] * 8
        elif case == "prefs_update":
            assert payloads == [{**_PREFS_DEFAULTS, "notify_10q": False}] * 8
        elif case == "prefs_refused":
            assert payloads == [{"detail": "Channel must be one of: email, in_app."}] * 8
        else:
            # The bell's one alert, unread until the reader opens it.
            assert [[(item["ticker"], item["read"]) for item in payload["items"]] for payload in payloads] == [
                [("CACHED", case == "seen")]] * 8
            assert [payload["unread_count"] for payload in payloads] == [0 if case == "seen" else 1] * 8
        with sessions() as db:
            names = [name for (name,) in db.query(User.full_name).order_by(User.id)]
            seen = [stamp is not None for (stamp,) in db.query(User.notifications_seen_at).order_by(User.id)]
            prefs = db.query(NotificationPreferences.user_id, NotificationPreferences.notify_10q).order_by(
                NotificationPreferences.user_id).all()
        # Each write landed once per reader, and the refusal and the failures wrote nothing: a first read
        # stores one row of defaults per reader, and an update stores its change.
        assert names == ["Renamed" if case == "profile" else "Original"] * 8
        assert seen == [case == "seen"] * 8
        assert [tuple(row) for row in prefs] == [(user_id, case != "prefs_update") for user_id in range(1, 9)]
    finally:
        engine.dispose()


def _account_records_fixture(monkeypatch, tmp_path):
    """A four-slot pool with eight owners, each with a Stripe customer, the data export and the account deletion
    wired to it, and the deletion's Stripe cancellation and PostHog client faked as blocking 0.05 s calls, as
    the synchronous SDKs are. Returns the engine, a session factory, the request sessions as they open, what ran
    on the loop (checkouts, statements, checkins), and each third-party call with the connections checked out
    while it ran, whether it ran on the loop, and the account it named."""
    from app.models import User
    from app.routers import auth, users

    engine = create_engine(
        f"sqlite:///{tmp_path / 'account-records.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all(User(email=f"account-owner-{i}@example.com", is_active=True, stripe_customer_id=f"cus_{i}")
                   for i in range(8))
        db.commit()

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

    loop_thread = threading.get_ident()
    on_loop: dict[str, list[bool]] = {"checkouts": [], "statements": [], "checkins": []}
    event.listen(engine, "checkout", lambda *_: on_loop["checkouts"].append(threading.get_ident() == loop_thread))
    event.listen(engine, "before_cursor_execute",
                 lambda *_: on_loop["statements"].append(threading.get_ident() == loop_thread))
    # A release on the loop runs its rollback and checkin there, and neither is a checkout or a statement.
    event.listen(engine, "checkin", lambda *_: on_loop["checkins"].append(threading.get_ident() == loop_thread))

    third_party_calls: list[tuple[str, int, bool, str]] = []

    def blocking(name: str, account: str) -> None:
        third_party_calls.append((name, engine.pool.checkedout(), threading.get_ident() == loop_thread, account))
        time.sleep(0.05)

    def cancel(stripe_customer_id: str, _user_id: int) -> None:
        blocking("Stripe cancellation", stripe_customer_id)

    class Posthog:
        """The surface of PostHog 7.71's client the deletion uses."""

        def capture(self, event: str, **kwargs: Any) -> None:
            assert event == "$delete"
            blocking("PostHog capture", kwargs["distinct_id"])

        def flush(self, timeout_seconds: float = 10) -> None:
            blocking("PostHog flush", "")

    monkeypatch.setattr(users, "_cancel_billable_subscriptions", cancel)
    monkeypatch.setattr(users, "posthog_client", Posthog())
    monkeypatch.setattr(users, "POSTHOG_AVAILABLE", True)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    return engine, sessions, request_sessions, on_loop, third_party_calls


async def _account_record_request(transport: httpx.ASGITransport, method: str, i: int) -> httpx.Response:
    """Owner ``i``'s data export (GET) or account deletion (DELETE)."""
    from app.routers import auth

    token = auth.create_access_token({"sub": f"account-owner-{i}@example.com"})
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"Authorization": f"Bearer {token}"}) as client:
        return await client.request(method, "/api/users/export" if method == "GET" else "/api/users/me")


# Each failing case's service call, made to raise after its first query: the export's unit releases the connection
# in its finally, and the deletion's rollback returns it before the unit's release, so the route answers its 500
# with nothing left for the finalizer.
_ACCOUNT_RECORD_FAILS = {
    "export_fails": ("app.services.user_data_export_service", "build_user_data_export"),
    "delete_fails": ("app.services.user_account_service", "delete_user"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,case", [
    ("GET", "export"), ("DELETE", "delete"), ("GET", "export_fails"), ("DELETE", "delete_fails"),
])
async def test_account_export_and_deletion_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, case):
    """Eight owners on four slots, exporting or deleting, a failing unit per route included: every checkout,
    statement and release runs off the loop and nothing is left for the finalizer, and each deletion makes its
    Stripe cancellation and PostHog calls off the loop, the eight naming each owner's Stripe customer and account
    once between them. The single deletion below shows those calls hold no connection, and
    test_account_deletion_api.py that a failed delete rolls back before the release."""
    import importlib

    from app.models import AuditLog, User

    engine, sessions, request_sessions, on_loop, third_party_calls = _account_records_fixture(monkeypatch, tmp_path)
    if case in _ACCOUNT_RECORD_FAILS:
        def fails_after_its_first_query(db: Session, *_args: Any, **_kwargs: Any) -> None:
            db.query(User.id).first()
            raise RuntimeError("the unit failed after its first query")

        module, name = _ACCOUNT_RECORD_FAILS[case]
        monkeypatch.setattr(importlib.import_module(module), name, fails_after_its_first_query)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        responses = await asyncio.gather(*[_account_record_request(transport, method, i) for i in range(8)])
        # Every checkout, the auth lookup's included, waited in the thread pool, and every statement and
        # release ran there: none on the loop (read before this test's own reads below).
        assert on_loop["checkouts"] and on_loop["checkouts"] == [False] * len(on_loop["checkouts"])
        assert on_loop["statements"] and on_loop["statements"] == [False] * len(on_loop["statements"])
        assert on_loop["checkins"] and on_loop["checkins"] == [False] * len(on_loop["checkins"])
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        assert [response.status_code for response in responses] == [500 if case in _ACCOUNT_RECORD_FAILS else 200] * 8
        payloads = [response.json() for response in responses]
        if case == "export":
            assert [(payload["profile"]["user_id"], payload["profile"]["email"]) for payload in payloads] == [
                (i + 1, f"account-owner-{i}@example.com") for i in range(8)]
        elif case == "delete":
            assert [{key: payload["third_party_deletions"][key] for key in ("stripe", "posthog")}
                    for payload in payloads] == [{"stripe": "subscriptions_cancelled", "posthog": "deletion_requested"}] * 8
        else:
            detail = ("We could not export your data. Try again in a moment." if method == "GET"
                      else "We could not delete your account. Contact support.")
            assert payloads == [{"detail": detail}] * 8
        # The deletions' third-party calls all run off the loop and name each owner's customer and account once
        # between them (the single deletion pins one request to its own); a failing unit's rollback undoes none.
        assert [on for _, _, on, _ in third_party_calls] == [False] * (24 if method == "DELETE" else 0)
        assert sorted(account for name, _, _, account in third_party_calls if name != "PostHog flush") == (
            sorted([f"cus_{i}" for i in range(8)] + [str(i + 1) for i in range(8)]) if method == "DELETE" else [])
        with sessions() as db:
            accounts = db.query(User.id).count()
            audit = [action for (action,) in db.query(AuditLog.action)]
        # The export's audit row follows its payload, and the deletion's precedes the account's deletion, so a
        # failed delete keeps its row (pre-existing; test_account_deletion_api.py pins it over HTTP).
        assert accounts == (0 if case == "delete" else 8)
        assert audit == {"export": ["data_exported"] * 8, "delete": ["user_deleted"] * 8,
                         "export_fails": [], "delete_fails": ["user_deleted"] * 8}[case]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_account_deletion_holds_no_connection_while_stripe_and_posthog_answer(monkeypatch, tmp_path):
    """One deletion: its Stripe cancellation, on the Stripe threads, and PostHog's capture and flush, in a
    worker thread, run with no connection checked out and none of them on the loop; then the account is gone."""
    from app.models import User

    engine, sessions, _, _, third_party_calls = _account_records_fixture(monkeypatch, tmp_path)
    try:
        response = await _account_record_request(httpx.ASGITransport(app=app, raise_app_exceptions=False), "DELETE", 0)
        assert response.status_code == 200, response.text
        assert third_party_calls == [("Stripe cancellation", 0, False, "cus_0"), ("PostHog capture", 0, False, "1"),
                                     ("PostHog flush", 0, False, "")]
        assert engine.pool.checkedout() == 0
        with sessions() as db:
            assert db.query(User.id).filter(User.email == "account-owner-0@example.com").first() is None
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "pro", "free", "missing", "taste_refused", "cap_refused", "cap_lease_refused",
])
async def test_copilot_ask_releases_its_connection_off_the_loop_before_it_streams(monkeypatch, tmp_path, case):
    """The Copilot ask stream's filing read, its snapshot and the admission (the cap read and the lease, or the
    free taste's lease) run in one thread-pool unit that releases the request session before the stream
    starts, its refusals included (the taste's at its lease, the cap's at its read and at its lease), so eight
    askers on four slots make no checkout, statement or release on the loop and leave nothing for the
    finalizer. On the loop, the admission's wait for the account's ``users`` row lock froze every request on
    the instance, and a missing filing or a cap reached at its read left its transaction for the finalizer.
    Each admitted question is metered once, its lease converted; a refusal writes nothing."""
    from datetime import timedelta
    from uuid import uuid4

    from app.config import settings
    from app.models import User, UserUsage
    from app.models.usage_reservation import UsageReservation
    from app.routers import auth
    from app.routers import summaries as summaries_router
    from app.services.copilot_service import PROVIDER_STARTED_STAGE
    from app.services.subscription_service import (
        LIFETIME_SCOPE, QA_RESERVATION_KIND, QA_TASTE_RESERVATION_KIND, get_current_month,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'copilot-ask.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    pro = case in ("pro", "missing", "cap_refused", "cap_lease_refused")
    with sessions() as db:
        company = Company(cik="0000000005", ticker="ASK", name="Ask fixture")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000005-26-000001", filing_type="10-K",
                        filing_date=utcnow(), sec_url="https://example.test/ask/",
                        document_url="https://example.test/ask.htm")
        db.add(filing)
        db.flush()
        db.add(FilingContentCache(filing_id=filing.id, critical_excerpt="Revenue was $100.0 million."))
        for i in range(8):
            asker = User(email=f"asker-{i}@example.com", is_active=True, is_pro=pro,
                         copilot_free_taste_used=2 if case == "taste_refused" else 0)
            db.add(asker)
            db.flush()
            if case == "taste_refused":
                # Two used and one held reach the taste of three: the dependency's plain read passes, and
                # the admission refuses.
                db.add(UsageReservation(user_id=asker.id, month=LIFETIME_SCOPE, kind=QA_TASTE_RESERVATION_KIND,
                                        token=uuid4().hex, expires_at=utcnow() + timedelta(minutes=5),
                                        created_at=utcnow()))
            if case == "cap_lease_refused":
                # None used and one held reach a cap of one: the cap read passes, and the lease refuses.
                db.add(UsageReservation(user_id=asker.id, month=get_current_month(), kind=QA_RESERVATION_KIND,
                                        token=uuid4().hex, expires_at=utcnow() + timedelta(minutes=5),
                                        created_at=utcnow()))
        db.commit()
        filing_id = 999 if case == "missing" else filing.id

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # The admission's statements ran on the loop on the connection the auth lookup had checked out in the thread
    # pool, and its commit gave that connection back there: neither is a checkout.
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    async def answer(*, filing, question, history=None):
        yield {"type": "progress", "stage": PROVIDER_STARTED_STAGE}
        await asyncio.sleep(0.05)  # the other askers' admissions run while this one streams
        yield {"type": "complete", "answer": "ok", "citations": [], "grounded": 0, "kind": "answer"}

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    # The metering's own short sessions, in worker threads; not request sessions.
    monkeypatch.setattr(summaries_router, "SessionLocal", sessions)
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    monkeypatch.setattr(summaries_router, "ASK_LIMITER", RateLimiter(limit=100, window_seconds=60))
    monkeypatch.setattr(summaries_router, "answer_filing_question", answer)
    monkeypatch.setattr(summaries_router, "_emit_copilot_cost_best_effort", lambda *_a, **_k: None)
    if case in ("cap_refused", "cap_lease_refused"):
        monkeypatch.setattr(settings, "COPILOT_MONTHLY_QUESTION_CAP", 0 if case == "cap_refused" else 1)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def ask(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"asker-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.post(f"/api/summaries/filing/{filing_id}/ask-stream", json={"question": "Q?"})

    try:
        responses = await asyncio.gather(*[ask(i) for i in range(8)])
        # Every checkout, the auth lookup's included, and every statement and release, the metering's included,
        # ran in the thread pool: none on the loop (read before this test's own reads below).
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        expected = {"pro": 200, "free": 200, "missing": 404, "taste_refused": 403, "cap_refused": 429,
                    "cap_lease_refused": 429}[case]
        assert [response.status_code for response in responses] == [expected] * 8
        if expected == 200:
            assert all('"type": "complete"' in response.text for response in responses)
        else:
            detail = {
                "missing": "Filing not found",
                "taste_refused": "You've used your 3 free Copilot questions.",
                "cap_refused": "You've reached this month's fair-use limit of 0 Copilot questions.",
                "cap_lease_refused": "You've reached this month's fair-use limit of 1 Copilot questions.",
            }[case]
            assert all(response.json()["detail"].startswith(detail) for response in responses)
        with sessions() as db:
            questions = [count for (count,) in db.query(UserUsage.qa_count).filter(
                UserUsage.month == get_current_month()).order_by(UserUsage.user_id)]
            tastes = [used for (used,) in db.query(User.copilot_free_taste_used).order_by(User.id)]
            leases = db.query(UsageReservation).count()
        # Each admitted question was metered once and its lease converted; a refusal metered nothing, and the
        # leases already held stay for their own questions.
        assert questions == ([1] * 8 if case == "pro" else [])
        assert tastes == [1 if case == "free" else 2 if case == "taste_refused" else 0] * 8
        assert leases == (8 if case in ("taste_refused", "cap_lease_refused") else 0)
    finally:
        engine.dispose()


def _summary_export_fixture(tmp_path, name: str, *, pro: bool):
    """A four-slot pool over one 10-K with its content cache and summary, a summary whose filing 998 is gone
    (SQLite leaves the key unenforced), and eight readers (Pro or Free)."""
    from datetime import datetime, timezone

    from app.models import User

    engine = create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=1.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="CACHED", name="Cached fixture")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000001-26-000001", filing_type="10-K",
                        filing_date=datetime(2026, 2, 3, tzinfo=timezone.utc), sec_url="https://example.test/filing/",
                        document_url="https://example.test/filing.htm")
        db.add(filing)
        db.flush()
        db.add(FilingContentCache(filing_id=filing.id, critical_excerpt="Revenue rose 10% on higher volumes."))
        db.add(Summary(filing_id=filing.id, business_overview="Overview", raw_summary={"sections": {
            "executive_snapshot": {"headline": "Revenue rose 10%.", "key_points": ["Volumes grew"]}}}))
        db.add(Summary(filing_id=998, business_overview="Orphaned"))
        for i in range(8):
            db.add(User(email=f"export-reader-{i}@example.com", is_active=True, is_pro=pro))
        db.commit()
    return engine, sessions


def _fake_weasyprint(monkeypatch, on_render: Callable[[str], None]) -> None:
    """WeasyPrint for the summary PDF: ``HTML(string=...).write_pdf()`` hands the markup to ``on_render`` and
    returns a stub, so the export's own HTML build runs on the rows the route read."""
    import sys
    import types

    class HTML:
        def __init__(self, *, string: str) -> None:
            self.markup = string

        def write_pdf(self, **_options: Any) -> bytes:
            on_render(self.markup)
            return b"%PDF-test"

    weasyprint = types.ModuleType("weasyprint")
    weasyprint.HTML = HTML
    monkeypatch.setitem(sys.modules, "weasyprint", weasyprint)


_EXPORT_STATUS = {"export": 200, "free": 403, "no_summary": 404, "no_filing": 404}


@pytest.mark.asyncio
@pytest.mark.parametrize("export", ["pdf", "csv"])
@pytest.mark.parametrize("case", ["export", "free", "no_summary", "no_filing"])
async def test_summary_exports_release_their_connection_off_the_loop(monkeypatch, tmp_path, export, case):
    """Each summary export runs its plan check (the reader's subscription read), its summary and filing reads and
    the release in one thread-pool unit, its refusals included, so eight readers on four slots (Free for the plan's
    403) make no checkout, statement or release on the loop and leave nothing for the finalizer. The export is
    built from the detached rows, which carry the filing's content cache and company. On the loop, the plan check
    and both reads ran there, the PDF's company read after them, and every case left its transaction, the auth
    lookup's, for the finalizer, the export keeping it through its build and render."""
    from app.routers import auth

    engine, _ = _summary_export_fixture(tmp_path, "summary-exports.db", pro=case != "free")
    renders: list[str] = []
    _fake_weasyprint(monkeypatch, renders.append)
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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    filing_id = {"no_summary": 999, "no_filing": 998}.get(case, 1)

    async def export_as(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"export-reader-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.get(f"/api/summaries/filing/{filing_id}/export/{export}")

    try:
        responses = await asyncio.gather(*[export_as(i) for i in range(8)])
        # Every checkout, the auth lookup's included, and every statement and release ran in the thread pool.
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        assert [response.status_code for response in responses] == [_EXPORT_STATUS[case]] * 8
        if case == "export":
            assert [response.headers["content-disposition"] for response in responses] == [
                f'attachment; filename="Cached fixture_10-K_20260203.{export}"'] * 8
            # Each build read the company's name and the summary's text from the detached rows.
            built = renders if export == "pdf" else [response.content.decode() for response in responses]
            assert len(built) == 8
            assert all("Cached fixture · 10-K summary" in text and "Revenue rose 10%." in text for text in built)
            if export == "pdf":
                assert [response.content for response in responses] == [b"%PDF-test"] * 8
            else:
                assert all(text.startswith("\ufeffEarningsNerd · AI summaries of SEC filings") for text in built)
        else:
            detail = {
                "free": f"{export.upper()} export is a Pro feature. Upgrade to Pro to access this feature.",
                "no_summary": "Summary not found",
                "no_filing": "Filing not found",
            }[case]
            assert [response.json() for response in responses] == [{"detail": detail}] * 8
            assert renders == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("export", ["pdf", "csv"])
async def test_summary_exports_hold_no_connection_while_they_render(monkeypatch, tmp_path, export):
    """The summary exports finish their plan check and reads and release the session before they render: no
    pool slot waits on the PDF's render or the CSV's build."""
    from app.routers import auth
    from app.services.export_service import ExportService

    engine, _ = _summary_export_fixture(tmp_path, "summary-export-render.db", pro=True)
    held: dict[str, int] = {}

    def render(_markup: str) -> None:
        held["pdf"] = engine.pool.checkedout()

    build_csv = ExportService.generate_csv

    def generate_csv(self, summary, filing) -> str:
        held["csv"] = engine.pool.checkedout()
        return build_csv(self, summary, filing)

    _fake_weasyprint(monkeypatch, render)
    monkeypatch.setattr(ExportService, "generate_csv", generate_csv)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    token = auth.create_access_token({"sub": "export-reader-0@example.com"})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            response = await client.get(f"/api/summaries/filing/1/export/{export}")
        assert response.status_code == 200
        # The render ran with no connection out: the route's unit had released the session.
        assert held == {export: 0}
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,case", [
    ("GET", "/api/admin/feedback", "feedback_list"),
    ("PATCH", "/api/admin/feedback/{feedback}", "feedback_status"),
    ("PATCH", "/api/admin/feedback/9999", "feedback_missing"),
    ("DELETE", "/api/admin/filing/{filing}/summary", "delete_summary"),
    ("DELETE", "/api/admin/filing/9999/summary", "filing_missing"),
    ("DELETE", "/api/admin/filing/{filing}/xbrl", "clear_xbrl"),
    ("DELETE", "/api/admin/filing/9999/xbrl", "xbrl_missing"),
    ("DELETE", "/api/admin/filing/{filing}/reset", "reset_filing"),
    ("DELETE", "/api/admin/filing/9999/reset", "reset_missing"),
    ("GET", "/api/admin/filings/audit-xbrl", "audit_xbrl"),
    ("POST", "/api/admin/filings/bulk-reset-stale", "bulk_reset_dry"),
    ("POST", "/api/admin/filings/bulk-reset-stale?dry_run=false", "bulk_reset"),
    ("POST", "/api/admin/summaries/reset-all", "reset_all_dry"),
    ("POST", "/api/admin/summaries/reset-all?dry_run=false", "reset_all"),
])
async def test_admin_maintenance_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, path, case):
    """The admin feedback triage and the filing and summary maintenance routes run their service call (with the
    status update's or the reset-all's audit row) and release in one thread-pool unit, their 404s included, so eight
    admins on four slots make no checkout, statement or release on the loop and leave nothing for the finalizer. On
    the loop, each statement after the auth lookup ran there (the stale-XBRL audit and bulk reset loading every
    filing's XBRL), each read after a write's commit checked a connection out there, and every case but a summary
    delete that found its filing left its transaction for the finalizer, the 404s included."""
    from app.models import AuditLog, User
    from app.models.feedback import Feedback
    from app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-maintenance.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    filing_ids: list[int] = []
    feedback_ids: list[int] = []
    with sessions() as db:
        company = Company(cik="0000000006", ticker="ADMN", name="Admin fixture")
        db.add(company)
        db.flush()
        for i in range(8):
            db.add(User(email=f"admin-{i}@example.com", is_active=True, is_admin=True))
            # Each filing's XBRL trails its period by ten years, so the audit and the bulk reset find all eight.
            filing = Filing(company_id=company.id, accession_number=f"0000000006-26-00000{i}", filing_type="10-K",
                            filing_date=utcnow(), period_end_date=utcnow(), sec_url=f"https://example.test/admin/{i}/",
                            document_url=f"https://example.test/admin/{i}.htm",
                            xbrl_data={"revenue": [{"period": "2015-12-31", "value": 1}]})
            db.add(filing)
            db.flush()
            db.add(Summary(filing_id=filing.id, business_overview="# Summary", raw_summary={}))
            db.add(SummaryGenerationProgress(filing_id=filing.id, stage="completed", started_at=utcnow(),
                                             updated_at=utcnow()))
            db.add(FilingContentCache(filing_id=filing.id, critical_excerpt="Revenue was $1.0 million."))
            feedback = Feedback(type="bug", message=f"Report {i}", status="new")
            db.add(feedback)
            db.flush()
            filing_ids.append(filing.id)
            feedback_ids.append(feedback.id)
        db.commit()
        # Admin i sends request i; the audit log stores the admin's id as text.
        admin_ids = {email: str(user_id) for user_id, email in db.query(User.id, User.email)}
    emails = [f"admin-{i}@example.com" for i in range(8)]

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

    loop_thread = threading.get_ident()
    loop_checkouts: list[bool] = []
    event.listen(engine, "checkout", lambda *_: loop_checkouts.append(threading.get_ident() == loop_thread))
    # The routes' statements ran on the loop on the connection the auth lookup had checked out in the thread pool,
    # and a commit gave it back there: neither is a checkout.
    loop_statements: list[bool] = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_: loop_statements.append(threading.get_ident() == loop_thread))
    loop_checkins: list[bool] = []
    event.listen(engine, "checkin", lambda *_: loop_checkins.append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def send(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"admin-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            url = path.format(filing=filing_ids[i], feedback=feedback_ids[i])
            if method == "PATCH":
                return await client.patch(url, json={"status": "triaged"})
            return await client.request(method, url)

    try:
        responses = await asyncio.gather(*[send(i) for i in range(8)])
        # Every checkout, the auth lookup's included, and every statement and release ran in the thread pool:
        # none on the loop (read before this test's own reads below).
        assert loop_checkouts and loop_checkouts == [False] * len(loop_checkouts)
        assert loop_statements and loop_statements == [False] * len(loop_statements)
        assert loop_checkins and loop_checkins == [False] * len(loop_checkins)
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        missing = case in ("feedback_missing", "filing_missing", "xbrl_missing", "reset_missing")
        assert [response.status_code for response in responses] == [404 if missing else 200] * 8
        payloads = [response.json() for response in responses]
        if case == "feedback_list":
            assert [len(payload["feedback"]) for payload in payloads] == [8] * 8
        elif case == "feedback_status":
            assert sorted((payload["id"], payload["status"]) for payload in payloads) == [
                (feedback_id, "triaged") for feedback_id in feedback_ids]
        elif missing:
            assert [payload["detail"] for payload in payloads] == [
                "Feedback not found" if case == "feedback_missing" else "Filing not found"] * 8
        elif case == "audit_xbrl":
            assert [(payload["total_filings_with_xbrl"], payload["stale_filings_count"]) for payload in payloads] == [
                (8, 8)] * 8
        elif case == "bulk_reset_dry":
            assert [payload["affected_count"] for payload in payloads] == [8] * 8
        elif case == "reset_all_dry":
            assert [payload["deleted_count"] for payload in payloads] == [8] * 8
        elif case == "delete_summary":
            assert [payload["summary_deleted"] for payload in payloads] == [True] * 8
        elif case == "clear_xbrl":
            assert [payload["had_xbrl_data"] for payload in payloads] == [True] * 8
        elif case == "reset_filing":
            assert [payload["deleted"] for payload in payloads] == [
                {"summary": True, "xbrl_data": True, "content_cache": True, "progress": True}] * 8
        elif case in ("bulk_reset", "reset_all"):
            # Each reads all eight filings or summaries before any of the others commits, or none after (below).
            counted = [payload["affected_count" if case == "bulk_reset" else "deleted_count"] for payload in payloads]
            assert set(counted) <= {0, 8} and 8 in counted, counted
        with sessions() as db:
            summaries = db.query(Summary).count()
            # A cleared JSON column holds JSON null, which a SQL IS NOT NULL still counts.
            xbrl = sum(1 for (data,) in db.query(Filing.xbrl_data) if data is not None)
            caches = db.query(FilingContentCache).count()
            statuses = sorted(status for (status,) in db.query(Feedback.status))
            audits = sorted(
                (action, user_id, user_email, entity_id or "", tuple(sorted((details or {}).items())))
                for action, user_id, user_email, entity_id, details in db.query(
                    AuditLog.action, AuditLog.user_id, AuditLog.user_email, AuditLog.entity_id, AuditLog.details)
            )
        # Each write took effect, and the reads, the dry runs and the 404s wrote nothing. SQLite has no advisory
        # locks, so here a bulk reset or reset-all can read before another's delete commits, then report, and a
        # reset-all audit, rows the other deleted; on PostgreSQL the maintenance lock runs them one at a time, and
        # each after the first finds nothing (tests/integration/test_admin_maintenance_transactions.py). Each audit
        # row names the admin whose request wrote it, and what that request answered.
        assert summaries == (0 if case in ("delete_summary", "reset_filing", "bulk_reset", "reset_all") else 8)
        assert xbrl == (0 if case in ("clear_xbrl", "reset_filing", "bulk_reset") else 8)
        assert caches == (0 if case == "reset_filing" else 8)
        assert statuses == ["triaged" if case == "feedback_status" else "new"] * 8
        if case == "feedback_status":
            assert audits == sorted(
                ("feedback_status_changed", admin_ids[email], email, str(feedback_ids[i]), (("status", "triaged"),))
                for i, email in enumerate(emails))
        elif case == "reset_all":
            # One row for each reset-all whose plan found the eight summaries, with the count it answered, and none
            # for one whose plan found none.
            deleted = (("deleted_count", 8), ("filing_type", None), ("include_saved", False), ("skipped_saved_count", 0))
            assert audits == sorted(
                ("summaries_bulk_reset", admin_ids[emails[i]], emails[i], "", deleted)
                for i, count in enumerate(counted) if count == 8)
        else:
            assert audits == []
    finally:
        engine.dispose()


def _invite_fixture(monkeypatch, tmp_path, send_invite_email):
    """A four-slot pool with eight admins, eight pending invites bound to invitees (cohort ``seed-{i}``) and eight
    used ones, the invite routes wired to it with ``send_invite_email`` as their mail sender and invitations
    ready. Returns the engine, a session factory, the request sessions as they open, whether each checkout,
    statement and checkin ran on the loop, the seeded invite ids and each admin's id as the audit log stores it."""
    from app.models import InviteCode, User
    from app.routers import admin, auth
    from app.services import legal_readiness_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-invites.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for i in range(8):
            db.add(User(email=f"admin-{i}@example.com", is_active=True, is_admin=True))
        db.flush()
        for i in range(8):
            db.add(InviteCode(code_hash=f"{i:064x}", email=f"invitee-{i}@example.com", cohort=f"seed-{i}",
                              expires_at=utcnow() + timedelta(days=7)))
            db.add(InviteCode(code_hash=f"{i + 8:064x}", email=f"redeemed-{i}@example.com",
                              expires_at=utcnow() + timedelta(days=7), used_at=utcnow()))
        db.commit()
        pending = [invite_id for (invite_id,) in db.query(InviteCode.id).filter(
            InviteCode.used_at.is_(None)).order_by(InviteCode.id)]
        used = [invite_id for (invite_id,) in db.query(InviteCode.id).filter(
            InviteCode.used_at.isnot(None)).order_by(InviteCode.id)]
        # Admin i sends request i; the audit log stores the admin's id as text.
        admin_ids = {email: str(user_id) for user_id, email in db.query(User.id, User.email)}

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

    loop_thread = threading.get_ident()
    on_loop: dict[str, list[bool]] = {"checkouts": [], "statements": [], "checkins": []}
    event.listen(engine, "checkout", lambda *_: on_loop["checkouts"].append(threading.get_ident() == loop_thread))
    # The routes' statements ran on the loop on the connection the auth lookup had checked out in the thread pool,
    # and a commit gave it back there: neither is a checkout.
    event.listen(engine, "before_cursor_execute",
                 lambda *_: on_loop["statements"].append(threading.get_ident() == loop_thread))
    event.listen(engine, "checkin", lambda *_: on_loop["checkins"].append(threading.get_ident() == loop_thread))

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    monkeypatch.setattr(admin, "send_invite_email", send_invite_email)
    monkeypatch.setattr(legal_readiness_service, "is_collection_available", lambda: True)
    monkeypatch.setattr(legal_readiness_service, "is_marketing_available", lambda: True)
    return engine, sessions, request_sessions, on_loop, pending, used, admin_ids


async def _invite_request(transport: httpx.ASGITransport, method: str, path: str, body: dict | None,
                          i: int) -> httpx.Response:
    """Admin ``i``'s request, signed in as them, with invite ``i``'s and invitee ``i``'s placeholders filled."""
    from app.routers import auth

    token = auth.create_access_token({"sub": f"admin-{i}@example.com"})
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"Authorization": f"Bearer {token}"}) as client:
        if body is None:
            return await client.request(method, path)
        return await client.request(method, path, json={key: value.format(i=i) if isinstance(value, str) else value
                                                        for key, value in body.items()})


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body,case", [
    ("GET", "/api/admin/invites", None, "list"),
    ("POST", "/api/admin/invites", {"cohort": "wave-{i}"}, "mint"),
    ("POST", "/api/admin/invites", {"email": "new-{i}@example.com", "send_email": True}, "mint_email"),
    ("POST", "/api/admin/invites/{pending}/revoke", None, "revoke"),
    ("POST", "/api/admin/invites/9999/revoke", None, "revoke_missing"),
    ("POST", "/api/admin/invites/{used}/revoke", None, "revoke_used"),
    ("POST", "/api/admin/invites/{pending}/resend", None, "resend"),
    ("POST", "/api/admin/invites/9999/resend", None, "resend_missing"),
    ("POST", "/api/admin/invites/{used}/resend", None, "resend_used"),
    ("POST", "/api/admin/invites/{pending}/resend", None, "resend_unready"),
])
async def test_admin_invite_routes_release_their_connection_off_the_loop(monkeypatch, tmp_path, method, path, body,
                                                                       case):
    """The admin invite routes run their session work in thread-pool units, released before the invite mail and
    before they answer, their 404s and 409s included: the mint and the re-send mint in one unit and write their
    audit row in another after the mail, and the list and the revoke (with its audit row) are one unit each. So
    eight admins on four slots, each mail taking 0.05 s, make no checkout, statement or release on the loop and
    leave nothing for the finalizer. On the loop, the list and the revoke ran every statement after the auth lookup
    there, and the mint and the re-send held their connection through the mail (E171); the mail case below pins that
    no connection is out while a mail sends. Odd admins' mails fail, so each audit row and answer must say whether
    its own mail went. With invitation mail closed, as production keeps it, a re-send of a bound invite answers 503
    from its unit, released, and changes nothing."""
    from app.models import AuditLog, InviteCode
    from app.services import legal_readiness_service

    sent: list[tuple[str, str]] = []

    async def send_invite_email(*, to_email: str, magic_link: str, name: str | None = None) -> None:
        await asyncio.sleep(0.05)  # the other admins' units run while this mail sends
        if int(to_email.split("@")[0].rsplit("-", 1)[1]) % 2:
            raise RuntimeError("the mail provider refused the message")
        sent.append((to_email, magic_link))

    engine, sessions, request_sessions, on_loop, pending, used, admin_ids = _invite_fixture(
        monkeypatch, tmp_path, send_invite_email)
    if case == "resend_unready":
        monkeypatch.setattr(legal_readiness_service, "is_marketing_available", lambda: False)
    emails = [f"admin-{i}@example.com" for i in range(8)]
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        responses = await asyncio.gather(*[
            _invite_request(transport, method, path.format(pending=pending[i], used=used[i]), body, i)
            for i in range(8)
        ])
        # Every checkout, the auth lookup's included, and every statement and release ran in the thread pool:
        # none on the loop (read before this test's own reads below).
        assert on_loop["checkouts"] and on_loop["checkouts"] == [False] * len(on_loop["checkouts"])
        assert on_loop["statements"] and on_loop["statements"] == [False] * len(on_loop["statements"])
        assert on_loop["checkins"] and on_loop["checkins"] == [False] * len(on_loop["checkins"])
        assert engine.pool.checkedout() == 0
        # Each route released its own connection; the dependency's finalizer found nothing open.
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]] * 8
        expected = {"revoke_missing": 404, "resend_missing": 404, "revoke_used": 409, "resend_used": 409,
                    "resend_unready": 503}.get(case, 200)
        assert [response.status_code for response in responses] == [expected] * 8
        payloads = [response.json() for response in responses]
        with sessions() as db:
            invites = {invite.id: invite for invite in db.query(InviteCode)}
            audits = sorted(
                (action, user_id, user_email, entity_type, entity_id, tuple(sorted((details or {}).items())))
                for action, user_id, user_email, entity_type, entity_id, details in db.query(
                    AuditLog.action, AuditLog.user_id, AuditLog.user_email, AuditLog.entity_type,
                    AuditLog.entity_id, AuditLog.details)
            )
        minted = sorted(set(invites) - set(pending) - set(used))
        if case == "list":
            assert [sorted(row["status"] for row in payload["invites"]) for payload in payloads] == [
                ["pending"] * 8 + ["used"] * 8] * 8
        elif expected != 200:
            assert [payload["detail"] for payload in payloads] == [{
                404: "Invite not found", 409: "Invite already redeemed",
                503: "Invitation email delivery is currently unavailable."}[expected]] * 8
        elif case in ("mint", "mint_email"):
            assert sorted(payload["id"] for payload in payloads) == minted
            assert [(payload["email"], payload["cohort"], payload["emailed"]) for payload in payloads] == [
                (f"new-{i}@example.com", None, i % 2 == 0) if case == "mint_email" else (None, f"wave-{i}", False)
                for i in range(8)]
            assert all("/register?invite=" in payload["invite_link"] for payload in payloads)
        elif case == "revoke":
            assert [(payload["invite_id"], payload["status"]) for payload in payloads] == [
                (invite_id, "revoked") for invite_id in pending]
        elif case == "resend":
            assert [payload["revoked_invite_id"] for payload in payloads] == pending
            assert sorted(payload["id"] for payload in payloads) == minted
            assert [(payload["email"], payload["cohort"], payload["emailed"]) for payload in payloads] == [
                (f"invitee-{i}@example.com", f"seed-{i}", i % 2 == 0) for i in range(8)]
        # Each write took effect, and the list, the 404s, the 409s and the 503s wrote nothing.
        assert len(minted) == (8 if case in ("mint", "mint_email", "resend") else 0)
        assert sorted(invite_id for invite_id, invite in invites.items() if invite.is_revoked) == (
            pending if case in ("revoke", "resend") else [])
        assert sorted(invite_id for invite_id, invite in invites.items() if invite.used_at is not None) == used
        # Each mail that went carried its own request's link, and each minted invite names the admin who minted it.
        assert sorted(sent) == sorted(
            (payloads[i]["email"], payloads[i]["invite_link"]) for i in range(0, 8, 2) if case in ("mint_email", "resend"))
        if case in ("mint", "mint_email", "resend"):
            assert [invites[payload["id"]].created_by for payload in payloads] == [
                int(admin_ids[email]) for email in emails]
        # Each audit row names the admin whose request wrote it and what that request answered.
        by_admin = {payload.get("revoked_invite_id", payload.get("invite_id")): payload for payload in payloads}
        if case in ("mint", "mint_email"):
            assert audits == sorted(
                ("invite_minted", admin_ids[emails[i]], emails[i], "invite", str(payload["id"]),
                 (("cohort", None), ("emailed", i % 2 == 0)) if case == "mint_email" else
                 (("cohort", f"wave-{i}"), ("emailed", False)))
                for i, payload in enumerate(payloads))
        elif case == "revoke":
            assert audits == sorted(
                ("invite_revoked", admin_ids[emails[i]], emails[i], "invite", str(pending[i]), ()) for i in range(8))
        elif case == "resend":
            assert audits == sorted(
                ("invite_resent", admin_ids[emails[i]], emails[i], "invite", str(by_admin[pending[i]]["id"]),
                 (("cohort", f"seed-{i}"), ("emailed", i % 2 == 0), ("revoked_invite_id", pending[i])))
                for i in range(8))
        else:
            assert audits == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["mint", "resend"])
async def test_invite_mint_and_resend_hold_no_connection_while_their_mail_sends(monkeypatch, tmp_path, route):
    """The mint and the re-send release their session before the invite mail, and write their audit row in a unit
    of their own after it, so no pool slot waits on the mail provider and the row records that the mail went."""
    from app.models import AuditLog
    from app.routers import admin

    held: list[tuple[str, int, int]] = []
    engine, sessions, request_sessions, _, pending, _, _ = _invite_fixture(monkeypatch, tmp_path, None)

    async def send_invite_email(*, to_email: str, magic_link: str, name: str | None = None) -> None:
        checked_out = engine.pool.checkedout()  # read before this check's own session checks one out
        with sessions() as db:
            held.append((to_email, checked_out, db.query(AuditLog).count()))

    monkeypatch.setattr(admin, "send_invite_email", send_invite_email)
    try:
        response = await _invite_request(
            httpx.ASGITransport(app=app, raise_app_exceptions=False), "POST",
            "/api/admin/invites" if route == "mint" else f"/api/admin/invites/{pending[0]}/resend",
            {"email": "new-{i}@example.com", "send_email": True} if route == "mint" else None, 0,
        )
        assert response.status_code == 200, response.text
        assert held == [("new-0@example.com" if route == "mint" else "invitee-0@example.com", 0, 0)]
        assert engine.pool.checkedout() == 0
        assert [request.open_at_close[-1:] for request in request_sessions] == [[False]]
        with sessions() as db:
            assert [(action, (details or {}).get("emailed")) for action, details in db.query(
                AuditLog.action, AuditLog.details)] == [("invite_minted" if route == "mint" else "invite_resent", True)]
    finally:
        engine.dispose()


@pytest.mark.parametrize("error", [
    OperationalError("ROLLBACK", {}, Exception("server closed the connection unexpectedly")),
    IllegalStateChangeError("Method 'close()' can't be called here; another method is in progress"),
])
def test_release_logs_a_failed_close_instead_of_raising_it(caplog, error):
    """Units release in a ``finally``, so a close that raised would replace the unit's own outcome:
    a committed rotation would answer 500, and a refresh's 401 would become a 500. The release logs
    any failed close, with its traceback, which Sentry's logging integration reports."""

    class FailingClose:
        def close(self) -> None:
            raise error

    filing_list_service.release_request_session(FailingClose())
    [logged] = [record for record in caplog.records
                if "Releasing the request session failed" in record.getMessage()]
    assert logged.exc_info[1] is error


# ── Structure: every async route keeps its request session off the loop ──────────────
#
# The ratchet: an async route never works its request session on the event loop.
#
# An ``async def`` route runs on the event loop. A query or commit on the request session there
# checks out a pooled connection on the loop and, unless the same synchronous unit releases it, keeps
# it until the sync ``get_db`` finalizer runs in the thread pool after the route yields. In production
# (four slots, no overflow) the fifth such request blocks the whole loop for the pool timeout while
# the four holders' finalizers wait for that loop: the summary read and its progress poll answered
# 4x200 then 4x500 in a burst of eight (``lessons/ops-release-cached-filing-reads-before-yield.md``).
# The fix shape is a sync function handed to ``run_in_threadpool`` that does the session work, builds
# the payload and releases the session (``get_summary``, ``get_what_changed``, ``get_company_peers``),
# or a service that reads and releases in one unit, called through ``run_in_threadpool``. A service
# called with the session on the loop checks out on the loop too.
#
# An AST walk reads every ``async def`` under ``app/routers/`` that receives a session: a parameter
# named ``db``, annotated with ``Session`` (bare or inside ``Annotated``, or through a module-level
# alias of either) or defaulting to ``Depends(get_db...)``. It follows the session into each name the
# body binds to it: by an assignment, an annotated assignment or a walrus (``s = db``,
# ``s: Session = db``, ``(s := db)``), pairwise through tuple or list unpacking (``s, n = db, 1``; with
# a starred element, those before it from the front and those after it from the back), by
# ``with db as s``, and as a nested def's or lambda's default (``def unit(s=db)``, the session inside
# that def or lambda). A value is the session when it is such a name, or when a branch of a
# conditional, a walrus's value, an operand of an ``or`` or the last operand of an ``and`` is one
# (``db if flag else None``, ``other or db``; a Session is always true, so it is never the value of an
# ``and`` it does not end).
#
# Each body is read in a scope of its own, the function's and each nested def's or lambda's: its
# parameters shadow the names outside, but for one defaulting to the session or to a unit, and what
# it binds binds nothing outside it; a class body, too, binds nothing the function's code sees. Each
# of those bodies but a class's, which is read once, in order, as it runs, is read flow-insensitively:
# again until the names bound to the session and the units in it stop growing, so a use counts
# whatever the order of the binding, the def and the use in the source.
#
# It counts each use of the session in the code that runs on the loop:
#
# - each attribute read off it (``db.query(...)``, ``db.commit()``, ``fn = db.get``,
#   ``(db if flag else other).query(...)``);
# - each call it is handed to, as an argument or a keyword's value, once per call
#   (``service.read(db, 1)``, ``service.read(session=db)``, ``await service.aread(db)``), but a thread
#   dispatcher's;
# - each ``with`` it enters (``with db:``), whose exit closes it;
# - each call, by a name bound to it, of a unit whose body uses the session: a nested sync def, a
#   lambda bound by any of the forms above, or a parameter defaulting to a unit (``unit()``,
#   ``run = unit; run()``, ``def outer(run=unit): return run()``), since that body then runs on the
#   loop. A unit's body is read by these same rules: a call there of another such unit counts, and what
#   it hands to the thread pool does not, so a unit that only dispatches
#   (``def begin(): return run_in_threadpool(meter, db)``) or only builds another unit is clean.
#
# The code that runs on the loop is the function's own body, with the bodies of its nested
# ``async def``s and classes, the decorators and defaults of its nested defs and lambdas, and the
# decorators, bases and keywords of its nested classes, which run when they are defined. The bodies
# of its nested sync defs and lambdas run where they are called or handed, normally the thread pool,
# so they count only through a call of the unit on the loop (a class's methods within its body only); an
# uncalled method, or the session itself, handed straight to the thread pool
# (``run_in_threadpool(db.commit)``, ``run_in_threadpool(service.read, db, 1)``) counts nothing. A
# thread dispatcher is a call whose last name is in ``_THREAD_DISPATCHERS``.
#
# Strict: the walk does not look inside a callee, so it counts each call the session is handed to,
# though a callee may never use it on the loop. On main four such hand-offs never do: the four OAuth
# starts' ``_start_google`` and ``_start_apple`` put their state write in the thread pool themselves
# (since #1547). ``admin_account_service.create_free_account``, a refusal, took the session until E171's
# invite slice dropped it.
# The two OAuth callbacks' ``issue_session(db, user, ..., refresh_token=...)`` is not one: it reads
# ``user.email``, which the mint's commit expired, so it refreshes the user through the request
# session, on the loop. A logged or type-checked session (``logger.info("%s", db)``,
# ``isinstance(db, Session)``) counts too, and so do a dispatcher reached through an import alias, a
# session inside ``functools.partial`` or a generator expression handed to the thread pool, an uncalled
# method handed to a dispatcher by keyword, a comprehension's variable named like the session
# (comprehensions get no scope of their own here), and, the walk being flow-insensitive, a name a body
# rebinds away from the session or from a unit. The route hands its units to ``run_in_threadpool``
# itself instead, with the session among that call's own arguments, and stops handing the session to a
# callee that never uses it. A session handed to ``stripe_threads.run_on_stripe_threads`` counts too,
# deliberately: it would hold a pooled connection on a Stripe thread across Stripe calls. There the
# session work goes in a released ``run_in_threadpool`` unit first, and the Stripe call on the Stripe
# threads with no session (E170).
#
# A function's count may not exceed its ceiling in ``ON_LOOP_CEILINGS``; an unlisted function's
# ceiling is 0, so every new async route starts clean. The ceilings are the counts when the walk last
# changed. A PR that moves a route's session work off the loop lowers its entry in the same diff and
# deletes it at 0. The ratchet fails only above a ceiling, never below one: while other branches edit
# routers in parallel (as #1325 did, moving the contact form's persistence into a service), an exact match would
# turn main red when one of them merges with fewer calls, as ``test_router_orm_ceilings_allowlist.py``
# explains. Lowering is therefore each fixing PR's job, checked in review.
#
# Out of reach, and left to the burst test above for the routes it lists and to review elsewhere:
# - a session reached through a container: an argument (``service.read((db, 1))``), a starred or
#   double-starred argument (``service.read(*[db])``, ``service.read(**{"session": db})``), a name
#   holding one (``service.read(*args)``, ``first, *rest = 1, db``), an unpacking that cannot place
#   it (``first, s = *rows, db, *more``), a loop over one (``for s in (db,)``) or an index
#   (``sessions[0]``);
# - a session reached through an attribute (``holder.db``), or returned by a unit
#   (``def handle(): return db``, then ``handle().query(...)``);
# - a unit called other than by a name bound to it: a lambda called where it is written, a method of a
#   nested class (``Unit().run()``), a unit a call returns or wraps (``run = make_unit(1); run()``,
#   ``run = partial(unit, 1); run()``), or a unit handed to a callee that calls it on the loop
#   (``service.call(lambda: db.query(...))``);
# - a unit over the session handed to ``run_on_stripe_threads`` (``run_on_stripe_threads(unit)``): it
#   holds the connection on a Stripe thread across its Stripe calls, as a session handed there would,
#   but the walk does not read what a callee does with a unit;
# - a session the route opens itself from ``SessionLocal`` (it does not wait on the dependency's
#   finalizer);
# - an ORM instance's lazy load, or its refresh once a commit has expired it (the generate stream's
#   force branch, E104, has its own case above, and the OAuth callbacks' ``issue_session`` counts as
#   the hand-off it is).
#
# ``test_walk_sees_each_form`` scores the walk on planted forms, the gaps and strict forms among them,
# so a regression in the walk fails there instead of passing every router vacuously.

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# (router file relative to backend/, function name) -> its ceiling. Counted by this file's own walk
# when the ratchet landed (2026-10-16), after its PR took the summary read and its progress poll off
# the loop, and recounted when the walk began counting the session handed to a call (2026-10-24):
# each entry is a route E121 (``auth.py``) or E171 names in ``tasks/todo.md``. The blank line between
# entries keeps in-place number edits on different entries mergeable in any order.
ON_LOOP_CEILINGS: dict[tuple[str, str], int] = {
    ("app/routers/admin.py", "refresh_stale_summaries"): 2,

    ("app/routers/auth.py", "apple_callback"): 6,

    ("app/routers/auth.py", "apple_login"): 1,

    ("app/routers/auth.py", "apple_start"): 1,

    ("app/routers/auth.py", "change_password"): 2,

    ("app/routers/auth.py", "google_callback"): 6,

    ("app/routers/auth.py", "google_login"): 1,

    ("app/routers/auth.py", "google_start"): 1,

    ("app/routers/auth.py", "list_connections"): 1,

    ("app/routers/auth.py", "register"): 5,

    ("app/routers/auth.py", "reset_password"): 2,

    ("app/routers/auth.py", "unlink_connection"): 2,

    ("app/routers/auth.py", "verify_email"): 3,

    ("app/routers/summaries.py", "generate_summary_stream"): 7,
}

# The walk must keep seeing the routers' async session routes; fewer means a broken walk.
MIN_ASYNC_SESSION_FUNCTIONS = 60

# Callees that run their callable argument in a worker thread of the default pool, where a unit of
# session work belongs. ``stripe_threads.run_on_stripe_threads`` is not one: a session handed to it
# would hold a pooled connection on a Stripe thread across Stripe calls, so it counts as a hand-off.
_THREAD_DISPATCHERS = frozenset({"run_in_threadpool", "run_owned_sync", "to_thread", "run_sync", "run_in_executor"})


def _tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _names_session(node: ast.AST | None, aliases: set[str]) -> bool:
    """Whether an annotation or default names a session: ``Session``, ``Depends(get_db...)``, or a
    module-level alias of either."""
    if node is None:
        return False
    for part in ast.walk(node):
        if _tail(part) in {"Session", "get_db"} | aliases:
            return True
    return False


def _session_params(fn: ast.AsyncFunctionDef, aliases: set[str]) -> set[str]:
    positional = fn.args.posonlyargs + fn.args.args
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(fn.args.defaults))
    defaults += fn.args.defaults
    pairs = list(zip(positional, defaults)) + list(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
    return {
        arg.arg for arg, default in pairs
        if arg.arg == "db" or _names_session(arg.annotation, aliases) or _names_session(default, aliases)
    }


def _values(node: ast.AST | None) -> Iterator[ast.AST]:
    """What ``node`` may evaluate to: itself, or each branch of a conditional, a walrus's value, each
    operand of an ``or`` and the last operand of an ``and`` (an earlier one is the value of an ``and``
    only when false, which a Session or a function never is)."""
    if isinstance(node, ast.IfExp):
        yield from _values(node.body)
        yield from _values(node.orelse)
    elif isinstance(node, ast.BoolOp):
        for value in node.values if isinstance(node.op, ast.Or) else node.values[-1:]:
            yield from _values(value)
    elif isinstance(node, ast.NamedExpr):
        yield from _values(node.value)
    elif node is not None:
        yield node


def _is_session(node: ast.AST | None, names: set[str]) -> bool:
    return any(isinstance(value, ast.Name) and value.id in names for value in _values(node))


def _defaults(args: ast.arguments) -> list[tuple[str, ast.expr]]:
    """Each parameter in ``args`` that has a default, with its default."""
    positional = args.posonlyargs + args.args
    pairs = list(zip((arg.arg for arg in positional[len(positional) - len(args.defaults):]), args.defaults))
    pairs += [(arg.arg, default) for arg, default in zip(args.kwonlyargs, args.kw_defaults) if default is not None]
    return pairs


def _unpacked(targets: list[ast.expr], values: list[ast.expr]) -> list[tuple[ast.expr, ast.expr]]:
    """The (target, value) pairs an unpacking assigns one to one: all of them with no starred element,
    else those before the first starred element on either side, matched from the front, and those
    after the last one, matched from the back."""
    target_stars, value_stars = (
        [index for index, element in enumerate(elements) if isinstance(element, ast.Starred)]
        for elements in (targets, values)
    )
    if not target_stars and not value_stars:
        return list(zip(targets, values))
    front = min(stars[0] for stars in (target_stars, value_stars) if stars)
    back = min(
        len(elements) - (stars[-1] + 1 if stars else front)
        for elements, stars in ((targets, target_stars), (values, value_stars))
    )
    pairs = list(zip(targets[:front], values[:front]))
    return pairs + list(zip(targets[len(targets) - back:], values[len(values) - back:]))


def _parameters(args: ast.arguments) -> set[str]:
    """Every parameter name in ``args``."""
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
    return {arg.arg for arg in every if arg is not None}


def _on_loop_uses(fn: ast.AsyncFunctionDef, sessions: set[str]) -> list[tuple[int, str]]:
    """``(line, use)`` for each use of the session on the loop in ``fn``: an attribute read off it,
    ``handed to <callee>`` for a call it is handed to, ``closed at its with's exit`` for a ``with`` it
    enters, or ``calls <name> on the loop`` for a unit whose body uses it, called there by a name bound
    to that unit.

    Each body, the function's and each nested def's or lambda's, is read flow-insensitively: again
    until the names bound to the session and the units in it stop growing, and its last pass counts."""

    def settle(body: list[ast.AST], scope: set[str], callable_units: set[str]) -> list[tuple[int, str]]:
        while True:
            known = len(scope), len(callable_units)
            uses: list[tuple[int, str]] = []
            walk(body, scope, callable_units, uses.append)
            if (len(scope), len(callable_units)) == known:
                return uses

    def walk(
        body: list[ast.AST], scope: set[str], callable_units: set[str], record: Callable[[tuple[int, str]], None],
    ) -> None:
        """Read ``body`` as code that runs on the loop, where ``scope`` names the session and
        ``callable_units`` the units, and record each use."""
        handed_to_thread: set[int] = set()

        def read_scoped(args: ast.arguments, scoped_body: list[ast.AST]) -> list[tuple[int, str]]:
            """The uses in a nested def's or lambda's body when it runs, read by these same rules: its own
            parameters shadow the names outside, but for one defaulting to the session or to a unit."""
            own = _parameters(args)
            defaults = _defaults(args)
            inner = (scope - own) | {parameter for parameter, default in defaults if _is_session(default, scope)}
            inner_units = (callable_units - own) | {
                parameter for parameter, default in defaults if any(is_unit(value) for value in _values(default))
            }
            return settle(scoped_body, inner, inner_units)

        def is_unit(value: ast.AST) -> bool:
            if isinstance(value, ast.Lambda):
                return bool(read_scoped(value.args, [value.body]))
            return isinstance(value, ast.Name) and value.id in callable_units

        def bind(target: ast.AST, value: ast.AST | None) -> None:
            if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
                for part, part_value in _unpacked(target.elts, value.elts):
                    bind(part, part_value)
            elif isinstance(target, ast.Name):
                if _is_session(value, scope):
                    scope.add(target.id)
                if any(is_unit(part) for part in _values(value)):
                    callable_units.add(target.id)

        def visit(node: ast.AST) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                # Its decorators and defaults run here, when it is defined.
                for part in [*getattr(node, "decorator_list", []), *node.args.defaults, *node.args.kw_defaults]:
                    if part is not None:
                        visit(part)
                if isinstance(node, ast.AsyncFunctionDef):
                    # Its body runs on the loop, when it is awaited or iterated.
                    for use in read_scoped(node.args, node.body):
                        record(use)
                elif isinstance(node, ast.FunctionDef) and read_scoped(node.args, node.body):
                    # Its body runs where it is called or handed, normally the thread pool; called by a
                    # name here, it runs on the loop.
                    callable_units.add(node.name)
                return
            if isinstance(node, ast.ClassDef):
                # Its decorators, bases and keywords, and its body, run here, when it is defined. Its body
                # binds nothing the function's code sees, so its methods are units within it only.
                for part in [*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords)]:
                    visit(part)
                walk(node.body, set(scope), set(callable_units), record)
                return
            if isinstance(node, ast.Call) and _tail(node.func) in _THREAD_DISPATCHERS:
                handed_to_thread.update(id(argument) for argument in node.args)
            elif isinstance(node, ast.Call):
                arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
                if any(_is_session(argument, scope) for argument in arguments):
                    record((node.lineno, f"handed to {ast.unparse(node.func)}"))
                elif isinstance(node.func, ast.Name) and node.func.id in callable_units:
                    record((node.lineno, f"calls {node.func.id} on the loop"))
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    bind(target, node.value)
            elif isinstance(node, ast.NamedExpr):
                bind(node.target, node.value)
            elif isinstance(node, ast.withitem):
                if _is_session(node.context_expr, scope):
                    record((node.context_expr.lineno, "closed at its with's exit"))
                if node.optional_vars is not None:
                    bind(node.optional_vars, node.context_expr)
            if (
                isinstance(node, ast.Attribute)
                and _is_session(node.value, scope)
                and id(node) not in handed_to_thread
            ):
                record((node.lineno, node.attr))
            for child in ast.iter_child_nodes(node):
                visit(child)

        for statement in body:
            visit(statement)

    return settle(fn.body, set(sessions), set())


def on_loop_session_uses(source: str) -> dict[str, list[tuple[int, str]]]:
    """Every ``async def`` in ``source`` that receives a session -> its uses of it on the loop.

    A function nested in one already read is part of it; any other function is searched for
    async session functions of its own."""
    tree = ast.parse(source)
    aliases = {
        target.id
        for statement in tree.body if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name) and _names_session(statement.value, set())
    }
    found: dict[str, list[tuple[int, str]]] = {}

    def search(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.AsyncFunctionDef) and (sessions := _session_params(child, aliases)):
                found.setdefault(child.name, []).extend(_on_loop_uses(child, sessions))
            else:
                search(child)

    search(tree)
    return found


def _router_uses() -> dict[tuple[str, str], list[tuple[int, str]]]:
    uses: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        relative = path.relative_to(BACKEND_DIR).as_posix()
        for name, sites in on_loop_session_uses(path.read_text(encoding="utf-8")).items():
            uses[(relative, name)] = sites
    return uses


def _over_ceilings(
    uses: dict[Any, list[tuple[int, str]]], ceilings: dict[Any, int],
) -> dict[Any, list[tuple[int, str]]]:
    """Each function whose uses on the loop outnumber its ceiling (0 when unlisted), with its uses."""
    return {key: sites for key, sites in uses.items() if len(sites) > ceilings.get(key, 0)}


def test_async_routes_keep_the_request_session_off_the_loop():
    uses = _router_uses()
    assert len(uses) >= MIN_ASYNC_SESSION_FUNCTIONS, f"the walk found only {len(uses)} async session functions"
    over = {f"{path}::{name}": sites for (path, name), sites in _over_ceilings(uses, ON_LOOP_CEILINGS).items()}
    assert not over, (
        "These async routes work their request session on the event loop, hand it to a call there, "
        f"or call a unit that uses it there, beyond their ceiling (line, use): {over}. Move the "
        "session work, the payload and the release into one sync function handed to "
        "run_in_threadpool, or into a service that reads and releases in one unit, called through "
        "run_in_threadpool with the session as its argument: a service called with the session on "
        "the loop checks out on the loop too (lessons/ops-release-cached-filing-reads-before-yield.md). "
        "Do not raise a ceiling to pass."
    )


_PLANTED = '''
from typing import Annotated, Callable
from fastapi import Depends
from fastapi.concurrency import run_in_threadpool as threadpool
from app.services.stripe_threads import run_on_stripe_threads
from sqlalchemy import orm
from sqlalchemy.orm import Session
from app.database import get_db
import anyio
import asyncio
import functools

SessionDep = Annotated[Session, Depends(get_db)]

async def flags_a_query_chain(db: Session = Depends(get_db)):
    return db.query(Row).filter(Row.id == 1).first()

async def flags_each_call_in_branches(flag: bool, db: Session = Depends(get_db)):
    if flag:
        try:
            db.add(Row())
            db.commit()
        except ValueError:
            db.rollback()
        finally:
            db.close()

async def flags_a_scoped_dependency(db: Session = Depends(get_db, scope="function")):
    return db.get(Row, 1)

async def flags_an_annotated_dependency(session: Annotated[Session, Depends(get_db)]):
    return session.execute(statement)

async def flags_a_module_alias(session: SessionDep):
    return session.scalars(statement)

async def flags_a_qualified_annotation(session: orm.Session):
    return session.scalar(statement)

async def flags_an_alias_in_the_body(db: Session = Depends(get_db)):
    held = db
    return held.query(Row).all()

async def flags_an_annotated_alias(db: Session = Depends(get_db)):
    held: Session = db
    return held.query(Row).all()

async def flags_a_walrus_alias(db: Session = Depends(get_db)):
    if (held := db) is not None:
        return held.query(Row).all()

async def flags_a_bound_method(db: Session = Depends(get_db)):
    read = db.get
    return read(Row, 1)

async def flags_a_nested_async_def(db: Session = Depends(get_db)):
    async def stream():
        yield db.query(Row).count()
    return stream()

async def flags_a_comprehension(ids: list, db: Session = Depends(get_db)):
    return [db.get(Row, row_id) for row_id in ids]

def factory():
    async def flags_a_route_a_factory_builds(db: Session = Depends(get_db)):
        return db.query(Row).all()
    return flags_a_route_a_factory_builds

async def clean_threadpool_closure(db: Session = Depends(get_db)):
    def unit():
        try:
            return db.query(Row).all()
        finally:
            release(db)
    return await run_in_threadpool(unit)

async def clean_uncalled_method_to_the_pool(db: Session = Depends(get_db)):
    await run_in_threadpool(db.commit)
    await anyio.to_thread.run_sync(db.rollback)
    await asyncio.to_thread(db.close)

async def clean_lambda_to_the_pool(db: Session = Depends(get_db)):
    return await run_in_threadpool(lambda: db.query(Row).all())

async def clean_no_session(request: Request):
    return await request.json()

def clean_sync_route(db: Session = Depends(get_db)):
    return db.query(Row).all()

async def flags_a_service_on_the_loop(db: Session = Depends(get_db)):
    return service.read(db, 1)

async def flags_a_keyword_handoff(db: Session = Depends(get_db)):
    return service.read(row_id=1, session=db)

async def flags_one_call_handed_the_session_twice(db: Session = Depends(get_db)):
    return service.copy(db, target=db)

async def flags_an_awaited_service(db: Session = Depends(get_db)):
    return await service.aread(db, 1)

async def flags_a_handoff_through_an_alias(db: Session = Depends(get_db)):
    held = db
    return service.read(held, 1)

async def flags_a_sync_def_called_with_the_session(db: Session = Depends(get_db)):
    def unit(session):
        return session.query(Row).all()
    return unit(db)

async def flags_a_handoff_in_a_nested_async_def(db: Session = Depends(get_db)):
    async def stream():
        yield service.read(db, 1)
    return stream()

async def flags_a_handoff_and_a_read(db: Session = Depends(get_db)):
    rows = service.read(db, 1)
    db.commit()
    return rows

async def clean_service_to_the_pool(db: Session = Depends(get_db)):
    await run_in_threadpool(service.read, db, 1)
    await run_owned_sync(service.read, db, 1)
    await run_in_threadpool(service.read, row_id=1, session=db)
    await anyio.to_thread.run_sync(service.read, db)
    await asyncio.get_running_loop().run_in_executor(None, service.read, db)
    return await asyncio.to_thread(service.read, db, 1)

async def flags_a_conditional_argument(flag: bool, db: Session = Depends(get_db)):
    return service.read(db if flag else None)

async def flags_a_boolean_argument(db: Session = Depends(get_db)):
    return service.read(db or other)

async def flags_the_other_branch_of_a_conditional(flag: bool, db: Session = Depends(get_db)):
    return service.read(None if flag else db)

async def flags_the_last_operand_of_an_and(flag: bool, db: Session = Depends(get_db)):
    return service.read(flag and db)

async def clean_an_earlier_operand_of_an_and(db: Session = Depends(get_db)):
    return service.read(db and other)

async def clean_a_conditional_on_the_session(db: Session = Depends(get_db)):
    return service.read(other if db else None)

async def flags_a_read_off_a_conditional(flag: bool, db: Session = Depends(get_db)):
    return (db if flag else other).query(Row).all()

async def flags_a_read_off_a_boolean(db: Session = Depends(get_db)):
    return (other or db).commit()

async def flags_a_read_off_a_walrus(db: Session = Depends(get_db)):
    return (held := db).query(Row).all()

async def flags_a_walrus_argument(db: Session = Depends(get_db)):
    service.read((held := db))
    return held.query(Row).all()

async def flags_an_alias_by_a_conditional(flag: bool, db: Session = Depends(get_db)):
    held = db if flag else None
    return held.query(Row).all()

async def flags_an_alias_by_unpacking(db: Session = Depends(get_db)):
    held, count = db, 1
    return held.query(Row).limit(count).all()

async def flags_an_alias_by_list_unpacking(db: Session = Depends(get_db)):
    [held, limit] = [db, 1]
    return held.query(Row).limit(limit).all()

async def flags_an_alias_by_nested_unpacking(db: Session = Depends(get_db)):
    limit, (held, flag) = 1, (db, True)
    return held.query(Row).limit(limit).all()

async def flags_an_alias_by_with(db: Session = Depends(get_db)):
    with db as held:
        return held.query(Row).all()

async def flags_a_with_block(db: Session = Depends(get_db)):
    with db:
        rows = service_rows()
    return rows

async def flags_an_alias_by_a_nested_async_default(db: Session = Depends(get_db)):
    async def inner(held=db):
        return held.query(Row).all()
    return await inner()

async def flags_an_alias_by_a_keyword_only_default(db: Session = Depends(get_db)):
    async def inner(*, held=db):
        return held.query(Row).all()
    return await inner()

async def flags_a_decorator_on_a_nested_def(db: Session = Depends(get_db)):
    @register(db)
    def unit():
        return 1
    return await run_in_threadpool(unit)

async def flags_a_default_on_a_nested_def(db: Session = Depends(get_db)):
    def unit(rows=service.read(db)):
        return rows
    return await run_in_threadpool(unit)

async def flags_a_keyword_only_default_on_a_nested_def(db: Session = Depends(get_db)):
    def unit(*, rows=service.read(db)):
        return rows
    return await run_in_threadpool(unit)

async def flags_a_lambda_default(db: Session = Depends(get_db)):
    unit = lambda rows=db.query(Row).all(): rows
    return await run_in_threadpool(unit)

async def flags_only_a_lambdas_default_on_the_loop(db: Session = Depends(get_db)):
    unit = lambda rows=service.read(db): rows
    return unit()

async def flags_a_class_body(db: Session = Depends(get_db)):
    class Payload:
        rows = db.query(Row).all()
    return Payload

async def flags_a_closure_called_on_the_loop(db: Session = Depends(get_db)):
    def unit():
        return db.query(Row).all()
    return unit()

async def flags_a_lambda_called_on_the_loop(db: Session = Depends(get_db)):
    unit = lambda: db.query(Row).all()
    return unit()

async def flags_a_closure_over_a_default_called_on_the_loop(db: Session = Depends(get_db)):
    def unit(held=db):
        return held.query(Row).all()
    return unit()

async def flags_a_default_after_a_plain_parameter(db: Session = Depends(get_db)):
    def unit(label, held=db):
        return held.query(Row).all()
    return unit("rows")

async def flags_a_positional_only_default(db: Session = Depends(get_db)):
    def unit(held=db, /):
        return held.query(Row).all()
    return unit()

async def flags_a_lambda_over_its_own_default(db: Session = Depends(get_db)):
    unit = lambda held=db: held.query(Row).all()
    return unit()

async def flags_a_lambda_bound_by_a_walrus(db: Session = Depends(get_db)):
    if (unit := lambda: db.query(Row).all()):
        return unit()

async def flags_a_lambda_bound_by_unpacking(db: Session = Depends(get_db)):
    unit, limit = lambda: db.query(Row).all(), 1
    return unit()

async def flags_a_lambda_bound_by_a_conditional(flag: bool, db: Session = Depends(get_db)):
    unit = (lambda: db.query(Row).all()) if flag else (lambda: [])
    return unit()

async def flags_a_lambda_bound_by_an_annotation(db: Session = Depends(get_db)):
    unit: Callable[[], list] = lambda: db.query(Row).all()
    return unit()

async def flags_a_unit_called_through_an_alias(db: Session = Depends(get_db)):
    def unit():
        return db.query(Row).all()
    run = unit
    return run()

async def flags_a_unit_handed_the_session_once(db: Session = Depends(get_db)):
    def unit(held):
        db.flush()
        return held.query(Row).all()
    return unit(db)

async def flags_a_unit_defined_after_its_caller(db: Session = Depends(get_db)):
    async def stream():
        yield unit()
    def unit():
        return db.query(Row).all()
    return stream()

async def flags_a_call_before_the_def_in_a_loop(db: Session = Depends(get_db)):
    for attempt in range(2):
        if attempt:
            return unit()
        def unit():
            return db.query(Row).all()

async def flags_a_unit_calling_a_unit(db: Session = Depends(get_db)):
    def build():
        return load()
    def load():
        return db.query(Row).all()
    return build()

async def flags_a_unit_over_an_alias_bound_after_it(db: Session = Depends(get_db)):
    def unit():
        return held.query(Row).all()
    held = db
    return unit()

async def flags_an_alias_bound_after_a_nested_async_def(db: Session = Depends(get_db)):
    async def stream():
        yield held.query(Row).count()
    held = db
    return stream()

async def flags_a_unit_calling_a_later_unit_inside_a_unit(db: Session = Depends(get_db)):
    def outer():
        def build():
            return load()
        def load():
            return db.query(Row).all()
        return build()
    return outer()

async def flags_an_alias_after_its_use_inside_a_unit(db: Session = Depends(get_db)):
    def unit():
        for attempt in range(2):
            if attempt:
                return held.query(Row).all()
            held = db
    return unit()

async def flags_a_call_before_the_def_in_a_loop_inside_a_unit(db: Session = Depends(get_db)):
    def unit():
        for attempt in range(2):
            if attempt:
                return load()
            def load():
                return db.query(Row).all()
    return unit()

async def flags_a_chain_of_three_units(db: Session = Depends(get_db)):
    def first():
        return second()
    def second():
        return third()
    def third():
        return db.query(Row).all()
    return first()

async def flags_a_lambda_bound_as_a_units_default(db: Session = Depends(get_db)):
    def outer(run=lambda: db.query(Row).all()):
        return run()
    return outer()

async def flags_a_unit_bound_as_a_units_default(db: Session = Depends(get_db)):
    def load():
        return db.query(Row).all()
    def outer(run=load):
        return run()
    return outer()

async def flags_a_unit_bound_as_a_nested_async_default(db: Session = Depends(get_db)):
    def load():
        return db.query(Row).all()
    async def stream(run=load):
        yield run()
    return stream()

async def flags_a_lambda_bound_as_a_lambdas_default(db: Session = Depends(get_db)):
    outer = lambda run=lambda: db.query(Row).all(): run()
    return outer()

async def flags_a_keyword_only_session_default_on_a_unit(db: Session = Depends(get_db)):
    def unit(*, held=db):
        return held.query(Row).all()
    return unit()

async def flags_a_conditional_default_on_a_unit(db: Session = Depends(get_db)):
    def unit(held=other or db):
        return held.query(Row).all()
    return unit()

async def flags_a_conditional_default_on_a_nested_async_def(flag: bool, db: Session = Depends(get_db)):
    async def inner(held=db if flag else None):
        return held.query(Row).all()
    return await inner()

async def flags_a_with_on_a_conditional(flag: bool, db: Session = Depends(get_db)):
    with (db if flag else other):
        pass

async def flags_a_class_header(db: Session = Depends(get_db)):
    @register(db)
    class Payload(make_base(db), metaclass=meta(db)):
        pass
    return Payload

async def clean_a_unit_that_hands_the_session_to_the_pool(db: Session = Depends(get_db)):
    def begin():
        return run_in_threadpool(service.charge, db, 1)
    return await begin()

async def clean_a_unit_factory(db: Session = Depends(get_db)):
    def make_unit(row_id):
        def unit():
            return db.get(Row, row_id)
        return unit
    return await run_in_threadpool(make_unit(1))

async def clean_a_unit_shadowing_the_session(db: Session = Depends(get_db)):
    def unit(db):
        return db.query(Row).all()
    return unit(other)

async def clean_a_method_named_like_a_free_function(db: Session = Depends(get_db)):
    class Reader:
        def read(self):
            return db.query(Row).all()
    return read(), Reader

async def clean_a_unit_parameter_defaulting_to_the_session(request: Request, db: Session = Depends(get_db)):
    def unit(session=db):
        return session.query(Row).all()
    session = request.session
    return session.get("key"), await run_in_threadpool(unit)

async def clean_a_positional_only_parameter_shadowing(db: Session = Depends(get_db)):
    def unit(db, /):
        return db.query(Row).all()
    return unit(other)

async def clean_a_keyword_only_parameter_shadowing(db: Session = Depends(get_db)):
    def unit(*, db):
        return db.query(Row).all()
    return unit(db=other)

async def clean_a_varargs_parameter_shadowing(db: Session = Depends(get_db)):
    def unit(*db):
        return db.count(None)
    return unit()

async def clean_a_kwargs_parameter_shadowing(db: Session = Depends(get_db)):
    def unit(**db):
        return db.get("key")
    return unit()

async def clean_a_parameter_shadowing_a_unit(db: Session = Depends(get_db)):
    def load():
        return db.query(Row).all()
    def outer(load):
        return load()
    return outer(len), await run_in_threadpool(load)

async def clean_a_lambda_parameter_shadowing(db: Session = Depends(get_db)):
    unit = lambda db: db.query(Row).all()
    return unit(other)

async def clean_a_lambda_that_only_dispatches(db: Session = Depends(get_db)):
    begin = lambda: run_in_threadpool(service.charge, db, 1)
    return await begin()

async def clean_a_nested_async_parameter_shadowing(db: Session = Depends(get_db)):
    async def inner(db):
        return db.query(Row).all()
    return await inner(SessionLocal())

async def flags_a_method_called_in_its_class_body(db: Session = Depends(get_db)):
    class Payload:
        def load():
            return db.query(Row).all()
        rows = load()
    return Payload

async def clean_a_class_body_binding(request: Request, db: Session = Depends(get_db)):
    class Config:
        session = db
        load = lambda: db.query(Row).all()
    session = request.session
    return session.get("key"), load(), Config

async def clean_a_method_call_named_like_a_unit(db: Session = Depends(get_db)):
    def load():
        return db.query(Row).all()
    rows = await run_in_threadpool(load)
    return cache.load(rows)

async def flags_a_bare_db_parameter(db):
    return db.query(Row).all()

async def flags_a_depends_default_alone(conn=Depends(get_db)):
    return conn.query(Row).all()

async def clean_closure_called_in_the_pool(db: Session = Depends(get_db)):
    def unit():
        return db.query(Row).all()
    return await run_in_threadpool(lambda: unit())

async def clean_helper_called_on_the_loop(db: Session = Depends(get_db)):
    def label(row_id):
        return f"row {row_id}"
    return await run_in_threadpool(service.read, db, label(1))

async def strict_partial_to_the_pool(db: Session = Depends(get_db)):
    return await run_in_threadpool(functools.partial(service.read, db, 1))

async def strict_a_logged_or_type_checked_session(db: Session = Depends(get_db)):
    logger.info("serving %s", db)
    return isinstance(db, Session)

async def strict_a_dispatcher_through_an_import_alias(db: Session = Depends(get_db)):
    return await threadpool(service.read, db, 1)

async def strict_a_generator_handed_to_the_pool(ids: list, db: Session = Depends(get_db)):
    return await run_in_threadpool(list, (db.get(Row, row_id) for row_id in ids))

async def strict_a_method_handed_to_the_pool_by_keyword(db: Session = Depends(get_db)):
    return await run_in_threadpool(func=db.commit)

async def strict_a_rebound_alias(db: Session = Depends(get_db)):
    held = db
    held = other
    return held.query(Row).all()

async def strict_a_rebound_unit_name(db: Session = Depends(get_db)):
    def unit():
        return db.query(Row).all()
    unit = label
    return unit()

async def strict_a_comprehension_variable_named_like_the_session(sessions: list, db: Session = Depends(get_db)):
    return [db.info for db in sessions]

async def strict_a_session_handed_to_the_stripe_threads(db: Session = Depends(get_db)):
    return await run_on_stripe_threads(service.read, db, 1)

async def gap_session_in_a_container(db: Session = Depends(get_db)):
    return service.read((db, 1))

async def gap_session_starred(db: Session = Depends(get_db)):
    return service.read(*[db], **{"session": db})

async def gap_session_in_a_name_holding_a_container(db: Session = Depends(get_db)):
    args = (db, 1)
    return service.read(*args)

async def gap_loop_over_a_container(db: Session = Depends(get_db)):
    for held in (db,):
        held.query(Row).all()

async def gap_session_by_an_index(db: Session = Depends(get_db)):
    sessions = [db]
    return sessions[0].query(Row).all()

async def flags_an_alias_before_a_starred_target(db: Session = Depends(get_db)):
    held, *rest = db, 1, 2
    return held.query(Row).all()

async def flags_an_alias_after_a_starred_target(db: Session = Depends(get_db)):
    first, *rest, held = 1, 2, 3, db
    return held.query(Row).all()

async def flags_an_alias_after_a_starred_value(rows: list, db: Session = Depends(get_db)):
    first, held = *rows, db
    return held.query(Row).all()

async def gap_session_under_a_starred_target(db: Session = Depends(get_db)):
    first, *rest = 1, db
    return rest[0].query(Row).all()

async def gap_session_between_starred_values(rows: list, more: list, db: Session = Depends(get_db)):
    first, held = *rows, db, *more
    return first.query(Row).all(), held.query(Row).all()

async def gap_a_starred_value_before_a_starred_target(xs: list, db: Session = Depends(get_db)):
    first, held, *rest = *xs, db, last
    return held.query(Row).all()

async def gap_a_starred_target_before_a_starred_value(zs: list, db: Session = Depends(get_db)):
    first, *rest, held, last = one, two, db, *zs
    return held.query(Row).all()

async def gap_a_session_a_unit_returns(db: Session = Depends(get_db)):
    def handle():
        return db
    return handle().query(Row).all()

async def gap_a_unit_a_factory_returns(db: Session = Depends(get_db)):
    def make_unit(row_id):
        def unit():
            return db.get(Row, row_id)
        return unit
    run = make_unit(1)
    return run()

async def gap_a_partial_of_a_unit(db: Session = Depends(get_db)):
    def unit(row_id):
        return db.get(Row, row_id)
    run = functools.partial(unit, 1)
    return run()

async def gap_a_unit_handed_to_the_stripe_threads(db: Session = Depends(get_db)):
    def delete_all():
        db.query(Row).delete()
        return stripe_service.cancel(1)
    return await run_on_stripe_threads(delete_all)

async def gap_a_method_of_a_nested_class(db: Session = Depends(get_db)):
    class Unit:
        def run(self):
            return db.query(Row).all()
    return Unit().run()

async def gap_lambda_called_at_once(db: Session = Depends(get_db)):
    return (lambda: db.query(Row).all())()

async def gap_lambda_handed_to_a_callee(db: Session = Depends(get_db)):
    return service.call(lambda: db.query(Row).all())

async def gap_lazy_load_on_the_loop(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user.watchlist

async def gap_session_the_route_opens():
    db = SessionLocal()
    return service.read(db, 1)

class Holder:
    db: Session

async def gap_session_in_an_attribute(holder: Holder, db: Session = Depends(get_db)):
    holder.db = db
    return holder.db.query(Row).all()
'''

# Function -> how many on-loop session uses the walk must find. ``gap_`` forms break the rule but
# are out of the walk's reach, and ``strict_`` forms keep it but are counted (the header names
# both); they are planted so a widened or narrowed walk updates this table on purpose. The walk
# reads no other planted function: ``clean_no_session`` and ``gap_session_the_route_opens`` receive
# no session, and ``clean_sync_route`` is a sync route (FastAPI runs it in the thread pool).
_PLANTED_COUNTS = {
    "flags_a_query_chain": 1,
    "flags_each_call_in_branches": 4,
    "flags_a_scoped_dependency": 1,
    "flags_an_annotated_dependency": 1,
    "flags_a_module_alias": 1,
    "flags_a_qualified_annotation": 1,
    "flags_an_alias_in_the_body": 1,
    "flags_an_annotated_alias": 1,
    "flags_a_walrus_alias": 1,
    "flags_a_bound_method": 1,
    "flags_a_nested_async_def": 1,
    "flags_a_comprehension": 1,
    "flags_a_route_a_factory_builds": 1,
    "clean_threadpool_closure": 0,
    "clean_uncalled_method_to_the_pool": 0,
    "clean_lambda_to_the_pool": 0,
    "flags_a_service_on_the_loop": 1,
    "flags_a_keyword_handoff": 1,
    "flags_one_call_handed_the_session_twice": 1,
    "flags_an_awaited_service": 1,
    "flags_a_handoff_through_an_alias": 1,
    "flags_a_sync_def_called_with_the_session": 1,
    "flags_a_handoff_in_a_nested_async_def": 1,
    "flags_a_handoff_and_a_read": 2,
    "clean_service_to_the_pool": 0,
    "flags_a_conditional_argument": 1,
    "flags_a_boolean_argument": 1,
    "flags_the_other_branch_of_a_conditional": 1,
    "flags_the_last_operand_of_an_and": 1,
    "clean_an_earlier_operand_of_an_and": 0,
    "clean_a_conditional_on_the_session": 0,
    "flags_a_read_off_a_conditional": 1,
    "flags_a_read_off_a_boolean": 1,
    "flags_a_read_off_a_walrus": 1,
    "flags_a_walrus_argument": 2,
    "flags_an_alias_by_a_conditional": 1,
    "flags_an_alias_by_unpacking": 1,
    "flags_an_alias_by_list_unpacking": 1,
    "flags_an_alias_by_nested_unpacking": 1,
    "flags_an_alias_by_with": 2,
    "flags_a_with_block": 1,
    "flags_an_alias_by_a_nested_async_default": 1,
    "flags_an_alias_by_a_keyword_only_default": 1,
    "flags_a_decorator_on_a_nested_def": 1,
    "flags_a_default_on_a_nested_def": 1,
    "flags_a_keyword_only_default_on_a_nested_def": 1,
    "flags_a_lambda_default": 1,
    "flags_only_a_lambdas_default_on_the_loop": 1,
    "flags_a_class_body": 1,
    "flags_a_closure_called_on_the_loop": 1,
    "flags_a_lambda_called_on_the_loop": 1,
    "flags_a_closure_over_a_default_called_on_the_loop": 1,
    "flags_a_default_after_a_plain_parameter": 1,
    "flags_a_positional_only_default": 1,
    "flags_a_lambda_over_its_own_default": 1,
    "flags_a_lambda_bound_by_a_walrus": 1,
    "flags_a_lambda_bound_by_unpacking": 1,
    "flags_a_lambda_bound_by_a_conditional": 1,
    "flags_a_lambda_bound_by_an_annotation": 1,
    "flags_a_unit_called_through_an_alias": 1,
    "flags_a_unit_handed_the_session_once": 1,
    "flags_a_unit_defined_after_its_caller": 1,
    "flags_a_call_before_the_def_in_a_loop": 1,
    "flags_a_unit_calling_a_unit": 1,
    "flags_a_unit_over_an_alias_bound_after_it": 1,
    "flags_an_alias_bound_after_a_nested_async_def": 1,
    "flags_a_unit_calling_a_later_unit_inside_a_unit": 1,
    "flags_an_alias_after_its_use_inside_a_unit": 1,
    "flags_a_call_before_the_def_in_a_loop_inside_a_unit": 1,
    "flags_a_chain_of_three_units": 1,
    "flags_a_lambda_bound_as_a_units_default": 1,
    "flags_a_unit_bound_as_a_units_default": 1,
    "flags_a_unit_bound_as_a_nested_async_default": 1,
    "flags_a_lambda_bound_as_a_lambdas_default": 1,
    "flags_a_keyword_only_session_default_on_a_unit": 1,
    "flags_a_conditional_default_on_a_unit": 1,
    "flags_a_conditional_default_on_a_nested_async_def": 1,
    "flags_a_with_on_a_conditional": 1,
    "flags_a_class_header": 3,
    "clean_a_unit_that_hands_the_session_to_the_pool": 0,
    "clean_a_unit_factory": 0,
    "clean_a_unit_shadowing_the_session": 0,
    "clean_a_method_named_like_a_free_function": 0,
    "clean_a_unit_parameter_defaulting_to_the_session": 0,
    "clean_a_positional_only_parameter_shadowing": 0,
    "clean_a_keyword_only_parameter_shadowing": 0,
    "clean_a_varargs_parameter_shadowing": 0,
    "clean_a_kwargs_parameter_shadowing": 0,
    "clean_a_parameter_shadowing_a_unit": 0,
    "clean_a_lambda_parameter_shadowing": 0,
    "clean_a_lambda_that_only_dispatches": 0,
    "clean_a_nested_async_parameter_shadowing": 0,
    "flags_a_method_called_in_its_class_body": 1,
    "clean_a_class_body_binding": 0,
    "clean_a_method_call_named_like_a_unit": 0,
    "flags_a_bare_db_parameter": 1,
    "flags_a_depends_default_alone": 1,
    "clean_closure_called_in_the_pool": 0,
    "clean_helper_called_on_the_loop": 0,
    "strict_partial_to_the_pool": 1,
    "strict_a_logged_or_type_checked_session": 2,
    "strict_a_dispatcher_through_an_import_alias": 1,
    "strict_a_generator_handed_to_the_pool": 1,
    "strict_a_method_handed_to_the_pool_by_keyword": 1,
    "strict_a_rebound_alias": 1,
    "strict_a_rebound_unit_name": 1,
    "strict_a_comprehension_variable_named_like_the_session": 1,
    "strict_a_session_handed_to_the_stripe_threads": 1,
    "gap_session_in_a_container": 0,
    "gap_session_starred": 0,
    "gap_session_in_a_name_holding_a_container": 0,
    "gap_loop_over_a_container": 0,
    "gap_session_by_an_index": 0,
    "flags_an_alias_before_a_starred_target": 1,
    "flags_an_alias_after_a_starred_target": 1,
    "flags_an_alias_after_a_starred_value": 1,
    "gap_session_under_a_starred_target": 0,
    "gap_session_between_starred_values": 0,
    "gap_a_starred_value_before_a_starred_target": 0,
    "gap_a_starred_target_before_a_starred_value": 0,
    "gap_a_session_a_unit_returns": 0,
    "gap_a_unit_a_factory_returns": 0,
    "gap_a_partial_of_a_unit": 0,
    "gap_a_unit_handed_to_the_stripe_threads": 0,
    "gap_a_method_of_a_nested_class": 0,
    "gap_lambda_called_at_once": 0,
    "gap_lambda_handed_to_a_callee": 0,
    "gap_lazy_load_on_the_loop": 0,
    "gap_session_in_an_attribute": 0,
}


def test_walk_sees_each_form():
    planted = on_loop_session_uses(_PLANTED)
    assert {name: len(sites) for name, sites in planted.items()} == _PLANTED_COUNTS
    # The ceiling check on the same uses: an unlisted function's ceiling is 0, and a count at its
    # ceiling passes.
    assert set(_over_ceilings(planted, {})) == {name for name, count in _PLANTED_COUNTS.items() if count}
    assert _over_ceilings(planted, _PLANTED_COUNTS) == {}
