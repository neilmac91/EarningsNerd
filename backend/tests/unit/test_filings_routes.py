"""Route characterization for GET /api/filings/company/{ticker} and the recent / single reads.

The company-list route's error mapping had no route-level test: the miss path's 404 / 503 / 500
(including a failure inside the CIK-first persistence), the cold live fetch's timeout / SEC-error /
unexpected-error fallbacks with and without rows to fall back on, the skip warnings and the old
cgi-bin URL rewrite in the live persistence, filing-type parsing, and the durable-task handoff
payloads with their release-before-enqueue ordering and their outage warning (still logged from
the router). This suite pins them so moving the route's database work into ``app/services/`` is
provably behaviour-neutral. It also pins that ``?filing_types=`` is validated where it enters and
never reaches the durable refresh, so a caller cannot queue one task per distinct value (the gate
for ``lessons/arch-caller-input-never-names-a-durable-task.md``), and that the route bounds the work
a request causes rather than the request: the durable handoffs spend a per-process budget, sized under
the queue's drain across the API's instances, and the live SEC fetch a per-client one, while a visit
served from stored rows that hands nothing off spends neither. SEC calls are patched on the shared ``sec_edgar_service`` singleton; every test runs on a
private SQLite engine and with the route's budgets unspent.
"""
import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

import main
import app.models  # noqa: F401 — register models on Base.metadata
from app.config import settings
from app.database import Base, get_db
from app.models import Company, Filing
from app.routers import filings as filings_mod
from app.services import background_task_runner, durable_tasks as transport, filing_amendment_service, filing_list_service
from app.services import rate_limiter
from app.services.durable_tasks import TaskEnvelope, TaskUnavailable
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.config import FilingType
from app.services.edgar.exceptions import EdgarError
from app.services.latest_filing_service import company_list_forms
from app.services.rate_limiter import RateLimiter
from tests.support.filings_budgets import unspend_filings_budgets
from tests.unit.test_sec_process_budgets import ROOT, SERVICE_STEP, _run, _service_instances

ROUTER_LOGGER = "app.routers.filings"
PERSIST_LOGGER = "app.services.filing_list_service"  # the live-persistence skip warnings moved
DEFAULT_TYPES = ["10-K", "10-Q", "10-K/A", "10-Q/A"]
ACCEPTED_TYPES = ["10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A", "20-F", "20-F/A", "40-F", "40-F/A",
                  "6-K", "6-K/A", "3", "4", "5", "13F-HR", "13F-HR/A"]
OTHER_TYPES = [form for form in ACCEPTED_TYPES if form not in DEFAULT_TYPES]  # with ENABLE_FPI_FILINGS off
UNAVAILABLE = "SEC EDGAR is temporarily unavailable. Please retry shortly."
SLOW = "SEC EDGAR is slow to respond and no cached data is available. Please retry in a moment."


def _archive(cik, accession):
    return f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession.replace('-', '')}/"


def _seed_company(session, ticker="COLD", cik="0000000002", backfilled=True):
    company = Company(
        cik=cik, ticker=ticker, name=f"{ticker} Co", exchange="NYSE",
        history_backfilled_at=datetime(2026, 1, 1, tzinfo=timezone.utc) if backfilled else None,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def _seed_filing(session, company_id, cik, accession, filing_type="10-K", year=2025, sec_url=None):
    url = sec_url or _archive(cik, accession)
    filing = Filing(
        company_id=company_id, accession_number=accession, filing_type=filing_type,
        filing_date=datetime(year, 2, 19), period_end_date=datetime(year - 1, 12, 31),
        document_url=url + "primary.htm", sec_url=url,
    )
    session.add(filing)
    session.commit()
    session.refresh(filing)
    return filing


@pytest.fixture(autouse=True)
def _unspent_budgets(monkeypatch):
    unspend_filings_budgets(monkeypatch)


@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    # No on-visit EFTS walk and no durable queue unless a test opts in.
    monkeypatch.setattr(settings, "ENABLE_HISTORY_BACKFILL_ON_VISIT", False)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", False)
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    monkeypatch.setitem(main.app.dependency_overrides, get_db, override_get_db)
    yield testing_session
    engine.dispose()


@pytest.fixture
def client(sessions):
    return TestClient(main.app)


def _router_records(caplog, name=ROUTER_LOGGER):
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == name]


_HIT = {"cik": "0000000042", "ticker": "MISS", "name": "Miss Co", "exchange": "NYSE"}


@pytest.mark.parametrize("scenario, status, detail", [
    ("no_results", 404, "Company not found"),
    ("search_edgar_error", 503, UNAVAILABLE),
    ("primary_edgar_error", 503, UNAVAILABLE),
    ("primary_runtime_error", 500, "Error fetching company: boom"),
    ("persist_key_error", 500, "Error fetching company: 'name'"),
])
def test_company_miss_maps_each_failure(client, sessions, monkeypatch, scenario, status, detail):
    """Each failure in the CIK-first miss path, including one raised while building the
    persistence call, reaches the same handler and writes no Company row."""
    fetched = []

    async def search(_ticker):
        if scenario == "no_results":
            return []
        if scenario == "search_edgar_error":
            raise EdgarError("search down")
        if scenario == "persist_key_error":
            return [{k: v for k, v in _HIT.items() if k != "name"}]
        return [dict(_HIT)]

    async def primary(_cik):
        if scenario == "primary_edgar_error":
            raise EdgarError("primary down")
        if scenario == "primary_runtime_error":
            raise RuntimeError("boom")
        return "MISS"

    async def get_filings(cik, types):
        fetched.append(cik)
        return []

    monkeypatch.setattr(sec_edgar_service, "search_company", search)
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", primary)
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    resp = client.get("/api/filings/company/miss")

    assert resp.status_code == status
    assert resp.json() == {"detail": detail}
    assert fetched == []
    with sessions() as s:
        assert s.query(Company).count() == 0


