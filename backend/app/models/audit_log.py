from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    """
    Audit log for tracking important user actions and data changes.

    This is critical for GDPR compliance and security monitoring.
    Tracks actions like: account creation, deletion, data exports,
    login attempts, permission changes, etc.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # User information (nullable because user may be deleted)
    user_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # e.g., "user_deleted", "data_exported", "login_failed"
    entity_type = Column(String(50), nullable=True)  # e.g., "user", "subscription", "summary"
    entity_id = Column(String(100), nullable=True)  # ID of the affected entity

    # Context and metadata
    ip_address = Column(String(64), nullable=True)  # Hashed IP for privacy
    user_agent = Column(String(500), nullable=True)
    details = Column(JSON, nullable=True)  # Additional context as JSON

    # Status
    status = Column(String(20), nullable=False, default="success")  # success, failed, partial
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id}, status='{self.status}')>"
