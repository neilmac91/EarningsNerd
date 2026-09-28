"""Attach exact section-owned units to model output — capital-plan quotes and declared table-cell scales; never rescale a number."""
from __future__ import annotations

import re
from typing import Any, Sequence

from lxml import etree, html

from app.services.ai.recovery_context import clean_filing_source, recovery_blocks
from app.services.edgar.debt_concepts import DEBT_MATURITY_SEQUENCE, DEBT_MATURITY_TOTAL
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
# A model copies the long-term debt maturity schedule ("3,542", "3,237", …) from a table whose
# banner declares "(Amounts in millions)" and writes "2027: $3,542; 2028: $3,237; …": every VALUE
# is source-exact while every UNIT is one million times too small (retained candidate-r WMT 10-K
# run 1, maturities bullet). ``figure_trace`` deliberately ignores unit-less dollar figures, so the
# class was invisible to the dollar gate. This owner repairs exactly ONE finite proposition, the
# complete long-term-debt maturity sequence, and nothing else:
#
#   the authored text is the affirmative introduction "[Annual|Contractual|Scheduled] maturities of
#   [our] long-term debt [during|for|over the next five [fiscal] years and thereafter] [are|were] as
#   follows:" followed by exactly five consecutive fiscal-year pairs, "Thereafter" and "Total",
#   each a bare "$N,NNN", and nothing after the total;
#
#   the filing's own inline XBRL carries, on the validated DEI report period, exactly one fact for
#   each of the six schedule concepts of ``debt_concepts.DEBT_MATURITY_SEQUENCE`` and one for the
#   schedule total concept, each in a table row labelled with that year / "Thereafter" / "Total",
#   in USD alone, with one shared ``scale`` of 3/6/9, whose digits equal the authored amounts in
#   order, whose first year is the fiscal year after the report period, and whose six amounts sum
#   to the total.
#
# Every part of that mapping (measure by concept, reporting basis by the sum identity, period by
# context, unit and scale by the fact's own attributes, row by label, order by position) is read
# from the source; the digits are never changed. Any other bare figure — an unlabelled amount, a
# different subject ("registration fees"), a reordered, partial or already-scaled sequence, a
# qualifier the grammar does not know, trailing text, a missing, conflicting, non-USD, scale-0 or
# other-period fact, a mismatched amount, row or year, a schedule that does not sum — is left
# unchanged with a recorded reason. Five review rounds showed every broader mechanism (banners,
# flattened lines, table geometry, cell ownership, digit-and-label binding) moving the
# counterexample rather than removing it; this owner does not read any of them.

# Inline-XBRL ``scale`` attribute → the fact's own unit multiplier (``0``/absent = as written).
_FACT_SCALE_WORD = {"3": "thousand", "6": "million", "9": "billion"}
_SCALE_FACTOR = {"thousand": 1e3, "million": 1e6, "billion": 1e9}
# A model-authored bare dollar figure: "$" + comma-grouped integer, no scale word (singular or
# plural), no decimals, not a currency-prefixed form ("US$", "NT$") and not a percentage.
_BARE_DOLLAR_FIGURE = re.compile(
    r"(?<![A-Za-z$\d,.])\$(\d{1,3}(?:,\d{3})+)"
    r"(?![\d,]|\.\d|\s*(?:thousands?|millions?|billions?|trillions?|bn|mn|tn|[kmbt])\b|\s*%)",
    re.I,
)
# The one supported introduction, with its supported qualifiers only.
_MATURITY_INTRO = re.compile(
    r"^(?:(?:annual|contractual|scheduled)\s+)?maturities\s+of\s+(?:our\s+)?long-term\s+debt"
    r"(?:\s+(?:during|for|over)\s+the\s+next\s+five\s+(?:fiscal\s+)?years\s+and\s+thereafter)?"
    r"(?:\s+(?:are|were))?\s+as\s+follows:$",
    re.I,
)
_AMOUNT = r"\$(\d{1,3}(?:,\d{3})+)"
_YEAR_PAIR = r"(\d{4}):\s*" + _AMOUNT
# Exactly five year pairs, Thereafter and Total, ";"-separated, an optional final period, nothing else.
_MATURITY_SEQUENCE = re.compile(
    r"^\s*" + r";\s*".join([_YEAR_PAIR] * 5)
    + r";\s*thereafter:\s*" + _AMOUNT + r";\s*total:\s*" + _AMOUNT + r"\.?\s*$",
    re.I,
)
_SKIP_TAGS = frozenset({"script", "style", "title"})
_AUDIT_CAP = 40
_SEQUENCE_LABELS = ("thereafter", "total")


def _normalize_label(label: str) -> str:
    return " ".join(label.replace("\xa0", " ").split()).rstrip(":").strip().lower()


