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

import math
from dataclasses import dataclass
from typing import Any, Optional

from app.services.edgar.models import MetricChange
from app.utils.numbers import parse_display_number

_MINUS = "−"  # U+2212 MINUS SIGN — byte-identical to the existing chip rendering


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
    """The one delta policy. ``is_ratio`` → ppt difference; otherwise relative % via MetricChange."""
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

    change = MetricChange.compute(current, prior)
    if change.percentage is None:
        # prior == 0 (or incomputable): no relative % is meaningful — direction only, no display.
        direction, tone = _direction_tone((current or 0) - (prior or 0))
        return MetricDelta(None, None, direction, tone, False, None)
    pct = round(change.percentage, 1)
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


def delta_for_row(row: dict) -> Optional[MetricDelta]:
    """Compute a Financial Highlights table row's delta from its displayed current/prior strings.

    A row is a ratio (ppts) only when BOTH values are percentages, and an amount (relative %) only
    when NEITHER is. A mixed row (one "%", one not — e.g. current "74.9%", prior "60.5") is
    inconsistent: computing it as an amount would reproduce the exact relative-%-for-a-margin error
    this service exists to kill, so it returns None and the caller shows no computed delta.
    """
    if not isinstance(row, dict):
        return None
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
