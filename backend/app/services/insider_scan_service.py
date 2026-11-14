"""The scan that fills an issuer's stored Form 4 trades, a few filings at a time (ADR 0009).

One step: claim the issuer's scan row under a lease; list its Form 4s when the last listing is over an hour old
(one request); fetch and parse at most ``STEP_FILINGS`` filings that have no outcome yet, newest first, committing
each; release the lease. A step that leaves filings listed says so, and its caller enqueues the next. Nothing here
waits on a request: the task worker runs it (or, with durable tasks off, the process after the response).

The step stops itself the moment SEC pushes back, because nothing else will: the circuit breaker does not count a
403, and edgartools' own client is not involved. A stopped scan records why and when it may run again.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from itertools import islice
from typing import Awaitable, Callable, Optional

from sqlalchemy import delete, func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.insider import InsiderFiling, InsiderScan, InsiderTransaction
from app.services.insider_form4 import (
    PARSER_VERSION,
    Form4ParseError,
    ownership_document_in,
    parse_form4,
    parser_supported,
)
from app.utils.datetimes import ensure_utc, utcnow
from app.utils.sec_urls import (
    build_sec_document_url,
    build_sec_submission_text_url,
    normalize_accession,
    normalize_cik,
)

logger = logging.getLogger(__name__)

# The most recent Form 4s a scan keeps for an issuer, and how many one step fetches. A fetch is one SEC request
# at the process's one request a second, so a step is about ten seconds of the task worker.
MAX_FILINGS = 60
STEP_FILINGS = 8
LIST_TTL = timedelta(hours=1)
# Longer than a step can take (a listing and STEP_FILINGS fetches of FETCH_TIMEOUT_SECONDS each, with their text
# fallbacks), so a lease only expires on a step that died.
LEASE = timedelta(minutes=5)
FETCH_TIMEOUT_SECONDS = 10.0
# After pushback with no Retry-After: five minutes, doubling, to six hours.
PAUSE_BASE = timedelta(minutes=5)
PAUSE_MAX = timedelta(hours=6)

SCAN_IDLE, SCAN_SCANNING, SCAN_PAUSED, SCAN_FAILED = "idle", "scanning", "paused", "failed"
FILING_LISTED, FILING_OK, FILING_NO_XML, FILING_NOT_FOUND, FILING_FAILED = "listed", "ok", "no_xml", "not_found", "failed"
# SEC lists a Form 4 under its issuer and under each reporting owner. A company that owns another issuer's shares
# has those filings in its own listing: they report the other issuer's shares, and are no insider activity here.
FILING_NOT_ISSUER = "not_issuer"
# A 200 whose body is neither a Form 4 document nor a submission's text file (an error or throttle page, a
# truncated answer). Nothing permanent is concluded from it the first time: the step stops as on pushback and the
# filing stays listed with this as its error. The same answer on the next attempt stores the filing as failed, so
# one bad filing cannot hold an issuer's scan for good.
UNEXPECTED_BODY = "unexpected_body"
# A submission's text file whole: it opens and closes with these, so one cut off part-way is not taken for a
# filing with no ownership document.
_SUBMISSION_TEXT_RE = re.compile(r"<SEC-DOCUMENT>.*</SEC-DOCUMENT>", re.DOTALL)

# What a step did: ran (it held the lease), busy (another step holds it), paused (not before paused_until).
OUTCOME_RAN, OUTCOME_BUSY, OUTCOME_PAUSED = "ran", "busy", "paused"


@dataclass(frozen=True)
class ListedFiling:
    accession: str
    filed_date: Optional[date]
    primary_document: Optional[str]


@dataclass
class StepStats:
    outcome: str = OUTCOME_RAN
    listed: int = 0          # filings a fresh listing added
    requests: int = 0        # SEC requests this step made, the listing included
    stored: int = 0          # filings parsed and stored
    trades: int = 0          # open-market trades in them
    not_issuer: int = 0      # filings this issuer made as an owner of another issuer's shares
    no_xml: int = 0
    not_found: int = 0
    failed: int = 0
    remaining: int = 0       # filings still listed, for the next step
    stopped: Optional[str] = None   # why the step ended early, when it did
    duration_ms: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


# What a reader of the stored trades is told about the scan behind them.
VIEW_COMPLETE, VIEW_SCANNING, VIEW_PAUSED, VIEW_FAILED = "complete", "scanning", "paused", "failed"
# How soon to ask again while a scan is under way, and the longest a reader is told to wait.
POLL_SECONDS = 8
MAX_POLL_SECONDS = 180
# One on-visit handoff per issuer a minute, however many readers ask (the bucket goes into the task's name).
VISIT_DEDUPE_SECONDS = 60
# After a wait on the process's own limiter, the next step starts this much later.
LIMITER_RETRY = timedelta(seconds=15)
# A scan whose row moved this recently is being carried on by its own chain of tasks: each step enqueues the next,
# so a visit hands nothing off. Past it with filings still unread, the chain broke and a visit restarts it.
CHAIN_QUIET = timedelta(seconds=45)
# Issuers scanning at once, across every process (read from the scan rows). The worker runs one task at a time and
# also sends account mail: a step is about ten seconds, and a mail queued behind the steps waits about one step per
# scan under way. A reader of a further issuer is served what is stored and told to ask again.
MAX_SCANS_UNDER_WAY = 3
UNDER_WAY_WINDOW = timedelta(minutes=5)


@dataclass(frozen=True)
class ScanView:
    status: str                          # complete | scanning | paused | failed
    filings_listed: int                  # Form 4s the scan knows of
    filings_read: int                    # of those, the ones with an outcome
    oldest_filed_date: Optional[date]    # the earliest filing read: how far back the stored trades reach
    refreshed_at: Optional[datetime]     # when the issuer's filings were last listed
    retry_after_seconds: Optional[int]   # when asking again can show more; None when nothing is pending
    due: bool                            # a step would do something now


Lister = Callable[[str], Awaitable[list[ListedFiling]]]
FetchDocument = Callable[[str], Awaitable[str]]


class _UnexpectedBody(Exception):
    """SEC answered 200 with something that is not the document asked for."""


class _Stop(Exception):
    """Ends the step. ``pause`` says whether SEC pushed back (the scan waits) or the step merely ran out."""

    def __init__(self, code: str, *, pause: bool, retry_after: Optional[float] = None):
        super().__init__(code)
        self.code, self.pause, self.retry_after = code, pause, retry_after


def _stop_for(exc: Exception) -> _Stop:
    """What an error from a fetch or a listing means for the scan, told by type, code and status."""
    from app.services.edgar.circuit_breaker import CircuitOpenError
    from app.services.edgar.exceptions import EdgarError, EdgarNetworkError, EdgarRateLimitError, EdgarTimeoutError

    # The document fetch hands the breaker's refusal on wrapped in an EdgarError; the listing raises it bare.
    breaker = exc if isinstance(exc, CircuitOpenError) else getattr(exc, "cause", None)
    if isinstance(breaker, CircuitOpenError):
        return _Stop("breaker_open", pause=True, retry_after=breaker.time_until_recovery)
    if isinstance(exc, EdgarRateLimitError):
        return _Stop("sec_429", pause=True, retry_after=exc.retry_after)
    if isinstance(exc, EdgarTimeoutError):
        return _Stop("sec_timeout", pause=True)
    if isinstance(exc, EdgarNetworkError):
        return _Stop("sec_unavailable", pause=True)
    if isinstance(exc, EdgarError):
        if exc.code == "EDGAR_WAIT_TIMEOUT":
            # The process's own limiter was busy. That says nothing about SEC: the next step carries on.
            return _Stop("limiter_wait", pause=False)
        status = exc.context.get("status_code")
        return _Stop(f"sec_{status}" if isinstance(status, int) else "sec_refused", pause=True)
    return _Stop(f"error_{type(exc).__name__}"[:60], pause=True)


async def _default_fetch(url: str) -> str:
    from app.services.edgar.compat import sec_edgar_service

    return await sec_edgar_service.get_filing_document(url, timeout=FETCH_TIMEOUT_SECONDS, max_retries=1)


def _list_form4s_sync(issuer_cik: str) -> list[ListedFiling]:
    from edgar import Company as EdgarCompany  # lazy: heavy dependency

    from app.services.ownership_extractor import _iso_date, _safe_getattr

    # The recent window only (one submissions request) and no amendments: the listing the live path made
    # (insider_service). The executor that runs this translates whatever edgartools raises.
    filings = EdgarCompany(int(issuer_cik)).get_filings(form="4", amendments=False, trigger_full_load=False)
    listed: list[ListedFiling] = []
    for filing in islice(filings, MAX_FILINGS):
        accession = str(_safe_getattr(filing, "accession_no") or _safe_getattr(filing, "accession_number") or "")
        if not accession:
            continue
        filed = _iso_date(_safe_getattr(filing, "filing_date"))
        listed.append(ListedFiling(
            accession=accession,
            filed_date=date.fromisoformat(filed) if filed else None,
            primary_document=str(_safe_getattr(filing, "primary_document") or "") or None,
        ))
    return listed


async def _default_list(issuer_cik: str) -> list[ListedFiling]:
    from app.services.edgar.async_executor import run_with_circuit_breaker

    return await run_with_circuit_breaker(lambda: _list_form4s_sync(issuer_cik), timeout=FETCH_TIMEOUT_SECONDS * 2)


def get_or_create_scan(db: Session, issuer_cik: str, now: datetime) -> InsiderScan:
    cik = normalize_cik(issuer_cik)
    scan = db.query(InsiderScan).filter(InsiderScan.issuer_cik == cik).first()
    if scan is not None:
        return scan
    db.add(InsiderScan(issuer_cik=cik, status=SCAN_SCANNING, pauses=0, steps=0, created_at=now, updated_at=now))
    try:
        db.commit()
    except IntegrityError:  # another process created it between the read and the write
        db.rollback()
    return db.query(InsiderScan).filter(InsiderScan.issuer_cik == cik).one()


def _claim(db: Session, cik: str, token: str, now: datetime) -> bool:
    """Unowned (or its lease ran out) and not paused → owned by ``token``. True iff this step now holds it."""
    stmt = update(InsiderScan).where(
        InsiderScan.issuer_cik == cik,
        or_(InsiderScan.lease_until.is_(None), InsiderScan.lease_until <= now),
        or_(InsiderScan.paused_until.is_(None), InsiderScan.paused_until <= now),
    ).values(lease_until=now + LEASE, updated_at=now, lease_token=token)
    claimed = db.execute(stmt.execution_options(synchronize_session=False)).rowcount == 1
    db.commit()
    return claimed


def _write_scan(db: Session, cik: str, token: str, now: datetime, **values) -> bool:
    """One fenced update of the scan row; True iff ``token`` still held the lease. Does not commit."""
    stmt = update(InsiderScan).where(InsiderScan.issuer_cik == cik, InsiderScan.lease_token == token).values(
        updated_at=now, **values)
    return db.execute(stmt.execution_options(synchronize_session=False)).rowcount == 1


def _store_listing(db: Session, cik: str, listed: list[ListedFiling], now: datetime) -> int:
    known = {row.accession for row in db.query(InsiderFiling.accession).filter(InsiderFiling.issuer_cik == cik)}
    added = 0
    for filing in listed:
        try:   # the listing is SEC's data: an accession no address can be built from is left out here (rule 9)
            digits = normalize_accession(filing.accession)
        except ValueError:
            logger.warning("Insider scan for CIK %s: a listed accession is not one, left out", cik)
            continue
        accession = f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"   # stored in SEC's one dashed spelling
        if accession in known:
            continue
        known.add(accession)
        db.add(InsiderFiling(
            accession=accession, issuer_cik=cik, filed_date=filing.filed_date,
            primary_document=(filing.primary_document or "")[:255] or None,
            status=FILING_LISTED, created_at=now, updated_at=now,
        ))
        added += 1
    return added


def _to_fetch(db: Session, cik: str) -> list[InsiderFiling]:
    """Filings with no outcome yet, newest first."""
    return (
        db.query(InsiderFiling)
        .filter(InsiderFiling.issuer_cik == cik, InsiderFiling.status == FILING_LISTED)
        .order_by(InsiderFiling.filed_date.desc().nullslast(), InsiderFiling.accession.desc())
        .limit(STEP_FILINGS)
        .all()
    )


def _remaining(db: Session, cik: str) -> int:
    return db.query(InsiderFiling).filter(InsiderFiling.issuer_cik == cik, InsiderFiling.status == FILING_LISTED).count()


def _document_name(primary_document: Optional[str]) -> Optional[str]:
    """The Form 4's XML as SEC serves it: the listing names the rendered view, ``xslF345X05/form4.xml``, and the
    document itself is the same file name in the filing's folder."""
    name = (primary_document or "").rsplit("/", 1)[-1].strip()
    return name if name.lower().endswith(".xml") else None


