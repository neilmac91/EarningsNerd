"""Form 6-K (FPI interim) grounding-text extraction (Phase 4).

A 6-K has NO numbered-item / XBRL structure — its content lives in EX-99.x exhibits (typically an
earnings press release) plus a brief cover page. So it must NOT go through the Item/XBRL section
pipeline (``xbrl_service.get_filing_sections``); instead we resolve edgartools' ``SixK`` object and
pull the press-release / exhibit text plus cover-page metadata as the grounding text for the model.

edgartools attribute names + return types drift across versions (cf. the ``Section.text`` method-vs-
property handling in ``xbrl_service`` and the Form 4 defenses in ``ownership_extractor``), and the
known edge case where ``SixK.text`` raises — so every access goes through getattr + callable() +
try/except and the whole extraction NEVER raises: a malformed 6-K degrades to whatever text we could
get (cover metadata at minimum), or ``None``.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from edgar import Company as EdgarCompany

from .async_executor import run_in_executor_with_timeout
from .config import EDGAR_DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# 6-Ks are small vs annual reports; cap grounding text so a pathological multi-exhibit filing can't
# blow the model context. Same order as the section-sample budget used elsewhere.
_SIXK_TEXT_CAP = 120_000


def _safe(obj: Any, name: str) -> Any:
    """getattr(obj, name), calling it if it's a method. Returns None on anything unexpected."""
    try:
        val = getattr(obj, name, None)
        return val() if callable(val) else val
    except Exception:  # noqa: BLE001 — edgartools version drift / network hiccups must not raise
        return None


def _press_release_text(six_k: Any) -> Optional[str]:
    """Concatenated text of the EX-99.x press release(s), or None."""
    prs = _safe(six_k, "press_releases")
    if prs is None:
        return None
    try:
        count = len(prs)
    except Exception:  # noqa: BLE001 — PressReleases may not be sized in some versions
        return None
    parts: list[str] = []
    for i in range(count):
        try:
            pr = prs[i]
        except Exception:  # noqa: BLE001 — one bad exhibit must not kill the rest
            continue
        text = _safe(pr, "text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts) if parts else None


def _extract_sixk_text_sync(cik_padded: str, accession_number: str) -> Optional[str]:
    """Resolve the 6-K's ``SixK`` object and assemble grounding text. Synchronous (runs in the edgar
    thread pool). Never raises — returns the best text it can, or ``None``."""
    try:
        company = EdgarCompany(cik_padded)
        filings = list(company.get_filings(accession_number=accession_number))
    except Exception as e:  # noqa: BLE001
        logger.info("6-K %s not resolvable for CIK %s: %s", accession_number, cik_padded, e)
        return None
    if not filings:
        return None

    six_k = _safe(filings[0], "obj")
    if six_k is None:
        return None

    # Cover-page header (what the filing contains + reporting month) orients the model.
    header_bits: list[str] = []
    desc = _safe(six_k, "content_description")
    if isinstance(desc, str) and desc.strip():
        header_bits.append(f"Cover page — material contained in this report: {desc.strip()}")
    month = _safe(six_k, "report_month")
    if isinstance(month, str) and month.strip():
        header_bits.append(f"Reporting month: {month.strip()}")

    # Body: prefer the earnings press release; fall back to all exhibit text.
    body = _press_release_text(six_k)
    if not body:
        full = _safe(six_k, "text")
        body = full.strip() if isinstance(full, str) and full.strip() else None

    if not body and not header_bits:
        return None

    combined = "\n\n".join([*header_bits, body or ""]).strip()
    return combined[:_SIXK_TEXT_CAP] if combined else None


async def get_sixk_text(
    accession_number: str, cik: str, *, timeout: Optional[float] = None
) -> Optional[str]:
    """Async: grounding text for a 6-K (cover metadata + press-release/exhibit text), or ``None``.

    Runs the network-bound SixK resolution + exhibit download in the edgar thread pool. Never
    raises; returns ``None`` on timeout/failure so the caller degrades gracefully.
    """
    cik_padded = str(cik).zfill(10)
    budget = timeout if timeout is not None else max(EDGAR_DEFAULT_TIMEOUT_SECONDS, 30.0)
    try:
        return await run_in_executor_with_timeout(
            lambda: _extract_sixk_text_sync(cik_padded, accession_number),
            timeout=budget,
        )
    except Exception as e:  # noqa: BLE001 — incl. asyncio.TimeoutError
        logger.warning("6-K text extraction failed/timed out for %s: %s", accession_number, e)
        return None
