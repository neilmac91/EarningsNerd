# EarningsNerd deploy / infra audit — 2026-09-04

> Appendix 01 of `docs/ENGINEERING_AUDIT_2026-09.md`. Written by the deploy/infra workstream; corrected by the lead where noted (CONCURRENTLY usage).

Scope: root cause of the hung `deploy-backend` job on PR #634 (run 29524625738, job 87710378965), production-vs-main drift, the other three workflows, deploy-design fragility, remediation. Repo state audited: branch `claude/earnings-nerd-audit-plan-8iikp3` == `main` @ `e8ea339` (2026-07-16). Production backend == `4994360` (PR #633, deployed 2026-07-13 21:19Z, CI run 29285536512 green). GitHub facts were pulled live via the Actions API today.

Severity: P0 = production-impacting / blocks all deploys; P1 = bites on the next deploy or silently degrades a feature; P2 = hygiene/drift. Effort = engineer-hours to land + verify.

## Summary

**Root cause (confirmed, high confidence).** The deploy hung on `backend/migrations/20260122_add_markdown_cache_columns.sql:4-7` — `ALTER TABLE filing_content_cache ADD COLUMN IF NOT EXISTS …` (psql reports the statement's last line, 7). The three columns have existed since January, so this was a **no-op re-application**, but PostgreSQL takes `ACCESS EXCLUSIVE` before the `IF NOT EXISTS` check, so one open transaction that had read `filing_content_cache` parked it. There is no `lock_timeout`/`statement_timeout` anywhere in the repo, and `deploy-backend` has no `timeout-minutes` (`ci.yml:287-296`) — the job ran 360 min 11 s (18:38:42Z → 00:38:53Z) and was killed by **GitHub's default 6 h job timeout**, not by a person. PR #634 added zero migration files (`git diff 4994360..e8ea339 -- backend/migrations` is empty); the loop at `ci.yml:366-369` re-applies all 32 files every deploy, taking ~20 ACCESS EXCLUSIVE + ~43 SHARE locks on hot tables for nothing. Who held the lock for 6 h is **unknown** (hypotheses ranked: zombie idle-in-transaction backend ≈50%, a human psql/Studio session ≈25%, stuck SSE generator ≈15%, hand-run job ≈10%). Important collateral hypothesis to verify: while the ALTER waited, every new query on `filing_content_cache` (filing content endpoint, every summary generation) queued behind it, and stuck threadpool threads would have wedged the 12+8 pool → probable broad 503s 18:40Z–00:38Z on 7/16–17. Check Cloud Run metrics/Sentry for that window.

**Production vs main drift (backend @4994360 vs @e8ea339, 8 files):** sitemap rewrite (truthful lastmod, only summarized filings, 1 h cache; prod runs two uncached full scans per hit and advertises URLs that frontend@main marks `noindex`); API-host `robots.txt` `Disallow: /` (prod still `Allow: /` + non-www sitemap pointer); anonymous `force_refresh` removed from `/api/hot_filings`; 30/min/IP limit on `/insiders`; 20/min/IP on `/search/full-text`; three test files. **No live frontend/backend incompatibility**: all four SSR endpoints frontend@main fetches exist at 4994360 (`companies.py:436`, `filings.py:170,390`, `summaries.py:418`); new rate limits key on browser IP, not Vercel's.

**Other automation:** `refresh-index-membership.yml` failed on both 8/1 and 9/1 because Wikipedia's Nasdaq-100 article **no longer contains a constituents table at all** (verified live via the MediaWiki sections API today) — permanent loss of the keyless source; bounded impact (filter fails open, committed list from 2026-07-07). `data-quality-weekly.yml` 8/8 green (latest 8/31). `ops.yml` dormant since 7/8; still has a `push` trigger on a stale branch that exists on origin. Lead's ruff finding folded in: `ci.yml:27` installs ruff/bandit unpinned, so the next backend push likely goes red at lint before deploy can run.

**Top 3 remediation items:**
1. **P0 — one PR that both hardens and catches up (≈4 h):** `timeout-minutes: 30` on the job; `PGOPTIONS="-c lock_timeout=10s -c statement_timeout=120s -c idle_in_transaction_session_timeout=30s"` + retry on 55P03 + `pg_stat_activity` dump on failure; pin `ruff==0.15.8`/bandit via `requirements-dev.txt`; rule-12 gate `backend/tests/unit/test_migration_lock_safety.py` (asserts ci.yml timeouts; frozen allowlist of the 17 legacy unguarded files; new files must use `DO $$ IF NOT EXISTS` guards / `CONCURRENTLY`). The test lives under `backend/`, which is what triggers CD — there is no other lever: `workflow_dispatch` never deploys (`ci.yml:290`) and the 7/16 run is past GitHub's 30-day re-run window. Pre-flight: check `pg_stat_activity` for idle-in-transaction sessions first.
2. **P0 — stop re-applying applied files (≈3 h):** `schema_migrations(filename, sha256, applied_at)` ledger so the loop skips recorded files; plus Cloud SQL flag `idle_in_transaction_session_timeout=600000` as a DB-side backstop. Supersede rule 3's "re-apply ALL" wording with a lesson.
3. **P1 — index-membership source (≈2 h):** switch to `--source fmp` with an `FMP_API_KEY` secret (or another keyless Nasdaq-100 source) and add failure notification; plus doc sync (`DEPLOYMENT.md:28,65,359-365`, `CLAUDE.md:120` says 6 jobs, ci.yml updates 7).

---

## Full report

### 1. Root cause of the 6-hour hang — CONFIRMED

**1.1 Timeline (UTC, from `get_workflow_job` + job log)**

| Time | Event |
|---|---|
| 07-16 18:36:19 | CI run starts on push of merge `e8ea339` |
| 18:38:42 | `deploy-backend` starts (tests green) |
| 18:38:52–18:40:23 | Build/push OK — `backend:e8ea339`, digest `sha256:16036cef…` (image exists today) |
| 18:40:23 | "Apply database migrations" starts; proxy `Listening on 127.0.0.1:5432` at 18:40:37 |
| 18:40:39 | File 1 `20260120_create_waitlist_signups.sql` applies in 0.6 s (4× "already exists, skipping") |
| 18:40:39 | File 2 `20260122_add_markdown_cache_columns.sql` — proxy `Accepted connection from 127.0.0.1:58220` … silence |
| 07-17 00:38:50 | SIGTERM to proxy; `psql:…20260122_add_markdown_cache_columns.sql:7: server closed the connection unexpectedly` |
| 00:38:53 | Job completed; steps 8–11 (Deploy Cloud Run, both job-image updates, Verify health) `skipped` |

Duration 360 min 11 s = GitHub Actions' default job `timeout-minutes` (360). Nobody cancelled it; the default timeout did (reported as "cancelled"). `deploy-backend` sets no timeout (`ci.yml:287-296`); only `e2e-tests` does (`ci.yml:213`).

**1.2 The blocking statement** — `backend/migrations/20260122_add_markdown_cache_columns.sql:4-7`:

```sql
ALTER TABLE filing_content_cache
ADD COLUMN IF NOT EXISTS markdown_content TEXT,
ADD COLUMN IF NOT EXISTS markdown_generated_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS markdown_sections JSONB;
```

Target table is `filing_content_cache`, not `summaries`. The columns are in the ORM (`app/models/__init__.py:313-315`) and have been re-applied on every deploy since 2026-07-07, so this was a no-op. PostgreSQL resolves `ALTER TABLE … ADD COLUMN` to `AccessExclusiveLock` and acquires it when opening the relation, before the `IF NOT EXISTS` name check inside the sub-command. `IF NOT EXISTS` suppresses the error, not the lock. `ACCESS EXCLUSIVE` conflicts with the `ACCESS SHARE` any open `SELECT` transaction holds. Repo-wide grep for `lock_timeout|statement_timeout|idle_in_transaction` (py/yml/sql/md) = 0 hits. psql ran non-interactively; no prompt.

**1.3 What held the lock — UNKNOWN, ranked hypotheses.** Excluded: no `ops.yml` run that day (last 07-08); 07-16 was a Thursday (no Monday crons); `filing-scan` has a 1800 s task-timeout and commits per company (`app/services/filing_scan_service.py:225,260`).
1. Zombie "idle in transaction" backend from a SIGKILLed Cloud Run instance/job task (~50%). No `idle_in_transaction_session_timeout` set anywhere.
2. Human session (Cloud SQL Studio / psql) left inside `BEGIN` (~25%).
3. App request-scoped transaction (~15%): `stream_filing_summary` opens `session = database.SessionLocal()` (`summary_pipeline.py:196`); first query `joinedload(Filing.content_cache)` (`:214`) takes ACCESS SHARE; committed at `:897/:924`, closed `:1040`; `record_progress` commits interleave; generator bounded by `PIPELINE_TIMEOUT_SECONDS = 120` (`:137`). Only a generator parked at `yield` with a dead consumer stretches this.
4. Hand-run maintenance job (~10%): `scripts/backfill_facts.py:43,80,109`, `scripts/backfill_filing_history.py:36` use one session per run, but commit per company.

**1.4 Probable collateral production impact — VERIFY (P0 as incident).** Postgres queues new conflicting requests behind a waiting request. While the ACCESS EXCLUSIVE request waited (18:40:39 → 00:38:50), every new query on `filing_content_cache` blocked: `GET /api/filings/{id}/content` (`routers/filings.py:422`), every summary generation (`summary_pipeline.py:214,447,556,865`; `summary_generation_service.py:459,508`; `routers/summaries.py:163,355,444`). Blocked psycopg2 calls hold threadpool threads and pooled connections even after Cloud Run's 600 s timeout; pool is 12+8 per instance with `pool_timeout=10` (`ci.yml:388`; `app/database.py:22,40`), so ~20 such requests wedge an instance and all DB-backed endpoints 503. Medium-high confidence the API was severely degraded for most of that window. Check Cloud Run 5xx/latency and Sentry before the next deploy.

**1.5 Pattern breadth (all files re-run every deploy).** 32 files; counting top-level statements outside `DO $$`:
- 20 `ALTER TABLE … ADD COLUMN IF NOT EXISTS`/`DROP NOT NULL` in 17 files, ACCESS EXCLUSIVE on: `filing_content_cache` (20260122), `users` (20260126, 20260615 ×2, 20260620_users, 20260624_is_beta, 20260629), `companies` (20260618, 20260706, 20260711), `watchlist` (20260618, 20260703), `filings` (20260620_filing), `user_usage` (20260621, 20260707), `invite_codes` (20260624_cohort), `notification_preferences` (20260628), `trend_analysis` (20260708_add), `summaries` (20260708_summary ×2).
- ~43 `CREATE INDEX IF NOT EXISTS`; none uses `CONCURRENTLY` (`20260710_filings_company_type_date_index.sql` deliberately chose a plain `CREATE INDEX`, per its header comment). Non-concurrent CREATE INDEX takes SHARE on the table before the existence check (medium confidence on ordering) — queues behind open writers.
- Only `20260705_summary_filing_id_unique.sql` uses the lock-free `DO $$ IF NOT EXISTS (SELECT … pg_constraint) THEN ALTER … END IF $$` pattern.
- `git diff 4994360..e8ea339 -- backend/migrations` is empty. The step was introduced in `f66ace1` (2026-07-07); 40 backend pushes since. The loop (`ci.yml:366-369`) has no "new file" notion — always applies all 32 → ~60 lock acquisitions per deploy for zero schema benefit. The missing timeout turned a 10 s stall class into a 6 h outage.

### 2. Backend on `main` but NOT in production (`git diff --stat 4994360..e8ea339 -- backend/`, 8 files, +409/−37)

| File | Change | Impact today (prod = old) | Catch-up risk |
|---|---|---|---|
| `app/routers/sitemap.py` (+137) | Truthful `lastmod`; only companies with ≥1 filing and filings with a summary; 45k cap; `/terms`; 1 h per-process cache + single-flight; sync endpoint | Prod runs two uncached full scans per `/sitemap.xml`, stamps "today" as lastmod daily, and lists summary-less filings that frontend@main marks `noindex` (`frontend/app/filing/[id]/page.tsx:85`) — live sitemap/noindex contradiction | None |
| `main.py` robots.txt | API host → `Disallow: /` (was `Disallow: /api/` + `Allow: /` + non-www sitemap pointer) | Crawlers currently invited onto the API host and its uncached sitemap | None |
| `app/routers/hot_filings.py` | Anonymous `force_refresh` removed; refresh only via admin-token POST | Prod: any caller can force full recompute (cost/abuse) | None — no frontend caller (grep = 0); unknown query params ignored |
| `app/routers/insiders.py` | 30/min/IP on `GET /api/companies/{ticker}/insiders` (live EDGAR) | Anonymous bursts can starve the 10 req/s SEC budget | Caller `InsiderActivityPanel` is `'use client'`; keyed on browser IP via `TRUSTED_PROXY_HOPS=1` (`rate_limiter.py:75-84`). Safe |
| `app/routers/search.py` | 20/min/IP on `GET /api/search/full-text` | Same class | Client-side, feature-flagged. Safe |
| `tests/smoke/test_critical_paths.py`; `tests/unit/test_public_edgar_rate_limits.py` (+70); `tests/unit/test_sitemap.py` (+174) | Tests | — | — |

**2.1 frontend@main → backend@main dependency: none.** `frontend/lib/serverApi.ts:226-236` fetches `/api/companies/{ticker}`, `/api/filings/company/{ticker}`, `/api/filings/{id}`, `/api/summaries/filing/{id}` — all exist at 4994360 (`routers/companies.py:436`, `routers/filings.py:170,390`, `routers/summaries.py:418`; prefixes `main.py:341,344,345`). `frontend/app/sitemap.ts:70-81` tolerates optional lastmod. SSR fetches use `AbortSignal.timeout(5000)` and degrade to the client shell. Frontend-only drift: `frontend/vercel.json` `iad1 → pdx1` while `docs/DEPLOYMENT.md:65` still says `iad1`.

### 3. Other automation

**3.1 `refresh-index-membership.yml` — failing every month (P1, root cause confirmed).** Runs 30694838077 (08-01) and 33511750077 (09-01) both: `ERROR fetch failed (wikipedia): no constituents table found at https://en.wikipedia.org/wiki/Nasdaq-100`, exit 2, from `_read_wiki_table` (`backend/scripts/refresh_index_membership.py:116`). S&P page still parses. Verified today (page HTML + MediaWiki `action=parse&prop=sections|wikitext`): the Nasdaq-100 article has no Components section (sections: History, Selection criteria, Performance, Record values, Annual returns, Closing milestones…), wikitext has 0 "Ticker" and 4 tables; `List_of_Nasdaq-100_companies` and `Nasdaq-100_companies` 404. Permanent loss of the keyless source. Bounded impact: committed list `backend/app/data/index_membership.json` (wikipedia, 515, from `db47315` 2026-07-07), filter fails open, `CALENDAR_INDEX_FILTER_ENABLED` ships off. Fix: `--source fmp` + `FMP_API_KEY` secret (verify FMP plan includes constituent endpoints), or another keyless Nasdaq-100 source behind the existing sanity floor; add failure notification (two failures unnoticed for 5 weeks). ~2 h.

**3.2 `data-quality-weekly.yml` — healthy.** 8/8 success, latest 33430093824 (08-31). Executes `earningsnerd-filing-digest --args=scripts/data_quality_report.py --wait` (`:42-44`); depends on `GCP_WIF_PROVIDER`/`GCP_DEPLOYER_SA` (present) and the job carrying DATABASE_URL + RESEND_API_KEY. Green = job exited 0, not "email arrived". Runs on the job's current image (4994360) — fine.

**3.3 `ops.yml` — dormant since 07-08 (P2).**

> **Lead correction (PR #653 review, 2026-09-04):** the branch named in the push trigger no longer exists on origin (`git ls-remote` returns nothing), so the trigger is dead rather than dangerous; the fix is to remove the trigger, not delete a branch.
 17 runs, one failure (run 10, fixed by run 11). Fragility: `on.push.branches: [claude/earningsnerd-data-quality-fpg7bz]` + `paths: ops/requests/**` (`ops.yml:47-49`) still fires prod ops from a stale branch that exists on origin (`git ls-remote`); same no-`lock_timeout` psql pattern (`ops.yml:212-214`, read-only SQL); `concurrency: ops` separate from `deploy-backend` — "do not dispatch during a deploy" is prose only (`ops.yml:16`); `cloud-sql-proxy` v2.14.0 downloaded without checksum (also `ci.yml:349-351`).

### 4. Deploy design fragility

- **4.1 Timeouts (P0):** none on the job (`ci.yml:287-296`); none in psql (`ci.yml:368`); `pg_isready` loop bounded 30 s but unasserted (fails fast anyway).
- **4.2 Concurrency (P1):** `group: deploy-backend, cancel-in-progress: false` (`ci.yml:291-293`) — no deadlock, but a hung deploy holds the group 6 h; later pushes queue.
- **4.3 Levers (P1):** `Detect backend changes` (`ci.yml:303-312`) diffs `HEAD^..HEAD` for `^backend/` → a ci.yml-only fix does not deploy. `deploy-backend.if` requires `push` (`ci.yml:290`) → `workflow_dispatch` never deploys. GitHub re-run window is 30 days; the 07-16 run is 50 days old → not re-runnable. Only lever: a push to main touching `backend/`. Fallback: hand-run `gcloud run deploy … --image=…:e8ea339` with flags from `ci.yml:381-391` + `update-traffic` + job updates (drift-prone).
- **4.4 Docs drift (P2):** `DEPLOYMENT.md:28-29` says health-check `/health` (code: `/health/detailed`, `ci.yml:417-428`); `:28` "refreshes the pregeneration job" (code updates 7 jobs, `ci.yml:405`); `CLAUDE.md:120-121` "all 6 Cloud Run jobs" (7 incl. `earningsnerd-notable-filings`); `DEPLOYMENT.md:65` `iad1` vs `pdx1`; `DEPLOYMENT.md:359-365` still says apply two migrations by hand (contradicts line 14); `:32` "Nothing manual" — deployer-SA IAM only documented in `ci.yml:336-337`; `lessons/arch-migrations-no-alembic.md` equates idempotent with safe.
- **4.5 Unpinned lint toolchain (P1, lead's evidence):** `ci.yml:27` `pip install ruff bandit`; no pin in `backend/requirements*.txt` or `ruff.toml`. Lead measured ruff 0.15.8 clean vs 0.16.6 → 2767 findings. Lead confirmed: the tree is clean under 0.16.6 with an explicit `--select E,F`, i.e. 0.16 widened the default rule set; explicit `select` in ruff.toml + a pin removes the drift.

### 5. Remediation

**5a. Catch-up (P0, ~1 h founder time + the PR).** Do not re-trigger CD as-is.
1. Confirm the 07-16 incident window in Cloud Run metrics/Sentry (0.5 h).
2. Pre-flight (0.5 h, read-only, Cloud SQL Studio or `gcloud sql connect`, or a new `ops/detection/pg_activity.sql` via `ops.yml detection-sql`): `SELECT pid, state, xact_start, application_name, client_addr, left(query,80) FROM pg_stat_activity WHERE state <> 'idle' AND xact_start < now() - interval '2 minutes'`; `pg_locks` joined to `pg_class` for `filing_content_cache`. `pg_terminate_backend` any zombie.
3. Land one PR: §5b + §5c (tests under `backend/tests/unit/` trigger CD) + ruff pin + doc sync. Merging is the catch-up; migrations are a pure no-op (no new files since #633).
4. Watch the migration step: with `lock_timeout` it fails in seconds and now prints the blocker; terminate, re-run.
5. Verify: `robots.txt` → `Disallow: /`; `/sitemap.xml` static entries without `<lastmod>`, no summary-less filings; `/health/detailed`; `hot_filings?force_refresh=true` still 200; 31 bursts to `/insiders` → 429 with `Retry-After`.
Risks: ruff red (pin in same PR); live blocker (fast fail, diagnosable); e2e apt flake (mitigated `ci.yml:229-249`); flag drift only on the hand-run fallback.

**5b. Durable fix (P0)**

| # | Change | Where | Effort |
|---|---|---|---|
| 1 | `timeout-minutes: 30` on `deploy-backend`; `timeout 900` on the migration run | `ci.yml:287`, `:329` | 0.25 h |
| 2 | `export PGOPTIONS="-c lock_timeout=10s -c statement_timeout=120s -c idle_in_transaction_session_timeout=30s"` before the loop. No `--single-transaction` (it would forbid a future `CREATE INDEX CONCURRENTLY`, which cannot run inside a transaction block) | `ci.yml:366-369` | 0.5 h |
| 3 | Retry on SQLSTATE 55P03: 5 attempts, 15 s apart | same | 0.5 h |
| 4 | On final failure dump `pg_stat_activity` + `pg_locks` for the relation (no secrets) | same | 0.5 h |
| 5 | Ledger `schema_migrations(filename pk, sha256, applied_at)`; skip recorded (filename, sha256); files stay byte-identical (edited file → new hash → re-apply once). Seed: apply all once under lock_timeout+retry, or pre-insert 32 rows. Supersede rule 3's "re-apply ALL" wording with a lesson/ADR | `ci.yml` + `backend/migrations/README.md` or `docs/adr/0007` | 3 h |
| 6 | New-migration pattern: `DO $$ IF NOT EXISTS (SELECT 1 FROM information_schema.columns …) THEN ALTER … END IF $$`; `CREATE INDEX CONCURRENTLY IF NOT EXISTS` on existing tables | enforced by §5c | — |
| 7 | Cloud SQL flag `idle_in_transaction_session_timeout=600000` on `earningsnerd-db` (check restart) | GCP | 0.5 h |
| 8 | Optional `migrator` role with `ALTER ROLE … SET lock_timeout='10s'` | GCP + secret | 1 h |

**5c. CI gates (rule 12, P1)**
1. `backend/tests/unit/test_migration_lock_safety.py` (~2 h), modelled on `test_naive_utcnow_allowlist.py`: parse `.github/workflows/ci.yml` (`Path(__file__).resolve().parents[3] / ".github/workflows/ci.yml"`) and assert `deploy-backend` has `timeout-minutes` and the migration `run:` contains `lock_timeout` + `statement_timeout`; for every `backend/migrations/*.sql` not in a frozen `LEGACY_UNGUARDED` allowlist (the 17 files above, by name) assert no top-level `ALTER TABLE` outside a `DO $$ … IF NOT EXISTS (information_schema|pg_catalog …)` block, `CONCURRENTLY` on any `CREATE INDEX` for a table not created in the same file, and `^\d{8}_[a-z0-9_]+\.sql$` names; allowlist can only shrink.
2. Toolchain pin (~0.5 h): `backend/requirements-dev.txt` with `ruff==0.15.8` + pinned bandit; `ci.yml:27` installs from it; CLAUDE.md gate uses the same file; test asserts no bare `pip install ruff|bandit` in ci.yml. Separate autofix/bump PR later.
3. Doc sync (~1 h): `DEPLOYMENT.md` items in §4.4, `CLAUDE.md:120` (7 jobs; rule 3 wording), update `lessons/arch-migrations-no-alembic.md`, add `lessons/ops-migrations-need-lock-timeout.md`.

**5d. Other**

| Item | Sev | Effort |
|---|---|---|
| Nasdaq-100 source → FMP or other keyless source; failure notification | P1 | 2 h |
| Remove `ops.yml` stale-branch push trigger (or delete branch); consider one shared `prod-db` concurrency group | P2 | 0.25 h |
| Pin `cloud-sql-proxy` sha256 in `ci.yml` and `ops.yml` | P2 | 0.25 h |
| Verify the 07-16 incident window; write lesson | P0 (verification) | 0.5 h |

### 6. Evidence index
- `get_workflow_job(87710378965)`: `started_at 2026-07-16T18:38:42Z`, `completed_at 2026-07-17T00:38:53Z`, step 7 `cancelled` 18:40:23→00:38:50, steps 8–11 `skipped`. `list_workflow_runs(ci.yml, main, push)`: #634 `cancelled`; #633 run 29285536512 `success` 07-13 21:19Z.
- Job log tail: `== applying 20260122_add_markdown_cache_columns.sql ==` → `Accepted connection from 127.0.0.1:58220` (18:40:39) → SIGTERM (00:38:50) → `psql:…:7: server closed the connection unexpectedly`.
- `ci.yml`: `:7` workflow_dispatch; `:27` unpinned lint; `:213` e2e timeout; `:287-296` deploy job (`:290` if, `:291-293` concurrency); `:303-312` change detection; `:329-370` migration step (`:349-351` proxy download, `:361-364` pg_isready, `:366-369` loop, `:368` psql); `:371-393` deploy; `:405` 7 jobs; `:417-428` health.
- Migrations: `20260122…sql:4-7`; guard example `20260705_summary_filing_id_unique.sql`; `git diff 4994360..e8ea339 -- backend/migrations` empty; step introduced `f66ace1` (07-07); 40 backend pushes since.
- App surfaces: `app/database.py:22-48,76-101`; `summary_pipeline.py:137,196,214,897,924,1040`; `routers/filings.py:422`; `routers/summaries.py:163,355,444`; `models/__init__.py:306-319`; `rate_limiter.py:75-84`.
- Drift: `git diff 4994360..e8ea339 -- backend/` (8 files); `frontend/lib/serverApi.ts:226-236`; routes at 4994360 `companies.py:436`, `filings.py:170,390`, `summaries.py:418`.
- Index refresh: runs 30694838077, 33511750077 both `failure`, identical error; script `:93-122`; live Wikipedia check 2026-09-04; committed list `db47315`.
- Other workflows: data-quality 8/8 success (latest 33430093824, 08-31); ops 17 runs (latest 28911656754, 07-08); `ops.yml:16,47-49,212-214`; stale branch exists on origin.
- Docs: `docs/DEPLOYMENT.md:14,28-29,32,65,359-365`; `CLAUDE.md:120-121`.
