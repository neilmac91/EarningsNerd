"""Availability of new collection and commercial activity, separate from existing-user rights.

Configuration supplies an operator-approved public notice; it cannot certify compliance. Sales
and promotion deliberately have no enabling switch until their consent/lifecycle controls exist.
"""
from __future__ import annotations

from typing import TypedDict

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import settings

TERMS_VERSION = "2026-10-24"
ELIGIBILITY_VERSION = "2026-10-24"
COLLECTION_UNAVAILABLE_MESSAGE = "New registrations and submissions are temporarily unavailable."

_EMAIL = TypeAdapter(EmailStr)
_PLACEHOLDERS = frozenset({"tbd", "todo", "unknown", "placeholder", "not published", "n/a"})


class CollectionUnavailable(Exception):
    """The caller must not collect new prospect/account information."""


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


def require_collection_available() -> None:
    if not is_collection_available():
        raise CollectionUnavailable(COLLECTION_UNAVAILABLE_MESSAGE)


def is_checkout_available() -> bool:
    """New checkout remains closed until the offer/assent and deletion-intent protocol lands."""
    return False


def is_marketing_available() -> bool:
    """Promotion remains closed until permission, unsubscribe and suppression are implemented."""
    return False
