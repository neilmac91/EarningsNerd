"""filing_section_service: Item 1A extraction, storage, pairing and the Change Report block.

DB-backed on the suite's SQLite (tables via create_all). The SEC boundary is faked: documents
come from an injected fetcher and, except in the parser tests, an injected parser; nothing here
reaches the network (tests/support/network_gate.py would fail the test). Fixture text is
synthetic; no real filing is quoted.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import Company, Filing, FilingSectionText, Summary, User, Watchlist
from app.services import filing_section_service as svc
from app.services.change_report_service import build_change_report, change_report_for_filing
from app.utils.datetimes import ensure_utc

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
TEASER = svc.SectionAccess(svc.ACCESS_TEASER, 3)

PRIOR_TEXT = (
    "Item 1A. Risk Factors\n\n"
    "We depend on a small number of customers for a large share of our revenue.\n\n"
    "Our products may contain defects that could harm our reputation.\n\n"
    "Changes in tax law could increase our effective tax rate."
)
LATER_TEXT = (
    "Item 1A. Risk Factors\n\n"
    "We depend on a limited number of customers for a large share of our revenue.\n\n"
    "Our products may contain defects that could harm our reputation.\n\n"
    "We face intense competition, and competitors may have greater resources than we do.\n\n"
    "Cyberattacks on our systems could expose confidential information."
)
STUB_TEXT = (
    "Item 1A. Risk Factors\n\n"
    "There have been no material changes to the risk factors described in Part I, Item 1A of our "
    "Annual Report on Form 10-K."
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


_WATCHLIST_ROWS: list[int] = []


@pytest.fixture
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        # The scan suite walks every watched company; this module's watchers must not outlive it.
        session.rollback()
        if _WATCHLIST_ROWS:
            session.query(Watchlist).filter(Watchlist.id.in_(_WATCHLIST_ROWS)).delete(synchronize_session=False)
            session.commit()
            _WATCHLIST_ROWS.clear()
        session.close()


def _company(db, *, watched_by=None):
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:5].upper()}", name=f"Co {suffix}")
    db.add(company)
    db.commit()
    if watched_by is not None:
        row = Watchlist(user_id=watched_by.id, company_id=company.id)
        db.add(row)
        db.commit()
        _WATCHLIST_ROWS.append(row.id)
    return company


def _filing(db, company, form, period, filed, *, suffix=None):
    suffix = suffix or uuid.uuid4().hex[:10]
    filing = Filing(
        company_id=company.id,
        accession_number=f"test-{suffix}",
        filing_type=form,
        filing_date=filed,
        period_end_date=period,
        document_url=f"https://sec.example/{suffix}/doc.htm",
        sec_url=f"https://sec.example/{suffix}/",
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)
    return filing


def _user(db, *, is_pro=False):
    user = User(email=f"sections-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                email_verified=True, is_active=True, is_pro=is_pro)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _pair(db, *, watched_by=None):
    """A company with two 10-Ks (FY2024 filed 2025, FY2025 filed 2026) and a 10-K/A of the later."""
    company = _company(db, watched_by=watched_by)
    prior = _filing(db, company, "10-K", datetime(2024, 12, 31, tzinfo=timezone.utc), datetime(2025, 2, 20, tzinfo=timezone.utc))
    later = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc))
    amendment = _filing(db, company, "10-K/A", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 4, 1, tzinfo=timezone.utc))
    return company, prior, later, amendment


def _fetch(documents):
    """Fake SEC transport: document_url -> 'html' (any string; the fake parser maps it to text)."""
    async def fetch(url):
        return documents[url]
    return fetch


def _parse(texts):
    """Fake parser: the 'html' string is looked up in ``texts`` (None -> missing section)."""
    def parse(html, form):
        text = texts.get(html)
        if text is None:
            return svc.ExtractedSection(status=svc.STATUS_MISSING)
        return svc.ExtractedSection(status=svc.STATUS_OK, text=text, detection_method="toc", confidence=0.95)
    return parse


def _attempt(db, filing, text, *, now=NOW):
    documents = {filing.document_url: f"html-{filing.id}"}
    return asyncio.run(svc.extract_for_filing(
        db, filing, fetch_document=_fetch(documents), parse=_parse({f"html-{filing.id}": text}), now=now,
    ))


def _extract(db, filing, text, *, now=NOW):
    """Store ``text`` as the filing's Item 1A and return its row."""
    return _attempt(db, filing, text, now=now).row


def _missing(db, filing, *, now=NOW):
    """An attempt whose document has no Item 1A."""
    return asyncio.run(svc.extract_for_filing(
        db, filing, fetch_document=_fetch({filing.document_url: "h"}), parse=_parse({}), now=now,
    ))


def _ids(db, **kw):
    kw.setdefault("limit", 100)
    kw.setdefault("now", NOW)
    return [f.id for f in svc.select_filings_for_extraction(db, **kw)]


def _row(db, filing_id):
    return db.query(FilingSectionText).filter(FilingSectionText.filing_id == filing_id).one()


# --- the real parser on synthetic documents ---------------------------------------------------

