# CLAUDE.md - EarningsNerd

## Project Overview

EarningsNerd is an AI-powered SEC filing analysis platform that transforms dense SEC filings (10-Ks and 10-Qs) into clear, actionable insights for investors. It combines SEC EDGAR data retrieval, XBRL parsing, and generative AI summarization.

## Tech Stack

**Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0, PostgreSQL 15, Redis 7
**Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, React Query
**AI:** OpenAI-compatible API (Google AI Studio gemini-3-pro-preview)
**Payments:** Stripe | **Email:** Resend | **Analytics:** PostHog, Vercel Analytics | **Errors:** Sentry

## Quick Commands

### Backend (from `/backend`)
```bash
pip install -r requirements.txt                    # Install dependencies
alembic upgrade head                               # Run migrations (before tests)
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
│   ├── routers/          # API endpoints (auth, companies, filings, summaries, admin, etc.)
│   ├── services/         # Business logic layer
│   │   ├── edgar/        # SEC EDGAR integration (circuit_breaker, client, xbrl_service)
│   │   ├── logging_service.py   # Structured logging with correlation IDs
│   │   ├── metrics_service.py   # Application metrics aggregation
│   │   ├── redis_service.py     # Connection pooling, cache helpers, health checks
│   │   └── openai_service.py    # AI summarization logic
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic validation schemas
│   ├── integrations/     # External APIs (finnhub, earnings_whispers)
│   ├── config.py         # Pydantic Settings (env validation)
│   └── database.py       # DB session management
├── tests/                # pytest tests (unit/, integration/, performance/)
├── prompts/              # AI system prompts (10k-analyst-agent.md, 10q-analyst-agent.md)
├── scripts/              # Verification and debug scripts
├── migrations/           # Alembic migrations
└── main.py               # FastAPI app entry point

/frontend
├── app/                  # Next.js App Router pages
│   ├── (auth)/           # Login/register routes
│   ├── company/[ticker]/ # Company detail pages
│   ├── filing/[id]/      # Filing summary pages
│   ├── compare/          # Filing comparison pages
│   ├── dashboard/        # User dashboard (watchlist, saved summaries)
│   ├── contact/          # Contact form page
│   └── layout.tsx        # Root layout with providers
├── components/           # Reusable React components (34+ components)
├── features/             # Domain modules (auth, companies, filings, summaries, watchlist, contact)
│   └── */api/            # API client functions per domain
├── lib/
│   ├── api/client.ts     # Axios instance with auth interceptors
│   ├── api/types.ts      # TypeScript API types
│   └── featureFlags.ts   # Feature flag configuration
└── hooks/                # Custom React hooks
```

## Key Files

### Backend Services

| File | Purpose |
|------|---------|
| `backend/app/services/openai_service.py` | AI summarization logic, prompt engineering |
| `backend/app/services/summary_generation_service.py` | Summary orchestration, progress tracking |
| `backend/app/services/sec_client.py` | High-level facade combining SEC EDGAR, rate limiter, filing parser, markdown serializer |
| `backend/app/services/filing_parser.py` | Parses SEC filings into semantic structures using sec-parser |
| `backend/app/services/markdown_serializer.py` | Converts parsed SEC filings to clean Markdown for LLM consumption |
| `backend/app/services/subscription_service.py` | User subscription usage tracking (FREE_TIER_SUMMARY_LIMIT = 5) |
| `backend/app/services/rate_limiter.py` | In-memory sliding window rate limiter |
| `backend/app/services/sec_rate_limiter.py` | SEC EDGAR-specific rate limiter with token bucket and exponential backoff |
| `backend/app/services/email_service.py` | Resend API wrapper for email delivery with HTML templates |
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

### External Integrations (`backend/app/integrations/`)

| File | Purpose |
|------|---------|
| `finnhub.py` | News sentiment analysis (buzz_ratio, articles_in_last_week, bullish_percent) |
| `earnings_whispers.py` | Earnings surprise signals and company earnings data |

### API Routers (`backend/app/routers/`)

| File | Prefix | Purpose |
|------|--------|---------|
| `summaries.py` | `/api/summaries` | Summary endpoints with SSE streaming |
| `filings.py` | `/api/filings` | Filing retrieval and management |
| `companies.py` | `/api/companies` | Company search and details |
| `auth.py` | `/api/auth` | Authentication (login, register, refresh) |
| `users.py` | `/api/users` | User profile, export, deletion |
| `admin.py` | `/api/admin` | Admin endpoints for data management |
| `compare.py` | `/api/compare` | Filing comparison endpoints |
| `contact.py` | `/api/contact` | Contact form submission |
| `email.py` | `/api/email` | Email management endpoints |
| `hot_filings.py` | `/api` | Hot filings (`GET /hot-filings`, `POST /refresh-hot-filings`) |
| `trending.py` | `/api` | Trending tickers (`GET /trending-tickers`) |
| `subscriptions.py` | `/api/subscriptions` | Subscription management |
| `saved_summaries.py` | `/api/saved-summaries` | Save/manage summaries |
| `watchlist.py` | `/api/watchlist` | Company watchlist management |
| `webhooks.py` | `/api` | Resend webhook handlers (`POST /webhooks/resend`) |
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
- **Feature-Based Structure:** `/features` groups domains (auth, companies, filings, summaries, watchlist, contact)
- **React Query:** Server state management with caching and auto-refetch
- **Type Safety:** Strict TypeScript throughout
- **Feature Flags:** `lib/featureFlags.ts` controls optional features
- **Error Boundaries:** `GlobalErrorBoundary`, `ChartErrorBoundary` for graceful error handling

