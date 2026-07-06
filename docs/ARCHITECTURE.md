# Architecture

EarningsNerd turns dense SEC filings (10-K / 10-Q, plus 20-F/6-K behind a flag) into
structured, evidence-backed summaries and multi-period trend analysis. This is the system
map — the canonical structural reference. The agent-facing index is [`CLAUDE.md`](../CLAUDE.md);
operational runbook material is in [`docs/OPERATIONS.md`](./OPERATIONS.md); the env-var
reference is [`docs/CONFIGURATION.md`](./CONFIGURATION.md).

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
                     │ SEC EDGAR     │     │ DeepSeek        │      │ PostgreSQL 15  │
                     │ (edgartools)  │     │ (deepseek-v4-pro│      │ (Cloud SQL)    │
                     │ + XBRL        │     │  OpenAI-compat) │      │                │
                     └───────────────┘     └────────────────┘      └────────────────┘
```

- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind/shadcn, React Query for
  server state, Recharts for financial charts, PostHog + Sentry. Auth is an **HttpOnly
  cookie** set by the backend — the token is never readable by client JS.
- **Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0 ORM (no raw SQL), async I/O throughout.
- **AI:** an OpenAI-*compatible* client pointed at **DeepSeek**; default model
  `deepseek-v4-pro` (`backend/app/config.py`; ADR-0006 — previously Gemini, ADR-0002).
  Not OpenAI/GPT-4: the `OPENAI_*` naming is a compatibility shim.
- **Caching:** two-tier (L1 in-memory LRU + L2 Redis). **Redis is off in production**
  (ADR-0004) — prod runs L1-only; Redis is local-dev via docker-compose.

## How a summary is generated (the ONE orchestrator)

There is a single generation pipeline — `app/services/summary_pipeline.py`
(`stream_filing_summary`, a transport-agnostic async generator yielding plain event dicts).
Every consumer drains it:

- **User-facing:** `POST /api/summaries/filing/{id}/generate-stream`
  (`routers/summaries.py`) maps events through `to_sse()`; progress is also pollable via
  `GET .../progress`. SSE heartbeats every 3s.
- **Batch (cron/precompute/pregenerate):** `generate_summary_background()`
  (`summary_generation_service.py`) drains the same generator headless — funnel telemetry
  suppressed, `current_user=None` — used by `precompute_service.py` (the token-gated
  `/internal/jobs/precompute` trigger) and `scripts/pregenerate_examples.py` (weekly cron).
  There is **no legacy second path** (removed July 2026, S1).

```
stream_filing_summary(filing_id, ...)
  a. Fetch filing text from SEC EDGAR   (24h FilingContentCache short-circuit)
  b. Extract XBRL financials in parallel (edgar/xbrl_service, accession-aware)
  c. Extract critical sections from the filing text
  d. Summarize with the AI model         (in-stage timeout → deterministic XBRL fallback)
  e. Quality verdict via assess_quality  (9-section taxonomy, 4/9 bar, XBRL grounding)
  f. Persist Summary + FilingContentCache; increment usage (full results only)
  → events: progress → chunk → (partial|complete) | error
```

Product invariant: summaries are **filing-only** — no content from outside the chosen
filing (including prior filings) enters user-visible output. Cross-filing insight lives in
explicit surfaces (Multi-Period Analysis, change reports). `Summary.filing_id` is UNIQUE;
a losing concurrent writer returns the existing row.

Resilience on this path: a **circuit breaker** in front of SEC EDGAR (network errors trip
it; business errors and heavy local parses don't), a **token-bucket rate limiter** for
SEC's 10 req/s cap, strict **JSON-contract repair** for AI output, and a **deterministic
fallback summary** (`fallback_summary.py`) when the model fails or times out.
Thresholds/tuning: see docs/OPERATIONS.md.

## Repo layout

```
backend/
├── app/
│   ├── routers/          # HTTP/SSE only — delegate to services
│   ├── services/         # business logic (~54 modules)
│   │   ├── edgar/        # SEC EDGAR layer (client, xbrl, breaker, executor, extractors)
│   │   └── ai/           # AI internals behind the openai_service façade
│   ├── models/           # SQLAlchemy ORM (core in __init__.py, rest in submodules)
│   ├── schemas/          # Pydantic request/response contracts
│   ├── integrations/     # external market-data APIs
│   ├── utils/            # datetimes.py (aware utcnow + iso_z), numbers.py (coerce_float)
│   ├── config.py         # Pydantic Settings — ALL env access goes through it
│   └── database.py       # session management + ensure_additive_columns
├── evals/                # AI eval harness + regression gate (see evals/RUNBOOK.md)
├── prompts/              # 9 prompt files: 10k/10q/20f/6k analyst+structured, trends-analyst
├── migrations/           # idempotent SQL, re-applied on EVERY deploy (no Alembic)
├── scripts/              # operational one-offs & verification (see docs/OPERATIONS.md)
├── docs/                 # historical specs + edgartools-best-practices.md
└── tests/                # unit/ integration/ smoke/ performance/ (config: pytest.ini;
                          #   async tests use pytest-asyncio + AsyncMock)

