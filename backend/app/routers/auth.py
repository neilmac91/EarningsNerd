from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, status, Request, Response, Query, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import urlencode
import hashlib
import hmac
import json
import secrets
import logging

import httpx
import jwt

from app.database import get_db
from app.dependencies import resolve_current_user_or_none
from app.models import InviteCode, User
from app.config import settings
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.pwned_passwords import is_password_pwned
from app.services.turnstile import enforce_turnstile
from app.schemas.account_agreement import AccountAgreementInput
from app.services.account_agreement_service import AcceptedAccountAgreement, accept_current_agreement
from app.services.legal_readiness_service import (
    CollectionUnavailable, is_checkout_available, require_collection_available,
)
from app.utils.text import has_control_characters
from app.services import (
    account_mail_service,
    audit_service,
    auth_account_service,
    filing_list_service,
    invite_service,
    login_lockout,
    oauth_account_service,
    refresh_token_service,
)
from app.services.durable_tasks import AccountMail
from app.services.oauth_verify import _verify_apple_id_token, _verify_google_id_token
from app.services.password_utils import (
    _DUMMY_PASSWORD_HASH,
    bound_checked_password,
    get_password_hash,
    in_password_thread,
    validate_password_strength,
    verify_password,
)
from app.services.refresh_token_service import RefreshTokenError, RefreshTokenReuseError
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
# Third tier, one budget per process for the account mail both routes queue (F60): the two limits above
# bound each caller, not all callers together, and an IPv6 block holds enough addresses to pass the per-IP
# one at will. Every request that passes them queues a task on the shared one-at-a-time Cloud Tasks queue
# (0.2 dispatches/s, about 720 an hour), so this caps account mail at 60 an hour per API instance, 120 at
# the service's two, and a flood costs that hour's reset and verification mail instead of the whole queue.
# The same 429 answers every address.
ACCOUNT_MAIL_LIMITER = RateLimiter(limit=60, window_seconds=3600)
# POST /refresh per IP (E96). A browser single-flights its refresh per tab (``ensureRefreshed``), so N open tabs
# waking at once send N; the cap leaves room for a burst of tabs behind one shared address, and a client looping
# refreshes is refused within the minute. Checked before the rotation takes a connection or the users row lock.
REFRESH_LIMITER = RateLimiter(limit=60, window_seconds=60)
# Every OAuth start persists a single-use state row: bound the
# unauthenticated writers per IP. Sized for a person retrying a sign-in, not a script.
OAUTH_START_LIMITER = RateLimiter(limit=20, window_seconds=60)
# Per-account failed-login lockout is now durable + anti-enumeration (services/login_lockout,
# keyed on the email hash and backed by the DB), replacing the old in-memory RateLimiter here.

# Google/Apple OAuth FLOW endpoints (the redirect + Google token-exchange run in this router). The
# JWKS fetch + id-token verification moved to app.services.oauth_verify (roadmap S3) and are
# re-imported below so the callbacks still call them by name.
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# Google: holds the state itself (SameSite=Lax; the callback is a same-site GET redirect).
_OAUTH_STATE_COOKIE = "oauth_state"
# Apple: holds an HMAC of the state (SameSite=None; the callback is a cross-site form_post).
_APPLE_STATE_COOKIE = "apple_oauth_state"
_OAUTH_STATE_MAX_AGE = oauth_account_service.OAUTH_STATE_TTL_SECONDS  # 10 minutes, as the state row

# Apple authentication uses the id_token delivered directly in Apple's form_post callback
# (response_type="code id_token"), so no authorization-code exchange / ES256 client secret is
# required — only Apple's JWKS for signature checks (handled in oauth_verify).
_APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class UserCreate(AccountAgreementInput):
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

    @field_validator("password")
    @classmethod
    def bound_password(cls, value: str) -> str:
        return bound_checked_password(value)


class Token(BaseModel):
    access_token: str
    token_type: str


class MessageResponse(BaseModel):
    message: str


class OAuthStartRequest(BaseModel):
    """Body of ``POST /api/auth/{google,apple}/start``. The invite travels in the body, never in a
    URL: request logs record query strings, and the raw token is a live single-use credential."""
    invite: Optional[str] = Field(None, max_length=128)
    # Omitted together means an existing-account login. A signup must confirm every field;
    # strict booleans refuse strings/numbers, and the shared input validates current versions.
    adult_eligible: StrictBool | None = None
    terms_accepted: StrictBool | None = None
    terms_version: StrictStr | None = None
    eligibility_version: StrictStr | None = None

    @model_validator(mode="after")
    def validate_signup_agreement(self) -> "OAuthStartRequest":
        fields = set(AccountAgreementInput.model_fields)
        if self.model_fields_set & fields:
            AccountAgreementInput.model_validate(self.model_dump(include=fields))
        return self

    def accepted_agreement(self) -> AcceptedAccountAgreement | None:
        return accept_current_agreement() if self.adult_eligible is True else None


def _require_new_collection() -> None:
    try:
        require_collection_available()
    except CollectionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class RefreshRequest(BaseModel):
    # Optional body fallback for non-browser clients; browsers use the HttpOnly cookie.
    refresh_token: Optional[str] = None


class LogoutAllRequest(BaseModel):
    """The account the tab shows (E157 (2)). A tab learns of another tab's login only through /me (E29 (3)), so a
    stale tab posts with the cookies of the account the browser holds now; naming its own lets the route refuse to end
    that account's sessions, and to end its own from the refresh cookie once the access token has lapsed. Optional, so
    a page loaded before the field logs out as before."""

    account_id: Optional[StrictInt] = None


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

    @field_validator("current_password")
    @classmethod
    def bound_current_password(cls, value: Optional[str]) -> Optional[str]:
        return bound_checked_password(value)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


