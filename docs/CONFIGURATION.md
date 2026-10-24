# Configuration Reference — environment variables

W3-2 source checkpoint (2026-09-06): explicit deploy pins below are implemented in the
workflow source; merge/deployment and effective-pin verification remain pending. Defaults
remain distinct from the founder-approved calendar service override.

The complete environment-variable reference for backend (`backend/.env`) and frontend
(`frontend/.env.local`). Definitions and validation live in `backend/app/config.py`
(Pydantic Settings — ALL backend env access goes through it; never `os.getenv` in app code,
except the pre-Settings infra-bootstrap constants in `database.py`, `redis_service.py`, and
`edgar/config.py`)
and `frontend/lib/featureFlags.ts`. Production uses a mix of Cloud Run environment overrides and Google Secret
Manager mounts (see [DEPLOYMENT.md](DEPLOYMENT.md)).
A settings validation error names the failing field and the reason but withholds the value (`REGISTRATION_MODE`'s
own message quotes its value; it holds no secret). A settings object prints no value; `scripts/deploy_check.py` and
`scripts/smoke_resend.py` print a secret's presence and length only; a malformed `DATABASE_URL` or `REDIS_URL` is
reported by its error's type, never the parser's message, which can quote the password. Sentry receives no frame's
local variables, and the `X-Internal-Token` header, every outbound request's query string, the credential keys of a
request body, each secret setting's whole value and each connection URL's password (8 characters or more; the limits
are in the lesson) reach it as `[Filtered]` (another placeholder if a weak secret overlaps that one), wherever an
error, a transaction, a log or a metric holds them
(`main._sentry_options`). The rules,
their gates and the echoes not yet gated: `lessons/ops-never-echo-environment-values.md`. To debug a value, read it
from its source (Secret Manager, `backend/.env`).

> Moved out of CLAUDE.md in the July 2026 refactor (Wave 3 / M3) — this file is now the
> canonical env reference; keep it in sync with `config.py` when adding fields.

## Backend Settings inventory

These are **declared code defaults**, not a dump of live production values. `""` means an
empty string, `null` means no value, and `required` means there is no default. The table is
checked against `Settings.model_fields` by `backend/tests/unit/test_configuration_reference.py`;
add or change a field and update its row in the same PR. Examples below show configuration
choices and placeholders, not a second default inventory.

Environment names are case-insensitive and have no prefix. Settings reads `.env` relative to
the process working directory (normally `backend/`); process environment normally wins over
`.env`, and unknown `.env` keys are rejected. Two constructor details matter: a nonblank process
`OPENAI_API_KEY` longer than 10 characters replaces the parsed value after trimming; and
`COOKIE_SECURE` is re-derived from `ENVIRONMENT` unless that name is present in the process
environment (a value supplied only in `.env` is therefore overwritten). Set production
`COOKIE_SECURE` explicitly in the process environment when overriding the derived behavior.

CI's service deployment explicitly sets `ENVIRONMENT=production`, `COOKIE_DOMAIN=.earningsnerd.io`,
`TRUSTED_PROXY_HOPS=1`, `ENABLE_FPI_FILINGS=true`, `STREAM_SECTION_REVEAL=true`,
`REGISTRATION_MODE=invite_only`, the DeepSeek URL/model, and `SENTRY_RELEASE` to the deployed SHA.
It mounts `DEEPSEEK_API_KEY` as `OPENAI_API_KEY`. Other secrets and existing environment overrides
can be managed separately; these repository declarations do **not** verify their live values.
Jobs have independent environment settings. Use the read-only describe-service procedure in
[DEPLOYMENT.md](DEPLOYMENT.md) to inspect rollout flags; do not infer a deployed flag from its
code default. Production cache policy remains Redis-off/L1-only (ADR-0004).

