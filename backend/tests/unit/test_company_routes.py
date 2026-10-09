"""Route characterization for /api/companies search, trending and get-by-ticker.

The error mapping of these three routes had no route-level test: the SEC-unavailable 503s, the
generic 500 detail strings, the 404, the unsupported-foreign response, which get-by-ticker failures
stay outside its wrapped 500, and the multi-CIK concurrent-search recovery (its
``company_upsert_conflict`` line on the router's logger, its commit, the resolver's ``path``
labels, which errors enter it and the generic 500 when it fails too). This suite pins them for the
move of the routes' database work into ``app/services/company_lookup_service.py``. Row counts
cannot see a dropped recovery commit here: under SQLite's legacy transaction handling the per-row
SAVEPOINT is the outermost transaction and its RELEASE commits, so a commit spy pins it instead.
Transaction placement beyond what these tests observe (e.g. the post-commit refresh, which changes
no response) rests on the move being verbatim. SEC calls and Yahoo quotes are patched; rows live
in the shared test DB (trending uses a private engine) and every shared-DB row this file creates
is deleted.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

import app.routers.companies as companies_router
from app.database import SessionLocal, get_db
from app.models import Company, Filing
from app.services import company_lookup_service
from app.services.company_coverage import UNSUPPORTED_FOREIGN_REASON
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.exceptions import EdgarError
from main import app

RACED_CIK = "0009900001"
NEW_CIK = "0009900002"
_CIKS = [RACED_CIK, NEW_CIK, RACED_CIK.lstrip("0"), NEW_CIK.lstrip("0")]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _purge():
    db = SessionLocal()
    try:
        db.query(Company).filter(Company.cik.in_(_CIKS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_rows():
    _purge()
    yield
    _purge()


@pytest.fixture(autouse=True)
def _no_quotes(monkeypatch):
    async def no_quote(_ticker):
        return None

    monkeypatch.setattr(companies_router, "get_stock_quote", no_quote)
    monkeypatch.setattr(companies_router, "_get_stock_quote_with_timeout", no_quote)


def _sec(*hits):
    async def search(_query):
        return list(hits)

    return search


async def _primary_from_cik(cik):
    return f"ZZ{cik[-1]}"


def _hit(cik, ticker="ZZX", name="Zeta Corp", exchange="NASDAQ"):
    return {"cik": cik, "ticker": ticker, "name": name, "exchange": exchange}


@pytest.fixture()
def override_db():
    """Serve the route a caller-supplied session (restored afterwards)."""
    sessions = []

    def install(db):
        sessions.append(db)

        def _override():
            yield db

        app.dependency_overrides[get_db] = _override

    yield install
    app.dependency_overrides.pop(get_db, None)
    for db in sessions:
        db.close()


@pytest.fixture()
def resolver_paths(monkeypatch):
    """The ``path`` label each call to the CIK-first resolver passes (it names the call site in
    ``company_resolution``'s ``company_upsert_conflict`` warning)."""
    paths = []
    real = company_lookup_service.resolve_or_create_company_by_cik

    def recording(db, **kwargs):
        paths.append(kwargs["path"])
        return real(db, **kwargs)

    monkeypatch.setattr(company_lookup_service, "resolve_or_create_company_by_cik", recording)
    return paths


def _unique_cik_violation():
    return IntegrityError("INSERT INTO companies", {}, Exception("UNIQUE constraint failed"))


def _spy_commits(monkeypatch, db, caplog, fail_first=None):
    """Per ``db.commit()``, how many ``company_upsert_conflict`` lines were logged before it.

    ``fail_first`` (an exception) makes the first commit raise it instead.
    """
    calls = []
    real_commit = db.commit

    def commit():
        calls.append(sum("company_upsert_conflict" in r.getMessage() for r in caplog.records))
        if fail_first is not None and len(calls) == 1:
            raise fail_first
        real_commit()

    monkeypatch.setattr(db, "commit", commit)
    return calls


def _router_log(caplog):
    """(level, message) of each record on the router's logger, in order."""
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == "app.routers.companies"]


# --- /search ---------------------------------------------------------------------------------