def _synthetic_10k(risk_paragraphs):
    body = "\n".join(f"<div><p>{p}</p></div>" for p in risk_paragraphs)
    return f"""<html><body>
<p style="font-weight:bold">PART I</p>
<table><tr><td><a href="#i1">Item 1.</a></td><td>Business</td></tr>
<tr><td><a href="#i1a">Item 1A.</a></td><td>Risk Factors</td></tr>
<tr><td><a href="#i1b">Item 1B.</a></td><td>Unresolved Staff Comments</td></tr>
<tr><td><a href="#i2">Item 2.</a></td><td>Properties</td></tr></table>
<p id="i1" style="font-weight:bold">Item 1. Business</p>
<p>Example Holdings makes example widgets for example customers.</p>
<p id="i1a" style="font-weight:bold">Item 1A. Risk Factors</p>
{body}
<p id="i1b" style="font-weight:bold">Item 1B. Unresolved Staff Comments</p>
<p>None.</p>
<p id="i2" style="font-weight:bold">Item 2. Properties</p>
<p>We lease an example office.</p>
</body></html>"""


_SYNTHETIC_10Q = """<html><body><p><b>PART I. FINANCIAL INFORMATION</b></p>
<p><b>Item 1. Financial Statements</b></p><p>Example statements.</p>
<p><b>Item 2. Management's Discussion and Analysis</b></p><p>Example discussion.</p>
<p><b>PART II. OTHER INFORMATION</b></p>
<p><b>Item 1. Legal Proceedings</b></p><p>None.</p>
<p><b>Item 1A. Risk Factors</b></p>
<p>There have been no material changes to the risk factors described in our Annual Report on Form 10-K.</p>
<p><b>Item 2. Unregistered Sales of Equity Securities</b></p><p>None.</p>
<p><b>Item 6. Exhibits</b></p><p>Exhibit list.</p></body></html>"""


def test_parse_item_1a_locates_the_section_in_a_10k_and_a_10q():
    paragraphs = [
        "Our revenue depends on a small number of example customers.",
        "We face intense competition in the example widget market, which could reduce our margins.",
    ]
    result = svc.parse_item_1a(_synthetic_10k(paragraphs), "10-K")
    assert result.status == svc.STATUS_OK
    assert result.text.startswith("Item 1A. Risk Factors")
    for paragraph in paragraphs:
        assert paragraph in result.text
    assert "Unresolved Staff Comments" not in result.text and "example office" not in result.text

    quarterly = svc.parse_item_1a(_SYNTHETIC_10Q, "10-Q")
    assert quarterly.status == svc.STATUS_OK
    assert "no material changes" in quarterly.text
    assert "Exhibit list" not in quarterly.text and "Example discussion" not in quarterly.text
    assert svc.is_reference_only(quarterly.text) is True


def test_parse_item_1a_falls_back_to_any_part_when_the_part_heading_is_missing():
    paragraphs = ["Our revenue depends on a small number of example customers."]
    html = _synthetic_10k(paragraphs).replace('<p style="font-weight:bold">PART I</p>\n', "")
    assert "PART I" not in html
    result = svc.parse_item_1a(html, "10-K")
    assert result.status == svc.STATUS_OK and paragraphs[0] in result.text


def test_parse_item_1a_reports_a_document_without_the_section_as_missing():
    html = "<html><body><p><b>Item 1. Business</b></p><p>Widgets.</p><p><b>Item 2. Properties</b></p><p>An office.</p></body></html>"
    assert svc.parse_item_1a(html, "10-K").status == svc.STATUS_MISSING


def test_reference_only_detection():
    assert svc.is_reference_only(STUB_TEXT) is True
    assert svc.is_reference_only(LATER_TEXT) is False
    assert svc.is_reference_only("x" * 3000 + " no material changes") is False  # a restated section is never short


# --- extraction and the cached summary --------------------------------------------------------

def test_extract_stores_the_text_and_the_summary_against_the_prior(db):
    _, prior, later, _ = _pair(db)
    prior_row = _extract(db, prior, PRIOR_TEXT)
    assert prior_row.status == svc.STATUS_OK and prior_row.extractor_version == svc.EXTRACTOR_VERSION
    assert prior_row.char_count == len(PRIOR_TEXT) and prior_row.paragraph_count == 3  # heading excluded
    assert prior_row.sha256 and prior_row.detection_method == "toc" and prior_row.confidence == 0.95
    assert prior_row.reference_only is False
    assert ensure_utc(prior_row.extracted_at) == NOW and ensure_utc(prior_row.attempted_at) == NOW
    assert prior_row.diff_prior_filing_id is None and prior_row.diff_summary is None
    assert prior_row.diff_engine_version == svc.section_diff.ENGINE_VERSION  # evaluated: no prior exists

    later_row = _extract(db, later, LATER_TEXT)
    assert later_row.diff_prior_filing_id == prior.id
    assert later_row.diff_summary["counts"] == {"unchanged": 1, "modified": 1, "added": 2, "removed": 1, "moved": 0}
    assert later_row.diff_summary["items_total"] == 4 and later_row.diff_summary["has_changes"] is True
    assert later_row.diff_summary["reference_only"] is False and later_row.diff_summary["prior_reference_only"] is False
    assert later_row.diff_computed_at is not None
    assert db.query(FilingSectionText).filter(FilingSectionText.filing_id == later.id).count() == 1


def test_extracting_the_prior_after_the_later_refreshes_the_later_summary(db):
    _, prior, later, _ = _pair(db)
    later_row = _extract(db, later, LATER_TEXT)
    assert later_row.diff_prior_filing_id is None and later_row.diff_summary is None
    _extract(db, prior, PRIOR_TEXT)
    db.expire_all()
    refreshed = _row(db, later.id)
    assert refreshed.diff_prior_filing_id == prior.id
    assert refreshed.diff_summary["counts"]["modified"] == 1


