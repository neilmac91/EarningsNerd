"""Durable alert delivery (E11b-1): one batch per outbound email, its frozen payload, and the
filings it owns.

The scan services used to send first and log afterwards, so a concurrent run could send twice
and a failed attempt suppressed every retry. Now selection persists a ``DeliveryBatch`` (frozen
subject + HTML, a provider idempotency key bound to that payload) with its ordered
``DeliveryItem`` rows BEFORE any external send, and delivery moves through fenced conditional
transitions (``notification_delivery_service``). The compatibility ``NotificationLog`` row and the
watchlist watermark are written only when the provider accepts the email.

Project-specific table names (lessons/ops-deploy-owned-state-needs-a-distinctive-name.md). Plain
strings, not PG enums, so SQLite unit tests and PostgreSQL share the schema.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

KIND_FILING_REALTIME = "filing_realtime"
KIND_FILING_DIGEST = "filing_digest"

STATUS_READY = "ready"            # durable work awaiting a worker
STATUS_CLAIMED = "claimed"        # short preparation lease; no dispatch yet
STATUS_SENDING = "sending"        # dispatch authorised and committed before external I/O
STATUS_ACCEPTED = "accepted"      # provider accepted; inbox delivery is a separate question
STATUS_RETRYABLE = "retryable"    # documented retryable outcome, replay identity retained
STATUS_AMBIGUOUS = "ambiguous"    # acceptance unknown; never auto-dispatched again
STATUS_SUPPRESSED = "suppressed"  # current user/watch/preference/entitlement state forbids dispatch
TERMINAL_STATUSES = frozenset({STATUS_ACCEPTED, STATUS_AMBIGUOUS, STATUS_SUPPRESSED})


class DeliveryBatch(Base):
    __tablename__ = "earningsnerd_delivery_batches"
    __table_args__ = (
        Index("ix_earningsnerd_delivery_batches_due", "status", "next_attempt_at"),
        Index("ix_earningsnerd_delivery_batches_lease", "status", "lease_expires_at"),
    )

    id = Column(Integer, primary_key=True)
    kind = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    # Frozen at selection: a retry replays these bytes, never a re-query or a re-render.
    to_email = Column(Text, nullable=False)
    from_email = Column(Text, nullable=False)
    expected_item_count = Column(Integer, nullable=False)
    subject = Column(Text, nullable=False)
    body_html = Column(Text, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    # Provider idempotency key, assigned once and bound to payload_sha256; never regenerated.
    idempotency_key = Column(String(36), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default=STATUS_READY)
    owner_token = Column(String(36), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    first_dispatch_at = Column(DateTime(timezone=True), nullable=True)  # replay window anchor
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    provider_email_id = Column(String(64), nullable=True)
    last_error_kind = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="delivery_batches")
    items = relationship(
        "DeliveryItem", back_populates="batch", cascade="all, delete-orphan", order_by="DeliveryItem.position"
    )


class DeliveryItem(Base):
    __tablename__ = "earningsnerd_delivery_items"
    __table_args__ = (
        # Realtime and digest can never both own one filing for one user on one channel.
        UniqueConstraint("user_id", "filing_id", "channel", name="uq_earningsnerd_delivery_items_owner"),
        Index("ix_earningsnerd_delivery_items_batch", "batch_id", "position"),
    )

    id = Column(Integer, primary_key=True)
    batch_id = Column(
        Integer, ForeignKey("earningsnerd_delivery_batches.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filing_id = Column(Integer, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(20), nullable=False)
    position = Column(Integer, nullable=False)

    batch = relationship("DeliveryBatch", back_populates="items")
    filing = relationship("Filing")
