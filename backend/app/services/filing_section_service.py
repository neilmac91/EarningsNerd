"""Item 1A section text per filing: extraction, storage and the "what changed" wording diff.

The one home for the ``filing_section_text`` table (``app/models/filing_section_text.py``):

* ``extract_for_filing`` fetches a 10-K/10-Q primary document through the existing SEC transport
  (``sec_edgar_service.get_filing_document``: shared limiter, breaker, retries; CLAUDE.md rule 5),
  locates Item 1A with edgartools' HTML parser (local, breaker-exempt, run off the event loop) and
  upserts one row per (filing, section). Amendments are not fetched: a 10-K/A seldom carries the
  section and the comparison pairs originals.
* ``run_section_extraction`` is the job body the hourly filing scan (``scripts/filing_scan.py``,
  behind ``ENABLE_SECTION_CHANGES``) and the operator script (``scripts/extract_sections.py``)
  share: a bounded, newest-first batch over the filings of the companies somebody watches or has
  a summary for, so nothing is ever fetched because an anonymous page view asked. The same pass
  recomputes cached comparison summaries left behind by an older diff engine.
* ``build_section_changes`` is the Change Report's ``section_changes`` block: the stored text of
  the viewed filing diffed (``section_diff``) against the stored text of its prior same-form
  filing, in full for Pro and as a short teaser for everyone else. A cached summary of that diff
  lives on the later filing's row so lists can read counts without recomputing.

Only the filings' own text is stored or served (rule 2). Services stay HTTP-free: the router
derives the viewer's access from the entitlements and hands it in as plain data.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, NamedTuple, Optional

from sqlalchemy import desc, exists, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.models import Filing, Summary, Watchlist
from app.models.filing_section_text import FilingSectionText
from app.services import section_diff
from app.services.entitlements import get_entitlements
from app.utils.datetimes import ensure_utc, iso_z, utcnow

logger = logging.getLogger(__name__)

SECTION_ITEM_1A = "item_1a"
SECTION_LABELS = {SECTION_ITEM_1A: "Item 1A. Risk Factors"}
# Bump when ``parse_item_1a`` or ``_tidy`` would store different text for the same document; every
# row produced by an older extractor is then re-fetched, newest first, within the batch limit.
EXTRACTOR_VERSION = 1
SUPPORTED_FORMS = ("10-K", "10-Q")

STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_FAILED = "failed"
STATUS_OVERSIZE = "oversize"

ACCESS_NONE = "none"
ACCESS_TEASER = "teaser"
ACCESS_FULL = "full"

FETCH_TIMEOUT_SECONDS = 60.0
# A 13 MB 10-K parses in about 8 s on the job's single CPU, peaking near 370 MB of RSS.
PARSE_TIMEOUT_SECONDS = 120.0
# A failed attempt (a fresh failure, or a failed re-extraction of a row that keeps its older
# text) is not retried by the scheduled batch until it is this old; the operator script's
# ``retry_failed`` ignores the wait.
RETRY_FAILED_AFTER = timedelta(hours=24)
# Filings older than this are never selected: three fiscal years give every current 10-K/10-Q a
# prior to pair with, without walking a company's backfilled history to 2001.
WINDOW_DAYS = 3 * 365
# Cached summaries behind the current diff engine recomputed per batch (CPU only, no SEC request).
SUMMARY_RECOMPUTE_BATCH = 200
# A 10-Q "no material changes" pointer is short; a restated section never is.
_REFERENCE_ONLY_MAX_CHARS = 2000
_REFERENCE_ONLY = re.compile(
    r"no material (?:change|update)s?|not (?:been )?materially (?:changed|updated)|"
    r"(?:refer|see|incorporated)\w*\b.{0,120}\b(?:annual report|form 10-k)",
    re.I,
)
# A pointer that goes on to restate or add a risk is not a pointer.
_REFERENCE_CARVE_OUT = re.compile(r"\b(?:except|other than|in addition|supplement\w*|as (?:updated|supplemented) below)\b", re.I)

FetchDocument = Callable[[str], Awaitable[str]]
ParseSection = Callable[[str, str], "ExtractedSection"]


@dataclass(frozen=True)
class ExtractedSection:
    """What the parser found in one document."""

    status: str
    text: Optional[str] = None
    detection_method: Optional[str] = None
    confidence: Optional[float] = None
    error_type: Optional[str] = None


class ExtractionAttempt(NamedTuple):
    """One stored attempt: the row as it now stands and what this attempt found.

    ``status`` is the attempt's outcome, not necessarily the row's: a failed re-extraction keeps
    the row's older ``ok`` text (see ``_upsert``)."""

    row: FilingSectionText
    status: str