def test_company_miss_persists_the_sec_company_and_serves_its_live_list(client, sessions, monkeypatch):
    """The success branch: CIK-first create under the primary ticker, then the cold live fetch.

    The persistence unit commits the new Company itself, before the live fetch. The row count cannot
    see that commit (the resolver's SAVEPOINT RELEASE already commits under SQLite; Postgres would
    lose the row), so the request session's own ``commit()`` calls before the fetch are counted."""
    commits = []
    commits_before_fetch = []

    def override_get_db():
        db = sessions()
        real_commit = db.commit

        def commit():
            commits.append(1)
            real_commit()

        db.commit = commit
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setitem(main.app.dependency_overrides, get_db, override_get_db)

    async def search(_ticker):
        return [dict(_HIT, ticker="MISS-PA")]

    async def primary(_cik):
        return "MISS"

    accession = "0000000042-26-000001"

    async def get_filings(cik, types):
        assert (cik, types) == ("0000000042", DEFAULT_TYPES)
        commits_before_fetch.append(len(commits))
        return [{
            "accession_number": accession, "filing_type": "10-K", "filing_date": "2026-02-19",
            "report_date": "2025-12-31", "sec_url": _archive(cik, accession),
            "document_url": _archive(cik, accession) + "primary.htm",
        }]

    monkeypatch.setattr(sec_edgar_service, "search_company", search)
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", primary)
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    resp = client.get("/api/filings/company/miss-pa")

    assert resp.status_code == 200
    assert commits_before_fetch == [1]
    with sessions() as s:
        company = s.query(Company).one()
        assert (company.cik, company.ticker, company.name, company.exchange) == (
            "0000000042", "MISS", "Miss Co", "NYSE",
        )
        filing_id = s.query(Filing).one().id
    assert resp.json() == [{
        "id": filing_id, "filing_type": "10-K", "filing_date": "2026-02-19T00:00:00",
        "report_date": "2025-12-31T00:00:00", "accession_number": accession,
        "document_url": _archive("0000000042", accession) + "primary.htm",
        "sec_url": _archive("0000000042", accession),
        "company": {"id": company.id, "ticker": "MISS", "name": "Miss Co", "exchange": "NYSE"},
        "superseded_by_accession": None,
    }]


def _timeout_fetch(monkeypatch, before=None):
    """A real ``asyncio.wait_for`` timeout: the fake outlives a tiny route timeout."""
    monkeypatch.setattr(filing_list_service, "SEC_REQUEST_TIMEOUT_SECONDS", 0.01)

    async def get_filings(cik, types):
        if before:
            before()
        await asyncio.sleep(5)

    return get_filings


def _raising_fetch(error, before=None):
    async def get_filings(cik, types):
        if before:
            before()
        raise error

    return get_filings


_COLD_FAILURES = {
    "timeout": (None, 503, SLOW,
                [(logging.WARNING, "SEC EDGAR timeout for COLD, returning cached filings")]),
    "edgar": (EdgarError("edgar down"), 503, UNAVAILABLE,
              [(logging.WARNING, "SEC EDGAR error for COLD: edgar down, attempting to return cached filings")]),
    "unexpected": (RuntimeError("boom"), 500, "Error fetching filings: boom",
                   [(logging.ERROR, "Unexpected error fetching filings for COLD")]),
}


@pytest.mark.parametrize("kind", sorted(_COLD_FAILURES))
def test_cold_fetch_failure_without_cached_rows(client, sessions, monkeypatch, caplog, kind):
    error, status, detail, logs = _COLD_FAILURES[kind]
    with sessions() as s:
        _seed_company(s)
    fetch = _timeout_fetch(monkeypatch) if error is None else _raising_fetch(error)
    monkeypatch.setattr(sec_edgar_service, "get_filings", fetch)

    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER):
        resp = client.get("/api/filings/company/cold")

    assert resp.status_code == status
    assert resp.json() == {"detail": detail}
    assert _router_records(caplog) == logs
    assert filing_list_service._filings_synced_at == {}


@pytest.mark.parametrize("kind", sorted(_COLD_FAILURES))
def test_cold_fetch_failure_serves_rows_persisted_meanwhile(client, sessions, monkeypatch, caplog, kind):
    """Rows another writer persisted during the SEC wait are the fallback (rollback, then read)."""
    error, _status, _detail, logs = _COLD_FAILURES[kind]
    with sessions() as s:
        company_id = _seed_company(s).id
    accession = "0000000002-26-000009"

    def persist_meanwhile():
        with sessions() as other:
            _seed_filing(other, company_id, "0000000002", accession)

    fetch = (
        _timeout_fetch(monkeypatch, persist_meanwhile) if error is None
        else _raising_fetch(error, persist_meanwhile)
    )
    monkeypatch.setattr(sec_edgar_service, "get_filings", fetch)

    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER):
        resp = client.get("/api/filings/company/cold")

    assert resp.status_code == 200
    assert [row["accession_number"] for row in resp.json()] == [accession]
    assert resp.json()[0]["company"]["ticker"] == "COLD"
    expected_logs = list(logs)
    if kind == "unexpected":
        expected_logs.append((logging.INFO, "Returning 1 cached filings for COLD after error"))
    assert _router_records(caplog) == expected_logs


def test_live_persistence_failure_rolls_back_and_maps_to_500(client, sessions, monkeypatch):
    """An error raised inside the live persistence (a bad SEC date) reaches the route's generic
    handler: nothing is written, no stamp is recorded and the detail carries the error text."""
    with sessions() as s:
        _seed_company(s)
    good = "0000000002-26-000001"

    async def get_filings(cik, types):
        return [
            {"accession_number": good, "filing_type": "10-K", "filing_date": "2026-02-19",
             "sec_url": _archive(cik, good), "document_url": _archive(cik, good) + "a.htm"},
            {"accession_number": "0000000002-26-000002", "filing_type": "10-Q",
             "filing_date": "not-a-date", "sec_url": _archive(cik, "x"), "document_url": "d"},
        ]

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    resp = client.get("/api/filings/company/cold")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Error fetching filings: Invalid isoformat string: 'not-a-date'"}
    with sessions() as s:
        assert s.query(Filing).count() == 0
    assert filing_list_service._filings_synced_at == {}


def test_live_persistence_failure_after_flush_is_rolled_back_before_the_fallback(
    client, sessions, monkeypatch, caplog
):
    """A failure after the batch flush (marking superseded filings) is rolled back before the
    fallback read: the flushed, uncommitted row is neither served nor kept, and the route maps the
    error to its 500."""
    with sessions() as s:
        _seed_company(s)
    accession = "0000000002-26-000001"

    async def get_filings(cik, types):
        return [{"accession_number": accession, "filing_type": "10-K", "filing_date": "2026-02-19",
                 "sec_url": _archive(cik, accession), "document_url": _archive(cik, accession) + "a.htm"}]

    def failing_supersede(db, company_id):
        raise RuntimeError("supersede failed")

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)
    monkeypatch.setattr(filing_amendment_service, "mark_superseded_filings", failing_supersede)

    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER):
        resp = client.get("/api/filings/company/cold")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Error fetching filings: supersede failed"}
    assert _router_records(caplog) == [(logging.ERROR, "Unexpected error fetching filings for COLD")]
    with sessions() as s:
        assert s.query(Filing).count() == 0
    assert filing_list_service._filings_synced_at == {}


