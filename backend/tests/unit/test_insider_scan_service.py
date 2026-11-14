"""One step of an issuer's Form 4 scan (ADR 0009): app/services/insider_scan_service.py.

A real SQLite database, an injected listing and an injected document fetch that count their calls: the tests
state how many SEC requests a step makes, that a stored filing is never fetched again, and that the step stops
at the first pushback and stays stopped. Two steps claiming one scan on PostgreSQL:
tests/integration/test_insider_scan_transactions.py.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.insider import InsiderFiling, InsiderScan, InsiderTransaction
from app.services import insider_scan_service as scan_service
from app.services.edgar.circuit_breaker import CircuitOpenError
from app.services.edgar.exceptions import (
    CompanyNotFoundError,
    EdgarError,
    EdgarNetworkError,
    EdgarNotFoundError,
    EdgarRateLimitError,
    EdgarTimeoutError,
    translate_edgartools_exception,
)
from app.services.insider_scan_service import (
    LEASE,
    LIST_TTL,
    MAX_FILINGS,
    PAUSE_BASE,
    PAUSE_MAX,
    STEP_FILINGS,
    ListedFiling,
    run_scan_step,
)
from tests.support.form4_documents import form4, submission_text, trade

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
CIK = "999999"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/999999/"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def accession(n: int) -> str:
    return f"0000999999-26-{n:06d}"


def listing(count: int, *, start: int = 1, document: str = "xslF345X05/form4.xml") -> list[ListedFiling]:
    """``count`` filings, the highest number filed last."""
    return [ListedFiling(accession(n), date(2026, 1, 1) + timedelta(days=n), document)
            for n in range(start + count - 1, start - 1, -1)]


class Sec:
    """Stands in for SEC: a listing and documents by address, every call recorded."""

    def __init__(self, filings: list[ListedFiling], *, document: str | None = None):
        self.filings = filings
        self.document = document or form4(trades=[trade("P", "100", "10.00", "2026-10-01")])
        self.listings = 0
        self.fetched: list[str] = []
        self.answers: dict[str, object] = {}   # address → text, or an exception to raise
        self.list_error: Exception | None = None

    async def list_filings(self, cik: str) -> list[ListedFiling]:
        self.listings += 1
        if self.list_error is not None:
            raise self.list_error
        return list(self.filings)

    async def fetch(self, url: str) -> str:
        self.fetched.append(url)
        answer = self.answers.get(url, self.document)
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def requests(self) -> int:
        return self.listings + len(self.fetched)


async def step(db: Session, sec: Sec, *, now: datetime = NOW):
    return await run_scan_step(db, CIK, now=now, list_filings=sec.list_filings, fetch_document=sec.fetch)


def xml_url(n: int, name: str = "form4.xml") -> str:
    return f"{ARCHIVE}{accession(n).replace('-', '')}/{name}"


def text_url(n: int) -> str:
    return f"{ARCHIVE}{accession(n)}.txt"


def scan_row(db: Session) -> InsiderScan:
    db.expire_all()
    return db.query(InsiderScan).one()


def statuses(db: Session) -> dict[str, str]:
    db.expire_all()
    return {row.accession: row.status for row in db.query(InsiderFiling)}


def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --- what one step costs ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_first_step_lists_once_and_fetches_only_its_share_newest_first(db):
    sec = Sec(listing(20))
    stats = await step(db, sec)

    assert (sec.listings, len(sec.fetched), stats.requests) == (1, STEP_FILINGS, 1 + STEP_FILINGS)
    assert sec.fetched == [xml_url(n) for n in range(20, 20 - STEP_FILINGS, -1)]   # the raw XML, not the rendered view
    assert (stats.outcome, stats.listed, stats.stored, stats.trades, stats.remaining) == ("ran", 20, STEP_FILINGS, STEP_FILINGS, 12)
    scan = scan_row(db)
    assert (scan.status, scan.lease_token, scan.lease_until, scan.steps, scan.error_code) == ("scanning", None, None, 1, None)
    assert db.query(InsiderTransaction).count() == STEP_FILINGS
    trade_row = db.query(InsiderTransaction).filter_by(accession=accession(20)).one()
    assert (trade_row.issuer_cik, trade_row.ordinal, trade_row.transaction_code, trade_row.shares, trade_row.price,
            trade_row.transaction_date, trade_row.filed_date) == (CIK, 0, "P", 100.0, 10.0, date(2026, 10, 1), date(2026, 1, 21))


@pytest.mark.asyncio
async def test_later_steps_resume_without_listing_again_or_fetching_a_stored_filing(db):
    sec = Sec(listing(20))
    await step(db, sec)
    second = await step(db, sec, now=NOW + timedelta(minutes=1))
    third = await step(db, sec, now=NOW + timedelta(minutes=2))

    assert sec.listings == 1
    assert len(sec.fetched) == len(set(sec.fetched)) == 20
    assert (second.requests, second.remaining, third.requests, third.remaining) == (STEP_FILINGS, 4, 4, 0)
    scan = scan_row(db)
    assert (scan.status, scan.steps) == ("idle", 3)
    assert set(statuses(db).values()) == {"ok"}

    fourth = await step(db, sec, now=NOW + timedelta(minutes=3))
    assert (fourth.requests, fourth.stored, sec.requests) == (0, 0, 21)   # a complete scan costs nothing to ask again


@pytest.mark.asyncio
async def test_the_listing_is_read_again_after_its_hour_and_only_new_filings_are_fetched(db):
    sec = Sec(listing(3))
    await step(db, sec)
    sec.filings = listing(5)
    early = await step(db, sec, now=NOW + LIST_TTL - timedelta(seconds=1))
    late = await step(db, sec, now=NOW + LIST_TTL)

    assert (early.requests, late.listed, late.requests) == (0, 2, 3)
    assert sec.fetched[3:] == [xml_url(5), xml_url(4)]
    assert db.query(InsiderTransaction).count() == 5


@pytest.mark.asyncio
async def test_a_listing_longer_than_the_scan_keeps_is_cut_to_the_most_recent(db):
    sec = Sec(listing(MAX_FILINGS + 15))
    stats = await step(db, sec)

    assert stats.listed == MAX_FILINGS
    assert min(statuses(db)) == accession(16)


# --- where the document is -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_filing_whose_xml_is_not_at_that_name_is_read_from_the_submission_text(db):
    sec = Sec(listing(4))
    sec.answers = {
        xml_url(4): EdgarNotFoundError("gone"), text_url(4): submission_text(sec.document, accession=accession(4)),
        xml_url(3): EdgarNotFoundError("gone"), text_url(3): "<SEC-DOCUMENT>a paper filing, scanned</SEC-DOCUMENT>",
        xml_url(2): EdgarNotFoundError("gone"), text_url(2): EdgarNotFoundError("gone"),
    }
    stats = await step(db, sec)

    assert sec.fetched == [xml_url(4), text_url(4), xml_url(3), text_url(3), xml_url(2), text_url(2), xml_url(1)]
    assert stats.requests == 8
    assert statuses(db) == {accession(4): "ok", accession(3): "no_xml", accession(2): "not_found", accession(1): "ok"}
    assert (stats.stored, stats.no_xml, stats.not_found, stats.remaining) == (2, 1, 1, 0)
    assert scan_row(db).status == "idle"   # every filing has an outcome: none is asked for again


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_document", [None, "primary_doc.html", "../../etc/x.xml/", "xslF345X05/bad name.xml"])
async def test_a_listing_without_a_usable_xml_name_goes_straight_to_the_submission_text(db, primary_document):
    sec = Sec(listing(1, document=primary_document))
    sec.answers = {text_url(1): submission_text(sec.document, accession=accession(1))}
    stats = await step(db, sec)

    assert sec.fetched == [text_url(1)]
    assert (stats.requests, stats.stored) == (2, 1)


@pytest.mark.asyncio
async def test_an_unreadable_form_4_is_recorded_and_the_step_carries_on(db):
    sec = Sec(listing(3))
    sec.answers = {xml_url(3): "<ownershipDocument><documentType>4</documentType></ownershipDocument>",
                   xml_url(2): form4(document_type="3")}
    stats = await step(db, sec)

    assert (stats.failed, stats.stored, stats.stopped) == (2, 1, None)
    assert statuses(db) == {accession(3): "failed", accession(2): "failed", accession(1): "ok"}
    failed = db.query(InsiderFiling).filter_by(accession=accession(3)).one()
    assert failed.error_type and failed.parser_version == scan_service.PARSER_VERSION and failed.attempted_at is not None
    assert scan_row(db).status == "idle"


THROTTLE_PAGE = "<html><head><title>SEC.gov | Request Rate Threshold Exceeded</title></head><body></body></html>"


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["at the XML's address", "at the text file's address"])
async def test_a_200_that_is_not_the_document_stops_the_step_and_only_a_second_one_fails_the_filing(db, where):
    """An error or throttle page served with a 200, or a cut-off answer, says nothing lasting about the filing."""
    sec = Sec(listing(3, document="xslF345X05/form4.xml" if where.startswith("at the XML") else None))
    bad = xml_url(3) if where.startswith("at the XML") else text_url(3)
    sec.answers = {text_url(n): submission_text(sec.document, accession=accession(n)) for n in (1, 2, 3)}
    sec.answers[bad] = THROTTLE_PAGE
    first = await step(db, sec)

    assert (first.stopped, first.stored, first.failed, sec.fetched) == ("sec_unexpected_body", 0, 0, [bad])
    row = db.query(InsiderFiling).filter_by(accession=accession(3)).one()
    assert (row.status, row.error_type) == ("listed", "unexpected_body")
    scan = scan_row(db)
    assert (scan.status, scan.error_code, utc(scan.paused_until)) == ("paused", "sec_unexpected_body", NOW + PAUSE_BASE)

    second = await step(db, sec, now=NOW + PAUSE_BASE)   # the same answer again: this filing is given up
    assert (second.stopped, second.failed, second.remaining, len(sec.fetched)) == ("sec_unexpected_body", 1, 2, 2)
    assert statuses(db)[accession(3)] == "failed"

    third = await step(db, sec, now=NOW + PAUSE_BASE * 3)   # and the issuer's other filings are reached
    assert (third.stopped, third.stored, third.remaining) == (None, 2, 0)


@pytest.mark.asyncio
async def test_a_good_answer_after_an_unexpected_one_stores_the_filing(db):
    sec = Sec(listing(1))
    sec.answers = {xml_url(1): "   "}
    await step(db, sec)
    sec.answers = {}
    stats = await step(db, sec, now=NOW + PAUSE_BASE)

    row = db.query(InsiderFiling).filter_by(accession=accession(1)).one()
    db.refresh(row)
    assert (stats.stored, row.status, row.error_type) == (1, "ok", None)


@pytest.mark.asyncio
async def test_a_listed_accession_no_address_can_be_built_from_is_left_out(db):
    good = listing(2)
    sec = Sec([ListedFiling("not-an-accession", date(2026, 3, 1), "form4.xml"),
               ListedFiling("0000999999-26-0000011", date(2026, 3, 1), "form4.xml"), *good])
    stats = await step(db, sec)

    assert (stats.listed, stats.stored, stats.stopped, stats.remaining) == (2, 2, None, 0)
    assert set(statuses(db)) == {accession(1), accession(2)}
    assert scan_row(db).status == "idle"


@pytest.mark.asyncio
async def test_the_holder_of_the_lease_decides_from_the_row_as_it_stands_after_the_claim(db, monkeypatch):
    """Another step can list and release between this step's first read and its claim."""
    sec = Sec(listing(2))
    real_claim = scan_service._claim

    def another_step_listed_just_before(session, cik, token, now):
        session.query(InsiderScan).update({"last_listed_at": now, "pauses": 3})
        session.commit()
        return real_claim(session, cik, token, now)

    monkeypatch.setattr(scan_service, "_claim", another_step_listed_just_before)
    stats = await step(db, sec)
    assert (sec.listings, stats.requests) == (0, 0)   # no second listing within the hour

    db.add(InsiderFiling(accession=accession(1), issuer_cik=CIK, filed_date=date(2026, 1, 2),
                         primary_document="form4.xml", status="listed", created_at=NOW, updated_at=NOW))
    db.commit()
    sec.answers = {xml_url(1): refused(403)}
    await step(db, sec, now=NOW + timedelta(minutes=1))
    scan = scan_row(db)
    assert (scan.pauses, utc(scan.paused_until)) == (4, NOW + timedelta(minutes=1) + PAUSE_BASE * 8)


