from fastapi import APIRouter, HTTPException, Depends, status, Request, Response, Query, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import urlencode
import asyncio
import hashlib
import hmac
import json
import secrets
import logging

import httpx
import jwt

from app.database import get_db
from app.models import InviteCode, User, OAuthAccount, OAuthState
from app.config import settings
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.pwned_passwords import is_password_pwned
from app.services.turnstile import enforce_turnstile
from app.utils.text import has_control_characters
from app.services import audit_service, invite_service, login_lockout, refresh_token_service
from app.services.oauth_verify import _verify_apple_id_token, _verify_google_id_token
from app.services.password_utils import (
    _DUMMY_PASSWORD_HASH,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.services.refresh_token_service import (
    revoke_all_for_user,
    RefreshTokenError,
    RefreshTokenReuseError,
)
from app.services.posthog_client import (
    EVENT_INVITE_REDEEMED,
    EVENT_SIGNUP_COMPLETED,
    EVENT_TRIAL_STARTED,
    capture_event,
)

try:  # Sentry is an optional dependency (mirrors main.py / users.py); fall back to a no-op.
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

LOGIN_LIMITER = RateLimiter(limit=10, window_seconds=60)
REGISTER_LIMITER = RateLimiter(limit=5, window_seconds=60)
RESET_REQUEST_LIMITER = RateLimiter(limit=3, window_seconds=3600)   # 3/hr per email
RESEND_VERIFY_LIMITER = RateLimiter(limit=3, window_seconds=3600)   # 3/hr per email
# Second tier for the email-scoped reset/verify limits above: a per-IP cap across ALL emails, so a
# single IP can't spray reset/verification mail to thousands of different addresses (Resend cost +
# domain-reputation abuse). The per-email limiters stop bombing ONE victim; this stops fan-out.
RESET_RESEND_IP_LIMITER = RateLimiter(limit=20, window_seconds=3600)  # 20/hr per IP, all emails
# OAuth starts persist a state row (always for Apple, for an invited Google sign-up): bound the
# unauthenticated writers per IP. Sized for a person retrying a sign-in, not a script.
OAUTH_START_LIMITER = RateLimiter(limit=20, window_seconds=60)
# Per-account failed-login lockout is now durable + anti-enumeration (services/login_lockout,
# keyed on the email hash and backed by the DB), replacing the old in-memory RateLimiter here.

EMAIL_VERIFY_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1

# Google/Apple OAuth FLOW endpoints (the redirect + Google token-exchange run in this router). The
# JWKS fetch + id-token verification moved to app.services.oauth_verify (roadmap S3) and are
# re-imported below so the callbacks still call them by name.
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# Google: holds the state itself (SameSite=Lax; the callback is a same-site GET redirect).
_OAUTH_STATE_COOKIE = "oauth_state"
# Apple: holds an HMAC of the state (SameSite=None; the callback is a cross-site form_post).
_APPLE_STATE_COOKIE = "apple_oauth_state"
_OAUTH_STATE_MAX_AGE = 600  # 10 minutes

# Apple authentication uses the id_token delivered directly in Apple's form_post callback
# (response_type="code id_token"), so no authorization-code exchange / ES256 client secret is
# required — only Apple's JWKS for signature checks (handled in oauth_verify).
_APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = Field(None, max_length=100)
    # Closed-beta magic-link token. Required only when REGISTRATION_MODE="invite_only".
    invite_code: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: Optional[str]) -> Optional[str]:
        # Mirrors users.ProfileUpdate: trimmed, empty clears the name; control characters rejected.
        if value is None:
            return None
        value = value.strip()
        if has_control_characters(value):
            raise ValueError("Name must not contain control characters.")
        return value or None


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class Token(BaseModel):
    access_token: str
    token_type: str


class MessageResponse(BaseModel):
    message: str


class OAuthStartRequest(BaseModel):
    """Body of ``POST /api/auth/{google,apple}/start``. The invite travels in the body, never in a
    URL: request logs record query strings, and the raw token is a live single-use credential."""
    invite: Optional[str] = Field(None, max_length=128)


class RefreshRequest(BaseModel):
    # Optional body fallback for non-browser clients; browsers use the HttpOnly cookie.
    refresh_token: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class ChangePasswordRequest(BaseModel):
    # `current_password` is required to CHANGE an existing password; it may be omitted by
    # OAuth-only users SETTING a password for the first time (they're already authenticated).
    current_password: Optional[str] = None
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


# ─── Token helpers ──────────────────────────────────────────────────────────────

