from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class RefreshToken(Base):
    """
    Opaque refresh token issued alongside the short-lived access token.

    Only the SHA-256 hash of the raw token is stored, so a database leak does not
    expose usable credentials. Tokens are single-use and rotated on every refresh:
    presenting a token mints a new one and revokes the old. Presenting an
    already-revoked token is treated as a reuse/theft signal and revokes the whole
    chain for that user (see refresh_token_service.rotate_refresh_token).

    ``expires_at``/``revoked_at`` are stored as naive UTC to match the ``datetime.utcnow()``
    convention used elsewhere in auth and to avoid timezone-comparison pitfalls on SQLite.
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # SHA-256 hex digest of the raw token (64 chars). The raw token is never persisted.
    token_hash = Column(String(64), unique=True, nullable=False, index=True)

    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    # Rotation chain: the token that superseded this one (set when rotated).
    replaced_by_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True)

    # Lightweight audit context (best-effort; not used for authorization).
    user_agent = Column(String(500), nullable=True)
    ip_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked_at is not None})>"
