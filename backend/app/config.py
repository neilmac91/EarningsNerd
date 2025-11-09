from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Database
    # Using SQLite for development if PostgreSQL is not available
    DATABASE_URL: str = "sqlite:///./earningsnerd.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # SEC EDGAR API
    SEC_EDGAR_BASE_URL: str = "https://data.sec.gov"
    
    # OpenAI API / OpenRouter
    # Check environment variable first, then .env file
    # Pydantic Settings automatically prioritizes env vars, but we'll make it explicit
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"  # OpenRouter base URL
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""  # Webhook signing secret from Stripe dashboard

    # X / Twitter API
    TWITTER_BEARER_TOKEN: str = ""

    # JWT
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # App Settings
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
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
    
    def validate_openai_config(self) -> tuple[bool, list[str]]:
        """Validate OpenAI/OpenRouter configuration and return (is_valid, warnings)"""
        warnings = []
        is_valid = True
        
        # Check base URL
        if not self.OPENAI_BASE_URL:
            warnings.append("OPENAI_BASE_URL is not set")
            is_valid = False
        elif "openrouter.ai" not in self.OPENAI_BASE_URL.lower():
            warnings.append(f"OPENAI_BASE_URL ({self.OPENAI_BASE_URL}) does not appear to be OpenRouter. Expected 'openrouter.ai' in URL.")
        
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