def _generate_token() -> tuple[str, str]:
    """Return (raw_token_to_email, sha256_hash_to_store). Never store the raw token."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        **data,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": uuid4().hex,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# Durable, non-credential marker that a session exists, read by the Next.js edge middleware
# (frontend/middleware.ts) to gate protected routes. Scoped to the parent domain + "/" and given
# the refresh-token lifetime, so the route guard does NOT bounce a logged-in user every time the
# short-lived (30-min) access token rotates. Carries no credential value — real authentication is
# still the HttpOnly access/refresh tokens validated on every request. Keep this name in sync with
# the literal in frontend/middleware.ts (pinned by a regression test on both sides).
SESSION_PRESENCE_COOKIE = "en_session"


def _set_session_presence_cookie(response: Response) -> None:
    response.set_cookie(
        key=SESSION_PRESENCE_COOKIE,
        value="1",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _clear_session_presence_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_PRESENCE_COOKIE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    # (Re)issue the durable session-presence marker alongside every access token, so the edge
    # middleware sees the session for its full lifetime — not just the 30-min access window.
    _set_session_presence_cookie(response)


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    _clear_session_presence_cookie(response)


# Refresh cookie is scoped to the auth path so it is only ever sent to /api/auth/* —
# it never rides along with ordinary API requests, shrinking its exposure surface.
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path=REFRESH_COOKIE_PATH,
    )


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _hashed_client_ip(request: Request) -> Optional[str]:
    """Keyed SHA-256 of the client IP for privacy-preserving audit logs (never store raw IPs).

    Peppered with SECRET_KEY: a bare SHA-256 of an IPv4 is trivially reversible (the whole ~4.2B
    address space is precomputable), so the secret pepper is what actually makes it non-reversible.
    """
    ip = _client_ip(request)
    if not ip:
        return None
    return hashlib.sha256(f"{ip}:{settings.SECRET_KEY}".encode("utf-8")).hexdigest()


def issue_session(
    db: Session,
    user: User,
    response: Response,
    request: Request,
    *,
    refresh_token: Optional[str] = None,
    commit: bool = True,
) -> str:
    """Issue a full session on ``response``: set the access + presence cookies and the refresh cookie.

    The single mint point for the login paths. By default a NEW refresh token is minted and committed
    (login, change-password, OAuth callbacks) through ``refresh_token_service.mint_refresh_token``.
    Pass ``refresh_token=`` with ``commit=False`` when the caller already rotated + committed one (the
    ``/refresh`` endpoint). The mint can raise ``IntegrityError`` on a concurrent OAuth first-login,
    so callers that need the OAuth conflict redirect wrap this in their own try/except; every other
    caller lets it propagate. Returns the raw access token (body responses echo it).
    """
    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(response, access_token)
    if refresh_token is None:
        refresh_token = refresh_token_service.mint_refresh_token(
            db,
            user,
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
            commit=commit,
        )
    _set_refresh_cookie(response, refresh_token)
    return access_token


def _get_token_from_request(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request,
) -> Optional[str]:
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    return cookie_token


def _lookup_auth_user(db: Session, email: str) -> Optional[User]:
    # Pool checkout can wait. Keep it off the event loop so other requests can
    # finish and run their request-owned Session cleanup, returning pool slots.
    return db.query(User).filter(User.email == email).first()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _get_token_from_request(credentials, request)
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "sub", "iat", "iss", "aud"]},
            leeway=settings.JWT_LEEWAY_SECONDS,
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = await run_in_threadpool(_lookup_auth_user, db, email)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Attribute Sentry errors on this request to the authenticated user + beta cohort. Id only —
    # no email/PII, so send_default_pii=False is respected. No-op if Sentry isn't installed/configured.
    if sentry_sdk is not None:
        try:
            sentry_sdk.set_user({"id": str(user.id)})
            sentry_sdk.set_tag("beta", bool(getattr(user, "is_beta", False)))
        except Exception:  # pragma: no cover - defensive: monitoring never breaks auth
            pass

    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    token = _get_token_from_request(credentials, request)
    if not token:
        return None

    try:
        if not token or not isinstance(token, str) or len(token.strip()) == 0:
            return None

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "sub", "iat", "iss", "aud"]},
            leeway=settings.JWT_LEEWAY_SECONDS,
        )
        email: str = payload.get("sub")
        if email is None:
            return None
    except (jwt.PyJWTError, HTTPException, Exception) as e:
        logger.warning(f"Optional auth failed: {e.__class__.__name__} - {e}")
        return None

    try:
        user = await run_in_threadpool(_lookup_auth_user, db, email)
        if user and not user.is_active:
            logger.warning(f"Optional auth: user id={user.id} is inactive")
            return None
        return user
    except Exception as e:
        logger.error(f"Database error during optional auth: {e.__class__.__name__} - {e}")
        return None


# ─── Email helper (graceful in dev when Resend is not configured) ──────────────

async def _send_verification_email_safe(db: Session, user: User) -> None:
    """Generate + persist a verification token and email the link.
    Falls back to logging the link when Resend is unconfigured (dev)."""
    raw_token, hashed = _generate_token()
    user.email_verification_token = hashed
    user.email_verification_expires = datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFY_EXPIRY_HOURS)
    db.commit()

    link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    try:
        from app.services.email_service import send_verification_email
        await send_verification_email(to_email=user.email, name=user.full_name, verification_link=link)
    except Exception as e:
        # Only log the token-bearing link in local dev (log access -> account takeover otherwise).
        link_note = f"; link: {link}" if settings.ENVIRONMENT == "development" else ""
        logger.error(f"Verification email NOT sent to user id={user.id}: {e.__class__.__name__}: {e}{link_note}")


async def _send_account_exists_email_safe(user: User) -> None:
    """Tell the real account owner that someone tried to register with their email.

    This is how the existing-email branch of register stays opaque: the HTTP response is
    identical to a new signup, and only the inbox owner learns the account already exists.
    Best-effort — email failures must not change the (opaque) response."""
    try:
        from app.services.email_service import send_account_exists_email
        await send_account_exists_email(
            to_email=user.email,
            name=user.full_name,
            login_link=f"{settings.FRONTEND_URL}/login",
            reset_link=f"{settings.FRONTEND_URL}/forgot-password",
        )
    except Exception as e:
        logger.warning(f"Account-exists email not sent: {e.__class__.__name__}: {e}")


async def _send_oauth_linked_email_safe(user: User, provider: str) -> None:
    """Notify a user that a social identity was linked to their existing account.

    Best-effort: a federated identity attaching to a pre-existing account is exactly the event
    a victim would want to hear about if it wasn't them, so we surface it — but email failures
    must never break the login itself.
    """
    try:
        from app.services.email_service import send_oauth_linked_email
        await send_oauth_linked_email(to_email=user.email, name=user.full_name, provider=provider)
    except Exception as e:
        logger.warning(f"OAuth-linked notification not sent: {e.__class__.__name__}: {e}")


# ─── Endpoints ──────────────────────────────────────────────────────────────────

# Identical opaque response for every registration attempt — new email, existing email, or a
# concurrent-create race — so the endpoint never reveals whether an account exists
# (anti-enumeration). Differentiation happens only out-of-band, in the recipient's inbox.
_REGISTER_OPAQUE = {
    "message": "Thanks! Check your email for a link to finish setting up your account."
}


class RegistrationConfig(BaseModel):
    """Public read of the signup gate. `mode` mirrors settings.REGISTRATION_MODE; `beta_promo_enabled`
    says whether the closed-beta 100%-off promo is configured (STRIPE_BETA_PROMO_CODE_ID), i.e.
    whether an invited beta member actually gets Pro at $0."""

    mode: str
    beta_promo_enabled: bool


@router.get("/registration", response_model=RegistrationConfig)
async def get_registration_config(response: Response):
    """Unauthenticated, cacheable read of the registration gate.

    The marketing landing page renders its account CTAs ("Create a free account" vs "Request an
    invite") and the "Free for beta members" pricing line from this answer, so flipping
    REGISTRATION_MODE on the service flips the public copy without a frontend redeploy. Nothing
    here is secret: /register already answers "A valid invite is required" in invite-only mode.
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    return RegistrationConfig(
        mode=settings.REGISTRATION_MODE,
        beta_promo_enabled=bool(settings.STRIPE_BETA_PROMO_CODE_ID),
    )


@router.post("/register", response_model=MessageResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new user (verify-first, anti-enumeration).

    Always returns the same opaque message and never sets a session here:
    - New email → create the (unverified) account and email a verification link.
    - Existing email → email the owner that someone tried to sign up (no account created).
    The HTTP response is byte-identical in both cases, so probing /register cannot enumerate
    accounts. The user finishes via the email link, or by signing in with the password they
    just chose (login does not require verification).
    """
    enforce_rate_limit(
        request,
        REGISTER_LIMITER,
        "register",
        error_detail="Too many registration attempts. Please try again in a minute.",
    )
    await enforce_turnstile(request)  # no-op unless Turnstile is configured

    # Closed-beta gate. When invite-only, require a valid, unexpired, unused invite BEFORE any
    # account work. It rejects uniformly regardless of email, so it is not an enumeration vector;
    # the email-existence anti-enumeration (opaque response + bcrypt timing) is preserved below for
    # the valid-invite path. In "public" mode the invite is ignored and nothing changes.
    invite = None
    if settings.REGISTRATION_MODE == "invite_only":
        invite = invite_service.validate_invite(db, user_data.invite_code, user_data.email)
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A valid invite is required to register.",
            )

    # Reject breached passwords (HaveIBeenPwned, k-anonymity). Independent of email existence so
    # it isn't an enumeration vector; fails open if HIBP is unreachable.
    if await is_password_pwned(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach. Please choose a different password.",
        )

    # Always pay the bcrypt cost, even for an existing email, so response timing doesn't reveal
    # whether the account is new (hash + insert) vs. existing (no insert) — closes the timing oracle.
    hashed_password = await asyncio.to_thread(get_password_hash, user_data.password)

    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        # Don't reveal existence in the response; alert the real owner out-of-band instead.
        await _send_account_exists_email_safe(existing_user)
        return _REGISTER_OPAQUE

    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        email_verified=False,
    )
    db.add(user)
    try:
        db.flush()
        # Closed beta: consume the (already-validated) single-use invite in the SAME transaction as
        # the insert and tag the user beta-eligible, so the 100%-off promo applies at checkout. A
        # lost redemption race rolls the account back too (the invite's single-use invariant holds),
        # and a failed insert never burns an invite.
        if invite is not None:
            if not invite_service.redeem_invite(db, invite, user, commit=False):
                db.rollback()
                return _REGISTER_OPAQUE
            user.is_beta = True
        db.commit()
        db.refresh(user)
    except IntegrityError:
        # Lost a concurrent-create race for the same email — stay opaque (treat as existing).
        db.rollback()
        return _REGISTER_OPAQUE
    redeemed = invite is not None

    # Reverse trial is NOT granted at registration: the email is still unverified here, so granting
    # no-card Pro now would hand full features to a disposable/unverified address (repeatable for
    # free). It is granted on email verification instead (see verify_email), so a real, verified
    # inbox is required. NB before enabling REVERSE_TRIAL_ENABLED in prod, also add a
    # one-trial-per-identity guard (a hashed-IP / verified-email record, or require a card so
    # Stripe's own trial dedup applies) — verification raises the bar but doesn't alone stop an
    # attacker cycling many disposable-but-verifiable addresses.

    await _send_verification_email_safe(db, user)
    audit_service.log_register(db, user.id, user.email, ip_address=_hashed_client_ip(request))

    # Closed-beta activation funnel (best-effort; telemetry must never break registration). Keyed on
    # str(user.id) so it stitches with the frontend, which identifies on String(user.id). No PII
    # (e.g. email) is sent as a property.
    try:
        if redeemed:
            capture_event(
                str(user.id), EVENT_INVITE_REDEEMED, {"email_bound": invite.email is not None}
            )
        capture_event(
            str(user.id),
            EVENT_SIGNUP_COMPLETED,
            {"is_beta": bool(user.is_beta), "invited": invite is not None},
        )
        # EVENT_TRIAL_STARTED now fires in verify_email, where the reverse trial is actually granted.
    except Exception:  # pragma: no cover - defensive: telemetry never blocks signup
        logger.warning("Signup funnel telemetry failed for user %s", user.id, exc_info=True)

    return _REGISTER_OPAQUE


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Login user"""
    enforce_rate_limit(
        request,
        LOGIN_LIMITER,
        "login",
        error_detail="Too many login attempts. Please try again in a minute.",
    )
    await enforce_turnstile(request)  # no-op unless Turnstile is configured
    # Durable per-account lockout: bounds distributed brute-force/spray against one account across
    # many IPs, holds across instances/restarts, and is keyed on the email hash so a non-existent
    # address locks the same as a real one (no 429-vs-401 enumeration). Peek before bcrypt.
    lock_seconds = login_lockout.seconds_until_unlock(db, user_data.email)
    if lock_seconds is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts for this account. Please try again later.",
            headers={"Retry-After": str(lock_seconds)},
        )

    user = db.query(User).filter(User.email == user_data.email).first()
    hashed_ip = _hashed_client_ip(request)

    # Always run bcrypt — against the real hash if we have one, else a fixed dummy — so the
    # response timing is the same whether or not the email exists (no timing oracle). Offloaded
    # to a worker thread so the ~250ms hash doesn't block the event loop under login load.
    password_ok = await asyncio.to_thread(
        verify_password,
        user_data.password,
        user.hashed_password if (user and user.hashed_password) else _DUMMY_PASSWORD_HASH,
    )

    # Collapse every failure mode (unknown email, wrong password, social-only account, inactive
    # account) into one generic 401 so the response never reveals whether an account exists or
    # is disabled — closing the account-enumeration channel that a distinct 403 opened.
    if not user or not user.hashed_password or not password_ok or not user.is_active:
        login_lockout.record_failure(db, user_data.email)  # counts against the email (existent or not)
        audit_service.log_failed_login(db, user_data.email, ip_address=hashed_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    login_lockout.clear_failures(db, user_data.email)  # a successful login resets the lockout
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    access_token = issue_session(db, user, response, request)
    audit_service.log_login_success(db, user.id, user.email, ip_address=hashed_ip)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db),
):
    """Exchange a valid refresh token for a new access token (and a rotated refresh token)."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token and body is not None:
        raw_token = body.refresh_token

    try:
        # Commits the rotation; on a replay it commits the chain revocation before re-raising.
        user, new_refresh_token = refresh_token_service.rotate_and_commit(
            db,
            raw_token,
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
    except RefreshTokenReuseError as exc:
        _clear_refresh_cookie(response)
        _clear_auth_cookie(response)
        logger.warning(f"Refresh reuse detected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RefreshTokenError as exc:
        _clear_refresh_cookie(response)
        _clear_auth_cookie(response)
        logger.info(f"Refresh rejected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = issue_session(db, user, response, request, refresh_token=new_refresh_token, commit=False)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """Verify a user's email address using the single-use token from the verification email."""
    hashed = _hash_token(payload.token)
    now = datetime.now(timezone.utc)

    user = db.query(User).filter(User.email_verification_token == hashed).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link.")
    if user.email_verification_expires and user.email_verification_expires < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link has expired. Request a new one.")

    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    db.commit()

    # Grant the reverse trial only now, on verification — so no-card Pro requires a real, verified
    # inbox rather than being handed to any freshly-registered (unverified) address. Behind the flag
    # (default off), best-effort, and committed separately so a trial-grant failure can't undo the
    # verification. Skip entirely if the user already has active/trialing Pro — resolved via the
    # entitlements SSoT, not the is_pro mirror — so we neither duplicate-grant nor fire a spurious
    # "trial started" event. (start_reverse_trial is also internally idempotent.)
    if settings.REVERSE_TRIAL_ENABLED:
        from app.services.entitlements import is_pro_user
        from app.services.subscription_sync import start_reverse_trial
        if not is_pro_user(user):
            try:
                start_reverse_trial(db, user, settings.REVERSE_TRIAL_DAYS)
                db.commit()
            except Exception:
                db.rollback()
                logger.warning("Failed to start reverse trial for user %s on verify", user.id, exc_info=True)
            else:
                try:
                    capture_event(
                        str(user.id),
                        EVENT_TRIAL_STARTED,
                        {"source": "reverse_trial", "days": settings.REVERSE_TRIAL_DAYS},
                    )
                except Exception:
                    logger.warning("Trial-started telemetry failed for user %s", user.id, exc_info=True)
    return {"message": "Email verified. You can now use all features."}


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Resend the email verification link. Rate-limited to 3/hr per address + 20/hr per IP."""
    # Per-IP cap across all addresses (stops one IP spraying verification mail to many emails)...
    enforce_rate_limit(
        request, RESET_RESEND_IP_LIMITER, "resend-ip",
        error_detail="Too many resend requests. Please wait before trying again.",
    )
    # ...plus the per-email cap (email already normalized by the schema validator).
    enforce_rate_limit(
        request, RESEND_VERIFY_LIMITER, f"resend:{payload.email}",
        error_detail="Too many resend requests. Please wait before trying again.",
        include_client_ip=False,
    )
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return the same response (anti-enumeration)
    opaque = {"message": "If that email has an unverified account, a new verification link is on its way."}
    if not user or user.email_verified:
        return opaque

    await _send_verification_email_safe(db, user)
    return opaque


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request a password reset link. Rate-limited to 3/hr per email address + 20/hr per IP."""
    # Per-IP cap across all addresses (stops one IP spraying reset mail to many emails)...
    enforce_rate_limit(
        request, RESET_RESEND_IP_LIMITER, "reset-ip",
        error_detail="Too many reset requests. Please wait before trying again.",
    )
    # ...plus the per-email cap (email already normalized by the schema validator).
    enforce_rate_limit(
        request, RESET_REQUEST_LIMITER, f"reset:{payload.email}",
        error_detail="Too many reset requests. Please wait before trying again.",
        include_client_ip=False,
    )
    opaque = {"message": "If an account exists for that email, a password reset link is on its way."}

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password:
        # Unknown email, or a social-only account with no password — reveal nothing extra.
        return opaque

    raw_token, hashed = _generate_token()
    user.password_reset_token = hashed
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_EXPIRY_HOURS)
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    try:
        from app.services.email_service import send_password_reset_email
        await send_password_reset_email(to_email=user.email, name=user.full_name, reset_link=reset_link)
    except Exception as e:
        # Only log the token-bearing link in local dev (a logged reset link = account takeover).
        link_note = f"; link: {reset_link}" if settings.ENVIRONMENT == "development" else ""
        logger.error(f"Reset email NOT sent to user id={user.id}: {e.__class__.__name__}: {e}{link_note}")

    return opaque


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Set a new password using the single-use token from the reset email."""
    hashed = _hash_token(payload.token)
    now = datetime.now(timezone.utc)

    user = db.query(User).filter(User.password_reset_token == hashed).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.")
    if user.password_reset_expires and user.password_reset_expires < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link has expired. Request a new one.")

    if await is_password_pwned(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach. Please choose a different password.",
        )

    user.hashed_password = await asyncio.to_thread(get_password_hash, payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    # The user proved control of their inbox, so confirm the email too.
    user.email_verified = True
    # Reset is account recovery: revoke every existing session so a stolen/active refresh token
    # can't outlive the reset. The attacker is evicted; the legitimate owner logs in fresh.
    revoke_all_for_user(db, user.id)
    db.commit()
    return {"message": "Password updated. You can now log in with your new password."}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or change the signed-in user's password.

    - A user who already has a password must supply the correct ``current_password``.
    - An OAuth-only user (no password yet) may set one without a current password — this unlocks
      email/password sign-in alongside their Google/Apple logins.

    Applies the same strength + breached-password (HIBP) checks as registration/reset.
    """
    # Keyed per-user so a logged-in attacker can't brute-force the current password.
    enforce_rate_limit(
        request,
        LOGIN_LIMITER,
        f"change-password:{current_user.id}",
        error_detail="Too many password change attempts. Please try again later.",
        include_client_ip=False,  # per-account cap: an IP pool must not multiply it
    )
    if current_user.hashed_password:
        ok = await asyncio.to_thread(
            verify_password, payload.current_password or "", current_user.hashed_password
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect."
            )

    if await is_password_pwned(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach. Please choose a different password.",
        )

    current_user.hashed_password = await asyncio.to_thread(get_password_hash, payload.new_password)
    # A password change must evict every existing session (a stolen/old refresh token must not
    # survive it). Revoke all, then re-issue for THIS device so the acting user isn't logged out
    # moments later when their short-lived access token expires. No intermediate commit: the
    # password change, the revocation, and the new token are committed together by the single
    # db.commit() inside issue_session (called with the default commit=True), so a failure there
    # rolls the whole change back (no password-changed-but-500 inconsistency) and saves a commit
    # round-trip. This atomicity is the reason the pw-hash write above is NOT committed on its own.
    revoke_all_for_user(db, current_user.id)
    issue_session(db, current_user, response, request)
    return {"message": "Password updated."}


