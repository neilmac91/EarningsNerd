"""Single source of truth for period-over-period metric deltas.

Every %/ppt change shown on any summary surface — the Financial Highlights table, the What-changed
chips (filing page + dashboard feed), and the CSV/PDF exports — is computed HERE, once, with one
formatting policy:

* ratios / margins render in percentage POINTS: ``+14.4 ppts``
* everything else renders in relative percent: ``+85.2%`` (one decimal, U+2212 for negatives)

This ends the divergence where the same change appeared as +85% (LLM prose) / +85.0% (client-side
table math) / +85.2% (XBRL chips), and where a margin showed as a relative % on one surface and
ppts on another. Numbers come from code, never the model (lesson
``arch-no-precomputed-deltas-in-grounding``): the model writes prose; the arithmetic is here.
"""
from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.utils.numbers import parse_display_number

_MINUS = "−"  # U+2212 MINUS SIGN — byte-identical to the existing chip rendering

# Only an application-built outer envelope carrying this exact integer may authorize a stored
# ``change_display``. The model can write the row's prose ``change`` field; code owns these fields.
EXACT_CONTEXT_KEY = "metric_delta_context_version"
EXACT_CONTEXT_VERSION = 1

# Whole-label mapping only. Qualifiers ("adjusted", "segment", "continuing operations", …) describe
# a potentially different scope and must not borrow a standardized concept on a substring match.
_STRICT_XBRL_KEYS = {
    "net interest income": "net_interest_income",
    "non-interest income": "noninterest_income",
    "noninterest income": "noninterest_income",
    "net investment income": "net_investment_income",
    "premiums earned": "premiums_earned",
    "premium earned": "premiums_earned",
    "premiums earned (net)": "premiums_earned",
    "revenue": "revenue",
    "revenues": "revenue",
    "total revenue": "revenue",
    "total revenues": "revenue",
    "total net sales": "revenue",
    "net sales": "revenue",
    "net income": "net_income",
    "gross profit": "gross_profit",
    "operating income": "operating_income",
    "net margin": "net_margin",
    "gross margin": "gross_margin",
    "operating margin": "operating_margin",
    "diluted eps": "eps_diluted",
    "eps (diluted)": "eps_diluted",
    "diluted earnings per share": "eps_diluted",
    "earnings per share (diluted)": "eps_diluted",
}
_RATIO_KEYS = frozenset({"net_margin", "gross_margin", "operating_margin"})
_CODE_DELTA_FIELDS = ("change_display", "change_direction", "change_tone")
_NUMBER_TOKEN = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.(?P<decimals>[0-9]+))?")
_CURRENCY_CODE = re.compile(
    r"\b(USD|EUR|GBP|JPY|CNY|RMB|TWD|DKK|HKD|SGD|AUD|CAD|CHF|SEK|NOK|KRW|INR|BRL|MXN|ZAR|NZD)\b",
    re.IGNORECASE,
)
_SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "₩": "KRW"}
_DISPLAY_SCALE = {
    "k": Decimal("1e3"), "thousand": Decimal("1e3"),
    "m": Decimal("1e6"), "mn": Decimal("1e6"), "million": Decimal("1e6"),
    "b": Decimal("1e9"), "bn": Decimal("1e9"), "billion": Decimal("1e9"),
    "t": Decimal("1e12"), "tn": Decimal("1e12"), "trillion": Decimal("1e12"),
}


@dataclass(frozen=True)
class MetricDelta:
    """A computed change with one canonical display string. ``is_ppts`` picks the unit."""

    value: Optional[float]      # ppt difference when is_ppts; else the relative-% magnitude
    pct: Optional[float]        # relative-% magnitude for amounts; None for ratios
    direction: str              # 'up' | 'down' | 'flat'
    tone: str                   # 'gain' | 'loss' | 'flat' (design-system data tones)
    is_ppts: bool
    display: Optional[str]      # '+85.2%' / '−20.0%' / '+14.4 ppts'; None when incomputable


def _direction_tone(delta: float) -> tuple[str, str]:
    if delta > 0:
        return "up", "gain"
    if delta < 0:
        return "down", "loss"
    return "flat", "flat"


