"""Attach exact section-owned units to model output — capital-plan quotes and declared table-cell scales; never rescale a number."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.services.ai.recovery_context import clean_filing_source, recovery_blocks
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
# the scale word the source table declares, and only when every occurrence of that exact figure in
# the offered excerpt is a DEMONSTRATED table cell (delimited by the flattening's own cell
# separators, or a value-only line) whose row and banner are bound through table lines alone. It
# abstains when the source's own prose writes the figure bare (an issuer convention the MD&A-title
# owner above handles for its one documented form), when a cell is not delimited, when occurrences
# disagree, when the row or its detached label is excluded from the declared scale (per-share,
# counts, a foreign unit token), when prose, a heading run or another scope token separates the row
# from its banner, or when a literal reading is supported by XBRL. The figure's digits are never
# changed; nothing is rescaled.

_TABLE_SCALE_WORD = {
    "thousand": "thousand", "thousands": "thousand",
    "million": "million", "millions": "million",
    "billion": "billion", "billions": "billion",
}
# A banner at the start of a flattened table line: "(Amounts in millions)", "(Dollars in millions)",
# "(in thousands, except margin)", "($ in millions)", "(In millions, except per share amounts)".
_TABLE_DECLARATION = re.compile(
    r"^\((?:(?:amounts?|dollars?|figures|values|usd|us\$|\$)\s*)?(?:in\s+)?"
    r"(thousands?|millions?|billions?)\b[^)]*\)",
    re.I,
)
# A banner naming another currency is not a dollar scale; the bare "$" is a separate defect.
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
# Rows a "(… in millions, except …)" banner does not scale, or that are not dollar amounts at all.
# "due within one year" names a maturity band, so "year" alone never excludes a row.
_UNSCALED_ROW_LABEL = re.compile(
    r"\b(?:per[\s-]+(?:share|unit|adr|ads)|shares?|units?|counts?|number of|employees|associates|"
    r"stores|clubs|warehouses|square|percent|percentage|ratio|basis points)\b|\((?:in )?years?\)",
    re.I,
)
# A parenthesised unit, currency, per-unit or scope token on a header or label ("Fee ($)",
# "(in dollars)", "(per share)", "(%)") declares a scope this owner does not resolve.
_SCOPE_TOKEN = re.compile(
    r"\(\s*(?:\$|%|us\$|in\s+[a-z]|per\s+[a-z]|amounts?\b|dollars?\b|thousands?\b|millions?\b|billions?\b)",
    re.I,
)
_LINE_WORDS = re.compile(r"[A-Za-z]{2,}")
_SENTENCE_END = re.compile(r"(?<!\bU\.S)(?<!\bInc)(?<!\bCorp)(?<!\bNo)(?<!\bMr)(?<!\bMs)[.!?:](?:\s|$)")
# A whole line made of numeric cells (one-value-per-line flattening), dashes included.
_VALUE_ONLY_LINE = re.compile(
    r"^(?:[\s\xa0]*(?:\(?\$?\s*-?\d[\d,]*(?:\.\d+)?\s*%?\)?|[—–-])[\s\xa0]*)+$"
)
# A numeric cell on a row: a comma-grouped, decimal or percentage number at a cell boundary, or any
# digits closed by the flattening's own separator. A heading's stray digit ("Item 5") is not a cell.
_ROW_CELL = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+\.\d+|\d+%)(?=\)|\xa0|  |%|$)|\d(?=\xa0|  |\))")
_PROSE_WORDS = 12
_SENTENCE_WORDS = 4
_MAX_TEXT_RUN = 3
_DECLARATION_LOOKBACK_LINES = 80
_AUDIT_CAP = 40
_YEAR_GLUE = re.compile(r"(?:^|\D)((?:19|20)\d{2})$")
_CELL_DELIMITERS = ("\xa0", "  ")


def _is_prose_line(line: str) -> bool:
    """A flattened table row is a label plus cells; a filing sentence is long or ends a sentence."""
    words = _LINE_WORDS.findall(line)
    if len(words) >= _PROSE_WORDS:
        return True
    return len(words) >= _SENTENCE_WORDS and bool(_SENTENCE_END.search(line))


def _is_value_only(line: str) -> bool:
    return bool(line.strip()) and bool(_VALUE_ONLY_LINE.match(line))


def _is_statement_heading(line: str) -> bool:
    """A financial statement's own section heading is set in capitals (``ASSETS``)."""
    return line.upper() == line and any(ch.isalpha() for ch in line)


