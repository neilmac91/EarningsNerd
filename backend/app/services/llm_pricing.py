"""Best-effort LLM inference-cost estimation for telemetry (roadmap 2.1).

Turns token counts into an estimated USD cost using env-configurable per-1M-token rates. DeepSeek
prices INPUT tokens far cheaper on a context-cache HIT than a MISS (~120x), so when the response
reports the hit/miss split we price each bucket separately; otherwise we conservatively treat all
input as a cache miss. This is telemetry only — it must never raise on the request path.
"""

from __future__ import annotations

from app.config import settings


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