# ─── Token helpers ──────────────────────────────────────────────────────────────

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
    email: Optional[str] = None,
) -> str:
    """Issue a full session on ``response``: set the access + presence cookies and the refresh cookie.

    The single session-issue point for the login paths. By default a NEW refresh token is minted and
    committed (change-password) through ``refresh_token_service.mint_refresh_token``; an
    ``IntegrityError`` there propagates. Pass ``refresh_token=`` with ``commit=False`` when the caller
    already minted or rotated and committed one: the password login, whose
    ``auth_account_service.record_password_login`` mints under the account's lock, the ``/refresh``
    endpoint, and the OAuth callbacks, whose ``oauth_account_service.mint_oauth_refresh_token`` turns a
    concurrent first-login ``IntegrityError`` into the conflict redirect. Returns the raw access token
    (body responses echo it). A caller that passes ``refresh_token=`` has committed, which expired
    ``user``, so it must pass ``email=`` too, the address it read before that commit (the password login,
    ``/refresh`` and the OAuth callbacks do): the access token then reads nothing after the commit, so no
    failure there can turn a committed sign-in into an error (E121). Without it this raises ``TypeError``,
    which every route test of such a caller then fails on.
    """
    if refresh_token is not None and email is None:
        raise TypeError("issue_session(refresh_token=...) needs email=, the address read before the commit")
    access_token = create_access_token(data={"sub": email if email is not None else user.email})
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


def _not_logged_in() -> HTTPException:
    """The refusal of a request no live credential authenticates: ``get_current_user``'s, and the logout of every
    session's when no credential it reads names a user (E157 (2))."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="You are not logged in.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    credentials_exception = _not_logged_in()
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

    # Pool checkout can wait. Keep it off the event loop so other requests can
    # finish and run their request-owned Session cleanup, returning pool slots.
    user = await run_in_threadpool(auth_account_service.find_user_by_email, db, email)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive. Contact support with any questions.",
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
        # Off the event loop for the same pool-progress reason as get_current_user.
        user = await run_in_threadpool(auth_account_service.find_user_by_email, db, email)
        if user and not user.is_active:
            logger.warning(f"Optional auth: user id={user.id} is inactive")
            return None
        return user
    except Exception as e:
        logger.error(f"Database error during optional auth: {e.__class__.__name__} - {e}")
        return None


# ─── Email helpers (graceful in dev when Resend is not configured) ─────────────
# account_mail_service mails the reset and verification links, and logs a failed send by the
# exception's class alone (with the link in local development only).

async def _queue_account_mail(
    request: Request, background: BackgroundTasks, mail: AccountMail, email: str,
) -> None:
    """Hand an account mail to work after the response, the same way whatever the address holds.

    The request neither looks the account up, issues a token nor sends: those happen after the answer,
    in ``account_mail_service.send_account_mail``, which mails only an eligible account (F60). So an
    address with an account and one without take one path here, and the answer's timing no longer tells
    them apart. The caller has already taken its per-IP and per-address limits; this takes the
    process-wide ``ACCOUNT_MAIL_LIMITER`` first. With durable tasks the handoff is the ``account_mail``
    task, and one Cloud Tasks does not confirm raises ``TaskUnavailable``, which main.py answers 503 for
    any address; without, a background task in this process, as the other after-response work does when
    the flag is off. ``test_durable_task_payloads_server_owned.py`` pins who calls this and in what order.
    """
    enforce_rate_limit(
        request, ACCOUNT_MAIL_LIMITER, "account-mail",
        error_detail="Too many requests right now. Try again later.",
        include_client_ip=False,
    )
    if settings.DURABLE_TASKS_ENABLED:
        await account_mail_service.queue_account_mail(mail, email)
    else:
        background.add_task(account_mail_service.send_account_mail_after_response, mail, email)


async def _send_account_exists_email_safe(recipient: "_Recipient") -> None:
    """Tell the real account owner that someone tried to register with their email.

    This is how the existing-email branch of register stays opaque: the HTTP response is
    identical to a new signup, and only the inbox owner learns the account already exists.
    Best-effort — email failures must not change the (opaque) response. Takes the address and name the
    route's unit read, so the send runs after its release with no session (E121)."""
    try:
        from app.services.email_service import send_account_exists_email
        await send_account_exists_email(
            to_email=recipient.email,
            name=recipient.full_name,
            login_link=f"{settings.FRONTEND_URL}/login",
            reset_link=f"{settings.FRONTEND_URL}/forgot-password",
        )
    except Exception as e:
        # The class alone, as the reset and verification mail log theirs: a provider's error text can
        # quote the request, the recipient's address among it.
        logger.warning("Account-exists email not sent: %s", e.__class__.__name__)


@dataclass(frozen=True)
class _Recipient:
    """An account's address and name, read in a unit, for a notice sent after its release."""

    email: str
    full_name: Optional[str]


@dataclass(frozen=True)
class _Registered:
    """What register's account unit leaves the route once it has released its session: the existing account's
    address and name for the account-exists notice, or the new account's id, address and beta tag, or neither when the
    insert or the invite's redemption was refused."""

    exists: Optional[_Recipient] = None
    created: Optional[tuple[int, str, bool]] = None


@dataclass(frozen=True)
class _SignedIn:
    """What an OAuth callback's sign-in unit leaves the route once it has released its session: the account's
    address and name for the linked-account notice, read before the unit's commits expired them (E121)."""

    email: str
    full_name: Optional[str]
    linked_existing: bool


async def _send_oauth_linked_email_safe(user: _SignedIn, provider: str) -> None:
    """Notify a user that a social identity was linked to their existing account.

    Best-effort: a federated identity attaching to a pre-existing account is exactly the event
    a victim would want to hear about if it wasn't them, so we surface it — but email failures
    must never break the login itself.
    """
    try:
        from app.services.email_service import send_oauth_linked_email
        await send_oauth_linked_email(to_email=user.email, name=user.full_name, provider=provider)
    except Exception as e:
        logger.warning("OAuth-linked notification not sent: %s", e.__class__.__name__)


# ─── Endpoints ──────────────────────────────────────────────────────────────────

