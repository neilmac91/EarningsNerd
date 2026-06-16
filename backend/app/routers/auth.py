from fastapi import APIRouter, HTTPException, Depends, status, Request, Response, Query, Form
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import urlencode
import hashlib
import json
import secrets
import logging
import time

import httpx
import bcrypt
from jose import JWTError, jwt

from app.database import get_db
from app.models import User, OAuthAccount, OAuthState
from app.config import settings
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.refresh_token_service import (
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    RefreshTokenError,
    RefreshTokenReuseError,
)

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

LOGIN_LIMITER = RateLimiter(limit=10, window_seconds=60)
REGISTER_LIMITER = RateLimiter(limit=5, window_seconds=60)
RESET_REQUEST_LIMITER = RateLimiter(limit=3, window_seconds=3600)   # 3/hr per email
RESEND_VERIFY_LIMITER = RateLimiter(limit=3, window_seconds=3600)   # 3/hr per email

EMAIL_VERIFY_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1

# Google OAuth (OIDC) endpoints
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_OAUTH_STATE_COOKIE = "oauth_state"
_OAUTH_STATE_MAX_AGE = 600  # 10 minutes

# Apple Sign In constants and module-level caches.
# Authentication uses the id_token delivered directly in Apple's form_post
# callback (response_type="code id_token"), so no authorization-code exchange
# and no ES256 client secret are required — only the JWKS for signature checks.
_APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

_apple_jwks_cache: dict | None = None
_apple_jwks_cache_expires: float = 0.0


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")
        if not any(char.islower() for char in value):
            raise ValueError("Password must include at least one lowercase letter.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must include at least one uppercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must include at least one number.")
        return value


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
        if len(value) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")
        if not any(char.islower() for char in value):
            raise ValueError("Password must include at least one lowercase letter.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must include at least one uppercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must include at least one number.")
        return value


# ─── Password helpers (bcrypt) ──────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - supports both bcrypt and passlib formats"""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


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


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


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


def _issue_refresh_token(db: Session, user: User, request: Request, response: Response) -> None:
    """Mint a refresh token, persist it, and set the HttpOnly refresh cookie."""
    _, raw_token = create_refresh_token(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
    )
    db.commit()
    _set_refresh_cookie(response, raw_token)


def _get_token_from_request(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request,
) -> Optional[str]:
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    return cookie_token


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
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
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
        )
        email: str = payload.get("sub")
        if email is None:
            return None
    except (JWTError, HTTPException, Exception) as e:
        logger.warning(f"Optional auth failed: {e.__class__.__name__} - {e}")
        return None

    try:
        user = db.query(User).filter(User.email == email).first()
        if user and not user.is_active:
            logger.warning(f"Optional auth: User {email} is inactive")
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
        logger.warning(f"Verification email not sent ({e.__class__.__name__}); link: {link}")


async def _get_apple_jwks() -> dict:
    """Fetch (or return 1-hour-cached) Apple JWKS for id_token verification."""
    global _apple_jwks_cache, _apple_jwks_cache_expires
    now = time.time()
    if _apple_jwks_cache and now < _apple_jwks_cache_expires:
        return _apple_jwks_cache
    async with httpx.AsyncClient(timeout=10.0) as hx:
        resp = await hx.get(_APPLE_JWKS_URL)
        resp.raise_for_status()
        _apple_jwks_cache = resp.json()
        _apple_jwks_cache_expires = now + 3600
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


