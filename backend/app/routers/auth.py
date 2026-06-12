from fastapi import APIRouter, HTTPException, Depends, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import uuid
import hmac
import hashlib
import secrets
import logging

from jose import JWTError, jwt

from app.database import get_db
from app.models import User
from app.config import settings
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.audit_service import (
    log_failed_login,
    log_login_success,
    log_register,
    log_logout,
)

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
_argon2 = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

LOGIN_LIMITER          = RateLimiter(limit=10, window_seconds=60)
REGISTER_LIMITER       = RateLimiter(limit=5,  window_seconds=60)
RESET_REQUEST_LIMITER  = RateLimiter(limit=3,  window_seconds=3600)  # 3/hr per email
RESEND_VERIFY_LIMITER  = RateLimiter(limit=3,  window_seconds=3600)  # 3/hr per email

EMAIL_VERIFY_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1


# ─── Pydantic schemas ────────────────────────────────────────────────────────

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
        if len(value) > settings.PASSWORD_MAX_LENGTH:
            raise ValueError(f"Password must be at most {settings.PASSWORD_MAX_LENGTH} characters.")
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
        if len(value) > settings.PASSWORD_MAX_LENGTH:
            raise ValueError(f"Password must be at most {settings.PASSWORD_MAX_LENGTH} characters.")
        return value


