"""Attach exact section-owned units to model output — capital-plan quotes and declared table-cell scales; never rescale a number."""
from __future__ import annotations

import re
from typing import Any, Sequence

from lxml import etree, html

from app.services.ai.recovery_context import clean_filing_source, recovery_blocks
from app.services.edgar.statement_relationship_source import _cells, _nearby, _text
from app.services.provenance_service import _MIN_VERIFIABLE_LEN

# Deliberately narrow: a declaration immediately below the actual MD&A title, not a
# nearby table header. All exceptions are preserved verbatim. Unrecognized scopes abstain.
_DECLARATION = re.compile(
    r"\A(?:Table of Contents\s+)?Item[ \t\xa0]+2[ \t\xa0]*[—–-][ \t\xa0]*"
    r"Management[’']s Discussion and Analysis of Financial Condition and Results of Operations"
    r"\s*\n\s*(\(amounts in millions, except per share, share, percentages and warehouse count data\))",
)
_OTHER_SCOPE = re.compile(r"\b(?:amounts? in|in thousands|in millions|in billions)\b", re.I)
_CAPITAL_HEADING = "Capital Expenditure Plans"
_CONTEXT_KEY = "source_unit_context"


def attach_quote_unit_context(
    sections: dict[str, Any],
    offered_excerpt: str = "",
    layout: Sequence[tuple[str, str, int]] = (),
    *,
    recovered: bool = False,
) -> None:
    """Replace model annotations with source-owned final-primary context, or abstain.

    No source on preview, recovered forward section, missing section boundaries, multiple
    matches or conflicting scopes means no annotation. Quote/evidence bytes are untouched.
    Offsets are used only inside the exact cleaned representation, never as HTML locators.
    """
    forward = sections.get("forward_signals")
    quotes = forward.get("quotes") if isinstance(forward, dict) else None
    if not isinstance(quotes, list):
        return
    for quote in quotes:
        if isinstance(quote, dict):
            quote.pop(_CONTEXT_KEY, None)
    if recovered or not offered_excerpt or not layout:
        return
    source = clean_filing_source(offered_excerpt)
    blocks = recovery_blocks(source, layout)
    for quote in quotes:
        text = quote.get("quote") if isinstance(quote, dict) else None
        if not isinstance(text, str) or len(text.strip()) < _MIN_VERIFIABLE_LEN:
            continue
        # Whole raw match only: no fuzzy match, convenient inner fragment or normalized
        # indexes masquerading as source offsets. Duplicate occurrence is ambiguous.
        if source.count(text) != 1 or "$" not in text:
            continue
        candidates: list[str] = []
        for block in blocks:
            if block.families != ("mda",) or block.text.count(text) != 1:
                continue
            declaration = _DECLARATION.match(block.text)
            if declaration is None or _OTHER_SCOPE.search(block.text[declaration.end():]):
                continue
            heading = block.text.find(_CAPITAL_HEADING, declaration.end())
            if heading < 0 or block.text.count(_CAPITAL_HEADING) != 1:
                continue
            # Only the first paragraph under this exact standalone heading qualifies.
            if block.text[heading - 1:heading] != "\n":
                continue
            after_heading = heading + len(_CAPITAL_HEADING)
            if not block.text[after_heading:].startswith("\n\n"):
                continue
            paragraph_start = after_heading + 2
            paragraph_end = block.text.find("\n\n", paragraph_start)
            if paragraph_end < 0:
                continue  # an unterminated/truncated paragraph has no demonstrated boundary
            start = block.text.find(text)
            if paragraph_start <= start and start + len(text) <= paragraph_end:
                candidates.append(declaration[1])
        if len(candidates) == 1:
            quote[_CONTEXT_KEY] = candidates[0]


# This finite proposition supports one documented missing-unit form, not arbitrary paraphrases.
_NUMBER = r"\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_SPEND_PLAN = re.compile(
    r"it is our current intention to spend approximately "
    rf"(?P<amount>{_NUMBER}) during fiscal (?P<year>\d{{4}})(?=[,.])"
)
_AUTHORED_PLAN = re.compile(
    r"\bcurrent intention to spend approximately "
    rf"(?P<amount>{_NUMBER}) on capital expenditures during fiscal (?P<year>\d{{4}})(?=[,.]| and plans to )"
)
# Keep attribution and affirmative reporting separate from the financial proposition.
# Unknown subjects, modals, denial and preceding sentences abstain; no opaque prefix.
_AFFIRMATIVE_PLAN_INTRO = re.compile(
    r"(?:The (?:[Cc]ompany|filing)|[Mm]anagement) "
    r"(?:states?|stated|reports?|reported|notes?|noted|describes?|described) "
    r"(?:that )?(?:(?:it is|there is) )?(?:its|a|the) "
)
_AMBIGUOUS_PLAN = re.compile(
    r'["“”]|\b(?:not|never|if|unless|conditional|subsidiary|segment)\b', re.I
)