# Identical opaque response for every registration attempt — new email, existing email, or a
# concurrent-create race — so the endpoint never reveals whether an account exists
# (anti-enumeration). Differentiation happens only out-of-band, in the recipient's inbox.
_REGISTER_OPAQUE = {
    "message": "Check your email for a link to finish setting up your account."
}


class RegistrationConfig(BaseModel):
    """Public read of the signup gate. `mode` mirrors settings.REGISTRATION_MODE; `beta_promo_enabled`
    says whether the closed-beta 100%-off promo is configured AND checkout is available. A
    configured but unavailable offer must not produce a public promise of Pro at $0."""

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
        beta_promo_enabled=bool(settings.STRIPE_BETA_PROMO_CODE_ID) and is_checkout_available(),
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

    Two units in the thread pool, each released before what follows it (E121): the invite's read, before the
    breached-password check and the hash, and the account's lookup, its insert with the invite's redemption, and the
    register audit row, before either mail. So no pooled connection is out across the check, the hash or a send, and no
    statement runs on the event loop. Both mails are sent with no session: the account-exists notice from the address
    and name the unit read, and the verification link through the account mails' own unit
    (``account_mail_service.send_account_mail_after_response``), which issues the token on a session of its own.
    """
    enforce_rate_limit(
        request,
        REGISTER_LIMITER,
        "register",
        error_detail="Too many registration attempts. Try again in a minute.",
    )
    _require_new_collection()
    await enforce_turnstile(request)  # no-op unless Turnstile is configured
    email, full_name, hashed_ip = user_data.email, user_data.full_name, _hashed_client_ip(request)

    # Closed-beta gate. When invite-only, require a valid, unexpired, unused invite BEFORE any
    # account work. It rejects uniformly regardless of email, so it is not an enumeration vector;
    # the email-existence anti-enumeration (opaque response + hashing timing) is preserved below for
    # the valid-invite path. In "public" mode the invite is ignored and nothing changes.
    invite: Optional[InviteCode] = None
    if settings.REGISTRATION_MODE == "invite_only":
        def read_invite() -> Optional[InviteCode]:
            # The release detaches the invite without expiring it: the redemption below reads only its id, and the
            # funnel event whether it names an address.
            try:
                return invite_service.validate_invite(db, user_data.invite_code, email)
            finally:
                filing_list_service.release_request_session(db)

        invite = await run_in_threadpool(read_invite)
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
            detail="This password has appeared in a known data breach. Choose a different one.",
        )

    # Always pay the hashing cost, even for an existing email, so response timing doesn't reveal
    # whether the account is new (hash + insert) vs. existing (no insert) — closes the timing oracle.
    hashed_password = await in_password_thread(get_password_hash, user_data.password)
    agreement = accept_current_agreement()

    def register_account() -> _Registered:
        try:
            existing_user = auth_account_service.find_user_by_email(db, email)
            if existing_user is not None:
                return _Registered(exists=_Recipient(existing_user.email, existing_user.full_name))
            # Inserts the account and, in the same transaction, redeems the validated invite (beta tag).
            user = auth_account_service.create_password_account(
                db,
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                invite=invite,
                agreement=agreement,
            )
            if user is None:
                # A refused invite redemption (redeemed or revoked since it validated) or a lost concurrent-create
                # race: stay opaque (rolled back).
                return _Registered()
            # Read before the audit row's commit expires the account.
            user_id, stored_email, is_beta = user.id, user.email, bool(user.is_beta)
            audit_service.log_register(db, user_id, stored_email, ip_address=hashed_ip)
            return _Registered(created=(user_id, stored_email, is_beta))
        finally:
            filing_list_service.release_request_session(db)

    try:
        registered = await run_in_threadpool(register_account)
    except CollectionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if registered.exists is not None:
        # Don't reveal existence in the response; alert the real owner out-of-band instead.
        await _send_account_exists_email_safe(registered.exists)
        return _REGISTER_OPAQUE
    if registered.created is None:
        return _REGISTER_OPAQUE
    user_id, stored_email, is_beta = registered.created

    # Reverse trial is NOT granted at registration: the email is still unverified here, so granting
    # no-card Pro now would hand full features to a disposable/unverified address (repeatable for
    # free). It is granted on email verification instead (see verify_email), so a real, verified
    # inbox is required. NB before enabling REVERSE_TRIAL_ENABLED in prod, also add a
    # one-trial-per-identity guard (a hashed-IP / verified-email record, or require a card so
    # Stripe's own trial dedup applies) — verification raises the bar but doesn't alone stop an
    # attacker cycling many disposable-but-verifiable addresses.

    await account_mail_service.send_account_mail_after_response("verification", stored_email)

    # Closed-beta activation funnel (best-effort; telemetry must never break registration). Keyed on
    # str(user.id) so it stitches with the frontend, which identifies on String(user.id). No PII
    # (e.g. email) is sent as a property.
    try:
        if invite is not None:
            capture_event(
                str(user_id), EVENT_INVITE_REDEEMED, {"email_bound": invite.email is not None}
            )
        capture_event(
            str(user_id),
            EVENT_SIGNUP_COMPLETED,
            {"is_beta": is_beta, "invited": invite is not None},
        )
        # EVENT_TRIAL_STARTED now fires in verify_email, where the reverse trial is actually granted.
    except Exception:  # pragma: no cover - defensive: telemetry never blocks signup
        logger.warning("Signup funnel telemetry failed for user %s", user_id, exc_info=True)

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
        error_detail="Too many login attempts. Try again in a minute.",
    )
    await enforce_turnstile(request)  # no-op unless Turnstile is configured
    email, hashed_ip = user_data.email, _hashed_client_ip(request)
    user_agent, ip = request.headers.get("user-agent"), _client_ip(request)

    def look_up() -> tuple[Optional[int], Optional[tuple[int, Optional[str], bool]]]:
        # One unit in the thread pool, released before the hash check, so no login holds a pool slot while it
        # hashes (lessons/ops-release-cached-filing-reads-before-yield.md).
        try:
            # Durable per-account lockout: bounds distributed brute-force/spray against one account
            # across many IPs, holds across instances/restarts, and is keyed on the email hash so a
            # non-existent address locks the same as a real one (no 429-vs-401 enumeration). Peek
            # before the hash check.
            lock_seconds = login_lockout.seconds_until_unlock(db, email)
            if lock_seconds is not None:
                return lock_seconds, None
            user = auth_account_service.find_user_by_email(db, email)
            return None, (user.id, user.hashed_password, user.is_active) if user else None
        finally:
            filing_list_service.release_request_session(db)

    lock_seconds, account = await run_in_threadpool(look_up)
    if lock_seconds is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts for this account. Try again later.",
            headers={"Retry-After": str(lock_seconds)},
        )
    user_id, verified_hash, is_active = account or (None, None, False)

    # Always run the hash check — against the real hash if we have one, else a fixed dummy — so the
    # request performs comparable expensive work to reduce timing differences. Argon2id and legacy bcrypt
    # checks can still differ; the gap is unmeasured on Cloud Run (password_utils). The password thread
    # keeps the check off the event loop under login load.
    password_ok = await in_password_thread(verify_password, user_data.password, verified_hash or _DUMMY_PASSWORD_HASH)

    def finish() -> Optional[str]:
        # One unit in the thread pool after the hash check, released before the route returns.
        try:
            if verified_hash and password_ok and is_active:
                # Under the account's lock, and only while the hash just verified is still its own (E121).
                login = auth_account_service.record_password_login(
                    db, user_id, verified_hash, email, user_agent=user_agent, ip=ip,
                )
                if login is not None:
                    # The address the service read before its commit: nothing after it reads the user (E121).
                    user, refresh_token, stored_email = login
                    access_token = issue_session(
                        db, user, response, request, refresh_token=refresh_token, commit=False, email=stored_email,
                    )
                    audit_service.log_login_success(db, user_id, stored_email, ip_address=hashed_ip)
                    return access_token
            login_lockout.record_failure(db, email)  # counts against the email (existent or not)
            audit_service.log_failed_login(db, email, ip_address=hashed_ip)
            return None
        finally:
            filing_list_service.release_request_session(db)

    access_token = await run_in_threadpool(finish)
    # Collapse every failure mode (unknown email, wrong password, social-only account, inactive
    # account, a password reset or change since the hash was read) into one generic 401 so the
    # response never reveals whether an account exists or is disabled — closing the
    # account-enumeration channel that a distinct 403 opened.
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db),
):
    """Exchange a valid refresh token for a new access token (and a rotated refresh token)."""
    enforce_rate_limit(
        request,
        REFRESH_LIMITER,
        "refresh",
        error_detail="Too many session refreshes. Try again in a minute.",
    )
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token and body is not None:
        raw_token = body.refresh_token
    user_agent, ip = request.headers.get("user-agent"), _client_ip(request)

    def rotate_and_issue() -> str:
        # One unit in the thread pool, released before the route returns: the rotation's checkout never
        # waits on the event loop (lessons/ops-release-cached-filing-reads-before-yield.md), and the access
        # token takes the address read before the rotation's commit, so nothing after that commit can fail it
        # (E121): the client would lose the rotated token, and its next refresh would replay the old one.
        try:
            # Commits the rotation; on a replay it commits the chain revocation before re-raising.
            user, new_refresh_token, email = refresh_token_service.rotate_and_commit(
                db, raw_token, user_agent=user_agent, ip=ip,
            )
            return issue_session(
                db, user, response, request, refresh_token=new_refresh_token, commit=False, email=email,
            )
        finally:
            filing_list_service.release_request_session(db)

    # A refusal sets no cookie, on purpose (E121). It cannot tell whether the cookies it refused are still the
    # browser's: the request carries the cookies of the moment it was sent, and a login in another tab, an OAuth
    # sign-in's redirect or another tab's refresh can have replaced them before this answer lands, so a deletion here
    # could end that newer session. With nothing newer set, the browser keeps the refused cookies, en_session included,
    # so the edge guard (frontend/middleware.ts) still lets it reach a protected page, whose /me read then finds no
    # session. The refusing tab ends the session it knew and clears the session marker every tab reads
    # (notifySessionLost, frontend/lib/api/session.ts); no tab then silently renews a newer login until a /me read
    # succeeds and marks it again (getCurrentUser). A kept refresh cookie that was rotated away meets the replay sweep
    # each time it is sent, which revokes that token's chain, the live tokens its rotations lead to; the account's other
    # sessions keep theirs (E96, refresh_token_service.rotate_refresh_token). Before E121 this route set deletions on
    # the injected Response and then raised; FastAPI answers an exception with a fresh response, so they never reached
    # the browser (tests/unit/test_raised_answers_carry_no_injected_headers.py pins that and refuses the form).
    try:
        access_token = await run_in_threadpool(rotate_and_issue)
    except RefreshTokenReuseError as exc:
        logger.warning(f"Refresh reuse detected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has ended. Log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RefreshTokenError as exc:
        logger.info(f"Refresh rejected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has ended. Log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"access_token": access_token, "token_type": "bearer"}


def _grant_reverse_trial_on_verify(db: Session, user: User, user_id: int) -> bool:
    """Grant the reverse trial to an account its verification just confirmed, in the verification's thread-pool
    unit, and say whether it was granted.

    Only now, on verification, so no-card Pro needs a real, verified inbox rather than any freshly registered
    (unverified) address. Committed on its own, after the verification's commit, and best-effort: its eligibility
    read, the grant, its commit and the discard of a failed grant are each caught and logged, so nothing here undoes
    the verification or turns its answer into an error (E121). An account that already has active or trialing Pro,
    resolved through ``entitlements.is_pro_user`` (the plan's one source, rule 4), is skipped, and a link's second
    post waits at the verification's row lock and is refused (``verify_email_token``), so neither a duplicate grant
    nor a spurious "trial started" event happens (``start_reverse_trial`` is idempotent too)."""
    from app.services.entitlements import is_pro_user

    try:
        if is_pro_user(user):
            return False
        auth_account_service.grant_reverse_trial(db, user, settings.REVERSE_TRIAL_DAYS)
    except Exception:
        try:
            auth_account_service.discard_reverse_trial(db)
        except Exception as discard_failure:
            # The class alone, as the account mails log theirs: a database error's text quotes its statement.
            logger.warning("Discarding a failed reverse trial for user %s failed: %s",
                           user_id, discard_failure.__class__.__name__)
        logger.warning("Failed to start reverse trial for user %s on verify", user_id, exc_info=True)
        return False
    return True


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """Verify a user's email address using the single-use token from the verification email.

    One unit in the thread pool, released before the route answers, verifies the address and, behind
    ``REVERSE_TRIAL_ENABLED`` (default off), grants the reverse trial in a commit of its own, so no statement,
    commit or read of the account its commit expired runs on the event loop (E121). The trial-started event is
    sent after the release."""
    def verify() -> Optional[int]:
        try:
            user, user_id = auth_account_service.verify_email_token(db, payload.token)
            if settings.REVERSE_TRIAL_ENABLED and _grant_reverse_trial_on_verify(db, user, user_id):
                return user_id
            return None
        finally:
            filing_list_service.release_request_session(db)

    try:
        trial_user_id = await run_in_threadpool(verify)
    except auth_account_service.AccountTokenInvalidError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link.") from None
    except auth_account_service.AccountTokenExpiredError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link has expired. Request a new one.") from None

    if trial_user_id is not None:
        try:
            capture_event(
                str(trial_user_id),
                EVENT_TRIAL_STARTED,
                {"source": "reverse_trial", "days": settings.REVERSE_TRIAL_DAYS},
            )
        except Exception:
            logger.warning("Trial-started telemetry failed for user %s", trial_user_id, exc_info=True)
    return {"message": "Email verified."}


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    background: BackgroundTasks,
):
    """Resend the email verification link. Rate-limited to 3/hr per address + 20/hr per IP, and
    with forgot-password to 60/hr per process (``ACCOUNT_MAIL_LIMITER``).

    Opaque in body and timing: every request within the limits queues the same mail and gets the same
    answer; only an unverified account is mailed, after the response (``_queue_account_mail``)."""
    # Per-IP cap across all addresses (stops one IP spraying verification mail to many emails)...
    enforce_rate_limit(
        request, RESET_RESEND_IP_LIMITER, "resend-ip",
        error_detail="Too many resend requests. Try again later.",
    )
    # ...plus the per-email cap (email already normalized by the schema validator).
    enforce_rate_limit(
        request, RESEND_VERIFY_LIMITER, f"resend:{payload.email}",
        error_detail="Too many resend requests. Try again later.",
        include_client_ip=False,
    )
    await _queue_account_mail(request, background, "verification", payload.email)
    # Always return the same response (anti-enumeration)
    return {"message": "If that email has an unverified account, a new verification link is on its way."}


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background: BackgroundTasks,
):
    """Request a password reset link. Rate-limited to 3/hr per email address + 20/hr per IP, and
    with resend-verification to 60/hr per process (``ACCOUNT_MAIL_LIMITER``).

    Opaque in body and timing: every request within the limits queues the same mail and gets the same
    answer; only an account with a password is mailed, after the response (``_queue_account_mail``)."""
    # Per-IP cap across all addresses (stops one IP spraying reset mail to many emails)...
    enforce_rate_limit(
        request, RESET_RESEND_IP_LIMITER, "reset-ip",
        error_detail="Too many reset requests. Try again later.",
    )
    # ...plus the per-email cap (email already normalized by the schema validator).
    enforce_rate_limit(
        request, RESET_REQUEST_LIMITER, f"reset:{payload.email}",
        error_detail="Too many reset requests. Try again later.",
        include_client_ip=False,
    )
    await _queue_account_mail(request, background, "password_reset", payload.email)
    return {"message": "If an account exists for that email, a password reset link is on its way."}


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Set a new password using the single-use token from the reset email.

    Two units in the thread pool, the token's account read and the reset, each released before what follows
    it, so the breached-password check and the hash hold no pooled connection and no statement or lock wait runs
    on the event loop (E121, lessons/ops-release-cached-filing-reads-before-yield.md)."""
    def find_account() -> int:
        try:
            return auth_account_service.find_password_reset_user(db, payload.token).id
        finally:
            filing_list_service.release_request_session(db)

    try:
        user_id = await run_in_threadpool(find_account)
    except auth_account_service.AccountTokenInvalidError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.") from None
    except auth_account_service.AccountTokenExpiredError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link has expired. Request a new one.") from None

    if await is_password_pwned(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach. Choose a different one.",
        )

    hashed_password = await in_password_thread(get_password_hash, payload.new_password)

    def reset() -> None:
        # Sets the password, burns the token, confirms the email (the user proved control of the inbox)
        # and revokes every session (account recovery evicts an attacker), in one commit, under the
        # account's users row lock (its revocation takes it before any token write).
        try:
            auth_account_service.complete_password_reset_by_id(db, user_id, hashed_password)
        finally:
            filing_list_service.release_request_session(db)

    try:
        await run_in_threadpool(reset)
    except auth_account_service.AccountTokenInvalidError:
        # The account was deleted while this request hashed; nothing was written.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.") from None
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

    Two units in the thread pool around the waits (E121): the auth lookup's read is released first, so no
    pooled connection is out while the current password is checked, the breached-password check runs or
    the new one is hashed; the change and this device's new session are then one unit, released before
    the route returns (lessons/ops-release-cached-filing-reads-before-yield.md).
    """
    # The release detaches the user without expiring it: the id, email and hash the lookup loaded stay
    # readable with no query, here and in the unit below.
    await run_in_threadpool(filing_list_service.release_request_session, db)
    # Keyed per-user so a logged-in attacker can't brute-force the current password.
    enforce_rate_limit(
        request,
        LOGIN_LIMITER,
        f"change-password:{current_user.id}",
        error_detail="Too many password change attempts. Try again later.",
        include_client_ip=False,  # per-account cap: an IP pool must not multiply it
    )
    verified_hash = current_user.hashed_password
    if verified_hash:
        ok = await in_password_thread(verify_password, payload.current_password or "", verified_hash)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect."
            )

    if await is_password_pwned(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach. Choose a different one.",
        )

    new_password_hash = await in_password_thread(get_password_hash, payload.new_password)

    def change() -> bool:
        # A password change must evict every existing session (a stolen/old refresh token must not
        # survive it). Revoke all, then re-issue for THIS device so the acting user isn't logged out
        # moments later when their short-lived access token expires. No intermediate commit:
        # stage_password_change only stages the new hash and the revocation, and the single commit
        # inside issue_session (refresh_token_service.mint_refresh_token, default commit=True) commits
        # them with the new token, so a failure there rolls the whole change back (no
        # password-changed-but-500 inconsistency) and saves a commit round-trip. Nothing after that
        # commit raises: the refresh cookie is set, and the release logs a failure instead.
        try:
            if not auth_account_service.stage_password_change(db, current_user, new_password_hash, verified_hash):
                return False
            issue_session(db, current_user, response, request)
            return True
        finally:
            filing_list_service.release_request_session(db)

    if not await run_in_threadpool(change):
        # A reset or another change committed while this request hashed (E121).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect."
        )
    return {"message": "Password updated."}


# ─── OAuth state binding (shared by Google and Apple) ───────────────────────────
# The state rows, the new-account gate and account resolution live in oauth_account_service.

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

def _google_authorize_url(request: Request) -> tuple[str, str]:
    """Answer 503 when Google is not configured, rate limit, then mint a state and build Google's
    consent URL for it. Returns ``(url, state)``. The route saves the state
    (``oauth_account_service.save_google_state``, with the invite's hash when the invite is live) in
    the thread pool before it answers, then sets the state cookie: it hands its session to the thread
    pool itself, and to nothing on the event loop (E121)."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Logging in with Google is not available.")
    enforce_rate_limit(
        request, OAUTH_START_LIMITER, "oauth-start",
        error_detail="Too many login attempts. Try again shortly.",
    )
    state = secrets.token_urlsafe(32)
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
    """Redirect the browser to Google's consent screen (plain login: state, no signup assent).

    An invited sign-up starts through ``POST /api/auth/google/start`` instead, so the raw invite
    token never appears in a request URL (request logs record query strings).
    """
    url, state = _google_authorize_url(request)
    # Plain login consumes its state too, but needs no signup evidence for an existing account.
    await run_in_threadpool(oauth_account_service.save_google_state, db, state, None, None)
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
    agreement = body.accepted_agreement()
    if agreement is not None:
        _require_new_collection()
    url, state = _google_authorize_url(request)
    # Signup assent and any live invite are bound to this single-use state.
    await run_in_threadpool(oauth_account_service.save_google_state, db, state, body.invite, agreement)
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
    # Bytes, not str: compare_digest raises TypeError on a non-ASCII str (a 500 instead of the mismatch redirect).
    if not stored_state or not secrets.compare_digest(stored_state.encode(), state.encode()):
        return RedirectResponse(f"{frontend_url}/login?error=oauth_state_mismatch", status_code=302)

    # Consume server state before the provider exchange: restoring a browser cookie must not
    # replay a finished flow. Only a signup start stores assent; existing login does not need it.
    consumed = await run_in_threadpool(oauth_account_service.consume_oauth_state, db, state)
    if consumed is None:
        return RedirectResponse(f"{frontend_url}/login?error=oauth_state_mismatch", status_code=302)
    _, invite_code_hash, agreement = consumed

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

    redirect = RedirectResponse(url=frontend_url, status_code=302)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE)
    user_agent, client_ip, hashed_ip = request.headers.get("user-agent"), _client_ip(request), _hashed_client_ip(request)

    def sign_in() -> _SignedIn:
        # One unit in the thread pool, released before the route awaits the linked-account notice (E121).
        try:
            # Existing link → existing verified account (linked) → new account through the invite gate;
            # stages the link and last_login_at for the commit below.
            user, linked_existing, created = oauth_account_service.resolve_google_user(
                db,
                subject=google_sub,
                email=email,
                email_verified=email_verified_by_google,
                full_name=full_name,
                invite_code_hash=invite_code_hash,
                agreement=agreement,
            )
            # Read before the mint's commit expires the user: nothing after that commit reads it.
            user_id, signed_in = user.id, _SignedIn(user.email, user.full_name, linked_existing)
            # Commits the sign-in with its refresh token; a lost first-sign-in race is rolled back.
            refresh_token = oauth_account_service.mint_oauth_refresh_token(
                db, user, user_agent=user_agent, ip=client_ip
            )
            issue_session(db, user, redirect, request, refresh_token=refresh_token, commit=False, email=signed_in.email)
            if created:
                # A sign-up as well as a login: the register row a password sign-up writes, so the log tells
                # this sign-up from a later login (D-054). Written only now, after the sign-in committed.
                audit_service.log_register(db, user_id, signed_in.email, ip_address=hashed_ip)
            audit_service.log_oauth_login(db, user_id, signed_in.email, provider="google", ip_address=hashed_ip)
            if linked_existing:
                # Security-relevant: a federated identity was just attached to a pre-existing account.
                audit_service.log_oauth_linked(db, user_id, signed_in.email, provider="google", ip_address=hashed_ip)
            return signed_in
        finally:
            filing_list_service.release_request_session(db)

    try:
        signed_in = await run_in_threadpool(sign_in)
    except oauth_account_service.OAuthSignInRefused as refused:
        if refused.lost_create_race:
            logger.warning("%s OAuth IntegrityError creating account", "google")
        return RedirectResponse(f"{frontend_url}/login?error={refused.error_code}", status_code=302)
    except oauth_account_service.OAuthAccountConflictError:
        logger.warning("Google OAuth IntegrityError for sub=%s", google_sub)
        return RedirectResponse(f"{frontend_url}/login?error=google_account_conflict", status_code=302)
    if signed_in.linked_existing:
        await _send_oauth_linked_email_safe(signed_in, "Google")
    return redirect