# ─── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=Token)
async def register(
    user_data: UserCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Register a new user, issue a session, and send an email-verification link."""
    enforce_rate_limit(
        request,
        REGISTER_LIMITER,
        "register",
        error_detail="Too many registration attempts. Please try again in a minute.",
    )
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        email_verified=False,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    await _send_verification_email_safe(db, user)

    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(response, access_token)
    _issue_refresh_token(db, user, request, response)
    return {"access_token": access_token, "token_type": "bearer"}


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
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(response, access_token)
    _issue_refresh_token(db, user, request, response)
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
        user, new_refresh_token = rotate_refresh_token(
            db,
            raw_token,
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
        db.commit()
    except RefreshTokenReuseError as exc:
        db.commit()
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

    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(response, access_token)
    _set_refresh_cookie(response, new_refresh_token)
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
    return {"message": "Email verified. You can now use all features."}


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Resend the email verification link. Rate-limited to 3/hr per address."""
    enforce_rate_limit(
        request, RESEND_VERIFY_LIMITER, f"resend:{payload.email}",
        error_detail="Too many resend requests. Please wait before trying again.",
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
    """Request a password reset link. Rate-limited to 3/hr per email address."""
    enforce_rate_limit(
        request, RESET_REQUEST_LIMITER, f"reset:{payload.email}",
        error_detail="Too many reset requests. Please wait before trying again.",
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
        logger.warning(f"Reset email not sent to {user.email} ({e.__class__.__name__}); link: {reset_link}")

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

    user.hashed_password = get_password_hash(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    # The user proved control of their inbox, so confirm the email too.
    user.email_verified = True
    db.commit()
    return {"message": "Password updated. You can now log in with your new password."}


# ─── Google OAuth (OIDC via httpx — no extra dependency) ───────────────────────

@router.get("/google")
async def google_login():
    """Redirect the browser to Google's consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google Sign-In is not configured.")
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
    redirect = RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)
    redirect.set_cookie(
        _OAUTH_STATE_COOKIE, state, httponly=True, samesite="lax",
        max_age=_OAUTH_STATE_MAX_AGE, secure=settings.COOKIE_SECURE,
    )
    return redirect


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

    # Exchange the authorization code for tokens.
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
            access_token_google = token_resp.json().get("access_token")
            if not access_token_google:
                raise ValueError("no access_token in Google response")

            userinfo_resp = await hx.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token_google}"},
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()
    except Exception as exc:
        logger.warning("Google OAuth exchange failed: %s", exc.__class__.__name__)
        return RedirectResponse(f"{frontend_url}/login?error=google_token_failed", status_code=302)

    google_sub = userinfo.get("sub")
    email = (userinfo.get("email") or "").strip().lower() or None
    email_verified_by_google = bool(userinfo.get("email_verified", False))
    full_name = userinfo.get("name")

    if not google_sub or not email:
        return RedirectResponse(f"{frontend_url}/login?error=google_missing_claims", status_code=302)

    oauth_row = (
        db.query(OAuthAccount)
        .filter_by(provider="google", provider_account_id=google_sub)
        .first()
    )

    if oauth_row:
        user = oauth_row.user
    else:
        # Link to an existing account only when both sides have a verified email.
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing and existing.email_verified and email_verified_by_google:
            user = existing
        else:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=None,
                email_verified=email_verified_by_google,
            )
            db.add(user)
            db.flush()
        db.add(OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=google_sub,
            provider_email=email,
        ))

    user.last_login_at = datetime.now(timezone.utc)

    redirect = RedirectResponse(url=frontend_url, status_code=302)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE)
    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(redirect, access_token)
    try:
        _, raw_refresh = create_refresh_token(
            db, user, user_agent=request.headers.get("user-agent"), ip=_client_ip(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Google OAuth IntegrityError for sub=%s", google_sub)
        return RedirectResponse(f"{frontend_url}/login?error=google_account_conflict", status_code=302)
    _set_refresh_cookie(redirect, raw_refresh)
    return redirect


# ─── Apple Sign In (ES256 client secret, form_post callback, JWKS verification) ──

@router.get("/apple")
async def apple_login(db: Session = Depends(get_db)):
    """Redirect the browser to Apple's consent screen."""
    if not settings.APPLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Apple Sign In is not configured.")

    # Lazy GC: remove expired state rows.
    # Naive UTC (matches refresh_token_service) so the TTL comparison works
    # whether expires_at is read back tz-aware (Postgres) or naive (SQLite).
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)

    state = secrets.token_urlsafe(32)
    raw_nonce = secrets.token_urlsafe(32)
    db.add(OAuthState(
        state=state,
        nonce=raw_nonce,
        expires_at=now + timedelta(minutes=10),
    ))
    db.commit()

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
    return RedirectResponse(url=f"{_APPLE_AUTH_URL}?{urlencode(params)}", status_code=302)


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
        return RedirectResponse(f"{frontend_url}/login?error=apple_denied", status_code=302)
    if not state or not id_token:
        return RedirectResponse(f"{frontend_url}/login?error=apple_invalid", status_code=302)

    # Validate state from DB (form_post drops SameSite=Lax cookies).
    # Naive UTC (see apple_login) so expires_at comparison is backend-agnostic.
    now = datetime.utcnow()
    state_row = db.query(OAuthState).filter_by(state=state).first()
    if not state_row or state_row.expires_at < now:
        if state_row:
            db.delete(state_row)
            db.commit()
        return RedirectResponse(f"{frontend_url}/login?error=oauth_state_mismatch", status_code=302)

    raw_nonce = state_row.nonce
    db.delete(state_row)
    db.commit()

    # Verify Apple's id_token
    try:
        claims = await _verify_apple_id_token(id_token, raw_nonce)
    except Exception as exc:
        logger.warning("Apple id_token verification failed: %s", exc)
        return RedirectResponse(f"{frontend_url}/login?error=apple_invalid", status_code=302)

    apple_sub = claims.get("sub")
    if not apple_sub:
        return RedirectResponse(f"{frontend_url}/login?error=apple_missing_claims", status_code=302)

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

    if oauth_row:
        user_obj = oauth_row.user
        if full_name and not user_obj.full_name:
            user_obj.full_name = full_name
    else:
        if not email:
            # No email and no existing link — can't create an account
            return RedirectResponse(f"{frontend_url}/login?error=apple_missing_claims", status_code=302)

        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            if existing.email_verified and email_verified_by_apple:
                user_obj = existing
                if full_name and not user_obj.full_name:
                    user_obj.full_name = full_name
            else:
                # Email exists but can't be safely linked (unverified on either side).
                # Attempting a new insert would hit the UNIQUE constraint.
                return RedirectResponse(
                    f"{frontend_url}/login?error=apple_account_conflict", status_code=302
                )
        else:
            user_obj = User(
                email=email,
                full_name=full_name,
                hashed_password=None,
                email_verified=email_verified_by_apple,
            )
            db.add(user_obj)
            db.flush()

        db.add(OAuthAccount(
            user_id=user_obj.id,
            provider="apple",
            provider_account_id=apple_sub,
            provider_email=email,
        ))

    user_obj.last_login_at = now
    redirect = RedirectResponse(url=frontend_url, status_code=302)
    access_token = create_access_token(data={"sub": user_obj.email})
    _set_auth_cookie(redirect, access_token)
    try:
        _, raw_refresh = create_refresh_token(
            db, user_obj,
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Apple OAuth IntegrityError for sub=%s", apple_sub)
        return RedirectResponse(f"{frontend_url}/login?error=apple_account_conflict", status_code=302)
    _set_refresh_cookie(redirect, raw_refresh)
    return redirect


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_pro": current_user.is_pro,
        "email_verified": current_user.email_verified,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Revoke the refresh token (if present) and clear both auth cookies."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if revoke_refresh_token(db, raw_token):
        db.commit()
    _clear_auth_cookie(response)
    _clear_refresh_cookie(response)
    return {"status": "success"}
