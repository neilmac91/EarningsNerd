"""P0-1 guardrail (data-quality plan): search returns ONE row per CIK bearing the PRIMARY ticker.

SEC's company_tickers.json carries one entry per listed security. Pre-fix, /api/companies/search
appended one response row per entry AND overwrote Company.ticker last-write-wins — preferreds
sort last in the file, so searching "jpm" persisted JPMorgan as JPM-PM (and the site served the
preferred share's quote). Each test uses the class's ACTUAL corrupting query: the common ticker
itself for preferred-suffix issuers ("jpm"), a shorter-prefix query for multi-class issuers
("goog" — "googl" would pass even on the broken code).
"""

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, get_db
from app.models import Company
from app.services.edgar.compat import sec_edgar_service
from main import app

JPM_CIK = "0000019617"
GOOGL_CIK = "0001652044"
BRK_CIK = "0001067983"
_ALL_CIKS = [JPM_CIK, GOOGL_CIK, BRK_CIK, JPM_CIK.lstrip("0"), GOOGL_CIK.lstrip("0"), BRK_CIK.lstrip("0")]

# File order mirrors SEC's: common/primary listings first, preferreds & secondary classes at
# higher indices (the load-bearing property the primary-ticker heuristic rests on).
FIXTURE_TICKERS = {
    "0": {"cik_str": 19617, "ticker": "JPM", "title": "JPMORGAN CHASE & CO"},
    "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
    "2": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
    "3": {"cik_str": 1652044, "ticker": "GOOG", "title": "Alphabet Inc."},
    "4": {"cik_str": 1067983, "ticker": "BRK-A", "title": "BERKSHIRE HATHAWAY INC"},
    "5": {"cik_str": 19617, "ticker": "JPM-PC", "title": "JPMORGAN CHASE & CO"},
    "6": {"cik_str": 1652044, "ticker": "GOOGN", "title": "Alphabet Inc."},
    "7": {"cik_str": 19617, "ticker": "JPM-PD", "title": "JPMORGAN CHASE & CO"},
    "8": {"cik_str": 19617, "ticker": "JPM-PM", "title": "JPMORGAN CHASE & CO"},
}


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


@pytest.fixture(autouse=True)
def clean_rows(db):
    db.rollback()
    db.query(Company).filter(Company.cik.in_(_ALL_CIKS)).delete()
    db.commit()
    yield
    db.rollback()
    db.query(Company).filter(Company.cik.in_(_ALL_CIKS)).delete()
    db.commit()


@pytest.fixture(autouse=True)
def fixture_tickers(monkeypatch):
    async def fake_tickers():
        return FIXTURE_TICKERS

    async def fake_quote(ticker):
        return None

    monkeypatch.setattr(sec_edgar_service, "_get_cached_tickers", fake_tickers)
    # The primary-ticker map is a class-level memo keyed off the tickers cache; reset it so this
    # fixture's FIXTURE_TICKERS drives it and nothing leaks in/out across tests.
    from app.services.edgar.compat import SECEdgarServiceCompat

    SECEdgarServiceCompat._primary_map = None
    SECEdgarServiceCompat._primary_map_built_at = None
    import app.routers.companies as companies_router

    monkeypatch.setattr(companies_router, "_get_stock_quote_with_timeout", fake_quote)
    monkeypatch.setattr(companies_router, "get_stock_quote", fake_quote)


def test_search_jpm_returns_single_row_with_primary_ticker(client, db):
    """The preferred-suffix class: the common ticker itself is the corrupting query."""
    resp = client.get("/api/companies/search", params={"q": "jpm"})
    assert resp.status_code == 200
    rows = [r for r in resp.json() if r["cik"] == JPM_CIK]
    assert len(rows) == 1  # one row per CIK, not one per share class
    assert rows[0]["ticker"] == "JPM"
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


def test_search_goog_prefix_resolves_googl(client, db):
    """The multi-class class: a shorter-prefix query matches GOOG/GOOGL/GOOGN; the primary
    (first file-order) entry must win — pre-fix, GOOGN (last) won the persisted ticker."""
    resp = client.get("/api/companies/search", params={"q": "goog"})
    assert resp.status_code == 200
    rows = [r for r in resp.json() if r["cik"] == GOOGL_CIK]
    assert len(rows) == 1
    assert rows[0]["ticker"] == "GOOGL"
    db.expire_all()
    assert db.query(Company).filter(Company.cik == GOOGL_CIK).one().ticker == "GOOGL"


def test_repeat_search_does_not_mutate(client, db):
    client.get("/api/companies/search", params={"q": "jpm"})
    client.get("/api/companies/search", params={"q": "jpm"})
    db.expire_all()
    rows = db.query(Company).filter(Company.cik == JPM_CIK).all()
    assert len(rows) == 1
    assert rows[0].ticker == "JPM"