def capital_plan_proposition(
    offered_excerpt: str = "", layout: Sequence[tuple[str, str, int]] = (),
) -> tuple[str, str] | None:
    """A unique source-owned dollar spending intention and fiscal year, with million scope."""
    source = clean_filing_source(offered_excerpt)
    matches = list(_SPEND_PLAN.finditer(source))
    if len(matches) != 1:
        return None
    match = matches[0]
    start = source.rfind("\n\n", 0, match.start()) + 2
    end = source.find("\n\n", match.end())
    if end < 0 or _AMBIGUOUS_PLAN.search(source[start:end]):
        return None
    # Reuse the exact quote ownership contract without altering any real quote or trusting a badge.
    probe = {"forward_signals": {"quotes": [{"quote": match[0]}]}}
    attach_quote_unit_context(probe, source, layout)
    context = probe["forward_signals"]["quotes"][0].get(_CONTEXT_KEY)
    if context != "(amounts in millions, except per share, share, percentages and warehouse count data)":
        return None
    return match['amount'], match['year']


def restore_authored_plan_units(
    sections: dict[str, Any], proposition: tuple[str, str] | None = None,
) -> None:
    """Insert only the owned scale in a matching authored plan; all other bytes stay intact."""
    forward = sections.get('forward_signals')
    guidance = forward.get('guidance') if isinstance(forward, dict) else None
    if not proposition or not isinstance(guidance, str) or _AMBIGUOUS_PLAN.search(guidance):
        return
    match = _AUTHORED_PLAN.search(guidance)
    if (match is None or (match['amount'], match['year']) != proposition
            or _AFFIRMATIVE_PLAN_INTRO.fullmatch(guidance[:match.start()]) is None):
        return
    # More than one spending intention is ambiguous even if the initial amount happens to match.
    if guidance.count('intention to spend') != 1:
        return
    offset = match.end('amount')
    forward['guidance'] = guidance[:offset] + ' million' + guidance[offset:]


# --- declared table-cell scale restoration ------------------------------------------------------
#
# A model copies a cell ("3,542") from a table whose banner declares "(Amounts in millions)" and
# writes "$3,542": the VALUE is source-exact while the UNIT is one million times too small
# (retained candidate-r WMT 10-K run 1, maturities bullet). ``figure_trace`` deliberately ignores
# unit-less dollar figures, so the class was invisible to the dollar gate. This owner restores ONLY
# the scale word the SOURCE DOCUMENT declares for that figure, and only when every occurrence of
# the exact digits in the filing's own HTML is owned by a structured declaration: an inline-XBRL
# fact whose ``scale`` attribute and USD unit declare the number's own measure, or a ``<td>`` that
# holds exactly that amount inside a ``<table>`` whose own cells (or the one node immediately
# before it) declare the scale, on a row whose label and column headers are not excluded from it.
# Flattened excerpt text carries no table boundary, so it never owns anything: a list item, a short
# sentence or an adjacent unbannered table cannot inherit a banner because they are not cells of
# the declaring table. It abstains when the issuer's prose writes the digits bare anywhere in the
# document, when a fact declares the bare reading (``scale="0"``), when occurrences disagree, when
# the row, column or fact unit is per-share/count/percent, when the table has no declaration of
# its own, when the source document is unavailable (cached-excerpt generations), or when a literal
# reading is supported by standardized XBRL. The figure's digits are never changed.

