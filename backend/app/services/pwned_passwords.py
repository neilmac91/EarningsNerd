"""Breached-password screening via the HaveIBeenPwned Pwned Passwords range API.

Uses k-anonymity: only the first 5 hex chars of the password's SHA-1 hash are sent to HIBP,
which returns every suffix sharing that prefix; the match is done locally. The full hash and
the password itself never leave this process.

Fails open: any network/parse error (or a disabled flag) returns ``False`` so a third-party
outage can never block sign-ups or password resets.
"""
from __future__ import annotations

import hashlib
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"
_TIMEOUT_SECONDS = 2.5


async def is_password_pwned(password: str) -> bool:
    """Return True only if ``password`` is known to appear in public breach corpora.

    One lookup of the whole password, which is what a new hash keys on: it is Argon2id over every byte
    (``password_utils.get_password_hash``, E97), so a breached text that shares only its first 72 bytes
    does not open the account and is not screened as it was while new hashes were bcrypt.

    Returns False when the check is disabled, the password is empty, or the lookup fails for any
    reason (fail-open).
    """
    if not settings.PWNED_PASSWORD_CHECK_ENABLED or not password:
        return False
    return bool(await _is_listed(password))


async def _is_listed(password: str) -> bool | None:
    """One range-API lookup for ``password``: True if listed, False if not, None if the lookup
    failed (the caller fails open)."""
    # SHA-1 is mandated by the HIBP range API (the k-anonymity protocol hashes with SHA-1); it is
    # NOT used as a security primitive here — the protection comes from matching against the breach
    # corpus, not from SHA-1's collision resistance. usedforsecurity=False documents that intent and
    # satisfies bandit B324.
    sha1 = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as hx:
            resp = await hx.get(
                f"{_HIBP_RANGE_URL}{prefix}",
                headers={
                    # Add-Padding returns decoy hashes (count 0) so response size can't reveal
                    # how many real matches share the prefix.
                    "Add-Padding": "true",
                    "User-Agent": "EarningsNerd-PasswordCheck",
                },
            )
            resp.raise_for_status()

        for line in resp.text.splitlines():
            hash_suffix, _, count = line.partition(":")
            if hash_suffix.strip().upper() == suffix:
                try:
                    return int(count.strip()) > 0  # count 0 == padding, not a real breach hit
                except ValueError:
                    return True
        return False
    except Exception as exc:  # fail open — never block on a third-party dependency
        logger.warning(
            "Pwned-password check unavailable (%s); allowing password", exc.__class__.__name__
        )
        return None
