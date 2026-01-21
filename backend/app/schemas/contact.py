from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactSubmissionCreate(BaseModel):
    """Schema for creating a contact form submission"""
    name: str = Field(..., min_length=2, max_length=100, description="Sender's name")
    email: EmailStr = Field(..., description="Sender's email address")
    subject: Optional[str] = Field(None, max_length=200, description="Optional subject line")
    message: str = Field(..., min_length=10, max_length=2000, description="Message content")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize name"""
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters long")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate and sanitize message"""
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) < 10:
            raise ValueError("Message must be at least 10 characters long")
        return v

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize subject"""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class ContactSubmissionResponse(BaseModel):
    """Schema for contact form submission response"""
    id: int
    name: str
    email: str
    subject: Optional[str]
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