_TABLE_SCALE_WORD = {
    "thousand": "thousand", "thousands": "thousand",
    "million": "million", "millions": "million",
    "billion": "billion", "billions": "billion",
}
# Inline-XBRL ``scale`` attribute → the fact's own unit multiplier (``0``/absent = as written).
_FACT_SCALE_WORD = {"3": "thousand", "6": "million", "9": "billion"}
# A scale declaration inside a table's own cells or caption, or as the whole text of the node
# immediately before the table: "(Amounts in millions)", "(Dollars in millions)", "($ in millions)",
# "(In millions, except per share amounts)", "Expected Maturity Date (Amounts in millions)".
_TABLE_DECLARATION = re.compile(
    r"\((?:(?:amounts?|dollars?|figures|values|usd|us\$|\$)\s*)?(?:in\s+)?"
    r"(thousands?|millions?|billions?)\b[^)]*\)",
    re.I,
)
# A declaration naming another currency is not a dollar scale; the bare "$" is a separate defect.
_NON_DOLLAR_BANNER = re.compile(
    r"\b(?:euros?|eur|rmb|cny|yen|jpy|dkk|sek|nok|chf|gbp|pounds?|krw|inr|brl|twd|hkd|sgd|aud|cad)\b"
    r"|nt\$|hk\$|€|£|¥",
    re.I,
)
# A model-authored bare dollar figure: "$" + comma-grouped integer, no scale word (singular or
# plural), no decimals, not a currency-prefixed form ("US$", "NT$") and not a percentage.
_BARE_DOLLAR_FIGURE = re.compile(
    r"(?<![A-Za-z$\d,.])\$(\d{1,3}(?:,\d{3})+)"
    r"(?![\d,]|\.\d|\s*(?:thousands?|millions?|billions?|trillions?|bn|mn|tn|[kmbt])\b|\s*%)",
    re.I,
)
# Rows a "(… in millions, except …)" declaration does not scale, or that are not dollar amounts.
# "due within one year" names a maturity band, so "year" alone never excludes a row.
_UNSCALED_ROW_LABEL = re.compile(
    r"\b(?:per[\s-]+(?:share|unit|adr|ads)|shares?|units?|counts?|number of|employees|associates|"
    r"stores|clubs|warehouses|square|percent|percentage|ratio|basis points)\b|\((?:in )?years?\)",
    re.I,
)
# A parenthesised unit, currency, per-unit or scope token on a label ("Fee ($)", "(in dollars)",
# "(per share)", "(%)") declares a scope this owner does not resolve.
_SCOPE_TOKEN = re.compile(
    r"\(\s*(?:\$|%|us\$|in\s+[a-z]|per\s+[a-z]|amounts?\b|dollars?\b|thousands?\b|millions?\b|billions?\b)",
    re.I,
)
# A column header that declares a non-dollar or unscaled column ("Shares", "Per share", "Rate", "%");
# a scope token on a header ("Fee ($)") is checked with the same ``_SCOPE_TOKEN`` as row labels.
_UNSCALED_COLUMN = re.compile(
    r"\b(?:shares?|units?|per[\s-]+(?:share|unit|adr|ads)|rate|percent|percentage|counts?|number)\b|%",
    re.I,
)
# A cell that is exactly one comma-grouped amount, optionally in parentheses or after "$".
_CELL_AMOUNT = re.compile(r"^\(?\s*\$?\s*(\d{1,3}(?:,\d{3})+)\s*\)?$")
_SKIP_TAGS = frozenset({"script", "style", "title"})
_AUDIT_CAP = 40


def _ancestor(node: Any, tags: frozenset[str]) -> Any:
    for candidate in (node, *node.iterancestors()):
        if isinstance(candidate.tag, str) and candidate.tag.lower() in tags:
            return candidate
    return None