def test_live_persistence_skips_incomplete_rows_and_rewrites_viewer_urls(client, sessions, monkeypatch, caplog):
    """Rows without a URL or accession are skipped with a warning; an existing row on the old
    cgi-bin viewer URL is rewritten (a dirty-only commit), or kept when the new URLs are partial."""
    # Non-SEC host: the model listener rejects a legacy sec.gov viewer URL on INSERT.
    viewer = "https://legacy.example/cgi-bin/viewer?action=view&cik=2&accession_number="
    with sessions() as s:
        company_id = _seed_company(s).id
        rewritten = _seed_filing(s, company_id, "0000000002", "0000000002-25-000001", "8-K",
                                 sec_url=viewer + "1")
        kept = _seed_filing(s, company_id, "0000000002", "0000000002-25-000002", "8-K",
                            sec_url=viewer + "2")
        rewritten_id, kept_id = rewritten.id, kept.id
    new_url = _archive("0000000002", "0000000002-25-000001")

    async def get_filings(cik, types):
        return [
            {"accession_number": "0000000002-26-000001", "filing_type": "10-K",
             "filing_date": "2026-02-19", "sec_url": None, "document_url": "d"},
            {"accession_number": None, "filing_type": "10-K", "filing_date": "2026-02-19",
             "sec_url": "s", "document_url": "d"},
            {"accession_number": "0000000002-26-000003", "filing_type": "10-K",
             "filing_date": "2026-02-19", "sec_url": "s", "document_url": None},
            {"accession_number": "0000000002-25-000001", "filing_type": "8-K",
             "filing_date": "2025-02-19", "sec_url": new_url, "document_url": new_url + "new.htm"},
            {"accession_number": "0000000002-25-000002", "filing_type": "8-K",
             "filing_date": "2025-02-19", "sec_url": "s2", "document_url": None},
        ]

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    with caplog.at_level(logging.WARNING, logger=PERSIST_LOGGER):
        resp = client.get("/api/filings/company/cold")

    assert resp.status_code == 200
    assert [(r["id"], r["sec_url"], r["document_url"]) for r in resp.json()] == [
        (rewritten_id, new_url, new_url + "new.htm"),
        (kept_id, viewer + "2", viewer + "2primary.htm"),
    ]
    assert _router_records(caplog, PERSIST_LOGGER) == [
        (logging.WARNING, "Skipping filing 0000000002-26-000001 - missing sec_url"),
        (logging.WARNING, "Skipping filing - missing accession_number"),
        (logging.WARNING, "Skipping new filing 0000000002-26-000003 - missing document_url"),
        (logging.WARNING, "Skipping URL update for filing 0000000002-25-000002 - new sec_url or document_url is None"),
    ]
    with sessions() as s:
        assert s.query(Filing).count() == 2
        assert s.get(Filing, rewritten_id).sec_url == new_url  # committed, not just flushed
        assert s.get(Filing, kept_id).sec_url == viewer + "2"
    assert ("COLD", tuple(DEFAULT_TYPES)) in filing_list_service._filings_synced_at


@pytest.mark.parametrize("params, fpi, expected", [
    ({"filing_types": " 10-K, 8-K"}, False, ["10-K", "8-K", "10-K/A"]),
    # Validated where it enters: spellings read as the SEC form, unknown forms and blanks dropped.
    ({"filing_types": "10k, 10-q/a,JUNK,"}, False, ["10-K", "10-Q/A", "10-K/A"]),
    ({"filing_types": "JUNK,"}, False, []),  # names no known form: lists nothing
    ({}, True, ["10-K", "10-Q", "20-F", "6-K", "40-F", "10-K/A", "10-Q/A"]),
    ({}, False, DEFAULT_TYPES),
])
def test_filing_types_parse_and_expand_amendments(client, sessions, monkeypatch, params, fpi, expected):
    with sessions() as s:
        _seed_company(s)
    asked = []

    async def get_filings(cik, types):
        asked.append((cik, types))
        return []

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", fpi)
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    resp = client.get("/api/filings/company/cold", params=params)

    assert resp.status_code == 200
    assert resp.json() == []
    assert asked == [("0000000002", expected)]


def test_durable_handoff_payloads_and_pool_release(tmp_path, monkeypatch):
    """With durable tasks on, a cached company hands both the history backfill and the refresh to
    the queue (history first), with frozen payloads, keys and seconds, and holds no pooled
    connection during either control-plane wait."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'handoff.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool, pool_size=1, max_overflow=0, pool_timeout=0.05,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        with testing_session() as db:
            yield db

    with testing_session() as s:
        company_id = _seed_company(s, ticker="DUR", backfilled=False).id
        _seed_filing(s, company_id, "0000000002", "0000000002-25-000001")

    calls = []

    async def enqueue(kind, payload, *, dedupe_key=None, dedupe_seconds=None):
        calls.append((kind, payload, dedupe_key, dedupe_seconds, engine.pool.checkedout()))
        return f"task-{kind}"

    fetched = []

    async def get_filings(cik, types):
        fetched.append(cik)
        return []

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_HISTORY_BACKFILL_ON_VISIT", True)
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)
    monkeypatch.setitem(main.app.dependency_overrides, get_db, override_get_db)
    try:
        resp = TestClient(main.app).get("/api/filings/company/dur")
    finally:
        engine.dispose()

    assert resp.status_code == 200
    assert [row["accession_number"] for row in resp.json()] == ["0000000002-25-000001"]
    assert calls == [
        ("history", {"company_id": company_id}, f"history:{company_id}", 300, 0),
        ("filings", {"company_id": company_id, "filing_types": DEFAULT_TYPES},
         f"filings:{company_id}", 10800, 0),
    ]
    assert fetched == []


def test_durable_miss_path_releases_the_company_persist_before_the_history_handoff(tmp_path, monkeypatch):
    """A first view of a ticker the database does not hold persists the SEC company in its own unit
    and, with durable tasks on (production's setting), hands the new company's history backfill to
    the queue. The persist's own release is all that frees the connection before that control-plane
    wait: the route releases nothing itself (lessons/ops-release-cached-filing-reads-before-yield.md)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'miss-handoff.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool, pool_size=1, max_overflow=0, pool_timeout=0.05,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        with testing_session() as db:
            yield db

    calls = []

    async def enqueue(kind, payload, *, dedupe_key=None, dedupe_seconds=None):
        calls.append((kind, payload, engine.pool.checkedout()))
        return f"task-{kind}"

    async def search(_ticker):
        return [dict(_HIT)]

    async def primary(_cik):
        return "MISS"

    async def get_filings(cik, types):
        return []

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_HISTORY_BACKFILL_ON_VISIT", True)
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    monkeypatch.setattr(sec_edgar_service, "search_company", search)
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", primary)
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)
    monkeypatch.setitem(main.app.dependency_overrides, get_db, override_get_db)
    try:
        resp = TestClient(main.app).get("/api/filings/company/miss")
        with testing_session() as s:
            company_id = s.query(Company).filter(Company.ticker == "MISS").one().id
    finally:
        engine.dispose()

    assert resp.status_code == 200 and resp.json() == []
    assert calls == [("history", {"company_id": company_id}, 0)]


