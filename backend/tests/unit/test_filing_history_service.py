"""P1-6 guardrail (data-quality plan): the EFTS deep-history backfill service.

Pins: query-less windowing since 2001; EftsHit → NOT-NULL-safe filing dict; amendments (/A) kept
and unknown/legacy forms excluded (matching the display form set); a foreign issuer's 20-F/40-F
walked in the same query only behind ENABLE_FPI_FILINGS; accession dedupe across windows; the
company stamped only when a window succeeded; the 5xx retry bounded at 3; a per-window failure
tolerated without losing the other windows' rows.
"""
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integrations.sec_api import EftsHit, EftsSearchResult, SECFullTextSearchClient
from app.models import Base, Company, Filing
from app.services import filing_history_service as fh
from app.services.edgar.config import FilingType
from app.services.latest_filing_service import company_list_forms


def _engine_session():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)()


def _hit(accession, form, filed="2020-02-14", period="2019-12-31", doc="a.htm"):
    return EftsHit(
        accession_no=accession, form=form, filed_date=filed, period_ending=period,
        cik="0000019617", company="JPM", ticker="JPM", document=doc,
        sec_url="https://www.sec.gov/Archives/edgar/data/19617/000001961720000001/",
        document_url="https://www.sec.gov/Archives/edgar/data/19617/000001961720000001/" + doc, items=[],
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
        "sec_url": "https://www.sec.gov/Archives/edgar/data/19617/000001961720000001/",
        "document_url": "https://www.sec.gov/Archives/edgar/data/19617/000001961720000001/a.htm",
    }
    # dashed accession is preserved verbatim (the upsert key is the dashed form).
    assert d["accession_number"] == "0000019617-20-000012"


@pytest.mark.parametrize("form", ["10-K405", "NT 10-K", "8-K", None])
def test_hit_to_filing_dict_drops_other_forms(form):
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

    assert stats["inserted"] == 4  # amendment retained + shared accession deduped across windows
    assert company.history_backfilled_at is not None
    assert db.query(Filing).filter(Filing.company_id == company.id).count() == 4
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


@pytest.mark.asyncio
async def test_backfill_all_windows_fail_does_not_stamp(monkeypatch):
    """Every window failing must leave the company UN-stamped so the next visit re-walks it (rather
    than marking it 'done' with no data)."""
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2020)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_WINDOW_YEARS", 4)
    db = _engine_session()
    company = Company(cik="0000019617", ticker="JPM", name="JPM")
    db.add(company)
    db.commit()

    class _AllFail:
        async def search(self, **kw):
            raise RuntimeError("EFTS 503")

    stats = await fh.backfill_company(db, company, efts_client=_AllFail())
    assert stats["windows_ok"] == 0
    assert stats["inserted"] == 0
    assert company.history_backfilled_at is None
    assert db.query(Filing).filter(Filing.company_id == company.id).count() == 0


# ---- Foreign private issuers: 20-F and 40-F annual reports behind ENABLE_FPI_FILINGS ----
# SEC's recent submissions window holds about a year (or about 1,000 filings), only weeks for an
# issuer that furnishes a 6-K most business days, so the live list never reaches its older annual
# reports; the history walk is the path that does.

FPI_CIK = "0000313807"
# A switcher: a Canadian issuer on 40-F through 2019, then a domestic 10-K/10-Q filer, with the 6-Ks
# it furnished as a foreign issuer. (accession, form, filed, period ending)
_SWITCHER = [
    ("0000313807-18-000001", "40-F", "2018-03-01", "2017-12-31"),
    ("0000313807-18-000002", "40-F/A", "2018-06-01", "2017-12-31"),
    ("0000313807-19-000003", "6-K", "2019-05-01", None),
    ("0000313807-19-000004", "40-F", "2019-03-01", "2018-12-31"),
    ("0000313807-21-000005", "10-K", "2021-02-20", "2020-12-31"),
    ("0000313807-21-000006", "10-Q", "2021-05-01", "2021-03-31"),
]


def _efts_client(filings, sent):
    """The real EFTS client over a fake transport. Each request's query string is recorded in
    ``sent`` as sent, and answered with the ``filings`` of a requested form filed in its window."""

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.query.decode())
        params = request.url.params
        hits = [
            {"_id": f"{accession}:doc.htm", "_source": {
                "file_type": form, "file_date": filed, "period_ending": period,
                "ciks": [FPI_CIK], "display_names": [f"Test Co (TCO) (CIK {FPI_CIK})"],
            }}
            for accession, form, filed, period in filings
            if form in params["forms"].split(",") and params["startdt"] <= filed <= params["enddt"]
        ]
        return httpx.Response(200, json={"hits": {"total": {"value": len(hits)}, "hits": hits}})

    return SECFullTextSearchClient(transport=httpx.MockTransport(respond))


