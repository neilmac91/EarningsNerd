from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(now)
            return True

    def retry_after(self, key: str) -> Optional[int]:
        now = time.monotonic()
        with self._lock:
            window = self._hits.get(key)
            if not window:
                return None
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()
            if not window:
                return None
            return max(1, int(self.window_seconds - (now - window[0])))


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter,
    key_suffix: str,
    *,
    error_detail: str,
) -> None:
    client_ip = _get_client_ip(request)
    key = f"{client_ip}:{key_suffix}"
    if limiter.allow(key):
        return
    retry_after = limiter.retry_after(key)
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=error_detail,
        headers=headers,
    )
