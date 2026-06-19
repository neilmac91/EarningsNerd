"""Filing Pulse — a calm, sourced read on attention around a filing.

Roadmap A3 (`docs/competitive-strategy-roadmap-2026.md`): take the multi-signal buzz components the
pipeline already computes (recency, reader interest, filing cadence, earnings proximity, news volume,
sentiment) and present them as a calm, transparent, source-attributed gauge — deliberately **not** a
1-100 hype score or red/green "casino" meter (the Stocktwits failure mode we reject).

Pure and deterministic: it transforms an already-computed ``buzz_components`` dict + score into a
labelled, normalized view. No network calls, no new data sources.
"""

from __future__ import annotations

from typing import Any, Optional

# Human-facing label + plain-language description + the signal source, per buzz component key emitted
# by ``hot_filings.HotFilingRecord.buzz_components``.
_COMPONENT_META: dict[str, tuple[str, str, str]] = {
    "recency": ("Recently filed", "How recently this filing was submitted", "EDGAR"),
    "search_activity": ("Reader interest", "EarningsNerd searches for this company", "EarningsNerd"),
    "filing_velocity": ("Filing cadence", "How frequently this company has filed lately", "EDGAR"),
    "filing_type_bonus": ("Filing type", "Weighting for higher-signal filing types", "EDGAR"),
    "earnings_calendar": ("Earnings proximity", "Closeness to a scheduled earnings date", "FMP"),
    "news_buzz": ("News volume", "Recent news-article volume", "Finnhub"),
    "news_headlines": ("Headline activity", "Recent headline count", "Finnhub"),
    "news_sentiment": ("News sentiment", "Bullish/bearish tilt vs. sector", "Finnhub"),
}

# Calm tiers keyed off the composite score. Intentionally qualitative words, not a precise number —
# the score is a relative attention signal, not a rating. Ordered high → low.
_PULSE_TIERS: list[tuple[float, str]] = [
    (12.0, "Elevated"),
    (7.0, "Active"),
    (3.0, "On the radar"),
    (0.0, "Quiet"),
]


def pulse_tier(score: float) -> str:
    """Map a composite buzz score to a calm qualitative tier."""
    for threshold, label in _PULSE_TIERS:
        if score >= threshold:
            return label
    return "Quiet"


def compose_pulse(
    buzz_components: Optional[dict], buzz_score: Optional[float]
) -> dict[str, Any]:
    """Compose a calm, source-attributed Filing Pulse from raw buzz components.

    Returns ``{score, tier, has_signal, components}`` where ``components`` lists only the active
    (non-zero) signals, each with a human label, description, source, value, and share-of-total —
    sorted by contribution. Tolerant of missing/empty/malformed input.
    """
    comps = buzz_components if isinstance(buzz_components, dict) else {}
    score = float(buzz_score) if isinstance(buzz_score, (int, float)) else 0.0

    active: list[dict[str, Any]] = []
    for key, (label, description, source) in _COMPONENT_META.items():
        value = comps.get(key)
        if isinstance(value, (int, float)) and value > 0:
            active.append(
                {
                    "key": key,
                    "label": label,
                    "description": description,
                    "source": source,
                    "value": round(float(value), 2),
                }
            )

    total = sum(c["value"] for c in active)
    for c in active:
        c["share"] = round(c["value"] / total * 100) if total else 0
    active.sort(key=lambda c: c["value"], reverse=True)

    return {
        "score": round(score, 2),
        "tier": pulse_tier(score),
        "has_signal": bool(active),
        "components": active,
    }
