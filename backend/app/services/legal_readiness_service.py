"""Availability of new collection and commercial activity, separate from existing-user rights.

Configuration supplies an operator-approved public notice; it cannot certify compliance. Sales
and promotion deliberately have no enabling switch until their consent/lifecycle controls exist.
Requested beta-invitation email is a capability of its own (``invitation_email_readiness``): its
permission record, send-time suppression, unsubscribe and authenticated bounce/complaint updates
exist in code, so it has an operator switch, effective only while each of its conditions holds.

Invited-cohort registration (``invited_cohort_readiness``) is an admission exception, not collection:
while collection is held, under ``REGISTRATION_MODE=invite_only``, an invitation bound to its
recipient's address whose cohort is exactly the configured one may still open an account. Collection
readiness and the public readiness answer do not change with it, so general registration, the
waitlist, contact, promotion and checkout stay as they say. Each creation path asks ``admits_invite``
(before an invitation is minted, re-issued or mailed) or ``require_account_admission`` (where an
account is created), afresh each time.

The readiness reasons name conditions, never values: an unpublished operator's draft fields, the
provider key, the webhook secret and the configured cohort stay out of every response.
"""
from __future__ import annotations

from typing import TypedDict

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import settings
from app.services import resend_service
from app.services.resend_webhook_service import signing_key
from app.utils.text import has_control_characters

TERMS_VERSION = "2026-10-24"
ELIGIBILITY_VERSION = "2026-10-24"
COLLECTION_UNAVAILABLE_MESSAGE = "New registrations and submissions are temporarily unavailable."
INVITATION_EMAIL_UNAVAILABLE_MESSAGE = "Invitation email delivery is currently unavailable."

# Why new collection is held, in the order an operator clears them (docs/LEGAL_READINESS.md).
COLLECTION_DISABLED = "collection_disabled"          # LEGAL_COLLECTION_ENABLED is false
OPERATOR_UNPUBLISHED = "operator_unpublished"        # LEGAL_OPERATOR_PUBLISHED is false
OPERATOR_INCOMPLETE = "operator_incomplete"          # published, but a field is missing or invalid
# Why requested invitation email is held, as above.
COLLECTION_UNAVAILABLE = "collection_unavailable"    # no invitation can be redeemed, so none is mailed
INVITATION_EMAIL_DISABLED = "invitation_email_disabled"  # LEGAL_INVITATION_EMAIL_ENABLED is false
PROVIDER_UNCONFIGURED = "provider_unconfigured"      # RESEND_API_KEY is empty
PROVIDER_FEEDBACK_UNVERIFIED = "provider_feedback_unverified"  # no usable Svix RESEND_WEBHOOK_SECRET
# Why the invited-cohort exception is held, as above.
REGISTRATION_NOT_INVITE_ONLY = "registration_not_invite_only"  # REGISTRATION_MODE is public: it narrows invites only
INVITED_COHORT_DISABLED = "invited_cohort_disabled"  # LEGAL_INVITED_COHORT_ENABLED is false
INVITED_COHORT_UNSET = "invited_cohort_unset"        # LEGAL_INVITED_COHORT is empty, or no invite could carry it

# InviteCode.cohort's width: a longer configured cohort matches no invite.
_COHORT_MAX_LENGTH = 64

_EMAIL = TypeAdapter(EmailStr)
_PLACEHOLDERS = frozenset({"tbd", "todo", "unknown", "placeholder", "not published", "n/a"})


class CollectionUnavailable(Exception):
    """The caller must not collect new prospect/account information."""


class Capability(TypedDict):
    available: bool
    reasons: list[str]


class PublicOperator(TypedDict):
    legal_name: str
    postal_address: str
    country: str
    contact_email: str


def public_operator() -> PublicOperator | None:
    """Return only an explicitly published, complete notice; never leak draft configuration.

    This checks presence and transport-safe values, not the legal sufficiency of a name/address.
    The operator must verify those details before authorizing publication.
    """
    if not settings.LEGAL_OPERATOR_PUBLISHED:
        return None
    values = {
        "legal_name": settings.LEGAL_OPERATOR_NAME.strip(),
        "postal_address": settings.LEGAL_OPERATOR_POSTAL_ADDRESS.strip(),
        "country": settings.LEGAL_OPERATOR_COUNTRY.strip(),
        "contact_email": settings.LEGAL_OPERATOR_EMAIL.strip(),
    }
    if any(not value or value.casefold() in _PLACEHOLDERS for value in values.values()):
        return None
    # Postal addresses may be multiline; reject other control characters and markup is never
    # rendered as HTML by the public notice component.
    if any(any(ord(char) < 32 and char not in "\n\r\t" for char in value) for value in values.values()):
        return None
    try:
        email = str(_EMAIL.validate_python(values["contact_email"]))
    except ValidationError:
        return None
    return PublicOperator(
        legal_name=values["legal_name"], postal_address=values["postal_address"],
        country=values["country"], contact_email=email,
    )


def is_collection_available() -> bool:
    return settings.LEGAL_COLLECTION_ENABLED and public_operator() is not None