# ─── OAuth account creation + state (shared by Google and Apple) ────────────────

def _oauth_new_account_gate(
    db: Session, *, email: str, email_verified: bool, invite_code_hash: Optional[str]
) -> tuple[Optional[str], Optional[InviteCode]]:
    """Decide whether a social sign-in may create a NEW User (linking is decided by the callers).

    Returns ``(error_code, invite)``. ``error_code`` is None when creation may proceed, else the
    ``/login?error=`` code to redirect with: ``email_unverified`` when the provider has not verified
    the address (an unverified claim never seeds an account), ``invite_required`` when
    REGISTRATION_MODE is invite_only and the sign-in carries no valid invite. ``invite`` is the
    validated invite the caller must redeem in the SAME transaction as the insert (None in public
    mode). Mirrors the register() gate; tests/unit/test_oauth_invite_gate.py keeps every ``User(``
    construction in this module behind it.
    """
    if not email_verified:
        return "email_unverified", None
    if settings.REGISTRATION_MODE != "invite_only":
        return None, None
    invite = invite_service.validate_invite_hash(db, invite_code_hash, email)
    if invite is None:
        return "invite_required", None
    return None, invite


def _oauth_create_account(
    db: Session,
    *,
    provider: str,
    email: str,
    full_name: Optional[str],
    email_verified: bool,
    invite_code_hash: Optional[str],
) -> tuple[Optional[User], Optional[str]]:
    """Create the User for a first social sign-in, or say why not.

    Returns ``(user, None)`` with the row flushed but not committed (the caller's issue_session
    commits it together with the provider link and the session), or ``(None, error_code)`` after
    rolling back. When invite-only mode requires an invite it is consumed here, inside the same
    transaction, so a lost redemption race never leaves an account behind.
    """
    error_code, invite = _oauth_new_account_gate(
        db, email=email, email_verified=email_verified, invite_code_hash=invite_code_hash
    )
    if error_code:
        return None, error_code
    user = User(email=email, full_name=full_name, hashed_password=None, email_verified=email_verified)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # Lost a concurrent first-sign-in race for the same email.
        db.rollback()
        logger.warning("%s OAuth IntegrityError creating account", provider)
        return None, f"{provider}_account_conflict"
    if invite is not None:
        if not invite_service.redeem_invite(db, invite, user, commit=False):
            db.rollback()
            return None, "invite_required"
        user.is_beta = True
    return user, None


