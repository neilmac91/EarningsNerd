"""Notable-filings service: pure scoring, the EDGAR scan (stubbed EFTS), and the serve path.

Hermetic: the scan is tested with a SimpleNamespace EFTS stub (the `test_earnings_calendar_engine`
pattern) against the real (SQLite) engine via create_all, and the serve path against a private
in-memory SQLite database per test, so the companies, filings and summaries a case seeds meet no
other test's rows. No network.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.models import Company, Filing, NotableFiling, Summary
from app.services import notable_filings_service as svc
from app.services.notable_filings_service import (
    MAX_FILINGS,
    MIN_COMPANIES,
    SERVE_WINDOW_DAYS,
    NotableFilingsService,
    base_signal,
    demand_boost,
    run_scan,
)
from app.utils.datetimes import utcnow
from app.utils.sec_urls import build_sec_archive_url


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _clear():
    from app.database import SessionLocal
    from app.models import NotableFiling

    db = SessionLocal()
    db.query(NotableFiling).delete(synchronize_session=False)
    db.commit()
    db.close()


def _new_db():
    from app.database import SessionLocal

    return SessionLocal()


def _seed(ticker, filed_date, score, *, reason="earnings_results", form="8-K", accession=None):
    from app.database import SessionLocal
    from app.models import NotableFiling

    db = SessionLocal()
    db.add(NotableFiling(
        accession_number=accession or f"{ticker}-{filed_date.isoformat()}-{score}",
        ticker=ticker.upper(),
        company_name=f"{ticker} Inc",
        form=form,
        reason=reason,
        filed_date=filed_date,
        score=score,
        sec_url=f"https://www.sec.gov/Archives/edgar/data/1/{ticker}/",
    ))
    db.commit()
    db.close()


def _hit(accession, *, form="8-K", items=None, ticker="AAPL", filed=None,
         company="Apple Inc.", sec_url="https://www.sec.gov/Archives/edgar/data/320193/x/"):
    return SimpleNamespace(
        accession_no=accession,
        form=form,
        items=items or [],
        ticker=ticker,
        company=company,
        cik="0000320193",
        filed_date=(filed or date(2026, 7, 6)).isoformat(),
        sec_url=sec_url,
    )


class _EftsStub:
    """Returns canned hits per (query, forms) key; records every call."""

    def __init__(self, hits_by_key=None):
        self.calls = []
        self._hits = hits_by_key or {}

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        key = (kwargs.get("query"), kwargs.get("forms"))
        hits = self._hits.get(key, []) if kwargs.get("from_offset", 0) == 0 else []
        return SimpleNamespace(hits=hits, total=len(self._hits.get(key, [])))


# ---- pure scoring -----------------------------------------------------------

def test_base_signal_weights_and_reasons():
    assert base_signal("8-K", ["2.02", "9.01"]) == (80.0, "earnings_results")
    # Max item wins: a 2.02 + 1.03 filing is a bankruptcy story, not an earnings one.
    assert base_signal("8-K", ["2.02", "1.03"]) == (95.0, "bankruptcy")
    assert base_signal("8-K", ["4.02"]) == (90.0, "restatement")
    assert base_signal("SC 13D", None) == (70.0, "activist_stake")
    assert base_signal("10-K", None) == (55.0, "annual_report")
    assert base_signal("10-Q", None) == (45.0, "quarterly_report")
    assert base_signal("S-1", None) == (40.0, "ipo_filing")


def test_base_signal_drops_noise():
    # Routine 8-K items only → drop.
    assert base_signal("8-K", ["7.01", "8.01", "9.01"]) is None
    assert base_signal("8-K", []) is None
    # Unknown forms and amendments → drop.
    assert base_signal("424B5", None) is None
    assert base_signal("S-1/A", None) is None
    assert base_signal(None, None) is None


def test_base_signal_tolerates_case_and_whitespace():
    assert base_signal(" 10-k ", None) == (55.0, "annual_report")
    assert base_signal("8-K", [" 2.02 "]) == (80.0, "earnings_results")


def test_demand_boost_monotone_and_bounded():
    assert demand_boost(0, 0) == 0.0
    assert demand_boost(10, 0) > demand_boost(1, 0)
    assert demand_boost(0, 10) > demand_boost(0, 1)
    # Demand re-ranks within a tier but can't lift a 10-Q (45) over a bankruptcy (95).
    assert 45.0 + demand_boost(100, 100) < 95.0


# ---- scan -------------------------------------------------------------------

@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_scan_upserts_scores_and_drops(monkeypatch):
    _clear()
    from app.models import NotableFiling

    today = svc.today_eastern()
    hits_by_key = {
        ('"Results of Operations and Financial Condition"', "8-K"): [
            _hit("acc-1", items=["2.02", "9.01"], ticker="AAPL", filed=today),
            _hit("acc-2", items=["7.01"], ticker="ZZZ", filed=today),   # low-signal → drop
            _hit("acc-3", items=["2.02"], ticker="", filed=today),      # no ticker → drop
            _hit("acc-4", items=["2.02"], ticker="NOURL", filed=today, sec_url=None),  # → drop
        ],
        ('"annual report"', "10-K"): [
            _hit("acc-5", form="10-K", ticker="MSFT", filed=today - timedelta(days=1)),
            # Same accession as the 8-K sweep — exhibit-style duplicate → counted once.
            _hit("acc-1", items=["2.02"], ticker="AAPL", filed=today),
        ],
    }
    stub = _EftsStub(hits_by_key)
    db = _new_db()
    try:
        stats = await run_scan(db, efts_client=stub, days=2)
        assert stats.commit_failed is False
        assert stats.upserted_new == 2  # AAPL 8-K + MSFT 10-K
        assert stats.dropped_low_signal == 1
        assert stats.dropped_no_ticker == 1
        assert stats.dropped_no_url == 1
        assert stats.dropped_duplicate >= 1

        rows = {r.accession_number: r for r in db.query(NotableFiling).all()}
        assert set(rows) == {"acc-1", "acc-5"}
        assert rows["acc-1"].reason == "earnings_results"
        assert float(rows["acc-1"].score) == pytest.approx(80.0)
        assert rows["acc-5"].reason == "annual_report"

        # Query-less listing calls (S-1 / SC 13D) never paginate: every call is page 0.
        for call in stub.calls:
            if not call.get("query"):
                assert call.get("from_offset", 0) == 0
    finally:
        db.close()
        _clear()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_scan_rerun_updates_score_preserves_first_seen():
    _clear()
    from app.models import NotableFiling

    today = svc.today_eastern()
    key = ('"Results of Operations and Financial Condition"', "8-K")
    stub = _EftsStub({key: [_hit("acc-1", items=["2.02"], ticker="AAPL", filed=today)]})

    db = _new_db()
    try:
        await run_scan(db, efts_client=stub, days=1)
        first = db.query(NotableFiling).one()
        first_seen, last_seen = first.first_seen_at, first.last_seen_at

        stats = await run_scan(db, efts_client=stub, days=1)
        assert stats.upserted_updated == 1
        db.expire_all()
        again = db.query(NotableFiling).one()
        assert again.first_seen_at == first_seen
        assert again.last_seen_at >= last_seen
    finally:
        db.close()
        _clear()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_scan_prunes_old_rows():
    _clear()
    today = svc.today_eastern()
    _seed("OLD", today - timedelta(days=20), 80)
    _seed("KEEP", today - timedelta(days=3), 80)

    db = _new_db()
    try:
        stats = await run_scan(db, efts_client=_EftsStub(), days=1)
        assert stats.pruned == 1
        from app.models import NotableFiling
        tickers = [r.ticker for r in db.query(NotableFiling).all()]
        assert tickers == ["KEEP"]
    finally:
        db.close()
        _clear()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_scan_commit_failure_rolls_back():
    _clear()
    today = svc.today_eastern()
    key = ('"Results of Operations and Financial Condition"', "8-K")
    stub = _EftsStub({key: [_hit("acc-1", items=["2.02"], ticker="AAPL", filed=today)]})

    db = _new_db()
    try:
        def _boom():
            raise RuntimeError("commit refused")

        db.commit = _boom  # type: ignore[method-assign]
        stats = await run_scan(db, efts_client=stub, days=1)
        assert stats.commit_failed is True
    finally:
        db.close()

    check = _new_db()
    try:
        from app.models import NotableFiling
        assert check.query(NotableFiling).count() == 0
    finally:
        check.close()
        _clear()


# ---- serve ------------------------------------------------------------------
#
# D-046's rule (docs/brand/decisions-log.md, F3): 10-K and 10-Q filings only, from companies that
# hold a summary the filing page shows, newest first, one per company, at most six.

READY = "Revenue rose 6% as services grew."

_REASON_BY_FORM = {
    "10-K": "annual_report", "10-Q": "quarterly_report", "8-K": "earnings_results",
    "S-1": "ipo_filing", "SC 13D": "activist_stake",
}


@pytest.fixture
def serve_db():
    """A private in-memory database for one serve case."""
    from app.models import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)


_OWN_CIK = object()


def _cik(ticker):
    """The CIK this file gives a ticker's issuer, built from its letters' code points, so a candidate
    and its stored company agree unless a case gives one of them another."""
    return "".join(str(ord(c)) for c in ticker).zfill(10)


def _candidate(db, ticker, days_ago, *, form="10-K", score=50.0, cik=_OWN_CIK):
    """A stored EDGAR candidate as the scan writes one, with no ingested filing behind it."""
    db.add(NotableFiling(
        accession_number=f"{ticker}-{form}-{days_ago}",
        ticker=ticker,
        cik=_cik(ticker) if cik is _OWN_CIK else cik,
        company_name=f"{ticker} Inc",
        form=form,
        reason=_REASON_BY_FORM[form],
        filed_date=svc.today_eastern() - timedelta(days=days_ago),
        score=score,
        sec_url=f"https://www.sec.gov/Archives/edgar/data/1/{ticker}/",
    ))
    db.commit()


def _company(db, ticker, *filings, cik=None):
    """A stored company with one filing per entry: a ``(body, raw_summary)`` pair for a filing with
    that summary, or ``None`` for a filing with none. Its CIK is the ticker's own unless given."""
    cik = cik or _cik(ticker)
    company = Company(cik=cik, ticker=ticker, name=f"{ticker} Inc")
    db.add(company)
    db.flush()
    for i, summary in enumerate(filings):
        accession = f"{cik.zfill(10)}-26-{i:06d}"
        url = build_sec_archive_url(cik, accession)
        filing = Filing(company_id=company.id, accession_number=accession, filing_type="10-K",
                        filing_date=utcnow(), sec_url=url, document_url=f"{url}doc.htm")
        db.add(filing)
        db.flush()
        if summary is not None:
            body, raw_summary = summary
            db.add(Summary(filing_id=filing.id, business_overview=body, raw_summary=raw_summary))
    db.commit()


