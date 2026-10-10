"""Deterministic number and comparison formatting."""
from __future__ import annotations

from decimal import Decimal


# --- dataset assembly --------------------------------------------------------------------------


# Sentinel for `_growth`: a comparison was attempted but crossing zero makes a percentage
# meaningless (finance convention "n/m" — not meaningful), e.g. investing cash flow swinging from
# +$503M to -$71.9B renders "-14,399.2%" under plain division. Distinct from None (no prior at
# all), so the UI/prompt can say "n/m" instead of rendering nothing.
NOT_MEANINGFUL = "nm"


def _format_value(value: float, unit: str, percent: bool) -> str:
    if percent:
        return f"{value:.1f}%"
    if unit == "pure":
        return f"{value:.2f}x"
    if unit.endswith("/shares"):
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def _pct_str(value: float) -> str:
    return f"{value * 100:+.1f}%"


def _fmt_growth(value: float | str, is_percent: bool) -> str:
    """Render a YoY/QoQ delta for the prompt: NOT_MEANINGFUL as "n/m"; a percent-unit series'
    delta (already a percentage-POINT number, no ×100) as "+X.Xpp"; everything else as the usual
    signed relative percentage."""
    if value == NOT_MEANINGFUL:
        return "n/m"
    if is_percent:
        return f"{value:+.1f}pp"
    return _pct_str(value)


def _ratio_threshold_value(value: float) -> str:
    """Expose enough ratio precision to preserve its exact relation to 1.00x."""
    decimals = 4
    while value != 1.0 and decimals < 16 and f"{value:.{decimals}f}" == f"{1.0:.{decimals}f}":
        decimals += 1
    return f"{value:.{decimals}f}x"


def _ordered_percentage_values(
    values: list[float], *, already_percent: bool = False, signed: bool = True
) -> tuple[list[str], bool]:
    """Render an ordered percentage sequence without hiding strict changes through rounding."""
    scale = Decimal(1) if already_percent else Decimal(100)
    scaled = [Decimal(str(value)) * scale for value in values]
    sign = "+" if signed else ""
    for decimals in range(1, 5):
        rendered = [f"{value:{sign}.{decimals}f}%" for value in scaled]
        if all(first != second for first, second in zip(rendered, rendered[1:])):
            return rendered, True
    rendered = [f"{value:{sign}.4f}%" for value in scaled]
    return rendered, False