# ─── Password helpers ────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("$argon2"):
        try:
            return _argon2.verify(hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHashError):
            return False
    # bcrypt fallback for existing hashes
    try:
        import bcrypt as _bcrypt
        return _bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        try:
            from passlib.context import CryptContext
            return CryptContext(schemes=["bcrypt"], deprecated="auto").verify(plain_password, hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    return _argon2.hash(password)


# ─── Token helpers ───────────────────────────────────────────────────────────

def _generate_token() -> tuple[str, str]:
    """Return (raw_token_to_email, sha256_hash_to_store). Never store the raw token."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        **data,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": uuid4().hex,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


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
    response.delete_cookie(key=settings.COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")


def _get_token_from_request(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request,
) -> Optional[str]:
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.cookies.get(settings.COOKIE_NAME)


def _add_auth_security_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ─── Auth dependencies ───────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
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
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE, issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "sub", "iat", "iss", "aud"]},
        )
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    token = _get_token_from_request(credentials, request)
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE, issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "sub", "iat", "iss", "aud"]},
        )
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError, AttributeError) as e:
        logger.debug(f"Optional auth failed: {e.__class__.__name__}")
        return None

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user and not user.is_active:
            return None
        return user
    except Exception as e:
        logger.error(f"DB error during optional auth: {e.__class__.__name__}")
        return None


# ─── Email helper (graceful in dev when Resend is not configured) ─────────────

async def _send_verification_email_safe(user: User, frontend_url: str) -> None:
    """Send verification email; in dev without Resend, log the link instead."""
    from app.services.email_service import send_verification_email
    from app.services.resend_service import ResendError

    raw_token, hashed = _generate_token()
    expiry = datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFY_EXPIRY_HOURS)
    user.email_verification_token = hashed
    user.email_verification_expires = expiry
    # Caller must commit after this function

    link = f"{frontend_url}/verify-email?token={raw_token}"
    try:
        await send_verification_email(to_email=user.email, name=user.full_name, verification_link=link)
    except ResendError as e:
        # Dev / unconfigured Resend — log the link so local testing still works
        logger.warning(f"Resend not configured ({e}). Verification link: {link}")

    return raw_token  # not used by callers, but useful in tests


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/register")
async def register(
    user_data: UserCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Register a new user. Returns the same opaque message for new and duplicate emails."""
    enforce_rate_limit(request, REGISTER_LIMITER, "register",
                       error_detail="Too many registration attempts. Please try again in a minute.")
    _add_auth_security_headers(response)
    ip = _get_client_ip(request)
    frontend_url = settings.FRONTEND_URL

    existing_user = db.query(User).filter(User.email == user_data.email).first()

    if existing_user:
        # Equalise timing with a real hash, then silently notify the existing address.
        get_password_hash(user_data.password)
        try:
            from app.services.email_service import send_account_exists_email
            from app.services.resend_service import ResendError
            await send_account_exists_email(
                to_email=existing_user.email,
                name=existing_user.full_name,
                login_link=f"{frontend_url}/login",
                reset_link=f"{frontend_url}/forgot-password",
            )
        except Exception:
            pass  # never surface to caller
        return {"message": "If that email address is new to us, check your inbox for a verification link."}

    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        email_verified=False,
    )
    db.add(user)
    try:
        db.flush()  # get user.id without committing
    except IntegrityError:
        db.rollback()
        get_password_hash(user_data.password)
        return {"message": "If that email address is new to us, check your inbox for a verification link."}

    await _send_verification_email_safe(user, frontend_url)
    db.commit()
    db.refresh(user)
    log_register(db, user.id, user.email, ip_address=ip)

    # Issue session cookie so the user can browse; gated actions require email_verified
    access_token = create_access_token(data={"sub": str(user.id)})
    _set_auth_cookie(response, access_token)
    return {
        "message": "If that email address is new to us, check your inbox for a verification link.",
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate with email and password."""
    enforce_rate_limit(request, LOGIN_LIMITER, "login",
                       error_detail="Too many login attempts. Please try again in a minute.")
    _add_auth_security_headers(response)
    ip = _get_client_ip(request)

    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        log_failed_login(db, email=user_data.email, ip_address=ip, error_message="invalid_credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    log_login_success(db, user.id, user.email, ip_address=ip)

    access_token = create_access_token(data={"sub": str(user.id)})
    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Verify a user's email address using the single-use token from the verification email."""
    _add_auth_security_headers(response)
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
    response: Response,
    db: Session = Depends(get_db),
):
    """Resend the email verification link. Rate-limited to 3/hr per address."""
    enforce_rate_limit(request, RESEND_VERIFY_LIMITER, f"resend:{payload.email}",
                       error_detail="Too many resend requests. Please wait before trying again.")
    _add_auth_security_headers(response)

    user = db.query(User).filter(User.email == payload.email).first()
    # Always return the same response (anti-enumeration)
    _OPAQUE = {"message": "If that email has an unverified account, a new verification link is on its way."}

    if not user or user.email_verified:
        return _OPAQUE

    await _send_verification_email_safe(user, settings.FRONTEND_URL)
    db.commit()
    return _OPAQUE


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Request a password reset link. Rate-limited to 3/hr per email address."""
    enforce_rate_limit(request, RESET_REQUEST_LIMITER, f"reset:{payload.email}",
                       error_detail="Too many reset requests. Please wait before trying again.")
    _add_auth_security_headers(response)
    _OPAQUE = {"message": "If an account exists for that email, a password reset link is on its way."}

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return _OPAQUE
    if not user.hashed_password:
        # Social-only account — let them know they log in via Google/Apple
        # (we know the account exists, but we reveal nothing extra about the provider)
        return _OPAQUE

    raw_token, hashed = _generate_token()
    expiry = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_EXPIRY_HOURS)
    user.password_reset_token = hashed
    user.password_reset_expires = expiry
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    try:
        from app.services.email_service import send_password_reset_email
        from app.services.resend_service import ResendError
        await send_password_reset_email(to_email=user.email, name=user.full_name, reset_link=reset_link)
    except Exception as e:
        logger.warning(f"Could not send reset email to {user.email}: {e}. Link: {reset_link}")

    return _OPAQUE


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Set a new password using the single-use token from the reset email."""
    _add_auth_security_headers(response)
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
    # Also verify email if somehow not verified (user just proved email access)
    user.email_verified = True
    db.commit()
    return {"message": "Password updated. You can now log in with your new password."}


@router.get("/me")
async def get_current_user_info(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile."""
    _add_auth_security_headers(response)
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_pro": current_user.is_pro,
        "email_verified": current_user.email_verified,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    """Clear the auth cookie."""
    _add_auth_security_headers(response)
    try:
        user = await get_current_user_optional(request, credentials, db)
        if user:
            log_logout(db, user.id, user.email, ip_address=_get_client_ip(request))
    except Exception:
        pass
    _clear_auth_cookie(response)
    return {"status": "success"}