def _ready(db, *tickers):
    """Companies that each hold one summary the filing page shows."""
    for ticker in tickers:
        _company(db, ticker, (READY, None))


def _served(db, **kwargs):
    return [(f["ticker"], f["form"]) for f in NotableFilingsService().get_notable_filings(db, **kwargs)["filings"]]


def test_serve_flag_off_returns_empty(serve_db):
    _ready(serve_db, "AAA", "BBB", "CCC")
    for days_ago, ticker in enumerate(("AAA", "BBB", "CCC"), start=1):
        _candidate(serve_db, ticker, days_ago)
    # Default is off; be explicit anyway.
    assert settings.NOTABLE_FILINGS_ENABLED is False
    result = NotableFilingsService().get_notable_filings(serve_db)
    assert result == {"filings": [], "status": "empty", "timestamp": result["timestamp"]}


def test_serve_drops_every_form_but_10k_and_10q(serve_db, enabled):
    """An 8-K, an S-1 and an SC 13D are dropped though each company holds a summary to open, and a
    newer one does not hide its company's 10-Q or 10-K: the form filter runs before the
    one-per-company pick."""
    _ready(serve_db, "AAA", "BBB", "CCC", "DDD")
    _candidate(serve_db, "AAA", 1, form="8-K", score=95.0)
    _candidate(serve_db, "BBB", 1, form="S-1")
    _candidate(serve_db, "CCC", 1, form="SC 13D")
    _candidate(serve_db, "AAA", 2, form="10-Q")
    _candidate(serve_db, "BBB", 3, form="10-K")
    _candidate(serve_db, "DDD", 4, form="10-Q")
    assert _served(serve_db) == [("AAA", "10-Q"), ("BBB", "10-K"), ("DDD", "10-Q")]


