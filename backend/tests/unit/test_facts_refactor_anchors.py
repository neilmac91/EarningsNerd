"""Wave 0 anchors for the facts_service refactor (F0; tasks/refactor-plan-2026-10.md, module M2).

The plan splits ``app/services/facts_service.py`` into a ``facts/`` package behind a façade. Each
test pins today's behaviour at a seam those cuts cross, so the pure moves and the splits of
``normalize_companyfacts`` / ``upsert_facts`` / ``backfill_facts`` cannot change it silently. Line
references are ``backend/app/services/facts_service.py`` on main at 76d45732.

Every boundary is faked in-process: the SEC limiter singleton (no token waits), ``httpx``, the
edgar compat singleton's extractor, the registered app loop, and a private SQLite file per test.
No test rebinds a name on facts_service's namespace. Two facts-owned objects are touched in place
and restored: the companyfacts instant-tag registry (F0.5) and the in-flight dict (F0.4), so the
façade must keep re-exporting those same objects.
"""
import asyncio
import logging
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import date, datetime, timedelta, timezone
from unittest import mock

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import database
from app.config import settings
from app.models import Base, Company, Filing, FinancialFact, User, Watchlist
from app.services import event_loop, facts_service
from app.services.edgar import compat
from app.services.sec_rate_limiter import sec_rate_limiter
from app.utils.datetimes import utcnow
from app.utils.sec_urls import companyfacts_url


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    """A private SQLite file per test (the test_data_completeness.py fixture): no rows shared with
    any other test, so the anchors pass in any order and on any worker. ``autoflush=False`` mirrors
    ``app.database.SessionLocal``, the session every production caller of these jobs uses.
    ``synchronous=OFF`` drops the per-statement fsync of a throwaway file (create_all 1.3 s → 0.06 s);
    transactions and locking are unchanged."""
    engine = create_engine(f"sqlite:///{tmp_path / 'facts_anchors.sqlite'}")
    event.listen(engine, "connect", lambda dbapi_conn, _record: dbapi_conn.execute("PRAGMA synchronous=OFF"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def app_loop(monkeypatch):
    """A live application loop on its own thread, registered as ``main.py``'s lifespan does."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, name="f0-app-loop", daemon=True)
    thread.start()
    monkeypatch.setattr(event_loop, "_app_loop", loop)
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    loop.close()


@pytest.fixture
def inflight():
    """The per-process in-flight dict, emptied for the test and restored after, IN PLACE: the
    ingest path reads this one object, wherever the refactor puts it."""
    saved = dict(facts_service._inflight_syncs)
    facts_service._inflight_syncs.clear()
    yield facts_service._inflight_syncs
    facts_service._inflight_syncs.clear()
    facts_service._inflight_syncs.update(saved)


def _limiter(fake):
    """Swap the shared SEC limiter's entry point; ``patch.object`` deletes the instance attribute on
    exit, so the singleton is left exactly as found (the conftest's reason for using it)."""
    return mock.patch.object(sec_rate_limiter, "execute_with_backoff", fake)


def _fake_httpx(monkeypatch, responses):
    """``httpx.AsyncClient`` without a socket: GET <url> answers ``responses[url]`` (an Exception
    is raised by ``raise_for_status``, like an HTTP error). Returns the (url, loop) of each GET."""
    gets: list[tuple[str, asyncio.AbstractEventLoop]] = []

    class Response:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            if isinstance(self._body, Exception):
                raise self._body

        def json(self):
            return self._body

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, **kwargs):
            gets.append((url, asyncio.get_running_loop()))
            return Response(responses[url])

    monkeypatch.setattr(httpx, "AsyncClient", AsyncClient)
    return gets


def _filing(db, company, accession, filed, xbrl_data):
    row = Filing(
        company_id=company.id, accession_number=accession, filing_type="10-K",
        filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
        sec_url=f"https://example.test/{accession}/",
        document_url=f"https://example.test/{accession}/primary.htm",
        xbrl_data=xbrl_data,
    )
    db.add(row)
    db.flush()
    return row


def _current(period, **values):
    """Standardized metrics in ``extract_standardized_metrics``'s shape: one current point each."""
    return {concept: {"current": {"period": period, "value": value}} for concept, value in values.items()}


def _messages(caplog, prefix):
    # Matched by text, not logger name: a pure move renames the module logger.
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(prefix)]


def test_f0_1_backfill_default_fetcher_fetches_once_per_company_and_caches(sessions, app_loop, monkeypatch):
    """F0.1 — ``backfill_facts(db)``, the call shape of ``app/routers/internal.py:175``, resolves the
    default fetcher to the module's ``_fetch_companyfacts_sync`` (facts_service.py:763) and fetches
    companyfacts ONCE per company, caching the extracted authoritative map, or ``{}`` for a miss,
    by company (:804-809). Every existing test injects a fetcher or disables the cross-check.

    The sync bridge hands each fetch to the registered app loop through the shared limiter, so a
    request running on that loop identifies the default fetcher without patching facts_service.
    A has two filings and one fetch whose cached map corrects both; C's fetch fails and the empty
    map is cached too, so C's second filing does not refetch.
    """
    url = {cik: companyfacts_url(cik) for cik in ("1001", "1002", "1003")}
    gets = _fake_httpx(monkeypatch, {
        url["1001"]: {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 900.0},
            {"start": "2024-01-01", "end": "2024-12-31", "val": 1000.0},
        ]}}}}},
        url["1002"]: {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 5000.0},
        ]}}}}},
        url["1003"]: RuntimeError("503 Service Unavailable"),
    })
    limited: list[asyncio.AbstractEventLoop] = []

    async def no_wait(request_fn, *args, **kwargs):
        limited.append(asyncio.get_running_loop())
        return await request_fn(*args, **kwargs)

    def extract(xbrl_data):  # every parsed revenue is scale-bugged; only companyfacts can fix it
        return _current(xbrl_data["period"], revenue=1.0)

    with sessions() as db:
        a, b, c = (Company(cik=cik, ticker=ticker, name=ticker)
                   for cik, ticker in (("1001", "AAA"), ("1002", "BBB"), ("1003", "CCC")))
        db.add_all([a, b, c])
        db.flush()
        for company, accession, filed, period in (
            (a, "A-FY23", "2024-02-01", "2023-12-31"),
            (b, "B-FY23", "2024-02-15", "2023-12-31"),
            (c, "C-FY23", "2024-03-01", "2023-12-31"),
            (a, "A-FY24", "2025-02-01", "2024-12-31"),
            (c, "C-FY24", "2025-03-01", "2024-12-31"),
        ):
            _filing(db, company, accession, filed, {"period": period})
        db.commit()

        with _limiter(no_wait), mock.patch.object(compat.xbrl_service, "extract_standardized_metrics", extract):
            stats = facts_service.backfill_facts(db)

        rows = [(r.accession, r.concept, r.period_end, float(r.value), r.source, r.reconciled, r.is_latest)
                for r in db.query(FinancialFact).order_by(FinancialFact.accession)]

    assert [u for u, _loop in gets] == [url["1001"], url["1002"], url["1003"]]
    assert [loop for _u, loop in gets] == [app_loop] * 3
    assert limited == [app_loop] * 3
    assert stats == {"filings_processed": 5, "facts_inserted": 5, "facts_skipped": 0,
                     "facts_rejected": 0, "extract_errors": 0}
    assert rows == [
        ("A-FY23", "revenue", date(2023, 12, 31), 900.0, "companyfacts", True, True),
        ("A-FY24", "revenue", date(2024, 12, 31), 1000.0, "companyfacts", True, True),
        ("B-FY23", "revenue", date(2023, 12, 31), 5000.0, "companyfacts", True, True),
        ("C-FY23", "revenue", date(2023, 12, 31), 1.0, "edgar_xbrl", True, True),
        ("C-FY24", "revenue", date(2024, 12, 31), 1.0, "edgar_xbrl", True, True),
    ]


