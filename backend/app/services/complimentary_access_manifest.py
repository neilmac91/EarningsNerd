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
            raise ValueError("must be printable text without surrounding spaces")
        return value

    @model_validator(mode="after")
    def _distinct_accounts(self):
        ids = [account.account_id for account in self.accounts]
        if len(set(ids)) != len(ids):
            raise ValueError("names an account id more than once")
        fingerprints = [account.email_sha256 for account in self.accounts]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("names an address fingerprint more than once")
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


def _describe(error: dict) -> str:
    place = ".".join(
        str(part) if isinstance(part, int) or part in _NAMED_KEYS else "<unexpected key>" for part in error["loc"]
    )
    return f"{place or 'manifest'}: {error['msg']}"


def load_manifest(raw: bytes) -> tuple[Manifest, str]:
    """Parse a manifest's JSON strictly (no unknown keys, no coerced types) and return it with its digest. Raises
    :class:`ManifestError` naming each fault's place and kind; no input value enters the message."""
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
