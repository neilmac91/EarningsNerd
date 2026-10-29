from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    referral_code = Column(String(8), unique=True, index=True, nullable=False)
    referred_by = Column(String(8), index=True, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Nothing writes or reads this since E46 (2) dropped the welcome mail's verification step, whose
    # link led to no page; the column stays, as dropping one is a schema change of its own.
    email_verified = Column(Boolean, default=False, nullable=False)
    welcome_email_sent = Column(Boolean, default=False, nullable=False)
    position = Column(Integer, nullable=False)
    priority_score = Column(Integer, default=0, nullable=False)