def maturity_proposition(text: str) -> dict[str, Any] | None:
    """Parse ``text`` as the one supported proposition, or return None.

    Result: ``{"years": [int x5], "amounts": [str x7] (digits, in order), "ends": [int x7] (the
    index just after each "$N,NNN", in order)}``. The introduction grammar and the sequence shape
    are both exact; a reordered, partial, already-scaled or trailing-text form is not a proposition."""
    head, sep, tail = text.partition("as follows:")
    if not sep:
        return None
    intro = " ".join(head.split()) + " as follows:"
    if not _MATURITY_INTRO.match(intro):
        return None
    match = _MATURITY_SEQUENCE.match(tail)
    if not match:
        return None
    years = [int(match.group(i)) for i in (1, 3, 5, 7, 9)]
    if any(years[i + 1] != years[i] + 1 for i in range(4)):
        return None
    groups = (2, 4, 6, 8, 10, 11, 12)
    offset = len(head) + len(sep)
    return {"years": years, "amounts": [match.group(i) for i in groups],
            "ends": [offset + match.end(i) for i in groups]}


class TableUnitIndex:
    """The filing's own source document, parsed on first use; the proposition's resolution cached.

    Ownership evidence is the filing's tagged maturity sequence: concept, row label, DEI report
    period, unit, scale, amounts and their sum, all read from the source."""

    def __init__(self, source_html: str) -> None:
        self._html = source_html
        self._cache: dict[tuple[Any, ...], tuple[str | None, str]] = {}
        self._document: Any = None
        self._parsed = False
        self._facts: dict[str, list[Any]] | None = None
        self._units: dict[str, list[str]] | None = None
        self._contexts: dict[str, str | None] | None = None
        self._period: str | None = None
        self._period_read = False

    def resolve_maturity_sequence(self, years: Sequence[int], amounts: Sequence[str]) -> tuple[str | None, str]:
        """``(scale word, reason)`` for the authored sequence, else ``(None, why)``."""
        key = (tuple(years), tuple(amounts))
        if key in self._cache:
            return self._cache[key]
        result = self._resolve(list(years), list(amounts))
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
        """One walk: facts by qualified concept, unit measures, and each context's period end."""
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
                facts.setdefault((node.get("name") or "").strip(), []).append(node)
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

    def _resolve(self, years: list[int], amounts: list[str]) -> tuple[str | None, str]:
        if self._parse() is None:
            return None, "no_source_document"
        period = self._report_period()
        if period is None:
            return None, "no_report_period"
        if years[0] != int(period[:4]) + 1:
            return None, "year_mismatch"
        self._index()
        assert self._facts is not None and self._units is not None and self._contexts is not None
        concepts = (*DEBT_MATURITY_SEQUENCE, DEBT_MATURITY_TOTAL)
        labels = [*(str(year) for year in years), *_SEQUENCE_LABELS]
        scales: set[str] = set()
        for concept, label, amount in zip(concepts, labels, amounts):
            on_period = [fact for fact in self._facts.get(concept, [])
                         if self._contexts.get(fact.get("contextref") or "") == period]
            if not on_period:
                return None, "missing_fact"
            # Inline XBRL may repeat one fact in several tables (the retained WMT total appears in
            # the debt table and the schedule); repeats must agree, and one must sit in the schedule row.
            if len({_text(fact) for fact in on_period}) > 1:
                return None, "conflicting_facts"
            if _text(on_period[0]) != amount:
                return None, "amount_mismatch"
            if not any(self._row_label(fact) == label for fact in on_period):
                return None, "row_label_mismatch"
            for fact in on_period:
                if self._units.get(fact.get("unitref") or "", []) != ["iso4217:usd"]:
                    return None, "non_dollar_unit"
                scale = (fact.get("scale") or "0").strip()
                if scale == "0":
                    return None, "declared_unscaled"
                word = _FACT_SCALE_WORD.get(scale)
                if word is None:
                    return None, "unsupported_scale"
                scales.add(word)
        if len(scales) != 1:
            return None, "mixed_scales"
        values = [int(amount.replace(",", "")) for amount in amounts]
        if sum(values[:6]) != values[6]:
            return None, "sequence_does_not_sum"
        return next(iter(scales)), "declared"

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
    """Insert the declared scale word after each figure of a complete, source-owned long-term-debt
    maturity proposition; leave every other bare dollar figure exactly as written.

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
        proposition = maturity_proposition(text)
        if proposition is None:
            unresolved.extend({"slot": slot, "figure": m.group(0), "reason": "unsupported_proposition"}
                              for m in matches)
            continue
        scale, reason = index.resolve_maturity_sequence(proposition["years"], proposition["amounts"])
        values = [float(a.replace(",", "")) for a in proposition["amounts"]]
        if scale is not None and any(_literal_supported(v, grounded) for v in values):
            scale, reason = None, "literal_xbrl_match"
        figures = ["$" + a for a in proposition["amounts"]]
        if scale is None:
            unresolved.extend({"slot": slot, "figure": f, "reason": reason} for f in figures)
            continue
        edited = text
        for end in reversed(proposition["ends"]):
            edited = edited[:end] + " " + scale + edited[end:]
        for figure, value in zip(figures, values):
            restored.append({"slot": slot, "figure": figure, "unit": scale,
                             "xbrl_corroborated": _literal_supported(value * _SCALE_FACTOR[scale], grounded)})
        container[key] = edited
    if not found:
        return None
    # Totals are exact; the detail lists are capped so a pathological summary cannot bloat the row.
    return {"restored_count": len(restored), "unresolved_count": len(unresolved),
            "restored": restored[:_AUDIT_CAP], "unresolved": unresolved[:_AUDIT_CAP]}