class SectionAccess(NamedTuple):
    """How much of the block a viewer gets, as the router resolved it from the entitlements."""

    level: str                    # ACCESS_NONE | ACCESS_TEASER | ACCESS_FULL
    item_limit: Optional[int]     # items shown; None = every item


NO_SECTION_ACCESS = SectionAccess(ACCESS_NONE, 0)
FULL_SECTION_ACCESS = SectionAccess(ACCESS_FULL, None)


class SectionExtractionHalted(RuntimeError):
    """The SEC breaker is open: nothing was attempted, the batch stops."""


# --- extraction -------------------------------------------------------------------------------

def _tidy(text: str) -> str:
    """Normalize line endings and blank-line runs; keep trailing spaces (the re-flow signal)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", text)
    return text.strip("\n")


def parse_item_1a(html: str, form: str) -> ExtractedSection:
    """Locate Item 1A in a 10-K (Part I) or 10-Q (Part II) primary document. Local CPU work only."""
    from edgar.documents import HTMLParser
    from edgar.documents.config import ParserConfig

    document = HTMLParser(ParserConfig(form=form)).parse(html)
    part = "I" if form == "10-K" else "II"
    section = document.sections.get_item("1A", part) or document.sections.get_item("1A")
    if section is None:
        return ExtractedSection(status=STATUS_MISSING)
    text = _tidy(section.text() or "")
    if not text.strip():
        return ExtractedSection(status=STATUS_MISSING)
    confidence = getattr(section, "confidence", None)
    return ExtractedSection(
        status=STATUS_OK,
        text=text,
        detection_method=str(getattr(section, "detection_method", "") or "")[:32] or None,
        confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
    )


def is_reference_only(text: str) -> bool:
    """A short 10-Q section that only points back at the 10-K, however it is line-wrapped."""
    flat = " ".join(text.split())
    if len(flat) > _REFERENCE_ONLY_MAX_CHARS or not _REFERENCE_ONLY.search(flat):
        return False
    return not _REFERENCE_CARVE_OUT.search(flat)


async def _default_fetch(document_url: str) -> str:
    from app.services.edgar.compat import sec_edgar_service

    return await sec_edgar_service.get_filing_document(document_url, timeout=FETCH_TIMEOUT_SECONDS)


def _section_row(db: Session, filing_id: int) -> Optional[FilingSectionText]:
    return (
        db.query(FilingSectionText)
        .filter(FilingSectionText.filing_id == filing_id, FilingSectionText.section == SECTION_ITEM_1A)
        .first()
    )


def _upsert(db: Session, filing: Filing, result: ExtractedSection, *, now: datetime) -> FilingSectionText:
    """Write the attempt onto the filing's row.

    A failed attempt on a row that already holds ``ok`` text (a re-extraction after an
    ``EXTRACTOR_VERSION`` bump, or an operator retry) keeps that text: only ``attempted_at`` and
    ``error_type`` record the failure, and the selection waits ``RETRY_FAILED_AFTER`` before trying
    again. Any other result replaces the row's payload and clears its cached comparison, which
    ``refresh_diff_summaries`` recomputes.
    """
    row = _section_row(db, filing.id)
    if row is None:
        row = FilingSectionText(filing_id=filing.id, section=SECTION_ITEM_1A)
        db.add(row)
    row.attempted_at = now
    if result.status == STATUS_FAILED and row.status == STATUS_OK and row.text:
        row.error_type = result.error_type
        return row
    text = result.text if result.status == STATUS_OK else None
    row.extractor_version = EXTRACTOR_VERSION
    row.status = result.status
    row.text = text
    row.char_count = len(text) if text else 0
    row.paragraph_count = len(section_diff.split_paragraphs(text)[0]) if text else 0
    row.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    row.reference_only = bool(text) and is_reference_only(text)
    row.detection_method = result.detection_method
    row.confidence = result.confidence
    row.error_type = result.error_type
    row.extracted_at = now
    # New text invalidates the cached comparison; the refresh below recomputes it.
    row.diff_prior_filing_id = None
    row.diff_engine_version = None
    row.diff_summary = None
    row.diff_computed_at = None
    return row


def _is_breaker_open(exc: BaseException) -> bool:
    from app.services.edgar.circuit_breaker import CircuitOpenError

    return isinstance(exc, CircuitOpenError)


async def extract_for_filing(
    db: Session,
    filing: Filing,
    *,
    fetch_document: Optional[FetchDocument] = None,
    parse: Optional[ParseSection] = None,
    now: Optional[datetime] = None,
) -> Optional[ExtractionAttempt]:
    """Fetch, parse and store the filing's Item 1A; refresh the diff summaries it takes part in.

    Returns the attempt, or None for an unsupported form (nothing is fetched). A fetch or parse
    error is recorded as a failed attempt (never raised), so one bad document cannot stop a batch;
    an open SEC breaker raises ``SectionExtractionHalted`` without writing anything, because
    nothing was attempted.
    """
    if filing.filing_type not in SUPPORTED_FORMS:
        return None
    from app.services.edgar.async_executor import run_in_executor_with_timeout

    fetch_document = fetch_document or _default_fetch
    parse = parse or parse_item_1a
    now = now or utcnow()
    form = filing.filing_type
    try:
        html = await fetch_document(filing.document_url)
        result = await run_in_executor_with_timeout(lambda: parse(html, form), timeout=PARSE_TIMEOUT_SECONDS)
    except Exception as exc:  # EdgarError, timeouts, parser faults: all recorded
        # The executor wraps parser faults in EdgarError; the underlying type is the useful one.
        underlying = getattr(exc, "cause", None) or exc
        if _is_breaker_open(underlying):
            raise SectionExtractionHalted(f"SEC breaker open before filing {filing.id}") from exc
        logger.warning("Item 1A extraction failed for filing %s (%s): %s", filing.id, form, type(underlying).__name__)
        result = ExtractedSection(status=STATUS_FAILED, error_type=type(underlying).__name__[:120])
    if result.status == STATUS_OK and len(result.text or "") > settings.SECTION_TEXT_MAX_CHARS:
        result = ExtractedSection(status=STATUS_OVERSIZE, detection_method=result.detection_method,
                                  confidence=result.confidence)
    row = _upsert(db, filing, result, now=now)
    try:
        db.commit()
    except IntegrityError:
        # Another process (the operator script beside the hourly job) inserted the row first:
        # write this attempt onto theirs.
        db.rollback()
        row = _upsert(db, filing, result, now=now)
        db.commit()
    refresh_diff_summaries(db, filing, now=now)
    db.commit()
    return ExtractionAttempt(row=row, status=result.status)


# --- selection and the job body ----------------------------------------------------------------

def _watched_company():
    """``Filing``'s company is on somebody's watchlist."""
    return exists().where(Watchlist.company_id == Filing.company_id)


def _in_watched_cohort():
    """The batch's ``watched`` cohort as a filter on ``Filing``: a company somebody watches, or one
    with a summarized filing (so a summarized filing's prior is extracted too). The Change Report
    block tests a single filing against this same predicate, so its ``pending`` means what the
    batch does."""
    summarized_company = aliased(Filing)
    has_summary = exists().where(
        (summarized_company.company_id == Filing.company_id) & (Summary.filing_id == summarized_company.id)
    )
    return or_(_watched_company(), has_summary)


def select_filings_for_extraction(
    db: Session,
    *,
    limit: int,
    cohort: str = "watched",
    tickers: Optional[list[str]] = None,
    retry_failed: bool = False,
    window_days: Optional[int] = None,
    now: Optional[datetime] = None,
) -> list[Filing]:
    """Supported filings of the last ``window_days`` with no current row, newest first, watched
    companies ahead of the rest.

    ``cohort`` is ``"watched"`` (companies somebody watches or has a summary for, so a summarized
    filing's prior is extracted too) or ``"all"``; ``tickers`` narrows either. A failed attempt
    (a ``failed`` row, or an ``ok`` row whose re-extraction failed) blocks re-selection for
    ``RETRY_FAILED_AFTER`` unless ``retry_failed``.
    """
    if limit <= 0:
        return []
    now = now or utcnow()
    window_days = WINDOW_DAYS if window_days is None else window_days
    same_row = (FilingSectionText.filing_id == Filing.id) & (FilingSectionText.section == SECTION_ITEM_1A)
    current = FilingSectionText.extractor_version >= EXTRACTOR_VERSION
    if retry_failed:
        blocking = same_row & current & (FilingSectionText.status != STATUS_FAILED)
    else:
        recently_attempted = FilingSectionText.attempted_at > now - RETRY_FAILED_AFTER
        blocking = same_row & or_(
            current & or_(FilingSectionText.status != STATUS_FAILED, recently_attempted),
            # An older row whose re-extraction just failed waits too.
            FilingSectionText.error_type.isnot(None) & recently_attempted,
        )
    watched = _watched_company()
    query = db.query(Filing).filter(
        Filing.filing_type.in_(SUPPORTED_FORMS),
        Filing.filing_date >= now - timedelta(days=window_days),
        ~exists().where(blocking),
    )
    if cohort == "watched":
        query = query.filter(_in_watched_cohort())
    if tickers:
        from app.models import Company

        wanted = [t.strip().upper() for t in tickers if t and t.strip()]
        query = query.join(Company, Company.id == Filing.company_id).filter(Company.ticker.in_(wanted))
    return query.order_by(desc(watched), desc(Filing.filing_date), desc(Filing.id)).limit(limit).all()


async def run_section_extraction(
    db: Session,
    *,
    limit: Optional[int] = None,
    cohort: str = "watched",
    tickers: Optional[list[str]] = None,
    retry_failed: bool = False,
    window_days: Optional[int] = None,
    now: Optional[datetime] = None,
    fetch_document: Optional[FetchDocument] = None,
    parse: Optional[ParseSection] = None,
) -> dict[str, int]:
    """One bounded, serial pass: counts only (``job_run_service`` persists them).

    ``extract_errors`` fails the job; ``breaker_open`` (the batch stopped early because the SEC
    breaker is open) and ``summaries_recomputed`` (cached summaries brought up to the current
    diff engine) are informational.
    """
    limit = settings.SECTION_EXTRACTION_BATCH_LIMIT if limit is None else limit
    stats = {"selected": 0, "extracted_ok": 0, "missing": 0, "oversize": 0, "extract_errors": 0,
             "breaker_open": 0, "summaries_recomputed": 0}
    # The job owns this session (the scan job, the operator script, the task worker), so the
    # selection's read transaction is finished before the first SEC fetch and the selected filings
    # stay loaded across the per-filing commits: no pooled connection sits idle in transaction
    # through transport or the parse (lessons/ops-finish-only-job-owned-read-transactions.md).
    if db.new or db.dirty or db.deleted or db.in_nested_transaction():
        raise RuntimeError("run_section_extraction needs a session with no pending writes or nested transaction")
    prior_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    try:
        filings = select_filings_for_extraction(
            db, limit=limit, cohort=cohort, tickers=tickers, retry_failed=retry_failed, window_days=window_days, now=now
        )
        db.commit()  # the read-only selection is complete: the connection goes back before transport
        stats["selected"] = len(filings)
        for filing in filings:
            try:
                attempt = await extract_for_filing(db, filing, fetch_document=fetch_document, parse=parse, now=now)
            except SectionExtractionHalted as halted:
                logger.warning("Section extraction stopped: %s", halted)
                stats["breaker_open"] = 1
                break
            if attempt is None:
                continue
            if attempt.status == STATUS_OK:
                stats["extracted_ok"] += 1
            elif attempt.status == STATUS_FAILED:
                stats["extract_errors"] += 1
            else:
                stats[attempt.status] += 1
        stats["summaries_recomputed"] = recompute_stale_summaries(db, limit=SUMMARY_RECOMPUTE_BATCH, now=now)
    finally:
        db.expire_on_commit = prior_expire_on_commit
    return stats


# --- pairing and the cached diff ---------------------------------------------------------------

def _prior_filing(db: Session, filing: Filing) -> Optional[Filing]:
    """The latest earlier-period original of the same form and company: the Change Report's own
    prior rule, minus amendments (a strictly earlier reporting period, filed earlier; without the
    current period nothing is comparable)."""
    if filing.period_end_date is None:
        return None
    return (
        db.query(Filing)
        .filter(
            Filing.company_id == filing.company_id,
            Filing.filing_type == filing.filing_type,
            Filing.filing_date < filing.filing_date,
            Filing.period_end_date < filing.period_end_date,
        )
        .order_by(desc(Filing.period_end_date), desc(Filing.filing_date), desc(Filing.accession_number))
        .first()
    )


def _next_filing(db: Session, filing: Filing) -> Optional[Filing]:
    """The next same-form original, whose prior this filing is."""
    if filing.period_end_date is None:
        return None
    return (
        db.query(Filing)
        .filter(
            Filing.company_id == filing.company_id,
            Filing.filing_type == filing.filing_type,
            Filing.filing_date > filing.filing_date,
            Filing.period_end_date > filing.period_end_date,
        )
        .order_by(Filing.period_end_date, Filing.filing_date, Filing.accession_number)
        .first()
    )


def prior_section_row(db: Session, filing: Filing) -> Optional[FilingSectionText]:
    """The ``ok`` Item 1A row of the filing's prior (``_prior_filing``), else None. The comparison
    never skips a period: a prior without usable text leaves the filing without a comparison."""
    prior = _prior_filing(db, filing)
    if prior is None:
        return None
    row = _section_row(db, prior.id)
    return row if row is not None and row.status == STATUS_OK else None


_DIFF_CACHE: "OrderedDict[tuple[Optional[str], Optional[str], int], dict[str, Any]]" = OrderedDict()
_DIFF_CACHE_MAX = 32
_DIFF_CACHE_LOCK = threading.Lock()


def cached_diff(prior: FilingSectionText, later: FilingSectionText) -> dict[str, Any]:
    """``section_diff.diff_sections`` over two rows, memoized per process on their text hashes.

    The worst corpus pair takes about 150 ms; the page's server render and the client's own
    request both ask for it, so the hot pairs stay warm (ADR-0004: in-process L1, no Redis).
    Callers must not mutate the returned dict.
    """
    key = (prior.sha256, later.sha256, section_diff.ENGINE_VERSION)
    with _DIFF_CACHE_LOCK:
        hit = _DIFF_CACHE.get(key)
        if hit is not None:
            _DIFF_CACHE.move_to_end(key)
            return hit
    result = section_diff.diff_sections(prior.text or "", later.text or "")
    with _DIFF_CACHE_LOCK:
        _DIFF_CACHE[key] = result
        while len(_DIFF_CACHE) > _DIFF_CACHE_MAX:
            _DIFF_CACHE.popitem(last=False)
    return result


def compute_diff_summary(db: Session, row: FilingSectionText, *, now: Optional[datetime] = None) -> None:
    """Store the comparison summary (counts, never items) on an ``ok`` row."""
    now = now or utcnow()
    filing = row.filing if row.filing is not None else db.get(Filing, row.filing_id)
    prior = prior_section_row(db, filing) if row.status == STATUS_OK else None
    row.diff_engine_version = section_diff.ENGINE_VERSION
    row.diff_computed_at = now
    if prior is None:
        row.diff_prior_filing_id = None
        row.diff_summary = None
        return
    result = cached_diff(prior, row)
    row.diff_prior_filing_id = prior.filing_id
    row.diff_summary = {
        "counts": result["counts"],
        "words": result["words"],
        "paragraphs": result["paragraphs"],
        "has_changes": result["has_changes"],
        "items_total": len(result["items"]),
        "reference_only": bool(row.reference_only),
        "prior_reference_only": bool(prior.reference_only),
    }


def refresh_diff_summaries(db: Session, filing: Filing, *, now: Optional[datetime] = None) -> int:
    """Recompute the summary of this filing's row and of the next filing's row (this filing is
    its prior, so a change of status here changes that comparison). Returns how many were written."""
    written = 0
    row = _section_row(db, filing.id)
    if row is not None and row.status == STATUS_OK:
        compute_diff_summary(db, row, now=now)
        written += 1
    successor = _next_filing(db, filing)
    successor_row = _section_row(db, successor.id) if successor is not None else None
    if successor_row is not None and successor_row.status == STATUS_OK:
        compute_diff_summary(db, successor_row, now=now)
        written += 1
    return written


def recompute_stale_summaries(db: Session, *, limit: int, now: Optional[datetime] = None) -> int:
    """Bring up to ``limit`` ``ok`` rows whose cached summary predates ``section_diff.ENGINE_VERSION``
    (or was never computed) onto the current engine. CPU only; commits. Returns how many."""
    if limit <= 0:
        return 0
    rows = (
        db.query(FilingSectionText)
        .filter(
            FilingSectionText.section == SECTION_ITEM_1A,
            FilingSectionText.status == STATUS_OK,
            or_(FilingSectionText.diff_engine_version.is_(None),
                FilingSectionText.diff_engine_version < section_diff.ENGINE_VERSION),
        )
        .order_by(desc(FilingSectionText.extracted_at), desc(FilingSectionText.id))
        .limit(limit)
        .all()
    )
    for row in rows:
        compute_diff_summary(db, row, now=now)
    if rows:
        db.commit()
    return len(rows)


# --- the Change Report block -------------------------------------------------------------------

def section_changes_access(user: Any) -> SectionAccess:
    """None while the flag is off; otherwise what ``entitlements`` grants the viewer: every item
    for ``section_changes``, else the ``section_changes_items`` teaser."""
    if not settings.ENABLE_SECTION_CHANGES:
        return NO_SECTION_ACCESS
    entitlements = get_entitlements(user)
    if entitlements.section_changes:
        return FULL_SECTION_ACCESS
    return SectionAccess(ACCESS_TEASER, entitlements.section_changes_items)


def _filing_ref(filing: Filing) -> dict[str, Any]:
    return {
        "filing_id": filing.id,
        "accession_number": filing.accession_number,
        "filing_type": filing.filing_type,
        "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
        "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
    }


def _side(row: FilingSectionText) -> dict[str, Any]:
    return {
        "status": row.status,
        "extracted_at": iso_z(ensure_utc(row.extracted_at)) if row.extracted_at else None,
        "reference_only": bool(row.reference_only),
        "char_count": row.char_count,
        "paragraph_count": row.paragraph_count,
    }


def _outside_window(filing: Filing, now: datetime) -> bool:
    return filing.filing_date is not None and ensure_utc(filing.filing_date) < now - timedelta(days=WINDOW_DAYS)


def _in_cohort(db: Session, filing: Filing) -> bool:
    return db.query(Filing.id).filter(Filing.id == filing.id, _in_watched_cohort()).first() is not None


def _unextracted(db: Session, filing: Filing, side: str, now: datetime) -> tuple[str, str]:
    """The state of a side with no row: ``pending`` when the hourly batch will select the filing
    (``<side>_not_extracted``), else ``unavailable`` with why it will not: filed before the
    extraction window (``<side>_outside_window``) or a company nobody watches and no filing of
    which has a summary (``<side>_outside_cohort``). ``scripts/extract_sections.py`` reaches both
    by hand (``--window-days``, ``--all`` or ``--tickers``)."""
    if _outside_window(filing, now):
        return "unavailable", f"{side}_outside_window"
    if not _in_cohort(db, filing):
        return "unavailable", f"{side}_outside_cohort"
    return "pending", f"{side}_not_extracted"


def build_section_changes(db: Session, filing: Filing, access: SectionAccess) -> Optional[dict[str, Any]]:
    """The ``section_changes`` block, or None when the feature is off.

    ``status`` is ``ok`` (a comparison, ``items`` cut to ``access.item_limit``), ``pending`` (a side
    has no row yet and the hourly batch will extract it: ``current_not_extracted`` /
    ``prior_not_extracted``), ``no_prior`` (no earlier same-form filing exists) or ``unavailable``
    (nothing to compare as things stand: ``form_not_supported``; the current or the prior row is
    ``missing``, ``oversize`` or ``failed`` as ``current_<status>`` / ``prior_<status>``; or a side
    has no row and the batch will not select it, filed before the extraction window
    (``<side>_outside_window``) or a company outside the batch's cohort (``<side>_outside_cohort``)).
    ``prior_filing`` is set whenever a prior exists, so a reader can see which filing the state is
    about.
    """
    if access.level == ACCESS_NONE:
        return None
    block: dict[str, Any] = {
        "section": SECTION_ITEM_1A,
        "section_label": SECTION_LABELS[SECTION_ITEM_1A],
        "access": access.level,
        "engine_version": section_diff.ENGINE_VERSION,
        "prior_filing": None,
    }
    if filing.filing_type not in SUPPORTED_FORMS:
        return {**block, "status": "unavailable", "reason": "form_not_supported"}
    row = _section_row(db, filing.id)
    if row is None:
        status, reason = _unextracted(db, filing, "current", utcnow())
        return {**block, "status": status, "reason": reason}
    if row.status != STATUS_OK:
        return {**block, "status": "unavailable", "reason": f"current_{row.status}", "current": _side(row)}
    prior_filing = _prior_filing(db, filing)
    if prior_filing is None:
        return {**block, "status": "no_prior", "reason": "no_prior_filing", "current": _side(row)}
    block["prior_filing"] = _filing_ref(prior_filing)
    prior = _section_row(db, prior_filing.id)
    if prior is None:
        status, reason = _unextracted(db, prior_filing, "prior", utcnow())
        return {**block, "status": status, "reason": reason, "current": _side(row)}
    if prior.status != STATUS_OK:
        return {**block, "status": "unavailable", "reason": f"prior_{prior.status}", "current": _side(row), "prior": _side(prior)}
    result = cached_diff(prior, row)
    items = result["items"]
    shown = items if access.item_limit is None else items[: max(access.item_limit, 0)]
    return {
        **block,
        "status": "ok",
        "reason": None,
        "current": _side(row),
        "prior": _side(prior),
        "paragraphs": result["paragraphs"],
        "counts": result["counts"],
        "words": result["words"],
        "has_changes": result["has_changes"],
        "items": list(shown),
        "items_total": len(items),
        "truncated": len(shown) < len(items),
    }
