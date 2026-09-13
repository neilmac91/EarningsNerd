"""Qualify finite conventional cash claims without classifying arbitrary financial prose."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Callable

from .xbrl_narrative import cash_flow_basis

_AMOUNT = r"(?:\$|[A-Z]{3}\s+)-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:B|M|K| billion| million| thousand)"
_VERB = r"(?:increased to|decreased to|rose to|fell to|was)"
_FCF = r"free cash flow(?: \(OCF less capex\))? " + _VERB
_PAIR = re.compile(
    rf"Operating cash flow {_VERB} (?P<ocf_current>{_AMOUNT}) from (?P<ocf_prior>{_AMOUNT}), "
    rf"and {_FCF} (?P<fcf_current>{_AMOUNT}) from (?P<fcf_prior>{_AMOUNT})\.", re.I,
)
_SINGLE = re.compile(rf"{_FCF} (?P<fcf_current>{_AMOUNT}) from (?P<fcf_prior>{_AMOUNT})\.", re.I)
# Two observed whole mixed sentences. The asset suffix is preserved, never certified.
_MIXED = re.compile(
    rf"Operating cash flow of (?P<ocf_current>{_AMOUNT}) and free cash flow of (?P<fcf_current>{_AMOUNT})"
    rf"(?P<suffix>, while total assets grew to {_AMOUNT} from {_AMOUNT}\.)", re.I,
)
_MIXED_GROWTH = re.compile(
    rf"Operating cash flow of (?P<ocf_current>{_AMOUNT}) \((?P<ocf_growth>[+-]?\d+(?:\.\d+)?)% YoY\) "
    rf"and free cash flow of (?P<fcf_current>{_AMOUNT})"
    rf"(?P<suffix>, while total assets grew [+-]?\d+(?:\.\d+)?% to {_AMOUNT}\.)", re.I,
)
_SCALES = {"b": 10**9, "m": 10**6, "k": 10**3,
           "billion": 10**9, "million": 10**6, "thousand": 10**3}


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def _selected(metrics: dict) -> dict | None:
    """Use actual selected components: derived FCF itself has no currency/start metadata."""
    currency = metrics.get("reporting_currency")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        return None
    selected = {"currency": currency}
    for period in ("current", "prior"):
        points = []
        for key in ("operating_cash_flow", "capital_expenditures", "free_cash_flow"):
            entry = metrics.get(key)
            point = entry.get(period) if isinstance(entry, dict) else None
            if not isinstance(point, dict) or _number(point.get("value")) is None:
                return None
            points.append(point)
        ocf, capex, fcf = points
        if any(p.get("currency") != currency for p in (ocf, capex)):
            return None
        if ocf.get("period") != capex.get("period") or ocf.get("period") != fcf.get("period"):
            return None
        if not ocf.get("period_start") or ocf["period_start"] != capex.get("period_start"):
            return None
        try:
            start, end = date.fromisoformat(ocf["period_start"]), date.fromisoformat(ocf["period"])
        except (TypeError, ValueError):
            return None
        if start >= end or _number(ocf["value"]) - abs(_number(capex["value"])) != _number(fcf["value"]):
            return None
        selected[period] = {"start": start, "end": end, "ocf": ocf["value"], "fcf": fcf["value"]}
    if selected["prior"]["end"] >= selected["current"]["start"]:
        return None
    return selected


def _matches(token: str, value: float, currency: str) -> bool:
    match = re.fullmatch(r"(\$|[A-Z]{3}\s+)(-?[\d,.]+)\s*(B|M|K|billion|million|thousand)", token, re.I)
    if match is None or ("USD" if match[1] == "$" else match[1].strip().upper()) != currency:
        return False
    raw = match[2].replace(",", "")
    scale = Decimal(_SCALES[match[3].lower()])
    tolerance = Decimal("0.5") * Decimal(10) ** -len(raw.partition(".")[2]) * scale
    return abs(Decimal(raw) * scale - _number(value)) <= tolerance


def _matches_annual_growth(token: str, selected: dict) -> bool:
    current, prior = selected["current"], selected["prior"]
    # YoY needs the operands' actual comparable annual coverage, not a form/FY label.
    if any(not 320 <= (p["end"] - p["start"]).days <= 390 for p in (current, prior)):
        return False
    for key in ("start", "end"):
        a, b = current[key], prior[key]
        if a.year != b.year + 1 or (a.month, a.day) != (b.month, b.day):
            return False
    denominator = _number(prior["ocf"])
    if denominator <= 0:
        return False
    growth = (_number(current["ocf"]) - denominator) / denominator * 100
    tolerance = Decimal("0.5") * Decimal(10) ** -len(token.partition(".")[2])
    return abs(Decimal(token) - growth) <= tolerance


def qualify_cash_lead(sections: dict, metrics: dict, format_money: Callable[[float], str]) -> None:
    """Re-author only wholly recognized cash relationships; leave all other text untouched."""
    selected = _selected(metrics)
    if selected is None:
        return

    def replace(text: Any) -> Any:
        if not isinstance(text, str):
            return text
        match = (_PAIR.fullmatch(text) or _SINGLE.fullmatch(text)
                 or _MIXED.fullmatch(text) or _MIXED_GROWTH.fullmatch(text))
        if match is None:
            return text
        groups = match.groupdict()
        if groups.get("ocf_growth") and not _matches_annual_growth(groups["ocf_growth"], selected):
            return text
        for key, token in groups.items():
            if key in ("suffix", "ocf_growth"):
                continue
            metric, period = key.split("_")
            if not _matches(token, selected[period][metric], selected["currency"]):
                return text
        current, prior = selected["current"], selected["prior"]

        def comparison(metric: str) -> str:
            return (f"{format_money(current[metric])} for {current['start']} to {current['end']}, "
                    f"compared with {format_money(prior[metric])} for {prior['start']} to {prior['end']}")

        prefix = "Operating cash flow was " + comparison("ocf") + ". " if "ocf_current" in match.groupdict() else ""
        owned = (prefix + "Conventional free cash flow was " + comparison("fcf")
                 + " (" + cash_flow_basis("free_cash_flow") + ")")
        # Keep the exact model-authored asset clause; its figures are outside this certification.
        return owned + groups.get("suffix", ".")

    lead = sections.get("the_print")
    if isinstance(lead, str):
        sections["the_print"] = replace(lead)
    elif isinstance(lead, dict):
        for key in ("headline", "what_changed", "whatChanged"):
            if key in lead:
                lead[key] = replace(lead[key])
        for key in ("key_takeaways", "keyTakeaways"):
            if isinstance(lead.get(key), list):
                lead[key] = [replace(text) for text in lead[key]]
            elif isinstance(lead.get(key), str):
                lead[key] = replace(lead[key])
