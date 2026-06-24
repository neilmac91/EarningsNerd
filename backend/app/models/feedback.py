from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Feedback(Base):
    """In-dashboard beta feedback (bug report / feature request / general).

    Authenticated-only and kept separate from ``ContactSubmission`` so beta signal stays isolated
    from public contact-form traffic. ``user_id`` is captured for follow-up; ``ip_address`` is stored
    hashed (privacy), mirroring the contact pipeline.
    """

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # bug | feature | general — validated at the schema layer.
    type = Column(String(20), default="general", nullable=False, index=True)
    message = Column(Text, nullable=False)
    page_url = Column(String(500), nullable=True)
    status = Column(String(20), default="new", nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
