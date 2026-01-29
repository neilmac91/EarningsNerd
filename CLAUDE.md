# CLAUDE.md - EarningsNerd

## Project Overview

EarningsNerd is an AI-powered SEC filing analysis platform that transforms dense SEC filings (10-Ks and 10-Qs) into clear, actionable insights for investors. It combines SEC EDGAR data retrieval, XBRL parsing, and generative AI summarization.

## Tech Stack

**Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0, PostgreSQL 15, Redis 7
**Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, React Query
**AI:** OpenAI-compatible API (Google AI Studio gemini-2.0-flash)
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
│   ├── dashboard/        # User dashboard (watchlist, saved summaries)
│   └── layout.tsx        # Root layout with providers
├── components/           # Reusable React components
├── features/             # Domain modules (auth, companies, filings, summaries, watchlist)
│   └── */api/            # API client functions per domain
├── lib/
│   ├── api/client.ts     # Axios instance with auth interceptors
│   ├── api/types.ts      # TypeScript API types
│   └── featureFlags.ts   # Feature flag configuration
└── hooks/                # Custom React hooks
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/openai_service.py` | AI summarization logic, prompt engineering |
| `backend/app/services/summary_generation_service.py` | Summary orchestration, progress tracking |
| `backend/app/services/xbrl_service.py` | XBRL financial data extraction |
| `backend/app/services/redis_service.py` | Redis connection pooling, cache helpers, TTL config |
| `backend/app/services/logging_service.py` | Structured logging, correlation IDs, request context |
| `backend/app/services/metrics_service.py` | Application metrics for monitoring dashboards |
| `backend/app/services/edgar/circuit_breaker.py` | Circuit breaker pattern for SEC EDGAR resilience |
| `backend/app/services/audit_service.py` | Audit logging for GDPR compliance |
| `backend/app/routers/summaries.py` | Summary endpoints with SSE streaming |
| `backend/app/routers/admin.py` | Admin endpoints for data management |
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

### Frontend
- **Feature-Based Structure:** `/features` groups domains (auth, companies, filings, etc.)
- **React Query:** Server state management with caching and auto-refetch
- **Type Safety:** Strict TypeScript throughout
- **Feature Flags:** `lib/featureFlags.ts` controls optional features

## Database Models

Core tables in `backend/app/models/`:
- `User` - Authentication, preferences, `is_admin` flag
- `Company` - CIK, ticker, name
- `Filing` - SEC filings (10-K, 10-Q)
- `Summary` - AI-generated summaries
- `SavedSummary` - User-saved summaries
- `Watchlist` - User company watchlists
- `Subscription` - Stripe subscriptions
- `EmailSubscriber` - Newsletter signups
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
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SKIP_REDIS_INIT=false             # Set to true in tests to skip Redis (auto-set by conftest.py)
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
SECRET_KEY=...                    # JWT signing (recommended: 64+ chars)
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
RESEND_API_KEY=...
POSTHOG_API_KEY=...
SENTRY_DSN=...                    # Sentry error tracking DSN
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

- `backend/tests/smoke/test_critical_paths.py` - 18 smoke tests for critical paths
- `backend/tests/unit/test_circuit_breaker.py` - 14 circuit breaker pattern tests
- `backend/tests/integration/test_summaries_flow.py` - Summary generation E2E
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
  "cache": {"redis": {"healthy": true, "hit_rate": 84.75}},
  "database": {"pool_size": 10, "checked_in": 8, "checked_out": 2}
}
```

**Status codes:**
- `200` with `status: healthy` - All dependencies operational
- `200` with `status: degraded` - Non-critical dependency (Redis) unavailable
- `503` with `status: unhealthy` - Critical dependency (database) unavailable

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
