# EarningsNerd — Security / Ops audit (read-only), 2026-09-04

> Appendix 05 of `docs/ENGINEERING_AUDIT_2026-09.md`. Workstream report reproduced as written; hypotheses are labelled by the author.

Scope: repo at `main` = `e8ea339` (2026-07-16). Production backend = `4994360` (PR #633 merge, deployed 2026-07-13 21:13Z, CI run 29285536512). Production frontend = Vercel @ `main`. The 2026-07-16 backend deploy (CI run 29524625738) was cancelled after ~6 h. **[verified]** = read in code/CI logs; **[hypothesis]** = inferred, needs a live-environment check (no GCP/Sentry/Stripe/Vercel access from this session).

Tools run: `npm audit --json` (preconditions met), read-only git, GitHub MCP (PRs, check runs, job logs). `pip-audit` not installed → backend advisories reasoned from `backend/requirements.txt`. Repo untouched.

---

## A. Dependabot / PR triage

| PR | Change | Security? | CI on PR head | Recommendation | Risk of merging as-is |
|---|---|---|---|---|---|
| **#629** typescript 6.0.3 → 7.0.2 (devDep, MAJOR) | TS 7 native compiler; lockfile drops `tsserver` bin, adds 20 platform binaries | No | **FAIL** frontend-tests: ESLint crash `TypeError: Cannot read properties of undefined (reading 'Cjs')` in `@typescript-eslint/typescript-estree` (job 86761685411). Root cause: typescript-eslint 8.62/8.63 peer `typescript >=4.8.4 <6.1.0` (PR diff). e2e + lighthouse fail too; base stale (`e47cf48`, 07-12); `mergeable_state: unstable` | **CLOSE** (`@dependabot ignore this major version`); revisit when eslint-config-next/typescript-eslint support TS 7 | High — breaks lint + typecheck |
| **#635** actions/setup-python 6 → 7 | ESM rewrite; removes `pip-install` input; drops EOL Pythons | Hygiene | all 7 green (07-20) | **MERGE** — `ci.yml` uses only `python-version: '3.11'` | Low, CI-only |
| **#636** actions/setup-node 6 → 7 | ESM rewrite; cache-key outputs | No | all green (07-20) | **MERGE** — `ci.yml` uses `node-version` + `cache` only | Low, CI-only |
| **#639** pillow 12.2.0 → 12.3.0 (via weasyprint) | Perf/docs release; CVE fixes were already in 12.2.0 | No | all green (07-21) | **MERGE** (or fold into #651); only PDF export path | Low |
| **#640** dompurify 3.4.11 → 3.4.12 (via posthog-js) | Fixes GHSA-c2j3-45gr-mqc4 (low); `npm audit` shows newer GHSA-55q2-fjhq-7xh7 (moderate XSS, `<=3.4.12`) | Yes (partial) | all green (07-22; rebased 08-31) | **MERGE**, expect a 3.4.13+ follow-up | Low |
| **#641** fast-uri 3.1.2 → 3.1.4 (via ajv ← schema-utils/webpack) | Fixes GHSA-v2hh-gcrm-f6hx, GHSA-4c8g-83qw-93j6; 4 more need ≥3.1.6 | Yes (build-time) | all green | **MERGE**; not runtime-exposed | Low |
| **#642** pyasn1 0.6.3 → 0.6.4 (via python-jose → rsa) | CVE-2026-59884/59885/59886 (ASN.1 DoS) | Yes | all green (07-22) | **MERGE**. Runtime path = RS256 verify of Google/Apple id_tokens against provider JWKS (`auth.py:963`, `1080+`) → low exploitability | Low |
| **#651** pip minor group ×13 (edgartools 5.40.1→5.51.0, fastapi 0.139→0.141.1, json-repair, lxml, **pandas 3.0.4→3.0.5**, posthog 7.21→7.39, pydantic-settings, python-dotenv, redis 8.0.1→8.1.0, +4) | No CVEs cited; **pandas 3.0.4 is YANKED** ("Reported segfaults with datetime-related functionality", pip warning in lead's `backend-gate.log:2`) | Indirect (stability) | **FAIL** backend-tests: ruff `Found 2767 errors` (job 97358758408) — **not caused by this PR** (see ruff note). Others green. `eval-baseline` "success" in 5 s = **self-skipped** (no `DEEPSEEK_API_KEY` secret, `ci.yml:150-159`) — not an AI-quality pass | **HOLD** until ruff gate fixed; then **SPLIT**: (a) merge pandas/fastapi/lxml/posthog/etc.; (b) edgartools 5.40→5.51 alone, through the eval gate (`backend/evals/RUNBOOK.md`) | Medium — edgartools jump can shift extraction; pandas bump is a must |
| **#652** npm minor group ×17 (next 16.2.10→16.3.3, eslint-config-next →16.3.3, @sentry/nextjs 10.63→10.71, axios 1.18.1→1.20.0, posthog-js 1.396→1.422, react-query, recharts, autoprefixer, sonner, playwright, vitest, @types/node, @vitejs/plugin-react, user-event, png-to-ico, …) | **Yes** — next 16.2.10 has 9 advisories fixed ≥16.2.11 (§B); body cites GHSA-2xp9-vwfh-vxw4, GHSA-hmw2-7cc7-3qxx, GHSA-p293-qw3h-jr36 | **FAIL ×4** (run 33369943476): frontend-tests — new rule `@next/next/no-location-assign-relative-destination` on `frontend/components/GlobalErrorBoundary.tsx:52` (`window.location.href = '/'`) under `--max-warnings 0`; lighthouse + e2e — **`next build` fails**: `app/globals.css:408 ::highlight(copilot-citation)` → "'highlight' is not recognized as a valid pseudo-element"; backend-tests — ruff (same as main) | **HOLD**. Bump Next by hand: fix the two sites, target **next ≥16.3.4** (audit fix version), then `@dependabot recreate` the rest | **High — would break the Vercel production build** |
| **#570** draft (adds `tasks/homepage-sections-review-prompt.md`) | Investigation prompt already executed: `tasks/homepage-sections-review-findings.md` on main; "Notable filings" replaced Trending Filings (`config.py` NOTABLE_FILINGS_ENABLED comment) | No | clean; base `d9d1102` (07-06) | **CLOSE** (superseded) | None |

### Dependabot run 33369722541 (08-31) failure **[verified]**
Log: `postcss | dependency_file_not_resolvable | "Override for postcss@8.5.26 conflicts with direct dependency."` `frontend/package.json` lists `postcss` as a direct dep (`"^8.5.15"`) AND in `overrides` with the same literal. npm requires an override on a direct dep to match its spec exactly; once Dependabot bumps the direct dep to 8.5.26 the override no longer matches → unresolvable. The group PR (#652) was still created, but **postcss is stuck at 8.5.15** (GHSA-r28c-9q8g-f849 high, GHSA-fxqj-rqcc-2cmp moderate; fixed ≥8.5.23) until the override becomes `"postcss": "$postcss"` (npm reference form) or is removed. The run also logged `14 vulnerabilities (1 low, 13 high)` during `npm ci` on the PR branch.

### ruff gate is red on main — blocks every backend PR **[verified]**
- `ci.yml:23-27`: `pip install ruff bandit` **unpinned**. `backend/ruff.toml`: no `select` (defaults) + `ignore = ["E501"]`.
- main's lint passed on 07-16 (job 87709818797). The same tree now fails with **2,767 errors, all in `tests/`**, rules `DTZ005, I001, UP017, RUF059, F401, RUF100, RUF012, ARG002, B017…` — none in the E/F defaults of ruff 0.15.x.
- Reproduced: `ruff 0.15.8` on `backend/` → "All checks passed!"; a fresh venv with ruff 0.16.6 → "Found 2767 errors". PyPI latest 0.16.6 → **[hypothesis]** a 0.16.x release changed default selection/config discovery.
- Fix: pin `ruff==0.15.8` (+ bandit) in `ci.yml`, or set `[lint] select = ["E","F"]` in `ruff.toml`.

---

## B. Vulnerability exposure

`npm audit --json` on `frontend/package-lock.json` (v3): **22 advisories — 16 high, 5 moderate, 1 low** (run 2026-09-04).

### Runtime-exposed
| Package (installed) | Runs where | Advisories | Fix | Applicability |
|---|---|---|---|---|
| **next 16.2.10** (direct) | Vercel server/edge — **live in prod now** | GHSA-6gpp-xcg3-4w24 middleware bypass (H); GHSA-m99w-x7hq-7vfj DoS Server Actions (H); GHSA-89xv-2m56-2m9x SSRF Server Actions custom server (H); GHSA-p9j2-gv94-2wf4 SSRF via rewrites (H); GHSA-68g3-v927-f742 + GHSA-4633-3j49-mh5q cache confusion (M); GHSA-4c39-4ccg-62r3 unbounded Server Action payload (M); GHSA-q8wf-6r8g-63ch image-optimizer SVG DoS (M); GHSA-955p-x3mx-jcvp server-function disclosure (M) | ≥16.2.11; audit target **16.3.4** (bundled sharp/postcss) | `frontend/middleware.ts` is the waitlist/auth UX gate → bypass advisory applies (backend still enforces auth). No `rewrites`, no `"use server"` files → SSRF/Server-Action items likely N/A. `next/image` used (1 file) with `remotePatterns` → optimizer DoS applies |
| **sharp 0.34.5** (`node_modules/next/node_modules/sharp`) | `next/image` optimizer | GHSA-f88m-g3jw-g9cj libvips CVE-2026-33327/33328/35590/35591 (H) | via next ≥16.3.x | Top-level sharp 0.35.3 is dev-only and clean |
| **postcss 8.5.15** (direct; Tailwind build) | build | GHSA-r28c-9q8g-f849 (H), GHSA-fxqj-rqcc-2cmp (M) | ≥8.5.23 — **blocked by override conflict** | Build-time only |
| nanoid 3.3.12 (via postcss) | build | GHSA-28wg-ghj8-5hjv, GHSA-2v37-7h3g-55p8 | ≥3.3.18 | unlocks with postcss |
| **dompurify 3.4.11** (via posthog-js) | client | GHSA-c2j3-45gr-mqc4 (L), GHSA-55q2-fjhq-7xh7 (M) | ≥3.4.13 | #640 reaches 3.4.12 only |
| fflate 0.4.8 (via posthog-js) | client | GHSA-px8p-9vwx-vf98 (M) | ≥0.4.9 | not attacker-reachable here |
| fast-uri 3.1.2 (via ajv ← webpack) | build | 6 host-confusion/SSRF advisories | ≥3.1.6 | #641 → 3.1.4 |
| browserslist 4.28.4 (via autoprefixer) | build | GHSA-c83g-rgw3-j3cx, GHSA-73wf-gq98-2v4g (H) | ≥4.28.7 | in #652 chain |
| brace-expansion 5.0.6 (@sentry/bundler-plugin-core), 2.1.1 (glob) | build plugin | expansion DoS (H) | patched minors | `node_modules/brace-expansion 1.1.15` is dev |

### Dev-only
undici 7.28.0 (jsdom/vitest), ip-address 10.2.0 (socks ← lhci), js-yaml 4.2.0/5.1.0 (@eslint/eslintrc, @lhci/utils), express/body-parser/qs (@lhci/cli), extract-zip → puppeteer-core → lighthouse (@lhci/cli 0.15.1; only "fix" is a downgrade — ignore), postcss-selector-parser (L), typescript.

### Backend (reasoned; pip-audit unavailable)
- **pyasn1 0.6.3** → 3 CVEs (#642). **pandas 3.0.4 yanked** (segfaults) and is what the 07-13 prod image was built from **[verified via pip warning, not via a crash]**; used by edgartools statements/XBRL → bump (#651).
- python-jose 3.5.0 post CVE-2024-33663/33664 (fixed 3.4.0). cryptography 49.0.0, requests 2.34.2, urllib3 2.7.0, jinja2 3.1.6, lxml 6.1.1, starlette 1.3.1, fastapi 0.139.0, sqlalchemy 2.0.51 — no advisories known to me **[hypothesis; add `pip-audit -r backend/requirements.txt` to CI]**.
- **No dependency-audit gate** on either side: `npm ci` prints vulnerabilities and continues; bandit scans code only.

---

## C. Auth / authorization

### Verified sound
- **JWT**: HS256 (`config.py ALGORITHM`); `SECRET_KEY` validator rejects placeholders/<32 chars in every env (`config.py check_secret_key`); decode requires `exp,sub,iat,iss,aud`, 10 s leeway (`backend/app/routers/auth.py:361-367`); access 30 min; header or HttpOnly cookie (`auth.py:337-344`).
- **Refresh**: opaque, SHA-256 at rest, single-use rotation, reuse → chain revoked (`services/refresh_token_service.py:75-127`); cookies cleared on failure (`auth.py:671-712`); reset-password revokes all sessions (`auth.py:856-858`).
- **Reset/verify tokens**: `secrets.token_urlsafe(32)` hashed SHA-256, single-use, expiry-checked (`auth.py:177-185, 721-733, 839-850`). The 6 naive `datetime.utcnow()` sites (`refresh_token_service.py:66,100,144,150`; `auth.py:1055,1100`) match `tests/unit/test_naive_utcnow_allowlist.py` exactly.
- **Invite-only enforced server-side**: `settings.REGISTRATION_MODE == "invite_only"` checked before any account work (`auth.py:521-533`) via `invite_service.validate_invite` (`:67-77`, hash lookup, revoked/used/expired/email-bound) with guarded single-use redemption (`:80-89`); validator fails closed on typos (`config.py _normalize_registration_mode`). Deploy sets `REGISTRATION_MODE=invite_only` (`ci.yml` deploy step; added `a37f3b8` 07-09, before the 07-13 deploy → in prod). **Live value unverified** (`ops.yml describe-service` withholds it).
- **Login**: 10/min/IP (`auth.py:20`) + **DB-backed** per-account lockout, 10 failures → 15 min, email-hash keyed (`services/login_lockout.py:29-30`); unified 401; dummy bcrypt (`auth.py:622-660`).
- **Admin**: `is_admin` column; `_require_admin` (`admin.py:33-47`) in all 16 admin routes (AST scan: 0 missing); `/metrics` admin-only (`main.py:539-555`); no code grants `is_admin`.
- **Internal triggers**: `X-Internal-Token` via `hmac.compare_digest`, 503 when unset (`internal.py:26-36`); all 9 `/internal/jobs/*` routes gated.
- **Entitlements (rule 4)**: `is_pro` reads outside `entitlements.py` are only mirror writers (`subscription_sync.py:79,153,194`) and serializers (`users.py:80,115,337`, `auth.py:1207`); `subscriptions.py:113` derives from `get_plan()`; gates via `app/dependencies.py`; exports gate on `can_export`.
- **CORS**: explicit origins from `CORS_ORIGINS_STR`, credentials, explicit methods/headers, localhost regex only outside prod (`main.py:187-218`); API headers incl. HSTS (prod) + `CSP default-src 'none'` on `/api/` (`main.py:245-256`).
- **Stripe checkout**: `metadata.user_id` set server-side; discount/trial not self-grantable (`tests/unit/test_checkout_session.py:249`).

### Findings
| # | Finding | Evidence | Sev | Fix |
|---|---|---|---|---|
| C1 | **Anonymous cost holes still live in prod** (backend never redeployed): `GET /api/hot_filings?force_refresh=true` bypasses the 15-min cache → DB aggregation + FMP/Finnhub per request; `/api/companies/{t}/insiders` and `/api/search/full-text` hit SEC live with **no per-IP limit** (0 `enforce_rate_limit` in `4994360:backend/app/routers/{insiders,search}.py`); API-host `robots.txt` only disallows `/api/` (`4994360:backend/main.py:533`) so the then-uncached `/sitemap.xml` is crawlable. Fixes `b8cb847`, `d5ce7ac`, `944725c` are on main, undeployed | `git show 4994360:backend/app/routers/hot_filings.py:12-19`; run 29524625738 cancelled | **P1** | Unblock deploy (D1) |
| C2 | `GET /api/trending_tickers/refresh-prices?symbols=…` unauthenticated, unlimited, fans out to FMP for ≤50 symbols/call (`trending_service.refresh_prices` → `_fmp.get_quotes`); not covered by `b8cb847` | `routers/trending.py:49-79`; `services/trending_service.py:162-174` | **P1/P2** (P1 if FMP key is quota'd/paid) | `RateLimiter` like `insiders.py:20,40`, or retire in favour of cached `/trending_tickers` |
| C3 | All `RateLimiter`s per-process (`services/rate_limiter.py:13-33`); `--max-instances=2` → limits are 2× and reset on deploy; only login lockout is DB-backed | lesson `arch-per-process-state-on-cloud-run.md`; runbook §6 | P2 | Acceptable now; document; DB/Cloud Armor before raising instances |
| C4 | Turnstile dark unless both keys set, **fails open** on infra errors; prod state unknown | `services/turnstile.py:36-55`; runbook §6 "Action for you" | P2 **[prod state hypothesis]** | Confirm via `ops.yml describe-service`; consider fail-closed on `/register` |
| C5 | `X-Admin-Token` compare is `!=` (not constant-time) vs `internal.py:35` | `routers/hot_filings.py:84-86` | P2 (low practical) | `hmac.compare_digest` |
| C6 | **Rule 8 drift**: `main.py:21,26,29` `os.getenv` for Sentry outside the 3 sanctioned files though `Settings.SENTRY_DSN` exists; no AST gate for `os.getenv` (rule 12) | `backend/main.py:21-29`; `CLAUDE.md` rule 8 | P2 | Init Sentry from `settings` (or sanction `main.py`) + allowlist test |
| C7 | Cookie auth SameSite=lax + credentialed CORS, no CSRF token — safe because state changes are POST/DELETE and CORS is allow-listed | `auth.py:237-282`; `config.py COOKIE_SAMESITE` | P2 (guard) | Gate: no authenticated side-effecting GET |
| C8 | Plaintext e-mail in logs (`auth.py:428`, `auth.py:826`) | runbook §6 P3 | P3 | Hash/drop |
| C9 | Client Sentry ships `console.log/warn/error` to Sentry Logs, no `beforeSend` scrub (`instrumentation-client.ts:12`); backend OK (`send_default_pii=False` `main.py:38`; id-only `set_user` `auth.py:388`) | | P3 | Drop `"log"`; add scrubber |
| C10 | Docs drift: `docs/OPERATIONS.md:16` omits admin-JWT on `/metrics`; runbook §6 still lists XFF trust as deferred though `TRUSTED_PROXY_HOPS` is implemented (`rate_limiter.py:63-86`) and deployed; no admin-promotion procedure | | P3 | Fix in next docs PR |

---

## D. Observability, alerting, backups

| Failure | Existing signal | Notified | Gap |
|---|---|---|---|
| API down | `/health`, `/health/detailed` (`main.py:400-500`); checked only by the deploy's "Verify health" | nobody | No uptime check / alert policy anywhere (`docs/OPERATIONS.md:130-137` is a never-implemented "Suggested Thresholds" table) |
| Cloud Run job failed (7 jobs) | `logger.exception` in `internal.py` wrappers | nobody | No `job/completed_execution_count{result=failed}` alert; Scheduler failures unalerted |
| SEC breaker open | `logger.warning("Circuit … open")` (`main.py` handler); `/health/detailed` → degraded | nobody | No log-based alert |
| AI provider down 1 h | per-request failures; Sentry only for unhandled | nobody (Sentry rules **[unknown]**) | No error-rate alert |
| Stripe webhook failing | 500 on unexpected errors → Stripe retries (`subscriptions.py:392-393`); `stripe_events` audit trail | Stripe's endpoint-failure e-mails **[hypothesis]** | No in-app alert / post-deploy webhook check |
| Deploy hung | GitHub cancel after 6 h (no `timeout-minutes`) | founder via GitHub mail | D1 |
| Data quality | weekly e-mail (`data-quality-weekly.yml`, Mon 13:00 UTC) | founder | Works — the only proactive prod signal |

### D1 — Why the 07-16 deploy hung **[verified: job 87710378965]**
"Apply database migrations" re-applies all 32 `backend/migrations/*.sql` every deploy. psql finished `20260120_create_waitlist_signups.sql`, then **blocked at `20260122_add_markdown_cache_columns.sql:7` (`ALTER TABLE filing_content_cache ADD COLUMN IF NOT EXISTS …`) from 18:40:39Z until the 00:38:50Z cancel** ("server closed the connection unexpectedly" only when the proxy got SIGTERM). `ADD COLUMN IF NOT EXISTS` takes **ACCESS EXCLUSIVE** even as a no-op; the psql call has **no `lock_timeout`/`statement_timeout`**. Something held a conflicting lock on `filing_content_cache` (hot table: read by `routers/filings.py`, written by `services/content_cache.py`, `precompute_service.py`, `summary_generation_service.py`) for ≥6 h **[hypothesis: idle-in-transaction pooled connection or long job session]**. A *waiting* ACCESS EXCLUSIVE queues all later lock requests → filing-page reads likely stalled during the hang **[hypothesis — check Cloud Run 5xx/latency 07-16 18:40–00:38 UTC]**. Same class as `lessons/ops-no-ddl-in-startup-path.md`, now in the pre-deploy step.
Fix: `export PGOPTIONS='-c lock_timeout=15s -c statement_timeout=300s'` before the psql loop; retry ×3 with backoff; `timeout-minutes: 30` on `deploy-backend`. Structural: a `schema_migrations` ledger so applied files are skipped (no lock taken) — files stay idempotent per rule 3.

### Backups **[hypothesis unless noted]**
- Instance created with `--database-version=POSTGRES_15 --tier=db-g1-small --region=us-west1 --storage-size=10GB --storage-auto-increase` (`docs/DEPLOYMENT.md:103-105`, `tasks/gcp-deploy-runbook.md:36-38`) — **no** backup/PITR/retention/deletion-protection flags **[verified]**. gcloud defaults → daily backups ON (7 kept), **PITR OFF** (Enterprise edition), deletion protection OFF **[confirm: `gcloud sql instances describe earningsnerd-db --format='yaml(settings.backupConfiguration,settings.deletionProtectionEnabled)'`]**.
- No restore runbook, no drill, no scheduled export; only export procedure is the decommission dump for the OLD instance (`tasks/archive/db-network-lockdown-runbook.md:86-101`).
- Secret rotation documented only for `SECRET_KEY` (runbook §3).

---

## E. Unfinished ops work
1. Backend undeployed since 07-13 (D1 blocks); `--remove-env-vars=ENABLE_GUEST_DAILY_QUOTA` + `guest_daily_usage` table (`migrations/20260702_create_guest_daily_usage.sql`) have no code references — dead table.
2. Backend lint gate red with current ruff (A).
3. Dependabot postcss override conflict (A).
4. Next.js security bump needs `GlobalErrorBoundary.tsx:52` + `globals.css:408` fixed first.
5. pandas 3.0.4 yanked in pinned requirements and prod image.
6. Runbook §6 open: Turnstile keys (unknown), DPAs, MFA, retention purge jobs (`refresh_tokens`, `audit_logs`, `login_attempts`), log scrubbing; XFF entry stale.
7. `ops.yml` push trigger targets branch `claude/earningsnerd-data-quality-fpg7bz` (gone from remote) → dead; leftover `ops/requests/current.json`; `describe-service` allow set lacks `REGISTRATION_MODE`.
8. Docs drift (C6, C10); OPERATIONS.md thresholds never implemented; `tasks/todo.md` (finished SEO plan) not archived.
9. Stripe contract tests (locked) cover signature/malformed 400s, unknown user, StripeObject regression, idempotency, past_due/deleted downgrade; `invoice.payment_failed` and `trial_will_end` branches untested (log/telemetry only) — assessment only.
10. Close #629, #570.

---

## F. Top-5 investments
1. **Safe deploys, ship main** (½ day): PGOPTIONS lock/statement timeouts + retry + `timeout-minutes` in `ci.yml`; redeploy (closes C1 + sitemap crawl); then a `schema_migrations` ledger. Verify prod env (`REGISTRATION_MODE`, `TURNSTILE_SECRET_KEY`) via `ops.yml describe-service`.
2. **Pin CI toolchain, gate deps** (1 h): pin ruff/bandit or explicit `select`; `"postcss": "$postcss"`; add `pip-audit` + `npm audit --omit=dev --audit-level=high` steps (rule 12).
3. **Security bumps** (2–3 h): merge #642 #640 #641 #639 #635 #636; Next ≥16.3.4 by hand; split #651 (pandas first, edgartools via eval).
4. **Minimum alerting** (2 h): uptime check + alert on `/health/detailed`; Cloud Run job-failure alert; log-based alerts for circuit-open and generation failures; confirm Sentry rules + Stripe webhook health.
5. **Backup posture** (2 h + drill): PITR + deletion protection; monthly `gcloud sql export` to lifecycle-managed GCS; one-page rehearsed restore runbook.

Quick wins: constant-time admin-token compare (C5); rate-limit `refresh-prices` (C2); drop `"log"` from client Sentry console levels (C9); doc fixes (C10).
