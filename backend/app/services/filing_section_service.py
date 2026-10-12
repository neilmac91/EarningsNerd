"""Item 1A section text per filing: extraction, storage and the "what changed" wording diff.

The one home for the ``filing_section_text`` table (``app/models/filing_section_text.py``):

* ``extract_for_filing`` fetches a 10-K/10-Q primary document through the existing SEC transport
  (``sec_edgar_service.get_filing_document``: shared limiter, breaker, retries; CLAUDE.md rule 5),
  locates Item 1A with edgartools' HTML parser (local, breaker-exempt, run off the event loop) and
  upserts one row per (filing, section). Amendments are not fetched: a 10-K/A seldom carries the
  section and the comparison pairs originals.
* ``run_section_extraction`` is the job body the hourly filing scan (``scripts/filing_scan.py``,
  behind ``ENABLE_SECTION_CHANGES``) and the operator script (``scripts/extract_sections.py``)
  share: a bounded, newest-first batch over the watched companies' filings and the filings that
  already have a summary, so nothing is ever fetched because an anonymous page view asked.
* ``build_section_changes`` is the Change Report's ``section_changes`` block: the stored text of
  the viewed filing diffed (``section_diff``) against the stored text of its prior same-form
  filing, in full for Pro and as a short teaser for everyone else. A cached summary of that diff
  lives on the later filing's row so lists can read counts without recomputing.

Only the filings' own text is stored or served (rule 2). Services stay HTTP-free: access is a
plain string the router derives from the entitlements.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import desc, exists, or_
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
# Bump when ``parse_item_1a`` or ``_tidy`` would store different text for the same document.
EXTRACTOR_VERSION = 1
SUPPORTED_FORMS = ("10-K", "10-Q")

STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_FAILED = "failed"
STATUS_OVERSIZE = "oversize"

ACCESS_NONE = "none"
ACCESS_TEASER = "teaser"
ACCESS_FULL = "full"
# Items a Free or anonymous reader sees; the counts are never truncated.
TEASER_ITEMS = 3

FETCH_TIMEOUT_SECONDS = 60.0
# JPMorgan's 13 MB 10-K parses in about 8 s on the job's single CPU.
PARSE_TIMEOUT_SECONDS = 120.0
# A failed row is retried by the scheduled batch once it is this old; the operator script's
# ``retry_failed`` ignores the wait.
RETRY_FAILED_AFTER = timedelta(hours=24)
# Filings older than this are never selected: three fiscal years give every current 10-K/10-Q a
# prior to pair with, without walking a company's backfilled history to 2001.
WINDOW_DAYS = 3 * 365
# A 10-Q "no material changes" pointer is short; a restated section never is.
_REFERENCE_ONLY_MAX_CHARS = 2000
_REFERENCE_ONLY = re.compile(
    r"no material (?:change|update)s?|not (?:been )?materially (?:changed|updated)|"
    r"(?:refer|see|incorporated)\w*\b.{0,120}\b(?:annual report|form 10-k)",
    re.I | re.S,
)

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
    return len(text) <= _REFERENCE_ONLY_MAX_CHARS and bool(_REFERENCE_ONLY.search(text))


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
    row = _section_row(db, filing.id)
    if row is None:
        row = FilingSectionText(filing_id=filing.id, section=SECTION_ITEM_1A)
        db.add(row)
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


async def extract_for_filing(
    db: Session,
    filing: Filing,
    *,
    fetch_document: Optional[FetchDocument] = None,
    parse: Optional[ParseSection] = None,
    now: Optional[datetime] = None,
) -> Optional[FilingSectionText]:
    """Fetch, parse and store the filing's Item 1A; refresh the diff summaries it takes part in.

    Returns the row, or None for an unsupported form (nothing is fetched). A fetch or parse error
    is recorded as a ``failed`` row (never raised), so one bad document cannot stop a batch.
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
    except Exception as exc:  # EdgarError, CircuitOpenError, timeouts, parser faults: all recorded
        # The executor wraps parser faults in EdgarError; the underlying type is the useful one.
        underlying = getattr(exc, "cause", None) or exc
        logger.warning("Item 1A extraction failed for filing %s (%s): %s", filing.id, form, type(underlying).__name__)
        result = ExtractedSection(status=STATUS_FAILED, error_type=type(underlying).__name__[:120])
    if result.status == STATUS_OK and len(result.text or "") > settings.SECTION_TEXT_MAX_CHARS:
        result = ExtractedSection(status=STATUS_OVERSIZE, detection_method=result.detection_method,
                                  confidence=result.confidence)
    row = _upsert(db, filing, result, now=now)
    db.commit()
    if row.status == STATUS_OK:
        refresh_diff_summaries(db, filing, now=now)
        db.commit()
    return row