def collection_readiness() -> Capability:
    """``is_collection_available`` with the conditions that hold it, for the admin's banner (never the values)."""
    reasons: list[str] = []
    if not settings.LEGAL_COLLECTION_ENABLED:
        reasons.append(COLLECTION_DISABLED)
    if not settings.LEGAL_OPERATOR_PUBLISHED:
        reasons.append(OPERATOR_UNPUBLISHED)
    elif public_operator() is None:
        reasons.append(OPERATOR_INCOMPLETE)
    return Capability(available=not reasons, reasons=reasons)


def _configured_cohort() -> str | None:
    """``LEGAL_INVITED_COHORT`` when an invitation could carry it, else None. The match is exact, so a value no minted
    invitation can hold (surrounding whitespace, which a mint strips; a control character; more than the column's 64
    characters) is no cohort rather than a near match."""
    value = settings.LEGAL_INVITED_COHORT
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > _COHORT_MAX_LENGTH:
        return None
    return None if has_control_characters(value) else value


def invited_cohort_readiness() -> Capability:
    """Whether the invited-cohort exception admits accounts now, and what holds it (conditions, never the cohort).

    Effective only under ``REGISTRATION_MODE=invite_only``, with the operator's switch on and a cohort an invitation
    can carry. It admits nothing by itself: ``admits_invite`` and ``require_account_admission`` apply it to one
    invitation, which must also be bound to its recipient's address."""
    reasons: list[str] = []
    if settings.REGISTRATION_MODE != "invite_only":
        reasons.append(REGISTRATION_NOT_INVITE_ONLY)
    if not settings.LEGAL_INVITED_COHORT_ENABLED:
        reasons.append(INVITED_COHORT_DISABLED)
    if _configured_cohort() is None:
        reasons.append(INVITED_COHORT_UNSET)
    return Capability(available=not reasons, reasons=reasons)


def invited_cohort() -> str | None:
    """The one cohort the exception admits while it is available, else None. Callers read it where they decide, never
    from an answer an earlier unit or the browser held."""
    return _configured_cohort() if invited_cohort_readiness()["available"] else None


def is_invited_cohort_available() -> bool:
    return invited_cohort() is not None


def admits_invite(cohort: str | None, email: str | None) -> bool:
    """Whether an invitation with this stored cohort and address binding may open an account now: any while collection
    is available, as before the exception; otherwise only one bound to an address whose cohort is exactly the
    exception's. The check before an invitation is minted, re-issued or mailed; where an account is created,
    ``require_account_admission`` decides and the redemption repeats the test on the invitation's row."""
    if is_collection_available():
        return True
    configured = invited_cohort()
    return configured is not None and bool(email) and cohort == configured


def require_account_admission(*, invited: bool) -> str | None:
    """What admits a new account now, at the account services' boundary: None while collection is available (every
    path as before the exception), else the invited cohort, which admits an invited account only; the caller's
    redemption then requires the invitation's row to be bound to the account's address and in that cohort
    (``invite_service.redeem_invite``). Raises ``CollectionUnavailable`` when neither admits it."""
    if is_collection_available():
        return None
    cohort = invited_cohort()
    if cohort is None or not invited:
        raise CollectionUnavailable(COLLECTION_UNAVAILABLE_MESSAGE)
    return cohort


def invitation_email_readiness() -> Capability:
    """Whether a requested beta invitation may be emailed now, and what holds it.

    Each condition is one the controls need: collection or the invited-cohort exception, since the link must be
    redeemable (a send also needs its own link admitted: ``is_invitation_email_available_for``); the operator's
    switch, which stands for the founder's permission policy and the approved canary; the provider key; and a webhook
    secret the signature check can use, without which bounces and complaints cannot be authenticated, so they could
    not suppress later sends. The admin router and the sender both check it; neither trusts the browser's copy.
    """
    reasons: list[str] = []
    if not (is_collection_available() or is_invited_cohort_available()):
        reasons.append(COLLECTION_UNAVAILABLE)
    if not settings.LEGAL_INVITATION_EMAIL_ENABLED:
        reasons.append(INVITATION_EMAIL_DISABLED)
    if not resend_service.is_configured():
        reasons.append(PROVIDER_UNCONFIGURED)
    if signing_key(settings.RESEND_WEBHOOK_SECRET) is None:
        reasons.append(PROVIDER_FEEDBACK_UNVERIFIED)
    return Capability(available=not reasons, reasons=reasons)


def is_invitation_email_available() -> bool:
    return invitation_email_readiness()["available"]


def is_invitation_email_available_for(cohort: str | None, email: str | None) -> bool:
    """Whether the invitation with this cohort, bound to ``email``, may be emailed now: the capability, and a link its
    recipient may redeem (``admits_invite``)."""
    return is_invitation_email_available() and admits_invite(cohort, email)


def require_collection_available() -> None:
    if not is_collection_available():
        raise CollectionUnavailable(COLLECTION_UNAVAILABLE_MESSAGE)


def is_checkout_available() -> bool:
    """New checkout remains closed until the offer/assent and deletion-intent protocol lands."""
    return False


def is_marketing_available() -> bool:
    """General promotion (the waitlist's referral update, any campaign) remains closed: the beta's requested
    invitations are their own capability (``invitation_email_readiness``), and their controls cover them alone."""
    return False