class TableUnitIndex:
    """The filing's own source document, parsed on first use; per-figure resolutions cached.

    Ownership evidence is structural: inline-XBRL facts (``ix:nonFraction`` scale + unit) and
    ``<table>`` cells under the table's own declaration. Text outside a cell is prose."""

    def __init__(self, source_html: str) -> None:
        self._html = source_html
        self._cache: dict[str, tuple[str | None, str]] = {}
        self._document: Any = None
        self._parsed = False
        self._chunks: list[tuple[str, Any]] | None = None
        self._units: dict[str, list[str]] | None = None
        self._tables: dict[int, tuple[Any, tuple[str | None, str]]] = {}

    def resolve(self, figure: str) -> tuple[str | None, str]:
        """``(scale word, reason)``: the one declared scale every occurrence of ``figure`` in the
        source document shares, else ``(None, why)``. Reasons are audit vocabulary, not user text."""
        if figure in self._cache:
            return self._cache[figure]
        result = self._resolve(figure)
        self._cache[figure] = result
        return result

    # -- document access -------------------------------------------------------------------------

    def _parse(self) -> Any:
        if not self._parsed:
            self._parsed = True
            try:
                self._document = html.fromstring(
                    self._html.encode("utf-8"),
                    parser=html.HTMLParser(encoding="utf-8", no_network=True),
                )
            except (ValueError, TypeError, etree.ParserError, etree.XMLSyntaxError):
                self._document = None
        return self._document

    def _digit_chunks(self) -> list[tuple[str, Any]]:
        """Every text node carrying a digit, with the element that owns it (tails belong to the
        parent). Built once; a figure lookup is then a substring scan, not a document walk."""
        if self._chunks is None:
            chunks: list[tuple[str, Any]] = []
            document = self._parse()
            for node in (document.iter() if document is not None else ()):
                if not isinstance(node.tag, str) or node.tag.lower() in _SKIP_TAGS:
                    continue
                if node.text and any(ch.isdigit() for ch in node.text):
                    chunks.append((node.text, node))
                for child in node:
                    if child.tail and any(ch.isdigit() for ch in child.tail):
                        chunks.append((child.tail, node))
            self._chunks = chunks
        return self._chunks

    def _unit_measures(self) -> dict[str, list[str]]:
        if self._units is None:
            units: dict[str, list[str]] = {}
            document = self._parse()
            for node in (document.iter() if document is not None else ()):
                if isinstance(node.tag, str) and node.tag.lower().endswith(":unit") and node.get("id"):
                    units[node.get("id")] = [
                        _text(m).lower() for m in node.iter()
                        if isinstance(m.tag, str) and m.tag.lower().endswith(":measure")
                    ]
            self._units = units
        return self._units

    # -- ownership -------------------------------------------------------------------------------

    def _resolve(self, figure: str) -> tuple[str | None, str]:
        if self._parse() is None:
            return None, "no_source_document"
        scales: set[str] = set()
        found = False
        for text, node in self._digit_chunks():
            if figure not in text:
                continue
            found = True
            fact = _ancestor(node, frozenset({"ix:nonfraction"}))
            scale, reason = (
                self._fact_scale(fact, figure) if fact is not None else self._cell_scale(node, figure)
            )
            if scale is None:
                return None, reason
            scales.add(scale)
        if not found:
            return None, "no_occurrence"
        if len(scales) == 1:
            return next(iter(scales)), "declared"
        return None, "mixed_scales"

    def _fact_scale(self, fact: Any, figure: str) -> tuple[str | None, str]:
        """An inline-XBRL fact declares its own multiplier and unit; the digits must be the whole fact."""
        if _text(fact) != figure:
            return None, "prose_occurrence"
        measures = self._unit_measures().get(fact.get("unitref") or "", [])
        if measures != ["iso4217:usd"]:
            return None, "non_dollar_unit"
        scale = (fact.get("scale") or "0").strip()
        if scale == "0":
            return None, "declared_unscaled"
        word = _FACT_SCALE_WORD.get(scale)
        return (word, "declared") if word else (None, "unsupported_scale")

    def _cell_scale(self, node: Any, figure: str) -> tuple[str | None, str]:
        """An untagged cell is owned by its table's own declaration, its row label and its column."""
        cell = _ancestor(node, frozenset({"td", "th"}))
        if cell is None:
            return None, "prose_occurrence"
        text = _text(cell)
        match = _CELL_AMOUNT.match(text)
        if not match or match.group(1) != figure:
            return None, ("percent_occurrence" if text.rstrip().endswith("%") else "prose_occurrence")
        row = _ancestor(cell, frozenset({"tr"}))
        table = _ancestor(cell, frozenset({"table"}))
        if row is None or table is None:
            return None, "prose_occurrence"
        scale, reason = self._table_scale(table)
        if scale is None:
            return None, reason
        row_cells = row.xpath("./td|./th")
        cells = _cells(row)
        if cells is None or cell not in row_cells:
            return None, "unsupported_row"
        index = row_cells.index(cell)
        first = next((i for i, c in enumerate(cells) if c["text"]), None)
        if first is None or first >= index:
            return None, "no_row_label"
        label = cells[first]["text"]
        if _UNSCALED_ROW_LABEL.search(label) or _SCOPE_TOKEN.search(label):
            return None, "unscaled_row"
        following = next((c["text"] for c in cells[index + 1:] if c["text"]), "")
        if following.startswith("%"):
            return None, "percent_occurrence"
        start, end = cells[index]["column"], cells[index]["column"] + cells[index]["colspan"]
        rows = table.xpath("./tr|./thead/tr|./tbody/tr")
        matrix = [_cells(r) for r in rows]
        width = max((c["column"] + c["colspan"] for cs in matrix if cs for c in cs), default=0)
        for above in matrix[:rows.index(row)] if row in rows else []:
            for header in above or []:
                if (header["text"] and header["colspan"] < width
                        and header["column"] < end and header["column"] + header["colspan"] > start
                        and not _TABLE_DECLARATION.search(header["text"])
                        and (_UNSCALED_COLUMN.search(header["text"]) or _SCOPE_TOKEN.search(header["text"]))):
                    return None, "unscaled_column"
        return scale, "declared"

    def _table_scale(self, table: Any) -> tuple[str | None, str]:
        """The one dollar scale a table declares in its own cells or caption, else in the single
        text node immediately before it; anything else abstains."""
        key = id(table)
        if key in self._tables:
            return self._tables[key][1]
        words: set[str] = set()
        non_dollar = False
        texts = [_text(c) for c in table.xpath("./caption|./tr/td|./tr/th|./thead/tr/th|./thead/tr/td|"
                                               "./tbody/tr/td|./tbody/tr/th")]
        if not any(_TABLE_DECLARATION.search(t) for t in texts):
            preceding = next((n for n in _nearby(table) if _text(n)), None)
            declaration = _TABLE_DECLARATION.fullmatch(_text(preceding)) if preceding is not None else None
            texts = [declaration.group(0)] if declaration else []
        for text in texts:
            for match in _TABLE_DECLARATION.finditer(text):
                if _NON_DOLLAR_BANNER.search(match.group(0)):
                    non_dollar = True
                words.add(_TABLE_SCALE_WORD[match.group(1).lower()])
        if non_dollar:
            result: tuple[str | None, str] = (None, "non_dollar_banner")
        elif len(words) == 1:
            result = (next(iter(words)), "declared")
        else:
            result = (None, "mixed_scales" if words else "no_governing_banner")
        self._tables[key] = (table, result)
        return result


