"""A requested ticker binds to a company only by an exact match in SEC's ticker file.

``search_company`` is the typeahead's search: exact ticker hits first, then any entry whose name
or ticker merely contains the query. The company page, the filings list and precompute used to
take its first hit as the requested ticker's company, so a ticker missing from SEC's file (retired,
renamed or mistyped) served and persisted an unrelated issuer: RTN bound to Enterprise Products
PARTNERS, SQ to SQM, FB to FB Financial (FBK) and X to Exxon (XOM), and precompute paid to summarize
it. These tests pin the exact resolver (case-insensitive, '.' and '-' the same share-class
separator) on all three callers, and that the typeahead still returns partial matches.

Only the ticker file is faked (seeded into the L1 cache, so ``_get_cached_tickers``,
``_local_search`` and ``primary_ticker_for_cik`` run for real), plus the filings listing and the
stock quote. Rows live in the shared test DB; every row this file can create is deleted.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import app.routers.companies as companies_router
from app.config import settings
from app.database import SessionLocal
from app.models import Company, Filing
from app.services import filing_list_service
from app.services.edgar.compat import SECEdgarServiceCompat, sec_edgar_service
from app.services.precompute_service import precompute_one
from main import app

# Shaped like https://www.sec.gov/files/company_tickers.json (index -> entry, in SEC's file order;
# Berkshire lists its B shares first, so BRK-B is its primary). None of RTN (Raytheon before 2020),
# SQ (Block before 2025), FB (Meta before 2022) or X (U.S. Steel) is in it.
TICKER_FILE = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 34088, "ticker": "XOM", "title": "EXXON MOBIL CORP"},
    "2": {"cik_str": 1061219, "ticker": "EPD", "title": "ENTERPRISE PRODUCTS PARTNERS L.P."},
    "3": {"cik_str": 101829, "ticker": "RTX", "title": "RTX Corp"},
    "4": {"cik_str": 909037, "ticker": "SQM", "title": "SOCIEDAD QUIMICA Y MINERA DE CHILE S.A."},
    "5": {"cik_str": 1512673, "ticker": "XYZ", "title": "Block, Inc."},
    "6": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."},
    "7": {"cik_str": 1649749, "ticker": "FBK", "title": "FB Financial Corp"},
    "8": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
    "9": {"cik_str": 1067983, "ticker": "BRK-A", "title": "BERKSHIRE HATHAWAY INC"},
}
APPLE_CIK = "0000320193"
BERKSHIRE_CIK = "0001067983"
# A company stored while its ticker was listed (Raytheon Co., merged into RTX in 2020).
STORED_RETIRED = {"cik": "0001047122", "ticker": "RTN", "name": "RAYTHEON CO/"}

# Each retired ticker, and the unrelated issuer the first partial hit bound it to before the fix.
RETIRED = [("RTN", "EPD"), ("SQ", "SQM"), ("FB", "FBK"), ("X", "XOM")]
LISTED = [
    ("AAPL", APPLE_CIK, "AAPL"),
    ("aapl", APPLE_CIK, "AAPL"),
    ("BRK-B", BERKSHIRE_CIK, "BRK-B"),
    ("brk-b", BERKSHIRE_CIK, "BRK-B"),
    ("BRK.B", BERKSHIRE_CIK, "BRK-B"),
    ("brk.b", BERKSHIRE_CIK, "BRK-B"),
]

_CIKS = [str(entry["cik_str"]).zfill(10) for entry in TICKER_FILE.values()] + [STORED_RETIRED["cik"]]


def _purge() -> None:
    db = SessionLocal()
    try:
        ids = [row.id for row in db.query(Company.id).filter(Company.cik.in_(_CIKS))]
        if ids:
            db.query(Filing).filter(Filing.company_id.in_(ids)).delete(synchronize_session=False)
        db.query(Company).filter(Company.cik.in_(_CIKS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _stored_ciks() -> list[str]:
    db = SessionLocal()
    try:
        return sorted(row.cik for row in db.query(Company.cik).filter(Company.cik.in_(_CIKS)))
    finally:
        db.close()


def _seed_ticker_file(monkeypatch, ticker_file: dict) -> None:
    """Serve ``ticker_file`` from the fresh L1 cache (no network) and drop the primary-ticker memo."""
    monkeypatch.setattr(SECEdgarServiceCompat, "_tickers_cache", ticker_file)
    monkeypatch.setattr(SECEdgarServiceCompat, "_tickers_cache_time", datetime.now())
    monkeypatch.setattr(SECEdgarServiceCompat, "_primary_map", None)
    monkeypatch.setattr(SECEdgarServiceCompat, "_primary_map_built_at", None)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    _seed_ticker_file(monkeypatch, TICKER_FILE)

    async def no_quote(_ticker):
        return None

    monkeypatch.setattr(companies_router, "get_stock_quote", no_quote)
    monkeypatch.setattr(companies_router, "_get_stock_quote_with_timeout", no_quote)
    monkeypatch.setattr(settings, "ENABLE_HISTORY_BACKFILL_ON_VISIT", False)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", False)
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    _purge()
    yield
    _purge()


@pytest.fixture()
def listing(monkeypatch):
    """The CIKs the SEC filings listing was asked for; it returns no filings."""
    fetched: list[str] = []

    async def get_filings(cik, filing_types=None, limit=None):
        fetched.append(cik)
        return []

    monkeypatch.setattr(sec_edgar_service, "get_filings", get_filings)
    return fetched


# --- the three callers that bind a ticker -------------------------------------------------------


@pytest.mark.parametrize("ticker, first_partial_hit", RETIRED)
def test_company_route_404s_a_ticker_missing_from_the_sec_file(client, ticker, first_partial_hit):
    resp = client.get(f"/api/companies/{ticker}")
    assert resp.status_code == 404, f"{ticker} bound to {resp.json().get('ticker')} (first partial hit: {first_partial_hit})"
    assert resp.json() == {"detail": "Company not found"}
    assert _stored_ciks() == []


@pytest.mark.parametrize("ticker, first_partial_hit", RETIRED)
def test_filings_route_404s_a_ticker_missing_from_the_sec_file(client, listing, ticker, first_partial_hit):
    resp = client.get(f"/api/filings/company/{ticker}")
    assert resp.status_code == 404, f"{ticker} listed CIK {listing} (first partial hit: {first_partial_hit})"
    assert resp.json() == {"detail": "Company not found"}
    assert listing == []
    assert _stored_ciks() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker, first_partial_hit", RETIRED)
async def test_precompute_reports_company_not_found_for_a_ticker_missing_from_the_sec_file(
    listing, ticker, first_partial_hit
):
    result = await precompute_one(ticker, "10-K")
    assert result["status"] == "company_not_found", f"{ticker} resolved like {first_partial_hit}: {result}"
    assert listing == []
    assert _stored_ciks() == []


@pytest.mark.parametrize("ticker, cik, canonical", LISTED)
def test_company_route_resolves_listed_tickers_in_any_case_and_class_spelling(client, ticker, cik, canonical):
    resp = client.get(f"/api/companies/{ticker}")
    assert resp.status_code == 200, resp.json()
    assert (resp.json()["cik"], resp.json()["ticker"]) == (cik, canonical)
    assert _stored_ciks() == [cik]


@pytest.mark.parametrize("ticker, cik, _canonical", LISTED)
def test_filings_route_lists_the_listed_tickers_own_cik(client, listing, ticker, cik, _canonical):
    resp = client.get(f"/api/filings/company/{ticker}")
    assert resp.status_code == 200, resp.json()
    assert listing == [cik]


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker, cik, _canonical", LISTED)
async def test_precompute_resolves_listed_tickers_in_any_case_and_class_spelling(listing, ticker, cik, _canonical):
    result = await precompute_one(ticker, "10-K", dry_run=True)
    assert result["status"] == "no_filings", result
    assert listing == [cik]


def test_a_company_stored_under_a_retired_ticker_is_still_served_from_the_db(client, monkeypatch):
    """Deliberate: a row we stored while its ticker was listed stays reachable by that exact
    ticker. Only the SEC miss path changed; the DB lookup was always exact."""
    seed = SessionLocal()
    seed.add(Company(**STORED_RETIRED))
    seed.commit()
    seed.close()

    async def must_not_search(_query):
        raise AssertionError("a stored ticker must not reach the SEC ticker file")

    monkeypatch.setattr(sec_edgar_service, "search_company", must_not_search)
    resp = client.get("/api/companies/rtn")
    assert resp.status_code == 200, resp.json()
    assert (resp.json()["cik"], resp.json()["ticker"]) == (STORED_RETIRED["cik"], "RTN")


# --- the resolver and the typeahead -------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_ticker_is_exact_case_insensitive_and_treats_dot_and_dash_alike():
    resolve = sec_edgar_service.resolve_ticker
    assert await resolve("aapl") == {"ticker": "AAPL", "name": "Apple Inc.", "cik": APPLE_CIK, "exchange": None}
    for spelling in ("BRK-B", "brk-b", "BRK.B", "brk.b", " BRK.B "):
        assert (await resolve(spelling))["ticker"] == "BRK-B", spelling
    assert (await resolve("BRK.A"))["ticker"] == "BRK-A"
    for missing in ("RTN", "SQ", "FB", "X", "APL", "BRK", "", "   "):
        assert await resolve(missing) is None, missing


@pytest.mark.asyncio
async def test_resolve_ticker_finds_the_exact_entry_behind_more_partial_hits_than_search_returns(monkeypatch):
    """Twenty-five entries contain "AB" before the exact AB entry in file order; search caps at 20
    results, but it ranks exact ticker hits first, so the cap never drops the exact one."""
    crowded = {
        str(i): {"cik_str": 9_000_000 + i, "ticker": f"AB{i:02d}", "title": f"ABLE HOLDINGS {i}"}
        for i in range(25)
    }
    crowded["25"] = {"cik_str": 1109448, "ticker": "AB", "title": "AllianceBernstein Holding L.P."}
    _seed_ticker_file(monkeypatch, crowded)
    assert (await sec_edgar_service.resolve_ticker("ab"))["cik"] == "0001109448"


@pytest.mark.asyncio
async def test_search_still_returns_partial_name_and_ticker_matches():
    async def tickers(query):
        return [hit["ticker"] for hit in await sec_edgar_service.search_company(query)]

    assert await tickers("rtn") == ["EPD"]
    assert await tickers("sq") == ["SQM"]
    assert await tickers("fb") == ["FBK"]
    assert await tickers("brk") == ["BRK-B", "BRK-A"]


@pytest.mark.asyncio
async def test_search_ranks_a_dotted_class_ticker_as_its_exact_match():
    hits = await sec_edgar_service.search_company("brk.b")
    assert [hit["ticker"] for hit in hits] == ["BRK-B"]


def test_search_route_still_returns_partial_matches(client):
    resp = client.get("/api/companies/search", params={"q": "partners"})
    assert resp.status_code == 200, resp.json()
    assert [row["ticker"] for row in resp.json()] == ["EPD"]
    resp = client.get("/api/companies/search", params={"q": "SQ"})
    assert [row["ticker"] for row in resp.json()] == ["SQM"]
