"""Requested beta-invitation email: its suppression list and its per-link delivery ledger (EN-BETA PB-01).

``MailRecipient`` is one row per address, keyed by ``mail_suppression_service.recipient_hash`` (the address is never
stored here), for each address an invitation was emailed to and each one feedback or an unsubscribe suppressed; a
manual re-issue, which sends nothing, adds none. It is the lock a send and an unsubscribe both take, so an opt-out that commits first stops the send,
and it holds the address's suppression: an unsubscribe, a permanent bounce, a complaint or the provider's own
suppression list. Suppression covers invitation and any future promotional mail; requested account mail (verification,
password reset, security notices) never reads it. It outlives the invitation, the delivery and any account, since
honouring an opt-out needs the address recognised again.

``InviteDelivery`` is one row per invitation link that was emailed: the logical send (``delivery_ref``, the provider
idempotency key's and correlation tag's value), the request that permitted it (``permission_via`` and
``permission_requested_on``, recorded by ``created_by``), the provider's id and the state the evidence supports. The
link's raw token is never stored, here or anywhere: an outcome left unknown is resolved by a provider event or by an
admin re-send, which revokes this link and mails a new one, never by sending the same request blind.

Project-specific table names (lessons/ops-deploy-owned-state-needs-a-distinctive-name.md). Plain strings with CHECK
constraints, not PG enums, so SQLite unit tests and PostgreSQL share the schema.
"""
from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String

from app.database import Base

# Why an address is suppressed.
SUPPRESSED_UNSUBSCRIBED = "unsubscribed"
SUPPRESSED_HARD_BOUNCE = "hard_bounce"
SUPPRESSED_COMPLAINT = "complaint"
SUPPRESSED_BY_PROVIDER = "provider_suppressed"
SUPPRESSION_REASONS = (SUPPRESSED_UNSUBSCRIBED, SUPPRESSED_HARD_BOUNCE, SUPPRESSED_COMPLAINT, SUPPRESSED_BY_PROVIDER)

# How the recipient asked for an invitation (the permission the admin records with each send).
PERMISSION_VIA = ("email", "message", "call", "in_person", "other")

# What the evidence says of one emailed link. Local outcomes (written only while the row is "sending"):
STATUS_SENDING = "sending"        # authorised and committed before the provider call
STATUS_FAILED = "failed"          # nothing was sent (a retryable or permanent provider refusal), or the provider's
                                  # email.failed after acceptance
STATUS_UNKNOWN = "unknown"        # the provider may have accepted it; the answer was lost. Never sent again blind.
# Provider evidence (the API's acceptance or a signed webhook):
STATUS_ACCEPTED = "accepted"      # the provider accepted it for delivery: not delivered, not read
STATUS_DELAYED = "delayed"        # the provider is retrying delivery
STATUS_DELIVERED = "delivered"    # the recipient's mail server accepted it: not proof it reached the inbox
STATUS_BOUNCED = "bounced"        # the recipient's server refused it (bounce_type says how)
STATUS_SUPPRESSED = "suppressed"  # the provider refused to send to a suppressed address
STATUS_COMPLAINED = "complained"  # the recipient reported it as spam
DELIVERY_STATUSES = (
    STATUS_SENDING, STATUS_FAILED, STATUS_UNKNOWN, STATUS_ACCEPTED, STATUS_DELAYED, STATUS_DELIVERED,
    STATUS_BOUNCED, STATUS_SUPPRESSED, STATUS_COMPLAINED,
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class MailRecipient(Base):
    __tablename__ = "earningsnerd_mail_recipients"
    __table_args__ = (
        CheckConstraint(
            f"suppression_reason IS NULL OR {_in('suppression_reason', SUPPRESSION_REASONS)}",
            name="ck_earningsnerd_mail_recipients_reason",
        ),
        CheckConstraint(
            "(suppressed_at IS NULL) = (suppression_reason IS NULL)",
            name="ck_earningsnerd_mail_recipients_suppressed",
        ),
    )

    id = Column(Integer, primary_key=True)
    recipient_hash = Column(String(64), nullable=False, unique=True)
    suppressed_at = Column(DateTime(timezone=True), nullable=True)
    suppression_reason = Column(String(20), nullable=True)
    # What suppressed it: "unsubscribe:<delivery_ref>" or "resend:<svix-id>". The first suppression stands.
    suppression_event = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class InviteDelivery(Base):
    __tablename__ = "earningsnerd_invite_deliveries"
    __table_args__ = (
        CheckConstraint(_in("status", DELIVERY_STATUSES), name="ck_earningsnerd_invite_deliveries_status"),
        CheckConstraint(_in("permission_via", PERMISSION_VIA), name="ck_earningsnerd_invite_deliveries_permission"),
        Index("ix_earningsnerd_invite_deliveries_recipient", "recipient_hash"),
        Index("ix_earningsnerd_invite_deliveries_provider_email_id", "provider_email_id"),
    )

    id = Column(Integer, primary_key=True)
    # One email per link: a re-send mints a new invite, and with it a new delivery.
    invite_id = Column(Integer, ForeignKey("invite_codes.id", ondelete="CASCADE"), nullable=False, unique=True)
    recipient_hash = Column(String(64), nullable=False)
    # uuid4 hex, server-made: the Idempotency-Key ("en-invite-<ref>") and the tag the provider's events carry back.
    delivery_ref = Column(String(32), nullable=False, unique=True)
    # SHA-256 of the unsubscribe token the email carries; the raw token lives only in the email.
    unsubscribe_token_hash = Column(String(64), nullable=False, unique=True)
    status = Column(String(20), nullable=False)
    permission_via = Column(String(16), nullable=False)
    permission_requested_on = Column(Date, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider_email_id = Column(String(64), nullable=True)
    # An exception's class or the provider's failure reason, from a closed set: never a message or an address.
    error_kind = Column(String(40), nullable=True)
    bounce_type = Column(String(20), nullable=True)
    # The svix-id of the last provider event applied; NULL until one is, which is how a local outcome is told apart.
    last_event_id = Column(String(80), nullable=True)
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