@pytest.mark.asyncio
@pytest.mark.parametrize("fpi, forms, stored", [
    (False, "10-K%2C10-K%2FA%2C10-Q%2C10-Q%2FA", ["10-K", "10-Q"]),
    (True, "10-K%2C10-K%2FA%2C10-Q%2C10-Q%2FA%2C20-F%2C20-F%2FA%2C40-F%2C40-F%2FA",
     ["40-F", "40-F/A", "40-F", "10-K", "10-Q"]),
], ids=["fpi-off", "fpi-on"])
async def test_walk_sends_one_query_per_window_whatever_the_flag(monkeypatch, fpi, forms, stored):
    """One EFTS request per window with the flag on or off: the foreign annual reports join the same
    query, so they cost no request, and a domestic filer's hits are unchanged. With the flag off the
    queries and the stored rows are byte for byte those of the walk before FPI forms were added."""
    monkeypatch.setattr(fh.settings, "ENABLE_FPI_FILINGS", fpi)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2017)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_WINDOW_YEARS", 4)
    monkeypatch.setattr(fh, "utcnow", lambda: datetime(2026, 7, 8, tzinfo=timezone.utc))
    db = _engine_session()
    company = Company(cik=FPI_CIK, ticker="TCO", name="Test Co")
    db.add(company)
    db.commit()
    sent = []

    stats = await fh.backfill_company(db, company, efts_client=_efts_client(_SWITCHER, sent))

    windows = [("2017-01-01", "2020-12-31"), ("2021-01-01", "2024-12-31"), ("2025-01-01", "2026-07-08")]
    assert sent == [f"forms={forms}&startdt={start}&enddt={end}&ciks={FPI_CIK}" for start, end in windows]
    assert stats["windows"] == stats["windows_ok"] == 3
    rows = db.query(Filing).filter(Filing.company_id == company.id).order_by(Filing.accession_number).all()
    assert [row.filing_type for row in rows] == stored
    base = "https://www.sec.gov/Archives/edgar/data/313807/"
    for row in rows:
        accession, form, filed, period = next(f for f in _SWITCHER if f[0] == row.accession_number)
        assert row.sec_url == base + accession.replace("-", "") + "/"
        assert row.document_url == row.sec_url + "doc.htm"
        assert row.filing_date.date().isoformat() == filed
        assert row.period_end_date.date().isoformat() == period


@pytest.mark.parametrize("form, kept_with_fpi", [
    ("20-F", True), ("20-F/A", True), ("40-F", True), ("40-F/A", True), ("6-K", False), ("6-K/A", False),
])
def test_hit_to_filing_dict_keeps_fpi_annual_reports_only_behind_the_flag(monkeypatch, form, kept_with_fpi):
    """With the flag off a foreign form's hit is dropped, as before; with it on the annual reports
    and their amendments are kept, and the 6-K group stays out (a high-volume interim form)."""
    monkeypatch.setattr(fh.settings, "ENABLE_FPI_FILINGS", False)
    assert fh._hit_to_filing_dict(_hit("acc", form)) is None
    monkeypatch.setattr(fh.settings, "ENABLE_FPI_FILINGS", True)
    kept = fh._hit_to_filing_dict(_hit("acc", form))
    assert (kept is not None and kept["filing_type"] == form) is kept_with_fpi


@pytest.mark.asyncio
@pytest.mark.parametrize("fpi", [False, True], ids=["fpi-off", "fpi-on"])
async def test_backfill_walks_every_report_form_the_company_list_serves(monkeypatch, fpi):
    """Rule 12 gate: every form the company list serves by default, the 6-K group (FilingType
    .is_interim) aside, is a form the history walk queries and keeps under the same
    ENABLE_FPI_FILINGS state, with its amendment; the walk queries no other form. The walk only
    reaches what SEC's recent window no longer holds, so a list form it skips loses its older
    reports for good once the company is stamped."""
    monkeypatch.setattr(fh.settings, "ENABLE_FPI_FILINGS", fpi)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2024)
    fake = _FakeEfts({})

    await fh._fetch_history_rows(cik=FPI_CIK, ticker="TCO", efts_client=fake)

    walked = {form for call in fake.calls for form in call["forms"].split(",")}
    reports = {
        form.removesuffix("/A") for form in company_list_forms(fpi=fpi)
        if not FilingType.from_string(form, strict=False).is_interim
    }
    assert walked == reports | {f"{form}/A" for form in reports}
    assert all(fh._hit_to_filing_dict(_hit("acc", form)) for form in walked)