def test_search_without_sec_hits_returns_empty_list_without_touching_the_db(client, monkeypatch, override_db):
    db = SessionLocal()

    def no_query(*_a, **_k):
        raise AssertionError("search must not query the DB when SEC has no hits")

    monkeypatch.setattr(db, "query", no_query)
    override_db(db)
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec())
    resp = client.get("/api/companies/search", params={"q": "zeta"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_sec_error_is_503(client, monkeypatch):
    async def down(_query):
        raise EdgarError("down")

    monkeypatch.setattr(sec_edgar_service, "search_company", down)
    resp = client.get("/api/companies/search", params={"q": "zeta"})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "SEC EDGAR is temporarily unavailable. Please retry shortly."}


def test_search_database_failure_is_the_generic_500(client, monkeypatch, override_db):
    db = SessionLocal()

    def broken_query(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "query", broken_query)
    override_db(db)
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec(_hit(NEW_CIK)))
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)
    resp = client.get("/api/companies/search", params={"q": "zeta"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected error occurred while searching for companies."}


def test_search_race_keeps_every_cik_in_sec_order_and_logs_on_the_router_logger(
    client, monkeypatch, override_db, caplog, resolver_paths
):
    """Two CIKs, one raced: the batch flush hits unique-CIK, the recovery re-resolves BOTH (the
    genuinely-new one is not dropped), the response keeps SEC order, the conflict line names
    every response CIK on ``app.routers.companies``, and the recovery commits after that line."""
    seed = SessionLocal()
    seed.add(Company(cik=RACED_CIK, ticker="ZZ1", name="Zeta Corp"))
    seed.commit()
    seed.close()

    db = SessionLocal()
    real_query = db.query
    state = {"missed": False}

    def flaky_query(*args, **kwargs):
        if not state["missed"] and args and args[0] is Company:
            state["missed"] = True

            class _Empty:
                def filter(self, *a, **k):
                    return self

                def all(self):
                    return []

            return _Empty()
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db, "query", flaky_query)
    commits = _spy_commits(monkeypatch, db, caplog)
    override_db(db)
    monkeypatch.setattr(
        sec_edgar_service, "search_company", _sec(_hit(RACED_CIK, "ZZ1"), _hit(NEW_CIK, "ZZ2", "Zeta Two"))
    )
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)

    with caplog.at_level(logging.WARNING, logger="app.routers.companies"):
        resp = client.get("/api/companies/search", params={"q": "zeta"})

    assert resp.status_code == 200
    assert [(r["cik"], r["ticker"]) for r in resp.json()] == [(RACED_CIK, "ZZ1"), (NEW_CIK, "ZZ2")]
    conflict = [r for r in caplog.records if "company_upsert_conflict" in r.getMessage()]
    assert [(r.name, r.levelno, r.getMessage()) for r in conflict] == [(
        "app.routers.companies",
        logging.WARNING,
        f"company_upsert_conflict cik={RACED_CIK},{NEW_CIK} ticker=zeta path=companies.search",
    )]
    # The flush failed inside its SAVEPOINT, so the batch commit never ran: the only commit is the
    # recovery's, after the conflict line.
    assert commits == [1]
    assert resolver_paths == ["companies.search", "companies.search"]
    verify = SessionLocal()
    try:
        assert verify.query(Company).filter(Company.cik == RACED_CIK).count() == 1
        assert verify.query(Company).filter(Company.cik == NEW_CIK).count() == 1
    finally:
        verify.close()


def test_search_conflict_raised_by_the_batch_commit_takes_the_same_recovery(
    client, monkeypatch, override_db, caplog
):
    """The batch commit, not only the flush, sits inside the conflict handling: its IntegrityError
    logs the same conflict line and recovers to a 200 in SEC order."""
    db = SessionLocal()
    commits = _spy_commits(monkeypatch, db, caplog, fail_first=_unique_cik_violation())
    override_db(db)
    monkeypatch.setattr(
        sec_edgar_service, "search_company", _sec(_hit(RACED_CIK, "ZZ1"), _hit(NEW_CIK, "ZZ2", "Zeta Two"))
    )
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)

    with caplog.at_level(logging.WARNING, logger="app.routers.companies"):
        resp = client.get("/api/companies/search", params={"q": "zeta"})

    assert resp.status_code == 200
    assert [(r["cik"], r["ticker"]) for r in resp.json()] == [(RACED_CIK, "ZZ1"), (NEW_CIK, "ZZ2")]
    assert [r.getMessage() for r in caplog.records if "company_upsert_conflict" in r.getMessage()] == [
        f"company_upsert_conflict cik={RACED_CIK},{NEW_CIK} ticker=zeta path=companies.search",
    ]
    assert commits == [0, 1]


