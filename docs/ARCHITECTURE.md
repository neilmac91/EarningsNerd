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
├── migrations/           # idempotent SQL, applied once via the migration_ledger table (ADR-0007; no Alembic)
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
| `subscription_service.py` | Completed-use SQL counter increments; absent monthly buckets lock/re-read the parent User before creation; transaction-local lock waits; re-exports entitlement limits |
| `login_lockout.py` | Atomic failed-login upserts keyed by peppered email hash; existing reset/lock windows; success clear stays in the caller transaction |
| `subscription_sync.py` | Stripe identity/state mapping and event-ledger helpers |
| `subscription_webhook_service.py` | Worker-owned webhook transactions, per-account PostgreSQL locks, current-bound-ID created/updated reconciliation and post-commit analytics; cross-ID chronology remains separate |
| `stripe_subscription_reader.py` | Dedicated exact-ID provider read, validated identity/status/consumed optional fields, zero retries and connect/read inactivity limits; failure rolls back the event |
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
| `pulse_service.py` | Filing Pulse gauge (pure scoring; kept for roadmap A3). Its original producer — the FMP/Finnhub-backed hot-filings scorer — and the Stocktwits/FMP trending pipeline were torn down 2026-09 (WS-8a) |
| `turnstile.py` / `pwned_passwords.py` | Turnstile bot defense (dark when unset, fails OPEN on Cloudflare infra errors); breached-password screening |
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

`client.py` (EdgarTools calls, breaker-wrapped), `xbrl_service.py` (persisted accession snapshot first, then two-tier cached XBRL),
`compat.py` (ticker cache + document fetch), `circuit_breaker.py`, `async_executor.py`
(dedicated thread pool; `run_with_circuit_breaker` is the standard wrapper),
`instance_extractor.py` (**accession-aware**: selects facts for the filing's own reporting
period), `statement_parser.py` (pure DataFrame helpers), `sixk_extractor.py`, plus
`config.py`/`exceptions.py`/`models.py`. Breaker coverage is selective: the XBRL primary path
uses plain timeouts for local parsing, and its raw companyfacts fallback uses a single limiter
wait without the breaker. Existing raw-HTTP paths outside the layer — `SECFullTextSearchClient`
in `app/integrations/sec_api.py` and companyfacts fetching in `app/services/facts_service.py` —
use shared limiter/backoff without the breaker. Preserve the existing transport owners;
do not add raw-HTTP SEC bypasses outside them, even if paced.
`test_sec_gov_importers_allowlist.py` checks URL-literal homes and pure-builder/Settings HTTP
import exclusions; dynamic URLs and the full request graph are outside that gate's proof.

### Integrations (`app/integrations/`)

`sec_api` (EFTS full-text search, keyless, index since 2001 — feeds `/api/search`, the earnings
8-K sweep, and the notable-filings scan), `alpha_vantage` (earnings calendar data; personal-use
bridge tier). `fmp`, `finnhub` and `stocktwits` were **deleted** in 2026-09 (WS-8a): FMP's legacy
API is dead and all three ToS bar this use. `test_dead_integrations_allowlist.py` keeps an empty
importer allow-list and asserts the modules stay gone, so none can be resurrected without editing
that gate. (`FMP_API_KEY` survives only for the operator script `scripts/refresh_index_membership.py`.)

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
| `saved_summaries.py` / `contact.py` / `feedback.py` / `email.py` | `/api/...` | saved items, forms (rate-limited + Turnstile), email mgmt |
| `webhooks.py` | `/api` | Resend webhook (`POST /api/webhooks/resend`, Svix-verified) |
| `admin.py` | `/api/admin` | admin surface (see docs/OPERATIONS.md) |
| `internal.py` | `/internal` | token-gated Cloud Scheduler jobs: filing-scan, filing-digest, backfill-facts, sync-companyfacts, precompute, notable-filings-scan |
| `sitemap.py` | `/` | sitemap.xml |

## Frontend architecture

