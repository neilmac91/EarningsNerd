"""Dedicated beta-feedback pipeline: an in-dashboard bug/feature/general report endpoint.

Authenticated-only, so — per the roadmap decision — there is NO Turnstile: the session plus a
per-user rate limit are sufficient bot defense, and a CAPTCHA inside a dashboard widget is needless
friction. The submitter's user id is recorded for follow-up; the IP is hashed for privacy. A
``feedback_submitted`` PostHog event feeds the beta funnel, and the admin is notified best-effort.
"""
import hashlib
import html
import logging
from email.utils import parseaddr

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.models.feedback import Feedback
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services import filing_list_service
from app.services.posthog_client import capture_event
from app.services.rate_limiter import RateLimiter, enforce_rate_limit, get_client_ip
from app.services.resend_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)

# One-way IP hashing, peppered with SECRET_KEY (validated non-default in prod) — same approach as the
# contact pipeline, so no weak public default salt.
_IP_HASH_SALT = settings.IP_HASH_SALT or settings.SECRET_KEY

# Per-user sliding window (10/hour). Authenticated, so we key on user id (not IP). Generous — this
# guards against accidental spam/abuse, not legitimate beta chatter. State lives ONLY in the shared
# RateLimiter (bounded key cardinality, lazy idle cleanup, Retry-After).
FEEDBACK_LIMITER = RateLimiter(limit=10, window_seconds=3600)
FEEDBACK_RATE_LIMIT_DETAIL = (
    "You've sent a lot of feedback in the last hour. Try again a little later."
)


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{ip}{_IP_HASH_SALT}".encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str:
    return get_client_ip(request)


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit beta feedback (bug / feature / general) from the in-dashboard widget."""
    enforce_rate_limit(
        request,
        FEEDBACK_LIMITER,
        f"feedback:{current_user.id}",
        include_client_ip=False,  # per-user cap: an IP pool must not multiply it
        error_detail=FEEDBACK_RATE_LIMIT_DETAIL,
    )
    # Read before the insert's commit expires the user, whose session the unit then closes.
    user_id, user_email = current_user.id, current_user.email
    ip_address = _hash_ip(_client_ip(request))

    def persist() -> FeedbackResponse:
        # One unit in the thread pool: the insert and the response it echoes, released before the
        # admin mail goes out, so the send holds no pooled connection
        # (lessons/ops-release-cached-filing-reads-before-yield.md).
        feedback = Feedback(
            user_id=user_id,
            type=payload.type,
            message=payload.message,
            page_url=payload.page_url,
            status="new",
            ip_address=ip_address,
        )
        try:
            try:
                db.add(feedback)
                db.commit()
                db.refresh(feedback)
                logger.info("Feedback #%s (%s) from user %s", feedback.id, feedback.type, user_id)
            except Exception as e:  # pragma: no cover - defensive
                db.rollback()
                logger.error("Failed to save feedback: %s", e)
                raise HTTPException(status_code=500, detail="Failed to save feedback") from e
            return FeedbackResponse.model_validate(feedback)
        finally:
            filing_list_service.release_request_session(db)

    saved = await run_in_threadpool(persist)

    # Beta-funnel signal — telemetry must never break the request.
    try:
        capture_event(str(user_id), "feedback_submitted", {"type": saved.type})
    except Exception:  # pragma: no cover - defensive
        pass

    # Notify the admin best-effort; the row is already saved, so never fail on email.
    try:
        await _notify_admin(user_id, user_email, saved.id, payload)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to send feedback notification email")

    return saved


async def _notify_admin(user_id: int, user_email: str | None, feedback_id: int, payload: FeedbackCreate) -> None:
    from_email = settings.RESEND_FROM_EMAIL
    if not from_email:
        return
    # parseaddr robustly extracts the address from "Name <addr>" (falls back to the raw value).
    admin_email = parseaddr(from_email)[1] or from_email
    safe_email = html.escape(user_email or "")
    safe_message = html.escape(payload.message)
    page_html = (
        f'<p><strong>Page:</strong> {html.escape(payload.page_url)}</p>' if payload.page_url else ""
    )
    body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:16px;">
      <h2 style="margin:0 0 12px;">New beta feedback — {html.escape(payload.type)}</h2>
      <p><strong>From:</strong> {safe_email} (user #{user_id})</p>
      {page_html}
      <div style="background:#f9f9f9;border-left:4px solid #10B981;padding:12px;margin-top:8px;white-space:pre-wrap;">{safe_message}</div>
      <p style="color:#666;font-size:12px;margin-top:12px;">Feedback #{feedback_id}</p>
    </div>
    """
    await send_email(
        to=[admin_email],
        # Plain-text subject: use the raw email, not the HTML-escaped one (no &amp; entities here).
        subject=f"[Beta feedback] {payload.type} from {user_email or ''}",
        html=body,
    )
