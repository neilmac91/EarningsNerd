"""The one-time handoff of an OAuth sign-in from its provider callback to the page it lands on (E29 (5)).

A callback's answer is a navigation, which cannot hold the session cookies' Web Lock (``frontend/lib/api/client.ts``),
so it no longer sets the session cookies: a refresh another tab sent with the previous account's cookies could answer
after it and set those back over the new session's. The callback commits the sign-in with one of these rows instead
and redirects to the frontend's ``/auth/complete`` with the one-time code in the URL fragment, which no request log
records; that page posts the code to ``POST /api/auth/oauth/complete`` under the lock, and that post's answer sets the
session cookies (``oauth_account_service.commit_oauth_sign_in`` and ``redeem_session_handoff``).

Only SHA-256 hashes are stored: of the code, and of the browser-binding value the callback sets as a cookie on the
browser it answers (``binder_hash``), so a code minted in one browser is refused from another, which lacks that cookie
(login CSRF). A row is single use (``used_at``, set by a guarded UPDATE) and lives 120 seconds (``expires_at``).
Timezone-aware columns, written and compared with ``app.utils.datetimes.utcnow()``. Project-specific name: never adopt
a conventional table (``lessons/ops-deploy-owned-state-needs-a-distinctive-name.md``). The rows go with their account
(``ON DELETE CASCADE``), and the callback's commit deletes the expired ones.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.database import Base


class SessionHandoff(Base):
    __tablename__ = "earningsnerd_session_handoffs"
    __table_args__ = (
        UniqueConstraint("code_hash", name="uq_earningsnerd_session_handoffs_code_hash"),
        Index("ix_earningsnerd_session_handoffs_user_id", "user_id"),
        Index("ix_earningsnerd_session_handoffs_expires_at", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    # SHA-256 hex digests (64 chars). The raw code and binder are never persisted.
    code_hash = Column(String(64), nullable=False)
    binder_hash = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