def test_search_upgrades_corrupted_ticker_to_primary(client, db):
    """An already-corrupted row (the live prod state) is repaired by the next search."""
    db.add(Company(cik=JPM_CIK, ticker="JPM-PM", name="JPMORGAN CHASE & CO"))
    db.commit()
    resp = client.get("/api/companies/search", params={"q": "jpm"})
    assert resp.status_code == 200
    db.expire_all()
    row = db.query(Company).filter(Company.cik == JPM_CIK).one()
    assert row.ticker == "JPM"


def test_first_contact_multiticker_cik_single_insert(client, db):
    """Pre-fix, a not-yet-stored multi-ticker CIK created MULTIPLE same-CIK rows in one flush
    (unique-constraint 500). Now: exactly one insert, 200."""
    resp = client.get("/api/companies/search", params={"q": "berkshire"})
    assert resp.status_code == 200
    rows = [r for r in resp.json() if r["cik"] == BRK_CIK]
    assert len(rows) == 1
    assert rows[0]["ticker"] == "BRK-B"
    assert db.query(Company).filter(Company.cik == BRK_CIK).count() == 1


def test_preferred_class_url_resolves_to_canonical_row(client, db):
    """/api/companies/JPM-PM (stale bookmark) resolves via CIK to the canonical row without
    inserting — the frontend then normalizes the URL."""
    db.add(Company(cik=JPM_CIK, ticker="JPM", name="JPMORGAN CHASE & CO"))
    db.commit()
    resp = client.get("/api/companies/JPM-PM")
    assert resp.status_code == 200
    assert resp.json()["cik"] == JPM_CIK
    assert resp.json()["ticker"] == "JPM"
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


def test_get_company_self_heals_corrupted_ticker(client, db):
    """A JPM-PM-stored row (the live prod state) is canonicalized to JPM on the first
    /api/companies/JPM lookup — so the common's quote is served even before the repair runs,
    and any row the repair misses heals on first touch (the adversarial-review defense)."""
    db.add(Company(cik=JPM_CIK, ticker="JPM-PM", name="JPMORGAN CHASE & CO"))
    db.commit()
    resp = client.get("/api/companies/JPM")
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "JPM"
    db.expire_all()
    row = db.query(Company).filter(Company.cik == JPM_CIK).one()
    assert row.ticker == "JPM"


@pytest.mark.asyncio
async def test_primary_ticker_map_is_memoized(monkeypatch):
    """Efficiency guard (adversarial review): the primary lookup is O(1) off a map built once
    per tickers-cache refresh, not an O(N) scan per CIK — asserted via map object identity."""
    from app.services.edgar.compat import SECEdgarServiceCompat

    SECEdgarServiceCompat._primary_map = None
    SECEdgarServiceCompat._primary_map_built_at = None

    async def fake_tickers():
        return FIXTURE_TICKERS

    monkeypatch.setattr(sec_edgar_service, "_get_cached_tickers", fake_tickers)

    assert await sec_edgar_service.primary_ticker_for_cik("19617") == "JPM"
    first_map = SECEdgarServiceCompat._primary_map
    for _ in range(5):
        assert await sec_edgar_service.primary_ticker_for_cik("1652044") == "GOOGL"
    # Same map object across all lookups → built once, no per-CIK O(N) rebuild.
    assert SECEdgarServiceCompat._primary_map is first_map
    assert await sec_edgar_service.primary_ticker_for_cik("9999999") is None


def test_search_race_integrityerror_returns_200(db, monkeypatch):
    """Concurrent-search race: the existing-rows lookup misses, the insert hits unique-CIK,
    and the handler serves the winner's row — never a 500."""
    db.add(Company(cik=JPM_CIK, ticker="JPM", name="JPMORGAN CHASE & CO"))
    db.commit()

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

                def first(self):
                    return None

            return _Empty()
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db, "query", flaky_query)

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as racing_client:
            async def fake_tickers():
                return FIXTURE_TICKERS

            async def fake_quote(ticker):
                return None

            monkeypatch.setattr(sec_edgar_service, "_get_cached_tickers", fake_tickers)
            import app.routers.companies as companies_router

            monkeypatch.setattr(companies_router, "_get_stock_quote_with_timeout", fake_quote)
            resp = racing_client.get("/api/companies/search", params={"q": "jpm"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    rows = [r for r in resp.json() if r["cik"] == JPM_CIK]
    assert len(rows) == 1
    db.expire_all()
    assert db.query(Company).filter(Company.cik == JPM_CIK).count() == 1


@pytest.mark.asyncio
async def test_primary_ticker_is_first_file_order_entry(monkeypatch):
    async def fake_tickers():
        return FIXTURE_TICKERS

    monkeypatch.setattr(sec_edgar_service, "_get_cached_tickers", fake_tickers)
    assert await sec_edgar_service.primary_ticker_for_cik("0000019617") == "JPM"
    assert await sec_edgar_service.primary_ticker_for_cik("19617") == "JPM"
    assert await sec_edgar_service.primary_ticker_for_cik("1652044") == "GOOGL"
    assert await sec_edgar_service.primary_ticker_for_cik("1067983") == "BRK-B"
    assert await sec_edgar_service.primary_ticker_for_cik("9999999") is None