@pytest.mark.parametrize("held", [
    pytest.param(None, id="no stored company"),
    pytest.param((None,), id="a filing with no summary"),
    pytest.param((("Generating summary...", None),), id="the in-progress marker"),
    pytest.param((("## Executive Summary\n\nSummary temporarily unavailable. Please retry.", None),),
                 id="failure filler"),
    pytest.param(((READY, {"writer_error": "timeout"}),), id="a writer error"),
    pytest.param((("   ", None),), id="an empty body"),
])
def test_serve_drops_a_company_with_no_summary_the_page_shows(serve_db, enabled, held):
    """The window's newest 10-K is dropped when its company holds no summary, or only one the filing
    page would not show (summary_placeholders.is_summary_ready)."""
    if held is not None:
        _company(serve_db, "NOPE", *held)
    _candidate(serve_db, "NOPE", 0, form="10-K")
    _ready(serve_db, "AAA", "BBB", "CCC")
    for days_ago, ticker in enumerate(("AAA", "BBB", "CCC"), start=1):
        _candidate(serve_db, ticker, days_ago, form="10-Q")
    assert _served(serve_db) == [("AAA", "10-Q"), ("BBB", "10-Q"), ("CCC", "10-Q")]


def test_serve_counts_a_ready_summary_of_any_filing(serve_db, enabled):
    """A candidate is an EDGAR row, not an ingested filing: a 10-Q is served when its company holds a
    summary the page shows of another filing, here beside a filing with none and one mid-run. Prose
    about generating summaries is a summary, since the in-progress marker is case-sensitive."""
    _company(serve_db, "AAA", None, ("Generating summary...", None), (READY, None))
    _company(serve_db, "BBB", ("Management reworked its revenue-generating summary reports.", None))
    _ready(serve_db, "CCC")
    _candidate(serve_db, "AAA", 1, form="10-Q")
    _candidate(serve_db, "BBB", 2, form="10-Q")
    _candidate(serve_db, "CCC", 3, form="10-K")
    assert _served(serve_db) == [("AAA", "10-Q"), ("BBB", "10-Q"), ("CCC", "10-K")]


