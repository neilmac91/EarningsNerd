"""Attach exact section-owned units to model output — capital-plan quotes and declared table-cell scales; never rescale a number."""
from __future__ import annotations

import re
from typing import Any, Sequence

from lxml import etree, html

from app.services.ai.recovery_context import clean_filing_source, recovery_blocks
from app.services.edgar.statement_context import source_report_period
from app.services.edgar.statement_relationship_source import _text
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
# writes "2027: $3,542": the VALUE is source-exact while the UNIT is one million times too small
# (retained candidate-r WMT 10-K run 1, maturities bullet). ``figure_trace`` deliberately ignores
# unit-less dollar figures, so the class was invisible to the dollar gate. This owner restores ONLY
# the scale word the SOURCE DOCUMENT declares for THAT proposition: the authored statement must
# pair the figure with a label ("2027: $3,542", "Total: $38,166"), and the filing's own HTML must
# hold an inline-XBRL fact with exactly those digits, in a table row whose label is that label,
# whose unit is USD alone, whose ``scale`` attribute declares a multiplier, and whose context ends
# on the filing's own DEI report period. That is a row/period/amount mapping between the authored
# claim and one source cell; a matching digit string elsewhere establishes nothing. Everything else
# abstains, byte-identical and with a reason: no label beside the figure, no tagged fact, no row
# with that label, a non-dollar or per-share unit, a fact that declares the bare reading
# (``scale="0"``), another period, disagreeing scales, no source document (cached-excerpt
# generations), or a literal reading supported by standardized XBRL. Banners, flattened excerpt
# lines, header geometry and typography are never read: four review rounds showed each such
# heuristic moving the counterexample instead of removing it. The figure's digits are never changed.

# Inline-XBRL ``scale`` attribute → the fact's own unit multiplier (``0``/absent = as written).
_FACT_SCALE_WORD = {"3": "thousand", "6": "million", "9": "billion"}
# A model-authored bare dollar figure: "$" + comma-grouped integer, no scale word (singular or
# plural), no decimals, not a currency-prefixed form ("US$", "NT$") and not a percentage.
_BARE_DOLLAR_FIGURE = re.compile(
    r"(?<![A-Za-z$\d,.])\$(\d{1,3}(?:,\d{3})+)"
    r"(?![\d,]|\.\d|\s*(?:thousands?|millions?|billions?|trillions?|bn|mn|tn|[kmbt])\b|\s*%)",
    re.I,
)
# The authored label a figure is paired with: the text between the previous delimiter and the
# colon immediately before the figure ("… as follows: 2027: $3,542; Thereafter: $23,255").
_AUTHORED_LABEL = re.compile(r"(?:^|[;:(—–])\s*([^;:()—–]{1,80}?)\s*:\s*$")
_SKIP_TAGS = frozenset({"script", "style", "title"})
_AUDIT_CAP = 40


def _normalize_label(label: str) -> str:
    return " ".join(label.replace("\xa0", " ").split()).rstrip(":").strip().lower()


def authored_label(text: str, end: int) -> str | None:
    """The label the authored text pairs with the figure starting at ``end``, or None."""
    match = _AUTHORED_LABEL.search(text[:end])
    return match.group(1) if match else None


class TableUnitIndex:
    """The filing's own source document, parsed on first use; per-proposition resolutions cached.

    Ownership evidence is one inline-XBRL fact bound to the authored label through its table row,
    to the filing through its DEI report period, and to a unit through its own attributes."""

    def __init__(self, source_html: str) -> None:
        self._html = source_html
        self._cache: dict[tuple[str, str | None], tuple[str | None, str]] = {}
        self._document: Any = None
        self._parsed = False
        self._facts: dict[str, list[Any]] | None = None
        self._units: dict[str, list[str]] | None = None
        self._contexts: dict[str, str | None] | None = None
        self._period: str | None = None
        self._period_read = False

    def resolve(self, figure: str, label: str | None) -> tuple[str | None, str]:
        """``(scale word, reason)``: the one scale the source declares for ``label: $figure``, else
        ``(None, why)``. Reasons are audit vocabulary, not user text."""
        key = (figure, label)
        if key in self._cache:
            return self._cache[key]
        result = self._resolve(figure, label)
        self._cache[key] = result
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

    def _index(self) -> None:
        """One walk: facts by their exact text, unit measures, and each context's period end."""
        if self._facts is not None:
            return
        facts: dict[str, list[Any]] = {}
        units: dict[str, list[str]] = {}
        contexts: dict[str, str | None] = {}
        document = self._parse()
        for node in (document.iter() if document is not None else ()):
            if not isinstance(node.tag, str):
                continue
            tag = node.tag.lower()
            if tag == "ix:nonfraction":
                facts.setdefault(_text(node), []).append(node)
            elif tag.endswith(":unit") and node.get("id"):
                units[node.get("id")] = [
                    _text(m).lower() for m in node.iter()
                    if isinstance(m.tag, str) and m.tag.lower().endswith(":measure")
                ]
            elif tag.endswith(":context") and node.get("id"):
                ends = [_text(m) for m in node.iter() if isinstance(m.tag, str)
                        and m.tag.lower().split(":")[-1] in ("instant", "enddate")]
                contexts[node.get("id")] = ends[0] if len(ends) == 1 else None
        self._facts, self._units, self._contexts = facts, units, contexts

    def _report_period(self) -> str | None:
        if not self._period_read:
            self._period_read = True
            document = self._parse()
            self._period = source_report_period(document) if document is not None else None
        return self._period

    # -- ownership -------------------------------------------------------------------------------

    def _resolve(self, figure: str, label: str | None) -> tuple[str | None, str]:
        if label is None:
            return None, "no_authored_label"
        if self._parse() is None:
            return None, "no_source_document"
        self._index()
        assert self._facts is not None and self._units is not None and self._contexts is not None
        facts = self._facts.get(figure, [])
        if not facts:
            return None, "no_tagged_fact"
        wanted = _normalize_label(label)
        bound = [fact for fact in facts if self._row_label(fact) == wanted]
        if not bound:
            return None, "no_matching_row"
        period = self._report_period()
        if period is None:
            return None, "no_report_period"
        scales: set[str] = set()
        for fact in bound:
            if self._units.get(fact.get("unitref") or "", []) != ["iso4217:usd"]:
                return None, "non_dollar_unit"
            if self._contexts.get(fact.get("contextref") or "") != period:
                return None, "period_mismatch"
            scale = (fact.get("scale") or "0").strip()
            if scale == "0":
                return None, "declared_unscaled"
            word = _FACT_SCALE_WORD.get(scale)
            if word is None:
                return None, "unsupported_scale"
            scales.add(word)
        if len(scales) == 1:
            return next(iter(scales)), "declared"
        return None, "mixed_scales"

    @staticmethod
    def _row_label(fact: Any) -> str | None:
        """The leftmost text cell of the fact's own table row, when it precedes the fact's cell."""
        cell = row = None
        for ancestor in fact.iterancestors():
            if not isinstance(ancestor.tag, str):
                continue
            tag = ancestor.tag.lower()
            if tag in ("td", "th") and cell is None:
                cell = ancestor
            elif tag == "tr":
                row = ancestor
                break
        if cell is None or row is None:
            return None
        for candidate in row.xpath("./td|./th"):
            if candidate is cell:
                return None
            text = _text(candidate)
            if text:
                return _normalize_label(text)
        return None


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
    """Insert the declared scale word after each bare dollar figure whose authored proposition
    ("label: $figure") one source fact owns.

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
            scale, reason = index.resolve(figure, authored_label(text, match.start()))
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
