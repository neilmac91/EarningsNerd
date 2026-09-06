from __future__ import annotations

import time
from collections import OrderedDict, deque
from threading import Lock
from typing import Deque, Optional

from fastapi import HTTPException, Request, status

from app.config import settings


class RateLimiter:
    """Per-process sliding windows with bounded key cardinality and lazy idle cleanup."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = settings.RATE_LIMITER_MAX_KEYS
        self._hits: OrderedDict[str, Deque[float]] = OrderedDict()
        self._lock = Lock()

    def _remove_expired_keys(self, cutoff: float) -> None:
        # Last accepted hits are ordered: only the expired prefix needs examining. Each key is
        # removed at most once per insertion, and no auxiliary state survives _hits.clear().
        while self._hits:
            key, window = next(iter(self._hits.items()))
            if window and window[-1] >= cutoff:
                break
            del self._hits[key]

    def allow(self, key: str) -> bool:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._remove_expired_keys(cutoff)
            window = self._hits.get(key)
            if window is None:
                if len(self._hits) >= self.max_keys:
                    return False  # Never evict an active bucket and reset its allowance.
                window = deque()
                self._hits[key] = window
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(now)
            self._hits.move_to_end(key)
            return True

    def is_exhausted(self, key: str) -> bool:
        """True if ``key`` is currently at or over its limit.

        A read-only peek: unlike :meth:`allow` it does not record a hit, so callers can gate a
        request on prior activity (e.g. failed logins) without charging the current attempt.
        """
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._remove_expired_keys(cutoff)
            window = self._hits.get(key)
            if not window:
                return False
            while window and window[0] < cutoff:
                window.popleft()
            return len(window) >= self.limit

    def retry_after(self, key: str) -> Optional[int]:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._remove_expired_keys(cutoff)
            window = self._hits.get(key)
            if not window:
                return None
            while window and window[0] < cutoff:
                window.popleft()
            if not window:
                return None
            return max(1, int(self.window_seconds - (now - window[0])))


def get_client_ip(request: Request) -> str:
    """Best-effort, spoofing-resistant client IP for rate-limit keying and IP hashing.

    ``X-Forwarded-For`` is a client-controllable header — only the entries appended by our own
    proxies (the right-most ones) are trustworthy. ``settings.TRUSTED_PROXY_HOPS`` declares how many
    proxy hops sit in front of the app, so we take the Nth entry from the right (the real client,
    since the closest proxy appends it last). When the hop count is ``<= 0`` we DO NOT trust the
    header at all and fall back to the direct socket peer, so a forged ``X-Forwarded-For`` can never
    reset a per-IP limit or poison an IP hash. The left-most (fully client-supplied) entry is never
    used.
    """
    hops = settings.TRUSTED_PROXY_HOPS
    if hops and hops > 0:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
            if parts:
                # Nth-from-right; clamp so a short/forged chain can't index past the left-most hop.
                return parts[-min(hops, len(parts))]
    if request.client:
        return request.client.host
    return "unknown"


# Back-compat alias — existing callers import the underscored name.
_get_client_ip = get_client_ip


def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter,
    key_suffix: str,
    *,
    error_detail: str,
    include_client_ip: bool = True,
) -> None:
    # Email-scoped limits (password reset, resend-verification) pass include_client_ip=False so the
    # bucket is keyed on the email alone. Prefixing the client IP would let an attacker with an IP
    # pool multiply the per-email cap and bomb a victim's inbox.
    key = f"{_get_client_ip(request)}:{key_suffix}" if include_client_ip else key_suffix
    if limiter.allow(key):
        return
    retry_after = limiter.retry_after(key)
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=error_detail,
        headers=headers,
    )