def test_f0_2_sync_bridge_inside_a_running_loop_returns_none_without_the_limiter(app_loop, caplog):
    """F0.2 — called on a thread that is running a loop, ``_fetch_companyfacts_sync`` returns None at
    once (facts_service.py:493-496): it neither reaches the limiter nor hands the coroutine to the
    app loop, whose ``.result()`` would deadlock the loop that must run it. A live app loop on
    another thread is registered, so without the guard the fetch would visibly complete there."""
    reached: list[asyncio.AbstractEventLoop] = []

    async def canned(request_fn, *args, **kwargs):  # never runs the request: no socket either way
        reached.append(asyncio.get_running_loop())
        return {"facts": {}}

    async def caller():
        return facts_service._fetch_companyfacts_sync("320193")

    caplog.set_level(logging.WARNING)
    with _limiter(canned):
        result = asyncio.run(caller())

    assert result is None
    assert reached == []
    assert _messages(caplog, "companyfacts sync fetch") == [
        "companyfacts sync fetch skipped for CIK 320193: called from inside a loop"
    ]


def test_f0_2_sync_bridge_timeout_cancels_the_handed_off_fetch_and_returns_none(app_loop, monkeypatch, caplog):
    """F0.2 — when the app loop does not answer within ``COMPANYFACTS_SYNC_TIMEOUT_SECONDS``, the
    bridge cancels the handed-off future and returns None (facts_service.py:498-505), never
    falling through to a private loop. The future times out at once (no real wait); the coroutine
    is closed unscheduled."""

    class StuckFuture:
        def __init__(self):
            self.timeouts: list = []
            self.cancels = 0

        def result(self, timeout=None):
            self.timeouts.append(timeout)
            raise FuturesTimeoutError()

        def cancel(self):
            self.cancels += 1
            return True

    stuck = StuckFuture()
    handed: list[tuple[str, asyncio.AbstractEventLoop]] = []

    def run_coroutine_threadsafe(coro, loop):
        handed.append((coro.__name__, loop))
        coro.close()
        return stuck

    reached: list[bool] = []

    async def canned(request_fn, *args, **kwargs):
        reached.append(True)
        return {"facts": {}}

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", run_coroutine_threadsafe)
    caplog.set_level(logging.WARNING)
    with _limiter(canned):
        result = facts_service._fetch_companyfacts_sync("320193")

    assert result is None
    assert handed == [("_fetch_companyfacts_async", app_loop)]
    assert stuck.timeouts == [600.0]
    assert stuck.cancels == 1
    assert reached == []
    assert _messages(caplog, "companyfacts sync fetch") == ["companyfacts sync fetch timed out for CIK 320193"]


