"""Per-IP daily quota for anonymous (guest) summary generation (roadmap S5).

Keeps free, no-login activation sustainable by capping guest generations per IP per day while
NEVER gating the first summary of the day (a brand-new IP is always under the cap). This is the
denial-of-wallet backstop for the unauthenticated generate endpoint.

**Durable, not Redis-backed.** The earlier implementation used an atomic Redis INCR, but Redis is
OFF in production (SKIP_REDIS_INIT=true), so it failed open on every request there and never
actually capped anyone. State now lives in the ``guest_daily_usage`` table, so the cap holds across
Cloud Run instances and restarts.

**Keyed on the trusted client IP.** Callers pass ``rate_limiter.get_client_ip(request)`` — the real
client extracted from ``X-Forwarded-For`` per ``TRUSTED_PROXY_HOPS`` — NOT ``request.client.host``,
which behind Cloud Run is the shared Google front-end address (every guest would collapse onto one
key). The IP is stored only as a ``SECRET_KEY``-peppered SHA-256, so raw IPs are never persisted.

Still **fails open** (allowed) on any DB error: infrastructure must never block a first-time
visitor's first summary. A cost control is the wrong thing to fail closed on for activation.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GuestDailyUsage

logger = logging.getLogger(__name__)


def _ip_hash(client_ip: str) -> str:
    # Peppered so a bare SHA-256 of an IPv4 (the whole ~4.2B space is precomputable) isn't reversible.
    return hashlib.sha256(f"{client_ip}:{settings.SECRET_KEY}".encode("utf-8")).hexdigest()


def check_and_increment_guest_quota(db: Session, client_ip: str, limit: int) -> Tuple[bool, int]:
    """Record one guest generation for ``client_ip`` today and report whether it's allowed.

    Returns ``(allowed, count_today)``. ``allowed`` is True while the running count is within
    ``limit``. Fails open ``(True, 0)`` on any DB error — a first-time visitor's first summary must
    never be blocked by infrastructure. Pass the *trusted* client IP (get_client_ip), not the raw
    ``request.client.host``.
    """
    # An unresolvable IP fails open: otherwise every guest whose IP can't be determined would share
    # the one "unknown" key and collectively exhaust a single daily budget, blocking each other.
    if not client_ip or client_ip.strip().lower() in ("unknown", "", "none"):
        return True, 0

    try:
        ip_hash = _ip_hash(client_ip)
        today = datetime.now(timezone.utc).date()
        # with_for_update locks the row so concurrent generations from one IP serialize instead of
        # both reading the same count and overwriting each other (a lost update). No-op on SQLite,
        # which serializes writes anyway; a real row lock on Postgres (prod).
        row = (
            db.query(GuestDailyUsage)
            .filter(GuestDailyUsage.ip_hash == ip_hash)
            .with_for_update()
            .first()
        )
        if row is None:
            try:
                # Insert inside a SAVEPOINT so a concurrent insert's IntegrityError rolls back only
                # this statement — a plain db.rollback() on the shared request session would expire
                # every object loaded earlier in the request (e.g. the filing being summarized).
                with db.begin_nested():
                    db.add(GuestDailyUsage(ip_hash=ip_hash, usage_date=today, count=1))
                db.commit()
                return True, 1  # the first generation of the day is always under the cap
            except IntegrityError:
                # A concurrent request inserted the same row first — re-read it under the lock.
                row = (
                    db.query(GuestDailyUsage)
                    .filter(GuestDailyUsage.ip_hash == ip_hash)
                    .with_for_update()
                    .first()
                )
                if row is None:
                    return True, 0  # fail open — can't determine the count
        if row.usage_date != today:
            # First generation of a new UTC day — reset the daily window (one row, reused per IP).
            row.usage_date = today
            row.count = 1
        else:
            row.count = (row.count or 0) + 1
        db.commit()
        return row.count <= limit, int(row.count)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Guest quota: DB op failed, failing open: {exc}")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return True, 0