@pytest.mark.asyncio
async def test_a_filing_stored_twice_holds_its_trades_once(db):
    sec = Sec(listing(1), document=form4(trades=[trade("P", "1", "1.00", "2026-10-01"), trade("S", "2", "2.00", "2026-10-02")]))
    await step(db, sec)
    db.query(InsiderFiling).update({"status": "listed"})
    db.commit()
    await step(db, sec, now=NOW + timedelta(minutes=1))

    assert [(row.ordinal, row.transaction_code) for row in db.query(InsiderTransaction).order_by(InsiderTransaction.ordinal)] == [(0, "P"), (1, "S")]


@pytest.mark.asyncio
async def test_a_filing_this_company_made_as_an_owner_of_another_issuers_shares_stores_no_trades(db):
    """SEC lists a Form 4 under its issuer and under each reporting owner, so a company that holds another
    issuer's shares has those filings in its own listing. They are not insider activity at this company."""
    sec = Sec(listing(3))
    other = form4(issuer_cik="0000320193", ticker="OTHR", trades=[trade("S", "5000", "20.00", "2026-10-01")])
    sec.answers = {xml_url(3): other, xml_url(2): form4(issuer_cik="", trades=[trade("P", "1", "1.00", "2026-10-01")])}
    stats = await step(db, sec)

    assert statuses(db) == {accession(3): "not_issuer", accession(2): "not_issuer", accession(1): "ok"}
    assert (stats.not_issuer, stats.stored, stats.trades, stats.remaining) == (2, 1, 1, 0)
    assert [row.accession for row in db.query(InsiderTransaction)] == [accession(1)]
    assert scan_row(db).status == "idle"


