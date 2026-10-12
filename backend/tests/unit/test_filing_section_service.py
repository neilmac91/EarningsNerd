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

from app.config import settings
from app.models import Company, Filing, FilingSectionText, Summary, User, Watchlist
from app.services import filing_section_service as svc
from app.services.change_report_service import build_change_report

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)

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


@pytest.fixture
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _company(db, *, watched_by=None):
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:5].upper()}", name=f"Co {suffix}")
    db.add(company)
    db.commit()
    if watched_by is not None:
        db.add(Watchlist(user_id=watched_by.id, company_id=company.id))
        db.commit()
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


def _extract(db, filing, text, *, now=NOW):
    documents = {filing.document_url: f"html-{filing.id}"}
    return asyncio.run(svc.extract_for_filing(
        db, filing, fetch_document=_fetch(documents), parse=_parse({f"html-{filing.id}": text}), now=now,
    ))


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
    assert second.diff_summary["has_changes"] is False  # identical to the prior now
    assert db.query(FilingSectionText).filter(FilingSectionText.filing_id == later.id).count() == 1


def test_fetch_or_parse_failure_is_recorded_not_raised(db):
    _, prior, _, _ = _pair(db)
    failing = AsyncMock(side_effect=TimeoutError("sec timed out"))
    row = asyncio.run(svc.extract_for_filing(db, prior, fetch_document=failing, parse=_parse({}), now=NOW))
    assert row.status == svc.STATUS_FAILED and row.error_type == "TimeoutError"
    assert row.text is None and row.char_count == 0 and row.sha256 is None

    def broken(html, form):
        raise ValueError("parser fault")

    row = asyncio.run(svc.extract_for_filing(
        db, prior, fetch_document=_fetch({prior.document_url: "html"}), parse=broken, now=NOW,
    ))
    assert row.status == svc.STATUS_FAILED and row.error_type == "ValueError"  # the cause, not the executor's wrapper


def test_missing_section_is_recorded_without_text(db):
    _, prior, _, _ = _pair(db)
    row = asyncio.run(svc.extract_for_filing(
        db, prior, fetch_document=_fetch({prior.document_url: "html"}), parse=_parse({}), now=NOW,
    ))
    assert row.status == svc.STATUS_MISSING and row.text is None


def test_oversize_text_is_recorded_without_text(db, monkeypatch):
    monkeypatch.setattr(settings, "SECTION_TEXT_MAX_CHARS", 50)
    _, prior, _, _ = _pair(db)
    row = _extract(db, prior, PRIOR_TEXT)
    assert row.status == svc.STATUS_OVERSIZE and row.text is None and row.detection_method == "toc"


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

    def ids(**kw):
        kw.setdefault("now", NOW)
        return [f.id for f in svc.select_filings_for_extraction(db, limit=100, **kw) if f.id in universe]

    # Watched company first, newest first; a summarized company's prior comes too; never an
    # amendment, never a filing outside the window.
    assert ids() == [w_later.id, w_prior.id, s_later.id, s_prior.id]
    assert set(ids(cohort="all")) == universe - {w_amend.id, stale.id}
    assert ids(window_days=10 * 365) == [w_later.id, w_prior.id, stale.id, s_later.id, s_prior.id]
    assert ids(tickers=[w_later.company.ticker.lower()]) == [w_later.id, w_prior.id]
    assert [f.id for f in svc.select_filings_for_extraction(db, limit=0, now=NOW)] == []

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
    assert stats == {"selected": 4, "extracted_ok": 2, "missing": 1, "oversize": 0, "extract_errors": 1}  # 4th: no document
    assert _row(db, later.id).diff_prior_filing_id == prior.id
    monkeypatch.setattr(settings, "SECTION_EXTRACTION_BATCH_LIMIT", 0)
    assert asyncio.run(svc.run_section_extraction(db, fetch_document=fetch, parse=parse, now=NOW))["selected"] == 0


# --- the Change Report block ------------------------------------------------------------------