def _store_oauth_state(db: Session, state: str, nonce: str, invite_code_hash: Optional[str]) -> None:
    """Stage a single-use ``state`` row (10-minute TTL) after GC-ing expired rows; the caller commits
    (so the GET handler's write stays visible to tests/unit/test_read_only_get_endpoints.py).

    Apple always needs one (its form_post callback is checked against the row's nonce); Google only
    when the sign-in carries an invite, which rides on the row as its hash so the callback can
    validate and redeem it. Naive UTC throughout (see the OAuthState model) so the comparison is
    naive-vs-naive on both Postgres and SQLite.
    """
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)
    db.add(OAuthState(
        state=state,
        nonce=nonce,
        invite_code_hash=invite_code_hash,
        expires_at=now + timedelta(seconds=_OAUTH_STATE_MAX_AGE),
    ))


def _consume_oauth_state(db: Session, state: str) -> Optional[tuple[str, Optional[str]]]:
    """Delete the row for ``state`` and return its ``(nonce, invite_code_hash)``, or None when the
    state is unknown or expired (an expired row is deleted too). Single-use by construction."""
    row = db.query(OAuthState).filter_by(state=state).first()
    if row is None:
        return None
    live = row.expires_at >= datetime.utcnow()
    nonce, invite_code_hash = row.nonce, row.invite_code_hash
    db.delete(row)
    db.commit()
    return (nonce, invite_code_hash) if live else None


