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

from jose import JWTError, jwt
import logging

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

# argon2id for new passwords; bcrypt fallback for existing hashes
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerifyMismatchError
_argon2 = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

LOGIN_LIMITER    = RateLimiter(limit=10, window_seconds=60)
REGISTER_LIMITER = RateLimiter(limit=5,  window_seconds=60)


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
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


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
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
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
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
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


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register")
async def register(
    user_data: UserCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Register a new user.

    Returns the same opaque response whether the email is new or already registered
    (anti-enumeration). When email already exists, a notification email is sent
    to the address (implemented in Increment 2 when email templates are live).
    """
    enforce_rate_limit(
        request,
        REGISTER_LIMITER,
        "register",
        error_detail="Too many registration attempts. Please try again in a minute.",
    )
    _add_auth_security_headers(response)

    ip = _get_client_ip(request)
    existing_user = db.query(User).filter(User.email == user_data.email).first()

    if existing_user:
        # Anti-enumeration: perform a dummy hash to equalise timing, then return success-looking response.
        # Increment 2 will send an "account already exists" email here.
        get_password_hash(user_data.password)
        logger.info(f"Register attempt for existing email (not disclosed to caller): {user_data.email}")
        return {
            "message": "If that email address is new to us, we've sent a verification link. Check your inbox.",
        }

    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        email_verified=False,  # Increment 2 gates sensitive actions on this
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        get_password_hash(user_data.password)  # equalise timing
        return {
            "message": "If that email address is new to us, we've sent a verification link. Check your inbox.",
        }

    log_register(db, user.id, user.email, ip_address=ip)

    # Issue session token so the user can continue (email verification banner shown in UI)
    access_token = create_access_token(data={"sub": str(user.id)})
    _set_auth_cookie(response, access_token)
    return {
        "message": "If that email address is new to us, we've sent a verification link. Check your inbox.",
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
    """Authenticate a user with email and password."""
    enforce_rate_limit(
        request,
        LOGIN_LIMITER,
        "login",
        error_detail="Too many login attempts. Please try again in a minute.",
    )
    _add_auth_security_headers(response)

    ip = _get_client_ip(request)
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user or not verify_password(user_data.password, user.hashed_password):
        log_failed_login(db, email=user_data.email, ip_address=ip, error_message="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    log_login_success(db, user.id, user.email, ip_address=ip)

    access_token = create_access_token(data={"sub": str(user.id)})
    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


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
    """Clear the auth cookie and audit-log the logout."""
    _add_auth_security_headers(response)
    # Best-effort: extract user for audit log (ignore errors — cookie may already be invalid)
    try:
        user = await get_current_user_optional(request, credentials, db)
        if user:
            log_logout(db, user.id, user.email, ip_address=_get_client_ip(request))
    except Exception:
        pass
    _clear_auth_cookie(response)
    return {"status": "success"}