def test_section_changes_access_follows_the_flag_and_the_entitlement(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    assert svc.section_changes_access(SimpleNamespace(is_pro=True, subscription=None)) == svc.ACCESS_NONE
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    assert svc.section_changes_access(None) == svc.ACCESS_TEASER
    assert svc.section_changes_access(SimpleNamespace(is_pro=False, subscription=None)) == svc.ACCESS_TEASER
    assert svc.section_changes_access(SimpleNamespace(is_pro=True, subscription=None)) == svc.ACCESS_FULL


def test_section_changes_block_states(db):
    _, prior, later, amendment = _pair(db)
    assert svc.build_section_changes(db, later, svc.ACCESS_NONE) is None

    block = svc.build_section_changes(db, later, svc.ACCESS_FULL)
    assert (block["status"], block["reason"]) == ("pending", "current_not_extracted")
    assert block["section"] == "item_1a" and block["section_label"] == "Item 1A. Risk Factors"

    _extract(db, later, LATER_TEXT)
    block = svc.build_section_changes(db, later, svc.ACCESS_FULL)
    assert (block["status"], block["reason"]) == ("pending", "prior_not_extracted")
    assert block["current"]["paragraph_count"] == 4 and block["current"]["extracted_at"].endswith("Z")

    block = svc.build_section_changes(db, prior, svc.ACCESS_FULL)
    assert (block["status"], block["reason"]) == ("pending", "current_not_extracted")
    _extract(db, prior, PRIOR_TEXT)
    block = svc.build_section_changes(db, prior, svc.ACCESS_FULL)
    assert (block["status"], block["reason"]) == ("no_prior", "no_prior_filing")

    full = svc.build_section_changes(db, later, svc.ACCESS_FULL)
    assert full["status"] == "ok" and full["access"] == "full"
    assert full["prior_filing"]["filing_id"] == prior.id and full["prior_filing"]["accession_number"] == prior.accession_number
    assert full["counts"] == {"unchanged": 1, "modified": 1, "added": 2, "removed": 1, "moved": 0}
    # Reading order of the later text; the removed paragraph sits where it used to (after "defects").
    assert [i["kind"] for i in full["items"]] == ["modified", "removed", "added", "added"]
    assert full["items_total"] == 4 and full["truncated"] is False
    assert full["prior"]["reference_only"] is False and full["has_changes"] is True

    teaser = svc.build_section_changes(db, later, svc.ACCESS_TEASER)
    assert teaser["access"] == "teaser" and teaser["counts"] == full["counts"]
    assert len(teaser["items"]) == svc.TEASER_ITEMS and teaser["items_total"] == 4 and teaser["truncated"] is True
    assert teaser["items"] == full["items"][: svc.TEASER_ITEMS]

    block = svc.build_section_changes(db, amendment, svc.ACCESS_FULL)
    assert (block["status"], block["reason"]) == ("unavailable", "form_not_supported")


def test_a_missing_or_failed_current_section_is_unavailable(db):
    _, prior, _, _ = _pair(db)
    asyncio.run(svc.extract_for_filing(db, prior, fetch_document=_fetch({prior.document_url: "h"}), parse=_parse({}), now=NOW))
    block = svc.build_section_changes(db, prior, svc.ACCESS_FULL)
    assert (block["status"], block["reason"]) == ("unavailable", "current_missing")


def test_a_stub_10q_compares_and_is_labelled_reference_only(db):
    company = _company(db)
    q1 = _filing(db, company, "10-Q", datetime(2026, 3, 31, tzinfo=timezone.utc), datetime(2026, 5, 1, tzinfo=timezone.utc))
    q2 = _filing(db, company, "10-Q", datetime(2026, 6, 30, tzinfo=timezone.utc), datetime(2026, 8, 1, tzinfo=timezone.utc))
    _extract(db, q1, STUB_TEXT)
    _extract(db, q2, STUB_TEXT)
    block = svc.build_section_changes(db, q2, svc.ACCESS_FULL)
    assert block["status"] == "ok" and block["has_changes"] is False
    assert block["current"]["reference_only"] is True and block["prior"]["reference_only"] is True


def test_prior_requires_a_strictly_earlier_period_of_the_same_form(db):
    company = _company(db)
    annual = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc))
    quarterly = _filing(db, company, "10-Q", datetime(2026, 3, 31, tzinfo=timezone.utc), datetime(2026, 5, 1, tzinfo=timezone.utc))
    _extract(db, annual, PRIOR_TEXT)
    _extract(db, quarterly, LATER_TEXT)
    assert svc.prior_section_row(db, quarterly) is None  # a 10-K is never a 10-Q's prior
    undated = _filing(db, company, "10-Q", None, datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert svc.prior_section_row(db, undated) is None  # no period: nothing provably different


def test_change_report_carries_the_block_or_null(db):
    _, prior, later, _ = _pair(db)
    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, LATER_TEXT)
    report = build_change_report(db, later)
    assert report["section_changes"] is None and report["prior_filing"]["filing_id"] == prior.id
    report = build_change_report(db, later, section_access=svc.ACCESS_TEASER)
    assert report["section_changes"]["status"] == "ok" and report["section_changes"]["truncated"] is True


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
    assert block["access"] == "teaser" and block["truncated"] is True and len(block["items"]) == svc.TEASER_ITEMS

    pro = _user(db, is_pro=True)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": pro.email}))
    full = client.get(f"/api/summaries/filing/{later.id}/what-changed").json()["section_changes"]
    assert full["access"] == "full" and full["truncated"] is False and full["items_total"] == 4
    client.cookies.clear()

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    assert client.get(f"/api/summaries/filing/{later.id}/what-changed").json()["section_changes"] is None
    assert client.get("/api/summaries/filing/0/what-changed").status_code == 404


@pytest.mark.parametrize("enabled", [False, True])
def test_filing_scan_runs_the_extraction_batch_only_behind_the_flag(monkeypatch, enabled):
    from scripts import filing_scan
    from app.services import filing_scan_service
    from app.services import job_run_service as jobs

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", enabled)
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(return_value={"companies_scanned": 1}))
    monkeypatch.setattr(filing_scan_service, "run_daily_digest", AsyncMock(return_value={"digests_sent": 0}))
    extraction = AsyncMock(return_value={"selected": 2, "extracted_ok": 2, "missing": 0, "oversize": 0, "extract_errors": 0})
    monkeypatch.setattr(svc, "run_section_extraction", extraction)
    tracked = []
    original_track = jobs.track_job

    def observing_track(name, **kw):
        tracked.append(name)
        return original_track(name, **kw)

    monkeypatch.setattr(jobs, "track_job", observing_track)
    asyncio.run(filing_scan._main(digest=False, dry_run=False, cadence_minutes=60))
    assert tracked == (["filing-scan", "section-extraction"] if enabled else ["filing-scan"])
    assert extraction.await_count == (1 if enabled else 0)

    if enabled:
        tracked.clear()
        asyncio.run(filing_scan._main(digest=True, dry_run=False, cadence_minutes=60))
        assert tracked == ["filing-digest"]  # the digest pass never extracts