def test_f0_3_remediate_rolls_back_a_filing_whose_reprocess_raises_after_the_delete(sessions, caplog):
    """F0.3 — ``remediate_industry_facts`` writes each filing atomically (facts_service.py:945-963):
    blob overwrite, delete of its affected-concept rows, ``process_filing_facts(commit=False)``,
    one commit. When the reprocess raises after the delete, the rollback restores the blob and the
    deleted rows, so the NEXT filing's commit cannot persist the half-done one; the filing counts
    in ``errors`` and ``skipped_ids``. The raise comes from the edgar compat singleton's extractor,
    inside ``process_filing_facts``. ``TestRemediateIndustryFacts``
    (tests/unit/test_facts_service.py:1002-1097) covers replace, dry run and the None skip only."""
    corrected = _current("2024-12-31", net_interest_income=303_000_000.0,
                         noninterest_income=11_900_000.0, net_income=75_000_000.0)

    def extract(xbrl_data):
        if "boom" in xbrl_data:
            raise RuntimeError("re-extraction failed after the delete")
        return xbrl_data["std"]

    with sessions() as db:
        bank = Company(cik="6022001", ticker="BNK", name="Bank", sic="6022")
        db.add(bank)
        db.flush()
        older = _filing(db, bank, "BNK-FY23", "2024-03-01", {"stale": "FY23 fee-income revenue"})
        newer = _filing(db, bank, "BNK-FY24", "2025-03-01", {"stale": "FY24 fee-income revenue"})
        db.commit()
        facts_service.process_filing_facts(
            db, older, standardized=_current("2023-12-31", revenue=11_100_000.0, net_income=71_000_000.0))
        facts_service.process_filing_facts(
            db, newer, standardized=_current("2024-12-31", revenue=12_000_000.0, net_income=75_000_000.0))
        older_id, newer_id = older.id, newer.id
        older_stamp = older.processed_facts_at
        older_rows = sorted((r.id, r.concept, float(r.value), r.source, r.reconciled, r.is_latest)
                            for r in db.query(FinancialFact).filter_by(accession="BNK-FY23"))
        assert sorted(row[1] for row in older_rows) == ["net_income", "revenue"]  # the stale rows exist
        fresh = {older_id: {"boom": "re-extraction will fail"}, newer_id: {"std": corrected}}

        caplog.set_level(logging.WARNING)
        with mock.patch.object(compat.xbrl_service, "extract_standardized_metrics", extract):
            stats = facts_service.remediate_industry_facts(
                db, refetch=lambda _company, filing: fresh[filing.id], tickers=["bnk"])

    with sessions() as check:
        older_after = check.get(Filing, older_id)
        newer_after = check.get(Filing, newer_id)
        assert older_after.xbrl_data == {"stale": "FY23 fee-income revenue"}
        assert older_after.processed_facts_at == older_stamp
        assert sorted((r.id, r.concept, float(r.value), r.source, r.reconciled, r.is_latest)
                      for r in check.query(FinancialFact).filter_by(accession="BNK-FY23")) == older_rows
        assert newer_after.xbrl_data == {"std": corrected}
        assert sorted((r.concept, float(r.value), r.is_latest)
                      for r in check.query(FinancialFact).filter_by(accession="BNK-FY24")) == [
            ("net_income", 75_000_000.0, True),
            ("net_interest_income", 303_000_000.0, True),
            ("noninterest_income", 11_900_000.0, True),
        ]
    assert stats == {
        "companies": 1, "filings_refetched": 2, "filings_skipped": 0,
        "facts_deleted": 1, "facts_inserted": 2, "errors": 1,
        "remediated_ids": [newer_id], "skipped_ids": [older_id],
    }
    assert _messages(caplog, "remediate:") == [f"remediate: write failed for filing {older_id}"]


