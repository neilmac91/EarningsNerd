# Architecture

EarningsNerd turns dense SEC filings (10-K / 10-Q) into structured, evidence-backed summaries.
This document is the human-facing overview; the exhaustive, agent-oriented reference lives in
[`CLAUDE.md`](../CLAUDE.md).

## High-level

```
┌─────────────┐      HTTPS / SSE       ┌──────────────────────────────┐
│  Next.js 16 │ ─────────────────────▶ │  FastAPI backend             │
│  (Vercel)   │ ◀───────────────────── │  (Google Cloud Run)          │
└─────────────┘   cookie-based JWT     └──────────────────────────────┘
                                          │        │            │
                              ┌───────────┘        │            └───────────┐
                              ▼                     ▼                        ▼
                     ┌───────────────┐     ┌────────────────┐      ┌────────────────┐
                     │ SEC EDGAR     │     │ Google AI Studio│      │ PostgreSQL 15  │
                     │ (edgartools)  │     │ (Gemini, via    │      │ (Cloud SQL)    │
                     │ + XBRL        │     │  OpenAI-compat) │      │                │
                     └───────────────┘     └────────────────┘      └────────────────┘
```

- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind/shadcn, React Query for server
  state, Recharts for financial charts, PostHog + Sentry. Auth is an **HttpOnly cookie** set by the
  backend — the token is never readable by client JS.
- **Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0 ORM (no raw SQL), async I/O throughout.
- **AI:** an OpenAI-*compatible* client pointed at **Google AI Studio**; default model
  `gemini-3.1-pro-preview` (`backend/app/config.py`). Not OpenAI/GPT-4.
- **Caching:** two-tier (L1 in-memory LRU + L2 Redis). **Redis is off in production**, so prod runs
  L1-only; Redis is used for local dev via docker-compose.

## How a summary is generated (the core path)

The primary path is a streamed Server-Sent Events (SSE) response:

```
POST /api/summaries/filing/{id}/generate-stream        backend/app/routers/summaries.py
  1. (optional) auth + rate-limit; short-circuit if a Summary already exists
  2. StreamingResponse(stream_summary())  — hard 90s pipeline timeout
       a. Fetch filing text from SEC EDGAR  (24h FilingContentCache short-circuit)
       b. Extract XBRL financials in parallel  (edgar/xbrl_service via compat layer)
       c. Extract critical sections from the filing text (regex)
       d. Summarize with Gemini  (75s in-stage fallback → deterministic XBRL summary)
       e. Assess quality verdict + normalize facts
       f. Persist Summary + FilingContentCache; increment user usage
  3. SSE events: progress → chunk → partial → complete (or error)
```

Resilience features along this path: a **circuit breaker** in front of SEC EDGAR (network errors
trip it, business errors don't), a **token-bucket rate limiter** for SEC's 10 req/s limit, strict
**JSON-contract repair** for AI output, and a **deterministic fallback summary** when the model
fails or times out.

## Layering

- **Routers** (`app/routers/`) handle HTTP/SSE and delegate to services.
- **Services** (`app/services/`) hold business logic: AI (`openai_service.py`), summary
  orchestration, SEC/XBRL (`edgar/`), subscriptions, email, caching, metrics, logging.
- **Integrations** (`app/integrations/`) wrap external market-data APIs (Finnhub, FMP, Stocktwits,
  EarningsWhispers).
- **Models** (`app/models/`) are SQLAlchemy ORM tables; **schemas** (`app/schemas/`) are Pydantic
  request/response contracts.
- **Pipeline** (`app/../pipeline/`) is the modular SEC ETL (extract → validate → quality → write).

## Data model (core tables)

`User`, `Company`, `Filing`, `Summary`, `SavedSummary`, `Watchlist`, `UserUsage`, `UserSearch`,
`WaitlistSignup`, `ContactSubmission`, `AuditLog`, `FilingContentCache`,
`SummaryGenerationProgress`.

## Observability

- Structured JSON logging with per-request correlation IDs (`X-Correlation-ID`).
- `GET /health`, `GET /health/detailed` (DB + Redis + circuit breaker), `GET /metrics`.
- Sentry for error tracking (backend + frontend), PostHog for product analytics.

## Known architectural debt (tracked, not yet addressed)

- **Two summary pipelines** — the streaming path (`summaries.py`) and a background path
  (`summary_generation_service.py`) have diverged in partial-result caching behavior.
- **Two SEC backends** — a legacy `sec_edgar.py` still powers markdown endpoints alongside the
  newer EdgarTools-based path; the top-level `app/services/xbrl_service.py` is superseded by
  `edgar/xbrl_service.py`.

See `docs/history/plans/` for the original design and improvement plans behind these areas.
