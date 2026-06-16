"""Cloudflare Turnstile (bot defense) verification.

Verifies the token a browser Turnstile widget produces against Cloudflare's siteverify
endpoint. Designed for a safe, coordinated rollout:

- **Dark until configured.** When ``TURNSTILE_SECRET_KEY`` is unset, :func:`enforce_turnstile`
  is a no-op, so wiring it into endpoints changes nothing until the operator sets *both* the
  backend secret and the frontend ``NEXT_PUBLIC_TURNSTILE_SITE_KEY`` (which makes the widget
  render and send a token). Until then there is no widget and no enforcement.
- **Fail closed on a missing/invalid token** once configured (the common attack case).
- **Fail open on infra errors** (Cloudflare unreachable) — availability beats strict bot
  blocking for a sign-in form, and login still requires the password.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TIMEOUT_SECONDS = 4.0
# Header the frontend attaches; Cloudflare's own field name plus an explicit alias.
_TOKEN_HEADERS = ("cf-turnstile-response", "x-turnstile-token")


def turnstile_enabled() -> bool:
    return bool(settings.TURNSTILE_SECRET_KEY)


async def verify_turnstile(token: Optional[str], *, remote_ip: Optional[str] = None) -> bool:
    """Return True if ``token`` is valid — or if Turnstile is not configured (no-op)."""
    if not turnstile_enabled():
        return True
    if not token:
        return False

    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as hx:
            resp = await hx.post(_SITEVERIFY_URL, data=data)
            resp.raise_for_status()
            return bool(resp.json().get("success", False))
    except Exception as exc:  # fail open on infrastructure errors
        logger.warning(
            "Turnstile verification unavailable (%s); failing open", exc.__class__.__name__
        )
        return True


async def enforce_turnstile(request: Request) -> None:
    """Reject the request with 403 if Turnstile is configured and the token is missing/invalid.

    No-op when Turnstile is unconfigured.
    """
    if not turnstile_enabled():
        return
    token = next(
        (request.headers.get(h) for h in _TOKEN_HEADERS if request.headers.get(h)), None
    )
    remote_ip = request.client.host if request.client else None
    if not await verify_turnstile(token, remote_ip=remote_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bot verification failed. Please refresh the page and try again.",
        )
