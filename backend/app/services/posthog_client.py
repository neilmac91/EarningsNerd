from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

try:
    from posthog import Posthog
except Exception:  # pragma: no cover - optional dependency during startup
    Posthog = None  # type: ignore


logger = logging.getLogger(__name__)

_client: Optional["Posthog"] = None

# Activation funnel events (anonymous visitor -> first successful summary).
# Server-side generation outcomes are captured here (single source of truth for
# duration/result/quality); the frontend captures summary_viewed and forwards its
# PostHog distinct_id + entry_point so funnel steps join on one person.
EVENT_GENERATION_STARTED = "generation_started"
EVENT_GENERATION_SUCCEEDED = "generation_succeeded"
EVENT_GENERATION_FAILED = "generation_failed"
EVENT_GENERATION_TIMED_OUT = "generation_timed_out"
EVENT_SUMMARY_VIEWED = "summary_viewed"
# Fired when a free user is blocked by the monthly summary limit — the single best
# demand/pricing signal for future monetization (how often free users hit the wall).
EVENT_PAYWALL_HIT = "paywall_hit"
# Per-answer Copilot inference cost (tokens + estimated USD) — the unit-economics signal that gates
# whether a free-taste of Copilot (roadmap 2.2) is affordable. Emitted server-side, keyed on the
# same str(user.id) the frontend identifies on, so it joins the person's journey.
EVENT_COPILOT_INFERENCE = "copilot_inference_cost"

# Closed-beta activation funnel. All emitted server-side keyed on str(user.id) — which is the same
# canonical id the frontend identifies on (String(user.id)) — so server + client events stitch onto
# one person without a separate alias step. The funnel's "activated" step reuses the existing
# generation_succeeded event (PostHog funnels dedupe to first-per-user), so there is deliberately no
# separate "first_summary_generated" event — a Summary belongs to a Filing (shared), not a user, so
# "first per user" can't be computed cheaply in the SSE hot path.
EVENT_INVITE_REDEEMED = "invite_redeemed"
EVENT_SIGNUP_COMPLETED = "signup_completed"
EVENT_TRIAL_STARTED = "trial_started"


def get_posthog_client() -> Optional["Posthog"]:
    global _client
    if _client is not None:
        return _client
    if not settings.POSTHOG_API_KEY or Posthog is None:
        return None
    _client = Posthog(settings.POSTHOG_API_KEY, host=settings.POSTHOG_HOST)
    return _client


def capture_event(distinct_id: str, event: str, properties: Optional[dict] = None) -> None:
    client = get_posthog_client()
    if not client:
        return
    # PostHog's Python SDK uses the event-first signature
    # ``capture(event, *, distinct_id=..., properties=...)`` (one positional, rest
    # keyword-only). The legacy positional ``capture(distinct_id, event, properties)``
    # raises ``TypeError: too many positional arguments``, which the wrappers below
    # silently swallow — dropping every server-side event. Call it the modern way.
    client.capture(event, distinct_id=distinct_id, properties=properties or {})


def capture_funnel_event(
    distinct_id: str,
    event: str,
    *,
    duration_ms: Optional[int] = None,
    result_type: Optional[str] = None,
    quality_verdict: Optional[str] = None,
    entry_point: Optional[str] = None,
    **extra: object,
) -> None:
    """Capture an activation-funnel event. Never raises — telemetry must not
    break or slow summary generation."""
    properties: dict = {
        "duration_ms": duration_ms,
        "result_type": result_type,
        "quality_verdict": quality_verdict,
        "entry_point": entry_point,
        **extra,
    }
    properties = {k: v for k, v in properties.items() if v is not None}
    try:
        capture_event(distinct_id, event, properties)
    except Exception as exc:  # pragma: no cover - defensive: PostHog SDK/network issues
        logger.warning(f"PostHog capture failed for {event}: {exc}")


def capture_copilot_inference(
    distinct_id: str,
    *,
    model: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cache_hit_tokens: Optional[int] = None,
    cache_miss_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    filing_id: Optional[int] = None,
    ticker: Optional[str] = None,
    kind: Optional[str] = None,
    grounded: Optional[int] = None,
    is_free_taste: Optional[bool] = None,
) -> None:
    """Capture a Copilot answer's token usage + estimated inference cost. Never raises —
    telemetry must not break or slow the answer stream. ``is_free_taste`` tags answers served on a
    Free user's lifetime taste (roadmap 2.2) so that spend can be isolated from Pro spend."""
    properties: dict = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cost_usd": cost_usd,
        "filing_id": filing_id,
        "ticker": ticker,
        "kind": kind,
        "grounded": grounded,
        "is_free_taste": is_free_taste,
    }
    properties = {k: v for k, v in properties.items() if v is not None}
    try:
        capture_event(distinct_id, EVENT_COPILOT_INFERENCE, properties)
    except Exception as exc:  # pragma: no cover - defensive: PostHog SDK/network issues
        logger.warning(f"PostHog capture failed for {EVENT_COPILOT_INFERENCE}: {exc}")