def _governing_table_scale(lines: Sequence[str], index: int) -> str | None:
    """The banner bound to line ``index`` through table lines only.

    The block between the nearest banner above and line ``index`` is validated top-down: prose,
    any other unit/scope token or a non-dollar banner abstains; the banner may be followed by a
    header block of at most ``_MAX_TEXT_RUN`` text lines; after the first row, a text line is
    admitted only as a statement section heading (all capitals, the statements' own convention:
    ``ASSETS``, ``LIABILITIES AND EQUITY``) or as the label of the row or value-only line directly
    beneath it. Any other text (a heading run, a new table's title and header, a label with
    nothing numeric under it) severs the row from the banner."""
    block: list[str] = []
    scale: str | None = None
    for j in range(index - 1, -1, -1):
        line = lines[j].strip()
        if not line:
            continue
        banner = _TABLE_DECLARATION.match(line)
        if banner:
            if _NON_DOLLAR_BANNER.search(banner.group(0)):
                return None
            scale = _TABLE_SCALE_WORD[banner.group(1).lower()]
            break
        if _SCOPE_TOKEN.search(line) or _is_prose_line(line):
            return None
        block.append(line)
        if len(block) > _DECLARATION_LOOKBACK_LINES:
            return None
    if scale is None:
        return None
    block.reverse()
    header = 0
    for position, line in enumerate(block):
        if _ROW_CELL.search(line) or _is_value_only(line):
            header = -1
            continue
        if header >= 0:
            header += 1
            if header > _MAX_TEXT_RUN:
                return None
            continue
        if _is_statement_heading(line):
            continue
        following = block[position + 1] if position + 1 < len(block) else lines[index].strip()
        if not (_ROW_CELL.search(following) or _is_value_only(following)):
            return None
    return scale


def _detached_label(lines: Sequence[str], index: int) -> str | None:
    """The nearest preceding non-value line of a value-only row, or None when none exists."""
    for j in range(index - 1, -1, -1):
        line = lines[j].strip()
        if not line or _is_value_only(line):
            continue
        return "" if _TABLE_DECLARATION.match(line) else line
    return None


def _cell_kind(line: str, start: int, end: int) -> str | None:
    """'cell' when ``line[start:end]`` is a demonstrated table cell, 'percent' when it is a
    percentage cell, 'undelimited' when the digits are whole but no cell separator owns them, None
    when they are part of a larger number (a decimal, a longer digit run)."""
    before = line[:start]
    after = line[end:]
    if after and (after[0] in "0123456789," or (after[0] == "." and after[1:2].isdigit())):
        return None
    if before and before[-1] in ",.":
        return None
    if before and before[-1].isdigit() and not _YEAR_GLUE.search(before):
        # Two cells glued without a separator, or a longer number: not this figure.
        return None
    if after.lstrip(" \xa0")[:1] == "%":
        return "percent"
    if _is_value_only(line):
        return "cell"
    opened = before.endswith("(") or before.endswith("($")
    if after.startswith(_CELL_DELIMITERS) or (after.startswith(")") and opened):
        return "cell"
    stripped_before = before[:-1] if before.endswith("$") else before
    if not after and (opened or stripped_before.endswith(_CELL_DELIMITERS)):
        return "cell"
    return "undelimited"


@dataclass(frozen=True)
class TableUnitIndex:
    """The offered excerpt, line-addressed, with per-figure resolutions cached on demand."""

    lines: tuple[str, ...]
    _cache: dict = field(default_factory=dict, compare=False)

    def resolve(self, figure: str) -> tuple[str | None, str]:
        """``(scale word, reason)``: the one declared scale every demonstrated-cell occurrence of
        ``figure`` shares, else ``(None, why)``. Reasons are audit vocabulary, not user text."""
        if figure in self._cache:
            return self._cache[figure]
        result = self._resolve(figure)
        self._cache[figure] = result
        return result

    def _resolve(self, figure: str) -> tuple[str | None, str]:
        scales: set[str] = set()
        for index, line in enumerate(self.lines):
            position = line.find(figure)
            while position >= 0:
                start, position = position, line.find(figure, position + 1)
                kind = _cell_kind(line, start, start + len(figure))
                if kind is None:
                    continue
                if kind == "percent":
                    return None, "percent_occurrence"
                if _is_prose_line(line):
                    tail = line[start + len(figure):].lstrip()
                    word = tail.split(" ", 1)[0].rstrip(",.;:)").lower() if tail else ""
                    if word in _TABLE_SCALE_WORD:
                        scales.add(_TABLE_SCALE_WORD[word])
                        continue
                    return None, "prose_occurrence"
                if kind == "undelimited":
                    return None, "undelimited_cell"
                label = _detached_label(self.lines, index) if _is_value_only(line) else line[:start]
                if label is None:
                    return None, "no_governing_banner"
                if _UNSCALED_ROW_LABEL.search(label) or _SCOPE_TOKEN.search(label):
                    return None, "unscaled_row"
                scale = _governing_table_scale(self.lines, index)
                if scale is None:
                    return None, "no_governing_banner"
                scales.add(scale)
        if len(scales) == 1:
            return next(iter(scales)), "declared"
        return None, ("mixed_scales" if scales else "no_occurrence")


def build_table_unit_index(offered_excerpt: str = "") -> TableUnitIndex | None:
    """Line-address the exact cleaned excerpt the model read; None when there is no source."""
    source = clean_filing_source(offered_excerpt or "")
    if not source.strip():
        return None
    return TableUnitIndex(tuple(source.split("\n")))


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
