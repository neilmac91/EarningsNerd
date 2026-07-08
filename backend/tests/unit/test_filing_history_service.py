"""P1-6 guardrail (data-quality plan): the EFTS deep-history backfill service.

Pins: query-less windowing since 2001; EftsHit → NOT-NULL-safe filing dict; amendments (/A) and
unknown/legacy forms excluded (matching the display form set); accession dedupe across windows;
the company stamped only when a window succeeded; the 5xx retry bounded at 3; a per-window failure
tolerated without losing the other windows' rows.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integrations.sec_api import EftsHit, EftsSearchResult
from app.models import Base, Company, Filing
from app.services import filing_history_service as fh


def _engine_session():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)()


def _hit(accession, form, filed="2020-02-14", period="2019-12-31", doc="a.htm"):
    return EftsHit(
        accession_no=accession, form=form, filed_date=filed, period_ending=period,
        cik="0000019617", company="JPM", ticker="JPM", document=doc,
        sec_url="https://www.sec.gov/Archives/edgar/data/19617/x/",
        document_url="https://www.sec.gov/Archives/edgar/data/19617/x/" + doc, items=[],
    )


class _FakeEfts:
    """Returns a canned page-0 result per (start,end) window; records the calls it received."""

    def __init__(self, by_window):
        self.by_window = by_window
        self.calls = []

    async def search(self, *, query=None, forms=None, start_date=None, end_date=None, ciks=None, from_offset=0):
        self.calls.append({"forms": forms, "ciks": ciks, "start": start_date, "end": end_date, "from": from_offset})
        hits = self.by_window.get(start_date, [])
        return EftsSearchResult(query=query, total=len(hits), hits=hits)


def test_windows_cover_since_year_to_today():
    w = fh._windows(2001, datetime(2026, 7, 8), 8)
    assert w[0][0] == "2001-01-01"
    assert w[-1][1] == "2026-07-08"  # last window ends today, not year-end
    # contiguous, non-overlapping
    for (_, end), (start, _s) in zip(w, w[1:]):
        assert datetime.fromisoformat(start).year == datetime.fromisoformat(end).year + 1


def test_hit_to_filing_dict_keeps_clean_reports():
    d = fh._hit_to_filing_dict(_hit("0000019617-20-000012", "10-K"))
    assert d == {
        "accession_number": "0000019617-20-000012", "filing_type": "10-K",
        "filing_date": "2020-02-14", "report_date": "2019-12-31",
        "sec_url": "https://www.sec.gov/Archives/edgar/data/19617/x/",
        "document_url": "https://www.sec.gov/Archives/edgar/data/19617/x/a.htm",
    }
    # dashed accession is preserved verbatim (the upsert key is the dashed form).
    assert d["accession_number"] == "0000019617-20-000012"


@pytest.mark.parametrize("form", ["10-K/A", "10-Q/A", "10-K405", "NT 10-K", "8-K", None])
def test_hit_to_filing_dict_drops_amendments_and_other_forms(form):
    assert fh._hit_to_filing_dict(_hit("acc", form)) is None


@pytest.mark.parametrize("missing", ["sec_url", "document_url", "accession_no", "filed_date"])
def test_hit_to_filing_dict_drops_rows_missing_not_null_fields(missing):
    h = _hit("acc", "10-K")
    setattr(h, missing, None)
    assert fh._hit_to_filing_dict(h) is None


@pytest.mark.asyncio
async def test_backfill_company_inserts_dedupes_and_stamps(monkeypatch):
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2018)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_WINDOW_YEARS", 4)
    db = _engine_session()
    company = Company(cik="0000019617", ticker="JPM", name="JPMorgan Chase & Co")
    db.add(company)
    db.commit()

    windows = fh._windows(2018, fh.utcnow(), 4)
    shared = _hit("0000019617-19-000010", "10-K")  # appears in TWO windows → dedupe
    fake = _FakeEfts({
        windows[0][0]: [_hit("0000019617-18-000001", "10-K"), shared, _hit("acc-amend", "10-K/A")],
        windows[1][0]: [shared, _hit("0000019617-23-000003", "10-Q")],
    })

    stats = await fh.backfill_company(db, company, efts_client=fake)

    assert stats["inserted"] == 3  # two uniques in w0 (amendment dropped) + one new in w1; shared deduped
    assert company.history_backfilled_at is not None
    assert db.query(Filing).filter(Filing.company_id == company.id).count() == 3
    # every request carried the company CIK and no from-offset (query-less page-0 only)
    assert all(c["ciks"] == "0000019617" and c["from"] == 0 for c in fake.calls)


@pytest.mark.asyncio
async def test_backfill_tolerates_a_window_failure_but_still_stamps(monkeypatch):
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2018)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_WINDOW_YEARS", 4)
    db = _engine_session()
    company = Company(cik="0000019617", ticker="JPM", name="JPM")
    db.add(company)
    db.commit()
    windows = fh._windows(2018, fh.utcnow(), 4)

    class _PartlyFailing(_FakeEfts):
        async def search(self, *, start_date=None, **kw):
            if start_date == windows[0][0]:
                raise RuntimeError("EFTS 503")
            return await super().search(start_date=start_date, **kw)

    fake = _PartlyFailing({windows[1][0]: [_hit("0000019617-23-000003", "10-Q")]})
    stats = await fh.backfill_company(db, company, efts_client=fake)
    assert stats["windows_ok"] == len(windows) - 1
    assert stats["inserted"] == 1
    assert company.history_backfilled_at is not None  # one window succeeded → stamped


@pytest.mark.asyncio
async def test_search_retry_is_bounded_at_three():
    attempts = {"n": 0}

    class _AlwaysFails:
        async def search(self, **kw):
            attempts["n"] += 1
            raise RuntimeError("EFTS 500")

    with pytest.raises(RuntimeError):
        await fh._search_window_with_retry(_AlwaysFails(), forms="10-K", cik="1", start="2020-01-01", end="2020-12-31")
    assert attempts["n"] == fh._BACKFILL_RETRY_ATTEMPTS == 3


@pytest.mark.asyncio
async def test_batch_backfill_respects_explicit_ticker_cohort(monkeypatch):
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2022)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_WINDOW_YEARS", 8)
    db = _engine_session()
    db.add_all([
        Company(cik="0000019617", ticker="JPM", name="JPM"),
        Company(cik="0000070858", ticker="BAC", name="BAC"),
    ])
    db.commit()

    async def fake_backfill(_db, company, **kw):
        company.history_backfilled_at = fh.utcnow()
        return {"ticker": company.ticker, "inserted": 5, "windows": 1, "windows_ok": 1, "hits": 5}

    monkeypatch.setattr(fh, "backfill_company", fake_backfill)
    totals = await fh.batch_backfill(db, tickers=["JPM"])
    assert totals == {"companies": 1, "inserted": 5, "failed": 0}
