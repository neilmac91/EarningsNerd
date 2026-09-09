"""Shared numeric coercion helpers."""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional


def coerce_float(value: object) -> Optional[float]:
    """Best-effort float conversion: None for None / blank / non-numeric, else ``float(value)``.

    Consolidates the identical helpers the external integrations (finnhub, fmp, alpha_vantage)
    and the earnings-calendar service each carried privately.
    """
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_DISPLAY_UNITS = {
    "k": 3, "thousand": 3, "m": 6, "mn": 6, "million": 6,
    "b": 9, "bn": 9, "billion": 9, "t": 12, "trillion": 12,
}
_CURRENCY = (
    r"(?:US\$|NT\$|HK\$|S\$|A\$|C\$|R\$|"
    r"USD|EUR|GBP|JPY|CNY|RMB|TWD|DKK|HKD|SGD|AUD|CAD|CHF|"
    r"SEK|NOK|KRW|INR|BRL|MXN|ZAR|NZD|[$€£¥₹₩])"
)
_UNIT = r"(?:thousand|million|billion|trillion|mn|bn|[kmbt]|%|percent|bps|basis\s+points|x|×)"
_DISPLAY_SCALAR = re.compile(
    rf"(?P<sign1>[+−-])?\s*(?:{_CURRENCY})?\s*(?P<sign2>[+−-])?\s*"
    rf"(?P<paren>\()?\s*(?P<number>(?:[0-9]{{1,3}}(?:,[0-9]{{3}})+|[0-9]+)(?:\.[0-9]+)?|\.[0-9]+)"
    rf"\s*(?P<unit>{_UNIT})?\s*(?(paren)\))\s*(?P<outer_unit>{_UNIT})?",
    re.IGNORECASE,
)


def parse_display_number(value: object) -> tuple[Optional[Decimal], bool]:
    """Parse one explicit displayed scalar; return base units and an explicit-percent flag.

    Currency prefixes label values, never scale them or perform FX conversion. Unitless
    multiples and basis points retain their stated magnitude (120bps is 120, not 1.2%).
    Dates, ranges, prose, malformed grouping and unknown decorations remain unknown.
    Display text is owned by the caller and is never rewritten here.
    """
    if isinstance(value, bool):
        return None, False
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            return None, False
        return (number, False) if number.is_finite() else (None, False)
    if not isinstance(value, str):
        return None, False
    text = value.strip()
    outer_negative = text.startswith("(") and text.endswith(")")
    if outer_negative:
        text = text[1:-1].strip()
    match = _DISPLAY_SCALAR.fullmatch(text)
    if not match:
        return None, False
    sign1, sign2 = match.group("sign1", "sign2")
    parenthesized = bool(match.group("paren"))
    unit, outer_unit = match.group("unit", "outer_unit")
    # No contradictory signs, nested accounting signs or competing units.
    if (sign1 and sign2) or ((outer_negative or parenthesized) and (sign1 or sign2)):
        return None, False
    if (outer_negative and parenthesized) or (outer_unit and (unit or not parenthesized)):
        return None, False
    unit = (unit or outer_unit or "").lower()
    number = Decimal(match.group("number").replace(",", ""))
    number *= Decimal(10) ** _DISPLAY_UNITS.get(unit, 0)
    if outer_negative or parenthesized or (sign1 or sign2) in ("-", "−"):
        number = -number
    return number, unit in ("%", "percent")