def compute(current: Optional[float], prior: Optional[float], *, is_ratio: bool) -> MetricDelta:
    """The one delta policy, with one rounding pass from the supplied operands."""
    if current is None or prior is None:
        return MetricDelta(None, None, "flat", "flat", is_ratio, None)

    if is_ratio:
        diff = round(current - prior, 1)
        direction, tone = _direction_tone(diff)
        sign = "+" if diff > 0 else (_MINUS if diff < 0 else "")
        return MetricDelta(
            value=abs(diff), pct=None, direction=direction, tone=tone,
            is_ppts=True, display=f"{sign}{abs(diff):.1f} ppts",
        )

    if prior == 0:
        # prior == 0 (or incomputable): no relative % is meaningful — direction only, no display.
        direction, tone = _direction_tone((current or 0) - (prior or 0))
        return MetricDelta(None, None, direction, tone, False, None)
    # Do not pass through MetricChange.compute: it rounds to two decimals first, so a subsequent
    # one-decimal round turns 6.445% into 6.45% into 6.5%. Format once from the raw operands.
    pct = round(((current - prior) / abs(prior)) * 100, 1)
    direction, tone = _direction_tone(pct)
    sign = "+" if pct > 0 else (_MINUS if pct < 0 else "")
    return MetricDelta(
        value=abs(pct), pct=abs(pct), direction=direction, tone=tone,
        is_ppts=False, display=f"{sign}{abs(pct):.1f}%",
    )


def _parse_number(text: Any) -> tuple[Optional[float], bool]:
    """Adapt the shared displayed-scalar parser to the float-based delta policy."""
    number, is_percent = parse_display_number(text)
    if number is None:
        return None, is_percent
    value = float(number)
    return (value, is_percent) if math.isfinite(value) else (None, is_percent)


def strict_xbrl_metric_key(metric_name: Any) -> Optional[str]:
    """Map a complete metric label to one standardized concept; never infer from a substring."""
    if not isinstance(metric_name, str):
        return None
    return _STRICT_XBRL_KEYS.get(" ".join(metric_name.casefold().split()))


def _as_finite_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _display_resolution(text: Any) -> Optional[Decimal]:
    """Return one unit in the displayed scalar's last stated decimal place."""
    if not isinstance(text, str) or parse_display_number(text)[0] is None:
        return None
    token = _NUMBER_TOKEN.search(text)
    if token is None:
        return None
    decimals = len(token.group("decimals") or "")
    suffix = text[token.end():].casefold().replace(")", "").strip()
    unit_match = re.match(r"(thousand|million|billion|trillion|mn|bn|tn|[kmbt])\b", suffix)
    scale = _DISPLAY_SCALE.get(unit_match.group(1), Decimal(1)) if unit_match else Decimal(1)
    return scale * (Decimal(10) ** -decimals)


def _display_matches_exact(text: Any, exact: Decimal) -> bool:
    displayed, _ = parse_display_number(text)
    resolution = _display_resolution(text)
    if displayed is None or resolution is None:
        return False
    # The displayed scalar represents a rounded bucket. A minute Decimal-relative epsilon admits
    # binary-origin XBRL floats at the bucket boundary without widening the accounting tolerance.
    epsilon = max(abs(exact), Decimal(1)) * Decimal("1e-12")
    return abs(displayed - exact) <= resolution / 2 + epsilon


def _display_currency(text: Any) -> Optional[str]:
    if not isinstance(text, str):
        return None
    code = _CURRENCY_CODE.search(text)
    if code:
        value = code.group(1).upper()
        return "CNY" if value == "RMB" else value
    # Compound dollar symbols must be checked before the plain "$" fallback.
    for prefix, currency in (("A$", "AUD"), ("C$", "CAD"), ("HK$", "HKD"),
                             ("S$", "SGD"), ("NT$", "TWD"), ("R$", "BRL")):
        if prefix in text:
            return currency
    for symbol, currency in _SYMBOL_CURRENCY.items():
        if symbol in text:
            return currency
    return None


def _matching_duration_scopes(current: dict, prior: dict) -> bool:
    """Reject an annual/quarterly/YTD context mix when both facts expose duration metadata."""
    current_start, prior_start = current.get("period_start"), prior.get("period_start")
    if (current_start is None) != (prior_start is None):
        return False
    if current_start is None:
        return True  # Both are instant facts, or older metrics without duration metadata.
    try:
        current_days = (date.fromisoformat(current["period"]) - date.fromisoformat(current_start)).days
        prior_days = (date.fromisoformat(prior["period"]) - date.fromisoformat(prior_start)).days
    except (TypeError, ValueError):
        return False
    # Fiscal years and quarters can differ by a week (52/53-week calendars). That bounded variance
    # still rejects a quarter-vs-YTD or quarter-vs-annual scope substitution.
    return current_days > 0 and prior_days > 0 and abs(current_days - prior_days) <= 8


