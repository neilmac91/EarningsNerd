"""Route characterization for /api/companies search, trending and get-by-ticker.

The error mapping of these three routes had no route-level test: the SEC-unavailable 503s, the
generic 500 detail strings, the 404, the unsupported-foreign response and the multi-CIK
concurrent-search recovery (with its ``company_upsert_conflict`` line on the router's logger). This
suite pins them so moving the routes' database work into
``app/services/company_lookup_service.py`` is provably behaviour-neutral. SEC calls and Yahoo
quotes are patched; rows live in the shared test DB (trending uses a private engine) and every
shared-DB row this file creates is deleted.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.routers.companies as companies_router
from app.database import SessionLocal, get_db
from app.models import Company, Filing
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
    client, monkeypatch, override_db, caplog
):
    """Two CIKs, one raced: the batch flush hits unique-CIK, the recovery re-resolves BOTH (the
    genuinely-new one is not dropped), the response keeps SEC order, and the conflict line names
    every response CIK on ``app.routers.companies``."""
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
    verify = SessionLocal()
    try:
        assert verify.query(Company).filter(Company.cik == RACED_CIK).count() == 1
        assert verify.query(Company).filter(Company.cik == NEW_CIK).count() == 1
    finally:
        verify.close()


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
             "stock_quote": None, "coverage_status": None, "coverage_reason": None},
            {"id": 1, "cik": "0000000001", "ticker": "ONE", "name": "One", "exchange": "NYSE",
             "stock_quote": None, "coverage_status": None, "coverage_reason": None},
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
        "coverage_reason": UNSUPPORTED_FOREIGN_REASON,
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
        "stock_quote": None, "coverage_status": None, "coverage_reason": None,
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


def test_miss_with_unpersistable_sec_hit_is_the_wrapped_500(client, monkeypatch):
    """A failure inside the persistence unit keeps its wrapped 500 detail (str of the error)."""
    async def search(_query):
        return [{"cik": NEW_CIK, "ticker": "ZZ2"}]  # no "name": the persistence unit raises KeyError

    monkeypatch.setattr(sec_edgar_service, "search_company", search)
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)
    resp = client.get("/api/companies/ZZ2")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Error fetching company: 'name'"}


def test_miss_persists_the_sec_hit_under_its_primary_ticker(client, monkeypatch):
    monkeypatch.setattr(sec_edgar_service, "search_company", _sec(_hit(NEW_CIK, "ZZ2-PA", "Zeta Two")))
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", _primary_from_cik)
    resp = client.get("/api/companies/ZZ2-PA")
    assert resp.status_code == 200
    body = resp.json()
    assert (body["cik"], body["ticker"], body["name"], body["exchange"]) == (NEW_CIK, "ZZ2", "Zeta Two", "NASDAQ")
    verify = SessionLocal()
    try:
        assert verify.query(Company).filter(Company.cik == NEW_CIK).one().id == body["id"]
    finally:
        verify.close()
