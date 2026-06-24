from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

FeedbackType = Literal["bug", "feature", "general"]


class FeedbackCreate(BaseModel):
    """Schema for an in-dashboard beta feedback submission."""

    type: FeedbackType = "general"
    message: str = Field(..., min_length=5, max_length=4000, description="Feedback content")
    page_url: Optional[str] = Field(None, max_length=500, description="Page the feedback was sent from")

    @field_validator("message")
    @classmethod
    def _validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Message must be at least 5 characters long")
        return v

    @field_validator("page_url")
    @classmethod
    def _validate_page_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class FeedbackResponse(BaseModel):
    """Schema for a feedback submission response."""

    id: int
    type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# Admin-side feedback status values. Kept as a Literal so an invalid status in a PATCH body is
# rejected with a 422 by FastAPI/Pydantic before the handler runs.
FeedbackStatus = Literal["new", "triaged", "resolved"]


class FeedbackAdminItem(BaseModel):
    """A feedback row as surfaced in the admin dashboard (joined with the submitting user's email)."""

    id: int
    user_id: Optional[int]
    user_email: Optional[str]
    type: str
    message: str
    page_url: Optional[str]
    status: str
    created_at: datetime


class FeedbackStatusUpdate(BaseModel):
    """Admin PATCH body to transition a feedback row's triage status."""

    status: FeedbackStatus