def test_f0_4_sync_companyfacts_batch_isolates_each_company_failure(sessions, inflight, monkeypatch, caplog):
    """F0.4 — one company's failure never stops ``sync_companyfacts_batch`` (facts_service.py:2125-2153):
    an exception is logged, ROLLED BACK (so none of that company's staged writes ride a later
    company's commit) and counted ``failed``; an unsynced result counts ``failed``; a refresh adds
    its inserts; a TTL hit counts ``fresh``; IFRS-only counts on top; ``expire_on_commit`` is off
    for the walk and restored after. Its one test today patches it out
    (tests/unit/test_internal_durable_tasks.py:232)."""
    monkeypatch.setattr(settings, "COMPANYFACTS_SYNC_TTL_HOURS", 24)
    fy24 = {"start": "2024-01-01", "end": "2024-12-31", "accn": "K24", "form": "10-K", "filed": "2025-02-15"}
    payload = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [{**fy24, "val": 1000.0}]}},
        "NetIncomeLoss": {"units": {"USD": [{**fy24, "val": 100.0}]}},
    }}}
    ifrs_only = {"facts": {"ifrs-full": {"Revenue": {"units": {"EUR": []}}}}}

    with sessions() as db:
        companies = [Company(cik=f"20{i}", ticker=f"S{i}", name=f"Sync {i}") for i in range(1, 7)]
        companies[5].facts_synced_at = utcnow() - timedelta(hours=1)  # S6 is inside the TTL
        db.add_all(companies)
        db.commit()
        ids = [company.id for company in companies]
        assert ids == sorted(ids)  # the walk is in id order: S1 … S6

        fetched: list[str] = []
        walk_expire: list[bool] = []

        async def fetcher(cik):
            fetched.append(cik)
            walk_expire.append(db.expire_on_commit)
            if cik == "202":
                raise RuntimeError("companyfacts transport exploded")
            return {"201": payload, "203": None, "204": payload, "205": ifrs_only}[cik]

        real_commit = db.commit
        failed_commit: list[list[int]] = []

        def commit():  # the walk's first commit (S1's persist) fails at the database
            if not failed_commit:
                failed_commit.append(sorted({o.company_id for o in db.new if isinstance(o, FinancialFact)}))
                raise RuntimeError("connection lost at commit")
            real_commit()

        monkeypatch.setattr(db, "commit", commit)
        caplog.set_level(logging.WARNING)
        stats = asyncio.run(facts_service.sync_companyfacts_batch(db, fetcher=fetcher))
        expire_after = db.expire_on_commit

    with sessions() as check:
        facts = {cid: sorted((f.concept, float(f.value), f.source)
                             for f in check.query(FinancialFact).filter_by(company_id=cid)) for cid in ids}
        stamped = [check.get(Company, cid).facts_synced_at is not None for cid in ids]

    assert stats == {"companies": 6, "refreshed": 2, "fresh": 1, "failed": 3, "unsupported_ifrs": 1, "inserted": 3}
    assert fetched == ["201", "202", "203", "204", "205"]  # S6's TTL hit never fetches
    assert failed_commit == [[ids[0]]]
    assert facts == {
        ids[0]: [], ids[1]: [], ids[2]: [],
        ids[3]: [("net_income", 100.0, "companyfacts"), ("net_margin", 10.0, "derived"),
                 ("revenue", 1000.0, "companyfacts")],
        ids[4]: [], ids[5]: [],
    }
    assert stamped == [False, False, False, True, True, True]
    assert walk_expire == [False] * 5 and expire_after is True
    assert inflight == {}  # every claim released, failures included
    assert _messages(caplog, "companyfacts sync failed") == [
        f"companyfacts sync failed for company {ids[0]}",
        f"companyfacts sync failed for company {ids[1]}",
    ]