def test_durable_handoff_outage_serves_cached_rows_and_warns_from_the_router(
    client, sessions, monkeypatch, caplog
):
    """A queue outage on both handoffs still serves the persisted rows, without an SEC call, and
    each warning comes from the router's logger, as on the base router."""
    with sessions() as s:
        company_id = _seed_company(s, ticker="DUR", backfilled=False).id
        _seed_filing(s, company_id, "0000000002", "0000000002-25-000001")

    async def enqueue(kind, payload, *, dedupe_key=None, dedupe_seconds=None):
        raise TaskUnavailable("offline")

    fetched = []

    async def get_filings(cik, types):
        fetched.append(cik)
        return []

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_HISTORY_BACKFILL_ON_VISIT", True)
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        resp = client.get("/api/filings/company/dur")

    assert resp.status_code == 200
    assert [row["accession_number"] for row in resp.json()] == ["0000000002-25-000001"]
    assert _router_records(caplog) == [
        (logging.WARNING, "On-visit task handoff unavailable kind=history"),
        (logging.WARNING, "On-visit task handoff unavailable kind=filings"),
    ]
    assert fetched == []


def _fake_cloud_tasks(monkeypatch):
    """Configure durable tasks and run the real ``enqueue_task`` with only the Cloud Tasks HTTP call
    faked. The fake queue keeps one task per name and answers 409 for a name it already holds, as
    Cloud Tasks does. Both bucket clocks, the task name's and the router guard's, are pinned so a
    run cannot straddle a dedupe bucket."""
    for key, value in {
        "DURABLE_TASKS_ENABLED": True, "TASKS_PROJECT_ID": "test-project",
        "TASKS_LOCATION": "us-west1", "TASKS_QUEUE": "background",
        "TASKS_WORKER_URL": "https://worker-xyz-uw.a.run.app",
        "TASKS_INVOKER_EMAIL": "task-worker@test-project.iam.gserviceaccount.com",
    }.items():
        monkeypatch.setattr(settings, key, value)
    queue: dict[str, dict] = {}
    creates: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        task = json.loads(request.content)["task"]
        creates.append(task["name"])
        if task["name"] in queue:
            return httpx.Response(409, request=request, json={})
        queue[task["name"]] = json.loads(base64.b64decode(task["httpRequest"]["body"]))
        return httpx.Response(200, request=request, json={})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(transport, "_access_token", AsyncMock(return_value="metadata-only-token"))
    monkeypatch.setattr(
        transport.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(
        transport, "time", SimpleNamespace(time=lambda: 1_800_000_000.0, monotonic=time.monotonic),
    )
    monkeypatch.setattr(filings_mod, "utcnow", lambda: datetime.fromtimestamp(1_800_000_000, timezone.utc))
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    return queue, creates


@pytest.mark.parametrize("values, refreshes", [
    pytest.param([f"10-K,JUNK{i}" for i in range(40)], [DEFAULT_TYPES], id="40-junk-values"),
    # Known forms in other orders, subsets and spellings: validation alone cannot collapse these.
    pytest.param(["10-Q", "10-Q,10-K", "8-K,10-K", "10k,10-q", "10-K/A,10-Q,8-K"],
                 [DEFAULT_TYPES, OTHER_TYPES], id="known-forms"),
])
def test_filing_types_values_cannot_mint_durable_refresh_tasks(client, sessions, monkeypatch, values, refreshes):
    """Whatever ``?filing_types=`` says, the public route queues at most two background refreshes per
    company per time bucket: one of the company's list forms, and, once a visit serves stored rows
    of another form, one of the other accepted forms. The refresh payload used to carry the caller's list, and
    that payload names the Cloud Task (sha256 of key and body) and keys the router's per-process
    guard, so every distinct value queued a new task: a worker child process and an SEC fetch each,
    on the queue every durable job shares. Before the fix the 40 junk values queued 40 tasks."""
    with sessions() as s:
        company_id = _seed_company(s, ticker="DUR").id
        for n, form in enumerate(("10-K", "10-Q", "8-K"), start=1):
            _seed_filing(s, company_id, "0000000002", f"0000000002-25-00000{n}", form)
    queue, creates = _fake_cloud_tasks(monkeypatch)
    fetched = []

    async def get_filings(cik, types):
        fetched.append(types)
        return []

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    # One process: the router's per-process guard admits a single handoff.
    statuses = {client.get("/api/filings/company/dur", params={"filing_types": v}).status_code
                for v in values}
    one_process_creates = len(creates)
    # Every request on a fresh instance: each create names the one task, which the queue holds.
    for value in values:
        monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
        client.get("/api/filings/company/dur", params={"filing_types": value})

    assert len(queue) == len(refreshes), f"{len(queue)} durable tasks queued for one company in one bucket"
    assert sorted(queue.values(), key=lambda task: len(task["payload"]["filing_types"])) == [
        {"kind": "filings", "payload": {"company_id": company_id, "filing_types": forms}} for forms in refreshes
    ]
    assert one_process_creates == len(refreshes)
    assert statuses == {200}
    assert fetched == []  # every value was served from the stored rows


@pytest.mark.parametrize("value, served, refreshes", [
    ("10-K", ["10-K/A", "10-K"], [DEFAULT_TYPES]),  # the amendment rides along
    ("8-K", ["8-K"], [DEFAULT_TYPES, OTHER_TYPES]),  # a form outside the list forms adds the other forms
    ("10q,JUNK", ["10-Q"], [DEFAULT_TYPES]),  # read as 10-Q; the unknown form is dropped
])
def test_a_filing_types_filter_still_filters_the_served_rows(client, sessions, monkeypatch, value, served, refreshes):
    """The refresh never follows the caller's own forms, but the response still does."""
    with sessions() as s:
        company_id = _seed_company(s, ticker="DUR").id
        for n, (form, year) in enumerate((("10-K/A", 2025), ("10-K", 2024), ("10-Q", 2023), ("8-K", 2022)), 1):
            _seed_filing(s, company_id, "0000000002", f"0000000002-25-00000{n}", form, year=year)
    calls = []

    async def enqueue(kind, payload, *, dedupe_key=None, dedupe_seconds=None):
        calls.append((kind, payload))
        return f"task-{kind}"

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    monkeypatch.setattr(sec_edgar_service, "get_filings", AsyncMock(return_value=[]))

    resp = client.get("/api/filings/company/dur", params={"filing_types": value})

    assert resp.status_code == 200
    assert [row["filing_type"] for row in resp.json()] == served
    assert calls == [("filings", {"company_id": company_id, "filing_types": forms}) for forms in refreshes]


@pytest.mark.parametrize("stored, value, refreshes", [
    pytest.param(["10-K"], "10-K,8-K", [DEFAULT_TYPES], id="asks-for-an-8-K-it-does-not-hold"),
    pytest.param(["10-K", "8-K"], "10-K,8-K", [DEFAULT_TYPES, OTHER_TYPES], id="serves-a-stored-8-K"),
    pytest.param(["10-K", "4"], "10-K,8-K", [DEFAULT_TYPES], id="holds-a-Form-4-it-was-not-asked-for"),
])
def test_the_other_forms_refresh_follows_the_rows_a_visit_serves(client, sessions, monkeypatch, stored, value,
                                                                  refreshes):
    """A visit queues the other-forms refresh only when it serves stored rows of a form outside the
    list forms, the rows that would otherwise go stale. A request that merely names such a form, with
    none of it stored, refreshes the list forms alone, so it costs no second task."""
    with sessions() as s:
        company_id = _seed_company(s, ticker="DUR").id
        for n, form in enumerate(stored, start=1):
            _seed_filing(s, company_id, "0000000002", f"0000000002-25-00000{n}", form, year=2025 - n)
    calls = []

    async def enqueue(kind, payload, *, dedupe_key=None, dedupe_seconds=None):
        calls.append((kind, payload))
        return f"task-{kind}"

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    monkeypatch.setattr(sec_edgar_service, "get_filings", AsyncMock(return_value=[]))

    assert client.get("/api/filings/company/dur", params={"filing_types": value}).status_code == 200
    assert calls == [("filings", {"company_id": company_id, "filing_types": forms}) for forms in refreshes]


@pytest.mark.parametrize("fpi", [False, True])
def test_the_two_refresh_vocabularies_split_every_form_the_parameter_accepts(monkeypatch, fpi):
    """Between them the two refresh payloads hold each form ``?filing_types=`` can list exactly once,
    so a stored row of any form a visit asks for is refreshed by one of them."""
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", fpi)
    listed, other = company_list_forms(), filing_list_service.other_filing_forms()
    assert sorted(listed + other) == sorted(ACCEPTED_TYPES)
    for form in FilingType:
        assert set(filing_list_service.requested_filing_types(form.value)) <= set(listed + other), form


def _sec_row(n, form):
    accession = f"0000000002-26-{n:06d}"
    return {"filing_type": form, "filing_date": "2026-10-01", "report_date": None, "cik": "0000000002",
            "accession_number": accession, "sec_url": _archive("0000000002", accession),
            "document_url": _archive("0000000002", accession) + "primary.htm"}


FPI_LIST_TYPES = ["10-K", "10-Q", "20-F", "6-K", "40-F", "10-K/A", "10-Q/A"]  # with ENABLE_FPI_FILINGS on
FPI_OTHER_TYPES = [form for form in ACCEPTED_TYPES if form not in FPI_LIST_TYPES]


@pytest.mark.parametrize("stored, payload, fpi, fetched", [
    # The list refresh fetches every list form, stored or not, so a company's first 10-Q arrives.
    pytest.param(["10-K"], DEFAULT_TYPES, False, DEFAULT_TYPES, id="list-forms"),
    # The other refresh fetches only the other forms the company already has rows of.
    pytest.param(["10-K", "8-K"], OTHER_TYPES, False, ["8-K"], id="stored-8-K"),
    pytest.param(["10-K", "4", "8-K"], OTHER_TYPES, False, ["8-K", "4"], id="stored-8-K-and-Form-4"),
    # None stored: no SEC call and nothing written.
    pytest.param(["10-K"], OTHER_TYPES, False, [], id="none-stored"),
    # A task can outlive a change of ENABLE_FPI_FILINGS. Each payload keeps the meaning it was
    # queued with: the other forms queued with the flag off include 20-F, 6-K and 40-F, which are
    # list forms once it is on, and still fetch only the forms the company has.
    pytest.param(["10-K", "8-K"], OTHER_TYPES, True, ["8-K"], id="other-forms-queued-before-the-flag-went-on"),
    pytest.param(["10-K"], FPI_LIST_TYPES, False, FPI_LIST_TYPES, id="list-forms-queued-before-the-flag-went-off"),
    pytest.param(["10-K"], DEFAULT_TYPES, True, DEFAULT_TYPES, id="list-forms-queued-before-the-flag-went-on"),
    pytest.param(["20-F", "6-K/A"], FPI_OTHER_TYPES, False, ["6-K/A"], id="other-forms-queued-before-the-flag-went-off"),
])
@pytest.mark.asyncio
async def test_a_refresh_fetches_list_forms_and_only_other_forms_already_stored(sessions, monkeypatch, stored,
                                                                                payload, fpi, fetched):
    """The worker fetches a list-forms payload whole and keeps any other payload to the forms the
    company already has rows of, so the wider refresh keeps stored rows fresh without adding a form
    nobody stored. Fetching every other form instead, one visit asking for an 8-K wrote up to 50 of
    the newest rows across all of them: Forms 3/4/5 could crowd the 8-K out of that budget and showed
    as the company's latest filing on its watchers' pages."""
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", fpi)
    with sessions() as s:
        company_id = _seed_company(s, ticker="WRK").id
        for n, form in enumerate(stored, start=1):
            _seed_filing(s, company_id, "0000000002", f"0000000002-24-00000{n}", form, year=2024)
    calls = []

    async def get_filings(cik, forms):
        calls.append(forms)
        return [_sec_row(n, form) for n, form in enumerate(forms, start=1)]

    monkeypatch.setattr(background_task_runner, "SessionLocal", sessions)
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    await background_task_runner.run_background_task(
        TaskEnvelope(kind="filings", payload={"company_id": company_id, "filing_types": payload}))

    assert calls == ([fetched] if fetched else [])
    with sessions() as s:
        written = [f.filing_type for f in s.query(Filing).filter(Filing.filing_date >= datetime(2026, 1, 1))]
    assert sorted(written) == sorted(fetched)


@pytest.mark.asyncio
async def test_handoff_cache_evicts_at_the_freshness_cache_bound(monkeypatch):
    """The router's handoff cache shares filing_list_service.MAX_FILINGS_SYNC_ENTRIES and evicts
    its oldest entry first."""
    monkeypatch.setattr(filing_list_service, "MAX_FILINGS_SYNC_ENTRIES", 2)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    enqueue = AsyncMock()
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)

    for company_id in (1, 2, 3):
        await filings_mod._enqueue_visit_task(
            "history", {"company_id": company_id}, key=f"history:{company_id}", seconds=300,
        )

    assert enqueue.await_count == 3
    assert list(filings_mod._visit_task_handoffs) == [
        'history:history:2:{"company_id": 2}',
        'history:history:3:{"company_id": 3}',
    ]