def _apple_state_cookie_value(state: str) -> str:
    """HMAC-SHA256 of the Apple ``state`` keyed with SECRET_KEY: the browser-binding half of the
    callback's state check (the DB row is the single-use half)."""
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), state.encode("utf-8"), hashlib.sha256).hexdigest()


def _apple_redirect(url: str) -> RedirectResponse:
    """Redirect out of the Apple callback; the one-shot state-binding cookie is cleared either way."""
    redirect = RedirectResponse(url=url, status_code=302)
    redirect.delete_cookie(_APPLE_STATE_COOKIE, httponly=True, samesite="none", secure=True)
    return redirect


# ─── Google OAuth (OIDC via httpx — no extra dependency) ───────────────────────

def _live_invite_hash(db: Session, invite: Optional[str]) -> Optional[str]:
    """The hash of ``invite`` when it names a usable invite, else None: an OAuth start persists
    nothing for an unknown, revoked, used or expired token (the callback then sees no invite)."""
    if not invite:
        return None
    code_hash = invite_service.hash_invite_token(invite)
    return code_hash if invite_service.invite_hash_is_live(db, code_hash) else None


def _start_google(request: Request, db: Session, invite: Optional[str]) -> tuple[str, str]:
    """Rate limit, stage the state (with the invite's hash when the invite is live) and build
    Google's consent URL. Returns ``(url, state)``; the caller sets the state cookie."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google Sign-In is not configured.")
    enforce_rate_limit(
        request, OAUTH_START_LIMITER, "oauth-start",
        error_detail="Too many sign-in attempts. Please try again shortly.",
    )
    state = secrets.token_urlsafe(32)
    invite_code_hash = _live_invite_hash(db, invite)
    if invite_code_hash is not None:
        # The nonce column is NOT NULL but unused for Google (no OIDC nonce in this flow).
        _store_oauth_state(db, state, secrets.token_urlsafe(32), invite_code_hash)
        db.commit()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}", state


def _set_google_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        _OAUTH_STATE_COOKIE, state, httponly=True, samesite="lax",
        max_age=_OAUTH_STATE_MAX_AGE, secure=settings.COOKIE_SECURE,
    )


@router.get("/google")
async def google_login(request: Request, db: Session = Depends(get_db)):
    """Redirect the browser to Google's consent screen (plain sign-in: no invite, nothing persisted).

    An invited sign-up starts through ``POST /api/auth/google/start`` instead, so the raw invite
    token never appears in a request URL (request logs record query strings).
    """
    url, state = _start_google(request, db, None)
    redirect = RedirectResponse(url=url, status_code=302)
    _set_google_state_cookie(redirect, state)
    return redirect


@router.post("/google/start")
async def google_start(body: OAuthStartRequest, request: Request, db: Session = Depends(get_db)):
    """Start Google sign-in for the browser to follow: returns ``{"url": ...}`` and sets the state
    cookie. ``invite`` is the raw closed-beta token from the magic link, so an invited user can sign
    up with Google under REGISTRATION_MODE=invite_only: its hash is stored against the ``state`` and
    the callback validates + redeems it when it creates the account. Only the hash is stored, and
    only for an invite that is live; the start is rate limited per IP because it writes a row.
    """
    url, state = _start_google(request, db, body.invite)
    response = JSONResponse({"url": url})
    _set_google_state_cookie(response, state)
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Exchange Google's auth code, upsert the user, link the provider, issue a session."""
    frontend_url = settings.FRONTEND_URL

    if error:
        return RedirectResponse(f"{frontend_url}/login?error=google_denied", status_code=302)
    if not code or not state:
        return RedirectResponse(f"{frontend_url}/login?error=google_invalid", status_code=302)

    stored_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not stored_state or not secrets.compare_digest(stored_state, state):
        return RedirectResponse(f"{frontend_url}/login?error=oauth_state_mismatch", status_code=302)

    # An invited sign-up stored its invite hash against this state (google_login); plain sign-ins
    # have no row. Consumed up front so the row is single-use whatever happens next.
    consumed = _consume_oauth_state(db, state)
    invite_code_hash = consumed[1] if consumed else None

    # Exchange the authorization code for tokens, then cryptographically verify the id_token
    # (signature + audience + issuer) rather than trusting an access-token-authenticated
    # /userinfo response.
    try:
        async with httpx.AsyncClient(timeout=10.0) as hx:
            token_resp = await hx.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            google_id_token = token_resp.json().get("id_token")
            if not google_id_token:
                raise ValueError("no id_token in Google token response")
        claims = await _verify_google_id_token(google_id_token)
    except Exception as exc:
        logger.warning("Google OAuth exchange/verification failed: %s", exc.__class__.__name__)
        return RedirectResponse(f"{frontend_url}/login?error=google_token_failed", status_code=302)

    google_sub = claims.get("sub")
    email = (claims.get("email") or "").strip().lower() or None
    email_verified_by_google = bool(claims.get("email_verified", False))
    full_name = claims.get("name")

    if not google_sub or not email:
        return RedirectResponse(f"{frontend_url}/login?error=google_missing_claims", status_code=302)

    oauth_row = (
        db.query(OAuthAccount)
        .filter_by(provider="google", provider_account_id=google_sub)
        .first()
    )

    linked_existing = False
    if oauth_row:
        user = oauth_row.user
    else:
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            # Link to an existing account only when both sides have a verified email; otherwise a
            # new insert would hit the UNIQUE constraint.
            if not (existing.email_verified and email_verified_by_google):
                return RedirectResponse(
                    f"{frontend_url}/login?error=google_account_conflict", status_code=302
                )
            user = existing
            linked_existing = True
        else:
            user, error_code = _oauth_create_account(
                db,
                provider="google",
                email=email,
                full_name=full_name,
                email_verified=email_verified_by_google,
                invite_code_hash=invite_code_hash,
            )
            if user is None:
                return RedirectResponse(f"{frontend_url}/login?error={error_code}", status_code=302)
        db.add(OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=google_sub,
            provider_email=email,
        ))

    user.last_login_at = datetime.now(timezone.utc)

    redirect = RedirectResponse(url=frontend_url, status_code=302)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE)
    try:
        issue_session(db, user, redirect, request)
    except IntegrityError:
        db.rollback()
        logger.warning("Google OAuth IntegrityError for sub=%s", google_sub)
        return RedirectResponse(f"{frontend_url}/login?error=google_account_conflict", status_code=302)

    hashed_ip = _hashed_client_ip(request)
    audit_service.log_oauth_login(db, user.id, user.email, provider="google", ip_address=hashed_ip)
    if linked_existing:
        # Security-relevant: a federated identity was just attached to a pre-existing account.
        audit_service.log_oauth_linked(db, user.id, user.email, provider="google", ip_address=hashed_ip)
        await _send_oauth_linked_email_safe(user, "Google")
    return redirect