### Key Frontend Components

| Component | Purpose |
|-----------|---------|
| `SummarySections.tsx` | Summary display with collapsible sections |
| `SummaryProgress.tsx` | Real-time progress for summary generation |
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

Core tables in `backend/app/models/`:
- `User` - Authentication, preferences, `is_admin` flag
- `Company` - CIK, ticker, name
- `Filing` - SEC filings (10-K, 10-Q)
- `Summary` - AI-generated summaries
- `SavedSummary` - User-saved summaries
- `Watchlist` - User company watchlists
- `UserUsage` - Per-month summary generation count for rate limiting
- `UserSearch` - User search history tracking
- `WaitlistSignup` - Waitlist signups with referral codes and priority scoring
- `ContactSubmission` - Contact form submissions with status tracking
- `AuditLog` - User action audit trail (GDPR compliance)
- `FilingContentCache` - Cached filing content with markdown
- `SummaryGenerationProgress` - Real-time generation progress tracking

## Admin Features

Admin endpoints require `is_admin=True` on the user account. Available at `/api/admin/`:

| Endpoint | Purpose |
|----------|---------|
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

# AI Configuration
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_DEFAULT_MODEL=gemini-3-pro-preview  # Primary AI model
RECOVERY_MAX_CONCURRENCY=3        # Max concurrent calls for section recovery

# Auth & Security
SECRET_KEY=...                    # JWT signing (recommended: 64+ chars)

# Stripe
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...

# Email (Resend)
RESEND_API_KEY=...

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
NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS=true|false
NEXT_PUBLIC_ENABLE_SECTION_TABS=true|false
```

## Testing

- **Backend:** pytest + pytest-asyncio, AsyncMock for async services
- **Frontend:** Vitest (unit), Playwright (E2E), Testing Library (components)

### Test Markers

Custom pytest markers defined in `backend/tests/conftest.py`:
- `@pytest.mark.smoke` - Critical path validation tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.requires_db` - Tests requiring database (skip gracefully if unavailable)
- `@pytest.mark.slow` - Long-running tests

### Key Test Files

**Smoke Tests (`backend/tests/smoke/`):**
- `test_critical_paths.py` - 18 smoke tests for critical paths

**Unit Tests (`backend/tests/unit/`):**
- `test_circuit_breaker.py` - 14 circuit breaker pattern tests
- `test_two_tier_cache.py` - LRU eviction, concurrent access, stress tests
- `test_event_loop_safety.py` - Event loop detection, Redis connection safety
- `test_json_repair.py` - JSON repair functionality for malformed AI responses
- `test_openai_service_retry.py` - OpenAI service retry logic and error handling

**Integration Tests (`backend/tests/integration/`):**
- `test_summaries_flow.py` - Summary generation E2E
- `test_extra_cache_logic.py` - Additional cache scenarios and edge cases
- `test_stream_latency.py` - SSE streaming latency and performance
- `test_summary_stream_heartbeat.py` - Heartbeat behavior in streaming responses

**Other Tests:**
- `backend/tests/test_xbrl_extraction.py` - XBRL parsing validation
- `backend/tests/test_summary_quality.py` - Output quality validation
- `frontend/__tests__/guards.test.ts` - Route guard tests

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
- `verify_extraction_fix.py` - Full verification with app config
- `verify_extraction_mock.py` - Tests XBRL extraction with mock data
- `verify_xbrl_fallback.py` - Verifies XBRL fallback mechanisms
- `verify_startup_config.py` - Detailed startup configuration verification
- `test_startup.py` - Validates application startup configuration
- `debug_extraction.py` - Debug regex patterns for extraction
- `fix_null_sec_urls.py` - Repair filings with NULL sec_url values (see Data Integrity below)

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

## Deployment

- **Backend:** Render.com (see `render.yaml`)
- **Frontend:** Vercel or Firebase Hosting
- **Database:** Managed PostgreSQL
- **Cache:** Managed Redis
- **Analytics:** Vercel Analytics (auto-enabled), PostHog (event tracking)

## Claude Skills

This project includes a skill directory at `.claude/skills/` providing specialized knowledge for Claude Code.

### Available Skills

| Category | Skill | Description |
|----------|-------|-------------|
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
