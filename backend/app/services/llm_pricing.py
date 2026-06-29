"""Best-effort LLM inference-cost estimation for telemetry (roadmap 2.1).

Turns token counts into an estimated USD cost using env-configurable per-1M-token rates
(``AI_INPUT_PRICE_PER_1M_TOKENS`` / ``AI_OUTPUT_PRICE_PER_1M_TOKENS``). The rates are placeholders
for DeepSeek-class pricing — set them to the configured provider's actual rates so the cost metric
reflects real spend. This is telemetry only: it must never raise on the request path.
"""

from __future__ import annotations

from app.config import settings


def estimate_inference_cost_usd(prompt_tokens: int | None, completion_tokens: int | None) -> float:
    """Estimate USD cost from token counts and the configured per-1M-token rates.

    Returns 0.0 when token counts are missing/zero (so a usage-less response yields a 0 cost rather
    than an error). Rounded to 6 dp (sub-cent precision for per-question costs).
    """
    pt = prompt_tokens or 0
    ct = completion_tokens or 0
    cost = (
        pt * settings.AI_INPUT_PRICE_PER_1M_TOKENS
        + ct * settings.AI_OUTPUT_PRICE_PER_1M_TOKENS
    ) / 1_000_000
    return round(cost, 6)
