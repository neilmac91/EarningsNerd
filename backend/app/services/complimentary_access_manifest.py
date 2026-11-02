"""The private manifest a complimentary Pro grant or revoke runs from (PB-02), and the checks that need no database.

This module imports nothing from the application but pydantic, so the operator can fingerprint addresses and check
a manifest on their own machine with no settings and no database (``scripts/complimentary_access.py fingerprint``
and ``check``). The manifest itself never enters the repository: it names real accounts
(``docs/ops/complimentary-access.md``, "The manifest").
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

# The cap: active grants across every cohort, and the most accounts one manifest may name.
MAX_ACTIVE_GRANTS = 20
# A grant's review date falls after the day it is applied and at most this many days later.
MAX_REVIEW_DAYS = 366

_COHORT_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_RUNNER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,79}$"
# Manifest keys a fault may name; any other key is reported as unexpected without its spelling, since a malformed
# manifest could carry an address as a key.
_NAMED_KEYS = frozenset({
    "action", "cohort", "reason", "review_on", "operator_account_id", "accounts", "account_id", "email_sha256",
    "grant", "revoke",
})


class ManifestError(Exception):
    """The manifest is not one the operator command runs. ``problems`` names each fault by its place and kind, never
    by the value that failed, so the message is safe for a public log."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class ManifestAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    account_id: int = Field(gt=0)
    # SHA-256 of the account's address as accounts store it (:func:`email_fingerprint`).
    email_sha256: str = Field(pattern=_SHA256_PATTERN)


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cohort: str = Field(pattern=_COHORT_PATTERN)
    reason: str = Field(min_length=3, max_length=200)
    operator_account_id: int = Field(gt=0)
    accounts: list[ManifestAccount] = Field(min_length=1, max_length=MAX_ACTIVE_GRANTS)

    @field_validator("reason")
    @classmethod
    def _plain_reason(cls, value: str) -> str:
        if value != value.strip() or not value.isprintable():
            raise PydanticCustomError("reason_not_plain", "reason is not plain text")
        return value

    @model_validator(mode="after")
    def _distinct_accounts(self):
        ids = [account.account_id for account in self.accounts]
        if len(set(ids)) != len(ids):
            raise PydanticCustomError("repeated_account_id", "an account id repeats")
        fingerprints = [account.email_sha256 for account in self.accounts]
        if len(set(fingerprints)) != len(fingerprints):
            raise PydanticCustomError("repeated_fingerprint", "an address fingerprint repeats")
        return self


class GrantManifest(_Manifest):
    action: Literal["grant"]
    # The operator's review or end date for these grants. Nothing expires on it: the readout counts grants past it,
    # and the operator revokes them (docs/ops/complimentary-access.md, "End date").
    review_on: date


class RevokeManifest(_Manifest):
    action: Literal["revoke"]


Manifest = Union[GrantManifest, RevokeManifest]
_MANIFEST = TypeAdapter(Annotated[Manifest, Field(discriminator="action")])


def email_fingerprint(email: str) -> str:
    """SHA-256 of an address as accounts store it: registration and the social sign-ins keep ``strip().lower()`` of
    it, so the operator's fingerprint of the address a tester gave matches the stored one's."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def manifest_digest(manifest: Manifest) -> str:
    """SHA-256 of the manifest's canonical JSON (sorted keys, accounts in their order): the dry run reports it, and
    the apply runs only the manifest it names."""
    canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


# Each fault's words, by its error type: pydantic's, or this module's own (``PydanticCustomError``). A fault's message
# is never read, since pydantic's can quote the input (a discriminator's names the tag it found, whatever its type),
# so a report carries only these words and a place built from ``_NAMED_KEYS`` and list positions. A type outside this
# table reads "is not valid". Gate: the fault cases in tests/unit/test_complimentary_access_service.py and
# tests/unit/test_complimentary_access_script.py, each planting an address and an id.
_FAULTS = {
    "reason_not_plain": "must be printable text without surrounding spaces",
    "repeated_account_id": "names an account id more than once",
    "repeated_fingerprint": "names an address fingerprint more than once",
    "union_tag_invalid": "must be grant or revoke",
    "union_tag_not_found": "must be grant or revoke",
    "missing": "is required",
    "extra_forbidden": "is not a manifest key",
    "string_type": "must be a string",
    "string_pattern_mismatch": "does not match its format",
    "string_too_short": "is too short",
    "string_too_long": "is too long",
    "int_type": "must be an integer",
    "int_parsing": "must be an integer",
    "greater_than": "must be a positive integer",
    "date_type": "must be a date (YYYY-MM-DD)",
    "date_parsing": "must be a date (YYYY-MM-DD)",
    "date_from_datetime_parsing": "must be a date (YYYY-MM-DD)",
    "list_type": "must be a list",
    "too_short": "must name at least one account",
    "too_long": f"names more than {MAX_ACTIVE_GRANTS} accounts",
    "model_type": "must be an object",
    "model_attributes_type": "must be an object",
    "dict_type": "must be an object",
    "literal_error": "is not a known value",
    "json_invalid": "is not valid JSON",
    "json_type": "is not valid JSON",
}


def _describe(error: dict) -> str:
    place = ".".join(
        str(part) if isinstance(part, int) or part in _NAMED_KEYS else "<unexpected key>" for part in error["loc"]
    )
    return f"{place or 'manifest'}: {_FAULTS.get(error['type'], 'is not valid')}"


class _RepeatedKey(Exception):
    pass


def _refuse_repeated_keys(raw: bytes) -> None:
    """A JSON object that names a key twice keeps its last value under every parser here, so a hand-edited manifest
    whose first lines say ``grant`` could run as a revoke, or a second ``accounts`` replace the first: refuse it. The
    fault names no key, since a malformed manifest could carry an address as one. Text that is not JSON is left to
    the strict parse after, which words its fault from its type."""

    def pairs(items: list) -> dict:
        if len({key for key, _ in items}) != len(items):
            raise _RepeatedKey()
        return dict(items)

    try:
        json.loads(raw, object_pairs_hook=pairs)
    except _RepeatedKey:
        raise ManifestError(["manifest: names a key twice in one object"]) from None
    except (ValueError, RecursionError):
        return


def load_manifest(raw: bytes) -> tuple[Manifest, str]:
    """Parse a manifest's JSON strictly (no unknown keys, no repeated keys, no coerced types) and return it with its
    digest. Raises :class:`ManifestError` naming each fault's place and kind; no input value enters the message."""
    _refuse_repeated_keys(raw)
    try:
        manifest = _MANIFEST.validate_json(raw)
    except ValidationError as exc:
        raise ManifestError([_describe(error) for error in exc.errors(include_input=False, include_url=False)]) from None
    return manifest, manifest_digest(manifest)


def check_review_window(manifest: Manifest, today: date) -> None:
    """A grant's review date falls after ``today`` (UTC) and at most :data:`MAX_REVIEW_DAYS` later."""
    if isinstance(manifest, GrantManifest) and not today < manifest.review_on <= today + timedelta(days=MAX_REVIEW_DAYS):
        raise ManifestError([f"review_on: must fall after today and at most {MAX_REVIEW_DAYS} days later"])


def check_runner_label(runner: Optional[str]) -> None:
    """The run's provenance label (an Ops run id, ``local``) is short plain text, so the audit row carries no
    free-form input."""
    if runner is not None and not re.fullmatch(_RUNNER_PATTERN, runner):
        raise ManifestError(["runner: must be 1-80 letters, digits or :._/- and start with a letter or digit"])