async def _fetch_document(cik: str, filing: InsiderFiling, fetch: FetchDocument, stats: StepStats) -> Optional[str]:
    """The filing's ownership document, or None when SEC has the filing but no such document in it. The XML is
    asked for at the listing's file name; a 404 there, or a listing that names no usable XML, goes to the
    submission's text file. Raises ``EdgarNotFoundError`` when the filing itself is not there, ``_UnexpectedBody``
    for a 200 that is neither, and whatever the transport raises otherwise."""
    from app.services.edgar.exceptions import EdgarNotFoundError

    name = _document_name(filing.primary_document)
    try:
        url = build_sec_document_url(cik, filing.accession, name) if name else None
    except ValueError:
        url = None  # a name the builder refuses is never requested
    if url is not None:
        stats.requests += 1
        try:
            body = await fetch(url)
        except EdgarNotFoundError:
            pass  # not at that name: the submission's text file holds every document
        else:
            document = ownership_document_in(body)
            if document is None:
                raise _UnexpectedBody()
            return document
    stats.requests += 1
    text = await fetch(build_sec_submission_text_url(cik, filing.accession))
    document = ownership_document_in(text)
    if document is None and not _SUBMISSION_TEXT_RE.search(text or ""):
        raise _UnexpectedBody()
    return document