@pytest.mark.parametrize("kwargs, expected", [
    pytest.param({"tickers": ["ddd", "aaa"], "watchlist_only": True}, ["AAA", "DDD"], id="tickers-beat-watchlist"),
    pytest.param({"tickers": [], "watchlist_only": True}, ["BBB", "CCC"], id="empty-tickers-mean-none"),
    pytest.param({"watchlist_only": True}, ["BBB", "CCC"], id="watchlist-once-per-company"),
    pytest.param({"watchlist_only": True, "limit": 1}, ["BBB"], id="watchlist-limit"),
    pytest.param({}, ["AAA", "BBB", "CCC", "DDD"], id="all-companies"),
    pytest.param({"limit": 2}, ["AAA", "BBB"], id="all-limit"),
])
def test_f0_4_sync_companyfacts_batch_cohort_precedence(sessions, inflight, kwargs, expected):
    """F0.4 — cohort precedence (facts_service.py:2115-2123): explicit ``tickers`` (uppercased; an
    empty list counts as none) beat ``watchlist_only`` (companies on any user's watchlist, once
    each), which beats all companies; always in id order, with ``limit`` applied last."""
    with sessions() as db:
        companies = {t: Company(cik=f"cik-{t}", ticker=t, name=t) for t in ("AAA", "BBB", "CCC", "DDD")}
        users = [User(email="one@example.test"), User(email="two@example.test")]
        db.add_all([*companies.values(), *users])
        db.flush()
        db.add_all([
            Watchlist(user_id=users[0].id, company_id=companies["BBB"].id),
            Watchlist(user_id=users[1].id, company_id=companies["BBB"].id),
            Watchlist(user_id=users[0].id, company_id=companies["CCC"].id),
        ])
        db.commit()
        ticker_of = {company.cik: ticker for ticker, company in companies.items()}
        walked: list[str] = []

        async def fetcher(cik):
            walked.append(ticker_of[cik])
            return None  # unsynced: nothing is written, every walked company counts failed

        stats = asyncio.run(facts_service.sync_companyfacts_batch(db, fetcher=fetcher, **kwargs))

    assert walked == expected
    n = len(expected)
    assert stats == {"companies": n, "refreshed": 0, "fresh": 0, "failed": n, "unsupported_ifrs": 0, "inserted": 0}