# ─── Apple Sign In (ES256 client secret, form_post callback, JWKS verification) ──

def _start_apple(request: Request, db: Session, invite: Optional[str]) -> tuple[str, str]:
    """Rate limit, stage the nonce row (with the invite's hash when the invite is live) and build
    Apple's consent URL. Returns ``(url, state)`` without committing; each caller commits the row
    before returning the URL and setting the browser-binding cookie."""
    if not settings.APPLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Apple Sign In is not configured.")
    enforce_rate_limit(
        request, OAUTH_START_LIMITER, "oauth-start",
        error_detail="Too many sign-in attempts. Please try again shortly.",
    )

    state = secrets.token_urlsafe(32)
    raw_nonce = secrets.token_urlsafe(32)
    _store_oauth_state(db, state, raw_nonce, _live_invite_hash(db, invite))

    # Send sha256(raw_nonce) so Apple stores it in id_token; we verify on callback.
    params = {
        "client_id": settings.APPLE_CLIENT_ID,
        "redirect_uri": settings.APPLE_REDIRECT_URI,
        "response_type": "code id_token",
        "scope": "name email",
        "response_mode": "form_post",
        "state": state,
        "nonce": hashlib.sha256(raw_nonce.encode()).hexdigest(),
    }
    return f"{_APPLE_AUTH_URL}?{urlencode(params)}", state