@pytest.mark.asyncio
async def test_an_accession_in_two_issuers_listings_keeps_a_row_for_each_and_its_trades_once(db):
    sec = Sec(listing(1))   # the document names issuer 999999
    await step(db, sec)
    owner_filer = await run_scan_step(db, "555", now=NOW, list_filings=sec.list_filings, fetch_document=sec.fetch)

    assert (owner_filer.listed, owner_filer.not_issuer, owner_filer.stored) == (1, 1, 0)
    db.expire_all()
    assert {(row.issuer_cik, row.status) for row in db.query(InsiderFiling)} == {(CIK, "ok"), ("555", "not_issuer")}
    assert [(row.issuer_cik, row.accession) for row in db.query(InsiderTransaction)] == [(CIK, accession(1))]


# --- pushback ------------------------------------------------------------------------------------------------


def refused(status: int) -> EdgarError:
    return EdgarError("SEC document request refused", code="EDGAR_HTTP_REFUSED", context={"status_code": status})


PUSHBACK = [
    pytest.param(refused(403), "sec_403", PAUSE_BASE, id="403"),
    pytest.param(EdgarRateLimitError(retry_after=60), "sec_429", PAUSE_BASE, id="429"),
    pytest.param(EdgarRateLimitError(retry_after=1800), "sec_429", timedelta(minutes=30), id="429-long-retry-after"),
    pytest.param(EdgarRateLimitError(retry_after=10**6), "sec_429", PAUSE_MAX, id="429-absurd-retry-after"),
    pytest.param(EdgarNetworkError("SEC document server failed", context={"status_code": 503}), "sec_unavailable", PAUSE_BASE, id="503"),
    pytest.param(EdgarTimeoutError(timeout_seconds=10), "sec_timeout", PAUSE_BASE, id="timeout"),
    pytest.param(CircuitOpenError("edgar", "open", 30.0), "breaker_open", PAUSE_BASE, id="breaker"),
    pytest.param(EdgarError("SEC EDGAR circuit breaker is open", cause=CircuitOpenError("edgar", "open", 30.0)),
                 "breaker_open", PAUSE_BASE, id="breaker-as-the-fetch-wraps-it"),
    pytest.param(EdgarError("Failed to fetch document: boom"), "sec_refused", PAUSE_BASE, id="unclassified"),
    pytest.param(RuntimeError("boom"), "error_RuntimeError", PAUSE_BASE, id="not-an-edgar-error"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("error, code, pause", PUSHBACK)
async def test_the_step_stops_at_the_first_pushback_and_the_scan_waits(db, error, code, pause):
    sec = Sec(listing(6))
    sec.answers = {xml_url(4): error}
    stats = await step(db, sec)

    assert sec.fetched == [xml_url(6), xml_url(5), xml_url(4)]   # nothing after the refusal, and no text fallback
    assert (stats.stopped, stats.stored, stats.remaining) == (code, 2, 4)
    scan = scan_row(db)
    assert (scan.status, scan.error_code, scan.pauses, scan.lease_token) == ("paused", code, 1, None)
    assert utc(scan.paused_until) == NOW + pause
    assert statuses(db)[accession(4)] == "listed"   # it is fetched when the scan resumes

    waiting = await step(db, sec, now=NOW + pause - timedelta(seconds=1))
    assert (waiting.outcome, waiting.requests, waiting.remaining, len(sec.fetched)) == ("paused", 0, 4, 3)

    sec.answers = {}
    resumed = await step(db, sec, now=NOW + pause)
    assert (resumed.outcome, resumed.stored, resumed.remaining) == ("ran", 4, 0)
    assert sec.listings == (2 if pause >= LIST_TTL else 1)   # a wait past the listing's hour reads it again
    scan = scan_row(db)
    assert (scan.status, scan.error_code, scan.pauses, scan.paused_until) == ("idle", None, 0, None)


@pytest.mark.asyncio
async def test_each_pushback_in_a_row_doubles_the_wait_up_to_its_ceiling(db):
    sec = Sec(listing(1))
    sec.answers = {xml_url(1): refused(403)}
    now, waits = NOW, []
    for _ in range(9):
        await step(db, sec, now=now)
        scan = scan_row(db)
        waits.append(utc(scan.paused_until) - now)
        now = utc(scan.paused_until)

    assert waits[:4] == [PAUSE_BASE, PAUSE_BASE * 2, PAUSE_BASE * 4, PAUSE_BASE * 8]
    assert waits[-1] == PAUSE_MAX and scan_row(db).pauses == 9
    assert len(sec.fetched) == 9   # one request per wait, however long SEC keeps refusing


@pytest.mark.asyncio
@pytest.mark.parametrize("error, code", [
    # The listing's errors are edgartools' own, translated by their text (translate_edgartools_exception): a
    # refusal arrives as a plain EdgarError with no status.
    pytest.param(translate_edgartools_exception(RuntimeError("403 Client Error: Forbidden")), "sec_refused", id="403"),
    pytest.param(translate_edgartools_exception(RuntimeError("429 Too Many Requests")), "sec_429", id="429"),
    pytest.param(translate_edgartools_exception(RuntimeError("Connection reset by peer")), "sec_unavailable", id="network"),
    pytest.param(CircuitOpenError("edgar", "open", 30.0), "breaker_open", id="breaker"),
    pytest.param(EdgarTimeoutError(timeout_seconds=20), "sec_timeout", id="timeout"),
])
async def test_pushback_on_the_listing_stops_the_step_before_any_document(db, error, code):
    sec = Sec(listing(3))
    sec.list_error = error
    stats = await step(db, sec)

    assert (sec.requests, stats.requests, stats.stopped, stats.remaining) == (1, 1, code, 0)
    scan = scan_row(db)
    assert (scan.status, scan.error_code, scan.last_listed_at) == ("paused", code, None)


@pytest.mark.asyncio
async def test_a_wait_on_this_process_own_limiter_ends_the_step_without_a_pause(db):
    sec = Sec(listing(3))
    sec.answers = {xml_url(2): EdgarError("SEC document deadline expired while waiting", code="EDGAR_WAIT_TIMEOUT",
                                          context={"phase": "admission"})}
    stats = await step(db, sec)

    assert (stats.stopped, stats.stored, stats.remaining) == ("limiter_wait", 1, 2)
    scan = scan_row(db)
    assert (scan.status, scan.paused_until, scan.pauses, scan.error_code) == ("scanning", None, 0, None)
    again = await step(db, Sec(listing(3)), now=NOW + timedelta(seconds=30))
    assert (again.outcome, again.stored) == ("ran", 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [CompanyNotFoundError("999999"), EdgarNotFoundError("no such filer")])
async def test_an_issuer_sec_does_not_know_fails_the_scan_and_is_not_asked_about_at_once(db, error):
    sec = Sec([])
    sec.list_error = error
    stats = await step(db, sec)

    scan = scan_row(db)
    assert (stats.stopped, scan.status, scan.error_code) == ("issuer_not_found", "failed", "issuer_not_found")
    assert utc(scan.paused_until) == NOW + PAUSE_BASE
    assert (await step(db, sec, now=NOW + timedelta(minutes=1))).outcome == "paused" and sec.listings == 1


@pytest.mark.asyncio
async def test_an_edgartools_the_parser_was_not_written_for_fails_the_scan_before_any_request(db, monkeypatch):
    monkeypatch.setattr(scan_service, "parser_supported", lambda: False)
    sec = Sec(listing(3))
    stats = await step(db, sec)

    scan = scan_row(db)
    assert (sec.requests, stats.requests, stats.stopped) == (0, 0, "parser_unsupported")
    assert (scan.status, scan.error_code, scan.paused_until, scan.lease_token) == ("failed", "parser_unsupported", None, None)

    monkeypatch.setattr(scan_service, "parser_supported", lambda: True)   # the deploy that fixes it carries straight on
    assert (await step(db, sec, now=NOW + timedelta(seconds=5))).stored == 3
    assert scan_row(db).status == "idle"


# --- the lease -----------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_step_does_nothing_while_another_holds_the_lease_and_takes_over_once_it_runs_out(db):
    sec = Sec(listing(2))
    db.add(InsiderScan(issuer_cik=CIK, status="scanning", lease_token="another", lease_until=NOW + LEASE,
                       pauses=0, steps=0, created_at=NOW, updated_at=NOW))
    db.commit()

    held = await step(db, sec, now=NOW + LEASE - timedelta(seconds=1))
    assert (held.outcome, held.requests, sec.requests) == ("busy", 0, 0)
    assert scan_row(db).lease_token == "another"

    taken = await step(db, sec, now=NOW + LEASE)
    assert (taken.outcome, taken.stored) == ("ran", 2)


@pytest.mark.asyncio
async def test_a_step_that_lost_its_lease_stores_nothing_more_and_leaves_the_new_owners_lease_alone(db):
    sec = Sec(listing(3))
    real_fetch = sec.fetch

    async def fetch_and_lose_the_lease(url: str) -> str:
        if url == xml_url(2):
            db.query(InsiderScan).update({"lease_token": "taker", "lease_until": NOW + LEASE})
            db.commit()
        return await real_fetch(url)

    stats = await run_scan_step(db, CIK, now=NOW, list_filings=sec.list_filings, fetch_document=fetch_and_lose_the_lease)

    assert (stats.stopped, stats.stored) == ("lease_lost", 1)
    assert sec.fetched == [xml_url(3), xml_url(2)]
    assert statuses(db) == {accession(3): "ok", accession(2): "listed", accession(1): "listed"}
    assert db.query(InsiderTransaction).count() == 1
    scan = scan_row(db)
    assert (scan.lease_token, scan.steps) == ("taker", 0)


@pytest.mark.asyncio
async def test_a_session_with_pending_work_is_refused(db):
    db.add(InsiderScan(issuer_cik="5", status="idle", pauses=0, steps=0, created_at=NOW, updated_at=NOW))
    with pytest.raises(RuntimeError, match="no pending writes"):
        await step(db, Sec([]))


@pytest.mark.asyncio
async def test_the_issuer_is_stored_under_its_cik_without_leading_zeros(db):
    sec = Sec(listing(1))
    await run_scan_step(db, "0000999999", now=NOW, list_filings=sec.list_filings, fetch_document=sec.fetch)
    assert (scan_row(db).issuer_cik, sec.fetched) == (CIK, [xml_url(1)])
    with pytest.raises(ValueError):
        await run_scan_step(db, "not-a-cik", now=NOW, list_filings=sec.list_filings, fetch_document=sec.fetch)


# --- what the defaults ask SEC for ----------------------------------------------------------------------------


def test_the_default_listing_is_the_recent_window_without_amendments(monkeypatch):
    import edgar

    calls = []

    class Filing:
        def __init__(self, n: int):
            self.accession_no, self.filing_date, self.primary_document = accession(n), date(2026, 3, 1), "xslF345X05/form4.xml"

    class Company:
        def __init__(self, cik):
            calls.append(("company", cik))

        def get_filings(self, **kwargs):
            calls.append(("get_filings", kwargs))
            return iter(Filing(n) for n in range(MAX_FILINGS + 40, 0, -1))

    monkeypatch.setattr(edgar, "Company", Company)
    listed = scan_service._list_form4s_sync(CIK)

    # trigger_full_load=False keeps it to one submissions request; without it edgartools pages the full history.
    assert calls == [("company", 999999), ("get_filings", {"form": "4", "amendments": False, "trigger_full_load": False})]
    assert len(listed) == MAX_FILINGS
    assert listed[0] == ListedFiling(accession(MAX_FILINGS + 40), date(2026, 3, 1), "xslF345X05/form4.xml")


@pytest.mark.asyncio
async def test_the_default_fetch_is_one_attempt_through_the_shared_transport(monkeypatch):
    from app.services.edgar import compat

    calls = []

    async def get_filing_document(url, timeout=None, max_retries=3):
        calls.append((url, timeout, max_retries))
        return "text"

    monkeypatch.setattr(compat.sec_edgar_service, "get_filing_document", get_filing_document)
    assert await scan_service._default_fetch(xml_url(1)) == "text"
    assert calls == [(xml_url(1), scan_service.FETCH_TIMEOUT_SECONDS, 1)]


# --- the real transport's errors ---------------------------------------------------------------------------------


def through_the_real_transport(monkeypatch, respond):
    """``_default_fetch`` over ``sec_edgar_service.get_filing_document`` itself, with SEC played by a mock
    transport: what the scan concludes from a status is tied to how the transport reports that status."""
    import httpx

    from app.services.edgar import compat
    from app.services.edgar.circuit_breaker import CircuitBreaker

    real_client = httpx.AsyncClient

    async def execute(fn):
        return await fn()

    monkeypatch.setattr(compat, "edgar_circuit_breaker", CircuitBreaker("insider-scan-test"))
    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    monkeypatch.setattr(compat.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(respond)))


@pytest.mark.asyncio
@pytest.mark.parametrize("status, headers, code, pause", [
    (403, {}, "sec_403", PAUSE_BASE),
    (429, {"Retry-After": "1800"}, "sec_429", timedelta(minutes=30)),
    (429, {}, "sec_429", PAUSE_BASE),
    (503, {}, "sec_unavailable", PAUSE_BASE),
    (500, {}, "sec_unavailable", PAUSE_BASE),
    (401, {}, "sec_401", PAUSE_BASE),
])
async def test_each_refusing_status_from_the_real_transport_stops_and_pauses_the_scan(db, monkeypatch, status, headers, code, pause):
    import httpx

    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(status, headers=headers, text="refused")

    through_the_real_transport(monkeypatch, respond)
    sec = Sec(listing(3))
    stats = await run_scan_step(db, CIK, now=NOW, list_filings=sec.list_filings)

    assert requests == [xml_url(3)]   # one attempt, no retry, no text fallback, nothing after it
    assert (stats.stopped, stats.stored, stats.remaining) == (code, 0, 3)
    scan = scan_row(db)
    assert (scan.status, scan.error_code, utc(scan.paused_until)) == ("paused", code, NOW + pause)


@pytest.mark.asyncio
async def test_a_404_from_the_real_transport_falls_back_to_the_text_file_and_a_second_404_is_not_found(db, monkeypatch):
    import httpx

    document = form4(trades=[trade("P", "100", "10.00", "2026-10-01")])

    def respond(request):
        url = str(request.url)
        if url == text_url(2):
            return httpx.Response(200, text=submission_text(document, accession=accession(2)))
        return httpx.Response(404, text="not here")

    through_the_real_transport(monkeypatch, respond)
    sec = Sec(listing(2))
    stats = await run_scan_step(db, CIK, now=NOW, list_filings=sec.list_filings)

    assert (stats.stopped, stats.stored, stats.not_found, stats.requests) == (None, 1, 1, 5)
    assert statuses(db) == {accession(2): "ok", accession(1): "not_found"}
    assert scan_row(db).status == "idle"