def test_re_extraction_replaces_the_row_in_place(db):
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    first = _extract(db, later, LATER_TEXT)
    first_id, first_sha = first.id, first.sha256
    second = _extract(db, later, PRIOR_TEXT, now=NOW + timedelta(days=1))
    assert second.id == first_id and second.sha256 != first_sha
    assert ensure_utc(second.extracted_at) == NOW + timedelta(days=1)
    assert second.diff_summary["has_changes"] is False  # identical to the prior now
    assert db.query(FilingSectionText).filter(FilingSectionText.filing_id == later.id).count() == 1


def test_fetch_or_parse_failure_is_recorded_not_raised(db):
    _, prior, _, _ = _pair(db)
    failing = AsyncMock(side_effect=TimeoutError("sec timed out"))
    attempt = asyncio.run(svc.extract_for_filing(db, prior, fetch_document=failing, parse=_parse({}), now=NOW))
    assert attempt.status == svc.STATUS_FAILED
    row = attempt.row
    assert row.status == svc.STATUS_FAILED and row.error_type == "TimeoutError"
    assert row.text is None and row.char_count == 0 and row.sha256 is None
    assert ensure_utc(row.attempted_at) == NOW

    def broken(html, form):
        raise ValueError("parser fault")

    attempt = asyncio.run(svc.extract_for_filing(
        db, prior, fetch_document=_fetch({prior.document_url: "html"}), parse=broken, now=NOW,
    ))
    assert attempt.row.error_type == "ValueError"  # the cause, not the executor's wrapper


def test_a_failed_re_extraction_keeps_the_older_text_and_waits(db, monkeypatch):
    """An EXTRACTOR_VERSION bump re-selects every older row; a fetch that then fails must not
    throw the stored text away, and the row waits like a failed one before the next attempt."""
    watcher = _user(db)
    _, prior, later, _ = _pair(db, watched_by=watcher)
    _extract(db, prior, PRIOR_TEXT)
    first_sha = _extract(db, later, LATER_TEXT).sha256
    tickers = [prior.company.ticker]
    assert _ids(db, tickers=tickers) == []
    monkeypatch.setattr(svc, "EXTRACTOR_VERSION", svc.EXTRACTOR_VERSION + 1)
    assert _ids(db, tickers=tickers) == [later.id, prior.id]  # older extractor: newest first

    failing = AsyncMock(side_effect=TimeoutError("sec timed out"))
    attempt = asyncio.run(svc.extract_for_filing(db, later, fetch_document=failing, parse=_parse({}), now=NOW + timedelta(hours=1)))
    assert attempt.status == svc.STATUS_FAILED
    row = attempt.row
    assert row.status == svc.STATUS_OK and row.text == LATER_TEXT and row.sha256 == first_sha
    assert row.error_type == "TimeoutError" and row.extractor_version == svc.EXTRACTOR_VERSION - 1
    assert ensure_utc(row.attempted_at) == NOW + timedelta(hours=1) and ensure_utc(row.extracted_at) == NOW
    assert row.diff_prior_filing_id == prior.id  # the cached comparison survives with the text
    assert svc.build_section_changes(db, later, svc.FULL_SECTION_ACCESS)["status"] == "ok"

    assert _ids(db, tickers=tickers, now=NOW + timedelta(hours=2)) == [prior.id]  # waits
    assert _ids(db, tickers=tickers, now=NOW + timedelta(hours=1) + svc.RETRY_FAILED_AFTER + timedelta(minutes=1)) == [later.id, prior.id]
    assert _ids(db, tickers=tickers, now=NOW + timedelta(hours=2), retry_failed=True) == [later.id, prior.id]

    _extract(db, later, LATER_TEXT, now=NOW + timedelta(days=2))
    db.expire_all()
    assert _row(db, later.id).error_type is None and _row(db, later.id).extractor_version == svc.EXTRACTOR_VERSION


def test_missing_section_is_recorded_without_text(db):
    _, prior, _, _ = _pair(db)
    attempt = _missing(db, prior)
    assert attempt.status == svc.STATUS_MISSING
    assert attempt.row.status == svc.STATUS_MISSING and attempt.row.text is None


