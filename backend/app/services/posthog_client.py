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
    client.capture(distinct_id, event, properties or {})


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
