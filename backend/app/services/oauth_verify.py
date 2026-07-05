"""OAuth id-token verification (Google + Apple) — JWKS fetch + signature/claims checks.

Extracted from ``app.routers.auth`` (roadmap S3) so the identity-crypto lives outside the HTTP
router. Behavior-preserving: the functions and their module-level JWKS caches/constants moved
verbatim. The router re-imports ``_verify_google_id_token`` / ``_verify_apple_id_token`` and calls
them by name (so a test patching ``auth._verify_apple_id_token`` still intercepts the callback);
tests that patch the *internals* (``jwt`` / ``_get_apple_jwks``) target THIS module.

Verification takes only the id_token (and, for Apple, the raw nonce) — never app-user data.
"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
import time

import httpx
from jose import JWTError, jwt

from app.config import settings

# Google OIDC: identity is taken from the cryptographically-verified id_token, not the userinfo
# endpoint, so a forged/replayed access token cannot impersonate a user.
_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

# Apple Sign In: authentication uses the id_token delivered directly in Apple's form_post callback
# (response_type="code id_token"), so only the JWKS for signature checks is required.
_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

_google_jwks_cache: dict | None = None
_google_jwks_cache_expires: float = 0.0
_google_jwks_lock: asyncio.Lock | None = None

_apple_jwks_cache: dict | None = None
_apple_jwks_cache_expires: float = 0.0
_apple_jwks_lock: asyncio.Lock | None = None


def _get_google_jwks_lock() -> asyncio.Lock:
    # Lazy init so the lock binds to the running event loop, not import time (the codebase's
    # event-loop-safety pattern — see the two-tier cache). The None-check + assignment is atomic
    # under asyncio (no await between them), so concurrent first-callers can't create two locks.
    global _google_jwks_lock
    if _google_jwks_lock is None:
        _google_jwks_lock = asyncio.Lock()
    return _google_jwks_lock


def _get_apple_jwks_lock() -> asyncio.Lock:
    global _apple_jwks_lock
    if _apple_jwks_lock is None:
        _apple_jwks_lock = asyncio.Lock()
    return _apple_jwks_lock


async def _get_apple_jwks() -> dict:
    """Fetch (or return 1-hour-cached) Apple JWKS for id_token verification.

    A lazily-initialized lock serializes the cold-cache fetch so concurrent logins don't stampede
    Apple's JWKS endpoint; the second check inside the lock returns what the winning fetch cached.
    """
    global _apple_jwks_cache, _apple_jwks_cache_expires
    if _apple_jwks_cache and time.time() < _apple_jwks_cache_expires:
        return _apple_jwks_cache
    async with _get_apple_jwks_lock():
        if _apple_jwks_cache and time.time() < _apple_jwks_cache_expires:
            return _apple_jwks_cache
        async with httpx.AsyncClient(timeout=10.0) as hx:
            resp = await hx.get(_APPLE_JWKS_URL)
            resp.raise_for_status()
            _apple_jwks_cache = resp.json()
            _apple_jwks_cache_expires = time.time() + 3600
    return _apple_jwks_cache


async def _verify_apple_id_token(id_token: str, raw_nonce: str) -> dict:
    """Verify Apple id_token against Apple's JWKS; check nonce.

    python-jose does not reliably auto-select a key from a JWKS dict, so we
    extract the kid from the unverified header and select the matching key
    explicitly before calling jwt.decode.
    """
    jwks = await _get_apple_jwks()
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
        public_key = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == kid), None
        )
        if not public_key:
            raise ValueError("Matching key not found in Apple JWKS")
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
            # Require the claims we rely on to be present (defense-in-depth; the RS256 signature
            # against Apple's JWKS is the real gate). nonce is additionally checked below. Leeway
            # absorbs clock skew between Apple's servers and ours, same as our own token decode.
            options={"require": ["exp", "aud", "iss", "sub", "nonce"], "leeway": settings.JWT_LEEWAY_SECONDS},
        )
    except JWTError as exc:
        raise ValueError(f"Apple id_token invalid: {exc}")

    # Nonce binding is mandatory: we always send sha256(raw_nonce), so a
    # compliant id_token always echoes it back. A missing or mismatched nonce
    # means the token isn't bound to this auth request (replay/injection) — reject.
    token_nonce = claims.get("nonce")
    expected = hashlib.sha256(raw_nonce.encode()).hexdigest()
    if not token_nonce or not secrets.compare_digest(token_nonce, expected):
        raise ValueError("Apple id_token nonce missing or mismatched")

    return claims


async def _get_google_jwks() -> dict:
    """Fetch (or return 1-hour-cached) Google JWKS for id_token verification.

    Lock-serialized cold-cache fetch (see ``_get_apple_jwks``) so concurrent logins don't stampede
    Google's JWKS endpoint.
    """
    global _google_jwks_cache, _google_jwks_cache_expires
    if _google_jwks_cache and time.time() < _google_jwks_cache_expires:
        return _google_jwks_cache
    async with _get_google_jwks_lock():
        if _google_jwks_cache and time.time() < _google_jwks_cache_expires:
            return _google_jwks_cache
        async with httpx.AsyncClient(timeout=10.0) as hx:
            resp = await hx.get(_GOOGLE_JWKS_URL)
            resp.raise_for_status()
            _google_jwks_cache = resp.json()
            _google_jwks_cache_expires = time.time() + 3600
    return _google_jwks_cache


async def _verify_google_id_token(id_token: str) -> dict:
    """Verify a Google OIDC id_token and return its claims.

    Checks the RS256 signature against Google's JWKS, that the audience is our client_id, that
    the token is unexpired, and that the issuer is Google. This replaces trusting the /userinfo
    response, which only proves possession of an access token, not that it was minted for us.
    """
    jwks = await _get_google_jwks()
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
        public_key = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == kid), None
        )
        if not public_key:
            raise ValueError("Matching key not found in Google JWKS")
        # Google issues id_tokens with iss "https://accounts.google.com" or "accounts.google.com";
        # validate the issuer manually against both rather than via jose's single-string check.
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            options={"require": ["exp", "aud", "sub", "iss"]},
        )
    except JWTError as exc:
        raise ValueError(f"Google id_token invalid: {exc}")

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise ValueError("Google id_token has unexpected issuer")

    return claims
