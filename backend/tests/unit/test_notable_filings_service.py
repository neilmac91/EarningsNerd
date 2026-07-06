"""Notable-filings service: pure scoring, the EDGAR scan (stubbed EFTS), and the serve path.

Hermetic: the scan is tested with a SimpleNamespace EFTS stub (the `test_earnings_calendar_engine`
pattern) and the serve path against the real (SQLite) engine via create_all — no network.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import notable_filings_service as svc
from app.services.notable_filings_service import (
    MIN_COMPANIES,
    NotableFilingsService,
    base_signal,
    demand_boost,
    effective_score,
    run_scan,
)


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


def test_effective_score_decay():
    assert effective_score(80.0, 0) == 80.0
    assert effective_score(80.0, 3.5) == pytest.approx(40.0)
    assert effective_score(80.0, 7.0) == pytest.approx(20.0)
    # Fresh earnings 8-K beats a 6-day-old bankruptcy — the review's ordering requirement.
    assert effective_score(80.0, 1) > effective_score(95.0, 6)


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

@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_serve_flag_off_returns_empty():
    _clear()
    today = svc.today_eastern()
    for i, t in enumerate(["AAA", "BBB", "CCC"]):
        _seed(t, today - timedelta(days=1), 80 + i)
    db = _new_db()
    try:
        # Default is off; be explicit anyway.
        assert settings.NOTABLE_FILINGS_ENABLED is False
        result = await NotableFilingsService().get_notable_filings(db)
        assert result == {"filings": [], "status": "empty", "timestamp": result["timestamp"]}
    finally:
        db.close()
        _clear()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_serve_window_dedupe_and_ranking(monkeypatch):
    _clear()
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    today = svc.today_eastern()
    # Fresh earnings (decayed 80) must outrank an older bankruptcy (decayed 95).
    _seed("AAPL", today - timedelta(days=1), 80, reason="earnings_results")
    _seed("DOOM", today - timedelta(days=6), 95, reason="bankruptcy")
    # Two MSFT rows → only the better (fresher) one serves.
    _seed("MSFT", today - timedelta(days=1), 55, reason="annual_report")
    _seed("MSFT", today - timedelta(days=5), 55, reason="annual_report", accession="msft-old")
    # Outside the 7-day window → invisible even though unpruned.
    _seed("STALE", today - timedelta(days=10), 95)

    db = _new_db()
    try:
        result = await NotableFilingsService().get_notable_filings(db)
        assert result["status"] == "ok"
        tickers = [f["ticker"] for f in result["filings"]]
        assert tickers == ["AAPL", "MSFT", "DOOM"]
        by_ticker = {f["ticker"]: f for f in result["filings"]}
        assert by_ticker["AAPL"]["reason_label"] == "Earnings results"
        assert by_ticker["MSFT"]["filed_date"] == (today - timedelta(days=1)).isoformat()
    finally:
        db.close()
        _clear()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_serve_below_min_companies_is_empty(monkeypatch):
    _clear()
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    today = svc.today_eastern()
    for t in ["AAA", "BBB"][: MIN_COMPANIES - 1]:
        _seed(t, today - timedelta(days=1), 80)

    db = _new_db()
    try:
        result = await NotableFilingsService().get_notable_filings(db)
        assert result["status"] == "empty"
        assert result["filings"] == []
    finally:
        db.close()
        _clear()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_serve_limit_slices_full_ranked_list(monkeypatch):
    _clear()
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    today = svc.today_eastern()
    for i in range(5):
        _seed(f"TK{i}", today - timedelta(days=1), 50 + i)

    db = _new_db()
    try:
        service = NotableFilingsService()
        top2 = await service.get_notable_filings(db, limit=2)
        assert [f["ticker"] for f in top2["filings"]] == ["TK4", "TK3"]
        # Same cache window, larger limit → full list (cache holds the unsliced ranking).
        top5 = await service.get_notable_filings(db, limit=5)
        assert len(top5["filings"]) == 5
    finally:
        db.close()
        _clear()


@pytest.mark.asyncio
async def test_serve_never_raises_on_query_error(monkeypatch):
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)

    class _BrokenDB:
        def query(self, *args, **kwargs):
            raise RuntimeError("db down")

    result = await NotableFilingsService().get_notable_filings(_BrokenDB())
    assert result["status"] == "empty"
    assert result["filings"] == []
