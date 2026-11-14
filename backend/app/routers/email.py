from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from app.services import invite_delivery_service
from app.services.job_sessions import run_in_own_session_sync
from app.services.rate_limiter import RateLimiter, enforce_rate_limit

router = APIRouter()

# The opt-out is one click per email; a burst beyond this from one address is not a reader.
UNSUBSCRIBE_LIMITER = RateLimiter(limit=20, window_seconds=3600)


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
