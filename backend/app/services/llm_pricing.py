"""Best-effort LLM inference-cost estimation for telemetry (roadmap 2.1).

Turns token counts into an estimated USD cost using env-configurable per-1M-token rates. DeepSeek
prices INPUT tokens far cheaper on a context-cache HIT than a MISS (~120x), so when the response
reports the hit/miss split we price each bucket separately; otherwise we conservatively treat all
input as a cache miss. This is telemetry only — it must never raise on the request path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from app.config import settings

# Off-peak USD per 1M tokens as (cache-hit input, cache-miss input, output), keyed by model id
# prefix. DeepSeek bills 2x during UTC 01:00-04:00 and 06:00-10:00 Monday-Friday (ADR-0008); the
# multiplier is Settings-driven so a tariff change is config, not code. Unknown models fall back to
# the three Settings constants (which describe the configured default model).
_MODEL_PRICES_PER_1M: dict[str, tuple[float, float, float]] = {
    "deepseek-flash": (0.003, 0.15, 0.60),
    "deepseek-v4-flash": (0.003, 0.15, 0.60),   # retired alias, billed at Flash rates
    "deepseek-v4-pro": (0.003, 0.15, 0.60),     # retired 2026-09-14: routed to V4.1 Flash, billed at Flash rates
}
_PEAK_WINDOWS_UTC = ((1, 4), (6, 10))  # [start, end) hours, Monday-Friday


def is_peak_hour(at: Optional[datetime] = None) -> bool:
    """DeepSeek peak tariff window: 01:00-04:00 and 06:00-10:00 UTC, Monday to Friday."""
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc)
    if now.weekday() >= 5:
        return False
    return any(start <= now.hour < end for start, end in _PEAK_WINDOWS_UTC)


def prices_for_model(model: Optional[str]) -> tuple[float, float, float]:
    """(hit, miss, output) USD per 1M for ``model``; the Settings constants when unknown."""
    name = (model or "").lower()
    for prefix, prices in _MODEL_PRICES_PER_1M.items():
        if name == prefix or name.startswith(prefix + "-"):
            return prices
    return (
        settings.AI_INPUT_CACHE_HIT_PRICE_PER_1M,
        settings.AI_INPUT_CACHE_MISS_PRICE_PER_1M,
        settings.AI_OUTPUT_PRICE_PER_1M_TOKENS,
    )


def estimate_call_cost_usd(model: Optional[str], usage: Mapping[str, Any], *, at: Optional[datetime] = None) -> dict:
    """Peak-aware, per-model estimate for one provider call from a normalized ``ai_metrics`` usage
    row. Returns ``{"cost_usd": float | None, "peak": bool}``; ``None`` when no token count is known
    (never a claimed zero). Reasoning tokens are part of ``completion_tokens`` and priced as output."""
    peak = is_peak_hour(at)
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    hit, miss = usage.get("cache_hit_tokens"), usage.get("cache_miss_tokens")
    if prompt is None and completion is None and hit is None and miss is None:
        return {"cost_usd": None, "peak": peak}
    hit_price, miss_price, out_price = prices_for_model(model)
    multiplier = settings.AI_PEAK_PRICE_MULTIPLIER if peak else 1.0
    if hit is None and miss is None:
        miss = prompt or 0
        hit = 0
    cost = ((hit or 0) * hit_price + (miss or 0) * miss_price + (completion or 0) * out_price) * multiplier / 1_000_000
    return {"cost_usd": round(cost, 6), "peak": peak}


def estimate_inference_cost_usd(
    prompt_tokens: int | None,
    completion_tokens: int | None,
    *,
    cache_hit_tokens: int | None = None,
    cache_miss_tokens: int | None = None,
) -> float:
    """Estimate USD cost from token counts and the configured per-1M-token rates.

    When ``cache_hit_tokens`` / ``cache_miss_tokens`` are provided (DeepSeek reports them), input is
    priced per bucket. When the split is absent, all ``prompt_tokens`` are priced at the dearer
    cache-miss rate (conservative). Returns 0.0 when there are no tokens. Rounded to 6 dp.
    """
    completion = completion_tokens or 0
    hit = cache_hit_tokens or 0
    miss = cache_miss_tokens or 0
    if hit == 0 and miss == 0:
        # Split not reported → price all input at the (dearer) cache-miss rate.
        miss = prompt_tokens or 0
    cost = (
        hit * settings.AI_INPUT_CACHE_HIT_PRICE_PER_1M
        + miss * settings.AI_INPUT_CACHE_MISS_PRICE_PER_1M
        + completion * settings.AI_OUTPUT_PRICE_PER_1M_TOKENS
    ) / 1_000_000
    return round(cost, 6)