# --- selection and the job body ----------------------------------------------------------------

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
    filing's prior is extracted too) or ``"all"``; ``tickers`` narrows either. A ``failed`` row
    blocks re-selection for ``RETRY_FAILED_AFTER`` unless ``retry_failed``.
    """
    if limit <= 0:
        return []
    now = now or utcnow()
    window_days = WINDOW_DAYS if window_days is None else window_days
    blocking = (FilingSectionText.filing_id == Filing.id) & (FilingSectionText.section == SECTION_ITEM_1A) & (
        FilingSectionText.extractor_version >= EXTRACTOR_VERSION
    )
    if retry_failed:
        blocking = blocking & (FilingSectionText.status != STATUS_FAILED)
    else:
        blocking = blocking & or_(
            FilingSectionText.status != STATUS_FAILED,
            FilingSectionText.extracted_at > now - RETRY_FAILED_AFTER,
        )
    watched = exists().where(Watchlist.company_id == Filing.company_id)
    query = db.query(Filing).filter(
        Filing.filing_type.in_(SUPPORTED_FORMS),
        Filing.filing_date >= now - timedelta(days=window_days),
        ~exists().where(blocking),
    )
    if cohort == "watched":
        summarized_company = aliased(Filing)
        has_summary = exists().where(
            (summarized_company.company_id == Filing.company_id) & (Summary.filing_id == summarized_company.id)
        )
        query = query.filter(or_(watched, has_summary))
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
    """One bounded, serial pass: counts only (``job_run_service`` persists them)."""
    limit = settings.SECTION_EXTRACTION_BATCH_LIMIT if limit is None else limit
    stats = {"selected": 0, "extracted_ok": 0, "missing": 0, "oversize": 0, "extract_errors": 0}
    filings = select_filings_for_extraction(
        db, limit=limit, cohort=cohort, tickers=tickers, retry_failed=retry_failed, window_days=window_days, now=now
    )
    stats["selected"] = len(filings)
    for filing in filings:
        row = await extract_for_filing(db, filing, fetch_document=fetch_document, parse=parse, now=now)
        if row is None:
            continue
        if row.status == STATUS_OK:
            stats["extracted_ok"] += 1
        elif row.status == STATUS_FAILED:
            stats["extract_errors"] += 1
        else:
            stats[row.status] += 1
    return stats


# --- pairing and the cached diff ---------------------------------------------------------------

def prior_section_row(db: Session, filing: Filing) -> Optional[FilingSectionText]:
    """The ``ok`` Item 1A row of the latest earlier-period filing of the same form and company.

    Same rule as the Change Report's prior: a strictly earlier reporting period, never an
    amendment of the same period; without the current period nothing is comparable.
    """
    if filing.period_end_date is None:
        return None
    return (
        db.query(FilingSectionText)
        .join(Filing, FilingSectionText.filing_id == Filing.id)
        .filter(
            Filing.company_id == filing.company_id,
            Filing.filing_type == filing.filing_type,
            Filing.filing_date < filing.filing_date,
            Filing.period_end_date < filing.period_end_date,
            FilingSectionText.section == SECTION_ITEM_1A,
            FilingSectionText.status == STATUS_OK,
        )
        .order_by(desc(Filing.period_end_date), desc(Filing.filing_date), desc(Filing.accession_number))
        .first()
    )


def _has_prior_filing(db: Session, filing: Filing) -> bool:
    if filing.period_end_date is None:
        return False
    return db.query(
        exists().where(
            (Filing.company_id == filing.company_id)
            & (Filing.filing_type == filing.filing_type)
            & (Filing.filing_date < filing.filing_date)
            & (Filing.period_end_date < filing.period_end_date)
        )
    ).scalar()


def _next_section_row(db: Session, filing: Filing) -> Optional[FilingSectionText]:
    """The ``ok`` row of the next same-form filing, whose prior this filing may now be."""
    if filing.period_end_date is None:
        return None
    return (
        db.query(FilingSectionText)
        .join(Filing, FilingSectionText.filing_id == Filing.id)
        .filter(
            Filing.company_id == filing.company_id,
            Filing.filing_type == filing.filing_type,
            Filing.filing_date > filing.filing_date,
            Filing.period_end_date > filing.period_end_date,
            FilingSectionText.section == SECTION_ITEM_1A,
            FilingSectionText.status == STATUS_OK,
        )
        .order_by(Filing.period_end_date, Filing.filing_date, Filing.accession_number)
        .first()
    )


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
    """Recompute the summary of this filing's row and of the next filing's row (this filing may
    have just become its prior). Returns how many summaries were written."""
    written = 0
    row = _section_row(db, filing.id)
    if row is not None and row.status == STATUS_OK:
        compute_diff_summary(db, row, now=now)
        written += 1
    successor = _next_section_row(db, filing)
    if successor is not None:
        compute_diff_summary(db, successor, now=now)
        written += 1
    return written


# --- the Change Report block -------------------------------------------------------------------

def section_changes_access(user: Any) -> str:
    """``none`` while the flag is off, ``full`` for an entitled user, else ``teaser``."""
    if not settings.ENABLE_SECTION_CHANGES:
        return ACCESS_NONE
    if user is not None and get_entitlements(user).section_changes:
        return ACCESS_FULL
    return ACCESS_TEASER


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
        "extracted_at": iso_z(ensure_utc(row.extracted_at)) if row.extracted_at else None,
        "reference_only": bool(row.reference_only),
        "char_count": row.char_count,
        "paragraph_count": row.paragraph_count,
    }


def build_section_changes(db: Session, filing: Filing, access: str) -> Optional[dict[str, Any]]:
    """The ``section_changes`` block, or None when the feature is off.

    ``status`` is ``ok`` (a comparison, ``items`` cut to ``TEASER_ITEMS`` unless ``access`` is
    full), ``pending`` (a side is not extracted yet), ``no_prior`` (no earlier same-form filing
    exists) or ``unavailable`` (the section is missing, oversize, failed, or the form is not
    supported); ``reason`` says which side and why.
    """
    if access == ACCESS_NONE:
        return None
    block: dict[str, Any] = {
        "section": SECTION_ITEM_1A,
        "section_label": SECTION_LABELS[SECTION_ITEM_1A],
        "access": access,
        "engine_version": section_diff.ENGINE_VERSION,
        "prior_filing": None,
    }
    if filing.filing_type not in SUPPORTED_FORMS:
        return {**block, "status": "unavailable", "reason": "form_not_supported"}
    row = _section_row(db, filing.id)
    if row is None:
        return {**block, "status": "pending", "reason": "current_not_extracted"}
    if row.status != STATUS_OK:
        return {**block, "status": "unavailable", "reason": f"current_{row.status}", "current": _side(row)}
    prior = prior_section_row(db, filing)
    if prior is None:
        if not _has_prior_filing(db, filing):
            return {**block, "status": "no_prior", "reason": "no_prior_filing", "current": _side(row)}
        return {**block, "status": "pending", "reason": "prior_not_extracted", "current": _side(row)}
    result = cached_diff(prior, row)
    items = result["items"]
    shown = items if access == ACCESS_FULL else items[:TEASER_ITEMS]
    prior_filing = prior.filing if prior.filing is not None else db.get(Filing, prior.filing_id)
    return {
        **block,
        "status": "ok",
        "reason": None,
        "prior_filing": _filing_ref(prior_filing),
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
