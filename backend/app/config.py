from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os

# Single source of truth for the app version (FastAPI metadata, "/" payload,
# /metrics). Bump on notable releases; also serves as a deploy marker.
APP_VERSION = "1.1.0"

class Settings(BaseSettings):
    # Database
    # Using SQLite for development if PostgreSQL is not available
    DATABASE_URL: str = "sqlite:///./earningsnerd.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    SKIP_REDIS_INIT: bool = False  # Set to True in tests to skip Redis initialization
    
    # SEC EDGAR API
    SEC_EDGAR_BASE_URL: str = "https://data.sec.gov"
    SEC_USER_AGENT: str = "EarningsNerd/1.0 (contact@earningsnerd.io)"
    SEC_RATE_LIMIT_PER_SECOND: int = 10
    SEC_MAX_RETRIES: int = 5
    SEC_BASE_BACKOFF_SECONDS: float = 1.0
    # EDGAR full-text search (EFTS) — searches filing/exhibit text since 2001, keyless.
    SEC_EFTS_BASE_URL: str = "https://efts.sec.gov/LATEST/search-index"
    SEC_EFTS_TIMEOUT_SECONDS: float = 8.0
    
    # OpenAI-compatible API (Google AI Studio recommended)
    # Check environment variable first, then .env file
    # Pydantic Settings automatically prioritizes env vars, but we'll make it explicit
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"  # DeepSeek (OpenAI-compatible); override via env for other providers
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""  # Webhook signing secret from Stripe dashboard
    # Price IDs from Stripe Dashboard > Products > Pricing
    # MUST be set via environment variables - no defaults to fail obviously if misconfigured
    STRIPE_PRICE_MONTHLY_ID: str = ""
    STRIPE_PRICE_YEARLY_ID: str = ""
    # Closed-beta 100%-off access. The id of a Stripe *Promotion Code* (promo_…), backed by a
    # 100%-off, duration=forever Coupon. Consumed by the Week 2 invite flow, which applies it via
    # `discounts` gated on the user's beta eligibility server-side (never a client param); paired with
    # the checkout's payment_method_collection="if_required" the amount due is $0 and no card is
    # collected. Unset by default (feature off). Create per Stripe mode (test then live); store the
    # test id in dev, the live id via Secret Manager in prod.
    STRIPE_BETA_PROMO_CODE_ID: str = ""

    # Reverse trial: grant full Pro for N days, no card, on signup. Defaults OFF (rollout strategy
    # enables features per-environment via flags). When on, registration starts a `trialing` sub.
    REVERSE_TRIAL_ENABLED: bool = False
    REVERSE_TRIAL_DAYS: int = 7

    # Shared secret for token-gated internal job endpoints (e.g. Cloud Scheduler → /internal/jobs/*).
    # Unset disables those endpoints (they 503). Set to a long random string in prod.
    INTERNAL_JOB_TOKEN: str = ""

    # PostHog (server-side tracking)
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://us.i.posthog.com"

    # Sentry (error tracking)
    SENTRY_DSN: str = ""  # Get from Sentry.io project settings

    # Resend
    RESEND_API_KEY: str = ""
    RESEND_BASE_URL: str = "https://api.resend.com"
    # Must be an address on a Resend-verified domain. The resend.dev default only delivers to your
    # own Resend account, so leaving it unset would silently drop verification/reset emails to real
    # users. Matches the prod RESEND_FROM_EMAIL secret (overridden by it in prod regardless).
    RESEND_FROM_EMAIL: str = "EarningsNerd <hello@inbound.earningsnerd.io>"
    RESEND_WEBHOOK_SECRET: str = ""  # Webhook signing secret from Resend dashboard
    FRONTEND_URL: str = "https://earningsnerd.io"

    # X / Twitter API
    TWITTER_BEARER_TOKEN: str = ""

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # short-lived; the frontend silently refreshes it
    # Refresh tokens (opaque, rotated, stored hashed server-side) are the durable session: the
    # access token above is short-lived and the frontend API client silently exchanges an
    # expired one via /api/auth/refresh, so users are not logged out every 30 minutes.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_COOKIE_NAME: str = "earningsnerd_refresh_token"
    PASSWORD_MIN_LENGTH: int = 12
    # Screen new/reset passwords against the HaveIBeenPwned breach corpus (k-anonymity).
    # Fails open on any error so a third-party outage never blocks sign-ups. Disabled in tests.
    PWNED_PASSWORD_CHECK_ENABLED: bool = True
    JWT_ISSUER: str = "earningsnerd"
    JWT_AUDIENCE: str = "earningsnerd-users"
    JWT_LEEWAY_SECONDS: int = 10

    # OAuth — Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "https://api.earningsnerd.io/api/auth/google/callback"

    # OAuth — Apple Sign In. The form_post id_token is verified directly against
    # Apple's JWKS, so only the Services ID (audience) and redirect URI are needed —
    # no team/key IDs or .p8 private key (those are only for client-secret/code exchange).
    APPLE_CLIENT_ID: str = ""   # Services ID, e.g. "io.earningsnerd.web"
    APPLE_REDIRECT_URI: str = "https://api.earningsnerd.io/api/auth/apple/callback"

    # Cloudflare Turnstile bot defense. When unset, verification is a no-op (dark) so the
    # feature only activates once BOTH this secret and the frontend NEXT_PUBLIC_TURNSTILE_SITE_KEY
    # are configured. Verifies the widget token on register/login/contact/waitlist.
    TURNSTILE_SECRET_KEY: str = ""

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

    @field_validator('STRIPE_BETA_PROMO_CODE_ID', mode='before')
    @classmethod
    def _check_beta_promo_id(cls, v):
        """Fail fast on the easy misconfiguration of pasting a Coupon id ('co_…') or the
        human-readable promotion *code* in place of the Promotion Code *id* ('promo_…'). Stripe's
        checkout ``discounts`` param requires the ``promo_`` id and 400s otherwise. Empty disables
        the beta promo (the default)."""
        if isinstance(v, str):
            v = v.strip()
            if v and not v.startswith("promo_"):
                raise ValueError(
                    "STRIPE_BETA_PROMO_CODE_ID must be a Stripe Promotion Code id starting with "
                    "'promo_' (not a coupon id 'co_…' nor the human-readable code). Leave it empty "
                    "to disable the beta promo."
                )
        return v

    @field_validator('RESEND_FROM_EMAIL', mode='before')
    @classmethod
    def _normalize_from_email(cls, v):
        """Tolerate a value accidentally wrapped in quotes — a very common Secret Manager / .env
        mistake (e.g. '"EarningsNerd <hello@x>"'), which Resend rejects with a 422 "Invalid `from`
        field". Only unwrap when the WHOLE value is wrapped in matching quotes, so a legitimately
        quoted display name ('"Earnings, Nerd" <hello@x>') is left intact.
        """
        if isinstance(v, str):
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1].strip()
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

    # Stocktwits API (no key required for trending endpoint)
    STOCKTWITS_TIMEOUT_SECONDS: float = 6.0

    # Financial Modeling Prep (FMP) API
    FMP_API_KEY: str = ""
    FMP_API_BASE: str = "https://financialmodelingprep.com/api/v3"
    FMP_TIMEOUT_SECONDS: float = 6.0
    FMP_MAX_CONCURRENCY: int = 4

    # Cache Settings
    XBRL_CACHE_TTL_HOURS: int = 24  # XBRL data changes only quarterly
    STRUCTURED_EXTRACTION_CACHE_TTL_SECONDS: int = 3600  # 1 hour for retry window

    # AI Model Settings
    AI_DEFAULT_MODEL: str = "deepseek-v4-pro"  # Primary model (DeepSeek V4 migration, non-thinking; chose pro over flash on the quality preference). Prod sets this + OPENAI_BASE_URL + OPENAI_API_KEY via env/Secret Manager.

    # Optional cheaper model for low-risk sub-tasks (cost/latency — roadmap A11).
    # Both default to "" → fall back to AI_DEFAULT_MODEL, so behavior is UNCHANGED until set.
    # Flip only after the eval harness (backend/evals) shows no quality regression.
    #   AI_FAST_MODEL             — cheaper model for any task that opts in (e.g. gemini-2.5-flash)
    #   AI_SECTION_RECOVERY_MODEL — overrides just the section-recovery task; falls back to AI_FAST_MODEL
    AI_FAST_MODEL: str = ""
    AI_SECTION_RECOVERY_MODEL: str = ""

    # Structured-output mode for Phase-A extraction (roadmap S1). When True, the structured
    # extraction call uses an API-level response_format (JSON object), a schema-described
    # prompt with the narrative-format instructions removed, and a pinned low temperature —
    # eliminating the prompt-vs-schema contradiction that drives "hit and miss" output.
    # Default False: keep the current behavior until the eval harness (S3) proves the new path
    # beats baseline. Toggle with USE_STRUCTURED_OUTPUT=true (no env prefix is configured on
    # Settings, so the env var name matches the field name; case-insensitive).
    USE_STRUCTURED_OUTPUT: bool = False

    # Native section extraction via edgartools (report-quality fix). The legacy regex extractor
    # in openai_service.extract_critical_sections assumes a line-oriented plain-text 10-K layout;
    # on modern inline-XBRL filings BeautifulSoup.get_text(separator='\n') shreds the item headers
    # across many lines, so the targeted regex captures ~0 chars and the pipeline silently falls
    # back to keyword "dense windows" (~260k chars of lower-precision text). edgartools' own parser
    # (filing.obj().sections / obj['Item 7']) resolves the real section boundaries, yielding a
    # smaller, higher-precision excerpt (verified: AAPL 10-K ~147k precise chars vs ~260k window).
    # When True (default), the pipeline prefers edgartools sections and falls back to the legacy
    # regex + dense-window path whenever sections come back empty/thin or parsing fails — so the
    # safety net is preserved. Set USE_EDGARTOOLS_SECTIONS=false for instant rollback to the
    # legacy-only behavior.
    USE_EDGARTOOLS_SECTIONS: bool = True

    # Semantic quality gate (roadmap S4). When True, a summary assessed "partial" (thin coverage
    # or financials not grounded in XBRL) does NOT consume the user's monthly quota — they
    # weren't served a full result. The summary is always persisted regardless (so the streamed
    # result doesn't vanish on refetch), and the UI surfaces partials honestly via the quality
    # badge + Regenerate. The verdict is always attached to raw_summary["quality"] (additive
    # metadata). Enabled (report-quality Phase 0): users are not charged quota for partial results.
    AI_QUALITY_GATE: bool = True

    # Anonymous (guest) daily summary quota (roadmap S5). Guests currently have no daily/monthly
    # cap (only 5/60s per IP), so one IP could trigger thousands of AI calls/month. A small daily
    # cap keeps free activation sustainable WITHOUT ever gating the first summary (a brand-new IP
    # is always under the cap). Fails open if Redis is unavailable — infra must never block a
    # first-time visitor's first summary. Default off; flip ENABLE_GUEST_DAILY_QUOTA to enable.
    ENABLE_GUEST_DAILY_QUOTA: bool = False
    GUEST_DAILY_SUMMARY_LIMIT: int = 3

    # AI Recovery Settings
    RECOVERY_MAX_CONCURRENCY: int = 3  # Max concurrent API calls for section recovery

    # "Ask this Filing" Copilot (A2 / P1). Pro-only grounded single-filing Q&A.
    #   COPILOT_MONTHLY_QUESTION_CAP — fair-use soft cap per Pro user per month (degrade, not punish).
    #   COPILOT_MAX_TOKENS           — max completion tokens for an answer (answer + citations JSON).
    #   COPILOT_CONTEXT_CHAR_CAP     — hard cap on filing excerpt chars stuffed into context.
    #   COPILOT_HISTORY_TURNS        — number of prior conversation turns kept for follow-ups.
    #   COPILOT_HISTORY_MAX_ITEMS    — hard cap on accepted history array length (prompt-stuffing/abuse guard).
    #   COPILOT_HISTORY_ITEM_CHAR_CAP— per-turn content char cap (the question field is already capped).
    COPILOT_MONTHLY_QUESTION_CAP: int = 1000
    COPILOT_MAX_TOKENS: int = 1200
    COPILOT_CONTEXT_CHAR_CAP: int = 120000
    COPILOT_HISTORY_TURNS: int = 6
    COPILOT_HISTORY_MAX_ITEMS: int = 50
    COPILOT_HISTORY_ITEM_CHAR_CAP: int = 8000

    # Stream Settings
    STREAM_HEARTBEAT_INTERVAL: int = 3  # Send updates every 3 seconds (reduced from 5s for better UX)
    STREAM_TIMEOUT: int = 600
    
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
        # Fail closed: production must never silently use the local SQLite default (an empty,
        # ephemeral, unencrypted DB on a fresh container). Force an explicit production DATABASE_URL.
        if self.ENVIRONMENT == "production" and self.DATABASE_URL.strip().lower().startswith("sqlite"):
            raise ValueError(
                "DATABASE_URL must point at a production database in production; refusing to start "
                "on the sqlite default. Set DATABASE_URL to your Postgres/Cloud SQL connection string."
            )
        # Warn (don't fail) if the session cookie isn't scoped to the parent domain in production.
        # When the frontend (earningsnerd.io / www) and API (api.earningsnerd.io) are different hosts
        # of the same site, an unset COOKIE_DOMAIN makes the auth cookie host-only on the API host —
        # invisible to the Next.js middleware on the frontend, which then redirect-loops every
        # protected route back to /login. A single-host deployment is legitimately fine unset.
        if self.ENVIRONMENT == "production" and not self.COOKIE_DOMAIN:
            import logging
            logging.getLogger("uvicorn.error").warning(
                "COOKIE_DOMAIN is unset in production. If the frontend and API are on different "
                "hosts of the same site, session cookies will be host-only and protected routes "
                "will redirect-loop. Set COOKIE_DOMAIN=.earningsnerd.io."
            )
    
    def validate_openai_config(self) -> tuple[bool, list[str]]:
        """Validate OpenAI-compatible configuration and return (is_valid, warnings)"""
        warnings = []
        is_valid = True
        
        # Check base URL - accept Google AI Studio, OpenRouter, or DeepSeek
        valid_providers = ["openrouter.ai", "generativelanguage.googleapis.com", "api.deepseek.com"]
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

        # Check Price IDs are set (critical for checkout sessions)
        if self.STRIPE_SECRET_KEY:
            if not self.STRIPE_PRICE_MONTHLY_ID:
                warnings.append(
                    "STRIPE_PRICE_MONTHLY_ID is not set. Monthly subscription checkout will fail. "
                    "Set this to your Stripe Price ID from Dashboard > Products > Pricing."
                )
                is_valid = False
            if not self.STRIPE_PRICE_YEARLY_ID:
                warnings.append(
                    "STRIPE_PRICE_YEARLY_ID is not set. Yearly subscription checkout will fail. "
                    "Set this to your Stripe Price ID from Dashboard > Products > Pricing."
                )
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

        # Live-mode guard: a test key in production (or live key in dev) means real money / wrong
        # account. Stripe test keys are `sk_test_*` / `pk_test_*`, live are `sk_live_*` / `pk_live_*`.
        if self.STRIPE_SECRET_KEY:
            is_test_key = self.STRIPE_SECRET_KEY.startswith("sk_test_")
            is_live_key = self.STRIPE_SECRET_KEY.startswith("sk_live_")
            if self.ENVIRONMENT == "production" and is_test_key:
                warnings.append(
                    "STRIPE_SECRET_KEY is a TEST key (sk_test_) but ENVIRONMENT=production. "
                    "Real subscriptions will not be charged. Use your live key (sk_live_)."
                )
                is_valid = False
            elif self.ENVIRONMENT != "production" and is_live_key:
                warnings.append(
                    "STRIPE_SECRET_KEY is a LIVE key (sk_live_) outside production "
                    f"(ENVIRONMENT={self.ENVIRONMENT}). Risk of charging real cards in dev/test. "
                    "Use a test key (sk_test_)."
                )
                is_valid = False
            if self.STRIPE_PUBLISHABLE_KEY:
                pub_test = self.STRIPE_PUBLISHABLE_KEY.startswith("pk_test_")
                pub_live = self.STRIPE_PUBLISHABLE_KEY.startswith("pk_live_")
                # Publishable + secret keys must agree on mode, or checkout breaks subtly.
                if (is_live_key and pub_test) or (is_test_key and pub_live):
                    warnings.append(
                        "STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY are in different modes "
                        "(one live, one test). They must match."
                    )
                    is_valid = False

        return is_valid, warnings

    def validate_resend_config(self) -> tuple[bool, list[str]]:
        """Validate outbound email (Resend) config and return (is_valid, warnings).

        Email is on the signup path (verify-first), so a misconfigured sender silently breaks
        registration for real users. The most common failure is leaving the From at the
        ``resend.dev`` test sender, which only delivers to your own Resend account.
        """
        warnings: list[str] = []
        from_email = (self.RESEND_FROM_EMAIL or "").strip()

        if not self.RESEND_API_KEY:
            warnings.append(
                "RESEND_API_KEY is not set — outbound email (verification, password reset) will fail."
            )
        if not from_email:
            warnings.append("RESEND_FROM_EMAIL is empty — set it to an address on a verified domain.")
        elif "resend.dev" in from_email.lower():
            warnings.append(
                f"RESEND_FROM_EMAIL is '{from_email}', which uses Resend's test sender that ONLY "
                "delivers to your own account. Real users will NOT receive verification/reset emails. "
                "Set it to an address on a Resend-verified domain (e.g. hello@inbound.earningsnerd.io)."
            )

        return (not warnings), warnings

settings = Settings()

