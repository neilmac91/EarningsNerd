from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class InviteCode(Base):
    """A single-use, server-side registration invite for the closed beta.

    Only the SHA-256 hash of the token is stored (never the raw token, which lives only in the magic
    link we email). ``email`` is optional: when set, only that address may redeem; when null, the
    first registration to present the token redeems it. Redemption is single-use (``used_at``) and
    sets ``User.is_beta``, so the 100%-off promo applies at checkout via server-set eligibility —
    never a client-supplied parameter.
    """
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    # SHA-256 hex digest of the raw token (mirrors the email-verification pattern in auth.py).
    code_hash = Column(String(64), unique=True, nullable=False, index=True)
    # Optional binding: when set, only this address may redeem the invite.
    email = Column(String(255), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    # Admin who minted it / user who redeemed it (SET NULL so a GDPR delete never orphans the row).
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
