"""P1-6 guardrail (data-quality plan): the EFTS deep-history backfill service.

Pins: query-less windowing since 2001; EftsHit → NOT-NULL-safe filing dict; 10-K/10-Q amendments
(/A) kept and unknown/legacy forms excluded (matching the display form set); a foreign issuer's
20-F/40-F, without their amendments, walked in the same query only behind ENABLE_FPI_FILINGS, by
every process that runs the walk, and walked again once for a foreign issuer stamped before;
accession dedupe across windows; the company stamped only when a window succeeded; the 5xx retry
bounded at 3; a per-window failure tolerated without losing the other windows' rows.
"""
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integrations.sec_api import EftsHit, EftsSearchResult, SECFullTextSearchClient
from app.models import Base, Company, Filing
from app.services import filing_history_service as fh
from app.services.edgar.config import FilingType
from app.services.filing_list_service import CompanyIdentity
from app.services.latest_filing_service import company_list_forms
from app.utils.sec_urls import build_sec_archive_url

REPO = Path(__file__).resolve().parents[3]


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
# The live list reads SEC's recent submissions window, the greater of about a year or about 1,000
# filings, so a foreign issuer's annual reports older than that window reach its company page only
# through the history walk.

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
    ``sent`` as sent, and answered with the ``filings`` of a requested form filed in its window. An
    amendment is answered under its root form too, as the P1-6 live walk saw (it dropped seven /A
    hits), so the walk's own filter must drop what it does not keep."""

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.query.decode())
        params = request.url.params
        hits = [
            {"_id": f"{accession}:doc.htm", "_source": {
                "file_type": form, "file_date": filed, "period_ending": period,
                "ciks": [FPI_CIK], "display_names": [f"Test Co (TCO) (CIK {FPI_CIK})"],
            }}
            for accession, form, filed, period in filings
            if {form, form.removesuffix("/A")} & set(params["forms"].split(","))
            and params["startdt"] <= filed <= params["enddt"]
        ]
        return httpx.Response(200, json={"hits": {"total": {"value": len(hits)}, "hits": hits}})

    return SECFullTextSearchClient(transport=httpx.MockTransport(respond))