def _store_outcome(db: Session, cik: str, token: str, filing_id: int, accession: str, status: str, now: datetime,
                   *, rows: Optional[list[dict]] = None, error_type: Optional[str] = None) -> bool:
    """One filing's outcome and its trades, in one transaction, only while the lease is held."""
    if not _write_scan(db, cik, token, now):
        db.rollback()
        return False
    db.execute(delete(InsiderTransaction).where(
        InsiderTransaction.accession == accession, InsiderTransaction.issuer_cik == cik))
    for ordinal, row in enumerate(rows or []):
        db.add(InsiderTransaction(
            accession=accession, ordinal=ordinal, issuer_cik=cik,
            insider_name=(row.get("insider_name") or None) and str(row["insider_name"])[:255],
            insider_title=(row.get("insider_title") or None) and str(row["insider_title"])[:255],
            is_director=row.get("is_director"), is_officer=row.get("is_officer"),
            is_ten_pct_owner=row.get("is_ten_pct_owner"),
            ticker=(row.get("ticker") or None) and str(row["ticker"])[:16],
            transaction_date=_as_date(row.get("transaction_date")),
            transaction_code=(row.get("transaction_code") or None) and str(row["transaction_code"])[:4],
            transaction_label=(row.get("transaction_label") or None) and str(row["transaction_label"])[:60],
            shares=row.get("shares"), price=row.get("price"), value=row.get("value"),
            acquired_disposed=(row.get("acquired_disposed") or None) and str(row["acquired_disposed"])[:1],
            is_10b5_1=row.get("is_10b5_1"), filed_date=_as_date(row.get("filed_date")), created_at=now,
        ))
    db.execute(
        update(InsiderFiling).where(InsiderFiling.id == filing_id).values(
            status=status, error_type=error_type, parser_version=PARSER_VERSION, attempted_at=now, updated_at=now,
        ).execution_options(synchronize_session=False)
    )
    db.commit()
    return True


