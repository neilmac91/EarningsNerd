from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.models import User
from app.routers.auth import get_current_user
from app.services.resend_service import ResendError, send_email

router = APIRouter()


class TestEmailRequest(BaseModel):
    to: EmailStr | None = None


@router.post("/test")
async def send_test_email(
    payload: TestEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a basic Resend test email."""
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
            html="<strong>It works!</strong>",
        )
    except ResendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"status": "sent", "resend": result}