def build_table_unit_index(source_html: str = "") -> TableUnitIndex | None:
    """Hold the filing's own source document for on-demand ownership; None when there is none."""
    if not source_html or not source_html.strip():
        return None
    return TableUnitIndex(source_html)


def _literal_supported(value: float, xbrl_values: Sequence[float]) -> bool:
    return any(abs(value - v) <= 0.5 for v in xbrl_values)


def restore_table_cell_units(
    sections: dict[str, Any],
    index: TableUnitIndex | None,
    *,
    xbrl_metrics: dict | None = None,
    recovered: Any = (),
) -> dict[str, Any] | None:
    """Insert the declared scale word after each bare dollar figure the source table owns.

    Mutates the policed model-prose slots in place (``figure_trace.policed_prose_slots``); recovered
    sections are skipped because their context was separately selected. Callers run it after the
    source binders so only surviving model prose is measured. Returns the audit
    ``{"restored_count", "unresolved_count", "restored": [...], "unresolved": [...]}`` (lists
    capped at ``_AUDIT_CAP``) or None when no bare figure was found.
    """
    from app.services.ai.figure_trace import policed_prose_slots, xbrl_values

    if index is None or not isinstance(sections, dict):
        return None
    recovered_keys = frozenset(recovered or ())
    grounded = xbrl_values(xbrl_metrics) if xbrl_metrics else []
    restored: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    found = False
    for slot, container, key, text in list(policed_prose_slots(sections)):
        matches = list(_BARE_DOLLAR_FIGURE.finditer(text))
        if not matches:
            continue
        found = True
        section = re.split(r"[.\[]", slot, 1)[0]
        if section in recovered_keys:
            unresolved.extend({"slot": slot, "figure": m.group(0), "reason": "recovered"} for m in matches)
            continue
        edited = text
        for match in reversed(matches):
            figure = match.group(1)
            scale, reason = index.resolve(figure)
            value = float(figure.replace(",", ""))
            if scale is not None and _literal_supported(value, grounded):
                scale, reason = None, "literal_xbrl_match"
            if scale is None:
                unresolved.append({"slot": slot, "figure": match.group(0), "reason": reason})
                continue
            corroborated = _literal_supported(
                value * {"thousand": 1e3, "million": 1e6, "billion": 1e9}[scale], grounded,
            )
            edited = edited[:match.end()] + " " + scale + edited[match.end():]
            restored.append({"slot": slot, "figure": match.group(0), "unit": scale,
                             "xbrl_corroborated": corroborated})
        if edited != text:
            container[key] = edited
    if not found:
        return None
    # Totals are exact; the detail lists are capped so a pathological summary cannot bloat the row.
    return {"restored_count": len(restored), "unresolved_count": len(unresolved),
            "restored": restored[:_AUDIT_CAP], "unresolved": unresolved[:_AUDIT_CAP]}