def _as_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _pause_until(now: datetime, pauses: int, retry_after: Optional[float]) -> datetime:
    backoff = min(PAUSE_BASE * (2 ** min(pauses, 12)), PAUSE_MAX)
    asked = timedelta(seconds=float(retry_after)) if retry_after and retry_after > 0 else timedelta(0)
    return now + min(max(backoff, asked), PAUSE_MAX)


async def run_scan_step(
    db: Session,
    issuer_cik: str,
    *,
    now: Optional[datetime] = None,
    list_filings: Optional[Lister] = None,
    fetch_document: Optional[FetchDocument] = None,
) -> StepStats:
    """One bounded step of an issuer's scan. Returns what it did; ``remaining > 0`` asks for another step.

    The session is the caller's and must hold no pending work: every read transaction is finished before a
    request to SEC, and each filing is committed on its own (lessons/ops-finish-only-job-owned-read-transactions.md).
    """
    from app.services.edgar.exceptions import EdgarNotFoundError

    if db.new or db.dirty or db.deleted or db.in_nested_transaction():
        raise RuntimeError("run_scan_step needs a session with no pending writes or nested transaction")
    started = time.monotonic()
    clock = utcnow if now is None else (lambda: now)  # a test's fixed time stays fixed through the step
    now = clock()
    cik = normalize_cik(issuer_cik)
    list_filings, fetch_document = list_filings or _default_list, fetch_document or _default_fetch
    stats = StepStats()
    token = uuid.uuid4().hex

    scan = get_or_create_scan(db, cik, now)
    paused_until = scan.paused_until
    db.commit()
    if not _claim(db, cik, token, now):
        stats.outcome = OUTCOME_PAUSED if paused_until is not None and ensure_utc(paused_until) > now else OUTCOME_BUSY
        stats.remaining = _remaining(db, cik)
        db.commit()
        return stats

    # Read again now that the lease is held: a step that released between the read above and the claim may have
    # listed, paused or cleared a pause, and only the holder's view decides a listing or a backoff.
    last_listed_at, pauses = db.query(InsiderScan.last_listed_at, InsiderScan.pauses).filter(
        InsiderScan.issuer_cik == cik).one()
    pauses = pauses or 0
    db.commit()

    prior_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    stop: Optional[_Stop] = None
    failed_code: Optional[str] = None
    try:
        if not parser_supported():
            # The installed edgartools is not the one this parser was written against: no request is worth
            # making until a deploy fixes that, and nothing is paused, so the fixed deploy carries straight on.
            failed_code = "parser_unsupported"
            raise _Stop(failed_code, pause=False)
        if last_listed_at is None or now - ensure_utc(last_listed_at) >= LIST_TTL:
            stats.requests += 1
            try:
                listed = await list_filings(cik)
            except EdgarNotFoundError as exc:
                failed_code = "issuer_not_found"  # SEC has no such filer: waits like any other stop
                raise _Stop(failed_code, pause=True) from exc
            except Exception as exc:
                raise _stop_for(exc) from exc
            stats.listed = _store_listing(db, cik, listed[:MAX_FILINGS], now)
            if not _write_scan(db, cik, token, now, last_listed_at=now):
                db.rollback()
                raise _Stop("lease_lost", pause=False)
            db.commit()

        filings = [(row.id, row.accession, row) for row in _to_fetch(db, cik)]
        db.commit()  # the selection is read: no connection is held across the requests below
        for filing_id, accession, filing in filings:
            try:
                document = await _fetch_document(cik, filing, fetch_document, stats)
            except EdgarNotFoundError:
                stats.not_found += 1
                if not _store_outcome(db, cik, token, filing_id, accession, FILING_NOT_FOUND, clock()):
                    raise _Stop("lease_lost", pause=False)
                continue
            except _UnexpectedBody as exc:
                again = filing.error_type == UNEXPECTED_BODY
                stats.failed += int(again)
                if not _store_outcome(db, cik, token, filing_id, accession, FILING_FAILED if again else FILING_LISTED,
                                      clock(), error_type=UNEXPECTED_BODY):
                    raise _Stop("lease_lost", pause=False) from exc
                raise _Stop("sec_unexpected_body", pause=True) from exc
            except Exception as exc:
                raise _stop_for(exc) from exc
            if document is None:
                stats.no_xml += 1
                if not _store_outcome(db, cik, token, filing_id, accession, FILING_NO_XML, clock()):
                    raise _Stop("lease_lost", pause=False)
                continue
            filed = filing.filed_date.isoformat() if filing.filed_date else None
            try:
                parsed = parse_form4(document, accession=accession, filed_date=filed)
            except Form4ParseError as exc:
                stats.failed += 1
                logger.warning("Form 4 %s was not readable: %s", accession, exc)
                if not _store_outcome(db, cik, token, filing_id, accession, FILING_FAILED, clock(),
                                      error_type=str(exc)[:60]):
                    raise _Stop("lease_lost", pause=False)
                continue
            if parsed.issuer_cik != cik:
                stats.not_issuer += 1
                if not _store_outcome(db, cik, token, filing_id, accession, FILING_NOT_ISSUER, clock()):
                    raise _Stop("lease_lost", pause=False)
                continue
            if not _store_outcome(db, cik, token, filing_id, accession, FILING_OK, clock(), rows=parsed.transactions):
                raise _Stop("lease_lost", pause=False)
            stats.stored += 1
            stats.trades += len(parsed.transactions)
    except _Stop as stopped:
        stop = stopped
        db.rollback()
    finally:
        db.expire_on_commit = prior_expire_on_commit

    stats.remaining = _remaining(db, cik)
    db.commit()
    release = {"lease_token": None, "lease_until": None, "steps": InsiderScan.steps + 1}
    if stop is None:
        release.update(status=SCAN_SCANNING if stats.remaining else SCAN_IDLE, error_code=None, pauses=0, paused_until=None)
    elif stop.pause:
        stats.stopped = stop.code
        release.update(status=SCAN_FAILED if failed_code else SCAN_PAUSED, error_code=stop.code, pauses=pauses + 1,
                       paused_until=_pause_until(clock(), pauses, stop.retry_after))   # from the refusal
    elif failed_code is not None:
        stats.stopped = failed_code
        release.update(status=SCAN_FAILED, error_code=failed_code)
    else:
        stats.stopped = stop.code
        release.update(status=SCAN_SCANNING if stats.remaining else SCAN_IDLE)
    if stop is None or stop.code != "lease_lost":
        _write_scan(db, cik, token, clock(), **release)
        db.commit()
    stats.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("Insider scan step for CIK %s: %s", cik, stats.as_dict())
    return stats