# ─── Apple Sign In (ES256 client secret, form_post callback, JWKS verification) ──

def _apple_authorize_url(request: Request) -> tuple[str, str, str]:
    """Answer 503 when Apple is not configured, rate limit, then mint a state and a nonce and build
    Apple's consent URL for them. Returns ``(url, state, raw_nonce)``. The route saves the nonce row
    (``oauth_account_service.save_apple_state``, with the invite's hash when the invite is live) in the
    thread pool, committed before it returns the URL and sets the browser-binding cookie: it hands its
    session to the thread pool itself, and to nothing on the event loop (E121)."""
    if not settings.APPLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Logging in with Apple is not available.")
    enforce_rate_limit(
        request, OAUTH_START_LIMITER, "oauth-start",
        error_detail="Too many login attempts. Try again shortly.",
    )

    state = secrets.token_urlsafe(32)
    raw_nonce = secrets.token_urlsafe(32)

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
    return f"{_APPLE_AUTH_URL}?{urlencode(params)}", state, raw_nonce


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
    url, state, raw_nonce = _apple_authorize_url(request)
    await run_in_threadpool(oauth_account_service.save_apple_state, db, state, raw_nonce, None, None)
    redirect = RedirectResponse(url=url, status_code=302)
    _set_apple_state_cookie(redirect, state)
    return redirect


