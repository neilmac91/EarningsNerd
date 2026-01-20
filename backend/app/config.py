from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union
import os

class Settings(BaseSettings):
    # Database
    # Using SQLite for development if PostgreSQL is not available
    DATABASE_URL: str = "sqlite:///./earningsnerd.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # SEC EDGAR API
    SEC_EDGAR_BASE_URL: str = "https://data.sec.gov"
    
    # OpenAI-compatible API (Google AI Studio recommended)
    # Check environment variable first, then .env file
    # Pydantic Settings automatically prioritizes env vars, but we'll make it explicit
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"  # Google AI Studio base URL
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""  # Webhook signing secret from Stripe dashboard
    STRIPE_PRICE_MONTHLY_ID: str = "price_pro_monthly"
    STRIPE_PRICE_YEARLY_ID: str = "price_pro_yearly"

    # PostHog (server-side tracking)
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://us.i.posthog.com"

    # Resend
    RESEND_API_KEY: str = ""
    RESEND_BASE_URL: str = "https://api.resend.com"
    RESEND_FROM_EMAIL: str = "EarningsNerd <onboarding@resend.dev>"

    # X / Twitter API
    TWITTER_BEARER_TOKEN: str = ""

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    PASSWORD_MIN_LENGTH: int = 12
    JWT_ISSUER: str = "earningsnerd"
    JWT_AUDIENCE: str = "earningsnerd-users"
    JWT_LEEWAY_SECONDS: int = 10

    @field_validator('SECRET_KEY', mode='before')
    @classmethod
    def check_secret_key(cls, v, values):
        """Ensure SECRET_KEY is not the default in production"""
        if values.data.get("ENVIRONMENT") == "production" and v == "change-this-secret-key-in-production":
            raise ValueError(
                "CRITICAL: Default 'SECRET_KEY' is in use in a production environment. "
                "Set a strong, random secret in your environment variables."
            )
        if not v:
            raise ValueError("SECRET_KEY must be set.")
        return v

    # App Settings
    ENVIRONMENT: str = "development"
    COOKIE_NAME: str = "earningsnerd_access_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str | None = None
    # Store as string to avoid pydantic-settings JSON parsing issues
    # Use cors_origins property to get the parsed list
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://127.0.0.1:3000,https://earningsnerd.io,https://www.earningsnerd.io"
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(',') if origin.strip()]
    HOT_FILINGS_REFRESH_TOKEN: str = ""
    HOT_FILINGS_USER_AGENT: str = (
        "EarningsNerdBot/1.0 (+https://earningsnerd.com/contact)"
    )
    EARNINGS_WHISPERS_API_BASE: str = "https://www.earningswhispers.com/api"
    FINNHUB_API_BASE: str = "https://finnhub.io/api/v1"
    FINNHUB_API_KEY: str = ""
    FINNHUB_TIMEOUT_SECONDS: float = 6.0
    FINNHUB_MAX_CONCURRENCY: int = 4
    
    class Config:
        env_file = ".env"
        # Pydantic Settings automatically checks environment variables first
        # This ensures we get the value from Cursor settings if available
        case_sensitive = False
        env_file_encoding = 'utf-8'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Explicitly check for environment variable (including Cursor's settings)
        # This handles cases where Cursor settings are passed as env vars
        env_key = os.getenv('OPENAI_API_KEY')
        if env_key and env_key.strip() and len(env_key) > 10:
            self.OPENAI_API_KEY = env_key.strip()
        if "COOKIE_SECURE" not in os.environ:
            self.COOKIE_SECURE = self.ENVIRONMENT == "production"
    
    def validate_openai_config(self) -> tuple[bool, list[str]]:
        """Validate OpenAI-compatible configuration and return (is_valid, warnings)"""
        warnings = []
        is_valid = True
        
        # Check base URL - accept Google AI Studio or OpenRouter
        valid_providers = ["openrouter.ai", "generativelanguage.googleapis.com"]
        if not self.OPENAI_BASE_URL:
            warnings.append("OPENAI_BASE_URL is not set")
            is_valid = False
        elif not any(provider in self.OPENAI_BASE_URL.lower() for provider in valid_providers):
            warnings.append(
                f"OPENAI_BASE_URL ({self.OPENAI_BASE_URL}) does not appear to be a supported provider. "
                "Expected Google AI Studio or OpenRouter."
            )
        
        # Check API key
        if not self.OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY is not set")
            is_valid = False
        elif len(self.OPENAI_API_KEY) < 20:
            warnings.append(f"OPENAI_API_KEY appears too short (length: {len(self.OPENAI_API_KEY)}). Expected at least 20 characters.")
            is_valid = False
        
        return is_valid, warnings
    
    def validate_stripe_config(self) -> tuple[bool, list[str]]:
        """Validate Stripe configuration and return (is_valid, warnings)"""
        warnings = []
        is_valid = True
        
        # Check if Stripe is configured at all
        if not self.STRIPE_SECRET_KEY:
            warnings.append("STRIPE_SECRET_KEY is not set. Stripe features (subscriptions, payments) will be disabled.")
            is_valid = False
        elif len(self.STRIPE_SECRET_KEY) < 20:
            warnings.append(f"STRIPE_SECRET_KEY appears too short (length: {len(self.STRIPE_SECRET_KEY)}). Expected at least 20 characters.")
            is_valid = False
        
        # Check webhook secret (critical for subscription management)
        if self.STRIPE_SECRET_KEY and not self.STRIPE_WEBHOOK_SECRET:
            warnings.append(
                "STRIPE_WEBHOOK_SECRET is not set. Webhook endpoints will fail signature verification. "
                "Subscription events (checkout completion, cancellations) will not be processed. "
                "Set STRIPE_WEBHOOK_SECRET from your Stripe Dashboard > Developers > Webhooks > Signing secret."
            )
            # Don't mark as invalid since Stripe can work without webhooks (manual subscription management)
            # but warn strongly
        
        return is_valid, warnings

settings = Settings()