def _exact_delta_for_row(row: dict, metric: Any, metric_key: str) -> Optional[MetricDelta]:
    """Return a delta only when exact XBRL operands match the row's basis and displayed values."""
    if not isinstance(metric, dict):
        return None
    current = metric.get("current")
    prior = metric.get("prior")
    if not isinstance(current, dict) or not isinstance(prior, dict):
        return None
    current_value = _as_finite_decimal(current.get("value"))
    prior_value = _as_finite_decimal(prior.get("value"))
    current_period = current.get("period")
    prior_period = prior.get("period")
    if (
        current_value is None or prior_value is None
        or not isinstance(current_period, str) or not current_period.strip()
        or not isinstance(prior_period, str) or not prior_period.strip()
        or current_period.strip() == prior_period.strip()
    ):
        return None

    # Reject cross-form, cross-quarter, currency and duration/instant drift. Missing optional metadata
    # stays unknown rather than being fabricated; a conflict is an explicit refusal.
    for field in ("form", "fiscal_period", "currency"):
        left, right = current.get(field), prior.get(field)
        if left is not None and right is not None and left != right:
            return None
    current_start, prior_start = current.get("period_start"), prior.get("period_start")
    if not _matching_duration_scopes(current, prior):
        return None
    if current_start is not None and current_start == prior_start:
        return None
    current_tag, prior_tag = current.get("raw_tag"), prior.get("raw_tag")
    if current_tag and prior_tag and current_tag != prior_tag:
        return None

    current_text = row.get("current_period") or row.get("currentPeriod")
    prior_text = row.get("prior_period") or row.get("priorPeriod")
    _, current_pct = parse_display_number(current_text)
    _, prior_pct = parse_display_number(prior_text)
    is_ratio = metric_key in _RATIO_KEYS
    if current_pct != is_ratio or prior_pct != is_ratio:
        return None
    currency = current.get("currency") or prior.get("currency")
    if isinstance(currency, str):
        for text in (current_text, prior_text):
            displayed_currency = _display_currency(text)
            if displayed_currency is not None and displayed_currency != currency.upper():
                return None
    if not _display_matches_exact(current_text, current_value):
        return None
    if not _display_matches_exact(prior_text, prior_value):
        return None
    return compute(float(current_value), float(prior_value), is_ratio=is_ratio)


def bind_exact_xbrl_deltas(financial_section: Any, xbrl_metrics: Any) -> Any:
    """Scrub model delta fields and bind exact operands only after strict concept/value validation."""
    if not isinstance(financial_section, dict):
        return financial_section
    result = copy.deepcopy(financial_section)
    rows = result.get("table")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in _CODE_DELTA_FIELDS:
            row.pop(field, None)
        metric_key = strict_xbrl_metric_key(row.get("metric"))
        metric = xbrl_metrics.get(metric_key) if metric_key and isinstance(xbrl_metrics, dict) else None
        delta = _exact_delta_for_row(row, metric, metric_key) if metric_key else None
        if delta is not None and delta.display is not None:
            row.update({
                "change_display": delta.display,
                "change_direction": delta.direction,
                "change_tone": delta.tone,
            })
    return result


def delta_for_row(row: dict, *, exact_owned: bool = False) -> Optional[MetricDelta]:
    """Compute a Financial Highlights table row's delta from its displayed current/prior strings.

    A row is a ratio (ppts) only when BOTH values are percentages, and an amount (relative %) only
    when NEITHER is. A mixed row (one "%", one not — e.g. current "74.9%", prior "60.5") is
    inconsistent: computing it as an amount would reproduce the exact relative-%-for-a-margin error
    this service exists to kill, so it returns None and the caller shows no computed delta.
    """
    if not isinstance(row, dict):
        return None
    if exact_owned and isinstance(row.get("change_display"), str):
        display = row["change_display"]
        direction = row.get("change_direction")
        tone = row.get("change_tone")
        if direction in {"up", "down", "flat"} and tone in {"gain", "loss", "flat"}:
            return MetricDelta(None, None, direction, tone, False, display)
    cur, cur_pct = _parse_number(row.get("current_period") or row.get("currentPeriod"))
    prior, prior_pct = _parse_number(row.get("prior_period") or row.get("priorPeriod"))
    if cur is None or prior is None:
        return None
    if cur_pct != prior_pct:
        return None  # mixed units — don't guess; the caller falls back to "no computed delta"
    return compute(cur, prior, is_ratio=cur_pct)


def row_delta_fields(row: dict) -> dict:
    """API fields for a table row: change_display/change_direction/change_tone (empty if incomputable)."""
    d = delta_for_row(row)
    if d is None or d.display is None:
        return {}
    return {"change_display": d.display, "change_direction": d.direction, "change_tone": d.tone}