def _set_apple_state_cookie(response: Response, state: str) -> None:
    # Apple posts the callback cross-site, so this cookie is SameSite=None, which browsers accept
    # only together with Secure; it is Secure unconditionally (not COOKIE_SECURE) because Apple
    # requires an HTTPS redirect URI even locally (docs/auth/05_apple_signin_runbook.md, Part 3).
    # It binds the state to the browser that started the flow: the callback accepts a posted state
    # only together with this cookie, and the DB row makes it single-use.
    response.set_cookie(
        _APPLE_STATE_COOKIE, _apple_state_cookie_value(state), httponly=True, samesite="none",
        max_age=_OAUTH_STATE_MAX_AGE, secure=True,
    )


@router.get("/apple")
async def apple_login(request: Request, db: Session = Depends(get_db)):
    """Redirect the browser to Apple's consent screen (plain sign-in: no invite). An invited
    sign-up starts through ``POST /api/auth/apple/start`` so the token never rides in a URL."""
    url, state = _start_apple(request, db, None)
    db.commit()
    redirect = RedirectResponse(url=url, status_code=302)
    _set_apple_state_cookie(redirect, state)
    return redirect


@router.post("/apple/start")
async def apple_start(body: OAuthStartRequest, request: Request, db: Session = Depends(get_db)):
    """Start Sign in with Apple for the browser to follow: ``{"url": ...}`` plus the binding cookie
    (``invite``: as for google_start)."""
    url, state = _start_apple(request, db, body.invite)
    db.commit()
    response = JSONResponse({"url": url})
    _set_apple_state_cookie(response, state)
    return response