def test_search_conflict_recovery_failure_is_the_generic_500(client, monkeypatch, override_db, caplog):
    """The recovery runs inside the route's generic handler: when it fails too (here the per-row
    resolve), the conflict line is followed by the generic ERROR line and the generic 500, not by
    the app's global handler."""
    db = SessionLocal()
    commits = _spy_commits(monkeypatch, db, caplog, fail_first=_unique_cik_violation())
    override_db(db)
    failure = OperationalError("SELECT companies", {}, Exception("database is locked"))

    def resolver_down(_db, **_kwargs):
        raise failure

    monkeypatch.setattr(company_lookup_service, "resolve_or_create_company_by_cik", resolver_down)
    monkeypatch.setattr(
        sec_edgar_service, "search_company", _sec(_hit(RACED_CIK, "ZZ1"), _hit(NEW_CIK, "ZZ2", "Zeta Two"))
    )
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)

    with caplog.at_level(logging.WARNING, logger="app.routers.companies"):
        resp = TestClient(app, raise_server_exceptions=False).get("/api/companies/search", params={"q": "zeta"})

    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected error occurred while searching for companies."}
    assert _router_log(caplog) == [
        (logging.WARNING, f"company_upsert_conflict cik={RACED_CIK},{NEW_CIK} ticker=zeta path=companies.search"),
        (logging.ERROR, f"Unexpected error searching companies for 'zeta': {failure}"),
    ]
    assert commits == [0]  # the recovery's own commit never ran


def test_search_non_integrity_commit_failure_skips_the_conflict_recovery(
    client, monkeypatch, override_db, caplog, resolver_paths
):
    """Only the unique-CIK IntegrityError enters the conflict recovery: another database error at
    the batch commit goes straight to the generic 500, with no conflict line and no recovery."""
    db = SessionLocal()
    failure = OperationalError("COMMIT", {}, Exception("database is locked"))
    commits = _spy_commits(monkeypatch, db, caplog, fail_first=failure)
    override_db(db)
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec(_hit(NEW_CIK, "ZZ2", "Zeta Two")))
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)

    with caplog.at_level(logging.WARNING, logger="app.routers.companies"):
        resp = client.get("/api/companies/search", params={"q": "zeta"})

    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected error occurred while searching for companies."}
    assert _router_log(caplog) == [
        (logging.ERROR, f"Unexpected error searching companies for 'zeta': {failure}"),
    ]
    assert commits == [0]
    assert resolver_paths == []


# --- /trending -------------------------------------------------------------------------------


def test_trending_orders_by_recent_filing_count_and_honours_limit(client, override_db, tmp_path):
    """A private engine, so the shared test DB's filings cannot reorder the ranking."""
    engine = create_engine(f"sqlite:///{tmp_path / 'trending.db'}", connect_args={"check_same_thread": False})
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    now = datetime.now(timezone.utc)
    with sessions() as seed:
        one = Company(cik="0000000001", ticker="ONE", name="One", exchange="NYSE")
        two = Company(cik="0000000002", ticker="TWO", name="Two", exchange=None)
        quiet = Company(cik="0000000003", ticker="QUIET", name="Quiet")
        seed.add_all([one, two, quiet])
        seed.flush()
        # QUIET's only filings are older than the 30-day window, so it never ranks.
        dated = [(one, now), (two, now), (two, now), (quiet, now - timedelta(days=40)),
                 (quiet, now - timedelta(days=45)), (quiet, now - timedelta(days=50))]
        for n, (company, filed) in enumerate(dated):
            seed.add(Filing(
                company_id=company.id,
                accession_number=f"0000000000-26-00000{n}",
                filing_type="10-Q",
                filing_date=filed,
                document_url="https://example.test/f",
                sec_url="https://example.test/f/",
            ))
        seed.commit()
    override_db(sessions())
    try:
        resp = client.get("/api/companies/trending")
        assert resp.status_code == 200
        assert resp.json() == [
            {"id": 2, "cik": "0000000002", "ticker": "TWO", "name": "Two", "exchange": None,
             "stock_quote": None, "coverage_status": None, "coverage_reason": None,
             "latest_filing": None},
            {"id": 1, "cik": "0000000001", "ticker": "ONE", "name": "One", "exchange": "NYSE",
             "stock_quote": None, "coverage_status": None, "coverage_reason": None,
             "latest_filing": None},
        ]
        limited = client.get("/api/companies/trending", params={"limit": 1})
        assert [r["ticker"] for r in limited.json()] == ["TWO"]
    finally:
        engine.dispose()


# --- /{ticker} -------------------------------------------------------------------------------


