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
                     │ (edgartools)  │     │ (deepseek-flash │      │ (Cloud SQL)    │
                     │ + XBRL        │     │  OpenAI-compat) │      │                │
                     └───────────────┘     └────────────────┘      └────────────────┘
```

- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind/shadcn, React Query for
  server state, Recharts for financial charts, PostHog + Sentry. Auth is an **HttpOnly
  cookie** set by the backend — the token is never readable by client JS.
- **Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0 ORM (no raw SQL), async I/O throughout.
- **AI:** an OpenAI-*compatible* client pointed at **DeepSeek**; default model
  `deepseek-flash` (`backend/app/config.py`; ADR-0008 — previously `deepseek-v4-pro`, ADR-0006; Gemini, ADR-0002).
  Not OpenAI/GPT-4: the `OPENAI_*` naming is a compatibility shim.
- **Caching:** two-tier (L1 in-memory LRU + L2 Redis). **Redis is off in production**
  (ADR-0004) — prod runs L1-only; Redis is local-dev via docker-compose.

## How a summary is generated (the ONE orchestrator)

### Durable after-response work

With `DURABLE_TASKS_ENABLED`, on-visit filing refresh/history and timed-out coverage syncs hand
identifier-only control messages to Cloud Tasks before claiming delivery. A private task-only
Cloud Run service runs one delivery at a time. Its `task_worker_main:app` entrypoint verifies
Google-signed OIDC audience and the dedicated service-account email; queue headers grant no access.
It executes existing services in a fresh Python child, killing and reaping that process at 480
seconds or on cancellation. Task acknowledgement follows successful persistence, before the
540-second dispatch and 600-second service deadlines. This bounds native threads as well as async
work. An application guard admits only one native child per worker process and rejects overlapping
delivery promptly for retry, holding that permit through kill/reap. [HTTP/1.1 client disconnects do
not reach Cloud Run containers](https://docs.cloud.google.com/run/docs/troubleshooting#client_disconnect_does_not_propagate_to_cloud_run); cleanup guarantees cover the work deadline or handler cancellation,
not all transport loss. At-least-once delivery can still repeat completed work, so existing
cache/upsert and notification ownership remain necessary. The parent opens no SQL pool or startup
schema path. Existing scheduled jobs remain primary
for fleet work; manual HTTP cohorts fan out at most 50 identifiers/pairs with stable retry names.
Forced paid precompute is rejected in durable mode because it cannot be safely replayed.

The API keeps its warm instance. Coverage retains its 20-second fast path and `syncing` polling;
the local attempt is cancelled/drained before durable handoff. Summary generation retains its
single pipeline and SSE contract. Its synchronous workers are owned and drained before releasing
generation leadership. A valid cached excerpt no longer launches a redundant document download.


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
  c. Parse critical sections locally from the fetched primary-document HTML (edgar/xbrl_sections;
                                         no SEC call; starts once (a) has the text; awaited (30 s /
                                         40 s bound) before the excerpt is built and joined with (b))
  d. Summarize with the AI model; the admission lease is counted as one usage unit when the
                                         request dispatcher signals the first provider request
                                         (in-stage timeout → deterministic XBRL fallback)
  e. Quality verdict via assess_quality  (9-section taxonomy, 4/9 bar, XBRL grounding);
                                         a partial verdict refunds the unit
  f. Persist Summary + FilingContentCache (settles the unit; a provider-side failure before
                                         this refunds it, a client disconnect never does;
                                         lease-less callers — the background drain, uncapped
                                         Pro — count full results here instead)
  → events: progress → chunk → (partial|complete) | error
```

The generator itself is a short stage map (`_stage_sequence()` in `summary_pipeline.py`) over
`app/services/summary_stages/`, one shared `GenerationRun` per generation:

