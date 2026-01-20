from __future__ import annotations

from typing import Iterable

import httpx

from app.config import settings


class ResendError(RuntimeError):
    pass


async def send_email(
    to: Iterable[str],
    subject: str,
    html: str,
    from_email: str | None = None,
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

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{settings.RESEND_BASE_URL}/emails",
            json=payload,
            headers=headers,
        )

    if response.status_code >= 400:
        raise ResendError(
            f"Resend API error ({response.status_code}): {response.text}"
        )

    return response.json()