def test_unsupported_foreign_ticker_short_circuits_before_sec(client, monkeypatch):
    async def must_not_search(_query):
        raise AssertionError("an unsupported foreign ticker must not reach SEC")

    monkeypatch.setattr(sec_edgar_service, "search_company", must_not_search)
    resp = client.get("/api/companies/tcehy")
    assert resp.status_code == 200
    assert resp.json() == {
        "id": 0, "cik": "", "ticker": "TCEHY", "name": "Tencent Holdings Ltd", "exchange": None,
        "stock_quote": None, "coverage_status": "unsupported_foreign",
        "coverage_reason": UNSUPPORTED_FOREIGN_REASON, "latest_filing": None,
    }


def test_stored_company_is_served_without_sec(client, monkeypatch):
    seed = SessionLocal()
    seed.add(Company(cik=NEW_CIK, ticker="ZZ2", name="Zeta Two", exchange="NYSE"))
    seed.commit()
    company_id = seed.query(Company.id).filter(Company.cik == NEW_CIK).scalar()
    seed.close()

    async def must_not_search(_query):
        raise AssertionError("a stored ticker must not reach SEC")

    monkeypatch.setattr(sec_edgar_service, "search_company", must_not_search)
    resp = client.get("/api/companies/zz2")
    assert resp.status_code == 200
    assert resp.json() == {
        "id": company_id, "cik": NEW_CIK, "ticker": "ZZ2", "name": "Zeta Two", "exchange": "NYSE",
        "stock_quote": None, "coverage_status": None, "coverage_reason": None, "latest_filing": None,
    }


def test_miss_without_sec_hit_is_404(client, monkeypatch):
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec())
    resp = client.get("/api/companies/ZZNONE")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Company not found"}


def test_miss_with_sec_error_is_503(client, monkeypatch):
    async def down(_query):
        raise EdgarError("down")

    monkeypatch.setattr(sec_edgar_service, "search_company", down)
    resp = client.get("/api/companies/ZZNONE")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "SEC EDGAR is temporarily unavailable. Please retry shortly."}


def test_stored_ticker_lookup_failure_is_not_the_wrapped_500(client, monkeypatch, override_db):
    """The stored-ticker SELECT runs outside the miss path's try, so its failure reaches the app's
    global handler instead of becoming "Error fetching company: ..."."""
    db = SessionLocal()

    def broken_query(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "query", broken_query)
    override_db(db)
    resp = TestClient(app, raise_server_exceptions=False).get("/api/companies/ZZ2")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "db down", "type": "internal_server_error"}


def test_post_persist_release_failure_is_not_the_wrapped_500(client, monkeypatch, override_db):
    """The release after the persistence unit also runs outside the try (unlike the persistence
    unit itself, below)."""
    db = SessionLocal()
    real_close = db.close
    closes = []

    def close():
        closes.append(1)
        if len(closes) == 2:  # 1: before the SEC wait; 2: after the persistence unit
            raise RuntimeError("release failed")
        real_close()

    monkeypatch.setattr(db, "close", close)
    override_db(db)
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec(_hit(NEW_CIK, "ZZ2", "Zeta Two")))
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)
    resp = TestClient(app, raise_server_exceptions=False).get("/api/companies/ZZ2")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "release failed", "type": "internal_server_error"}


def test_miss_with_unpersistable_sec_hit_is_the_wrapped_500(client, monkeypatch):
    """A failure inside the persistence unit keeps its wrapped 500 detail (str of the error)."""
    async def search(_query):
        return [{"cik": NEW_CIK, "ticker": "ZZ2"}]  # no "name": the persistence unit raises KeyError

    monkeypatch.setattr(sec_edgar_service, "search_company", search)
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)
    resp = client.get("/api/companies/ZZ2")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Error fetching company: 'name'"}


def test_miss_persists_the_sec_hit_under_its_primary_ticker(client, monkeypatch, override_db, caplog, resolver_paths):
    """The persistence unit commits the new row itself. The row count alone cannot see that commit
    (the resolver's SAVEPOINT RELEASE already commits under SQLite; Postgres would lose the row), so
    the commit spy pins it."""
    db = SessionLocal()
    commits = _spy_commits(monkeypatch, db, caplog)
    override_db(db)
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec(_hit(NEW_CIK, "ZZ2-PA", "Zeta Two")))
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)
    resp = client.get("/api/companies/ZZ2-PA")
    assert resp.status_code == 200
    assert commits == [0]
    assert resolver_paths == ["companies.get_company"]
    body = resp.json()
    assert (body["cik"], body["ticker"], body["name"], body["exchange"]) == (NEW_CIK, "ZZ2", "Zeta Two", "NASDAQ")
    verify = SessionLocal()
    try:
        assert verify.query(Company).filter(Company.cik == NEW_CIK).one().id == body["id"]
    finally:
        verify.close()
