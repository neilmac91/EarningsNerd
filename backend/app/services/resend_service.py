"""Resend transport — the only place the outbound email API is called.

Outcomes are classified so a durable delivery record (E11b-1) can decide what a retry means:
``ResendRetryableError`` (rate limit, server error, or a connection that was never established,
so nothing was sent), ``ResendPermanentError`` (the request was rejected; the same payload will
be rejected again) and ``ResendAmbiguousError`` (bytes may have reached the provider and the
answer was lost: timeout, dropped connection, unparsable response). All three extend
``ResendError`` so existing callers that catch it are unchanged. An ``Idempotency-Key`` is sent
when the caller supplies one; Resend documents 24 h retention and returns the original response
for a repeated request with the same key and payload.
"""
from __future__ import annotations

from typing import Iterable

import httpx

from app.config import settings


class ResendError(RuntimeError):
    pass


class ResendRetryableError(ResendError):
    """Retry is supported: 429, 5xx, a documented concurrent-request conflict, or no connection."""


class ResendPermanentError(ResendError):
    """The provider rejected this request; retrying the same payload cannot succeed."""


class ResendAmbiguousError(ResendError):
    """The request may have been accepted; the outcome is unknown."""


# Documented error names (https://www.resend.com/docs/api-reference/errors).
_CONCURRENT_IDEMPOTENT = "concurrent_idempotent_requests"
_INVALID_IDEMPOTENT = "invalid_idempotent_request"


def _error_name(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    return str(body.get("name", "")) if isinstance(body, dict) else ""


async def send_email(
    to: Iterable[str],
    subject: str,
    html: str,
    from_email: str | None = None,
    *,
    idempotency_key: str | None = None,
) -> dict:
    if not settings.RESEND_API_KEY:
        raise ResendError("Resend is not configured. Set RESEND_API_KEY.")

    payload = {
        "from": from_email or settings.RESEND_FROM_EMAIL,
        "to": list(to),
        "subject": subject,
        "html": html,
    }
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.RESEND_BASE_URL}/emails",
                json=payload,
                headers=headers,
            )
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        # No connection was established, so no request reached the provider.
        raise ResendRetryableError(f"Resend connection failed: {e.__class__.__name__}") from e
    except httpx.TransportError as e:
        # Read timeout, dropped connection, protocol error: the request may have been accepted.
        raise ResendAmbiguousError(f"Resend outcome unknown: {e.__class__.__name__}") from e

    if response.status_code >= 400:
        message = f"Resend API error ({response.status_code}): {response.text}"
        name = _error_name(response)
        if name == _INVALID_IDEMPOTENT:
            # Same key, different payload: the original request stands; never re-key it.
            raise ResendAmbiguousError(message)
        if response.status_code >= 500:
            try:
                body = response.json()
            except ValueError as e:
                raise ResendAmbiguousError("Resend server error without a parsed response") from e
            if not isinstance(body, dict):
                raise ResendAmbiguousError("Resend server error without an object response")
        if response.status_code == 429 or response.status_code >= 500 or name == _CONCURRENT_IDEMPOTENT:
            raise ResendRetryableError(message)
        raise ResendPermanentError(message)

    if not 200 <= response.status_code < 300:
        raise ResendAmbiguousError("Resend returned no successful acceptance status")
    try:
        result = response.json()
    except ValueError as e:
        raise ResendAmbiguousError("Resend accepted the request but returned an unparsable response") from e
    if not isinstance(result, dict) or not isinstance(result.get("id"), str) or not result["id"].strip():
        raise ResendAmbiguousError("Resend returned no valid acceptance id")
    return result