def test_a_prior_that_turns_missing_clears_the_later_summary(db):
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    assert _extract(db, later, LATER_TEXT).diff_prior_filing_id == prior.id
    assert _missing(db, prior, now=NOW + timedelta(days=1)).row.status == svc.STATUS_MISSING
    db.expire_all()
    refreshed = _row(db, later.id)
    assert refreshed.diff_prior_filing_id is None and refreshed.diff_summary is None
    block = svc.build_section_changes(db, later, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("unavailable", "prior_missing")
    assert block["prior"]["status"] == "missing" and block["prior_filing"]["filing_id"] == prior.id
    _extract(db, prior, PRIOR_TEXT, now=NOW + timedelta(days=2))
    db.expire_all()
    assert _row(db, later.id).diff_summary["counts"]["modified"] == 1  # and back
    gone = _missing(db, later, now=NOW + timedelta(days=3)).row  # the later side turns missing
    assert gone.diff_prior_filing_id is None and gone.diff_summary is None and gone.diff_engine_version is None


def test_a_concurrent_insert_is_written_onto_not_duplicated(db, monkeypatch):
    """The operator script beside the hourly job: whoever inserts second writes onto the row."""
    from app.database import SessionLocal

    _, prior, _, _ = _pair(db)
    real_commit = db.commit
    raced = []

    def racing_commit():
        if not raced:
            raced.append(True)
            with SessionLocal() as other:
                other.add(FilingSectionText(
                    filing_id=prior.id, section=svc.SECTION_ITEM_1A, extractor_version=svc.EXTRACTOR_VERSION,
                    status=svc.STATUS_FAILED, error_type="TimeoutError", extracted_at=NOW, attempted_at=NOW,
                ))
                other.commit()
                other_id = other.query(FilingSectionText).filter(FilingSectionText.filing_id == prior.id).one().id
            raced.append(other_id)
            raise IntegrityError("INSERT INTO filing_section_text", {}, Exception("UNIQUE constraint failed"))
        real_commit()

    monkeypatch.setattr(db, "commit", racing_commit)
    attempt = _attempt(db, prior, PRIOR_TEXT, now=NOW + timedelta(minutes=1))
    assert attempt.status == svc.STATUS_OK
    rows = db.query(FilingSectionText).filter(FilingSectionText.filing_id == prior.id).all()
    assert [r.id for r in rows] == [raced[1]]
    assert rows[0].status == svc.STATUS_OK and rows[0].text == PRIOR_TEXT and rows[0].error_type is None


def test_oversize_text_is_recorded_without_text(db, monkeypatch):
    monkeypatch.setattr(settings, "SECTION_TEXT_MAX_CHARS", 50)
    _, prior, _, _ = _pair(db)
    attempt = _attempt(db, prior, PRIOR_TEXT)
    assert attempt.status == svc.STATUS_OVERSIZE
    assert attempt.row.status == svc.STATUS_OVERSIZE and attempt.row.text is None and attempt.row.detection_method == "toc"


def test_default_fetch_uses_the_shared_sec_transport(monkeypatch):
    from app.services.edgar.compat import sec_edgar_service

    get_document = AsyncMock(return_value="<html/>")
    monkeypatch.setattr(sec_edgar_service, "get_filing_document", get_document)
    assert asyncio.run(svc._default_fetch("https://sec.example/doc.htm")) == "<html/>"
    get_document.assert_awaited_once_with("https://sec.example/doc.htm", timeout=svc.FETCH_TIMEOUT_SECONDS)


def test_amendments_and_other_forms_are_not_fetched(db):
    _, _, _, amendment = _pair(db)
    fetch = AsyncMock(return_value="html")
    assert asyncio.run(svc.extract_for_filing(db, amendment, fetch_document=fetch, parse=_parse({}))) is None
    fetch.assert_not_awaited()
    assert db.query(FilingSectionText).filter(FilingSectionText.filing_id == amendment.id).count() == 0


# --- selection and the job body ---------------------------------------------------------------

def test_selection_prefers_watched_companies_newest_first_and_skips_done_rows(db):
    watcher = _user(db)
    _, w_prior, w_later, w_amend = _pair(db, watched_by=watcher)
    _, s_prior, s_later, _ = _pair(db)
    db.add(Summary(filing_id=s_later.id, business_overview="x"))
    db.commit()
    _, o_prior, o_later, _ = _pair(db)
    stale = _filing(db, w_later.company, "10-K", datetime(2021, 12, 31, tzinfo=timezone.utc), datetime(2022, 2, 1, tzinfo=timezone.utc))
    universe = {w_prior.id, w_later.id, s_prior.id, s_later.id, o_prior.id, o_later.id, w_amend.id, stale.id}
    tickers = [w_later.company.ticker, s_later.company.ticker, o_later.company.ticker]

    def ids(**kw):
        kw.setdefault("tickers", tickers)
        return _ids(db, **kw)

    # Watched company first, newest first; a summarized company's prior comes too; never an
    # amendment, never a filing outside the window.
    assert ids() == [w_later.id, w_prior.id, s_later.id, s_prior.id]
    assert set(ids(cohort="all")) == universe - {w_amend.id, stale.id}
    assert ids(window_days=10 * 365) == [w_later.id, w_prior.id, stale.id, s_later.id, s_prior.id]
    assert ids(tickers=[w_later.company.ticker.lower()]) == [w_later.id, w_prior.id]
    assert ids(limit=1) == [w_later.id] and ids(limit=0) == []

    _extract(db, w_later, LATER_TEXT)
    assert ids() == [w_prior.id, s_later.id, s_prior.id]

    failing = AsyncMock(side_effect=RuntimeError("boom"))
    asyncio.run(svc.extract_for_filing(db, w_prior, fetch_document=failing, parse=_parse({}), now=NOW))
    assert ids() == [s_later.id, s_prior.id]  # a fresh failure waits
    assert ids(retry_failed=True) == [w_prior.id, s_later.id, s_prior.id]
    assert ids(now=NOW + svc.RETRY_FAILED_AFTER + timedelta(minutes=1))[0] == w_prior.id


def test_run_section_extraction_counts_outcomes_including_errors(db, monkeypatch):
    watcher = _user(db)
    _, prior, later, _ = _pair(db, watched_by=watcher)
    _, other_prior, _, _ = _pair(db, watched_by=watcher)
    documents = {prior.document_url: "prior", later.document_url: "later", other_prior.document_url: "other"}
    parse = _parse({"prior": PRIOR_TEXT, "later": LATER_TEXT})  # "other" -> missing

    async def fetch(url):
        return documents[url]

    stats = asyncio.run(svc.run_section_extraction(
        db, limit=100, tickers=[prior.company.ticker, other_prior.company.ticker], fetch_document=fetch, parse=parse, now=NOW,
    ))
    assert stats == {"selected": 4, "extracted_ok": 2, "missing": 1, "oversize": 0, "extract_errors": 1,  # 4th: no document
                     "breaker_open": 0, "summaries_recomputed": 0}
    assert _row(db, later.id).diff_prior_filing_id == prior.id
    monkeypatch.setattr(settings, "SECTION_EXTRACTION_BATCH_LIMIT", 0)
    assert asyncio.run(svc.run_section_extraction(db, fetch_document=fetch, parse=parse, now=NOW))["selected"] == 0


def test_an_open_breaker_halts_the_batch_without_writing(db):
    from app.services.edgar.circuit_breaker import CircuitOpenError

    watcher = _user(db)
    _, prior, later, _ = _pair(db, watched_by=watcher)
    fetch = AsyncMock(side_effect=CircuitOpenError("sec", "open", 30.0))
    with pytest.raises(svc.SectionExtractionHalted):
        asyncio.run(svc.extract_for_filing(db, later, fetch_document=fetch, parse=_parse({}), now=NOW))
    stats = asyncio.run(svc.run_section_extraction(
        db, limit=100, tickers=[later.company.ticker], fetch_document=fetch, parse=_parse({}), now=NOW,
    ))
    assert stats["selected"] == 2 and stats["breaker_open"] == 1 and stats["extract_errors"] == 0
    assert fetch.await_count == 2  # one before each halt, nothing after
    assert db.query(FilingSectionText).filter(FilingSectionText.filing_id.in_([prior.id, later.id])).count() == 0


def test_the_batch_holds_no_transaction_through_transport_and_refuses_pending_writes(db):
    """The job-owned session's selection is a finished read before the first fetch, and the
    per-filing commits leave the selected filings loaded, so no later fetch starts a transaction
    either: the pooled connection is never idle in transaction through SEC transport or the parse
    (lessons/ops-finish-only-job-owned-read-transactions.md). The session's expiry policy is
    restored afterwards, and a session carrying pending writes is refused rather than committed."""
    watcher = _user(db)
    _, prior, later, _ = _pair(db, watched_by=watcher)
    documents = {prior.document_url: "prior", later.document_url: "later"}
    in_transaction_at_fetch: list[bool] = []

    async def fetch(url):
        in_transaction_at_fetch.append(db.in_transaction())
        return documents[url]

    assert prior.company.ticker and db.in_transaction()  # the caller's own read is open on entry
    stats = asyncio.run(svc.run_section_extraction(
        db, limit=100, tickers=[prior.company.ticker], fetch_document=fetch,
        parse=_parse({"prior": PRIOR_TEXT, "later": LATER_TEXT}), now=NOW,
    ))
    assert stats["extracted_ok"] == 2 and in_transaction_at_fetch == [False, False]
    assert db.expire_on_commit is True
    assert _row(db, later.id).diff_prior_filing_id == prior.id

    db.add(Watchlist(user_id=watcher.id, company_id=prior.company_id))
    with pytest.raises(RuntimeError, match="pending writes"):
        asyncio.run(svc.run_section_extraction(db, limit=100, fetch_document=fetch, parse=_parse({}), now=NOW))
    db.rollback()
    assert db.expire_on_commit is True


def test_the_batch_recomputes_summaries_behind_the_diff_engine(db):
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    later_row = _extract(db, later, LATER_TEXT)
    later_row.diff_engine_version = svc.section_diff.ENGINE_VERSION - 1
    later_row.diff_summary = {"stale": True}
    db.commit()
    assert svc.recompute_stale_summaries(db, limit=10, now=NOW + timedelta(days=1)) >= 1
    db.expire_all()
    refreshed = _row(db, later.id)
    assert refreshed.diff_engine_version == svc.section_diff.ENGINE_VERSION
    assert refreshed.diff_summary["counts"]["modified"] == 1 and refreshed.diff_prior_filing_id == prior.id
    assert ensure_utc(refreshed.diff_computed_at) == NOW + timedelta(days=1)
    assert svc.recompute_stale_summaries(db, limit=10) == 0


# --- the Change Report block ------------------------------------------------------------------

def test_section_changes_access_follows_the_flag_and_the_entitlement(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    assert svc.section_changes_access(SimpleNamespace(is_pro=True, subscription=None)) == svc.NO_SECTION_ACCESS
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    assert svc.section_changes_access(None) == TEASER  # anonymous resolves to the Free plan
    assert svc.section_changes_access(SimpleNamespace(is_pro=False, subscription=None)) == TEASER
    assert svc.section_changes_access(SimpleNamespace(is_pro=True, subscription=None)) == svc.FULL_SECTION_ACCESS
    assert svc.FULL_SECTION_ACCESS.item_limit is None and svc.NO_SECTION_ACCESS.level == "none"


def test_section_changes_block_states(db):
    _, prior, later, amendment = _pair(db)
    assert svc.build_section_changes(db, later, svc.NO_SECTION_ACCESS) is None

    block = svc.build_section_changes(db, later, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("pending", "current_not_extracted")
    assert block["section"] == "item_1a" and block["section_label"] == "Item 1A. Risk Factors"
    assert block["engine_version"] == svc.section_diff.ENGINE_VERSION and block["prior_filing"] is None

    _extract(db, later, LATER_TEXT)
    block = svc.build_section_changes(db, later, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("pending", "prior_not_extracted")
    assert block["prior_filing"]["filing_id"] == prior.id  # which filing the state is about
    assert block["current"]["status"] == "ok" and block["current"]["paragraph_count"] == 4
    assert block["current"]["extracted_at"].endswith("Z")

    block = svc.build_section_changes(db, prior, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("pending", "current_not_extracted")
    _extract(db, prior, PRIOR_TEXT)
    block = svc.build_section_changes(db, prior, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("no_prior", "no_prior_filing")

    full = svc.build_section_changes(db, later, svc.FULL_SECTION_ACCESS)
    assert full["status"] == "ok" and full["access"] == "full" and full["reason"] is None
    assert full["prior_filing"]["filing_id"] == prior.id and full["prior_filing"]["accession_number"] == prior.accession_number
    assert full["counts"] == {"unchanged": 1, "modified": 1, "added": 2, "removed": 1, "moved": 0}
    # Reading order of the later text; the removed paragraph sits where it used to (after "defects").
    assert [i["kind"] for i in full["items"]] == ["modified", "removed", "added", "added"]
    assert full["items_total"] == 4 and full["truncated"] is False
    assert full["prior"]["reference_only"] is False and full["has_changes"] is True

    teaser = svc.build_section_changes(db, later, TEASER)
    assert teaser["access"] == "teaser" and teaser["counts"] == full["counts"]
    assert len(teaser["items"]) == 3 and teaser["items_total"] == 4 and teaser["truncated"] is True
    assert teaser["items"] == full["items"][:3]
    assert svc.build_section_changes(db, later, svc.SectionAccess(svc.ACCESS_TEASER, 0))["items"] == []

    block = svc.build_section_changes(db, amendment, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("unavailable", "form_not_supported")


def test_a_teaser_with_nothing_withheld_is_not_truncated(db):
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, PRIOR_TEXT.replace("small number", "limited number"))
    teaser = svc.build_section_changes(db, later, TEASER)
    assert teaser["items_total"] == 1 and len(teaser["items"]) == 1 and teaser["truncated"] is False


def test_a_missing_or_failed_current_section_is_unavailable(db):
    _, prior, _, _ = _pair(db)
    _missing(db, prior)
    block = svc.build_section_changes(db, prior, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("unavailable", "current_missing")
    assert block["current"]["status"] == "missing"


def test_the_comparison_never_skips_a_period(db):
    company = _company(db)
    oldest = _filing(db, company, "10-K", datetime(2023, 12, 31, tzinfo=timezone.utc), datetime(2024, 2, 20, tzinfo=timezone.utc))
    middle = _filing(db, company, "10-K", datetime(2024, 12, 31, tzinfo=timezone.utc), datetime(2025, 2, 20, tzinfo=timezone.utc))
    latest = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc))
    _extract(db, oldest, PRIOR_TEXT)
    assert _extract(db, latest, LATER_TEXT).diff_prior_filing_id is None  # never the period before last
    block = svc.build_section_changes(db, latest, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("pending", "prior_not_extracted")
    assert block["prior_filing"]["filing_id"] == middle.id
    _missing(db, middle)
    block = svc.build_section_changes(db, latest, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("unavailable", "prior_missing")
    assert block["prior"]["status"] == "missing" and block["current"]["status"] == "ok"
    assert svc.prior_section_row(db, latest) is None


def test_a_prior_outside_the_extraction_window_is_unavailable(db):
    company = _company(db)
    old = _filing(db, company, "10-K", datetime(2019, 12, 31, tzinfo=timezone.utc), datetime(2020, 2, 20, tzinfo=timezone.utc))
    new = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc))
    _extract(db, new, LATER_TEXT)
    block = svc.build_section_changes(db, new, svc.FULL_SECTION_ACCESS)
    assert (block["status"], block["reason"]) == ("unavailable", "prior_outside_window")
    assert block["prior_filing"]["filing_id"] == old.id
    # The same window bounds the batch: that prior is never fetched, so the block is not "pending".
    assert old.id not in [f.id for f in svc.select_filings_for_extraction(db, limit=100, cohort="all", tickers=[company.ticker])]


def test_a_stub_10q_compares_and_is_labelled_reference_only(db):
    company = _company(db)
    q1 = _filing(db, company, "10-Q", datetime(2026, 3, 31, tzinfo=timezone.utc), datetime(2026, 5, 1, tzinfo=timezone.utc))
    q2 = _filing(db, company, "10-Q", datetime(2026, 6, 30, tzinfo=timezone.utc), datetime(2026, 8, 1, tzinfo=timezone.utc))
    _extract(db, q1, STUB_TEXT)
    q2_row = _extract(db, q2, STUB_TEXT)
    block = svc.build_section_changes(db, q2, svc.FULL_SECTION_ACCESS)
    assert block["status"] == "ok" and block["has_changes"] is False
    assert block["current"]["reference_only"] is True and block["prior"]["reference_only"] is True
    assert q2_row.diff_summary["reference_only"] is True and q2_row.diff_summary["prior_reference_only"] is True
    q3 = _filing(db, company, "10-Q", datetime(2026, 9, 30, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc))
    q3_row = _extract(db, q3, LATER_TEXT)  # restated after a stub
    assert q3_row.diff_summary["reference_only"] is False and q3_row.diff_summary["prior_reference_only"] is True
    assert q3_row.diff_summary["has_changes"] is True


def test_prior_requires_a_strictly_earlier_period_of_the_same_form(db):
    company = _company(db)
    annual = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc))
    quarterly = _filing(db, company, "10-Q", datetime(2026, 3, 31, tzinfo=timezone.utc), datetime(2026, 5, 1, tzinfo=timezone.utc))
    _extract(db, annual, PRIOR_TEXT)
    _extract(db, quarterly, LATER_TEXT)
    assert svc.prior_section_row(db, quarterly) is None  # a 10-K is never a 10-Q's prior
    undated = _filing(db, company, "10-Q", None, datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert svc.prior_section_row(db, undated) is None  # no period: nothing provably different
    # The same period filed earlier (a re-filed 10-K) is not a prior; neither is an earlier
    # period that was filed later (a late 10-K): the prior must have been public first.
    refiled = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 1, 15, tzinfo=timezone.utc))
    _extract(db, refiled, PRIOR_TEXT)
    assert svc._prior_filing(db, annual) is None
    late = _filing(db, company, "10-K", datetime(2024, 12, 31, tzinfo=timezone.utc), datetime(2026, 6, 1, tzinfo=timezone.utc))
    _extract(db, late, PRIOR_TEXT)
    assert svc._prior_filing(db, annual) is None and svc._next_filing(db, late) is None


def test_the_prior_is_the_latest_earlier_period_and_the_successor_the_nearest(db):
    company = _company(db)
    fy23 = _filing(db, company, "10-K", datetime(2023, 12, 31, tzinfo=timezone.utc), datetime(2024, 2, 20, tzinfo=timezone.utc))
    fy24 = _filing(db, company, "10-K", datetime(2024, 12, 31, tzinfo=timezone.utc), datetime(2025, 2, 20, tzinfo=timezone.utc))
    fy25 = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc))
    assert svc._prior_filing(db, fy25).id == fy24.id and svc._next_filing(db, fy23).id == fy24.id
    _extract(db, fy25, LATER_TEXT)
    _extract(db, fy24, PRIOR_TEXT)
    _extract(db, fy23, PRIOR_TEXT)
    db.expire_all()
    assert _row(db, fy25.id).diff_prior_filing_id == fy24.id
    assert _row(db, fy24.id).diff_prior_filing_id == fy23.id  # refreshed by fy23's extraction
    assert _row(db, fy23.id).diff_prior_filing_id is None