- **`features/<domain>/`** owns domain components + API clients; **`components/`** is
  chrome + `ui/` only (allowlist-enforced). Key components and homes:
  `features/summaries/components/` (SummarySections + section renderers,
  FinancialMetricsTable, SummaryDisplay), `features/filings/components/` (NotableFilings,
  AskFilingAnswer, copilot/), `features/companies/components/` (CompanySearch),
  `features/analysis/components/` (Multi-Period Analysis),
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
`contact.py`, `audit_log.py`, `job_run.py` (`earningsnerd_job_runs`, independent scheduled-job attempts). Additional tables via migrations: `invite_codes`,
`feedback`, `login_attempts`, `earnings_events` (plus the orphaned `guest_daily_usage` —
unused since generation became account-required in #619; kept because migrations are re-run-safe, never destructive).

### Data-integrity invariants

- Domestic annual/quarterly amendments are ingested alongside originals. The additive
  `Filing.superseded_by_accession` column links older same-company, base-form, report-period
  rows to the newest amendment under a per-company non-key row lock. No report period means no inferred link. All ingestion paths
  call `filing_amendment_service`; Change Report orders by earlier report period, then filing
  date, preserving the selected filing's own content.
- Per-filing discrete-quarter facts retain fiscal labels anchored to the XBRL filing focus and
  their own distance from its report date. Comparative quarters move across fiscal years;
  non-calendar years do not use calendar-quarter labels. Missing/irregular metadata stays unknown.
  New labelled quarters demote legacy NULL-period twins; existing persisted snapshots require
  deliberate re-extraction to gain metadata they never contained. Fact writes serialize on the
  company row and preserve a known newer accession. The per-filing writer also preserves untied
  current companyfacts rows when their filing chronology cannot be established; the bulk writer
  uses the received normalizer ordering where local Filing chronology is unavailable. Older accession facts remain
  available for their own filing even when they are not the current company value.
- Per-filing reconciliation uses the calendar date of persisted `Filing.period_end_date`;
  missing dates do not invent a mismatch, and prior comparative periods are exempt. This applies
  to newly inserted identities: ordinary backfill skips existing rows and their flags. Optional
  authoritative companyfacts cross-checks can still clear local heuristic flags. There is no
  general historical flag-repair CLI; financial remediation replaces only its affected revenue/
  component concepts. A broader historical audit and scoped repair capability remains separate
  engineering work, with production execution reserved for the founder.
- Reconciliation flags follow values and the actual inputs used in growth calculations through
  analysis charts, metrics, citations and Excel exports. Citation verification is traceability,
  distinct from the financial value's reconciliation quality.

- `Filing.sec_url` / `Filing.document_url` are **NOT NULL**, enforced by SQLAlchemy event
  listeners (`before_insert` derives `sec_url` from the loaded Company's CIK + accession and
  raises when the company is not loaded — no placeholder URLs; `before_update` refuses to null
  it; both validate the URL shape, canonical archive form required on SEC hosts). Repair
  procedure: docs/TROUBLESHOOTING.md. Tests: `tests/unit/test_filing_url_listeners.py`.
- SEC archive URL format: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/`
  with CIK leading zeros stripped and accession dashes removed — built only by
  `app/utils/sec_urls.py::build_sec_archive_url()` (called from `edgar/client.py`,
  `integrations/sec_api.py`, the Filing listener and `scripts/fix_null_sec_urls.py`).
- Schema: `Base.metadata.create_all()` at startup + `ensure_additive_columns`; all other
  change via idempotent SQL in `backend/migrations/`, applied once per (filename, sha256) by
  `scripts/apply_migrations.sh` through the `migration_ledger` table (ADR-0007; no Alembic).

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

Monthly usage counter writes preserve existing first-row history and completion billing rules.
Existing buckets skip the parent User lock; first-month creation can contend with Stripe account
work, subject to `USAGE_COUNTER_LOCK_TIMEOUT_MS`. SQL increments prevent stale-session lost
updates for successfully committed calls. All old service and job writers must drain before the
first-use protocol holds fleet-wide. This does not reserve admission, repair historical duplicate
buckets or make best-effort completion metering strict billing accounting.

Failed-login recording uses the existing `login_attempts.email_hash` primary key for concurrent
insert/update and successful-clear ordering on PostgreSQL and SQLite. A failure waiting behind
a committed success clear creates a new history; after a rolled-back clear it increments the
retained history. Initial timestamps retain their database default, while updates stamp the
existing failure clock explicitly. The change counts completed failures; credential checks
already admitted before a lock are not reserved. Old revision writers must drain before their
read-modify-write path can no longer overwrite counts. Per-IP memory bounds, row retention and
new timeout/retry policy remain separate.