def scan_view(db: Session, issuer_cik: str, *, now: Optional[datetime] = None) -> ScanView:
    """The issuer's scan as a reader of its stored trades needs it. Reads only; no request to SEC."""
    now = now or utcnow()
    cik = normalize_cik(issuer_cik)
    scan = db.query(InsiderScan).filter(InsiderScan.issuer_cik == cik).first()
    if scan is None:
        return ScanView(VIEW_SCANNING, 0, 0, None, None, POLL_SECONDS, due=True)
    listed = db.query(InsiderFiling).filter(InsiderFiling.issuer_cik == cik).count()
    unread = _remaining(db, cik)
    oldest = db.query(func.min(InsiderFiling.filed_date)).filter(
        InsiderFiling.issuer_cik == cik, InsiderFiling.status != FILING_LISTED).scalar()
    refreshed = ensure_utc(scan.last_listed_at) if scan.last_listed_at is not None else None

    def view(status: str, retry: Optional[int], due: bool) -> ScanView:
        return ScanView(status, listed, listed - unread, oldest, refreshed, retry, due)

    failed = scan.status == SCAN_FAILED
    if scan.paused_until is not None and ensure_utc(scan.paused_until) > now:
        wait = math.ceil((ensure_utc(scan.paused_until) - now).total_seconds())
        return view(VIEW_FAILED if failed else VIEW_PAUSED, min(max(wait, POLL_SECONDS), MAX_POLL_SECONDS), False)
    # A step that holds the lease, or one that released it moments ago and enqueued the next, carries the scan on.
    carried = (scan.lease_until is not None and ensure_utc(scan.lease_until) > now) or (
        scan.updated_at is not None and now - ensure_utc(scan.updated_at) < CHAIN_QUIET)
    if failed:
        return view(VIEW_FAILED, MAX_POLL_SECONDS, not carried)   # a step is cheap; the first after a fix resumes
    stale = refreshed is None or now - refreshed >= LIST_TTL
    if unread or refreshed is None:
        return view(VIEW_SCANNING, POLL_SECONDS, not carried)
    # Everything listed is read. An hour-old listing is refreshed behind what is stored, which stays complete.
    return view(VIEW_COMPLETE, POLL_SECONDS if stale else None, stale and not carried)


