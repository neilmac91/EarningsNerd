"""Summary sections parsed from the primary document the pipeline already fetched (E28).

The summary pipeline downloads a filing's primary document once, through the app's SEC transport
(shared limiter and breaker, CLAUDE.md rule 5), and hands its HTML here. Parsing is local CPU work:
no SEC request, deliberately breaker-exempt, run by the XBRL service facade under one plain executor
timeout (``lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md``).

The text is what edgartools' own report classes return for the same document: ``TenK``, ``TenQ``
and ``TwentyF``, which ``Filing.obj()`` built until SEC's 403 on edgartools 5.58.0's index URL
disabled that path in early October 2026. Same parser, same configuration, same section keys and
the same 10-K lookup order, so the excerpt matches the one the eval baseline was pinned on
(``tests/unit/test_summary_sections_parity.py``).
"""

import re
from typing import Callable, Dict, Optional

from edgar.documents import CrossReferenceIndex, HTMLParser, ParserConfig, parse_html

from .xbrl_cache import logger


# Minimum length (chars) for a parsed section to count as real content rather than an
# empty/placeholder stub.
_SECTION_MIN_CHARS = 200

# Documents above this size are not parsed; the pipeline keeps the regex excerpt. Parse time and
# peak memory grow with the document. In the golden set the largest document with sections is
# JPMorgan's 12.9 MB 10-K (5.7 to 6.4 s; 503 MB process peak), and ASML's 24.9 MB 20-F took 10.9 s
# to parse and peaked at 713 MB to yield no sections at all
# (tasks/review-evidence/e28-native-sections-2026-10-15/parse_results.jsonl).
_MAX_SECTION_HTML_CHARS = 16_000_000

# 10-Q and 20-F sections are read by part-qualified key, in order; the first with real content
# wins (a 20-F files its statements under Item 18 or the older Item 17).
_PART_KEYS: Dict[str, tuple] = {
    "10-Q": (
        ("financials", ("part_i_item_1",)),
        ("mda", ("part_i_item_2",)),
        ("risk", ("part_ii_item_1a",)),
    ),
    "20-F": (
        ("risk", ("part_i_item_3",)),
        ("mda", ("part_i_item_5",)),
        ("financials", ("part_iii_item_18", "part_iii_item_17", "part_i_item_8")),
    ),
}

# 10-K items are unique across parts, so they are looked up by item number the way
# ``TenK.__getitem__`` does: canonical part key, combined-items heading, "Item X" key, friendly name,
# then the Cross Reference Index some filers (GE, Citigroup) use instead of item headings.
_TEN_K_ITEMS = (
    ("risk", "1a", "i", "risk_factors"),
    ("mda", "7", "ii", "mda"),
    ("financials", "8", "ii", "financial_statements"),
)
_PART_LINE = re.compile(r"^\b(PART\s+[IVXLC]+)\b")


def _text_of(section) -> Optional[str]:
    # A Section's ``text`` is a method in current edgartools; tolerate a plain attribute too.
    text = getattr(section, "text", None) if section is not None else None
    return text() if callable(text) else text


def _ten_k_item(sections, item: str, part: str, friendly: str,
                cross_reference: Callable[[], Optional[CrossReferenceIndex]]) -> Optional[str]:
    """``TenK.__getitem__("Item <item>")``: the first lookup that resolves wins, as edgartools has it."""
    if sections:
        text = _text_of(sections.get(f"part_{part}_item_{item}"))
        if text and text.strip():
            return text
        combined = re.compile(rf"part_[iv]+_items_(?:{re.escape(item)}_and_\d+|\d+_and_{re.escape(item)})")
        for key in sections:
            if combined.match(key):
                text = _text_of(sections.get(key))
                if text and text.strip():
                    return text
        for key in (f"Item {item.upper()}", friendly):
            if key in sections:
                return _text_of(sections.get(key))
    index = cross_reference()
    item_html = index.extract_item_content(item.upper()) if index is not None else None
    if item_html:
        text = parse_html(item_html).text()
        if text and text.strip():
            text = text.rstrip()
            last_line = text.split("\n")[-1]
            return text.rstrip(last_line) if _PART_LINE.match(last_line) else text
    return None


def _sections_from_html(html: str, base_form: str) -> Optional[Dict[str, str]]:
    """Parse ``html`` (the decoded primary document) and return the summary's canonical sections.

    Returns ``{"financials" | "mda" | "risk": text}`` with only the sections that parsed to real
    content, or None when the form is unsupported, the document is empty or too large, or nothing
    usable was found (callers then fall back to the regex extractor). A read error that leaves no
    section is raised for the service to log with the accession, never swallowed
    (``lessons/sec-run-our-entry-point-before-ruling-an-upstream-fix-out.md``).
    """
    if base_form not in ("10-K", "10-Q", "20-F") or not html:
        return None
    if len(html) > _MAX_SECTION_HTML_CHARS:
        logger.info(f"Section parse skipped: {len(html):,}-char {base_form} document is over the size cap")
        return None
    error: Optional[Exception] = None
    try:
        sections = HTMLParser(ParserConfig(form=base_form)).parse(html).sections
    except Exception as exc:  # noqa: BLE001 - a 10-K can still read the Cross Reference Index
        if base_form != "10-K":
            raise  # a 10-Q or 20-F has no other source
        sections, error = {}, exc  # TenK still tries the Cross Reference Index when its parser fails

    out: Dict[str, str] = {}
    if base_form == "10-K":
        index_cache: list = []

        def cross_reference() -> Optional[CrossReferenceIndex]:
            if not index_cache:  # built at most once, and only if a lookup gets that far
                index = CrossReferenceIndex(html)
                index_cache.append(index if index.has_index() else None)
            return index_cache[0]

        for canonical, item, part, friendly in _TEN_K_ITEMS:
            try:
                text = _ten_k_item(sections, item, part, friendly, cross_reference)
            except Exception as exc:  # noqa: BLE001 - a single missing/odd section must not abort the rest
                text, error = None, error or exc
            if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                out[canonical] = text.strip()
    else:
        for canonical, keys in _PART_KEYS[base_form]:
            for key in keys:
                text = _text_of(sections.get(key)) if hasattr(sections, "get") else None
                if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                    out[canonical] = text.strip()
                    break

    if not out and error is not None:
        raise error  # the first read error, as the reason nothing parsed
    return out or None