def test_change_report_carries_the_block_or_null(db):
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, LATER_TEXT)
    report = build_change_report(db, later)
    assert report["section_changes"] is None and report["prior_filing"]["filing_id"] == prior.id
    report = build_change_report(db, later, section_access=TEASER)
    assert report["section_changes"]["status"] == "ok" and report["section_changes"]["truncated"] is True
    # The router's unit: lookup and report together, None for a filing that does not exist.
    assert change_report_for_filing(db, later.id, section_access=TEASER)["section_changes"]["truncated"] is True
    assert change_report_for_filing(db, 0) is None


def test_cached_diff_is_memoized_on_the_text_hashes(db, monkeypatch):
    _, prior, later, _ = _pair(db)
    prior_row = _extract(db, prior, PRIOR_TEXT)
    later_row = _extract(db, later, LATER_TEXT)
    calls = []
    original = svc.section_diff.diff_sections

    def counting(a, b):
        calls.append(1)
        return original(a, b)

    monkeypatch.setattr(svc.section_diff, "diff_sections", counting)
    svc._DIFF_CACHE.clear()
    first = svc.cached_diff(prior_row, later_row)
    assert svc.cached_diff(prior_row, later_row) is first and calls == [1]
    reextracted = _extract(db, prior, STUB_TEXT, now=NOW + timedelta(days=1))  # new prior text, same later
    assert svc.cached_diff(reextracted, later_row) is not first and len(calls) >= 2