def scans_under_way(db: Session, *, excluding: str, now: Optional[datetime] = None) -> int:
    """How many other issuers' scans are reading filings now, in any process."""
    now = now or utcnow()
    return db.query(InsiderScan).filter(
        InsiderScan.issuer_cik != normalize_cik(excluding), InsiderScan.status == SCAN_SCANNING,
        InsiderScan.updated_at >= now - UNDER_WAY_WINDOW,
    ).count()


_local_scans: dict[str, asyncio.Task] = {}


async def request_scan(issuer_cik: str) -> bool:
    """Hand one step of the issuer's scan to the task worker; True when a step was handed off or started.

    Many readers in a minute make one task: the name carries the issuer and a one-minute bucket. Where durable
    tasks are off (development), one step runs in this process after the response, at most one per issuer.
    A queue that cannot take the task is logged and the reader is served what is stored.
    """
    from app.services.durable_tasks import enqueue_task
    from app.services.task_routing import TaskUnavailable

    cik = normalize_cik(issuer_cik)
    if settings.DURABLE_TASKS_ENABLED:
        try:
            await enqueue_task("insider_scan", {"issuer_cik": cik},
                               dedupe_key=f"insider-scan:{cik}:visit", dedupe_seconds=VISIT_DEDUPE_SECONDS)
            return True
        except (TaskUnavailable, ValueError):
            logger.warning("Insider scan handoff unavailable for CIK %s", cik)
            return False
    running = _local_scans.get(cik)
    if running is not None and not running.done():
        return False
    task = asyncio.create_task(_run_local_step(cik))
    _local_scans[cik] = task
    task.add_done_callback(lambda done, cik=cik: _local_scans.pop(cik, None) if _local_scans.get(cik) is done else None)
    return True