def _seed_stored(sessions, count):
    """``count`` backfilled companies C0, C1, ... each holding one stored 10-K, in id order."""
    ids = []
    with sessions() as s:
        for n in range(count):
            cik = f"{100 + n:010d}"
            ids.append(_seed_company(s, ticker=f"C{n}", cik=cik).id)
            _seed_filing(s, ids[-1], cik, f"{cik}-25-000001")
    return ids


def _recording_queue(monkeypatch):
    """Durable mode with the queue faked: the company ids handed off, in order."""
    handed = []

    async def enqueue(kind, payload, *, dedupe_key=None, dedupe_seconds=None):
        handed.append(payload["company_id"])
        return f"task-{kind}"

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(filings_mod, "enqueue_task", enqueue)
    monkeypatch.setattr(filings_mod, "_visit_task_handoffs", {})
    return handed


def test_handoffs_past_the_budget_serve_stored_rows_and_queue_nothing_until_the_window_passes(
    client, sessions, monkeypatch
):
    """A durable handoff is work a public visit queues for every durable job to wait behind, so it spends a
    per-process budget. Past it the visit still answers 200 with its stored rows and queues nothing, and
    the handoff guard is left unset, so the first visit after the window queues the task. Before the
    budget every stored company a crawl visited queued a refresh, faster than the queue's 0.2/s drain."""
    ids = _seed_stored(sessions, 4)
    handed = _recording_queue(monkeypatch)
    clock = [1_000.0]
    monkeypatch.setattr(rate_limiter, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(filings_mod, "VISIT_TASK_BUDGET", RateLimiter(limit=2, window_seconds=300))
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(sec_edgar_service, "get_filings", fetch)

    served = [client.get(f"/api/filings/company/c{n}") for n in range(4)]

    assert [r.status_code for r in served] == [200] * 4
    assert [[row["company"]["ticker"] for row in r.json()] for r in served] == [[f"C{n}"] for n in range(4)]
    assert handed == ids[:2]
    clock[0] += 301  # past the window
    late = client.get("/api/filings/company/c2")
    assert late.status_code == 200 and late.json() == served[2].json()
    assert handed == ids[:3]
    fetch.assert_not_called()


def test_visits_that_hand_nothing_off_spend_no_budget(client, sessions, monkeypatch):
    """The site's own server renders call this route from Vercel's shared IPs with no credential, once
    per company page render, and a refused render would cache a filings-less company page for 30
    minutes. A visit served from stored rows whose refresh this process already handed off this bucket
    does no work, so it spends neither budget however often it comes from one address."""
    ids = _seed_stored(sessions, 2)
    with sessions() as s:
        _seed_company(s)  # COLD: nothing stored
    handed = _recording_queue(monkeypatch)
    monkeypatch.setattr(filings_mod, "VISIT_TASK_BUDGET", RateLimiter(limit=2, window_seconds=300))
    monkeypatch.setattr(filings_mod, "LIVE_FETCH_LIMITER", RateLimiter(limit=1, window_seconds=60))
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(sec_edgar_service, "get_filings", fetch)

    first = client.get("/api/filings/company/c0")
    repeats = [client.get("/api/filings/company/c0") for _ in range(30)]
    other = client.get("/api/filings/company/c1")
    cold = client.get("/api/filings/company/cold")

    assert {r.status_code for r in [first, *repeats, other, cold]} == {200}
    assert all(r.json() == first.json() for r in repeats)
    assert handed == ids  # the 30 repeats left the second company its handoff
    assert fetch.await_count == 1  # and the one address its live fetch


def test_live_fetches_past_the_per_ip_budget_answer_429_only_when_nothing_is_stored(client, sessions, monkeypatch):
    """With nothing stored to serve, the request fetches the list from SEC while it waits, on the
    process's shared SEC pacing (1 request/s in production), so the fetch spends a per-client-IP budget,
    as search's does. Past it that client gets the 429, detail and Retry-After of the other limited
    public routes; a company with stored rows is still served to it, and another client's fetch proceeds.
    A listing that finds nothing is answered from its freshness stamp until the TTL passes (below), so
    each fetch here names other forms. A caller can still name a new set of forms per request; before the
    budget each such ``?filing_types=`` took this path, and one naming a form the company never filed
    took it on every request (#1373)."""
    with sessions() as s:
        _seed_company(s)  # COLD: nothing stored
        warm_id = _seed_company(s, ticker="WARM", cik="0000000003").id
        _seed_filing(s, warm_id, "0000000003", "0000000003-25-000001")
    _recording_queue(monkeypatch)
    fetched = []

    async def get_filings(cik, types):
        fetched.append(cik)
        return []

    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    monkeypatch.setattr(filings_mod, "LIVE_FETCH_LIMITER", RateLimiter(limit=2, window_seconds=60))
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    def get(ticker, client_ip, forms=None):
        return client.get(
            f"/api/filings/company/{ticker}", params={"filing_types": forms} if forms else None,
            headers={"X-Forwarded-For": client_ip},
        )

    allowed = [get("cold", "203.0.113.7", forms) for forms in ("10-K", "10-Q")]
    refused = get("cold", "203.0.113.7", "8-K")
    warm = get("warm", "203.0.113.7")
    other = get("cold", "198.51.100.9", "8-K")

    assert [r.status_code for r in allowed] == [200, 200]
    assert refused.status_code == 429
    assert refused.json() == {"detail": "Too many filing requests. Please retry in a minute."}
    assert 1 <= int(refused.headers["Retry-After"]) <= 60
    assert warm.status_code == 200
    assert [row["accession_number"] for row in warm.json()] == ["0000000003-25-000001"]
    assert other.status_code == 200
    assert fetched == ["0000000002"] * 3  # the refused request made no SEC call


def _listing_clock(monkeypatch):
    """The freshness stamp's clock, held still until the test moves it."""
    now = [datetime(2026, 10, 23, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(filing_list_service, "utcnow", lambda: now[0])
    return now


def test_a_listing_that_found_nothing_is_answered_from_its_stamp_until_the_ttl_passes(client, sessions, monkeypatch):
    """A fund, a trust, or a company with only 8-K or Form 3/4/5 rows has nothing in the default forms, so
    its live fetch persists nothing. That successful empty listing is the answer until the freshness TTL
    passes: the site's ISR renders of the page, all from one Vercel IP, cost one SEC fetch and one
    live-fetch slot per TTL, hand nothing off, and are never refused. Before, every render fetched again,
    and the eleventh in a minute from one IP got the 429 that ISR caches as an unavailable page for 30
    minutes."""
    with sessions() as s:
        company_id = _seed_company(s).id
        _seed_filing(s, company_id, "0000000002", "0000000002-25-000001", "8-K")  # not a default form
    handed = _recording_queue(monkeypatch)
    fetched = []

    async def get_filings(cik, types):
        fetched.append((cik, types))
        return []

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    now = _listing_clock(monkeypatch)

    def render():
        return client.get("/api/filings/company/cold", headers={"X-Forwarded-For": "76.76.21.21"})

    first = render()
    # From here a visit that spent a live-fetch slot would be refused.
    monkeypatch.setattr(filings_mod, "LIVE_FETCH_LIMITER", RateLimiter(limit=0, window_seconds=60))
    renders = [render() for _ in range(30)]
    now[0] += filing_list_service.FILINGS_LIST_TTL - timedelta(seconds=1)
    last_inside = render()
    assert len(fetched) == 1

    now[0] += timedelta(seconds=1)  # the stamp is a TTL old: the next visit lists again, once
    monkeypatch.setattr(filings_mod, "LIVE_FETCH_LIMITER", RateLimiter(limit=1, window_seconds=60))
    after = [render() for _ in range(5)]

    assert [(r.status_code, r.json()) for r in [first, *renders, last_inside, *after]] == [(200, [])] * 37
    assert fetched == [("0000000002", DEFAULT_TYPES)] * 2
    assert handed == []


@pytest.mark.parametrize("kind", sorted(_COLD_FAILURES))
def test_a_failed_live_listing_stamps_nothing_so_the_next_visit_fetches_again(client, sessions, monkeypatch, kind):
    """Only a listing SEC answered is cached (``lessons/arch-cache-only-reads-that-succeeded.md``). A fetch
    that times out or fails is answered with its error when nothing is stored, and leaves the key as it
    was, on a cold key and on a stale one alike, so the next visit fetches again instead of being answered
    an empty list. On the stale key a failure that wrote its stamp would make the visit after it a hit."""
    error, status, detail, _logs = _COLD_FAILURES[kind]
    with sessions() as s:
        _seed_company(s)
    monkeypatch.setattr(filing_list_service, "SEC_REQUEST_TIMEOUT_SECONDS", 0.05)
    script = [kind, "listed nothing", kind, "listed nothing"]
    fetched = []

    async def get_filings(cik, types):
        outcome = script[len(fetched)]
        fetched.append(outcome)
        if outcome != "listed nothing":
            if error is None:
                await asyncio.sleep(5)  # outlives the route's timeout
            raise error
        return []

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)
    now = _listing_clock(monkeypatch)

    def visit():
        return client.get("/api/filings/company/cold")

    cold_failure = visit()
    cold_retry = visit()
    stamped = visit()
    now[0] += filing_list_service.FILINGS_LIST_TTL
    stale_failure = visit()
    stale_retry = visit()

    for failed in (cold_failure, stale_failure):
        assert (failed.status_code, failed.json()) == (status, {"detail": detail})
    for served in (cold_retry, stamped, stale_retry):
        assert (served.status_code, served.json()) == (200, [])
    assert fetched == script  # each failure was followed by a fetch; the stamped visit made none


def test_stored_rows_are_served_as_before_whether_the_stamp_is_fresh_or_stale(client, sessions, monkeypatch):
    """The stamp changes only how a key with nothing stored is answered. A company with rows in the
    requested forms is served them with no SEC fetch and no live-fetch slot: while its stamp is stale (a
    TTL old) its refresh is handed off once per bucket, and while it is fresh not at all."""
    with sessions() as s:
        stale_id = _seed_company(s, ticker="STALE", cik="0000000003").id
        _seed_filing(s, stale_id, "0000000003", "0000000003-25-000001")
        fresh_id = _seed_company(s, ticker="FRESH", cik="0000000004").id
        _seed_filing(s, fresh_id, "0000000004", "0000000004-25-000001")
    handed = _recording_queue(monkeypatch)
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(sec_edgar_service, "get_filings", fetch)
    monkeypatch.setattr(filings_mod, "LIVE_FETCH_LIMITER", RateLimiter(limit=0, window_seconds=60))
    now = _listing_clock(monkeypatch)
    filing_list_service._mark_filings_synced("STALE", DEFAULT_TYPES, stale_id)
    now[0] += filing_list_service.FILINGS_LIST_TTL
    filing_list_service._mark_filings_synced("FRESH", DEFAULT_TYPES, fresh_id)
    assert not filing_list_service.filings_cache_fresh("STALE", DEFAULT_TYPES, stale_id)
    assert filing_list_service.filings_cache_fresh("FRESH", DEFAULT_TYPES, fresh_id)

    stale = [client.get("/api/filings/company/stale") for _ in range(3)]
    fresh = [client.get("/api/filings/company/fresh") for _ in range(3)]

    assert [(r.status_code, [row["accession_number"] for row in r.json()]) for r in stale] == [
        (200, ["0000000003-25-000001"])
    ] * 3
    assert [(r.status_code, [row["accession_number"] for row in r.json()]) for r in fresh] == [
        (200, ["0000000004-25-000001"])
    ] * 3
    assert handed == [stale_id]
    fetch.assert_not_called()


def test_a_listing_of_rows_another_company_stores_is_fetched_again_not_answered_empty(client, sessions, monkeypatch):
    """Accession numbers are unique, so a filing two companies list (a combined annual report of
    co-registrants, or a Form 4 in its issuer's and its reporting owner's listings) is stored once, under
    the company whose listing stored it first. The live fetch answers it to the other company too, but
    that company's stored rows hold nothing, so its stamp could not answer for the listing: the key is
    left unstamped and the next visit fetches and answers it again, as before, rather than an empty list."""
    accession = "0000000003-25-000001"
    with sessions() as s:
        _seed_company(s)  # COLD: nothing stored of its own
        parent_id = _seed_company(s, ticker="PARENT", cik="0000000003").id
        _seed_filing(s, parent_id, "0000000003", accession)
    fetched = []

    async def get_filings(cik, types):
        fetched.append(cik)
        return [{"accession_number": accession, "filing_type": "10-K", "filing_date": "2025-02-19",
                 "sec_url": _archive("0000000003", accession),
                 "document_url": _archive("0000000003", accession) + "primary.htm"}]

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    visits = [client.get("/api/filings/company/cold") for _ in range(2)]

    assert [(r.status_code, [row["accession_number"] for row in r.json()]) for r in visits] == [
        (200, [accession])
    ] * 2
    assert fetched == ["0000000002"] * 2


def test_a_stamp_answers_only_the_company_whose_listing_wrote_it(client, sessions, monkeypatch):
    """The stamp is keyed by (ticker, forms), and a ticker can pass to another company within the TTL: SEC
    reassigns it to a new CIK, and the old company's row self-heals to its new primary ticker on a visit.
    A stamp the old company's empty listing wrote must not answer the new one, which has nothing stored:
    the ticker's next visit fetches the new company's listing live. Before, it was answered an empty list
    until the TTL passed."""
    with sessions() as s:
        old_id = _seed_company(s).id  # COLD, CIK 0000000002: nothing stored
    new_cik = "0000000005"
    accession = f"{new_cik}-26-000001"
    sec_file = {}  # SEC's ticker file: ticker -> CIK
    fetched = []

    async def search(ticker):
        cik = sec_file.get(ticker.upper())
        return [{"cik": cik, "ticker": ticker.upper(), "name": f"{ticker.upper()} Co", "exchange": "NYSE"}] if cik else []

    async def primary(cik):
        return next(ticker for ticker, listed in sec_file.items() if listed == cik)

    async def get_filings(cik, types):
        fetched.append(cik)
        if cik != new_cik:
            return []
        return [{"accession_number": accession, "filing_type": "10-K", "filing_date": "2026-02-19",
                 "sec_url": _archive(new_cik, accession), "document_url": _archive(new_cik, accession) + "primary.htm"}]

    monkeypatch.setattr(sec_edgar_service, "search_company", search)
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", primary)
    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)

    def visit(ticker):
        r = client.get(f"/api/filings/company/{ticker}")
        return r.status_code, [row["accession_number"] for row in r.json()]

    stamped = visit("cold")  # the old company's listing finds nothing and stamps COLD
    sec_file.update({"RENAMED": "0000000002", "COLD": new_cik})
    renamed = visit("renamed")  # the old company's row self-heals to RENAMED
    moved = visit("cold")  # COLD now resolves to the new company, which stores nothing yet
    again = visit("cold")  # its own listing stamped COLD for it, so this visit is a hit

    assert [stamped, renamed, moved, again] == [(200, []), (200, []), (200, [accession]), (200, [accession])]
    assert fetched == ["0000000002", "0000000002", new_cik]
    with sessions() as s:
        assert [(c.id == old_id, c.cik, c.ticker) for c in s.query(Company).order_by(Company.id)] == [
            (True, "0000000002", "RENAMED"), (False, new_cik, "COLD"),
        ]


# The queue every durable job shares, as docs/DEPLOYMENT.md provisions it: one concurrent dispatch, at most
# 0.2/s, so a task holds the queue for max(5 s, its delivery time). A delivery execs a fresh Python child
# (about 1.7 s of imports) and a history backfill paces its 4 EFTS windows at 1 request/s, so a delivery is
# taken to average 6 s; the worker's measured request latency would replace this estimate.
QUEUE_PROVISIONING = "one concurrent dispatch, 0.2 dispatches/second"
DISPATCH_INTERVAL_SECONDS = 5
ASSUMED_DELIVERY_SECONDS = 6


def test_the_handoff_budget_takes_at_most_two_thirds_of_the_queue_drain_across_the_api_instances():
    """Limiter state is per process, so the handoffs of every API instance add up, and the queue drains one
    task per max(5 s, delivery time), not its 0.2/s dispatch ceiling, because it dispatches one at a time.
    Two thirds of that drain at most leaves the rest to companyfacts syncs, operator jobs and tasks already
    queued. Sized against the ceiling, 20 per 5 minutes on each of two instances took 80% of a 6 s drain."""
    assert QUEUE_PROVISIONING in " ".join((ROOT / "docs/DEPLOYMENT.md").read_text(encoding="utf-8").split())
    instances = _service_instances(_run(SERVICE_STEP))
    budget = filings_mod.VISIT_TASK_BUDGET
    handoffs_per_second = Fraction(instances * budget.limit, budget.window_seconds)
    drain = Fraction(1, max(DISPATCH_INTERVAL_SECONDS, ASSUMED_DELIVERY_SECONDS))
    assert handoffs_per_second <= Fraction(2, 3) * drain


def test_recent_and_single_filing_reads(client, sessions):
    with sessions() as s:
        first = _seed_company(s, ticker="AAA", cik="0000000011")
        second = _seed_company(s, ticker="BBB", cik="0000000012")
        old = _seed_filing(s, first.id, first.cik, "0000000011-23-000001", year=2023)
        newest = _seed_filing(s, second.id, second.cik, "0000000012-25-000001", "10-Q", year=2025)
        middle = _seed_filing(s, first.id, first.cik, "0000000011-24-000001", year=2024)
        ids = (old.id, newest.id, middle.id)
        company_ids = (first.id, second.id)

    recent = client.get("/api/filings/recent/latest", params={"limit": 2})
    single = client.get(f"/api/filings/{ids[1]}")

    assert recent.status_code == 200
    assert [(r["id"], r["company"]["ticker"]) for r in recent.json()] == [(ids[1], "BBB"), (ids[2], "AAA")]
    assert single.status_code == 200
    url = _archive("0000000012", "0000000012-25-000001")
    assert single.json() == {
        "id": ids[1], "filing_type": "10-Q", "filing_date": "2025-02-19T00:00:00",
        "report_date": "2024-12-31T00:00:00", "accession_number": "0000000012-25-000001",
        "document_url": url + "primary.htm", "sec_url": url,
        "company": {"id": company_ids[1], "ticker": "BBB", "name": "BBB Co", "exchange": "NYSE"},
        "superseded_by_accession": None,
    }