frontend/
├── app/                  # Next.js routes (filing/[id], company/[ticker], analysis/, …)
├── components/           # chrome + ui/ ONLY (Header, Footer, theme, boundaries, logos)
│                         #   — enforced by tests/unit/componentsAllowlist.spec.ts
├── features/<domain>/    # everything else: components/ + api/ per domain
│                         #   (auth, filings, summaries, companies, analysis, dashboard,
│                         #    watchlist, calendar, settings, marketing, …)
├── lib/                  # api/client.ts (shared axios), queryKeys.ts (key registry),
│                         # financialTone.ts, motion.ts, downloadBlob.ts, featureFlags.ts,
│                         # stripInternalNotices.ts (persisted summary markdown can carry
│                         #   internal AI fallback notices — strip at every render surface)
└── tests/                # unit/**/*.spec.* + e2e/ (the only test homes)
```

## Backend service catalog (selected)

| Service | Purpose |
|---|---|
| `summary_pipeline.py` | THE summary orchestrator (see above) |
| `summary_generation_service.py` | Headless drain for batch callers + quality verdict helpers (`assess_quality`, `calculate_section_coverage`) |
| `openai_service.py` | Façade over `app/services/ai/*` — orchestration core (`summarize_filing`, `generate_structured_summary`) stays here |
| `entitlements.py` | **Single source of truth** for plan gates (Free vs Pro); defines `FREE_TIER_SUMMARY_LIMIT = 5` |
| `subscription_service.py` | Usage tracking (re-exports entitlement limits) |
| `subscription_sync.py` | Idempotent Stripe webhook → `subscriptions` table |
| `refresh_token_service.py` | Refresh-token rotation + reuse theft-detection, hashed storage |
| `oauth_verify.py` / `password_utils.py` | Google/Apple JWKS + id-token verification; bcrypt + policy (extracted from the auth router) |
| `copilot_service.py` / `copilot_tools.py` | "Ask this Filing" Pro Q&A with verifiable deep-linked citations; numeric tool-use from `financial_fact` |
| `provenance_service.py` | Trace-to-Source: verifies AI excerpts, builds deep-link citations |
| `facts_service.py` | Normalized XBRL metrics (`financial_fact`) + SEC **companyfacts** multi-period ingest (duration-window Q1–Q4 labelling, derived Q4, latest-filed-wins) |
| `trend_analysis_service.py` | Multi-Period Analysis engine: deterministic YoY/QoQ/CAGR grid, `F#` citation markers, cached streamed narrative |
| `precompute_service.py` | Idempotent per-ticker filing resolution + summary precompute (cron + internal job) |
| `change_report_service.py` | Period-over-period change report (financial deltas + risk diffs) |
| `peers_service.py` / `insider_service.py` | Peer comparison by SIC; Form 4 insider activity (`ownership_extractor.py` parses the Form 4 tables DEFENSIVELY — EdgarTools' DataFrame column casing varies across versions; don't "simplify" the guards) |
| `dashboard_feed_service.py` / `calendar_service.py` / `filing_scan_service.py` / `notification_service.py` | Personalized feed; earnings calendar; new-filing alerts (dedup); alert prefs |
| `notable_filings_service.py` | Homepage "Notable filings": market-wide EFTS scan (8-K item materiality + form weights + owned demand), serve-from-Postgres, self-omitting |
| `hot_filings.py` / `trending_service.py` / `pulse_service.py` | LEGACY (surfaces retired/flag-hidden 2026-07; teardown PR pending — see tasks/homepage-sections-review-findings.md); Filing Pulse gauge kept for roadmap A3 |
| `guest_quota.py` / `turnstile.py` / `pwned_passwords.py` | Per-IP guest cap (fail-open); Turnstile bot defense (dark when unset, fails OPEN on Cloudflare infra errors); breached-password screening |
| `fallback_summary.py` | Deterministic summary when AI fails |
| `export_service.py` | PDF/HTML export (summaries + analysis) |
| `content_cache.py` / `summary_placeholders.py` | Shared FilingContentCache upsert; the summary-not-ready detector |
| `redis_service.py` / `logging_service.py` / `metrics_service.py` / `audit_service.py` | Cache helpers + event-loop safety; correlation-ID logging; app metrics; GDPR audit trail |

### The `ai/` package (behind the `openai_service` façade)

`extraction` (section layouts + financial-data extraction), `json_repair`,
`section_recovery` (targeted LLM re-ask), `markdown_render` (deterministic non-LLM
render), `xbrl_narrative`, `bank_guards`, `normalize`, `copilot_chat`, `model_flags`.
All external imports go through `app.services.openai_service` (re-export surface pinned
by `__all__`); a pkgutil-walking test asserts no submodule can see the `User` model.

### The `edgar/` layer

`client.py` (EdgarTools calls, breaker-wrapped), `xbrl_service.py` (two-tier cached XBRL),
`compat.py` (ticker cache + document fetch), `circuit_breaker.py`, `async_executor.py`
(dedicated thread pool; `run_with_circuit_breaker` is the standard wrapper),
`instance_extractor.py` (**accession-aware**: selects facts for the filing's own reporting
period), `statement_parser.py` (pure DataFrame helpers), `sixk_extractor.py`, plus
`config.py`/`exceptions.py`/`models.py`. All sec.gov traffic goes through this layer.

### Integrations (`app/integrations/`)

`sec_api` (EFTS full-text search, keyless, index since 2001 — feeds `/api/search`, the earnings
8-K sweep, and the notable-filings scan), `alpha_vantage` (earnings calendar data; personal-use
bridge tier), `stocktwits` (trending, keyless; unused pending a license — Apr 2026 ToS §5 bars
automated extraction), `fmp` + `finnhub` (**tombstoned** — FMP's legacy API is dead and both ToS
prohibit this use; importer allowlist enforced by `test_dead_integrations_allowlist.py`, teardown
PR pending).

## API routers

| Router | Prefix | Notes |
|---|---|---|
| `summaries.py` | `/api/summaries` | SSE generation, copilot Q&A, change reports, exports |
| `filings.py` / `companies.py` | `/api/filings`, `/api/companies` | retrieval, search, details |
| `peers.py` / `insiders.py` | `/api/companies` | `/{ticker}/peers`, `/{ticker}/insiders` |
| `analysis.py` | `/api/analysis` | Multi-Period Analysis: coverage (auth), dataset + SSE narrative + PDF (Pro `can_analyze_trends` gate) |
| `auth.py` / `users.py` | `/api/auth`, `/api/users` | login/register/refresh/OAuth; profile/export/deletion |
| `subscriptions.py` | `/api/subscriptions` | management + **signature-verified** Stripe webhook |
| `watchlist.py` | `/api/watchlist` + `/api/waitlist` | exports both routers |
| `dashboard.py` / `calendar.py` | `/api/dashboard`, `/api/calendar` | feed, upcoming calendar |
| `search.py` | `/api/search` | SEC full-text search (EFTS) |
| `notable_filings.py` / `reporting_this_week.py` | `/api` | discovery surfaces (serve-from-DB, self-omitting) |
| `hot_filings.py` / `trending.py` | `/api` | LEGACY discovery endpoints (frontend unmounted/flag-hidden; teardown PR pending) |
| `saved_summaries.py` / `contact.py` / `feedback.py` / `email.py` | `/api/...` | saved items, forms (rate-limited + Turnstile), email mgmt |
| `webhooks.py` | `/api` | Resend webhook (`POST /api/webhooks/resend`, Svix-verified) |
| `admin.py` | `/api/admin` | admin surface (see docs/OPERATIONS.md) |
| `internal.py` | `/internal` | token-gated Cloud Scheduler jobs: filing-scan, filing-digest, backfill-facts, sync-companyfacts, precompute, notable-filings-scan |
| `sitemap.py` | `/` | sitemap.xml |

## Frontend architecture

- **`features/<domain>/`** owns domain components + API clients; **`components/`** is
  chrome + `ui/` only (allowlist-enforced). Key components and homes:
  `features/summaries/components/` (SummarySections + section renderers,
  FinancialMetricsTable, SummaryDisplay), `features/filings/components/` (HotFilings,
  AskFilingAnswer, copilot/), `features/companies/components/` (CompanySearch,
  TrendingTickers), `features/analysis/components/` (Multi-Period Analysis),
  `app/filing/[id]/StreamingSummaryDisplay.tsx` (live generation UX).
- **Query keys** come exclusively from `lib/queryKeys.ts` (ESLint-enforced) — one factory
  per entity, prefix-invalidation via `all()`/`list(filters)` pairs.
- **Shared HTTP** via `lib/api/client.ts` (axios: auth-refresh interceptor,
  `withCredentials`). Raw `fetch` is sanctioned only for SSE stream readers and the
  server-side Next ISR fetches (`lib/serverApi.ts`, `app/sitemap.ts`).
- **Feature flags** in `lib/featureFlags.ts`; error boundaries: `GlobalErrorBoundary`
  (Sentry) + `ChartErrorBoundary`; chrome: `CompanyLogo` (Logo.dev + monogram fallback),
  `CookieConsent`, Header/Footer/Theme*.
- Design system: `frontend/DESIGN_SYSTEM.md` is canonical and MANDATORY before UI work.

## Data model

Core models in `models/__init__.py`: `User`, `OAuthAccount`/`OAuthState`, `Company`,
`Filing`, `Summary` (UNIQUE `filing_id`), `SavedSummary`, `Watchlist`, `UserUsage`
(per-month summary/QA/analysis counts), `UserSearch`, `FilingContentCache`,
`SummaryGenerationProgress`.
Submodules: `financial_fact.py` (normalized XBRL for peers/time-series),
`trend_analysis.py` (cached Multi-Period runs keyed by company/mode/range),
`notifications.py` (prefs + dedup ledger), `refresh_token.py` (rotation chain),
`subscription.py` (`Subscription` + `StripeEvent` idempotency ledger), `waitlist.py`,
`contact.py`, `audit_log.py`. Additional tables via migrations: `invite_codes`,
`feedback`, `guest_daily_usage`, `login_attempts`, `earnings_events`.

### Data-integrity invariants

- `Filing.sec_url` / `Filing.document_url` are **NOT NULL**, enforced by SQLAlchemy event
  listeners (`before_insert` auto-generates `sec_url` from the accession;
  `before_update` refuses to null it). Repair procedure: docs/TROUBLESHOOTING.md.
- SEC archive URL format: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/`
  with CIK leading zeros stripped and accession dashes removed — built only by
  `edgar/client.py::_transform_filing()`.
- Schema: `Base.metadata.create_all()` at startup + `ensure_additive_columns`; all other
  change via idempotent SQL in `backend/migrations/` (re-applied every deploy; no Alembic).

## Patterns & invariants

- **Datetime:** tz-aware UTC via `app/utils/datetimes.utcnow()` (+ `iso_z()` for the
  legacy `…Z` wire format). A deliberate 6-site **naive** allowlist exists for the
  OAuthState/RefreshToken token-expiry columns — enforced by
  `tests/unit/test_naive_utcnow_allowlist.py`.
- **Resilience numbers:** circuit breaker CLOSED → OPEN at 5 consecutive network failures,
  HALF_OPEN retry after 30s; only network errors trip it (404s/parse errors never do).
  SEC rate limit 10 req/s token bucket + exponential backoff — per-process, so count
  service instances + cron jobs against SEC's per-IP cap.
- **Caching:** two-tier L1 (LRU, max 1000, `asyncio.Lock`) + L2 Redis with stale-L1
  fallback; `CacheTTL`: XBRL 24h, filing metadata 6h, hot filings 5m; all cache ops capped
  at 2s. Redis connections survive event-loop changes (`_reset_on_loop_change()`).
- **Logging:** structured JSON with `X-Correlation-ID` propagation; `get_logger(__name__)`
  + `log_api_call()`.
- **DB discipline:** SQLAlchemy event listeners validate NOT NULL before writes; commits
  batched outside loops; commit ownership documented per service.
- **Boundary validation:** validate external data where it enters (SEC, Stripe, AI
  responses); don't re-validate internally-produced data downstream.

## Observability

- `GET /health` (LB probe), `GET /health/detailed` (DB + Redis + breaker),
  `GET /metrics` (breaker/cache/thread-pool/DB-pool stats) — details in docs/OPERATIONS.md.
- Sentry (backend + frontend), PostHog product analytics + inference-cost telemetry
  (`copilot_inference_cost`, `analysis_inference_cost` with grounding counters),
  Vercel Analytics on the frontend (auto-enabled via `@vercel/analytics` in `app/layout.tsx`).
- The eval harness (`backend/evals/`) pins summary quality (`baseline_scores.json`) with a
  CI regression gate on AI-relevant PRs.

## Known residual debt (minor)

- `FilingContentCache.markdown_*` columns are inert legacy (dropping needs a destructive
  migration).
- Recorded follow-ups from the 2026-07 refactor (see `tasks/architecture-refactor-plan.md`
  delta log): unify the two companyfacts fetchers on the async+limiter pattern; the
  concept-list registries stay deliberately separate (orderings encode tag priority);
  `_parse_company_facts` never populates its `total_liabilities`/`cash_and_equivalents`
  buckets (pinned as characterization, fix pending).

## Decision records

The significant, hard-to-reverse decisions — and their trade-offs — are ADRs in
[`docs/adr/`](./adr/): the hosting move to Cloud Run, the AI-provider migrations
(Gemini, then DeepSeek — ADR-0002/0006), `edgartools` for SEC data, Redis-off-in-prod,
and staying on React 18 under Next 16.
