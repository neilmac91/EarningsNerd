from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import User
from app.routers.auth import get_current_user
from app.services import invite_delivery_service
from app.services.job_sessions import run_in_own_session_sync
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.resend_service import ResendError, send_email

router = APIRouter()

# The opt-out is one click per email; a burst beyond this from one address is not a reader.
UNSUBSCRIBE_LIMITER = RateLimiter(limit=20, window_seconds=3600)


class TestEmailRequest(BaseModel):
    to: EmailStr | None = None


@router.post("/test")
async def send_test_email(
    payload: TestEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a basic Resend test email. Admin only.

    Sends from the platform's verified sender to an arbitrary recipient, so it must not be reachable
    by ordinary accounts — otherwise anyone could emit mail from our domain to any address and wreck
    its sending reputation. (The identical /api/admin/email/test is already admin-gated.)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    to_email = payload.to or current_user.email
    if not to_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipient email available.",
        )

    try:
        result = await send_email(
            to=[to_email],
            subject="EarningsNerd test email",
            html="<strong>It works.</strong>",
        )
    except ResendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"status": "sent", "resend": result}


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=invite_delivery_service.MAX_UNSUBSCRIBE_TOKEN)


@router.post("/unsubscribe")
async def unsubscribe(payload: UnsubscribeRequest, request: Request):
    """Stop invitation (and any future promotional) email to the address an unsubscribe link was sent to (EN-BETA
    PB-01). No login: the token is the email's own. Account mail the reader requests still arrives.

    A POST, never a GET: the page the email links (frontend/app/email/unsubscribe) reads the token from its fragment
    and posts it only when its reader presses the button, so a link scanner that fetches the page or this route
    changes nothing (a GET here answers 405). Idempotent: a second press is the same answer."""
    enforce_rate_limit(
        request, UNSUBSCRIBE_LIMITER, "email-unsubscribe", error_detail="Too many requests. Try again later."
    )
    found = await run_in_threadpool(run_in_own_session_sync, invite_delivery_service.unsubscribe, payload.token)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This unsubscribe link isn't valid.")
    return {"status": "unsubscribed"}