@router.post("/apple/start")
async def apple_start(body: OAuthStartRequest, request: Request, db: Session = Depends(get_db)):
    """Start Sign in with Apple for the browser to follow: ``{"url": ...}`` plus the binding cookie
    (``invite``: as for google_start)."""
    agreement = body.accepted_agreement()
    if agreement is not None:
        _require_new_collection()
    url, state, raw_nonce = _apple_authorize_url(request)
    await run_in_threadpool(oauth_account_service.save_apple_state, db, state, raw_nonce, body.invite, agreement)
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
    consumed = await run_in_threadpool(oauth_account_service.consume_oauth_state, db, state)
    if consumed is None:
        return _apple_redirect(f"{frontend_url}/login?error=oauth_state_mismatch")
    raw_nonce, invite_code_hash, agreement = consumed

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

    redirect = _apple_redirect(frontend_url)
    user_agent, client_ip, hashed_ip = request.headers.get("user-agent"), _client_ip(request), _hashed_client_ip(request)

    def sign_in() -> _SignedIn:
        # One unit in the thread pool, released before the route awaits the linked-account notice (E121).
        try:
            # Resolve user: existing oauth link → existing verified account → new account
            user_obj, linked_existing, created = oauth_account_service.resolve_apple_user(
                db,
                subject=apple_sub,
                email=email,
                email_verified=email_verified_by_apple,
                full_name=full_name,
                invite_code_hash=invite_code_hash,
                agreement=agreement,
            )
            # Read before the mint's commit expires the user: nothing after that commit reads it.
            user_id, signed_in = user_obj.id, _SignedIn(user_obj.email, user_obj.full_name, linked_existing)
            # Commits the sign-in with its refresh token; a lost first-sign-in race is rolled back.
            refresh_token = oauth_account_service.mint_oauth_refresh_token(
                db, user_obj, user_agent=user_agent, ip=client_ip
            )
            issue_session(db, user_obj, redirect, request, refresh_token=refresh_token, commit=False, email=signed_in.email)
            if created:
                # As for Google: the sign-up's register row, after the sign-in committed (D-054).
                audit_service.log_register(db, user_id, signed_in.email, ip_address=hashed_ip)
            audit_service.log_oauth_login(db, user_id, signed_in.email, provider="apple", ip_address=hashed_ip)
            if linked_existing:
                audit_service.log_oauth_linked(db, user_id, signed_in.email, provider="apple", ip_address=hashed_ip)
            return signed_in
        finally:
            filing_list_service.release_request_session(db)

    try:
        signed_in = await run_in_threadpool(sign_in)
    except oauth_account_service.OAuthSignInRefused as refused:
        if refused.lost_create_race:
            logger.warning("%s OAuth IntegrityError creating account", "apple")
        return _apple_redirect(f"{frontend_url}/login?error={refused.error_code}")
    except oauth_account_service.OAuthAccountConflictError:
        logger.warning("Apple OAuth IntegrityError for sub=%s", apple_sub)
        return _apple_redirect(f"{frontend_url}/login?error=apple_account_conflict")
    if signed_in.linked_existing:
        await _send_oauth_linked_email_safe(signed_in, "Apple")
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
    """Revoke the refresh token (if present) and clear the session cookies, on a 503 when the revoke fails."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    # Read before the revoke commits: the commit expires the user, and a read after it refreshes the row.
    actor = (current_user.id, current_user.email) if current_user else None
    hashed_ip = _hashed_client_ip(request)
    # Set once revoke_and_commit has returned: the session it ended stays ended, whatever the unit does after it.
    revoked = False

    def revoke() -> None:
        nonlocal revoked
        # One unit in the thread pool, released before the route returns: a revoke that finds no live
        # token commits nothing, and the audit write reads its row back, so either would otherwise
        # hold a connection for the dependency's finalizer.
        try:
            ended = refresh_token_service.revoke_and_commit(db, raw_token)
            revoked = True
            # The row names the user whose session the logout ended: the one whose refresh token it revoked,
            # which a logout after the session token's 30 minutes knows only from that token, and otherwise
            # the signed-in user. A logout that ends no session and names no user writes none (E137).
            logged = ended or actor
            if logged:
                audit_service.log_logout(db, logged[0], logged[1], ip_address=hashed_ip)
        finally:
            filing_list_service.release_request_session(db)

    try:
        await run_in_threadpool(revoke)
    except Exception:
        if not revoked:
            # The revoke failed (the token store down, the pool exhausted) and its unit rolled back: the session may
            # live on in the database, but this browser's cookies go regardless, or a shared computer stays signed
            # in. The deletions ride a response of our own: FastAPI drops the injected Response's headers from the
            # fresh response it builds for an exception, the global handler's 500 included. No audit row: no session
            # is known to have ended.
            logger.exception("Logout could not revoke the refresh token; clearing this browser's session cookies")
            incomplete = JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "This browser is logged out, but we could not end the session on the server."},
            )
            _clear_auth_cookie(incomplete)
            _clear_refresh_cookie(incomplete)
            return incomplete
        # The revoke committed and something after it raised: the session ended, so this is a logout that succeeded
        # and answers as one. Neither step after the commit lets its own failure out: create_audit_log catches it,
        # logs it, rolls back and returns None, and the release logs a failed close. So this is reached only if that
        # rollback itself raises, or when a step is made to raise, as test_logout_failure_clears_cookies.py makes
        # each in turn; the audit row is whatever that step left.
        logger.exception("Logout ended the session, but a step after the revoke's commit failed")
    _clear_auth_cookie(response)
    _clear_refresh_cookie(response)
    return {"status": "success"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    response: Response,
    payload: Optional[LogoutAllRequest] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(resolve_current_user_or_none),
):
    """Revoke every refresh token of the logged-in user (log out all devices) and clear this session.

    The user is the access token's, read as ``get_current_user`` reads it on every route: a bearer before the access
    cookie, and an inactive account refused with 403. When no access token names a user (none came, or it has lapsed
    after its 30 minutes, does not verify or names no account), a request that names the account its tab shows
    (``account_id``) finds its user from the same cookie a logout reads, if it carries a live refresh token (E157 (2));
    one that names none, from a page loaded before the field, is answered as before it. With no user, 401. A request
    that names another account than the user's is refused with 409: nothing is revoked and the cookies stay."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    # Read before the revoke commits: the commit expires the user, and a read after it refreshes the row.
    actor = (current_user.id, current_user.email) if current_user else None
    shown = payload.account_id if payload is not None else None
    hashed_ip = _hashed_client_ip(request)

    def revoke_all() -> int:
        # One unit in the thread pool, released before the route returns (see ``logout``): the refresh token's owner,
        # read when the access token named no one, the revocation under the users row lock, and the audit row.
        try:
            user = actor
            if user is None and shown is not None:
                user = refresh_token_service.live_token_owner(db, raw_token)
            if user is None:
                raise _not_logged_in()
            if shown is not None and shown != user[0]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This browser is logged in to a different account from the one this page shows, "
                        "so no devices were logged out."
                    ),
                )
            revoked = refresh_token_service.revoke_all_and_commit(db, user[0])
            audit_service.log_logout(db, user[0], user[1], ip_address=hashed_ip)
            return revoked
        finally:
            filing_list_service.release_request_session(db)

    revoked = await run_in_threadpool(revoke_all)
    _clear_auth_cookie(response)
    _clear_refresh_cookie(response)
    return {"status": "success", "sessions_revoked": revoked}


