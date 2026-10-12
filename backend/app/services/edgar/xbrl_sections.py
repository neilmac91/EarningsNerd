"""Local filing-section parsing behind the XBRL service facade.

The service keeps parsing under one plain executor timeout: large local document
parses are deliberately breaker-exempt and do not measure SEC health.
"""

from typing import Dict, Optional

from .client import resolve_filing_by_accession
from .xbrl_cache import logger


# Minimum length (chars) for an edgartools-parsed section to count as real content
# rather than an empty/placeholder stub.
_SECTION_MIN_CHARS = 200


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
    fall back to the legacy regex extractor).
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
    if base_form == "10-K":
        # 10-K items are unique across parts, so label lookup via __getitem__ is unambiguous
        # and returns clean section text (verified: AAPL Item 1A/7/8 -> 68k/18k/61k chars).
        for canonical, label in (("risk", "Item 1A"), ("mda", "Item 7"), ("financials", "Item 8")):
            try:
                text = obj[label]
            except Exception:  # noqa: BLE001 — a single missing/odd section must not abort the rest
                text = None
            if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                out[canonical] = text.strip()
    elif base_form == "10-Q":
        # 10-Q items repeat across parts (e.g. Item 2 is MD&A in Part I but Unregistered Sales
        # in Part II), so __getitem__ by label is ambiguous — obj['Item 2'] returns the WRONG
        # Part II section. Use the new parser's part-prefixed section keys to disambiguate.
        sections = getattr(obj, "sections", None) or {}
        for canonical, skey in (
            ("financials", "part_i_item_1"),
            ("mda", "part_i_item_2"),
            ("risk", "part_ii_item_1a"),
        ):
            # edgartools' Sections is dict-like (.get); Section.text is a method in 5.36.0, but
            # guard against it being a plain str/property in other versions.
            section = sections.get(skey) if hasattr(sections, "get") else None
            text_attr = getattr(section, "text", None) if section is not None else None
            text = text_attr() if callable(text_attr) else text_attr
            if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                out[canonical] = text.strip()
    elif base_form == "20-F":
        # 20-F (foreign private issuer annual report) uses Part/Item numbering distinct from a
        # 10-K: Item 3 (Key Information) carries the Risk Factors, Item 5 (Operating & Financial
        # Review and Prospects) is the MD&A equivalent, and the audited statements live under
        # Item 18 (or the older Item 17). Items repeat across parts, so use the part-prefixed
        # section keys like the 10-Q path. Each canonical maps to ordered candidate keys —
        # first one that yields real content wins (handles the Item 18-vs-17 filer choice).
        sections = getattr(obj, "sections", None) or {}
        for canonical, candidate_keys in (
            ("risk", ("part_i_item_3",)),
            ("mda", ("part_i_item_5",)),
            ("financials", ("part_iii_item_18", "part_iii_item_17", "part_i_item_8")),
        ):
            for skey in candidate_keys:
                section = sections.get(skey) if hasattr(sections, "get") else None
                text_attr = getattr(section, "text", None) if section is not None else None
                text = text_attr() if callable(text_attr) else text_attr
                if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                    out[canonical] = text.strip()
                    break

    return out or None
