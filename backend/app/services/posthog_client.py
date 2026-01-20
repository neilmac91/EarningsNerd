from __future__ import annotations

from typing import Optional

from app.config import settings

try:
    from posthog import Posthog
except Exception:  # pragma: no cover - optional dependency during startup
    Posthog = None  # type: ignore


_client: Optional["Posthog"] = None


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