@router.get("/connections")
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the user's sign-in methods: whether a password is set + any linked OAuth providers.

    One unit in the thread pool, the links' read, released before the route returns, so no statement or
    release runs on the event loop (E121, lessons/ops-release-cached-filing-reads-before-yield.md)."""
    user_id, has_password = current_user.id, bool(current_user.hashed_password)

    def read_links() -> list[dict[str, Optional[str]]]:
        try:
            return [
                {
                    "provider": r.provider,
                    "provider_email": r.provider_email,
                    "linked_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in oauth_account_service.list_oauth_accounts(db, user_id)
            ]
        finally:
            filing_list_service.release_request_session(db)

    providers = await run_in_threadpool(read_links)
    return {"has_password": has_password, "providers": providers}


@router.delete("/connections/{provider}")
async def unlink_connection(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlink an OAuth provider — but never remove the user's only remaining sign-in method.

    One unit in the thread pool, the unlink and its audit row, released before the route returns, so no
    statement or release runs on the event loop (E121, lessons/ops-release-cached-filing-reads-before-yield.md).
    In the thread pool two unlinks of one account can interleave, so the unlink takes the account's users row
    lock before its guard reads. A provider the route does not know is refused before any unit; the dependency's
    finalizer then ends the auth lookup's read, in the thread pool."""
    provider = provider.lower().strip()
    if provider not in {"google", "apple"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown provider.")
    # Read before the unlink commits: the commit expires the user, and a read after it refreshes the row.
    user_id, user_email = current_user.id, current_user.email
    hashed_ip = _hashed_client_ip(request)

    def unlink() -> None:
        # The link's delete commits on its own, then its oauth_unlinked audit row, which is best effort.
        try:
            # Lockout guard inside, under the account's users row lock: the user must keep a password or
            # another linked provider, and a concurrent unlink waits for this one's commit.
            oauth_account_service.unlink_oauth_provider(db, user_id, provider)
            audit_service.create_audit_log(
                db,
                action="oauth_unlinked",
                user_id=user_id,
                user_email=user_email,
                entity_type="user",
                ip_address=hashed_ip,
                details={"provider": provider},
            )
        finally:
            filing_list_service.release_request_session(db)

    try:
        await run_in_threadpool(unlink)
    except oauth_account_service.ProviderNotLinkedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That provider is not linked to your account."
        ) from None
    except oauth_account_service.LastSignInMethodError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't remove your only sign-in method. Set a password first, then unlink.",
        ) from None
    return {"status": "success", "unlinked": provider}
