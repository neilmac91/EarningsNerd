"""Source-owned financing comparison and verbatim capital-allocation evidence.

No model inference is admitted to this new representation. Source qualification is
performed by the filing extractor; this consumer never searches for other operands.
"""
from __future__ import annotations

import math
import re
from typing import Any

CAPITAL_CONTEXT_KEY = "capital_allocation_context_version"
CAPITAL_CONTEXT_VERSION = 1
OWNED_FIELD = "capital_allocation_verified"

# Unscaled numbers in a detached quotation can lose a table/section unit header.
# Keep only self-contained scales, percentages and calendar years; omit the whole
# passage on uncertainty rather than changing the source's words or guessing units.
_NUMBER = re.compile(r"(?<![\w])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_SCALE = re.compile(r"\s*(?:%|percent\b|thousand\b|million\b|billion\b|trillion\b)", re.I)

_PER_SHARE = re.compile(
    r"[$€£¥]\s*\d[\d,]*(?:\.\d+)?"
    r"(?:\s+(?:to|and)\s+[$€£¥]\s*\d[\d,]*(?:\.\d+)?)?"
    r"\s+per\s+(?:common\s+)?share\b", re.I,
)
_CALENDAR_DATE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?:[12]?\d|3[01]),?\s+(?:19|20)\d{2}\b", re.I,
)


def _self_contained_numbers(text: str) -> bool:
    denominated = [m.span() for pattern in (_PER_SHARE, _CALENDAR_DATE) for m in pattern.finditer(text)]
    for match in _NUMBER.finditer(text):
        if any(start <= match.start() and match.end() <= end for start, end in denominated):
            continue
        if _SCALE.match(text[match.end():]):
            continue
        token = match[0]
        if len(token) == 4 and token.isdigit() and 1900 <= int(token) <= 2100:
            if not re.search(r"(?:[$€£¥]|[A-Z]{3})\s*$", text[:match.start()]):
                continue
        return False
    return True


def _money(value: float, currency: str) -> str:
    prefix = "$" if currency == "USD" else currency + " "
    # Exact selected amounts, not rounding that can make unequal operands appear equal.
    return prefix + f"{abs(value):,.4f}".rstrip("0").rstrip(".")


def financing_statement(source: Any) -> str:
    """Describe the two already-qualified operands; never infer cause or annual cadence."""
    if not isinstance(source, dict):
        return ""
    current, prior = source.get("current"), source.get("prior")
    if not isinstance(current, dict) or not isinstance(prior, dict):
        return ""
    # Relational checks belong here even though individual source facts are qualified.
    for key in ("currency", "raw_tag", "entity_identifier", "entity_scheme", "scope"):
        if not current.get(key) or current[key] != prior.get(key):
            return ""
    values = [current.get("value"), prior.get("value")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return ""
    if not all(p.get("period_start") and p.get("period_end") for p in (current, prior)):
        return ""
    if current["period_end"] != source.get("period_of_report") or prior["period_end"] >= current["period_start"]:
        return ""
    concept = current["raw_tag"]
    if "ContinuingOperations" in concept:
        label = "Financing cash flow from continuing operations"
    else:
        label = "Financing cash flow"

    def operand(point: dict) -> str:
        value = point["value"]
        flow = "an inflow of " if value > 0 else "an outflow of " if value < 0 else "zero net flow of "
        return flow + _money(value, point["currency"])

    a, b = values
    if a > 0 and b > 0:
        relation = "Both periods had net inflows."
    elif a < 0 and b < 0:
        relation = "Both periods had net outflows."
    elif a > 0 and b < 0:
        relation = "Net financing changed from an outflow to an inflow."
    elif a < 0 and b > 0:
        relation = "Net financing changed from an inflow to an outflow."
    else:
        relation = ""  # zero is neither an inflow nor an outflow
    return (
        f"{label} for {current['period_start']} to {current['period_end']} was {operand(current)}, "
        f"compared with {operand(prior)} for {prior['period_start']} to {prior['period_end']}. "
        + relation
    ).strip()


def bind_capital_allocation(sections: dict, metrics: Any, source_text: str = "") -> None:
    """Replace this new-generation field, including forged annotations and sibling prose.

    Preview passes no source text, so only the code-owned comparison may appear.
    Final passes the exact primary or recovery context actually provided to the model.
    Legacy persisted sections are never sent through this generation-only function.
    """
    data = sections.get("value_drivers")
    if not isinstance(data, dict):
        return
    offered = data.pop("capital_allocation", None)
    data.pop("capitalAllocation", None)
    data.pop(OWNED_FIELD, None)
    # Program disclosures move into verified passages too: keeping untyped highlights
    # would allow the same unchecked comparison to reappear immediately below this field.
    highlights = data.pop("highlights", [])
    data.pop("analysis", None)
    passages = offered.get("filing_statements", []) if isinstance(offered, dict) else []
    candidates = list(passages) if isinstance(passages, list) else []
    if isinstance(highlights, list):
        candidates.extend(highlights)
    verified: list[str] = []
    for quote in candidates:
        if not isinstance(quote, str) or not 25 <= len(quote) <= 2000:
            continue
        if not source_text or source_text.count(quote) != 1 or not _self_contained_numbers(quote):
            continue
        if quote not in verified:
            verified.append(quote)
    metrics = metrics if isinstance(metrics, dict) else {}
    data[OWNED_FIELD] = {
        "comparison": financing_statement(metrics.get("financing_comparison_source")),
        "filing_statements": verified,
    }
