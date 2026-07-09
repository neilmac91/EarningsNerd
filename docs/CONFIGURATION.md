# Configuration Reference — environment variables

The complete environment-variable reference for backend (`backend/.env`) and frontend
(`frontend/.env.local`). Definitions and validation live in `backend/app/config.py`
(Pydantic Settings — ALL backend env access goes through it; never `os.getenv` in app code,
except the pre-Settings infra-bootstrap constants in `database.py`, `redis_service.py`, and
`edgar/config.py`)
and `frontend/lib/featureFlags.ts`. Production values are mounted from Google Secret
Manager onto Cloud Run (see docs/DEPLOYMENT.md).

> Moved out of CLAUDE.md in the July 2026 refactor (Wave 3 / M3) — this file is now the
> canonical env reference; keep it in sync with `config.py` when adding fields.

### Backend (.env)
```
# Database & Cache
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SKIP_REDIS_INIT=false             # Set to true in tests to skip Redis (auto-set by conftest.py)

# AI Configuration (OpenAI-compatible; provider configurable)
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.deepseek.com/v1   # DeepSeek default; override for other providers
AI_DEFAULT_MODEL=deepseek-v4-pro              # Primary AI model
AI_FAST_MODEL=                                # Optional cheaper model for low-risk tasks (falls back to default)
AI_SECTION_RECOVERY_MODEL=                    # Optional override for section recovery (falls back to AI_FAST_MODEL)
RECOVERY_MAX_CONCURRENCY=3                    # Max concurrent calls for section recovery
USE_STRUCTURED_OUTPUT=false                   # Phase-A structured extraction (JSON response_format)
USE_EDGARTOOLS_SECTIONS=true                  # Native edgartools section extraction (vs legacy regex)
AI_QUALITY_GATE=true                          # Partial summaries don't consume user quota
AI_FIGURE_TRACE_GATE=false                    # T3.2 number-diff gate: when on, an untraceable DOLLAR figure in summary prose tiers "partial". Default off (advisory: list attached to the verdict for measurement, never affects tier) until the corpus FP rate is measured
ENABLE_FPI_FILINGS=false                      # Foreign private issuer (ADR) filings: list 20-F/6-K/40-F on the company page (page-scoped; default off — see tasks/fpi-support-roadmap.md)
NOTABLE_FILINGS_ENABLED=false                 # Serve /api/notable_filings (scan job populates regardless; flip after the seed run — DEPLOYMENT.md §12)
NOTABLE_FILINGS_SCAN_DAYS=2                   # Trailing window (days) per scheduled notable-filings scan; seed run overrides via --days

# Copilot ("Ask this Filing" — Pro-only grounded Q&A)
COPILOT_MONTHLY_QUESTION_CAP=1000
COPILOT_MAX_TOKENS=2400
COPILOT_CONTEXT_CHAR_CAP=120000

# Auth & Security
SECRET_KEY=...                    # JWT signing (recommended: 64+ chars)
ACCESS_TOKEN_EXPIRE_MINUTES=30    # Short-lived; frontend silently refreshes
REFRESH_TOKEN_EXPIRE_DAYS=30      # Opaque, rotated, stored hashed
PASSWORD_MIN_LENGTH=12
PWNED_PASSWORD_CHECK_ENABLED=true # Screen new passwords against HaveIBeenPwned (fails open)
TURNSTILE_SECRET_KEY=...          # Cloudflare Turnstile bot defense (no-op/dark when unset)
INTERNAL_JOB_TOKEN=...            # Shared secret for /internal/jobs/* (endpoints 503 when unset)

# Multi-Period Analysis (Pro flagship)
ANALYSIS_MONTHLY_CAP=100          # Fair-use cap on fresh AI narratives/month (cached re-serves free)
ANALYSIS_MAX_TOKENS=3200
ANALYSIS_MAX_ANNUAL_PERIODS=10
ANALYSIS_MAX_QUARTERLY_PERIODS=12
COMPANYFACTS_SYNC_TTL_HOURS=24    # Freshness of the per-company SEC companyfacts ingest

# OAuth (Google + Apple Sign In)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...
APPLE_CLIENT_ID=...               # Services ID (audience)
APPLE_REDIRECT_URI=...

# Stripe
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRICE_MONTHLY_ID=...       # Required (no default) — fails obviously if misconfigured
STRIPE_PRICE_YEARLY_ID=...
PRO_TRIAL_DAYS=7                  # Card-required trial on Pro MONTHLY checkout (0 disables);
                                  # one trial per account (any prior Subscription row skips it)
REVERSE_TRIAL_ENABLED=false       # Retired no-card signup trial (superseded by PRO_TRIAL_DAYS); keep off
REVERSE_TRIAL_DAYS=7

# Email (Resend)
RESEND_API_KEY=...
RESEND_FROM_EMAIL=...             # Must be on a Resend-verified domain (else emails silently drop)
RESEND_WEBHOOK_SECRET=...         # Svix signing secret for the Resend webhook
FRONTEND_URL=https://earningsnerd.io  # Used in email links (verification, reset)

# Analytics & Monitoring
POSTHOG_API_KEY=...
SENTRY_DSN=...                    # Sentry error tracking DSN

# External APIs - Finnhub
FINNHUB_API_KEY=...               # Required for sentiment analysis
FINNHUB_API_BASE=https://finnhub.io/api/v1
FINNHUB_TIMEOUT_SECONDS=6.0       # Timeout for Finnhub API calls
FINNHUB_MAX_CONCURRENCY=4         # Max concurrent Finnhub requests

# External APIs - Financial Modeling Prep (FMP)
FMP_API_KEY=...                   # Stock validation, price data, earnings calendar
FMP_API_BASE=https://financialmodelingprep.com/api/v3
FMP_TIMEOUT_SECONDS=6.0
FMP_MAX_CONCURRENCY=4

# External APIs - Stocktwits (no key required for trending endpoint)
STOCKTWITS_TIMEOUT_SECONDS=6.0

# Hot Filings
HOT_FILINGS_REFRESH_TOKEN=...     # Token for hot filings service
HOT_FILINGS_USER_AGENT=...        # Custom User-Agent for hot filings

# Streaming Configuration
STREAM_HEARTBEAT_INTERVAL=3       # Heartbeat interval in seconds
STREAM_TIMEOUT=600                # Stream timeout in seconds

# Application
ENVIRONMENT=development|production
CORS_ORIGINS_STR=http://localhost:3000,https://yourdomain.com
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=...
NEXT_PUBLIC_POSTHOG_KEY=...
NEXT_PUBLIC_SENTRY_DSN=...
NEXT_PUBLIC_TURNSTILE_SITE_KEY=...                 # Pairs with backend TURNSTILE_SECRET_KEY
NEXT_PUBLIC_LOGO_DEV_TOKEN=...                     # Logo.dev publishable token for CompanyLogo (blank = monogram fallback only)
NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS=true|false
NEXT_PUBLIC_ENABLE_SECTION_TABS=true|false
NEXT_PUBLIC_ENABLE_CALENDAR=true|false             # Earnings calendar (owned EDGAR+Alpha Vantage engine; FMP no longer used)
NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY=true|false     # Form 4 insider activity panel
NEXT_PUBLIC_ENABLE_ANALYSIS=true|false             # Multi-Period Analysis (off: nav/CTA hidden + /analysis route 404s)
NEXT_PUBLIC_ENABLE_MARKET_MOVERS=true|false        # Homepage Market Movers (default off — dead FMP path, no license-clean source; findings review)
WAITLIST_MODE=...                                  # Server-side waitlist gating (not NEXT_PUBLIC_)
```
