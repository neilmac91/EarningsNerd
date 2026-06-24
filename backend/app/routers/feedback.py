"""Dedicated beta-feedback pipeline: an in-dashboard bug/feature/general report endpoint.

Authenticated-only, so — per the roadmap decision — there is NO Turnstile: the session plus a
per-user rate limit are sufficient bot defense, and a CAPTCHA inside a dashboard widget is needless
friction. The submitter's user id is recorded for follow-up; the IP is hashed for privacy. A
``feedback_submitted`` PostHog event feeds the beta funnel, and the admin is notified best-effort.
"""
import hashlib
import html
import logging
import os
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.models.feedback import Feedback
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.posthog_client import capture_event
from app.services.rate_limiter import get_client_ip
from app.services.resend_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)

# One-way IP hashing, peppered with SECRET_KEY (validated non-default in prod) — same approach as the
# contact pipeline, so no weak public default salt.
_IP_HASH_SALT = os.getenv("IP_HASH_SALT") or settings.SECRET_KEY

# Per-user sliding window. Authenticated, so we key on user id (not IP). Generous — this guards
# against accidental spam/abuse, not legitimate beta chatter.
_RATE_LIMIT_REQUESTS = 10
_RATE_LIMIT_WINDOW = timedelta(hours=1)
_rate_store: dict[int, list[datetime]] = {}


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{ip}{_IP_HASH_SALT}".encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str:
    return get_client_ip(request)


def _rate_limited(user_id: int) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - _RATE_LIMIT_WINDOW
    history = [t for t in _rate_store.get(user_id, []) if t > cutoff]
    if len(history) >= _RATE_LIMIT_REQUESTS:
        _rate_store[user_id] = history
        return True
    history.append(now)
    _rate_store[user_id] = history
    return False


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit beta feedback (bug / feature / general) from the in-dashboard widget."""
    if _rate_limited(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've sent a lot of feedback in a short window — please try again shortly.",
        )

    feedback = Feedback(
        user_id=current_user.id,
        type=payload.type,
        message=payload.message,
        page_url=payload.page_url,
        status="new",
        ip_address=_hash_ip(_client_ip(request)),
    )
    try:
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        logger.info("Feedback #%s (%s) from user %s", feedback.id, feedback.type, current_user.id)
    except Exception as e:  # pragma: no cover - defensive
        db.rollback()
        logger.error("Failed to save feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save feedback") from e

    # Beta-funnel signal — telemetry must never break the request.
    try:
        capture_event(str(current_user.id), "feedback_submitted", {"type": feedback.type})
    except Exception:  # pragma: no cover - defensive
        pass

    # Notify the admin best-effort; the row is already saved, so never fail on email.
    try:
        await _notify_admin(current_user, feedback)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to send feedback notification email")

    return feedback


async def _notify_admin(user: User, feedback: Feedback) -> None:
    from_email = settings.RESEND_FROM_EMAIL
    if not from_email:
        return
    # parseaddr robustly extracts the address from "Name <addr>" (falls back to the raw value).
    admin_email = parseaddr(from_email)[1] or from_email
    safe_email = html.escape(user.email or "")
    safe_message = html.escape(feedback.message)
    page_html = (
        f'<p><strong>Page:</strong> {html.escape(feedback.page_url)}</p>' if feedback.page_url else ""
    )
    body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:16px;">
      <h2 style="margin:0 0 12px;">New beta feedback — {html.escape(feedback.type)}</h2>
      <p><strong>From:</strong> {safe_email} (user #{user.id})</p>
      {page_html}
      <div style="background:#f9f9f9;border-left:4px solid #10B981;padding:12px;margin-top:8px;white-space:pre-wrap;">{safe_message}</div>
      <p style="color:#666;font-size:12px;margin-top:12px;">Feedback #{feedback.id}</p>
    </div>
    """
    await send_email(
        to=[admin_email],
        # Plain-text subject: use the raw email, not the HTML-escaped one (no &amp; entities here).
        subject=f"[Beta feedback] {feedback.type} from {user.email or ''}",
        html=body,
    )