@pytest.mark.asyncio
@pytest.mark.parametrize("fpi, forms, stored", [
    (False, "10-K%2C10-K%2FA%2C10-Q%2C10-Q%2FA", ["10-K", "10-Q"]),
    (True, "10-K%2C10-K%2FA%2C10-Q%2C10-Q%2FA%2C20-F%2C40-F", ["40-F", "40-F", "10-K", "10-Q"]),
], ids=["fpi-off", "fpi-on"])
async def test_walk_sends_one_query_per_window_whatever_the_flag(monkeypatch, fpi, forms, stored):
    """One EFTS request per window with the flag on or off: the foreign annual reports join the same
    query, so they cost no request, and a domestic filer's hits are unchanged. With the flag off the
    queries and the stored rows are byte for byte those of the walk before FPI forms were added; with
    it on the 40-F/A that EFTS lists under its root form is dropped, as the company list drops it."""
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
    assert stats["forms"] == unquote(forms)  # the log line names the forms walked, so a flagless walk shows
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
    ("20-F", True), ("40-F", True), ("20-F/A", False), ("40-F/A", False), ("6-K", False), ("6-K/A", False),
])
def test_hit_to_filing_dict_keeps_fpi_annual_reports_only_behind_the_flag(monkeypatch, form, kept_with_fpi):
    """With the flag off a foreign form's hit is dropped, as before; with it on the 20-F and 40-F are
    kept, and their amendments and the 6-K group (a high-volume interim form) stay out, as the
    company list leaves them out."""
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
    ENABLE_FPI_FILINGS state, and the walk queries and keeps no other form. The walk only reaches
    what SEC's recent window no longer holds, so a list form it skips loses its older reports for
    good once the company is stamped, and a form it adds stores rows no list serves. This holds the
    form sets in one process; that every process running the walk has the service's flag is
    test_every_process_that_walks_history_carries_the_services_fpi_flag."""
    monkeypatch.setattr(fh.settings, "ENABLE_FPI_FILINGS", fpi)
    monkeypatch.setattr(fh.settings, "HISTORY_BACKFILL_SINCE_YEAR", 2024)
    fake = _FakeEfts({})

    await fh._fetch_history_rows(cik=FPI_CIK, ticker="TCO", efts_client=fake)

    walked = {form for call in fake.calls for form in call["forms"].split(",")}
    reports = {
        form for form in company_list_forms(fpi=fpi) if not FilingType.from_string(form, strict=False).is_interim
    }
    assert walked == reports
    assert {form.value for form in FilingType if fh._hit_to_filing_dict(_hit("acc", form.value))} == walked


# ---- The deploy's one-time re-walk of the companies the 10-K/10-Q-only walk stamped ----
REWALK_MIGRATION = REPO / "backend/migrations/20261023_rewalk_foreign_issuer_history.sql"


def test_migration_clears_the_stamp_of_each_foreign_issuer_the_old_walk_stamped():
    """The old walk listed 10-K/10-Q only and stamped every company it walked, and a visit never walks
    a stamped company again. The migration clears the stamp of each stamped company that holds a 20-F,
    40-F or 6-K row, original or amendment (a foreign issuer, or one now filing 10-K/10-Q whose older
    40-F the old walk skipped), or holds no row at all, so its next visit walks it with the foreign
    forms. A company holding only 10-K/10-Q rows or other forms keeps its stamp, an unstamped one
    stays unstamped, and a second run changes nothing more."""
    db = _engine_session()
    stamp = datetime(2026, 9, 1, tzinfo=timezone.utc)
    held = {
        "FPI": ["6-K", "20-F"], "CAN": ["40-F/A"], "BARE": [], "DOM": ["10-K", "8-K"],
        "AMND": ["10-Q/A"], "SWCH": ["40-F", "10-K"], "8K": ["8-K"], "NEW": ["20-F"],
    }
    companies = {
        ticker: Company(cik=f"{n:010d}", ticker=ticker, name=ticker, history_backfilled_at=stamp)
        for n, ticker in enumerate(held, start=1)
    }
    companies["NEW"].history_backfilled_at = None
    db.add_all(companies.values())
    db.commit()
    for n, (ticker, form) in enumerate((t, f) for t, forms in held.items() for f in forms):
        cik, accession = companies[ticker].cik, f"{companies[ticker].cik}-26-{n:06d}"
        sec_url = build_sec_archive_url(cik, accession)
        db.add(Filing(
            company_id=companies[ticker].id, accession_number=accession, filing_type=form,
            filing_date=datetime(2026, 3, 1, tzinfo=timezone.utc), sec_url=sec_url,
            document_url=sec_url + "doc.htm",
        ))
    db.commit()
    script = REWALK_MIGRATION.read_text()
    # It bounds its PostgreSQL session as the recent migrations do; SQLite runs the UPDATE alone.
    assert "SET lock_timeout" in script and "SET statement_timeout" in script
    update = "\n".join(
        line for line in script.splitlines()
        if not line.startswith(("SET lock_timeout", "SET statement_timeout", "RESET "))
    )

    def migrate() -> dict[str, bool]:
        raw = db.get_bind().raw_connection()
        try:
            raw.driver_connection.executescript(update)
        finally:
            raw.close()
        db.expire_all()
        return {ticker: CompanyIdentity.of(company).needs_history_backfill for ticker, company in companies.items()}

    walked_again = {
        "FPI": True, "CAN": True, "BARE": True, "DOM": False,
        "AMND": False, "SWCH": True, "8K": False, "NEW": True,
    }
    assert migrate() == walked_again
    assert migrate() == walked_again
    assert db.get(Company, companies["DOM"].id).history_backfilled_at.replace(tzinfo=timezone.utc) == stamp


def _commands(run: str, marker: str) -> list[str]:
    """The commands of a step's script that contain ``marker``, comments dropped and continuation
    lines joined."""
    script = "\n".join(line for line in run.splitlines() if not line.lstrip().startswith("#"))
    return [command.strip() for command in script.replace("\\\n", " ").splitlines() if marker in command]


def _fpi_flag(command: str) -> str | None:
    """The ENABLE_FPI_FILINGS value a command's ``--update-env-vars`` sets, or None."""
    found = re.search(r"--update-env-vars=(\S+)", command)
    return dict(item.split("=", 1) for item in found.group(1).split(",")).get("ENABLE_FPI_FILINGS") if found else None


def test_every_process_that_walks_history_carries_the_services_fpi_flag():
    """The walk reads ENABLE_FPI_FILINGS in whichever process runs it, and a walk with the flag off
    stamps a foreign issuer without its 20-F/40-F, after which no visit walks it again. Every process
    that runs the walk in production carries the service's value: the API service and the task worker
    (the on-visit walk and the internal endpoint), from their deploy maps, and each Ops jobs-channel
    execution of scripts/backfill_filing_history.py, whose job's own map does not set the flag, from
    its execution's override."""
    workflows = REPO / ".github/workflows"
    deploy = yaml.load((workflows / "ci.yml").read_text(), Loader=yaml.BaseLoader)["jobs"]["deploy-backend"]["steps"]
    ops = yaml.load((workflows / "ops.yml").read_text(), Loader=yaml.BaseLoader)["jobs"]["ops"]["steps"]
    step = {s["name"]: s["run"] for s in deploy + ops if "name" in s and "run" in s}

    service = [_fpi_flag(c) for c in _commands(step["Deploy Cloud Run service"], "--update-env-vars")]
    worker = [_fpi_flag(c) for c in _commands(step["Update configured private task worker"], "--update-env-vars")]
    channel = [
        _fpi_flag(c)
        for c in _commands(step["Trigger filing-history backfill (internal endpoint; jobs-channel fallback)"], "jobs execute")
        if "backfill_filing_history.py" in c
    ]
    assert service == ["true"] and len(worker) == 1 and len(channel) == 2, (service, worker, channel)
    assert worker == service and channel == service * 2, (service, worker, channel)
