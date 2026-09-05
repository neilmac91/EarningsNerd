# Configuration Reference — environment variables

The complete environment-variable reference for backend (`backend/.env`) and frontend
(`frontend/.env.local`). Definitions and validation live in `backend/app/config.py`
(Pydantic Settings — ALL backend env access goes through it; never `os.getenv` in app code,
except the pre-Settings infra-bootstrap constants in `database.py`, `redis_service.py`, and
`edgar/config.py`)
and `frontend/lib/featureFlags.ts`. Production uses a mix of Cloud Run environment overrides and Google Secret
Manager mounts (see [DEPLOYMENT.md](DEPLOYMENT.md)).

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
| `DATABASE_URL` | `"sqlite:///./earningsnerd.db"` | Local SQLite fallback; production refuses SQLite and requires a Postgres/Cloud SQL connection string. |
| `REDIS_URL` | `"redis://localhost:6379"` | Local Redis endpoint. Production uses the L1 in-memory cache (ADR-0004). |
| `SKIP_REDIS_INIT` | `false` | Skip Redis initialization; true in hermetic tests and Redis-off deployments. |
| `SEC_EDGAR_BASE_URL` | `"https://data.sec.gov"` | SEC submissions/companyfacts API origin; calls must use the EDGAR service layer. |
| `SEC_USER_AGENT` | `"EarningsNerd/1.0 (contact@earningsnerd.io)"` | SEC contact identity; use a reachable operator address. |
| `SEC_RATE_LIMIT_PER_SECOND` | `10` | Per-process SEC request ceiling; SEC traffic from other processes also counts at the IP. |
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
| `STRIPE_PRICE_MONTHLY_ID` | `""` | Monthly checkout price ID; empty default makes configured checkout validation fail. |
| `STRIPE_PRICE_YEARLY_ID` | `""` | Yearly checkout price ID; empty default makes configured checkout validation fail. |
| `STRIPE_BETA_PROMO_CODE_ID` | `""` | Stripe Promotion Code ID for eligible beta invites; unset disables the discount. |
| `PRO_TRIAL_DAYS` | `0` | Card-required monthly trial; 0 disables; validated 0–30. Enable only with the matching frontend flag after the Stripe checklist. |
| `REVERSE_TRIAL_ENABLED` | `false` | Retired no-card signup trial; keep off. Cannot coexist with a positive PRO_TRIAL_DAYS. |
| `REVERSE_TRIAL_DAYS` | `7` | Duration of the retired reverse trial, days. |
| `REGISTRATION_MODE` | `"public"` | Validated public or invite_only registration; CI explicitly sets invite_only on the service. |
| `INVITE_EXPIRY_HOURS` | `168` | Invite token lifetime, hours. |
| `INTERNAL_JOB_TOKEN` | `""` | Shared internal-job endpoint secret; unset endpoints return 503. |
| `POSTHOG_API_KEY` | `""` | Server-side PostHog credential. |
| `POSTHOG_HOST` | `"https://us.i.posthog.com"` | Server-side PostHog ingestion origin. |
| `SENTRY_DSN` | `""` | Error tracking DSN; empty disables SDK setup. |
| `SENTRY_RELEASE` | `""` | Release tag; CI supplies the Git SHA; empty allows SDK detection. |
| `RESEND_API_KEY` | `""` | Outbound email credential; required for sending. |
| `RESEND_BASE_URL` | `"https://api.resend.com"` | Resend API origin. |
| `RESEND_FROM_EMAIL` | `"EarningsNerd <hello@inbound.earningsnerd.io>"` | Sender on a Resend-verified domain; complete surrounding quotes are normalized away. |
| `RESEND_WEBHOOK_SECRET` | `""` | Resend/Svix webhook signature secret. |
| `FRONTEND_URL` | `"https://earningsnerd.io"` | Public frontend origin used in email links. |
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
| `ENVIRONMENT` | `"development"` | Environment label; production enables SQLite refusal and secure-cookie derivation. |
| `COOKIE_NAME` | `"earningsnerd_access_token"` | Access-token cookie name. |
| `COOKIE_SECURE` | `false` | Declared default false; constructor derives true in production unless COOKIE_SECURE exists in the process environment. See precedence note below. |
| `COOKIE_SAMESITE` | `"lax"` | Cookie SameSite policy. |
| `COOKIE_DOMAIN` | `null` | Null means host-only. CI sets .earningsnerd.io for frontend/API cross-host sessions. |
| `CORS_ORIGINS_STR` | `"http://localhost:3000,http://127.0.0.1:3000,https://earningsnerd.io,https://www.earningsnerd.io"` | Comma-separated allowed origins; CORS_ORIGINS is a derived property, not another environment field. |
| `FMP_API_KEY` | `""` | Only the manual index-membership refresh uses this key; Wikipedia source is keyless. In-app FMP integration is retired. |
| `ALPHA_VANTAGE_API_KEY` | `""` | Licensed calendar bridge credential; leave empty for EDGAR-only operation until licensing is settled. |
| `ALPHA_VANTAGE_API_BASE` | `"https://www.alphavantage.co/query"` | Alpha Vantage calendar API endpoint. |
| `ALPHA_VANTAGE_TIMEOUT_SECONDS` | `20.0` | Calendar download timeout, seconds. |
| `ALPHA_VANTAGE_HORIZON` | `"3month"` | Calendar horizon: 3month, 6month or 12month. |
| `XBRL_CACHE_TTL_HOURS` | `24` | XBRL cache lifetime, hours. |
| `STRUCTURED_EXTRACTION_CACHE_TTL_SECONDS` | `3600` | Structured extraction retry cache lifetime, seconds. |
| `AI_DEFAULT_MODEL` | `"deepseek-v4-pro"` | Primary provider model; CI explicitly sets this and OPENAI_BASE_URL. |
| `AI_FAST_MODEL` | `""` | Optional cheaper task model; empty falls back to AI_DEFAULT_MODEL. Change only after evals. |
| `AI_SECTION_RECOVERY_MODEL` | `""` | Section-recovery override; empty falls back through AI_FAST_MODEL to AI_DEFAULT_MODEL. |
| `USE_STRUCTURED_OUTPUT` | `false` | Structured Phase-A response format; off pending eval bake-off. |
| `USE_EDGARTOOLS_SECTIONS` | `true` | Prefer native section extraction with legacy/thin-section fallback. |
| `AI_QUALITY_GATE` | `true` | Partial summaries persist but do not consume monthly quota. |
| `AI_FIGURE_TRACE_GATE` | `false` | Untraceable dollar figures tier summaries partial when armed; off keeps advisory audits. |
| `AI_FORWARD_QUOTE_GATE` | `false` | Drop forward quotes not verbatim in the filing when armed; off keeps advisory audits. |
| `AI_EVIDENCE_SNAP` | `false` | Replace unverifiable evidence with matched filing sentences when armed; off keeps advisory audits. Arm after the first weekly judged readout per D5. |
| `EVIDENCE_SNAP_MIN_SCORE` | `72.0` | Figure-bearing evidence similarity floor; no-figure evidence uses the separate in-module floor of 88. |
| `ENABLE_FPI_FILINGS` | `false` | Page-scoped 20-F/6-K/40-F discovery; CI explicitly enables it on the service. Other job form sets are separate. |
| `CALENDAR_INDEX_FILTER_ENABLED` | `false` | Restrict public calendar serve/ingest to committed index universe; watchlist exceptions remain; missing/short universe fails open. |
| `NOTABLE_FILINGS_ENABLED` | `false` | Serving gate only; scan job can populate while this is false. Arm only after the seed/quality rollout checklist. |
| `NOTABLE_FILINGS_SCAN_DAYS` | `2` | Scheduled scan trailing window, days; manual seed --days overrides it. |
| `RICHER_FINANCIALS_ENABLED` | `true` | Expanded cash-flow and working-capital facts; false restores legacy concept set. |
| `USE_STATEMENT_FINANCIALS` | `false` | Financial institutions use reported income-statement revenue; enable with eval evidence and remediate persisted facts separately. |
| `PRO_SUMMARY_MONTHLY_CAP` | `300` | Invisible Pro anti-abuse ceiling for fresh generations per month; 0 disables; billing remains unlimited. |
| `MAX_CONCURRENT_GENERATIONS` | `6` | Per-process full-generation semaphore; values at or below 0 disable the ceiling. |
| `RECOVERY_MAX_CONCURRENCY` | `3` | Concurrent section-recovery API calls. |
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
| `AI_INPUT_CACHE_HIT_PRICE_PER_1M` | `0.003625` | Configured USD estimate per million cached input tokens; telemetry assumption, not a live provider price quote. |
| `AI_INPUT_CACHE_MISS_PRICE_PER_1M` | `0.435` | Configured USD estimate per million uncached input tokens; update alongside model pricing. |
| `AI_OUTPUT_PRICE_PER_1M_TOKENS` | `0.87` | Configured USD estimate per million output tokens; does not model peak-hour surcharges. |
| `STREAM_HEARTBEAT_INTERVAL` | `3` | SSE heartbeat cadence, seconds. |
| `STREAM_TIMEOUT` | `600` | SSE timeout, seconds. |
| `STREAM_SECTION_REVEAL` | `false` | Progressive section previews with non-streaming fallback; CI enables on the service. |