# --- the endpoint and the scan hook -----------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def test_what_changed_endpoint_serves_a_teaser_anonymously_and_the_full_list_to_pro(db, client, monkeypatch):
    from app.routers.auth import create_access_token

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, LATER_TEXT)

    anonymous = client.get(f"/api/summaries/filing/{later.id}/what-changed")
    assert anonymous.status_code == 200
    block = anonymous.json()["section_changes"]
    assert block["access"] == "teaser" and block["truncated"] is True and len(block["items"]) == 3

    free = _user(db, is_pro=False)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": free.email}))
    signed_in = client.get(f"/api/summaries/filing/{later.id}/what-changed").json()["section_changes"]
    assert signed_in["access"] == "teaser" and len(signed_in["items"]) == 3 and signed_in["items_total"] == 4

    pro = _user(db, is_pro=True)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": pro.email}))
    full = client.get(f"/api/summaries/filing/{later.id}/what-changed").json()["section_changes"]
    assert full["access"] == "full" and full["truncated"] is False and full["items_total"] == 4
    client.cookies.clear()

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    assert client.get(f"/api/summaries/filing/{later.id}/what-changed").json()["section_changes"] is None
    assert client.get("/api/summaries/filing/0/what-changed").status_code == 404


def test_what_changed_endpoint_resolves_the_viewer_access_inside_the_threadpool_unit(db, client, monkeypatch):
    """``section_changes_access`` reads the viewer's subscription row (``get_entitlements``, a lazy
    load the auth dependency does not make), so the route resolves it inside the unit it hands to
    the threadpool, never on the event loop."""
    from app.routers import summaries as summaries_router
    from app.routers.auth import create_access_token

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, LATER_TEXT)
    real_run_in_threadpool = summaries_router.run_in_threadpool
    real_access = summaries_router.section_changes_access
    off_loop = {"active": False}
    resolved_off_loop: list[bool] = []

    async def spying_run_in_threadpool(func, *args, **kwargs):
        def unit(*a, **kw):
            off_loop["active"] = True
            try:
                return func(*a, **kw)
            finally:
                off_loop["active"] = False

        return await real_run_in_threadpool(unit, *args, **kwargs)

    def access(user):
        resolved_off_loop.append(off_loop["active"])
        return real_access(user)

    monkeypatch.setattr(summaries_router, "run_in_threadpool", spying_run_in_threadpool)
    monkeypatch.setattr(summaries_router, "section_changes_access", access)
    pro = _user(db, is_pro=True)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": pro.email}))
    full = client.get(f"/api/summaries/filing/{later.id}/what-changed").json()["section_changes"]
    client.cookies.clear()
    assert full["access"] == "full" and resolved_off_loop == [True]