def test_f0_5_normalize_companyfacts_identity_dedup_keeps_the_first_emitted(monkeypatch):
    """F0.5 — the last step of ``normalize_companyfacts`` (facts_service.py:1501-1512) keeps the FIRST
    fact per identity (concept, period_end, fiscal_period, unit, accession), in emission order.

    No payload reaches this step under the production registries: 60,000 randomized payloads gave
    no collision while F0 was written, and the same fuzz collides in about half of its payloads
    once a duration concept is also registered as an instant. This anchor registers one that way,
    in place on the shared registry object (monkeypatch restores it): the duration pass emits FY
    500 and Q4 130 for 2024-12-31, then the instant pass emits FY for the same end and accession
    from the later-listed item, 130 — the collision. The first-emitted FY 500 must survive. The
    2023 item carries no start, so only the instant pass emits it: proof the injected path is live.
    """
    monkeypatch.setitem(facts_service.COMPANYFACTS_INSTANT_TAGS, "gross_profit", ("GrossProfit",))
    k24 = {"accn": "K24", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-15"}
    payload = {"facts": {"us-gaap": {"GrossProfit": {"units": {"USD": [
        {**k24, "start": "2024-01-01", "end": "2024-12-31", "val": 500.0},
        {**k24, "start": "2024-10-01", "end": "2024-12-31", "val": 130.0},
        {"accn": "K23", "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-15",
         "end": "2023-12-31", "val": 410.0},
    ]}}}}}
    base = {"company_id": 7, "filing_id": None, "concept": "gross_profit", "raw_tag": "us-gaap:GrossProfit",
            "unit": "USD", "form": "10-K", "source": "companyfacts", "reconciled": True}

    facts, meta = facts_service.normalize_companyfacts(7, payload)

    assert meta == {"unsupported_ifrs": False, "quarterly_exclusions": [], "quarterly_excluded_count": 0}
    provenance = {"version": 1, "method": "reported", "validation": "passed", "reasons": [],
                  "formula": None, "inputs": [], "calculation_version": "quarterly-v2"}
    assert facts == [
        {**base, "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31), "value": 500.0,
         "accession": "K24", "fiscal_year": 2024, "fiscal_period": "FY",
         "provenance": {**provenance, "filed_at": "2025-02-15"}},
        {**base, "period_start": date(2024, 10, 1), "period_end": date(2024, 12, 31), "value": 130.0,
         "accession": "K24", "fiscal_year": 2024, "fiscal_period": "Q4",
         "provenance": {**provenance, "filed_at": "2025-02-15"}},
        {**base, "period_start": None, "period_end": date(2023, 12, 31), "value": 410.0,
         "accession": "K23", "fiscal_year": 2023, "fiscal_period": "FY",
         "provenance": {**provenance, "filed_at": "2024-02-15"}},
    ]


_YEAR = {"start": "2024-01-01", "end": "2024-12-31"}  # 365 days: duration penalty 0
_53_WEEKS = {"start": "2023-12-25", "end": "2024-12-31"}  # 372 days: duration penalty 7


@pytest.mark.parametrize("tag, items, expected", [
    pytest.param("Revenues", [{**_YEAR, "val": 1000.0}, {**_YEAR, "val": 1010.0}],
                 {("revenue", date(2024, 12, 31)): 1010.0}, id="equal-penalty-later-restatement-wins"),
    pytest.param("Assets", [{"end": "2024-12-31", "val": 5000.0}, {"end": "2024-12-31", "val": 5100.0}],
                 {("total_assets", date(2024, 12, 31)): 5100.0}, id="instant-later-restatement-wins"),
    pytest.param("Revenues", [{**_YEAR, "val": 1000.0}, {**_53_WEEKS, "val": 1100.0}],
                 {("revenue", date(2024, 12, 31)): 1000.0}, id="closer-to-a-year-beats-a-later-item"),
    pytest.param("Revenues", [{**_53_WEEKS, "val": 1100.0}, {**_YEAR, "val": 1000.0}],
                 {("revenue", date(2024, 12, 31)): 1000.0}, id="closer-to-a-year-wins-when-later"),
])
def test_f0_6_extract_authoritative_values_restatement_tie_break(tag, items, expected):
    """F0.6 — per period the item closest to 365 days wins, and on an EQUAL penalty the later list
    item wins: companyfacts lists in filing order, so that is the newer restatement (``<=`` at
    facts_service.py:420). An instant's penalty is always 0, so its latest-listed value wins."""
    payload = {"facts": {"us-gaap": {tag: {"units": {"USD": items}}}}}
    assert facts_service.extract_authoritative_values(payload) == expected