@pytest.mark.parametrize("case", [
    pytest.param("reused", id="an older issuer holds the ticker"),
    pytest.param("moved", id="its issuer is stored under another ticker"),
    pytest.param("no cik", id="the scan stored no CIK"),
])
def test_serve_matches_a_candidate_to_its_own_issuer(serve_db, enabled, case):
    """The test is at the candidate's issuer, the stored company holding its CIK, which must carry
    its ticker too. A reused ticker's older issuer lends no summary (``Company.ticker`` is not
    unique); an issuer stored under another ticker is not the company the card opens; a candidate
    with no CIK has no issuer to test."""
    if case == "reused":
        _company(serve_db, "NEW", (READY, None), cik="0000000777")
        _company(serve_db, "NEW", None)
        _candidate(serve_db, "NEW", 0)
    elif case == "moved":
        _company(serve_db, "WAS", (READY, None), cik=_cik("NEW"))
        _candidate(serve_db, "NEW", 0)
    else:
        _ready(serve_db, "NEW")
        _candidate(serve_db, "NEW", 0, cik=None)
    _ready(serve_db, "AAA", "BBB", "CCC")
    for days_ago, ticker in enumerate(("AAA", "BBB", "CCC"), start=1):
        _candidate(serve_db, ticker, days_ago, form="10-Q")
    assert _served(serve_db) == [("AAA", "10-Q"), ("BBB", "10-Q"), ("CCC", "10-Q")]


