from fastapi import APIRouter, HTTPException, Depends, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, timedelta
from uuid import uuid4
from jose import JWTError, jwt
import bcrypt
import logging
from app.database import get_db
from app.models import User
from app.config import settings
from app.services.rate_limiter import RateLimiter, enforce_rate_limit

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

LOGIN_LIMITER = RateLimiter(limit=10, window_seconds=60)
REGISTER_LIMITER = RateLimiter(limit=5, window_seconds=60)


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

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - supports both bcrypt and passlib formats"""
    try:
        # Try direct bcrypt verification first (most common)
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        # Fallback to passlib if bcrypt fails (for legacy hashes)
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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    now = datetime.utcnow()
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
        # Log the exception for debugging purposes
        logger.warning(f"Optional auth failed: {e.__class__.__name__} - {e}")
        # Silently ignore authentication errors for optional auth
        return None
    
    try:
        user = db.query(User).filter(User.email == email).first()
        if user and not user.is_active:
            return None
        return user
    except Exception as e:
        logger.error(f"Database error during optional auth: {e.__class__.__name__} - {e}")
        return None

@router.post("/register", response_model=Token)
async def register(
    user_data: UserCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Register a new user"""
    enforce_rate_limit(
        request,
        REGISTER_LIMITER,
        "register",
        error_detail="Too many registration attempts. Please try again in a minute.",
    )
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name
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
    
    # Create token
    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(response, access_token)
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
    
    access_token = create_access_token(data={"sub": user.email})
    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_pro": current_user.is_pro
    }

@router.post("/logout")
async def logout(response: Response):
    """Clear auth cookie"""
    _clear_auth_cookie(response)
    return {"status": "success"}