| Setting | Declared default | Purpose / override guidance |
|---|---|---|
| `DATABASE_URL` | `"sqlite:///./earningsnerd.db"` | Local SQLite fallback; production refuses SQLite and requires a Postgres/Cloud SQL connection string. A URL holding more than one `@` stops startup. The app decodes a percent-encoded user name or password, but the deploy's migration step (`ci.yml`) and the Ops workflow's Cloud SQL proxy step (`ops.yml`) split the URL at its first `@` and first `:` and hand both to `psql` undecoded, so an encoded one (an `@` written `%40`, as an IAM user's name would need) fails there: keep both to characters that need no encoding, as the hex password `docs/DEPLOYMENT.md` generates does. |
| `REDIS_URL` | `"redis://localhost:6379"` | Local Redis endpoint. Production uses the L1 in-memory cache (ADR-0004). |
| `SKIP_REDIS_INIT` | `false` | Skip Redis initialization; true in hermetic tests and Redis-off deployments. |
| `SEC_EDGAR_BASE_URL` | `"https://data.sec.gov"` | SEC submissions/companyfacts API origin; calls must use the EDGAR service layer. |
| `SEC_USER_AGENT` | `"EarningsNerd/1.0 (support@earningsnerd.io)"` | SEC contact identity; use a reachable operator address. |
| `SEC_RATE_LIMIT_PER_SECOND` | `10` | Per-process rate of the app's own SEC token bucket (capacity equals rate). SEC's 10 req/s applies per user across every process, so production pins `1` on the API service, every job and the task worker (`ci.yml`); edgartools' separate limiter is `EDGAR_RATE_LIMIT_PER_SEC` (see below the table). |
| `SEC_MAX_RETRIES` | `5` | EDGAR retry limit. |
| `SEC_BASE_BACKOFF_SECONDS` | `1.0` | Initial EDGAR retry backoff, seconds. |
| `COMPANYFACTS_SYNC_TTL_HOURS` | `24` | Companyfacts freshness, hours; a newer Filing can force a refresh earlier. |
| `SEC_EFTS_BASE_URL` | `"https://efts.sec.gov/LATEST/search-index"` | SEC full-text search endpoint. |
| `SEC_EFTS_TIMEOUT_SECONDS` | `8.0` | Full-text search request timeout, seconds. |
| `HISTORY_BACKFILL_SINCE_YEAR` | `2001` | Earliest year searched for historical filings. |
| `HISTORY_BACKFILL_WINDOW_YEARS` | `8` | Years per bounded EFTS history window. |
| `HISTORY_BACKFILL_MAX_COMPANIES` | `50` | Maximum companies per history backfill batch. |
| `ENABLE_HISTORY_BACKFILL_ON_VISIT` | `true` | Queue a one-time deep backfill on first company-page view. |
| `OPENAI_API_KEY` | `""` | OpenAI-compatible provider credential; CI mounts DEEPSEEK_API_KEY as this name. |
| `OPENAI_BASE_URL` | `"https://api.deepseek.com/v1"` | OpenAI-compatible provider base URL; paired with model and API key. |
| `STRIPE_SECRET_KEY` | `""` | Stripe server credential; match test/live mode to environment. |
| `STRIPE_PUBLISHABLE_KEY` | `""` | Backend validation of Stripe publishable/secret mode consistency; frontend has its own public variable. |
| `STRIPE_WEBHOOK_SECRET` | `""` | Stripe webhook signature secret. |
| `STRIPE_RECONCILIATION_CONNECT_TIMEOUT_SECONDS` | `2.0` | Dedicated exact-ID Stripe read (current subscription, invoice, serving Price) connect limit; finite, > 0 and ≤ 10 seconds. |
| `STRIPE_RECONCILIATION_READ_TIMEOUT_SECONDS` | `3.0` | Dedicated exact-ID Stripe read (current subscription, invoice, serving Price) inactivity limit; finite, > 0 and ≤ 10 seconds. |
| `STRIPE_PRICE_MONTHLY_ID` | `""` | Monthly checkout price ID; empty default makes configured checkout validation fail. Must be a USD Price recurring once a month at the advertised `PRO_PRICING.monthly` (`frontend/app/pricing/prices.ts`), in the same Stripe mode as `STRIPE_SECRET_KEY`; production changes follow [PRICING_OFFER.md](PRICING_OFFER.md) (backend first; its [machine checks](PRICING_OFFER.md#machine-checks) compare the bound amount with the page). |
| `STRIPE_PRICE_YEARLY_ID` | `""` | Yearly checkout price ID; empty default makes configured checkout validation fail. Must be a USD Price recurring once a year at the advertised `PRO_PRICING.yearly` (`frontend/app/pricing/prices.ts`), in the same Stripe mode as `STRIPE_SECRET_KEY`; production changes follow [PRICING_OFFER.md](PRICING_OFFER.md) (backend first; its [machine checks](PRICING_OFFER.md#machine-checks) compare the bound amount with the page). |
| `STRIPE_BETA_PROMO_CODE_ID` | `""` | Stripe Promotion Code ID for eligible beta invites; unset disables the discount. |
| `PRO_TRIAL_DAYS` | `0` | Card-required monthly trial; 0 disables; validated 0–30. Enable only with the matching frontend flag after the Stripe checklist. |
| `REVERSE_TRIAL_ENABLED` | `false` | Retired no-card signup trial; keep off. Cannot coexist with a positive PRO_TRIAL_DAYS. |
| `REVERSE_TRIAL_DAYS` | `7` | Duration of the retired reverse trial, days. |
| `REGISTRATION_MODE` | `"public"` | Validated public or invite_only registration, enforced on `/api/auth/register` and on the Google/Apple callbacks (an invited social sign-up sends the invite in the body of `POST /api/auth/google|apple/start`, never in a URL); CI explicitly sets invite_only on the service. |
| `INVITE_EXPIRY_HOURS` | `168` | Invite token lifetime, hours. |
| `LEGAL_COLLECTION_ENABLED` | `false` | Opt-in for new registration, waitlist and general-contact collection; also requires a complete, explicitly published operator notice. Does not enable checkout or promotion. See [LEGAL_READINESS.md](LEGAL_READINESS.md). |
| `LEGAL_OPERATOR_PUBLISHED` | `false` | Explicit authorization to return complete operator notice fields from `/api/legal/readiness` for display on the legal pages. Draft values remain withheld while false. |
| `LEGAL_OPERATOR_NAME` | `""` | Verified legal operator name for the public notice; no personal default. |
| `LEGAL_OPERATOR_POSTAL_ADDRESS` | `""` | Verified public postal address; multiline text supported. |
| `LEGAL_OPERATOR_COUNTRY` | `""` | Operator country for the public notice. |
| `LEGAL_OPERATOR_EMAIL` | `""` | Reachable legal-contact address; validated as an email before the notice can be published. |
| `INTERNAL_JOB_TOKEN` | `""` | Shared internal-job endpoint secret; unset endpoints return 503. |
| `DURABLE_TASKS_ENABLED` | `false` | Opt-in queue handoff for on-visit work, internal jobs and the account mail of forgot-password and resend-verification (F60). Enable after authenticated worker delivery is verified; keep CPU always allocated until then. |
| `TASKS_PROJECT_ID` | `""` | Project containing the task queue; required when durable delivery is enabled. |
| `TASKS_LOCATION` | `"us-west1"` | Queue region; co-locate with the API and worker. |
| `TASKS_QUEUE` | `"earningsnerd-background"` | Dedicated background queue with one concurrent delivery. |
| `TASKS_WORKER_URL` | `""` | Exact HTTPS run.app origin of the private worker, also its expected OIDC audience. |
| `TASKS_INVOKER_EMAIL` | `""` | Dedicated task service account whose verified email is accepted by the worker. |
| `TASKS_WORKER_PROCESS` | `false` | Enable only on the private task-only service; permits isolated child execution. |
| `TASKS_WORK_TIMEOUT_SECONDS` | `480` | Hard child work deadline, greater than zero and at most 480 seconds; child is killed and reaped before HTTP completion on timeout or disconnect. |
| `POSTHOG_API_KEY` | `""` | Server-side PostHog credential. |
| `POSTHOG_HOST` | `"https://us.i.posthog.com"` | Server-side PostHog ingestion origin. |
| `SENTRY_DSN` | `""` | Error tracking DSN; empty disables SDK setup. Events carry stack frames, source lines, messages and breadcrumbs, not local variables (`main._sentry_options`), and the value scrubber's hooks, one per channel (`before_send`, `before_send_transaction`, `before_send_log`, `before_send_metric`), withhold each secret setting's whole value (8 characters or more) and each connection URL's password wherever an error, a transaction, a log or a metric holds them, in any text and in the repr of any other value (a log record's `extra` with Sentry logs on). Never set the SDK's `data_collection` option: it disables the event scrubber and turns local variables back on. Never set `trace_lifecycle`: span streaming sends request headers as span attributes, which neither scrubber reads. Never set `max_value_length`: the serializer, which runs before `before_send` and `before_send_transaction`, would cut a string inside a secret. Never set `profile_session_sample_rate` or `profile_lifecycle`: continuous profiling sends profile chunks, which no hook sees. |
| `SENTRY_RELEASE` | `""` | Release tag; CI supplies the Git SHA; empty allows SDK detection. |
| `RESEND_API_KEY` | `""` | Outbound email credential; required for sending. |
| `RESEND_BASE_URL` | `"https://api.resend.com"` | Resend API origin. |
| `RESEND_FROM_EMAIL` | `"EarningsNerd <hello@inbound.earningsnerd.io>"` | Sender on a Resend-verified domain; complete surrounding quotes are normalized away. |
| `RESEND_REPLY_TO_EMAIL` | `"support@earningsnerd.io"` | Reply destination for direct transactional mail; defaults to the shared public role config. Durable deliveries freeze this optional value at selection; existing batches keep their stored value or header omission across retries and configuration changes. |
| `CONTACT_NOTIFICATION_EMAIL` | `"support@earningsnerd.io"` | Workspace recipient for contact-form notifications, independent of the sending address. |
| `FEEDBACK_NOTIFICATION_EMAIL` | `"support@earningsnerd.io"` | Workspace recipient for beta-feedback notifications, independent of the sending address. |
| `RESEND_WEBHOOK_SECRET` | `""` | Resend/Svix webhook signature secret. |
| `FRONTEND_URL` | `"https://www.earningsnerd.io"` | Public frontend origin: mail links, sign-in redirects and the mail header's tile (`/assets/earningsnerd-appicon.png`) are built on it. Use the origin that answers without a redirect (the apex answers 307 to www): sent mail keeps the whole address. Set it without a trailing slash: the tile and the waitlist's links strip one, the other links append their paths to it as it is. |
| `DATA_QUALITY_REPORT_EMAIL` | `"neil@earningsnerd.io"` | Recipient of the operator-run data-quality report. |
| `SECRET_KEY` | `required` | Required in every environment; at least 32 characters, known placeholders rejected. Prefer 64+ random characters. |
| `IP_HASH_SALT` | `""` | IP-hash pepper; call sites fall back to SECRET_KEY when empty. |
| `ALGORITHM` | `"HS256"` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access-token lifetime, minutes; clients silently refresh. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Rotated opaque refresh-token lifetime, days. |
| `REFRESH_COOKIE_NAME` | `"earningsnerd_refresh_token"` | Refresh-token cookie name. |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum password length. |
| `PWNED_PASSWORD_CHECK_ENABLED` | `true` | HaveIBeenPwned k-anonymity check for new/reset passwords; errors fail open; tests disable it. |
| `JWT_ISSUER` | `"earningsnerd"` | Required JWT issuer claim. |
| `JWT_AUDIENCE` | `"earningsnerd-users"` | Required JWT audience claim. |
| `JWT_LEEWAY_SECONDS` | `10` | JWT time-validation clock skew allowance, seconds. |
| `GOOGLE_CLIENT_ID` | `""` | Google OAuth client ID. |
| `GOOGLE_CLIENT_SECRET` | `""` | Google OAuth client secret. |
| `GOOGLE_REDIRECT_URI` | `"https://api.earningsnerd.io/api/auth/google/callback"` | Google OAuth callback URL; match provider registration. |
| `APPLE_CLIENT_ID` | `""` | Apple Services ID used as token audience. |
| `APPLE_REDIRECT_URI` | `"https://api.earningsnerd.io/api/auth/apple/callback"` | Apple OAuth callback URL; match provider registration. |
| `TURNSTILE_SECRET_KEY` | `""` | Cloudflare bot verification; empty is a no-op. Pair with frontend site key. |
| `TRUSTED_PROXY_HOPS` | `1` | Trusted proxies counted from the right of X-Forwarded-For; 0 ignores the header. CI sets 1 for direct Cloud Run ingress. |
| `RATE_LIMITER_MAX_KEYS` | `10000` | Per-process, per-limiter retained-key ceiling (1–100000); reject unseen keys at capacity instead of evicting active windows. Expired keys are removed lazily; peeks do not extend retention. Not a fleet or byte limit. |
| `ENVIRONMENT` | `"development"` | Environment label; production enables SQLite refusal and secure-cookie derivation. |
| `COOKIE_NAME` | `"earningsnerd_access_token"` | Access-token cookie name. |
| `COOKIE_SECURE` | `false` | Declared default false; constructor derives true in production unless COOKIE_SECURE exists in the process environment. See precedence note below. |
| `COOKIE_SAMESITE` | `"lax"` | Cookie SameSite policy. |
| `COOKIE_DOMAIN` | `null` | Null means host-only. CI sets .earningsnerd.io for frontend/API cross-host sessions. |
| `CORS_ORIGINS_STR` | `"http://localhost:3000,http://127.0.0.1:3000,https://earningsnerd.io,https://www.earningsnerd.io"` | Comma-separated allowed origins; CORS_ORIGINS is a derived property, not another environment field. |
| `FMP_API_KEY` | `""` | Optional for an explicit `refresh_index_membership.py --source fmp` invocation only. Automatic and scheduled refreshes use both public Wikipedia constituent lists without reading this key. In-app FMP integration is retired. |
| `ALPHA_VANTAGE_API_KEY` | `""` | Licensed calendar bridge credential; leave empty for EDGAR-only operation until licensing is settled. |
| `ALPHA_VANTAGE_API_BASE` | `"https://www.alphavantage.co/query"` | Alpha Vantage calendar API endpoint. |
| `ALPHA_VANTAGE_TIMEOUT_SECONDS` | `20.0` | Calendar download timeout, seconds. |
| `ALPHA_VANTAGE_HORIZON` | `"3month"` | Calendar horizon: 3month, 6month or 12month. |
| `XBRL_CACHE_TTL_HOURS` | `24` | XBRL cache lifetime, hours. |
| `STRUCTURED_EXTRACTION_CACHE_TTL_SECONDS` | `3600` | Structured extraction retry cache lifetime, seconds. |
| `AI_DEFAULT_MODEL` | `"deepseek-flash"` | Primary provider model. Deploy-time source is `.github/ai-model.env` (every workflow loads it into `GITHUB_ENV`); `tests/unit/test_retired_model_ids.py` keeps that file, this table and the code default identical. |
| `AI_FALLBACK_BASE_URL` | `""` | Optional fallback API base; empty uses primary origin. HTTPS only; a different origin requires its separate credential. |
| `AI_FALLBACK_MODEL` | `""` | Empty disables provider fallback. Configure only a model served by the fallback API after eval evidence. |
| `AI_FALLBACK_API_KEY` | `""` | Separate fallback credential. Required across origins; same-origin fallback may use the primary key. Never send the primary key to an arbitrary provider. |
| `AI_FAST_MODEL` | `""` | Optional cheaper task model; empty falls back to AI_DEFAULT_MODEL. Change only after evals. |
| `AI_SUMMARY_THINKING_EFFORT` | `""` | Experiment switch (W10): when set (`low`/`high`/`max`) the primary summary call runs DeepSeek thinking mode at that effort, drops `temperature` and raises `max_tokens` to `AI_SUMMARY_THINKING_MAX_TOKENS`; recovery and fallback calls stay non-thinking. Empty in production. |
| `AI_SUMMARY_THINKING_MAX_TOKENS` | `24000` | Output ceiling for the thinking-mode summary arm (reasoning tokens count toward it). |
| `AI_SECTION_RECOVERY_MODEL` | `""` | Section-recovery override; empty falls back through AI_FAST_MODEL to AI_DEFAULT_MODEL. |
| `USE_STRUCTURED_OUTPUT` | `false` | Structured Phase-A response format; off pending eval bake-off. Pinned explicitly in the `ci.yml` service and pregenerate deploy env. |
| `USE_EDGARTOOLS_SECTIONS` | `true` | Parse the 10-K, 10-Q and 20-F summary sections locally from the primary document the pipeline already fetched (edgartools' HTML parser in `edgar/xbrl_sections.py`; no SEC request), with the legacy regex/dense-window excerpt as the fallback when sections are empty or thin, the document is over 16,000,000 characters, or the parse fails or runs past its 30 s bound (40 s for a 20-F, counting time queued behind another parse). `false` is the regex-only rollback. The cap is an input change against the `obj()` path, which parsed any size within 30 s (40 s for a 20-F); no golden document over it has sections, and the `Section parse skipped` log counts the rest. From early October 2026 (between CI's reports of 4 and 7 October) until #1350's backport (deployed 2026-10-16) the source called `Filing.obj()`, which SEC's 403 on edgartools 5.58.0's index URL disabled, so each excerpt first built in that window is a regex excerpt and stays one until its stored excerpt is cleared or a forced precompute replaces its summary, which stores the excerpt that run rebuilt (`tasks/review-evidence/e28-native-sections-2026-10-15/`). |
| `AI_QUALITY_GATE` | `true` | Partial summaries persist but do not consume monthly quota. |
| `AI_FIGURE_TRACE_GATE` | `false` | Untraceable dollar figures tier summaries partial when armed; off keeps advisory audits. Pinned explicitly in the `ci.yml` service and pregenerate deploy env. |
| `AI_FORWARD_QUOTE_GATE` | `false` | Drop forward quotes not verbatim in the filing when armed; off keeps advisory audits. Pinned explicitly in the `ci.yml` service and pregenerate deploy env. |
| `AI_ATTRIBUTION_GATE` | `false` | Drop causal clauses ("driven by / reflecting / due to …") the filing does not state for that subject — the clause only, the movement stays. **Drops only what `AI_ATTRIBUTION_VERIFY`'s model verdict calls unstated**: armed without the verifier it removes nothing and records the refusal, because the lexical measurement alone is 47% precise (`tasks/review-evidence/pr805-path/attribution-gate-precision-2026-09-17.md`). Off keeps the advisory audit (`raw_summary["attribution_audit"]`) and the `attribution_unverified` counter. Pinned explicitly in the `ci.yml` service and pregenerate deploy env. |
| `AI_ATTRIBUTION_VERIFY` | `false` | One extra bounded model call per generation **whose gate flagged a clause** (about a quarter of them), deciding per clause whether the filing states that driver; same provider and cheap model as section recovery. This is the spend switch as well as the correctness one: verdicts are recorded in the audit for calibration whether or not the gate is armed, and any failure leaves the summary untouched. Pinned explicitly in the `ci.yml` service and pregenerate deploy env. |
| `AI_EVIDENCE_SNAP` | `false` | Replace unverifiable evidence with matched filing sentences when armed; off keeps advisory audits. **Armed in production since 2026-09-15** (founder decision after the first complete strong-judge readout, D5): the `ci.yml` service and pregenerate deploy env pin `true`; the code default stays `false` for local/dev. |
| `EVIDENCE_SNAP_MIN_SCORE` | `72.0` | Figure-bearing evidence similarity floor; no-figure evidence uses the separate in-module floor of 88. |
| `ENABLE_FPI_FILINGS` | `false` | Page-scoped 20-F/6-K/40-F discovery; CI explicitly enables it on the service. Other job form sets are separate. The history backfill also walks 20-F and 40-F in the same EFTS query (not their amendments, not 6-K), as the company list serves them, reading the flag in the process that runs the walk: the service and the task worker carry it in their deploy maps, and the Ops `backfill-filing-history` jobs-channel fallback sets it on its `earningsnerd-backfill-facts` execution (`ops.yml`), whose job map does not (gate: `tests/unit/test_filing_history_service.py`). A walk with it off, such as a local `scripts/backfill_filing_history.py`, lists 10-K/10-Q only, says so in its `History backfill` log line (`forms`) and still stamps the company, after which no visit walks it again; `migrations/20261023_rewalk_foreign_issuer_history.sql` cleared the stamps the 10-K/10-Q-only walk had left on foreign issuers. |
| `ENABLE_INSIDER_ACTIVITY` | `false` | Serves `GET /api/companies/{ticker}/insiders`; off, it answers 404. A cold load is a live edgartools fan-out (about two SEC requests per Form 4 for up to 60 Form 4s, so about 120) that the deploy-pinned 1 req/s budget cannot carry; the deploy pins it `false`, so leave it off with the frontend's `NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY` until a budget-aware insider scan lands (CODE RED record 17). |
| `ENABLE_SECTION_CHANGES` | `false` | "What changed" wording diff; set it on every process that reads it when it flips: the `earningsnerd-backend` service, the job images (the `earningsnerd-filing-scan` job extracts and writes the real-time alert line, the `earningsnerd-filing-digest` job the digest line) and the task worker, which runs the scan and the digest on the durable path (no `ci.yml` env map carries it; `tests/unit/test_section_changes_flag_placement.py` fails a flip that misses one of the three maps, spells the flag outside them, or forgets the `JOB_CADENCES` entry; a shell-sourced value such as `${ENABLE_SECTION_CHANGES}` counts as possibly on, so the cadence is due with it). On the `earningsnerd-filing-scan` job, the hourly real-time pass also stores Item 1A text for the watched cohort's 10-K/10-Q filings (one SEC request each, serial through the shared limiter; `filing_section_text`); on the `earningsnerd-backend` service, `GET /api/summaries/filing/{id}/what-changed` serves the paragraph-paired diff against the prior same-form filing as `section_changes` (Free and anonymous readers get the counts and the first `section_changes_items` items, 3; Pro the full list; `entitlements.py`), the dashboard feed carries each card's wording-change counts, a Pro reader's labels and receipt are served under `/api/summaries/filing/{id}/wording-review` (`section_reviews`), and a Pro recipient's new-filing alert and daily digest carry the "Risk factor wording: N paragraphs changed" line when the filing's comparison is cached at selection time (the real-time pass usually precedes the extraction batch, so the digest carries it more often). Off: nothing is fetched or stored, the block is `null`, the review endpoints answer `unavailable`/409 and no alert carries the line. `scripts/extract_sections.py` backfills a cohort regardless of the flag. At the flip, add `section-extraction` to `JOB_CADENCES` so `job_health` watches the batch. |
| `SECTION_EXTRACTION_BATCH_LIMIT` | `25` | Filings extracted per scan run, one SEC request each (up to three attempts). The 2026-10 corpus averaged 2.7 s per filing for fetch plus parse (7.7 s for the largest 10-K), so 25 takes about a minute; a document that times out on every attempt costs about three minutes on its own. One parse of the largest 10-K peaks near 370 MB inside the job's 1 GiB. |
| `SECTION_TEXT_MAX_CHARS` | `400000` | Section texts longer than this are recorded as `oversize` without their text (the longest Item 1A in the 2026-10 corpus was 161k characters). |
| `CALENDAR_INDEX_FILTER_ENABLED` | `false` | Restrict public calendar serve/ingest to committed index universe; watchlist exceptions remain; missing/short universe fails open. Settings default stays false. Founder-approved intentional service override is true; pregenerate is false, both explicit in `ci.yml`. This does not activate the Calendar UI. |
| `NOTABLE_FILINGS_ENABLED` | `false` | Serving gate only; scan job populates independently. Code default stays false; the [bounded September 28 rollout](../tasks/notable-rollout-2026-09-28.md) pins true in service and pregenerate deployment settings after the corrected labels release. This adds no model generation. |
| `NOTABLE_FILINGS_SCAN_DAYS` | `2` | Scheduled scan trailing window, days; manual seed --days overrides it. |
| `RICHER_FINANCIALS_ENABLED` | `true` | Expanded cash-flow and working-capital facts; false restores legacy concept set. |
| `USE_STATEMENT_FINANCIALS` | `true` | Financial institutions use reported income-statement revenue; explicit false overrides the default. SIC backfill and persisted-fact remediation remain separate operator runs (see below). Pinned explicitly in the `ci.yml` service and pregenerate deploy env. |
| `PRO_SUMMARY_MONTHLY_CAP` | `300` | Pro's fair-use ceiling on summary generations per calendar month (UTC), regenerations included: a run takes a unit when its provider request is issued, a run that fails, or comes back partial under `AI_QUALITY_GATE`, gives it back, and reading a stored summary never counts; 0 disables; billing remains unlimited. Published: the /pricing FAQ and the filing page's limit card state this default through `frontend/lib/planLimits.ts`, so change it here and the mirror follows, and never set it in a deploy map (`planLimitsLockstep.spec.ts` holds the mirror to this default and fails on any workflow line that names the variable). A value set by hand on the Cloud Run service is outside that gate, and the page overstates a lowered ceiling until the default changes. |
| `STARTUP_SCHEMA_DEADLINE_SECONDS` | `60` | Deadline for each schema step the serving container runs at startup (`create_all`, additive columns); 1 through 600 s. A step that exceeds it fails the start (Cloud Run keeps the last healthy revision) instead of hanging until the platform's startup timeout. Additive-column ALTERs also wait at most 5 s for their table lock on PostgreSQL. |
| `USAGE_COUNTER_LOCK_TIMEOUT_MS` | `3000` | PostgreSQL transaction-local lock waits for monthly counter writes; whole milliseconds from 1 through 10000. Does not bound total transaction/network duration. |
| `DELIVERY_CLAIM_TTL_SECONDS` | `60` | E11b-1: how long a worker's preparation claim on a delivery batch (`earningsnerd_delivery_batches`, status `claimed`) lasts before another worker may reclaim it; 1 through 600. |
| `DELIVERY_SEND_TTL_SECONDS` | `120` | E11b-1: the `sending` lease. An expired sending lease is never reclaimed (the email may have been accepted); the batch becomes `ambiguous` for reconciliation. 11 through 900; keep it above the 10 s Resend client timeout. |
| `DELIVERY_MAX_ATTEMPTS` | `5` | E11b-1: dispatch attempts per batch before it is parked as `ambiguous` (`attempts_exhausted`); 1 through 20. |
| `DELIVERY_RETRY_BACKOFF_SECONDS` | `300` | E11b-1: delay before the first retry of a `retryable` batch, doubled per attempt; 1 through 86400. |
| `DELIVERY_REPLAY_WINDOW_SECONDS` | `72000` | E11b-1: how long after a batch's first dispatch a retry may replay the same payload under the same `Idempotency-Key`; must stay inside Resend's documented 24 h retention (at most 86400). Past it a `retryable` batch (only ever reached through documented non-acceptance) is re-keyed with a fresh window, so the once-daily digest cadence can still retry; unknown outcomes are `ambiguous` and never re-keyed. |
| `USAGE_RESERVATION_TTL_SECONDS` | `300` | How long an admission reservation (E07b lease in `earningsnerd_usage_reservations`: summary, Copilot `qa` / lifetime `qa_taste`, `analysis`) holds a quota unit if the owning process dies before converting or releasing it; 181 through 3600 s, covering the 120 s pipeline timeout plus the bounded conversion lock wait. Expired rows are ignored by admission and swept on the account's next admission. |
| `MAX_CONCURRENT_GENERATIONS` | `6` | Per-process full-generation semaphore; values at or below 0 disable the ceiling. |
| `RECOVERY_MAX_CONCURRENCY` | `3` | Concurrent section-recovery API calls per process (semaphore on the service singleton). |
| `AI_CHAT_MAX_INFLIGHT` | `8` | E09b: at most this many in-flight Copilot chat / Analysis narration provider streams per process; 0 through 512, 0 disables. A chat request waits for a slot only within its own budget and fails as a timeout past it. The summary path is bounded separately by `MAX_CONCURRENT_GENERATIONS + RECOVERY_MAX_CONCURRENCY` and never queues behind chat, so a process holds at most this many plus that maximum provider streams; fleet load on the shared key is the sum over instances and jobs. |
| `COPILOT_MONTHLY_QUESTION_CAP` | `1000` | Monthly question fair-use ceiling per Pro account. |
| `COPILOT_MAX_TOKENS` | `2400` | Maximum Copilot completion tokens. |
| `COPILOT_CONTEXT_CHAR_CAP` | `120000` | Maximum filing excerpt characters in Copilot context. |
| `COPILOT_HISTORY_TURNS` | `6` | Prior conversation turns retained for follow-ups. |
| `COPILOT_HISTORY_MAX_ITEMS` | `50` | Maximum accepted history array length. |
| `COPILOT_HISTORY_ITEM_CHAR_CAP` | `8000` | Maximum characters per history item. |
| `ANALYSIS_MONTHLY_CAP` | `100` | Monthly fresh analysis narrative cap; cached re-serves are free. |
| `ANALYSIS_MAX_TOKENS` | `3200` | Maximum analysis narrative completion tokens. |
| `ANALYSIS_MAX_ANNUAL_PERIODS` | `10` | Maximum annual periods selectable. |
| `ANALYSIS_MAX_QUARTERLY_PERIODS` | `12` | Maximum quarterly periods selectable. |
| `AI_INPUT_CACHE_HIT_PRICE_PER_1M` | `0.003` | Configured USD estimate per million cached input tokens; telemetry assumption, not a live provider price quote. |
| `AI_INPUT_CACHE_MISS_PRICE_PER_1M` | `0.15` | Configured USD estimate per million uncached input tokens; update alongside model pricing. |
| `AI_OUTPUT_PRICE_PER_1M_TOKENS` | `0.6` | Configured USD estimate per million output tokens (off-peak); the PostHog per-answer estimate uses this flat rate. |
| `AI_PEAK_PRICE_MULTIPLIER` | `2.0` | Multiplier the per-call `ai_call` log estimate applies during DeepSeek peak hours (UTC 01:00–04:00 and 06:00–10:00, Mon–Fri); see `docs/OPERATIONS.md` "AI call telemetry". |
| `STREAM_HEARTBEAT_INTERVAL` | `3` | SSE heartbeat cadence, seconds. |
| `STREAM_TIMEOUT` | `600` | SSE timeout, seconds. |
| `STREAM_SECTION_REVEAL` | `false` | Progressive section previews with non-streaming fallback; CI enables on the service. |

**Library-read SEC budget (not a Settings field).** edgartools paces its own EDGAR HTTP (submissions,
filing objects, XBRL) with a second process-global limiter, a sliding window read once at import:
`EDGAR_RATE_LIMIT_PER_SEC` (library default `9`; `edgar/httpclient.py` in the pinned release). The app
wraps that traffic in `sec_rate_limiter` only in the SIC lookup (`app/services/edgar/company_sic.py`), so a
process's configured SEC ceiling is at most the sum of both. Production pins both to `1` on the API service,
every job and the task worker (`.github/workflows/ci.yml`; gate
`backend/tests/unit/test_sec_process_budgets.py`); leave it unset locally.

Current-bound-ID subscription created/updated reconciliation makes one Stripe read with zero SDK
retries and a dedicated transport closed after every outcome. These connect/read inactivity limits
are not a total five-second deadline: DNS or a progressing response can exceed their sum. The
worker retains its account lock and database connection during the read. Failure returns 503 with
state/event rollback; it never falls back to the stale event. Checkout, initial/different-ID events
and signed deletion keep their existing behavior and do not use these settings.

### Backend configuration examples (.env)
```
# Database & Cache
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SKIP_REDIS_INIT=false             # Set to true in tests to skip Redis (auto-set by conftest.py)

# AI Configuration (OpenAI-compatible; provider configurable)
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.deepseek.com/v1   # DeepSeek default; override for other providers
AI_DEFAULT_MODEL=deepseek-flash              # Primary AI model
AI_FAST_MODEL=                                # Optional cheaper model for low-risk tasks (falls back to default)
AI_SECTION_RECOVERY_MODEL=                    # Optional override for section recovery (falls back to AI_FAST_MODEL)
RECOVERY_MAX_CONCURRENCY=3                    # Max concurrent calls for section recovery
USE_STRUCTURED_OUTPUT=false                   # Phase-A structured extraction (JSON response_format)
USE_EDGARTOOLS_SECTIONS=true                  # Parse sections locally from the fetched primary document (vs regex fallback); no SEC call
AI_QUALITY_GATE=true                          # Partial summaries don't consume user quota
AI_FIGURE_TRACE_GATE=false                    # T3.2 number-diff gate: when on, an untraceable DOLLAR figure in summary prose tiers "partial". Default off (advisory: list attached to the verdict for measurement, never affects tier) until the corpus FP rate is measured
AI_ATTRIBUTION_GATE=false                     # #805 path step 4: drop unstated causal clauses when on; advisory audit when off
AI_ATTRIBUTION_VERIFY=false                   # #805 path step 5: one bounded model verdict per flagged generation; the gate drops only what it calls unstated
AI_FORWARD_QUOTE_GATE=false                   # T5.4 forward-quote hard gate: when on, a §5 quote not locatable verbatim in the filing text is DROPPED at generation time (content repair — never tiers). Default off (advisory: audit + greppable forward_quote_unverified counter always emitted) until the fleet FP rate is measured
AI_EVIDENCE_SNAP=false                        # Evidence auto-snap (post-#631): when on, non-verifying P&L-takeaway/footnote supporting_evidence is REPLACED at generation time by the best-matching REAL excerpt sentence (which then earns the Verified badge). Code default off (advisory: audit + greppable evidence_snap counter always emitted, recording original + candidate per would-snap); production deploys pin true since 2026-09-15 (founder decision after the first complete strong-judge readout)
EVIDENCE_SNAP_MIN_SCORE=72.0                  # Snap floor for FIGURE-BEARING evidence (rapidfuzz max(token_set, partial) on normalized text; the shared non-year-figure guard supplies the precision). No-figure evidence uses a stricter in-module floor (88)
ENABLE_FPI_FILINGS=false                      # Foreign private issuer (ADR) filings: list 20-F/6-K/40-F on the company page (page-scoped; default off — see tasks/archive/fpi-support-roadmap.md)
ENABLE_INSIDER_ACTIVITY=false                 # Insider (Form 4) endpoint; off = 404. Pairs with NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY; leave off until the insider scan fits the 1 req/s SEC pin
ENABLE_SECTION_CHANGES=false                  # "What changed" Item 1A wording diff; set on the service, the job images and the task worker together (the gate test_section_changes_flag_placement.py reads the three maps); off = nothing fetched, block null
SECTION_EXTRACTION_BATCH_LIMIT=25             # Filings extracted per scan run (one SEC request each, up to three attempts; about 2.7 s per filing)
SECTION_TEXT_MAX_CHARS=400000                 # Longer section texts are recorded as oversize without their text
NOTABLE_FILINGS_ENABLED=false                 # Local default; production serving pin is true under tasks/notable-rollout-2026-09-28.md (scan populates independently)
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
STRIPE_PRICE_MONTHLY_ID=...       # Required for checkout (empty default) — fails validation if misconfigured
STRIPE_PRICE_YEARLY_ID=...
PRO_TRIAL_DAYS=0                  # Card-required trial on Pro MONTHLY checkout. DEFAULT 0 = OFF
                                  # (rollout convention). Set 7 on the service only after the PR #619
                                  # Stripe test-mode checklist, IN LOCKSTEP with the frontend's
                                  # NEXT_PUBLIC_ENABLE_PRO_TRIAL=true (trial copy must not show while
                                  # checkout grants no trial). Bounded 0-30 at boot; one trial per
                                  # account (any prior Subscription row skips it).
REVERSE_TRIAL_ENABLED=false       # Retired no-card signup trial (superseded by PRO_TRIAL_DAYS); keep off
REVERSE_TRIAL_DAYS=7

# Email (Resend)
RESEND_API_KEY=...
RESEND_FROM_EMAIL=...             # Must be on a Resend-verified domain (else emails silently drop)
RESEND_WEBHOOK_SECRET=...         # Svix signing secret for the Resend webhook
FRONTEND_URL=https://www.earningsnerd.io  # Mail links, sign-in redirects, the mail header's tile

# Analytics & Monitoring
POSTHOG_API_KEY=...
SENTRY_DSN=...                    # Sentry error tracking DSN
SENTRY_RELEASE=...                # Release tag for Sentry events (CI sets $GITHUB_SHA; empty = SDK default)

# External APIs - Financial Modeling Prep (FMP)
# The in-app FMP/Finnhub/Stocktwits clients and the trending/hot-filings surfaces were torn down
# (WS-8a, 2026-09). FMP_API_KEY is read ONLY by the operator-run
# backend/scripts/refresh_index_membership.py when explicitly selecting `--source fmp`.
# Default/automatic refresh uses public constituents without a key; the workflow does not read it.
# Existing secrets remain founder-owned and are not changed by the public-source replacement.
# Removed 2026-09-04 (delete from any local .env — Settings forbids unknown keys and fails at import):
# FINNHUB_API_KEY, FINNHUB_API_BASE, FINNHUB_TIMEOUT_SECONDS, FINNHUB_MAX_CONCURRENCY,
# STOCKTWITS_TIMEOUT_SECONDS, FMP_API_BASE, FMP_TIMEOUT_SECONDS, FMP_MAX_CONCURRENCY,
# TWITTER_BEARER_TOKEN, HOT_FILINGS_REFRESH_TOKEN, HOT_FILINGS_USER_AGENT.
FMP_API_KEY=...

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
SENTRY_AUTH_TOKEN=...                              # Build-time only (Vercel): Sentry source-map upload. Unset = no upload, build still succeeds
SENTRY_ORG=...                                     # Sentry org slug for the source-map upload (pairs with SENTRY_AUTH_TOKEN)
SENTRY_PROJECT=...                                 # Sentry project slug for the source-map upload (pairs with SENTRY_AUTH_TOKEN)
NEXT_PUBLIC_TURNSTILE_SITE_KEY=...                 # Pairs with backend TURNSTILE_SECRET_KEY
NEXT_PUBLIC_LOGO_DEV_TOKEN=...                     # Logo.dev publishable token for CompanyLogo (blank = monogram fallback only)
NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS=true|false
NEXT_PUBLIC_ENABLE_SECTION_TABS=true|false
NEXT_PUBLIC_ENABLE_CALENDAR=true|false             # Earnings calendar (owned EDGAR+Alpha Vantage engine; FMP no longer used)
NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY=true|false     # Form 4 insider activity panel (needs backend ENABLE_INSIDER_ACTIVITY=true; keep both off, see above)
NEXT_PUBLIC_ENABLE_ANALYSIS=true|false             # Multi-Period Analysis (off: nav/CTA hidden + /analysis route 404s)
NEXT_PUBLIC_ENABLE_FPI_FILINGS=true|false          # The plan cards name 20-F filings; set WITH the backend ENABLE_FPI_FILINGS (the API deploy sets it true)
NEXT_PUBLIC_ENABLE_PRO_TRIAL=true|false            # Advertise the 7-day Pro trial (default off; flip WITH backend PRO_TRIAL_DAYS=7)
WAITLIST_MODE=...                                  # Server-side waitlist gating (not NEXT_PUBLIC_)
```

### Statement-aware financial extraction

`USE_STATEMENT_FINANCIALS` (boolean, default **true**) selects as-reported income-statement
revenue/components for financial institutions. It avoids treating a bank's fee-income tag as total
revenue. Non-financial issuers keep their existing extraction. An explicit false env value still
overrides the default; all reads use `app.config.Settings`. The founder's SIC backfill and any
persisted financial remediation are separate runs (see the WS-7 section of `DEPLOYMENT.md`).
WS-6 coordinates the parity measurement and single honest baseline re-pin; the default change
must carry observed eval gate evidence before merge.
