"""Local filing-section parsing behind the XBRL service facade.

The service keeps parsing under one plain executor timeout: large local document
parses are deliberately breaker-exempt and do not measure SEC health.
"""

from typing import Any, Dict, Optional, Tuple

from .client import resolve_filing_by_accession
from .xbrl_cache import logger


# Minimum length (chars) for an edgartools-parsed section to count as real content
# rather than an empty/placeholder stub.
_SECTION_MIN_CHARS = 200

# 10-Q and 20-F items repeat across parts (a 10-Q's Item 2 is MD&A in Part I but Unregistered Sales
# in Part II), so label lookup is ambiguous; use the part-prefixed section keys. A 20-F carries Risk
# Factors under Item 3, the MD&A equivalent under Item 5, and the statements under Item 18 (or the
# older Item 17): each canonical maps to ordered candidate keys and the first with content wins.
_PART_KEYS = {
    "10-Q": (("financials", ("part_i_item_1",)), ("mda", ("part_i_item_2",)), ("risk", ("part_ii_item_1a",))),
    "20-F": (("risk", ("part_i_item_3",)), ("mda", ("part_i_item_5",)),
             ("financials", ("part_iii_item_18", "part_iii_item_17", "part_i_item_8"))),
}


def _section_text(sections: Any, key: str) -> Optional[str]:
    """Stripped text of one part-qualified section, or None when it is missing or a stub."""
    section = sections.get(key) if hasattr(sections, "get") else None
    # Section.text is a method in 5.36.0; guard against a plain str/property in other versions.
    text_attr = getattr(section, "text", None) if section is not None else None
    text = text_attr() if callable(text_attr) else text_attr
    return text.strip() if text and len(text.strip()) >= _SECTION_MIN_CHARS else None


def _sections_of(obj: Any) -> Tuple[Any, Optional[Exception]]:
    """``obj.sections`` with any error kept. ``getattr``'s default would also swallow an
    AttributeError raised inside the property, which hid the 2026-10 SEC 403 (edgartools_compat)."""
    try:
        return obj.sections or {}, None
    except Exception as exc:  # noqa: BLE001 — reported by the caller when no section parses
        return {}, exc


def _extract_sections_sync(
    cik_padded: str,
    accession_number: str,
    base_form: str,
) -> Optional[Dict[str, str]]:
    """Pull the critical narrative/financial sections via edgartools' own document parser.

    edgartools (``filing.obj()``) resolves real section boundaries from the filing's
    structure/inline-XBRL, which is robust to the element-fragmented HTML that defeats the
    legacy regex extractor in ``openai_service.extract_critical_sections``.

    Synchronous on purpose: the whole chain (company lookup -> filing resolution -> document
    parse) runs as ONE executor call, sharing a single timeout budget and thread-pool slot,
    mirroring ``_extract_from_filing_instance_sync``.

    Returns a dict keyed by canonical section ("financials" / "mda" / "risk") mapped to clean
    text, or None when the filing can't be resolved or yields no usable sections (callers then
    fall back to the legacy regex extractor; a read error that left no section is logged first).
    """
    _, filings = resolve_filing_by_accession(cik_padded, accession_number)
    if not filings:
        logger.info(f"Filing {accession_number} not found by accession for CIK {cik_padded}")
        return None

    obj = filings[0].obj()
    if obj is None:
        logger.info(f"Filing {accession_number} has no parsable document object")
        return None

    out: Dict[str, str] = {}
    error: Optional[Exception] = None
    if base_form == "10-K":
        # 10-K items are unique across parts, so label lookup via __getitem__ is unambiguous
        # and returns clean section text (verified: AAPL Item 1A/7/8 -> 68k/18k/61k chars).
        for canonical, label in (("risk", "Item 1A"), ("mda", "Item 7"), ("financials", "Item 8")):
            try:
                text = obj[label]
            except Exception as exc:  # noqa: BLE001 — a single missing/odd section must not abort the rest
                text, error = None, error or exc
            if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                out[canonical] = text.strip()
    elif base_form in _PART_KEYS:
        sections, error = _sections_of(obj)
        for canonical, candidate_keys in _PART_KEYS[base_form]:
            text = next(filter(None, (_section_text(sections, key) for key in candidate_keys)), None)
            if text:
                out[canonical] = text

    if not out and error is not None:
        logger.warning(f"Section parse found nothing for {accession_number} ({base_form}): {error!r}")
    return out or None
