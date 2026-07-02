# CLAUDE.md - EarningsNerd

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents (.claude/agents)
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update 'tasks/lessons.md' with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests -> then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management
1. **Plan First**: Write plan to 'tasks/todo.md' with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review to 'tasks/todo.md'
6. **Capture Lessons**: Update 'tasks/lessons.md' after corrections

## Core Principles
- **Simplicity First**: Strive for the simplest possible solution, avoiding over-engineering.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Touch only what's necessary to reduce the risk of unintended side-effects.
- **Suggest Better Approaches**: I'm always open to ideas on better ways to do things. Please don't hesitate to suggest a better way, or one that has long lasting impact over a tactical change. In this regard, if you see a clearly better approach, say so before implementing. Explain the tradeoff in 2-4 bullets. If the current request is still reasonable, proceed with it — switch to the alternative only when it avoids serious risk or wasted work.

> These reinforce the four behavioral principles in the `karpathy-guidelines` skill
> (`.claude/skills/meta/karpathy-guidelines/`): Think Before Coding, Simplicity First,
> Surgical Changes, Goal-Driven Execution.

## Project Overview

EarningsNerd is an AI-powered SEC filing analysis platform that transforms dense SEC filings (10-Ks and 10-Qs) into clear, actionable insights for investors. It combines SEC EDGAR data retrieval, XBRL parsing, and generative AI summarization.

## Tech Stack

**Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0, PostgreSQL 15, Redis 7
**Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui, React Query
**AI:** OpenAI-compatible API (default `deepseek-v4-pro` via `https://api.deepseek.com/v1`; provider + model are env-configurable via `OPENAI_BASE_URL` + `AI_DEFAULT_MODEL`)
**Payments:** Stripe | **Email:** Resend | **Analytics:** PostHog, Vercel Analytics | **Errors:** Sentry

## Quick Commands

### Backend (from `/backend`)
```bash
pip install -r requirements.txt                    # Install dependencies
# Schema is created at startup (Base.metadata.create_all in main.py's lifespan);
# one-off SQL migrations live in migrations/ and are applied manually.
uvicorn main:app --reload --host 0.0.0.0 --port 8000  # Dev server
pytest tests/                                      # Run all tests
pytest tests/unit/                                 # Unit tests only
pytest tests/smoke/ -v                             # Smoke tests (critical paths)
python3 scripts/deploy_check.py                    # Pre-deploy validation
python3 scripts/validate_db_performance.py         # PostgreSQL performance check
python3 scripts/verify_extraction_standalone.py   # Test XBRL extraction
```

### Frontend (from `/frontend`)
```bash
npm install          # Install dependencies
npm run dev          # Dev server (http://localhost:3000)
npm run test         # Vitest unit tests
npm run test:e2e     # Playwright E2E tests
npm run lint         # ESLint
npm run build        # Production build
```

### Infrastructure
```bash
docker-compose up -d postgres redis   # Start databases
docker-compose down                   # Stop databases
```

## Project Structure

```
/backend
├── app/
│   ├── routers/          # API endpoints (auth, companies, peers, insiders, filings, summaries, dashboard, search, internal, admin, etc.)
│   ├── services/         # Business logic layer (40+ services: AI, copilot, facts, entitlements, notifications, insiders, peers, etc.)
│   │   ├── edgar/        # SEC EDGAR integration (circuit_breaker, client, xbrl_service, instance_extractor, statement_parser)
│   │   ├── logging_service.py   # Structured logging with correlation IDs
│   │   ├── metrics_service.py   # Application metrics aggregation
│   │   ├── redis_service.py     # Connection pooling, cache helpers, health checks
│   │   └── openai_service.py    # AI summarization logic
│   ├── models/           # SQLAlchemy ORM models (User/Company/Filing/Summary in __init__.py; FinancialFact, notifications, refresh_token, subscription, waitlist, contact, audit_log in submodules)
│   ├── schemas/          # Pydantic validation schemas (summary, contact, fundamentals, insiders, peers, search)
│   ├── integrations/     # External APIs (finnhub, earnings_whispers, fmp, stocktwits, sec_api)
│   ├── config.py         # Pydantic Settings (env validation)
│   └── database.py       # DB session management
├── pipeline/             # SEC data pipeline (extract, validate, quality, schema, write)
├── evals/                # AI eval harness (golden sets, judge, copilot scorers) — see evals/RUNBOOK.md
├── tests/                # pytest tests (unit/, integration/, performance/, smoke/)
├── prompts/              # AI system prompts (10k/10q analyst-agent.md + 10k/10q structured-agent.md)
├── scripts/              # Verification and debug scripts
├── docs/                 # Design docs (plan_sec_pipeline.md)
├── migrations/           # One-off SQL migrations (applied manually; no Alembic)
└── main.py               # FastAPI app entry point

/frontend
├── app/                  # Next.js App Router pages
│   ├── login/, register/ # Auth routes (root-level, no route group)
│   ├── forgot-password/, reset-password/, check-email/, verify-email/  # Password reset + email verification flows
│   ├── company/[ticker]/ # Company detail pages
│   ├── filing/[id]/      # Filing summary pages
│   ├── compare/result/   # Filing comparison pages
│   ├── dashboard/        # User dashboard (settings/, watchlist/ subroutes)
│   ├── search/           # Global filing search page
│   ├── contact/          # Contact form page
│   ├── pricing/          # Pricing page
│   ├── waitlist/         # Waitlist signup page
│   ├── privacy/, security/, terms/  # Legal/info pages
│   └── layout.tsx        # Root layout with providers
├── components/           # Reusable React components (50+ files; subdirs: auth/, charts/, dashboard/, settings/, watchlist/, ui/)
├── features/             # Domain modules (auth, companies, filings, fundamentals, insiders, peers, search, subscriptions, summaries, notifications, watchlist, contact)
│   ├── */api/            # API client functions per domain
│   └── filings/components/  # Filing summary sections + copilot/ (Ask-this-Filing Q&A)
├── lib/
│   ├── api/client.ts     # Axios instance with auth interceptors
│   ├── api/types.ts      # TypeScript API types
│   ├── api/refresh.ts, api/session.ts  # Token refresh + session helpers
│   ├── serverApi.ts      # Server-side API helper (SSR/RSC)
│   ├── featureFlags.ts   # Feature flag configuration
│   ├── guards.ts         # Route guards
│   ├── formatters.ts, format.ts  # Formatting utilities
│   ├── entryPoint.ts     # Entry-point config
│   ├── analytics.ts      # Analytics integration
│   ├── QualityGate.ts    # Summary quality gating
│   └── stripInternalNotices.ts  # Strip internal AI notices from output
├── hooks/                # Custom React hooks (useCountUp)
└── types/                # Shared TypeScript types (summary.ts)
```

