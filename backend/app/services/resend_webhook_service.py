"""What a signed Resend webhook says, validated where it enters (CLAUDE.md rule 9); no database, no HTTP.

``signing_key`` reads the Svix secret the signature check keys its HMAC with (moved here from ``routers/webhooks.py``,
which still uses it, so the invitation-email readiness can tell a usable secret from a missing or malformed one).
``parse_event`` turns one delivery's ``type`` and ``data`` into a ``ProviderEvent`` holding only what the mail controls
act on: the provider's email id, our own delivery reference from the tags we sent, the recipients, and the bounce type
or failure reason from a closed vocabulary. Anything else in the payload (subjects, links, headers, agents) is dropped.

Payload shapes follow Resend's published webhook pages (https://resend.com/docs/webhooks/emails/bounced, .../complained,
.../delivered, .../sent, .../delivery_delayed, .../failed, .../suppressed): ``data.email_id``, ``data.to`` (a list),
``data.tags`` (an object of name to value), ``data.bounce.type`` ("Permanent" or "Temporary"), ``data.failed.reason``.
A retry of one delivery carries the same ``svix-id`` (Resend's event-types page), which is the event's identity here.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import EmailStr, TypeAdapter, ValidationError

# The tag every invitation email carries (invite_delivery_service), echoed in each of its events' data.tags.
DELIVERY_TAG = "en_invite_delivery"

EVENT_SENT = "email.sent"
EVENT_DELIVERED = "email.delivered"
EVENT_DELAYED = "email.delivery_delayed"
EVENT_BOUNCED = "email.bounced"
EVENT_COMPLAINED = "email.complained"
EVENT_FAILED = "email.failed"
EVENT_SUPPRESSED = "email.suppressed"
# The events that change what the controls know of a send, or of an address.
FEEDBACK_EVENTS = frozenset({
    EVENT_SENT, EVENT_DELIVERED, EVENT_DELAYED, EVENT_BOUNCED, EVENT_COMPLAINED, EVENT_FAILED, EVENT_SUPPRESSED,
})

BOUNCE_PERMANENT = "permanent"
BOUNCE_TEMPORARY = "temporary"
BOUNCE_UNDETERMINED = "undetermined"
_BOUNCE_TYPES = {
    "permanent": BOUNCE_PERMANENT,
    "temporary": BOUNCE_TEMPORARY,
    "transient": BOUNCE_TEMPORARY,  # Amazon SES's spelling of the same, which Resend sends through
}

_DELIVERY_REF = re.compile(r"^[0-9a-f]{32}$")
_EMAIL_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_EVENT_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_REASON = re.compile(r"^[a-z0-9_]{1,32}$")
_EMAIL = TypeAdapter(EmailStr)
_MAX_RECIPIENTS = 50


def signing_key(secret: str) -> Optional[bytes]:
    """The HMAC key a Svix signing secret carries: the base64 text after its ``whsec_`` prefix.

    None when that text is empty or not base64: a misconfigured secret, which must fail closed.
    """
    encoded = (secret or "").strip().removeprefix("whsec_")  # a secret stored with a newline still reads
    try:
        key = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
    except ValueError:  # binascii.Error, or a character outside ASCII
        return None
    return key or None


@dataclass(frozen=True)
class ProviderEvent:
    event_id: str
    type: str
    email_id: Optional[str]
    delivery_ref: Optional[str]
    recipients: tuple[str, ...]
    bounce_type: Optional[str] = None
    failure_reason: Optional[str] = None


def _tag_value(tags: Any, name: str) -> Optional[str]:
    """A tag's value from the object Resend's webhook pages show, or the list of {name, value} the send API takes."""
    if isinstance(tags, dict):
        value = tags.get(name)
        return value if isinstance(value, str) else None
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict) and tag.get("name") == name and isinstance(tag.get("value"), str):
                return tag["value"]
    return None


def _recipients(value: Any) -> tuple[str, ...]:
    """The valid addresses in ``data.to`` (a list, or one string), normalised as invites normalise them."""
    items = value if isinstance(value, list) else [value]
    found: list[str] = []
    for item in items[:_MAX_RECIPIENTS]:
        if not isinstance(item, str):
            continue
        try:
            address = str(_EMAIL.validate_python(item.strip())).lower()
        except ValidationError:
            continue
        if address not in found:
            found.append(address)
    return tuple(found)


def parse_event(event_type: Any, data: Any, event_id: Any) -> Optional[ProviderEvent]:
    """The validated feedback a signed delivery carries, or None when it carries none the controls act on."""
    if not isinstance(event_type, str) or event_type not in FEEDBACK_EVENTS or not isinstance(data, dict):
        return None
    if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
        return None
    email_id = data.get("email_id")
    email_id = email_id if isinstance(email_id, str) and _EMAIL_ID.fullmatch(email_id) else None
    ref = _tag_value(data.get("tags"), DELIVERY_TAG)
    ref = ref if isinstance(ref, str) and _DELIVERY_REF.fullmatch(ref) else None
    bounce_type = None
    if event_type == EVENT_BOUNCED:
        bounce = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
        raw = bounce.get("type")
        bounce_type = _BOUNCE_TYPES.get(raw.strip().lower(), BOUNCE_UNDETERMINED) if isinstance(raw, str) else BOUNCE_UNDETERMINED
    failure_reason = None
    if event_type == EVENT_FAILED:
        failed = data.get("failed") if isinstance(data.get("failed"), dict) else {}
        raw = failed.get("reason")
        failure_reason = raw if isinstance(raw, str) and _REASON.fullmatch(raw) else "unspecified"
    return ProviderEvent(
        event_id=event_id,
        type=event_type,
        email_id=email_id,
        delivery_ref=ref,
        recipients=_recipients(data.get("to")),
        bounce_type=bounce_type,
        failure_reason=failure_reason,
    )