async def _run_local_step(cik: str) -> None:
    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            await run_scan_step(db, cik)
    except Exception:  # noqa: BLE001 - a background step has no caller to tell
        logger.exception("Insider scan step failed for CIK %s", cik)


@dataclass(frozen=True)
class _FollowUp:
    key: str
    at: Optional[datetime]


def _follow_up(db: Session, cik: str, stats: StepStats, now: datetime) -> Optional[_FollowUp]:
    """The task that continues the scan after this step, if any. Cloud Tasks keeps a task's name for a day after
    it ran and drops a second task of that name without an error, so every name carries the scan's step count,
    which moves with each step that held the lease."""
    if stats.outcome != OUTCOME_RAN or stats.stopped == "lease_lost":
        return None   # another step holds the scan, or it is paused: that step, or a visit, carries it on
    scan = db.query(InsiderScan).filter(InsiderScan.issuer_cik == cik).one()
    steps, status, paused_until = scan.steps or 0, scan.status, scan.paused_until
    db.commit()
    if stats.stopped is None:
        return _FollowUp(f"insider-scan:{cik}:step:{steps}", None) if stats.remaining else None
    if stats.stopped == "limiter_wait":
        return _FollowUp(f"insider-scan:{cik}:step:{steps}", now + LIMITER_RETRY)
    if status == SCAN_PAUSED and paused_until is not None:
        # SEC pushed back: the scan resumes by itself when the pause is over, once per pause.
        return _FollowUp(f"insider-scan:{cik}:resume:{steps}", ensure_utc(paused_until))
    return None   # failed: a later visit asks again, nothing retries by itself


async def run_scan_task(payload: dict) -> None:
    """The task worker's entry: one step, then the task that continues the scan when there is more to do."""
    from app.database import SessionLocal
    from app.services.durable_tasks import InsiderScanTask, enqueue_task

    task = InsiderScanTask.model_validate(payload)
    with SessionLocal() as db:
        stats = await run_scan_step(db, task.issuer_cik)
        follow = _follow_up(db, task.issuer_cik, stats, utcnow())
    if follow is not None:
        await enqueue_task("insider_scan", {"issuer_cik": task.issuer_cik}, dedupe_key=follow.key, schedule_at=follow.at)
