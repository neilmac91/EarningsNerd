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
# Every code a money label can carry. ``money_prefix_for`` labels a figure with the filer's reporting
# currency, which comes from its XBRL units, so any ISO 4217 currency can appear: List One as of
# February 2026 (pycountry 26.2.16), without the fund codes and the X-codes that name no national
# currency (precious metals, bond-market units, the SDR, units of account, XTS and XXX). A code ISO
# has withdrawn, or none at all ("XYZ 5M"), stays unknown.
ISO_4217_CURRENCIES = frozenset("""
    AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF
    CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD
    HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL
    LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP
    PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT
    TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XCD XCG XOF XPF YER ZAR ZMW ZWG
""".split())
# These read in any case, as they did before the full list. The rest read in capitals only, as
# ``money_prefix_for`` writes them, so a word such as "all", "top" or "try" never reads as a currency.
_ANY_CASE_CODES = "USD|EUR|GBP|JPY|CNY|RMB|TWD|DKK|HKD|SGD|AUD|CAD|CHF|SEK|NOK|KRW|INR|BRL|MXN|ZAR|NZD"
CURRENCY_CODE = rf"(?:{_ANY_CASE_CODES}|(?-i:{'|'.join(sorted(ISO_4217_CURRENCIES))}))"
_CURRENCY = rf"(?:US\$|NT\$|HK\$|S\$|A\$|C\$|R\$|{CURRENCY_CODE}|[$€£¥₹₩])"
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


def money_prefix_for(reporting_currency: object) -> str:
    """The label for a money figure in the filer's reporting currency: a bare "$" for USD (or no
    currency, the backend's domestic default), else the ISO code and a space ("EUR 30.6B", "CNY 941.2B").

    Standardized XBRL values are in the reporting currency, and a CNY figure shown as "$" reads ~7x
    too large. The P&L table cells of a summary are labelled by this rule: the primary filler in
    ``ai/markdown_render.py``, the AI-timeout fallback in ``fallback_summary.py``, and the
    prior-period backfill both paths run before storing (``schemas/summary.py``
    ``attach_normalized_facts``). ``ai/bank_guards.py`` and ``ai/financing_comparison.py`` still
    carry their own copies of the same expression.
    """
    return "$" if str(reporting_currency or "USD").upper() == "USD" else f"{str(reporting_currency).upper()} "