## Key Files

### Backend Services

| File | Purpose |
|------|---------|
| `backend/app/services/openai_service.py` | AI summarization logic, prompt engineering |
| `backend/app/services/summary_generation_service.py` | Shared generation helpers (progress, quality, excerpt cache) + `generate_summary_background` (batch/cron only; the user-facing path is SSE streaming in `summaries.py`) |
| `backend/app/services/subscription_service.py` | User subscription usage tracking (FREE_TIER_SUMMARY_LIMIT = 5) |
| `backend/app/services/rate_limiter.py` | In-memory sliding window rate limiter |
| `backend/app/services/sec_rate_limiter.py` | SEC EDGAR-specific rate limiter with token bucket and exponential backoff |
| `backend/app/services/email_service.py` | Resend API wrapper for email delivery with HTML templates |
| `backend/app/services/resend_service.py` | Low-level Resend API client |
| `backend/app/services/fallback_summary.py` | Generates deterministic summaries when AI generation fails |
| `backend/app/services/prompt_loader.py` | Loads AI prompts from markdown files |
| `backend/app/services/hot_filings.py` | Identifies trending SEC filings using Finnhub/EarningsWhispers signals |
| `backend/app/services/trending_service.py` | Trending tickers with keyword sentiment analysis |
| `backend/app/services/export_service.py` | PDF/HTML export of summaries and filings |
| `backend/app/services/waitlist_service.py` | Waitlist signups with referral codes and priority scoring |
| `backend/app/services/posthog_client.py` | PostHog analytics event tracking |
| `backend/app/services/redis_service.py` | Redis connection pooling, cache helpers, TTL config, event loop safety |
| `backend/app/services/logging_service.py` | Structured logging, correlation IDs, request context |
| `backend/app/services/metrics_service.py` | Application metrics for monitoring dashboards |
| `backend/app/services/audit_service.py` | Audit logging for GDPR compliance |
| `backend/app/services/summary_pipeline.py` | Transport-agnostic summary-generation pipeline yielding plain dict events for SSE streaming |
| `backend/app/services/copilot_service.py` | "Ask this Filing" — scoped single-filing Q&A with verifiable, deep-linked citations (Pro) |
| `backend/app/services/copilot_tools.py` | Numeric XBRL tool-use for Copilot — exact values from `financial_fact` for calculations |
| `backend/app/services/provenance_service.py` | Trace-to-Source provenance: verifies AI excerpts and builds deep-link citations |
| `backend/app/services/change_report_service.py` | Period-over-period change report (financial deltas + risk-factor diffs) |
| `backend/app/services/facts_service.py` | Normalizes/upserts standardized XBRL metrics into the queryable `financial_fact` table |
| `backend/app/services/peers_service.py` | Cross-company peer comparison using `financial_fact` indexed by SIC |
| `backend/app/services/insider_service.py` | Form 4 insider-activity orchestration (open-market trades, Rule 10b5-1 split) |
| `backend/app/services/ownership_extractor.py` | Form 4 transaction extraction from EdgarTools (defensive against version variance) |
| `backend/app/services/dashboard_feed_service.py` | Personalized dashboard feed with deterministic "what changed" headlines |
| `backend/app/services/calendar_service.py` | Upcoming earnings calendar for watched companies (FMP-backed) |
| `backend/app/services/filing_scan_service.py` | New-filing detection + real-time/digest alert delivery (with dedup) for watched companies |
| `backend/app/services/notification_service.py` | Notification-preference helpers (alert eligibility, realtime/digest selection) |
| `backend/app/services/pulse_service.py` | Filing Pulse — calm, sourced buzz gauge from `buzz_components` |
| `backend/app/services/entitlements.py` | Single source of truth for plan-based feature gates / subscription state (Free vs Pro) |
| `backend/app/services/subscription_sync.py` | Syncs Stripe webhook events into the `subscriptions` table (idempotent) |
| `backend/app/services/refresh_token_service.py` | Refresh-token lifecycle (issue, rotate, revoke) with hashed storage + reuse theft-detection |
| `backend/app/services/guest_quota.py` | Per-IP daily summary quota for anonymous users (atomic Redis INCR, fail-open) |
| `backend/app/services/turnstile.py` | Cloudflare Turnstile bot-defense verification (dark rollout, fail-open on infra errors) |
| `backend/app/services/pwned_passwords.py` | Breached-password screening via HaveIBeenPwned k-anonymity range API |

