"""One bounded issuer FCF reconciliation shape from the supplied filing context.

This is an attributed source table, never a bridge to selected XBRL/derived FCF.
Unsupported definitions, denominations and table layouts abstain.
"""
from __future__ import annotations

import re

from .capital_passages import _LAYOUT
from .recovery_context import recovery_blocks

CONTEXT_KEY = "issuer_cash_disclosure_context_version"
CONTEXT_VERSION = 1
OWNED_FIELD = "issuer_cash_disclosure"
SOURCE_KEY = "_issuer_cash_disclosure_grounding"

_OCF = "Net cash provided by (used in) operating activities"
_PURCHASES = "Purchases of property and equipment, net of proceeds from sales and incentives"
_DEFINITION = f"Free cash flow is cash flow from operations reduced by “{_PURCHASES}.”"
_INT = r"(?:0|[1-9]\d{0,2}(?:,\d{3}){1,5}|[1-9]\d{0,17})"
_YEAR = r"(?:19|20)\d{2}"
_INTRO = re.compile(
    rf".+{re.escape(_DEFINITION)} The following is a reconciliation of free cash flow to the most "
    rf"comparable GAAP cash flow measure, “{re.escape(_OCF)},” for ({_YEAR}) and ({_YEAR}) \(in millions\):"
)
_LIMIT_START = ("Free cash flow has limitations as it omits certain components of the overall cash flow "
                "statement and does not represent the residual cash flow available for discretionary expenditures.")
_LIMIT_END = ("Therefore, we believe it is important to view free cash flow only as a complement "
              "to our entire consolidated statements of cash flows.")
_CURRENCY = "Our financial reporting currency is the U.S. Dollar"


def _row(line: str, label: str, *, deduction: bool = False) -> list[str] | None:
    cell = rf"\(({_INT})\)" if deduction else rf"\$({_INT})"
    match = re.fullmatch(re.escape(label) + cell + r"\s*" + cell, line)
    return list(match.groups()) if match else None


def _disclosure(source: str) -> dict | None:
    if len(source) > 320_000 or sum(line.strip() == "Free Cash Flow" for line in source.splitlines()) != 1:
        return None
    candidates = []
    for block in recovery_blocks(source, _LAYOUT):
        if not block.families or not set(block.families) <= {"financials", "mda"}:
            continue
        # Preserve physical line boundaries; only space characters within a line normalize.
        lines = [line.strip() for line in block.text.splitlines() if line.strip()]
        normalized = [re.sub(r"[^\S\r\n]+", " ", line) for line in lines]
        currencies = [i for i, line in enumerate(normalized) if "financial reporting currency is" in line]
        if (len(currencies) != 1 or not 0 < currencies[0] < len(lines) - 1
                or not normalized[currencies[0]].startswith(_CURRENCY + " and ")
                or not normalized[currencies[0]].endswith(".")
                or len(lines[currencies[0]]) > 2000 or source.count(lines[currencies[0]]) != 1):
            continue
        for i, line in enumerate(normalized):
            if line != "Free Cash Flow" or i == 0 or i + 7 >= len(lines):
                continue
            intro = _INTRO.fullmatch(normalized[i + 1])
            if not intro or len(lines[i + 1]) > 2000 or source.count(lines[i + 1]) != 1:
                continue
            years = list(intro.groups())
            if int(years[1]) != int(years[0]) + 1 or normalized[i + 2] != "Year Ended December 31,":
                continue
            if re.sub(r"\s", "", normalized[i + 3]) != "".join(years):
                continue
            ocf = _row(normalized[i + 4], _OCF)
            purchases = _row(normalized[i + 5], _PURCHASES, deduction=True)
            fcf = _row(normalized[i + 6], "Free cash flow")
            if not all((ocf, purchases, fcf)):
                continue
            if any(int(a.replace(",", "")) - int(b.replace(",", "")) != int(c.replace(",", ""))
                   for a, b, c in zip(ocf, purchases, fcf)):
                continue
            end = i + 7
            # Some filings include the other GAAP cash-flow totals after the reconciliation.
            # Recognize exactly the pair before the limitation, never search past arbitrary rows.
            if end < len(lines) and normalized[end].startswith("Net cash provided by (used in) investing activities"):
                for activity in ("investing", "financing"):
                    label = f"Net cash provided by (used in) {activity} activities"
                    cell = rf"\$(?:{_INT}|\({_INT}\))"
                    if end >= len(lines) or not re.fullmatch(re.escape(label) + cell + r"\s*" + cell, normalized[end]):
                        break
                    end += 1
                if end != i + 9:
                    continue
            if end >= len(lines) - 1:
                continue
            limitation = normalized[end]
            if (not limitation.startswith(_LIMIT_START) or not limitation.endswith(_LIMIT_END)
                    or len(lines[end]) > 2000 or source.count(lines[end]) != 1):
                continue
            candidates.append({
                "definition": lines[i + 1], "limitations": lines[end],
                "currency_statement": lines[currencies[0]],
                "headers": ["USD millions — year ended December 31", *years],
                "rows": [[_OCF, *ocf], [_PURCHASES, *(f"({v})" for v in purchases)],
                         ["Free cash flow", *fcf]],
            })
    return candidates[0] if len(candidates) == 1 else None


def bind_issuer_cash_disclosure(sections: dict, source: str = "") -> bool:
    """Replace model offers; previews have no source and defer this disclosure entirely."""
    data = sections.get("earnings_quality")
    if not isinstance(data, dict):
        return False
    data.pop(OWNED_FIELD, None)
    data.pop("issuerCashDisclosure", None)
    disclosure = _disclosure(source) if source else None
    if disclosure is None:
        return False
    data[OWNED_FIELD] = disclosure
    return True