| stage module | owns |
|---|---|
| `generation_run.py` | the run state (timings, lease/charge, owned tasks, filing snapshot) and the former closures: `run_sync_db`, `settle_charge`, `refund_charge`, `begin_charge`/`charge_lease` (metering at provider start), `release()` (the `finally`) |
| `admission.py` | `load_filing` (snapshot + existing-summary short-circuit), `join_or_lead` (A3 in-flight dedup), `admit` (24h cache validity, usage/fair-use gate, generation slot) |
| `fetch.py` | `fetch_document` (starts the XBRL task; cached text, 6-K exhibits, or the SEC fetch with heartbeats) |
| `enrichment.py` | `start_enrichment_tasks` (XBRL), `start_section_parse` (local parse of the fetched document), `parse_and_enrich` (progress, excerpt, bounded join) |
| `generation.py` | `generate` (provider task under the metering signal, heartbeats/previews, 75s fallback, error payload) |
| `finalize.py` | `finalize` (projection, quality verdict + measurement logs, persist, usage, telemetry, terminal events) |
| `failure.py` | `timed_out`, `failed` (the two `except` bodies) |

The stage modules reach every collaborator as `summary_pipeline.<name>` at call time (the patch
seams the tests rely on); `tests/unit/test_summary_stages_seams.py` gates that, the terminal-event
protocol and the orchestrator's length.

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
│   ├── utils/            # datetimes.py (aware utcnow, iso_z, ensure_utc, utc_from_iso), numbers.py (coerce_float)
│   ├── config.py         # Pydantic Settings — ALL env access goes through it
│   └── database.py       # session management (each engine session at UTC) + ensure_additive_columns
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
| `summary_pipeline.py` + `summary_stages/` | THE summary orchestrator (see above): the stage map, its stages and the patch seams the tests rely on |
| `summary_generation_service.py` | Headless drain for batch callers + quality verdict helpers (`assess_quality`, `calculate_section_coverage`) |
| `openai_service.py` | Façade over `app/services/ai/*` — orchestration core (`summarize_filing`, `generate_structured_summary`) stays here |
| `entitlements.py` | **Single source of truth** for plan gates (Free vs Pro); defines `FREE_TIER_SUMMARY_LIMIT = 5` |
| `subscription_service.py` | Completed-use SQL counter increments; absent monthly buckets lock/re-read the parent User before creation; transaction-local lock waits; re-exports entitlement limits |
| `login_lockout.py` | Atomic failed-login upserts keyed by peppered email hash; existing reset/lock windows; success clear stays in the caller transaction |
| `subscription_sync.py` | Stripe identity/state mapping and event-ledger helpers |
| `subscription_webhook_service.py` | Worker-owned webhook transactions, per-account PostgreSQL locks, current-bound-ID created/updated reconciliation and post-commit analytics; cross-ID chronology remains separate |
| `stripe_subscription_reader.py` | Dedicated exact-ID provider read, validated identity/status/consumed optional fields, zero retries and connect/read inactivity limits; a failed reconciliation read rolls back the event, a failed serving-Price read reports `unavailable` |
| `billing_serving_prices.py` | The public serving-charge report (`GET /api/subscriptions/prices`): what the bound Pro Prices charge, without IDs, cached per process; one read at a time, and no request waits on another's; the price-agreement checks compare it with the page (`docs/PRICING_OFFER.md`) |
| `billing_account_service.py` | The reader's `subscriptions` row (served by `GET /api/subscriptions/subscription`, counted by checkout's first-time-trial check) and the commit of a new Stripe customer id before checkout; the subscriptions router owns Stripe calls and HTTP responses |
| `refresh_token_service.py` | Refresh-token rotation + reuse theft-detection, hashed storage; every rotation and revocation of a user's tokens, a password login's mint, a password change and the account's deletion take the users row lock first |
| `oauth_verify.py` / `password_utils.py` | Google/Apple JWKS + id-token verification; bcrypt + policy (extracted from the auth router) |
| `auth_account_service.py` | Password-account persistence, verification/reset tokens and login/password writes; the auth router keeps HTTP gates, password hashing, mail and audit events |
| `oauth_account_service.py` | OAuth state, account creation/linking, refresh-token persistence and provider connections; the auth router owns provider exchange, cookies and responses |
| `user_account_service.py` | Profile updates and the database commit/rollback for account deletion; the users router owns third-party erasure and audit events |
| `user_data_export_service.py` | Read-only assembly of the account's personal-data export; the users router records the export and returns the download |
| `admin_account_service.py` | Provision a new Free account, send its password-setup link and audit the admin action; existing accounts are never changed |
| `admin_feedback_service.py` | Feedback listing, status updates and submitter-email lookup for admin triage; the router owns authorization and audit events |
| `admin_filing_service.py` | Per-filing summary/XBRL resets and stale-XBRL audit/bulk reset; the router owns authorization and error responses |
| `admin_summary_service.py` | Select and delete reset candidates or regenerate stale summaries through the single headless generation path; the router owns authorization, batch limits and responses |
| `watchlist_service.py` | Watchlist membership reads/writes and latest-filing, count, summary and generation-progress rows for insights; the watchlist router runs each route's session work, payload and release as one unit in the thread pool, and owns authentication, generation-status presentation and HTTP responses |
| `saved_summary_service.py` | Saved-summary bookmarks, notes, status and library row shaping; the router owns authentication, request validation and HTTP error mapping |
| `contact_submission_service.py` | Contact row construction and commit/refresh/rollback with the router's logger; the router owns request policy, HTTP error mapping and post-commit notifications |
| `user_notification_feed_service.py` | Sent-alert feed reads, unread counts and the seen-at write for the in-app bell; the users router owns authentication, request limits and response models |
| `company_lookup_service.py` | Company lookups, search upserts/CIK-conflict recovery and response snapshots with session release; the companies router owns SEC/quote I/O and HTTP error mapping |
| `filing_list_service.py` | Company filing-list freshness, cached reads, persistence, background refresh and on-visit history backfill, each request unit releasing its session; the filings router runs those units in the thread pool and keeps request-path SEC awaits, task scheduling/handoff, response models and error mapping |
| `filing_read_service.py` | Single/recent filing, cached-content and fundamentals reads, with payload construction and session release in one unit, which the filings router runs in the thread pool; the router owns response models/converters and missing-filing HTTP errors |
| `copilot_service.py` / `copilot_tools.py` | "Ask this Filing" Pro Q&A with verifiable deep-linked citations; numeric tool-use from `financial_fact` |
| `sitemap_service.py` | Eligible company/filing queries and bounded XML assembly; the sitemap router owns the hourly cache, single-flight lock and HTTP response |
| `provenance_service.py` | Trace-to-Source: verifies AI excerpts, builds deep-link citations |
| `facts_service.py` | Normalized XBRL metrics (`financial_fact`) + SEC **companyfacts** multi-period ingest (duration-window Q1–Q4 labelling, derived Q4, latest-filed-wins) |
| `analysis_data_access.py` | Analysis record reads and short-session ingest, metering and reservation-release units; the analysis router runs its request-session work in thread-pool units that release through `filing_list_service.release_request_session`, and keeps HTTP policy, task/stream ownership and call-time collaborator seams |
| `job_sessions.py` | Runs one job in a session of its own and closes it however the job ends, for work outside a request's `get_db` session: the internal triggers' flag-off background runs and the Resend click record; the callers keep their log lines and pass the job by an attribute resolved at call time |
| `trend_analysis_service.py` + `trend_analysis/` | Compatibility façade over domain modules: deterministic YoY/QoQ/CAGR datasets and `F#` markers, code-owned observations, validated selection and cached narrative streaming |
| `precompute_service.py` | Idempotent per-ticker filing resolution + summary precompute (cron + internal job) |
| `change_report_service.py` | Period-over-period change report (financial deltas; risk diffs withheld) plus, behind `ENABLE_SECTION_CHANGES`, the `section_changes` wording diff block |
| `section_review_service.py` | The Pro review of a filing's Item 1A wording changes (`section_reviews`): labels per content-addressed change id, completion when every change is labelled, the receipt (both texts' fingerprints, engine and extractor versions, counts, follow-ups) frozen then; a write locks the reader's row (`FOR UPDATE`) and recovers the insert race; `review_progress` gives the dashboard feed the same reconciled reading (live ids, receipt still matching); served by `routers/section_reviews.py` under `/api/summaries/filing/{id}/wording-review` behind the `section_changes` entitlement |
| `filing_section_service.py` / `section_diff.py` | Item 1A text per filing (`filing_section_text`): fetched through the SEC transport, located with edgartools' HTML parser (local), stored with status and a cached comparison summary; the watched-cohort batch the filing-scan job runs; `section_diff` is the pure paragraph-paired, word-level diff (page furniture dropped, line-wrapped typesetting re-flowed, exact/moved/fuzzy pairing, content-addressed item ids) |
| `peers_service.py` / `insider_service.py` | Peer comparison by SIC; Form 4 insider activity (`ownership_extractor.py` parses the Form 4 tables DEFENSIVELY — EdgarTools' DataFrame column casing varies across versions; don't "simplify" the guards) |
| `dashboard_feed_service.py` / `calendar_service.py` / `filing_scan_service.py` / `notification_service.py` | Personalized feed (with the Item 1A wording-change counts and the reader's review progress per card, behind `ENABLE_SECTION_CHANGES`); earnings calendar; new-filing alerts (dedup; a Pro recipient's alert and digest carry the "Risk factor wording" line when the filing's comparison is cached); alert prefs |
| `notable_filings_service.py` | Homepage "Notable filings": market-wide EFTS scan (8-K item materiality + form weights + owned demand) into Postgres; serves 10-K and 10-Q filings from companies holding a summary the filing page shows, newest first, at most six (D-046); self-omitting |
| `pulse_service.py` | Filing Pulse gauge (pure scoring; kept for roadmap A3). Its original producer — the FMP/Finnhub-backed hot-filings scorer — and the Stocktwits/FMP trending pipeline were torn down 2026-09 (WS-8a) |
| `turnstile.py` / `pwned_passwords.py` | Turnstile bot defense (dark when unset, fails OPEN on Cloudflare infra errors); breached-password screening |
| `fallback_summary.py` | Deterministic summary when AI fails |
| `export_service.py` | PDF/HTML export (summaries + analysis) |
| `content_cache.py` / `summary_placeholders.py` | Shared FilingContentCache upsert; the summary-not-ready detector |
| `redis_service.py` / `logging_service.py` / `metrics_service.py` / `audit_service.py` | Cache helpers + event-loop safety; correlation-ID logging; app metrics; GDPR audit trail |

The `trend_analysis/` package separates period coverage, formatting, series helpers, inflection
detectors, dataset construction, observation selection, citation resolution, numeric fidelity, cache
persistence and narrative streaming. `narrative.py` keeps database sessions and the provider singleton
lazily imported at call time. `trend_analysis_service.py` re-exports the original public and private
names, so the analysis router continues to resolve them through the same module.

Analysis datasets carry versioned `data_notes` from the pure `trend_analysis/data_notes.py`
builder. The web, chart downloads, PDF and Excel use the same reason groups, letters and counts;
old snapshots without this field use a presentation-only fallback. The web admits supplied notes
at the API boundary against the dataset's quality fields, rejecting malformed or mismatched
metadata rather than silently falling back. Notes do not change financial values or validation.

`presentation.py` formats selected observations after selection, preserving the model-facing
catalogue and prompt. Its `narrative_presentation` completion member binds structured red-flag
operands and UTF-16 text spans to the financial snapshot. Inline operand text remains in stored
Markdown for PDF; the web replaces those exact spans with evidence disclosures. Citation-only
concerns append to report notes without changing report counts or existing letters. The independent
`NARRATIVE_FORMAT_VERSION` controls cache and PDF compatibility; both presentation fields are
excluded from the financial fingerprint. An old format follows the existing system-invalidated
regeneration and metering path, without a schema change or bulk cache deletion.

### The `ai/` package (behind the `openai_service` façade)

`extraction` (section layouts + financial-data extraction), `json_repair`,
`section_recovery` (targeted LLM re-ask), `markdown_render` (deterministic non-LLM
render), `xbrl_narrative`, `bank_guards`, `normalize`, `copilot_chat`, `model_flags`,
`summary_finalize` (ordered post-provider phases), and `summary_prompt` (primary request
assembly and the raw schema template). Prompt assembly receives the live façade module,
so its prompt loaders, settings and schema bindings remain patchable at call time.
All external imports go through `app.services.openai_service` (re-export surface pinned
by `__all__`); a pkgutil-walking test asserts no submodule can see the `User` model.

### The `edgar/` layer

`client.py` (EdgarTools calls, breaker-wrapped), `xbrl_service.py` (persisted accession snapshot first, then two-tier cached XBRL),
`xbrl_companyfacts.py` (companyfacts fallback transport and parser, delegated by the service class),
`xbrl_sections.py` (the summary's sections, parsed locally from the primary document the pipeline
fetched: no SEC request, breaker-exempt CPU work on its own single worker, off the SEC pool),
`compat.py` (ticker cache + document fetch), `circuit_breaker.py`, `async_executor.py`
(dedicated thread pool; `run_with_circuit_breaker` is the standard wrapper),
`instance_extractor.py` (**accession-aware**: selects facts for the filing's own reporting
period), `statement_parser.py` (pure DataFrame helpers), `sixk_extractor.py`, plus
`config.py`/`exceptions.py`/`models.py`. Breaker coverage is selective: the XBRL primary path
uses plain timeouts for local parsing, and the raw companyfacts fallback in `xbrl_companyfacts.py`
uses a single limiter wait without the breaker. Existing raw-HTTP paths outside the layer — `SECFullTextSearchClient`
in `app/integrations/sec_api.py` and companyfacts fetching in `app/services/facts/transport.py` —
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
| `section_reviews.py` | `/api/summaries` | `/filing/{id}/wording-review` (+ `/labels`): the Pro review of a filing's Item 1A wording changes, behind the `section_changes` entitlement |
| `filings.py` / `companies.py` | `/api/filings`, `/api/companies` | retrieval, search, details |
| `peers.py` / `insiders.py` | `/api/companies` | `/{ticker}/peers`, `/{ticker}/insiders` |
| `analysis.py` | `/api/analysis` | Multi-Period Analysis: coverage (auth), dataset + SSE narrative + PDF (Pro `can_analyze_trends` gate) |
| `auth.py` / `users.py` | `/api/auth`, `/api/users` | login/register/refresh/OAuth; profile/export/deletion |
| `subscriptions.py` | `/api/subscriptions` | management + **signature-verified** Stripe webhook; public `GET /prices`, what checkout charges (no IDs) |
| `watchlist.py` | `/api/watchlist` + `/api/waitlist` | exports both routers |
| `dashboard.py` / `calendar.py` | `/api/dashboard`, `/api/calendar` | feed, upcoming calendar |
| `search.py` | `/api/search` | SEC full-text search (EFTS) |
| `notable_filings.py` / `reporting_this_week.py` | `/api` | discovery surfaces (serve-from-DB, self-omitting) |
| `saved_summaries.py` / `contact.py` / `feedback.py` / `email.py` | `/api/...` | saved items, forms (rate-limited + Turnstile), email mgmt |
| `webhooks.py` | `/api` | Resend webhook (`POST /api/webhooks/resend`, Svix-verified) |
| `admin.py` | `/api/admin` | admin surface (see docs/OPERATIONS.md) |
| `internal.py` | `/internal` | token-gated Cloud Scheduler jobs: filing-scan, filing-digest, retention-purge, earnings-calendar-refresh, earnings-day-alerts, backfill-facts, notable-filings-scan, sync-companyfacts, backfill-filing-history, precompute; with `DURABLE_TASKS_ENABLED` each is queued to `services/internal_task_runner.py`, otherwise it runs as a background task after the 202, and one that uses the database opens its own session (`services/job_sessions.py`); a precompute `dry_run` answers synchronously |
| `sitemap.py` | `/` | sitemap.xml |

## Frontend architecture

- **`features/<domain>/`** owns domain components + API clients; **`components/`** is
  chrome + `ui/` only (allowlist-enforced). Key components and homes:
  `features/summaries/components/` (SummarySections + section renderers,
  FinancialMetricsTable, SummaryDisplay), `features/filings/components/` (NotableFilings,
  copilot/), `features/companies/components/` (CompanySearch),
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
- Design system: read [`DESIGN.md`](../DESIGN.md) (portable visual reference) and then
  [`frontend/DESIGN_SYSTEM.md`](../frontend/DESIGN_SYSTEM.md) (implementation conventions and
  verification gates) before UI work. Token definitions and component code take precedence over
  both; maintenance rules are in [CLAUDE.md](../CLAUDE.md#design-documentation).

## Data model

Core models in `models/__init__.py`: `User`, `OAuthAccount`/`OAuthState`, `Company`,
`Filing`, `Summary` (UNIQUE `filing_id`), `SavedSummary`, `Watchlist`, `UserUsage`
(per-month summary/QA/analysis counts), `UserSearch`, `FilingContentCache`,
`SummaryGenerationProgress`.
Submodules: `financial_fact.py` (normalized XBRL for peers/time-series),
`trend_analysis.py` (cached Multi-Period runs keyed by company/mode/range),
`notifications.py` (prefs + dedup ledger), `refresh_token.py` (rotation chain),
`subscription.py` (`Subscription` + `StripeEvent` idempotency ledger), `waitlist.py`,
`contact.py`, `audit_log.py`, `job_run.py` (`earningsnerd_job_runs`, independent scheduled-job attempts),
`filing_section_text.py` (`filing_section_text`: Item 1A text per filing with its extraction status, attempt times and the cached comparison summary), `section_review.py` (`section_reviews`: a reader's labels, completion time and frozen receipt for one filing section). Additional tables via migrations: `invite_codes`,
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
  Annual-report (10-K/20-F/40-F and their amendments) points take the issuer's fiscal year from the
  same anchor (the DEI FY focus year less whole years back from the report date) wherever the
  calendar year of the period end misnames it: a year ending 1 February 2025 is fiscal 2024, a
  52-week year ending 1 January 2023 is fiscal 2022. The focus is trusted within the companyfacts
  writer's year bound (the end year or the year before), and the year before only where most of the
  year lies in it, so a December filer's lagging focus cannot move its years. One filing cannot
  outvote a lagging focus on a year ending January to early July (Salesforce's 10-K for its fiscal
  2026, ended 31 January 2026, says 2025), as the companyfacts year chain can, so the per-filing
  writer moves an annual report's FY rows onto the years companyfacts already stores for its period
  ends (`facts/fiscal_evidence`: FY rows from the fiscal-year-window writer that name one year and
  include a duration), by one offset for the whole filing; offsets that disagree keep the filing's
  labels, quarter labels never move, and a report opened before the first sync keeps its own (a
  known limit). Without a trusted focus, or for a point more than 18 days off a whole number of
  years from the report date (a transition period), the label is the calendar year of the end,
  never NULL (a NULL year would drop the period from Multi-Period Analysis). The fact identity
  leaves the year out, so this is what lets the per-filing and companyfacts writers name a period
  alike whichever stores it first, wherever a timely annual report (filed within 180 days of its
  end) anchors the companyfacts year chain, short of that limit. Where a contiguous chain holds
  none, the companyfacts writer keeps calendar years, for the chain's quarters too, while the
  per-filing labellers, which see no filing date, name the fiscal year. So a delinquent filer whose
  fiscal year is named for the calendar year before its end (in practice a year ending in January
  or February, a 52-week year ending in early January, or a March 20-F named by its start) carries
  two labels for one period end when its report is opened before the sync; synced first, the
  report takes the calendar years. A 10-Q filer's quarter rows were already mixed this way before
  the annual labeller (a 20-F filer has none, so for it the annual mix is new); the open follow-up,
  in the companyfacts writer, fixes both. The Multi-Period Analysis dataset reads current rows in
  period-end order, so a label that two period ends carry resolves to the later one, the axis
  bucket's own end.
  New labelled quarters demote legacy NULL-period twins; existing persisted snapshots require
  deliberate re-extraction to gain metadata they never contained. Fact writes serialize on the
  company row and preserve a known newer accession. The per-filing writer also preserves untied
  current companyfacts rows when their filing chronology cannot be established; the bulk writer
  uses the received normalizer ordering where local Filing chronology is unavailable. Older accession facts remain
  available for their own filing even when they are not the current company value.
- Companyfacts reads each concept from its reporting-currency unit list (`facts/currency.py`).
  A foreign list is read only when the USD list is its convenience translation (every USD
  period the collector keeps, by period end and span, is also kept from the foreign list; an
  item it drops counts on neither side); among such lists the per-filing extractor's
  `_reporting_currency` rule picks. A foreign US-GAAP filer's history is therefore stored as
  reported (CNY, JPY), never from its USD convenience translations. A filer with no USD list at
  all, such as a 10-K filer that reports in CAD, is stored in its own currency too, since no USD
  period then needs a twin; a USD-only read stored nothing for it. Any other shape keeps the USD
  list: a stray foreign fact, whatever its date, and a currency switch in either direction. A
  switcher's years reported in a non-USD currency are not ingested in that currency; after a
  switch to USD, its earlier years come from the USD convenience translations, as before. Quarter
  derivation works in any currency. Once the native row arrives, a sync demotes, never deletes,
  any current USD row at the same concept, period end and fiscal period, whatever its source or
  filing. The newer-accession rule above is per unit; across units the pick has already chosen
  the series currency. A derived ratio (`pure`) keeps its unit, so where a known filing date kept
  one computed from USD operands current, the sync demotes it and promotes the native
  calculation. A ratio stored before operands were recorded (2026-10-10) counts as USD-derived
  when it is derived and has no filing owner, because companyfacts was then read only in USD.
  One stored under the native calculation's own identity (same filing) keeps its
  USD operands, because ingestion never rewrites an identity; the journaled repair
  (`docs/quarterly-data-repair.md`) recomputes it.
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
  legacy `…Z` wire format); `utc_from_iso()` parses an ISO date or date-time from outside,
  such as an SEC listing's, as aware UTC. Every session `database.py`'s engine opens (the API, the
  jobs, the durable worker and the scripts that import it) runs at UTC (its `connect` listener, E151),
  so a `timestamptz` reads back at +00:00 and a naive value binds as UTC whatever zone the session
  would start in; gated on PostgreSQL by `tests/integration/test_session_time_zone.py`. Other sessions
  (psql's, for the deploy's migrations and the Ops SQL steps, and the engine
  `scripts/validate_db_performance.py` builds) start at the server's default zone, UTC on production's
  instance, which sets no `timezone` flag; of the SQL run there, `ops/capacity/snapshot.sql` sets its
  zone and `ops/detection/notable_homepage_candidates.sql` names one. The pin moves no stored instant.
  A database whose sessions ran at another zone before E100 holds SEC's bare dates at that zone's local
  midnight: east of UTC they read, pinned, as the day before, and either side they miss an amendment's
  period end, so such rows need normalizing before that database runs the pin. Production's sessions
  ran at UTC, so none is due there. A deliberate 6-site **naive**
  allowlist exists for the OAuthState/RefreshToken token-expiry columns — enforced by
  `tests/unit/test_naive_utcnow_allowlist.py`.
- **Resilience numbers:** circuit breaker CLOSED → OPEN at 5 consecutive network failures,
  HALF_OPEN retry after 30s; only network errors trip it (404s/parse errors never do).
  SEC rate limit 10 req/s token bucket + exponential backoff — per-process, so count
  service instances + cron jobs against SEC's per-IP cap.
  Chat admission (E09b): at most `AI_CHAT_MAX_INFLIGHT` (8) in-flight Copilot / Analysis
  provider streams per process, waiting for a slot only within their own budget; the summary
  path is bounded by its own two semaphores and never queues behind chat. Per-process too;
  `/metrics` reports every stream and both gates.
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
  Vercel Analytics on the frontend (`@vercel/analytics`, mounted from `app/layout.tsx` by
  `app/private-analytics.tsx` only once the visitor allows analytics, D-046).
- The eval harness (`backend/evals/`) pins summary quality (`baseline_scores.json`) with a
  CI regression gate on AI-relevant PRs.

## Known residual debt (minor)

- `FilingContentCache.markdown_*` columns are inert legacy (dropping needs a destructive
  migration).
- Recorded follow-up from the 2026-07 refactor (see `tasks/architecture-refactor-plan.md`
  delta log): the three concept-list registries (`facts_service`, `edgar/xbrl_service`,
  `edgar/instance_extractor`) stay deliberately separate, because their orderings encode tag
  priority; unifying them would change which tag wins. The other two follow-ups on that list are
  done: both companyfacts fetchers run on the shared SEC limiter (WS-8, 2026-09-04, made
  `facts_service`'s sync fetcher a bridge onto the rate-limited async one; the `xbrl_service`
  fallback was already limiter-wired), and `_parse_company_facts` has filled its
  `total_liabilities`/`cash_and_equivalents` buckets since 2026-09-05, pinned by
  `backend/tests/unit/test_companyfacts_fixture.py`.

## Decision records

The significant, hard-to-reverse decisions — and their trade-offs — are ADRs in
[`docs/adr/`](./adr/): the hosting move to Cloud Run, the AI-provider migrations
(Gemini, then DeepSeek — ADR-0002/0006), `edgartools` for SEC data, Redis-off-in-prod,
and staying on React 18 under Next 16.

Monthly usage counter writes preserve existing first-row history. A metered summary or Copilot
generation is counted as its provider call starts (summaries and Copilot alike: on the request
dispatcher's provider-start signal, fired at the request site, the admission lease converted in
the increment's commit); a provider-side failure or a partial-quality verdict refunds the unit through
the same SQL-arithmetic protocol (floor 0), and a client disconnect after the provider started
does not. Existing buckets skip the parent User lock; first-month creation can contend with
Stripe account work, subject to `USAGE_COUNTER_LOCK_TIMEOUT_MS`. SQL increments prevent
stale-session lost updates for successfully committed calls. All old service and job writers must
drain before the first-use protocol holds fleet-wide. This does not repair historical duplicate
buckets or make best-effort metering strict billing accounting.

Failed-login recording uses the existing `login_attempts.email_hash` primary key for concurrent
insert/update and successful-clear ordering on PostgreSQL and SQLite. A failure waiting behind
a committed success clear creates a new history; after a rolled-back clear it increments the
retained history. Initial timestamps retain their database default, while updates stamp the
existing failure clock explicitly. The change counts completed failures; credential checks
already admitted before a lock are not reserved. Old revision writers must drain before their
read-modify-write path can no longer overwrite counts. Per-IP memory bounds, row retention and
new timeout/retry policy remain separate.