@router.post("/apple/callback")
async def apple_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    id_token: Optional[str] = Form(None),
    user: Optional[str] = Form(None),
    error: Optional[str] = Form(None),
):
    """Handle Apple's form_post callback: verify id_token, upsert user, issue session."""
    frontend_url = settings.FRONTEND_URL

    if error:
        return _apple_redirect(f"{frontend_url}/login?error=apple_denied")
    if not state or not id_token:
        return _apple_redirect(f"{frontend_url}/login?error=apple_invalid")

    # State check, both halves: the SameSite=None cookie set at /apple must carry this state's HMAC
    # (browser binding; checked first so a post without it leaves the row untouched), then the DB
    # row is consumed for the nonce + optional invite (single use).
    bound = request.cookies.get(_APPLE_STATE_COOKIE)
    expected = _apple_state_cookie_value(state)
    if not bound or not secrets.compare_digest(bound.encode("utf-8"), expected.encode("utf-8")):
        return _apple_redirect(f"{frontend_url}/login?error=oauth_state_mismatch")
    consumed = _consume_oauth_state(db, state)
    if consumed is None:
        return _apple_redirect(f"{frontend_url}/login?error=oauth_state_mismatch")
    raw_nonce, invite_code_hash = consumed

    # Verify Apple's id_token
    try:
        claims = await _verify_apple_id_token(id_token, raw_nonce)
    except Exception as exc:
        logger.warning("Apple id_token verification failed: %s", exc)
        return _apple_redirect(f"{frontend_url}/login?error=apple_invalid")

    apple_sub = claims.get("sub")
    if not apple_sub:
        return _apple_redirect(f"{frontend_url}/login?error=apple_missing_claims")

    email = (claims.get("email") or "").strip().lower() or None
    email_verified_by_apple = str(claims.get("email_verified", "false")).lower() == "true"

    # Parse name from user JSON (Apple only sends this on first authorization)
    full_name: Optional[str] = None
    if user:
        try:
            user_data = json.loads(user)
            name_obj = user_data.get("name", {}) or {}
            first = (name_obj.get("firstName") or "").strip()
            last = (name_obj.get("lastName") or "").strip()
            full_name = " ".join(filter(None, [first, last])) or None
        except (ValueError, AttributeError, KeyError):
            pass

    # Resolve user: existing oauth link → existing verified account → new account
    oauth_row = db.query(OAuthAccount).filter_by(
        provider="apple", provider_account_id=apple_sub
    ).first()

    linked_existing = False
    if oauth_row:
        user_obj = oauth_row.user
        if full_name and not user_obj.full_name:
            user_obj.full_name = full_name
    else:
        if not email:
            # No email and no existing link — can't create an account
            return _apple_redirect(f"{frontend_url}/login?error=apple_missing_claims")

        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            if existing.email_verified and email_verified_by_apple:
                user_obj = existing
                linked_existing = True
                if full_name and not user_obj.full_name:
                    user_obj.full_name = full_name
            else:
                # Email exists but can't be safely linked (unverified on either side).
                # Attempting a new insert would hit the UNIQUE constraint.
                return _apple_redirect(f"{frontend_url}/login?error=apple_account_conflict")
        else:
            user_obj, error_code = _oauth_create_account(
                db,
                provider="apple",
                email=email,
                full_name=full_name,
                email_verified=email_verified_by_apple,
                invite_code_hash=invite_code_hash,
            )
            if user_obj is None:
                return _apple_redirect(f"{frontend_url}/login?error={error_code}")

        db.add(OAuthAccount(
            user_id=user_obj.id,
            provider="apple",
            provider_account_id=apple_sub,
            provider_email=email,
        ))

    user_obj.last_login_at = datetime.now(timezone.utc)
    redirect = _apple_redirect(frontend_url)
    try:
        issue_session(db, user_obj, redirect, request)
    except IntegrityError:
        db.rollback()
        logger.warning("Apple OAuth IntegrityError for sub=%s", apple_sub)
        return _apple_redirect(f"{frontend_url}/login?error=apple_account_conflict")

    hashed_ip = _hashed_client_ip(request)
    audit_service.log_oauth_login(db, user_obj.id, user_obj.email, provider="apple", ip_address=hashed_ip)
    if linked_existing:
        audit_service.log_oauth_linked(db, user_obj.id, user_obj.email, provider="apple", ip_address=hashed_ip)
        await _send_oauth_linked_email_safe(user_obj, "Apple")
    return redirect


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_pro": current_user.is_pro,
        "is_beta": current_user.is_beta,
        "is_admin": current_user.is_admin,
        "email_verified": current_user.email_verified,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Revoke the refresh token (if present) and clear both auth cookies."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    refresh_token_service.revoke_and_commit(db, raw_token)
    _clear_auth_cookie(response)
    _clear_refresh_cookie(response)
    if current_user:
        audit_service.log_logout(db, current_user.id, current_user.email, ip_address=_hashed_client_ip(request))
    return {"status": "success"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke every refresh token for the user (sign out all devices) and clear this session."""
    revoked = refresh_token_service.revoke_all_and_commit(db, current_user.id)
    _clear_auth_cookie(response)
    _clear_refresh_cookie(response)
    audit_service.log_logout(db, current_user.id, current_user.email, ip_address=_hashed_client_ip(request))
    return {"status": "success", "sessions_revoked": revoked}


@router.get("/connections")
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the user's sign-in methods: whether a password is set + any linked OAuth providers."""
    rows = db.query(OAuthAccount).filter(OAuthAccount.user_id == current_user.id).all()
    return {
        "has_password": bool(current_user.hashed_password),
        "providers": [
            {
                "provider": r.provider,
                "provider_email": r.provider_email,
                "linked_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.delete("/connections/{provider}")
async def unlink_connection(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlink an OAuth provider — but never remove the user's only remaining sign-in method."""
    provider = provider.lower().strip()
    if provider not in {"google", "apple"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown provider.")

    rows = db.query(OAuthAccount).filter(OAuthAccount.user_id == current_user.id).all()
    target = next((r for r in rows if r.provider == provider), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That provider is not linked to your account."
        )

    # Lockout guard: after removing this provider the user must keep at least one credential
    # (a password or another linked provider).
    remaining = (1 if current_user.hashed_password else 0) + (len(rows) - 1)
    if remaining < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't remove your only sign-in method. Set a password first, then unlink.",
        )

    db.delete(target)
    db.commit()
    audit_service.create_audit_log(
        db,
        action="oauth_unlinked",
        user_id=current_user.id,
        user_email=current_user.email,
        entity_type="user",
        ip_address=_hashed_client_ip(request),
        details={"provider": provider},
    )
    return {"status": "success", "unlinked": provider}