### Backend configuration examples (.env)
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
AI_FORWARD_QUOTE_GATE=false                   # T5.4 forward-quote hard gate: when on, a §5 quote not locatable verbatim in the filing text is DROPPED at generation time (content repair — never tiers). Default off (advisory: audit + greppable forward_quote_unverified counter always emitted) until the fleet FP rate is measured
AI_EVIDENCE_SNAP=false                        # Evidence auto-snap (post-#631): when on, non-verifying P&L-takeaway/footnote supporting_evidence is REPLACED at generation time by the best-matching REAL excerpt sentence (which then earns the Verified badge). Default off (advisory: audit + greppable evidence_snap counter always emitted, recording original + candidate per would-snap) until the fleet wrong-snap rate is measured
EVIDENCE_SNAP_MIN_SCORE=72.0                  # Snap floor for FIGURE-BEARING evidence (rapidfuzz max(token_set, partial) on normalized text; the shared non-year-figure guard supplies the precision). No-figure evidence uses a stricter in-module floor (88)
ENABLE_FPI_FILINGS=false                      # Foreign private issuer (ADR) filings: list 20-F/6-K/40-F on the company page (page-scoped; default off — see tasks/archive/fpi-support-roadmap.md)
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
FRONTEND_URL=https://earningsnerd.io  # Used in email links (verification, reset)

# Analytics & Monitoring
POSTHOG_API_KEY=...
SENTRY_DSN=...                    # Sentry error tracking DSN
SENTRY_RELEASE=...                # Release tag for Sentry events (CI sets $GITHUB_SHA; empty = SDK default)

# External APIs - Financial Modeling Prep (FMP)
# The in-app FMP/Finnhub/Stocktwits clients and the trending/hot-filings surfaces were torn down
# (WS-8a, 2026-09). FMP_API_KEY is read ONLY by the operator-run
# backend/scripts/refresh_index_membership.py (index constituents; `--source wikipedia` is keyless).
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
NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY=true|false     # Form 4 insider activity panel
NEXT_PUBLIC_ENABLE_ANALYSIS=true|false             # Multi-Period Analysis (off: nav/CTA hidden + /analysis route 404s)
NEXT_PUBLIC_ENABLE_PRO_TRIAL=true|false            # Advertise the 7-day Pro trial (default off; flip WITH backend PRO_TRIAL_DAYS=7)
WAITLIST_MODE=...                                  # Server-side waitlist gating (not NEXT_PUBLIC_)
```