### EDGAR Integration (`backend/app/services/edgar/`)

| File | Purpose |
|------|---------|
| `xbrl_service.py` | XBRL financial data extraction with two-tier caching |
| `compat.py` | SEC EDGAR compatibility layer with two-tier ticker caching |
| `client.py` | SEC EDGAR API client |
| `circuit_breaker.py` | Circuit breaker pattern for SEC EDGAR resilience |
| `async_executor.py` | Async wrapper for EdgarTools using dedicated thread pool |
| `config.py` | EdgarTools configuration (thread pool size, timeouts) |
| `exceptions.py` | EdgarTools-specific exception definitions |
| `models.py` | EdgarTools domain models (dataclass wrappers) |
| `instance_extractor.py` | Accession-aware XBRL instance extraction (selects facts for the filing's own reporting period) |
| `statement_parser.py` | Pure helpers extracting metric values from EdgarTools statement DataFrames |

### External Integrations (`backend/app/integrations/`)

| File | Purpose |
|------|---------|
| `finnhub.py` | News sentiment analysis (buzz_ratio, articles_in_last_week, bullish_percent) |
| `earnings_whispers.py` | Earnings surprise signals and company earnings data |
| `fmp.py` | Financial Modeling Prep: stock symbol validation, price data, earnings calendar |
| `stocktwits.py` | Stocktwits trending symbols API for social sentiment signals |
| `sec_api.py` | SEC EDGAR full-text search (EFTS) — keyless filing/exhibit text index since 2001 |

### SEC Data Pipeline (`backend/pipeline/`)

Modular ETL pipeline for SEC filing data (see `backend/docs/plan_sec_pipeline.md`):

| File | Purpose |
|------|---------|
| `extract.py` | Extraction logic for filing data |
| `validate.py` | Validation of extracted data |
| `quality.py` | Data quality checks |
| `schema.py` | Schema definitions for pipeline data |
| `write.py` | Persist/write pipeline output |

### API Routers (`backend/app/routers/`)

| File | Prefix | Purpose |
|------|--------|---------|
| `summaries.py` | `/api/summaries` | Summary generation (SSE streaming), copilot Q&A, change reports |
| `filings.py` | `/api/filings` | Filing retrieval and management |
| `companies.py` | `/api/companies` | Company search and details |
| `peers.py` | `/api/companies` | Cross-company peer comparison (`GET /{ticker}/peers`) |
| `insiders.py` | `/api/companies` | Form 4 insider activity (`GET /{ticker}/insiders`) |
| `auth.py` | `/api/auth` | Authentication (login, register, refresh, OAuth, password reset) |
| `users.py` | `/api/users` | User profile, preferences, export, deletion |
| `admin.py` | `/api/admin` | Admin endpoints for data management |
| `compare.py` | `/api/compare` | Filing comparison endpoints (Pro, entitlement-gated) |
| `contact.py` | `/api/contact` | Contact form submission (rate-limited, Turnstile) |
| `email.py` | `/api/email` | Email management endpoints |
| `search.py` | `/api/search` | SEC full-text search via EFTS (`GET /full-text`) |
| `dashboard.py` | `/api/dashboard` | Personalized dashboard (`GET /feed`, `GET /calendar/upcoming`) |
| `hot_filings.py` | `/api` | Hot filings (`GET /hot_filings`, `POST /hot_filings/refresh`) |
| `trending.py` | `/api` | Trending tickers (`GET /trending_tickers`, `GET /trending_tickers/refresh-prices`) |
| `subscriptions.py` | `/api/subscriptions` | Subscription management + Stripe webhook (`POST /api/subscriptions/webhook`, signature-verified) |
| `saved_summaries.py` | `/api/saved-summaries` | Save/manage summaries |
| `watchlist.py` | `/api/watchlist`, `/api/waitlist` | Company watchlist + waitlist signup (`waitlist_router`) |
| `webhooks.py` | `/api` | Resend webhook handler (`POST /api/webhooks/resend`) |
| `internal.py` | `/internal` | Token-gated job triggers for Cloud Scheduler (`POST /internal/jobs/filing-scan`, `/internal/jobs/filing-digest`, `/internal/jobs/backfill-facts`) |
| `sitemap.py` | `/` | XML sitemap generation (`GET /sitemap.xml`) |

### Other Key Files

| File | Purpose |
|------|---------|
| `backend/prompts/*.md` | System prompts for 10-K/10-Q analysis |
| `backend/scripts/deploy_check.py` | Pre-deployment validation script |
| `backend/scripts/validate_db_performance.py` | PostgreSQL performance benchmarking |
| `backend/tests/smoke/test_critical_paths.py` | Critical path smoke tests (18 tests) |
| `frontend/lib/api/client.ts` | API client with smart URL detection |
| `frontend/components/SummarySections.tsx` | Summary display component |

## Architecture Patterns

### Backend
- **Service Layer Pattern:** Routers handle HTTP, services contain business logic
- **Async/Await:** All I/O operations are async (SEC API, OpenAI, database)
- **Streaming Responses:** SSE for long-running summary generation with 3s heartbeats
- **Rate Limiting:** SEC EDGAR: 10 req/sec with exponential backoff
- **Caching:** Redis for XBRL data (24h TTL), filing content, markdown cache
- **Fallback System:** `fallback_summary.py` generates summaries when AI fails
- **Audit Logging:** Tracks user actions for GDPR compliance
- **Batch Transactions:** Database commits are batched outside loops for performance (see `filings.py`)
- **Model Validation:** SQLAlchemy event listeners validate NOT NULL fields before INSERT/UPDATE
- **Request Timeouts:** Per-endpoint configurable timeouts (30s default, 120s summaries)
- **Health Checks:** `/health` (basic), `/health/detailed` (DB + Redis + circuit breaker), `/metrics` (full stats)
- **Circuit Breaker Pattern:** Protects SEC EDGAR API from cascading failures:
  - States: CLOSED (normal) → OPEN (5 failures, reject fast) → HALF_OPEN (test recovery after 30s)
  - Only network errors trip circuit (timeouts, connection errors, rate limits)
  - Business errors (404, parse errors) do NOT trip circuit
  - Automatic recovery with configurable thresholds
- **Structured Logging:** JSON logs in production with correlation ID propagation:
  - `X-Correlation-ID` header auto-generated/extracted per request
  - Request context (method, path, client IP, duration) in all logs
  - Use `get_logger(__name__)` and `log_api_call()` helpers
- **Cache Helpers:** Type-safe Redis caching with TTL presets:
  - `cache_get()`, `cache_set()`, `cache_get_or_set()` for cache-aside pattern
  - `CacheTTL` enum: XBRL_DATA (24h), FILING_METADATA (6h), HOT_FILINGS (5m)
  - `CacheNamespace` for key organization (xbrl, filing, company, etc.)
  - 2-second timeout on all cache operations to prevent hanging
- **Two-Tier Caching:** XBRL data and SEC tickers use L1 (memory) + L2 (Redis):
  - L1: In-memory cache with LRU eviction (max 1000 entries) and `asyncio.Lock` protection
  - L2: Redis cache for persistence and cross-instance sharing
  - Graceful fallback to stale L1 cache on Redis/network failures
  - `get_xbrl_cache_stats()` returns both `l1_*` and legacy keys for compatibility
- **Thread-Safe Metrics:** Request metrics use `threading.RLock` for safe concurrent access:
  - Reentrant lock allows nested property calls without deadlock
  - All metric properties (`average_latency_ms`, `error_rate`, `requests_per_minute`) are protected
  - `record_request()` and `to_dict()` are fully thread-safe
- **Event Loop Safety:** Redis connections handle event loop changes gracefully:
  - `_reset_on_loop_change()` detects when running in a new event loop
  - Automatically resets pool/client/lock to prevent hangs on stale connections
  - Critical for test stability with Starlette TestClient

### Frontend
- **Feature-Based Structure:** `/features` groups domains (auth, companies, filings, subscriptions, summaries, watchlist, contact)
- **React Query:** Server state management with caching and auto-refetch
- **Type Safety:** Strict TypeScript throughout
- **Feature Flags:** `lib/featureFlags.ts` controls optional features
- **Error Boundaries:** `GlobalErrorBoundary`, `ChartErrorBoundary` for graceful error handling

### Key Frontend Components

| Component | Purpose |
|-----------|---------|
| `SummarySections.tsx` | Summary display with collapsible sections |
| `SummaryProgress.tsx` | Real-time progress for summary generation |
| `CompanyLogo.tsx` | Ticker-keyed company logo (Logo.dev) with an initials-monogram fallback — reused on every surface that shows a company; never a broken image or layout shift |
| `HotFilings.tsx` | Trending/hot SEC filings display |
| `TrendingCompanies.tsx` | List of trending companies |
| `TrendingTickers.tsx` | List of trending stock tickers |
| `FinancialCharts.tsx` | Financial data visualization |
| `FinancialMetricsTable.tsx` | Table display for financial metrics |
| `ComparisonMetricChart.tsx` | Filing comparison visualizations |
| `ContactForm.tsx` | Contact form component |
| `CookieConsent.tsx` | Cookie consent banner |
| `GlobalErrorBoundary.tsx` | App-wide error boundary with Sentry |
| `ChartErrorBoundary.tsx` | Error boundary for chart rendering |

## Database Models

Tables in `backend/app/models/` (core models live in `__init__.py`; the rest in submodules):
- `User` - Authentication, preferences, `is_admin` flag
- `OAuthAccount` / `OAuthState` - Social login (Google, Apple) provider links + short-lived state tokens
- `RefreshToken` - Single-use refresh tokens with rotation chain and audit context (`refresh_token.py`)
- `Company` - CIK, ticker, name, industry
- `Filing` - SEC filings (10-K, 10-Q, 8-K, etc.)
- `Summary` - AI-generated summaries
- `SavedSummary` - User-saved summaries
- `Watchlist` - User company watchlists (with alert tracking)
- `UserUsage` - Per-month summary/QA generation count for rate limiting
- `UserSearch` - User search history tracking
- `FinancialFact` - Normalized standardized XBRL metrics for peer/time-series queries (`financial_fact.py`)
- `NotificationPreferences` / `NotificationLog` - New-filing alert opt-ins + dedup ledger (`notifications.py`)
- `Subscription` / `StripeEvent` - Billing state (Stripe sync) + webhook idempotency ledger (`subscription.py`)
- `WaitlistSignup` - Waitlist signups with referral codes and priority scoring (`waitlist.py`)
- `ContactSubmission` - Contact form submissions with status tracking (`contact.py`)
- `AuditLog` - User action audit trail, GDPR compliance (`audit_log.py`)
- `FilingContentCache` - Cached filing content with markdown
- `SummaryGenerationProgress` - Real-time generation progress tracking

## Admin Features

Admin endpoints require `is_admin=True` on the user account. Available at `/api/admin/`:

| Endpoint | Purpose |
|----------|---------|
| `POST /email/test` | Send a test email via Resend (diagnoses email config; defaults to admin's own address) |
| `DELETE /filing/{id}/summary` | Delete summary for a filing |
| `DELETE /filing/{id}/xbrl` | Clear XBRL cache for a filing |
| `DELETE /filing/{id}/reset` | Full reset (summary, XBRL, content cache, progress) |
| `POST /xbrl/clear-memory-cache` | Clear in-memory XBRL cache |
| `GET /xbrl/cache-stats` | View XBRL cache statistics |
| `GET /filings/audit-xbrl` | Audit filings for stale XBRL data |
| `POST /filings/bulk-reset-stale` | Bulk reset stale filings (supports dry_run) |

## Environment Variables

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
ENABLE_FPI_FILINGS=false                      # Foreign private issuer (ADR) filings: list 20-F/6-K/40-F on the company page (page-scoped; default off — see tasks/fpi-support-roadmap.md)

# Copilot ("Ask this Filing" — Pro-only grounded Q&A)
COPILOT_MONTHLY_QUESTION_CAP=1000
COPILOT_MAX_TOKENS=1200
COPILOT_CONTEXT_CHAR_CAP=120000

# Auth & Security
SECRET_KEY=...                    # JWT signing (recommended: 64+ chars)
ACCESS_TOKEN_EXPIRE_MINUTES=30    # Short-lived; frontend silently refreshes
REFRESH_TOKEN_EXPIRE_DAYS=30      # Opaque, rotated, stored hashed
PASSWORD_MIN_LENGTH=12
PWNED_PASSWORD_CHECK_ENABLED=true # Screen new passwords against HaveIBeenPwned (fails open)
TURNSTILE_SECRET_KEY=...          # Cloudflare Turnstile bot defense (no-op/dark when unset)
INTERNAL_JOB_TOKEN=...            # Shared secret for /internal/jobs/* (endpoints 503 when unset)
ENABLE_GUEST_DAILY_QUOTA=false    # Per-IP daily summary cap for anonymous users (fails open)
GUEST_DAILY_SUMMARY_LIMIT=3

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
REVERSE_TRIAL_ENABLED=false       # Grant full Pro for N days on signup, no card
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

# External APIs - EarningsWhispers
EARNINGS_WHISPERS_API_BASE=https://www.earningswhispers.com/api

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
NEXT_PUBLIC_ENABLE_CALENDAR=true|false             # Earnings calendar (requires FMP_API_KEY)
NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY=true|false     # Form 4 insider activity panel
NEXT_PUBLIC_ENABLE_COMPARE=true|false              # Multi-filing Compare (off: nav/CTA hidden + /compare routes 404)
NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY=true|false    # Gate summary generation behind auth
WAITLIST_MODE=...                                  # Server-side waitlist gating (not NEXT_PUBLIC_)
```

## Testing

- **Backend:** pytest + pytest-asyncio, AsyncMock for async services
- **Frontend:** Vitest (unit), Playwright (E2E), Testing Library (components)

### Test Markers

Custom pytest markers defined in `backend/tests/conftest.py`:
- `@pytest.mark.smoke` - Critical path validation tests
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.requires_db` - Tests requiring database (skip gracefully if unavailable)
- `@pytest.mark.slow` - Long-running tests

### Key Test Files

**Smoke Tests (`backend/tests/smoke/`):**
- `test_critical_paths.py` - 18 smoke tests for critical paths

**Unit Tests (`backend/tests/unit/`):** (50+ files; representative selection below)
- `test_circuit_breaker.py` - 14 circuit breaker pattern tests
- `test_two_tier_cache.py` - LRU eviction, concurrent access, stress tests
- `test_event_loop_safety.py` - Event loop detection, Redis connection safety
- `test_json_repair.py` - JSON repair functionality for malformed AI responses
- `test_openai_service_retry.py` - OpenAI service retry logic and error handling
- `test_stocktwits_fmp.py` - Stocktwits and FMP integration tests
- Newer feature coverage: `test_copilot.py`, `test_copilot_tools.py`, `test_entitlements.py`,
  `test_facts_service.py`, `test_peers_service.py`, `test_insider_service.py`,
  `test_notification_service.py`, `test_filing_scan.py`, `test_guest_quota.py`,
  `test_turnstile.py`, `test_stripe_webhook.py`, `test_auth_flow.py`, `test_apple_signin.py`,
  `test_sec_full_text_search.py`, `test_dashboard_feed.py`, `test_provenance_service.py`

**Integration Tests (`backend/tests/integration/`):**
- `test_summaries_flow.py` - Summary generation E2E
- `test_extra_cache_logic.py` - Additional cache scenarios and edge cases
- `test_stream_latency.py` - SSE streaming latency and performance
- `test_summary_stream_heartbeat.py` - Heartbeat behavior in streaming responses

**Performance Tests (`backend/tests/performance/`):**
- `test_concurrent_streams.py` - Concurrent SSE stream load testing

**Other Tests:**
- `backend/tests/test_summary_quality.py` - Output quality validation
- `backend/tests/test_edgar_services.py` - EDGAR service tests
- `frontend/__tests__/guards.test.ts` - Route guard tests
- `frontend/tests/e2e/` - Playwright E2E specs (auth, dashboard, filing render)
- `frontend/tests/unit/` - Vitest unit specs (formatters, summary stream, markdown rendering)

### Test Configuration

The `backend/tests/conftest.py` automatically:
- Sets mock environment variables for tests
- Sets `SKIP_REDIS_INIT=true` to bypass Redis initialization
- Registers custom pytest markers

### Verification Scripts

Located in `backend/scripts/`:
- `deploy_check.py` - Pre-deployment validation (env vars, DB, dependencies)
- `validate_db_performance.py` - PostgreSQL performance benchmarking
- `verify_extraction_standalone.py` - Test XBRL extraction against live SEC data
- `verify_extraction_mock.py` - Tests XBRL extraction with mock data
- `verify_startup_config.py` - Detailed startup configuration verification
- `test_startup.py` - Validates application startup configuration
- `debug_extraction.py` - Debug regex patterns for extraction
- `fix_null_sec_urls.py` - Repair filings with NULL sec_url values (see Data Integrity below)
- `backfill_facts.py` - Backfill the `financial_fact` table from cached/parsed XBRL
- `filing_scan.py` - Scan for new filings on watched companies (alerts pipeline)
- `pregenerate_examples.py` - Pre-generate example summaries (weekly refresh cron)
- `verify_insider_extraction.py` - Verify Form 4 insider extraction against live SEC data

### AI Evals

`backend/evals/` holds the AI eval harness (golden sets, LLM judge, copilot scorers) used to gate
model/prompt changes before flipping flags like `AI_FAST_MODEL` or `USE_STRUCTURED_OUTPUT`. See
`backend/evals/RUNBOOK.md`.

## Data Integrity

### Filing Model Validation

The `Filing` model has NOT NULL constraints on `sec_url` and `document_url`. SQLAlchemy event listeners in `backend/app/models/__init__.py` enforce these at the Python level:

- **`before_insert`**: Validates `sec_url` and `document_url` are not None. Auto-generates `sec_url` if missing but `accession_number` exists.
- **`before_update`**: Prevents setting `sec_url` to None.

### SEC URL Generation

SEC filing URLs follow the format:
```
https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/
```

Where:
- `{cik}` = Company CIK with leading zeros stripped (e.g., `320193` not `0000320193`)
- `{accession}` = Accession number with dashes removed (e.g., `000032019323000077`)

This is generated in `backend/app/services/edgar/client.py:_transform_filing()`.

### Fixing Corrupt Data

If filings with NULL `sec_url` exist (causes `PendingRollbackError`), run:

```bash
# Dry run - see what would be fixed
python scripts/fix_null_sec_urls.py

# Apply fixes
python scripts/fix_null_sec_urls.py --execute

# Fix specific ticker
python scripts/fix_null_sec_urls.py --ticker BMRN --execute
```

## Health Check & Monitoring Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /health` | Basic health check for load balancers | `{"status": "healthy"}` |
| `GET /health/detailed` | Detailed check with DB + Redis + circuit breaker | See example below |
| `GET /metrics` | Application metrics for monitoring dashboards | See metrics response below |

### Detailed Health Check Response

```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "healthy": true,
      "latency_ms": 2.45
    },
    "redis": {
      "healthy": true,
      "latency_ms": 1.12
    },
    "sec_edgar_circuit": {
      "state": "closed",
      "healthy": true,
      "stats": {
        "total_requests": 1500,
        "success_rate": 98.5,
        "rejected_requests": 0
      }
    }
  },
  "timestamp": 1706454000.123
}
```

### Metrics Endpoint Response

```json
{
  "timestamp": "2024-01-29T12:34:56Z",
  "app": {"name": "EarningsNerd API", "version": "1.0.0", "environment": "production"},
  "requests": {
    "total_requests": 5432,
    "successful_requests": 5201,
    "average_latency_ms": 45.23,
    "error_rate_percent": 4.25,
    "requests_per_minute": 12
  },
  "circuit_breaker": {"sec_edgar": {"state": "closed", "stats": {...}}},
  "cache": {
    "redis": {"healthy": true, "hit_rate": 84.75, "hits": 1200, "misses": 215},
    "xbrl_l1": {
      "total_entries": 450,
      "valid_entries": 445,
      "max_size": 1000,
      "utilization_percent": 45.0,
      "hits": 3200,
      "misses": 800,
      "hit_rate": 80.0,
      "evictions": 50
    }
  },
  "thread_pool": {"edgar": {"max_workers": 4, "threads_created": 3}},
  "database": {"pool_size": 10, "checked_in": 8, "checked_out": 2}
}
```

**Status codes:**
- `200` with `status: healthy` - All dependencies operational
- `200` with `status: degraded` - Non-critical dependency (Redis) unavailable
- `503` with `status: unhealthy` - Critical dependency (database) unavailable

## Operational Runbook

### Cache Management

**L1 (In-Memory) Cache:**
- Max 1000 entries with LRU eviction
- 24-hour TTL
- Check stats: `GET /metrics` → `cache.xbrl_l1`
- Clear via admin: `POST /api/admin/xbrl/clear-memory-cache`

**L2 (Redis) Cache:**
- Persistent across restarts
- Shared across instances
- Check stats: `GET /metrics` → `cache.redis`
- Clear pattern: Use Redis CLI `SCAN` + `DEL` for bulk deletion

**Cache Pressure Indicators:**
- `l1_utilization_percent > 90%` - Cache is near capacity, expect more evictions
- `l1_evictions` increasing rapidly - High churn, consider increasing `_cache_max_size`
- `l1_hit_rate < 50%` - Poor cache effectiveness, review access patterns
- Look for `cache_eviction` events in logs for structured eviction details

### Circuit Breaker Management

**States:**
- `closed` - Normal operation, all requests pass through
- `open` - Failing fast, rejecting requests (check SEC EDGAR status)
- `half_open` - Testing recovery, limited requests allowed

**Actions:**
- If stuck in `open`: Check SEC EDGAR status, network connectivity
- Manual reset (if needed): Restart application or use admin endpoint
- Check stats: `GET /metrics` → `circuit_breaker.sec_edgar`

### Common Issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| Tests hang for 30+ minutes | Stale Redis connections from previous event loop | Fixed by `_reset_on_loop_change()` - update to latest code |
| `RuntimeError: Lock bound to different event loop` | asyncio.Lock created in wrong loop | Use lazy lock initialization pattern |
| High memory usage | L1 cache unbounded | Check `_cache_max_size` is set (default 1000) |
| Slow health checks | Sync DB check blocking event loop | Use `run_in_executor()` for DB operations |
| Metrics deadlock | Using `threading.Lock` with nested calls | Use `threading.RLock` for reentrant locking |

### Performance Tuning

**L1 Cache Size:**
```python
# In xbrl_service.py
_cache_max_size = 1000  # Increase for more memory, fewer evictions
```

**Redis Timeouts:**
```python
# In redis_service.py
CACHE_OPERATION_TIMEOUT = 2.0  # Increase if Redis is slow
```

**Thread Pool Size:**
```python
# In edgar/config.py
EDGAR_THREAD_POOL_SIZE = 4  # Increase for more concurrent SEC API calls
```

### Monitoring Alerts (Suggested Thresholds)

| Metric | Warning | Critical |
|--------|---------|----------|
| `cache.xbrl_l1.utilization_percent` | > 80% | > 95% |
| `cache.redis.healthy` | - | `false` |
| `circuit_breaker.sec_edgar.state` | `half_open` | `open` |
| `requests.error_rate_percent` | > 5% | > 15% |
| `database.checked_out` | > 8 | = pool_size |

## Request Timeout Configuration

Per-endpoint timeouts configured in `backend/main.py`:

| Endpoint Pattern | Timeout |
|------------------|---------|
| `/api/summaries/` | 120s |
| `/api/filings/` | 60s |
| `/health` | 5s |
| Default | 30s |

Streaming endpoints (`*stream*`, `*/progress`) are excluded from timeout middleware.

## API Conventions

- All API routes prefixed with `/api/` (admin routes at `/api/admin/`)
- JWT auth via `Authorization: Bearer <token>` header
- Streaming endpoints use Server-Sent Events (SSE)
- JSON responses with Pydantic schema validation

## Code Style

- **Python:** Type hints required, async/await for I/O, Pydantic validation
- **TypeScript:** Strict mode, interfaces for API responses, React hooks patterns
- **Both:** Comprehensive error handling, no raw SQL (use SQLAlchemy ORM)

## Design System (frontend)

**Canonical reference: `frontend/DESIGN_SYSTEM.md`** — read it before any UI work and link it in
subagent briefs for UI tasks. Token *definitions* live in `frontend/tailwind.config.js`. Non-negotiables:

- **Brand = ONE Sage accent in both themes** (the sage/slate split is retired). `mint-*`, `emerald-*`,
  `primary-*` (back-compat mint alias), and `green/blue/sky/teal/cyan/indigo-*` are **not** brand.
  `brand.DEFAULT #4F7A63` is a **fill only**; accent text/links = `brand.strong` (light) /
  `brand.strong-dark` (navy); tints = `brand.weak` bg + `brand.strong` text.
- **Primary button** — light: white label on `bg-brand`, hover `brand.strong`, active `brand.emphasis`.
  Dark: **navy-ink label on `brand.dark`**, hover brightens to `strong-dark`, active presses to
  `fill-dark`. White-on-`fill-dark` is 3.7:1 — never revert to it.
- **Contrast is audited against the warm cream `#F4F3EE`, not white.** Financial deltas as text use
  `gain.text #15803D` / `loss.text #B91C1C`; the 600-level `gain.light`/`loss.light` are
  graphic/chip-only (3:1 non-text floor). State colors: success `#15803D`, warning `#92400E`,
  error `#B91C1C` + `error.emphasis #991B1B` (destructive hover). Focus-visible =
  `shadow-ring-brand` / `shadow-ring-brand-dark`; destructive + invalid fields use `shadow-ring-error`.
- **Type v2 (fixed roles — the font switcher is retired):** headings = Inter WITH the `opsz` axis,
  weight 600, one theme-aware ink via `--heading-color` (this supersedes the old "no global heading
  color" rule — the global is now theme-safe by construction); body = `-apple-system → Inter`;
  data = Geist Mono + `tabular-nums` for all money/%/tickers/excerpts. Figtree and Helvetica retired.
  Serif (Newsreader) belongs to **`.filing-reader`** only — the real filing viewer; `.markdown-body`
  (the AI summary) shares the reader layout but stays on the body sans.
- **Theme-responsive pairs everywhere** (`bg-x-light dark:bg-x-dark`) on every shared surface.
  Muted text on dark = `secondary`, never `tertiary-dark` (fails WCAG AA).
- **Cards lift, not tint**: `bg-panel-light dark:bg-panel-dark` + border + `shadow-e2 dark:shadow-none`;
  hover **brightens**, never darkens; never `hover:opacity`. `brand-weak` is a tint, not a card fill.
- **Radius scale 4/8/12/16/24** — buttons + inputs 12, chips full, cards 16.
- **Component layer:** `components/ui/*` (Button + `buttonVariants`, Badge, Input + `inputClasses`,
  Card, DataTable, Skeleton, GuidanceCard) + `components/AskFilingAnswer.tsx`. Every component defines
  default/hover/active/focus-visible/disabled/loading plus the system states (empty, skeleton via the
  shared shimmer keyframe, error). Compose these — don't restyle raw elements. Chart `Direction`
  vocabulary = `lib/financialTone.ts` (`'up' | 'down' | 'flat'`); delta text routes through
  `financialTone.directionText` (= `gain.text`/`loss.text`).
- **Motion = tokens only:** `--duration-fast/base/slow/ambient` (150/200/600/1800ms) +
  `--ease-standard/pop` — no raw ms/bezier outside `globals.css :root` + the JS mirror `lib/motion.ts`.
  Count-up is `hooks/useCountUp` (never a fade); skeleton→content = `animate-content-in` on the
  loading flip; stagger = `animate-fade-up-stagger` + `--stagger-index` (cap 4, first paint only).
  Every animation has a reduced-motion fallback via `hooks/usePrefersReducedMotion` (static bone /
  static tint / instant final value). Nothing decorative — `animate-float` is retired.
- **One global `<ThemeToggle/>`** (in `Header`); no page-level toggles. The pre-paint script in
  `app/layout.tsx` prevents theme FOUC. No decorative gradients; the only glow is the hero search.

A theme/token change is **app-wide by default** (public + authenticated). Done-gate: a repo-wide grep
for legacy brand colors returns nothing, and the result is verified in **both themes** on the preview.

## Deployment

- **Backend:** Google Cloud Run (`earningsnerd-backend`, project `earnings-nerd`, region `us-west1`).
  Containerized via `backend/Dockerfile`; schema is created at startup by `Base.metadata.create_all()`
  (no Alembic). CD: the `deploy-backend` job in `.github/workflows/ci.yml` deploys on push to main
  — gated on all test jobs, only when `backend/` changed, keyless auth via Workload Identity
  Federation (repo variables `GCP_WIF_PROVIDER` + `GCP_DEPLOYER_SA`). It also updates the weekly
  example-refresh cron (Cloud Run job `earningsnerd-pregenerate` + Cloud Scheduler, Mondays 06:00
  UTC). Manual fallback: `gcloud builds submit` from `/backend` + `gcloud run deploy` — see
  `tasks/gcp-deploy-runbook.md`.
- **Database:** Cloud SQL for PostgreSQL 15 (`earningsnerd-db`), reached via the Cloud SQL connector
  socket (`?host=/cloudsql/<connection-name>` in `DATABASE_URL`).
- **Cache:** Redis is OFF in production (`SKIP_REDIS_INIT=true`) — the two-tier cache runs L1
  (in-memory) only; Redis via docker-compose for local development. Add Memorystore if needed.
- **Secrets:** Google Secret Manager, mounted as env vars on the Cloud Run service/job.
- **Custom domain:** `api.earningsnerd.io` via Cloud Run domain mapping (Cloudflare CNAME → `ghs.googlehosted.com`, DNS-only).
- **Frontend:** Vercel (`NEXT_PUBLIC_API_BASE_URL=https://api.earningsnerd.io`).
- **Analytics:** Vercel Analytics (auto-enabled), PostHog (event tracking).

> Migrated off Render.com (June 2026). The old `render.yaml` has been removed; it was stale
> (referenced a non-existent `alembic` setup and a removed `update_contact_schema.py`).

## Claude Skills

This project includes a skill directory at `.claude/skills/` providing specialized knowledge for Claude Code.

### Available Skills

| Category | Skill | Description |
|----------|-------|-------------|
| Meta | `karpathy-guidelines` | Four behavioral principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution) — see Core Principles |
| Meta | `llm-council` | Pressure-test a high-stakes decision through 5 advisors + anonymous peer review + chairman synthesis (triggers: "council this", "pressure-test this") |
| Payments | `stripe-best-practices` | Modern Stripe API patterns |
| Infrastructure | `cloudflare-agents-sdk` | Building AI agents on Cloudflare Workers |
| Frontend | `react-best-practices` | 57 React/Next.js optimization rules |
| Frontend | `web-design-guidelines` | UI code review tool |
| Deployment | `vercel-deploy` | Deploy to Vercel with claimable URLs |
| Subagents | `voltagent` | 126+ specialized Claude Code subagents |

### Using Skills

**Automatic**: Claude can auto-load relevant skills based on context (e.g., Stripe skill when discussing payments).

**Manual**: Invoke via slash command:
```
/stripe-best-practices
/react-best-practices
```

### Adding New Skills

1. Create directory under appropriate category in `.claude/skills/`
2. Add `SKILL.md` with frontmatter:
   ```yaml
   ---
   name: my-skill
   description: Brief description
   version: 1.0.0
   author: your-name
   ---
   ```
3. Include instructions and reference content

See `.claude/skills/README.md` for full documentation.