CLEAN_BATCH = {"selected": 2, "extracted_ok": 2, "missing": 0, "oversize": 0, "extract_errors": 0,
               "breaker_open": 0, "summaries_recomputed": 0}


@pytest.fixture
def job_outcomes(monkeypatch):
    """Every (job name, status, counters) the ledger records during the test."""
    from app.services import job_run_service as jobs

    outcomes = []
    original_track, original_finish = jobs.track_job, jobs._finish
    names = {}

    def observing_track(name, **kw):
        manager = original_track(name, **kw)
        names[id(manager)] = name
        return manager

    def observing_finish(run_id, status, attempt, error_type=None):
        outcomes.append((status, dict(attempt.counters), error_type))
        return original_finish(run_id, status, attempt, error_type)

    monkeypatch.setattr(jobs, "track_job", observing_track)
    monkeypatch.setattr(jobs, "_finish", observing_finish)
    return outcomes


@pytest.mark.parametrize("enabled", [False, True])
def test_filing_scan_runs_the_extraction_batch_only_behind_the_flag(monkeypatch, job_outcomes, enabled):
    from scripts import filing_scan
    from app.services import filing_scan_service

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", enabled)
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(return_value={"companies_scanned": 1}))
    monkeypatch.setattr(filing_scan_service, "run_daily_digest", AsyncMock(return_value={"digests_sent": 0}))
    extraction = AsyncMock(return_value=CLEAN_BATCH)
    monkeypatch.setattr(svc, "run_section_extraction", extraction)
    asyncio.run(filing_scan._main(digest=False, dry_run=False, cadence_minutes=60))
    assert extraction.await_count == (1 if enabled else 0)
    expected = [("succeeded", {"companies_scanned": 1}, None)]
    if enabled:
        expected.append(("succeeded", CLEAN_BATCH, None))
    assert job_outcomes == expected

    if enabled:
        job_outcomes.clear()
        asyncio.run(filing_scan._main(digest=True, dry_run=False, cadence_minutes=60))
        assert job_outcomes == [("succeeded", {"digests_sent": 0}, None)]  # the digest pass never extracts


