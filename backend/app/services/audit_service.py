"""
Audit logging service for GDPR compliance and security monitoring.

This service provides helper functions to create audit log entries for
important user actions and system events.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def create_audit_log(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry.

    Args:
        db: Database session
        action: Action being logged (e.g., "user_deleted", "data_exported")
        user_id: ID of the user performing the action (optional, may be deleted)
        user_email: Email of the user (optional, for deleted users)
        entity_type: Type of entity affected (e.g., "user", "subscription")
        entity_id: ID of the affected entity
        ip_address: Hashed IP address of the request
        user_agent: User agent string from the request
        details: Additional context as a dictionary (will be stored as JSON)
        status: Status of the action ("success", "failed", "partial")
        error_message: Error message if status is "failed"

    Returns:
        The created AuditLog instance

    Example:
        >>> create_audit_log(
        ...     db=db,
        ...     action="user_deleted",
        ...     user_id=123,
        ...     user_email="user@example.com",
        ...     entity_type="user",
        ...     entity_id="123",
        ...     details={"reason": "user_requested", "third_party_deletions": {...}},
        ...     status="success"
        ... )
    """
    try:
        audit_log = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status,
            error_message=error_message,
        )

        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)

        logger.info(
            f"Audit log created: action={action}, user_id={user_id}, "
            f"entity_type={entity_type}, status={status}"
        )

        return audit_log

    except Exception as e:
        logger.error(f"Failed to create audit log: {str(e)}")
        db.rollback()
        # Don't raise - audit logging should never break the main flow
        return None


# Convenience functions for common audit events

def log_user_deletion(
    db: Session,
    user_id: int,
    user_email: str,
    third_party_results: Dict[str, str],
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Log a user account deletion."""
    return create_audit_log(
        db=db,
        action="user_deleted",
        user_id=user_id,
        user_email=user_email,
        entity_type="user",
        entity_id=str(user_id),
        ip_address=ip_address,
        details={
            "third_party_deletions": third_party_results,
            "timestamp": datetime.utcnow().isoformat(),
        },
        status="success",
    )


def log_data_export(
    db: Session,
    user_id: int,
    user_email: str,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Log a user data export."""
    return create_audit_log(
        db=db,
        action="data_exported",
        user_id=user_id,
        user_email=user_email,
        entity_type="user",
        entity_id=str(user_id),
        ip_address=ip_address,
        details={
            "timestamp": datetime.utcnow().isoformat(),
        },
        status="success",
    )


def log_failed_login(
    db: Session,
    email: str,
    ip_address: Optional[str] = None,
    error_message: Optional[str] = None,
) -> AuditLog:
    """Log a failed login attempt."""
    return create_audit_log(
        db=db,
        action="login_failed",
        user_email=email,
        entity_type="user",
        ip_address=ip_address,
        details={
            "timestamp": datetime.utcnow().isoformat(),
        },
        status="failed",
        error_message=error_message,
    )


def log_subscription_change(
    db: Session,
    user_id: int,
    user_email: str,
    subscription_id: str,
    action: str,  # "created", "updated", "cancelled"
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Log a subscription change."""
    return create_audit_log(
        db=db,
        action=f"subscription_{action}",
        user_id=user_id,
        user_email=user_email,
        entity_type="subscription",
        entity_id=subscription_id,
        details=details or {},
        status="success",
    )
