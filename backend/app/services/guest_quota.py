"""Per-IP daily summary quota for anonymous (guest) users (roadmap S5).

Keeps free, no-login activation sustainable by capping guest generations per IP per day,
while NEVER gating the first summary (a brand-new IP is always under the cap). Backed by an
atomic Redis INCR so it works across instances; fails OPEN if Redis is unavailable — infra
must never block a first-time visitor's first summary.
"""
from __future__ import annotations

import datetime
import logging
from typing import Tuple

from app.services.redis_service import get_redis_client

logger = logging.getLogger(__name__)

_SECONDS_PER_DAY = 86400


async def check_and_increment_guest_quota(ip: str, limit: int) -> Tuple[bool, int]:
    """Atomically record one guest generation for `ip` today and report whether it's allowed.

    Returns (allowed, count_today). allowed is True while the running count is within `limit`.
    Fails open (allowed=True, count=0) on any Redis error or when Redis is unavailable."""
    try:
        client = await get_redis_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Guest quota: redis client unavailable, failing open: {exc}")
        return True, 0
    if client is None:
        return True, 0

    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    key = f"guest_quota:{ip}:{today}"
    try:
        count = await client.incr(key)
        if count == 1:
            # First hit today — set the rolling daily expiry.
            await client.expire(key, _SECONDS_PER_DAY)
        return count <= limit, int(count)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Guest quota: redis op failed, failing open: {exc}")
        return True, 0