def test_serve_matches_a_cik_in_either_spelling(serve_db, enabled):
    """A CIK matches zero-padded or stripped, on the candidate or the stored company, as
    ``company_resolution`` matches one."""
    _company(serve_db, "AAA", (READY, None), cik=_cik("AAA").lstrip("0"))
    _ready(serve_db, "BBB", "CCC")
    _candidate(serve_db, "AAA", 1, form="10-Q")
    _candidate(serve_db, "BBB", 2, form="10-Q", cik=_cik("BBB").lstrip("0"))
    _candidate(serve_db, "CCC", 3, form="10-K")
    assert _served(serve_db) == [("AAA", "10-Q"), ("BBB", "10-Q"), ("CCC", "10-K")]


def test_serve_orders_newest_first_with_the_score_breaking_a_tie(serve_db, enabled):
    """Newest first whatever the score; on one day the higher stored score leads. A company's newest
    row stands for it, and a row outside the window is not served."""
    _ready(serve_db, "AAA", "BBB", "CCC", "DDD", "OLD")
    _candidate(serve_db, "DDD", 5, form="10-K", score=90.0)
    _candidate(serve_db, "BBB", 3, form="10-K", score=55.0)
    _candidate(serve_db, "AAA", 1, form="10-Q", score=45.0)
    _candidate(serve_db, "CCC", 1, form="10-Q", score=60.0)
    _candidate(serve_db, "BBB", 2, form="10-Q", score=45.0)
    _candidate(serve_db, "OLD", SERVE_WINDOW_DAYS + 3, form="10-K", score=99.0)
    assert _served(serve_db) == [("CCC", "10-Q"), ("AAA", "10-Q"), ("BBB", "10-Q"), ("DDD", "10-K")]


def test_serve_caps_at_six_and_slices_within_the_cap(serve_db, enabled):
    """At most six however large ``limit`` is, read in two queries for the whole window; within one
    cache window a small and a large ``limit`` each get their own slice of the same list."""
    assert MAX_FILINGS == 6
    tickers = [f"TK{i}" for i in range(MAX_FILINGS + 2)]
    _ready(serve_db, *tickers)
    for days_ago, ticker in enumerate(tickers):
        _candidate(serve_db, ticker, days_ago, form="10-Q")
    statements = []
    event.listen(serve_db.get_bind(), "before_cursor_execute", lambda *args: statements.append(args[2]))
    service = NotableFilingsService()
    top2 = service.get_notable_filings(serve_db, limit=2)
    assert [f["ticker"] for f in top2["filings"]] == ["TK0", "TK1"]
    widest = service.get_notable_filings(serve_db, limit=12)
    assert [f["ticker"] for f in widest["filings"]] == tickers[:MAX_FILINGS]
    assert len(statements) == 2, statements


def test_serve_below_min_companies_is_empty(serve_db, enabled):
    tickers = ["AAA", "BBB"][: MIN_COMPANIES - 1]
    _ready(serve_db, *tickers)
    for days_ago, ticker in enumerate(tickers, start=1):
        _candidate(serve_db, ticker, days_ago)
    result = NotableFilingsService().get_notable_filings(serve_db)
    assert result["status"] == "empty"
    assert result["filings"] == []


def test_serve_never_raises_on_query_error(enabled):
    class _BrokenDB:
        def query(self, *args, **kwargs):
            raise RuntimeError("db down")

    result = NotableFilingsService().get_notable_filings(_BrokenDB())
    assert result["status"] == "empty"
    assert result["filings"] == []
