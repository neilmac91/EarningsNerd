"""Shared numeric coercion helpers."""
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