def test_filing_scan_still_extracts_after_a_failed_scan_and_survives_extraction_errors(monkeypatch, job_outcomes):
    from scripts import filing_scan
    from app.services import filing_scan_service
    from app.services.job_run_service import JobRunFailed

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    failed_batch = {**CLEAN_BATCH, "extracted_ok": 1, "extract_errors": 1}
    extraction = AsyncMock(return_value=failed_batch)
    monkeypatch.setattr(svc, "run_section_extraction", extraction)

    # A scan whose source errored still fails the execution, but only after the batch ran.
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(return_value={"companies_scanned": 2, "source_errors": 1}))
    with pytest.raises(JobRunFailed):
        asyncio.run(filing_scan._main(digest=False, dry_run=False, cadence_minutes=60))
    assert extraction.await_count == 1
    assert job_outcomes == [
        ("failed", {"companies_scanned": 2, "source_errors": 1}, "JobRunFailed"),
        ("failed", failed_batch, "JobRunFailed"),
    ]

    # A clean scan with a failed document: the batch's own row is failed, the execution is not
    # (Cloud Run would otherwise re-run the scan for a row that waits 24 h anyway).
    job_outcomes.clear()
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(return_value={"companies_scanned": 2}))
    asyncio.run(filing_scan._main(digest=False, dry_run=False, cadence_minutes=60))
    assert job_outcomes == [("succeeded", {"companies_scanned": 2}, None), ("failed", failed_batch, "JobRunFailed")]

    # Anything but recorded work failures (the database down, say) propagates at once, batch or no batch.
    extraction.reset_mock()
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(side_effect=RuntimeError("database unreachable")))
    with pytest.raises(RuntimeError):
        asyncio.run(filing_scan._main(digest=False, dry_run=False, cadence_minutes=60))
    assert extraction.await_count == 0
    job_outcomes.clear()
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(return_value={"companies_scanned": 2}))
    monkeypatch.setattr(svc, "run_section_extraction", AsyncMock(side_effect=RuntimeError("database unreachable")))
    with pytest.raises(RuntimeError):
        asyncio.run(filing_scan._main(digest=False, dry_run=False, cadence_minutes=60))
    assert job_outcomes == [("succeeded", {"companies_scanned": 2}, None), ("failed", {}, "RuntimeError")]


def test_operator_script_has_its_own_job_identity_and_widens_the_cohort_for_named_tickers(monkeypatch, job_outcomes):
    from scripts import extract_sections

    assert extract_sections.JOB_NAME == "section-extraction-manual"
    assert extract_sections.cohort_for(all_filings=False, tickers=[]) == "watched"
    assert extract_sections.cohort_for(all_filings=False, tickers=["AAPL"]) == "all"
    assert extract_sections.cohort_for(all_filings=True, tickers=[]) == "all"

    extraction = AsyncMock(return_value=CLEAN_BATCH)
    monkeypatch.setattr(svc, "run_section_extraction", extraction)
    from app.models import JobRun
    from app.database import SessionLocal

    asyncio.run(extract_sections._main(tickers=["AAPL"], cohort="all", limit=5, retry_failed=True, window_days=None))
    extraction.assert_awaited_once()
    assert extraction.await_args.kwargs == {"limit": 5, "cohort": "all", "tickers": ["AAPL"], "retry_failed": True, "window_days": None}
    assert job_outcomes == [("succeeded", CLEAN_BATCH, None)]
    with SessionLocal() as session:
        assert session.query(JobRun).filter(JobRun.job_name == "section-extraction-manual").count() >= 1
