# Implementation briefs — September 2026 remediation

**Status:** prepared 2026-09-04 by the chief-engineer session. Founder reviewed the one-pager and §2 on
2026-09-04 and answered "go with your recommendations" — every bold recommendation in §2 is now the
decision. Wave 1 dispatched the same day (see §6). **Source of truth for scope:** PR #653 (`docs/ENGINEERING_AUDIT_2026-09.md`,
`docs/audit-2026-09/01–06`, `tasks/todo.md` on that branch). This file adds what the audit does not:
code-verified corrections, sequencing, and one self-contained brief per workstream so an agent can
start without re-reading the appendices.

**Every brief inherits:** `CLAUDE.md` (all 12 rules), `lessons/README.md` (scan; open what applies),
`.claude/agents/README.md` → *Stack truth (2026-09)* (the per-agent files are stale on stack),
`lessons/ops-verify-plan-gaps-against-code.md` (re-read the cited lines before writing code — three
audit items below turned out to be already done or wrong). Plan in `tasks/todo.md`, small PRs, full
local gate before every push, rule-12 gate in the same PR as any "never again" rule. Agents are
dispatched from `.claude/agents/` (Sprint Coordinator hands off; owner named per brief).

---

## 0. Inputs

- **The one-pager** (`claude.ai/code/artifact/cb628415-…`, received as screenshots) is a rendered
  version of `docs/ENGINEERING_AUDIT_2026-09.md`: same three priorities, same nine founder decisions,
  same verification table. It repeats the "6-Ks … no summary path" claim corrected in C1 below.
  Nothing in it changes §3 ordering.

## 1. Corrections to the audit (verified in code this session — do not implement the wrong version)

| # | Audit says | Code says | Effect on plan |
|---|---|---|---|
| C1 | "6-Ks have no summary path" (synthesis §1.5, §4.3; app. 03; Phase 3 "stub containment") | Path exists: `backend/prompts/6k-analyst-agent.md`, `6k-structured-agent.md`; `summary_pipeline.py:358-489` (`get_sixk_text` EX-99 grounding) behind `ENABLE_FPI_FILINGS`, which prod sets (`ci.yml` service env). App. 06 #22 is right. | Phase 3 item becomes: 6-K classifier (earnings vs governance vs press release) + 6-K golden-set entries. Do **not** build a 6-K path or hide 6-Ks. |
| C2 | `ops.yml` stale branch "exists on origin" (app. 01) | `git ls-remote` today: gone. App. 05/06 right. | Fix = remove the `on.push` trigger from `ops.yml`, not delete a branch. |
| C3 | Rule-8 `os.getenv` sites: `main.py:21,26,29` (05) *or* `config.py:511,514` (03) | Both. Plus sanctioned `database.py`, `redis_service.py`, `edgar/config.py`. | Gate allow-list = those five files; fix `main.py` to read `settings`. |
| C4 | "Fire `signup_completed` on verify" (Phase 1) | Backend already emits it (`app/services/posthog_client.py:46`, tested in `test_beta_funnel_events.py`). Frontend `lib/analytics.ts:50-57` is dead. | Delete the dead frontend helper; no new event. |
| C5 | `/pricing` "useSearchParams forces CSR bailout" | Page is `'use client'` and **already Suspense-wrapped** (`page.tsx:458-464`) — the whole body is inside the boundary, so server HTML is only the spinner. | Fix stands (move the hook into a tiny child or read post-hydration); the diagnosis wording is off. |
| C6 | Flags on in prod "via ci.yml" / "by hand" | `ci.yml` sets only `ENABLE_FPI_FILINGS`, `STREAM_SECTION_REVEAL`, `REGISTRATION_MODE`, `COOKIE_DOMAIN`, `TRUSTED_PROXY_HOPS`, pools, model. `AI_*_GATE`, `AI_EVIDENCE_SNAP`, `NOTABLE_FILINGS_ENABLED`, `USE_STATEMENT_FINANCIALS` are **not** in the deploy; any prod value is hand-set and invisible to the repo. | Founder confirms via `ops.yml describe-service` before any flag work (add `REGISTRATION_MODE`/`USE_STATEMENT_FINANCIALS` to its allow set first). |
| C7 | PR #653 gate "17 legacy unguarded ALTERs" | Set verified 1:1. But the gate exempts *any* `DO $$` body (guarded or not), is line-anchored, ignores quoted identifiers, and skips `CREATE INDEX` (SHARE lock before existence check). `pg_stat_activity` dump filters `xact_start IS NOT NULL`, which hides other roles' sessions without `pg_read_all_stats`. | Brief WS-1. |

## 2. Founder decisions that block dispatch (recommendation in bold)

| # | Decision | Recommendation | Unblocks |
|---|---|---|---|
| D1 | Migration design: DO-guard only vs `schema_migrations` ledger | **Ledger** (filename, sha256, applied_at; skip recorded; ADR-0007 supersedes rule-3 wording). Guard-only leaves ~43 `CREATE INDEX` SHARE acquisitions per deploy and a 120 s `UPDATE financial_fact` re-run. | WS-2 |
| D2 | Universe refresh source | **FMP key if the plan includes constituents**, else S&P-only from Wikipedia + alert (Nasdaq-100 keyless source is permanently gone). | WS-4 |
| D3 | Dark surfaces for beta (Analysis, Notable, Calendar+AV licence, Insiders) | **Analysis on** (Pro flagship, needs companyfacts warm); **Notable after one week of job output**; **Calendar off until AV licence**; Insiders off. | WS-9 |
| D4 | Spend: universe pregeneration (~$25–50), v1→v2 drain (~$0.05/filing), golden-set runs (~$10) | **Approve all three**; run pregeneration only after WS-7 bank fixes + off-peak window. | WS-7, WS-6 |
| D5 | Arm `AI_EVIDENCE_SNAP` after first readout; then figure-trace / forward-quote | **Arm evidence-snap first** (+0.17 citation fidelity measured); keep forward-quote advisory (0 fabrications in 8/8 near-miss). | WS-6 |
| D6 | Dependabot: merge #635 #636 #639 #640 #641 #642; close #629 #570; split #651; hand-bump Next then recreate #652 | **Yes to all**; order in WS-3. | WS-3 |
| D7 | Dead-integration teardown (trending/FMP/hot_filings/Twitter) | **Approve** — it also moots two security quick-wins (C2, C5 in app. 05). | WS-8 |
| D8 | GCP/Vercel console: PITR + deletion protection; uptime + job-failure alerts; Sentry source-map env vars; Node 22 project setting; `describe-service` flag check | Founder-only; **do in parallel now**, no code dependency. | WS-1, WS-5 |

## 3. Sequencing

```
PR #653 merge (founder pre-flight → deploy-backend green → post-deploy checks)
 ├─ WS-1 gate hardening (follow-up to #653)          ── DevOps
 ├─ WS-3 Dependabot + Next 16.3.4 + Node 22          ── DevOps + Frontend        ← D6, D8
 ├─ WS-4 universe refresh + age gate                 ── Backend                  ← D2
 ├─ WS-5 frontend observability + public-page fixes  ── Frontend                 ← D8 (Sentry env)
 ├─ WS-8 quick-win gates + teardown                  ── Backend + Security       ← D7
 └─ WS-2 migration ledger + ADR + CI Postgres gate   ── Database                 ← D1
      └─ WS-7 data integrity (SIC, statement default, job_runs, amendments) ── Backend
           └─ WS-6 AI fidelity (parity → re-pin → dims → retry/fallback → guards) ── AI  ← D4, D5
                └─ pregeneration run (founder spend)                              ← D4
 WS-9 dark-surface flips                                                          ← D3, C6
 WS-10 docs/lessons hygiene                          ── Knowledge Curator (rolling)
```

Hard rules across workstreams: **eval re-pin** after any of — `USE_STATEMENT_FINANCIALS` in eval env,
G5 JPM facts restored, streaming exercised in the runner, new eval dimension, `--runs` change,
edgartools bump, Gemini-chain deletion, prompt reorder. Parity fixes land first, then re-pin, then
quality changes are measured against the honest bar. Any new migration file must pass the
`test_migration_lock_safety.py` gate (DO-guard, filename convention).

---

## 4. Workstream briefs

### WS-1 · Deploy-gate hardening (follow-up to PR #653) — owner: DevOps Automator (+ Database Specialist review)

**Goal.** Close the gaps found while verifying #653 without touching the catch-up deploy.
**Evidence.** `backend/tests/unit/test_migration_lock_safety.py:75-92` (`_strip_sql` drops every
`$tag$…$tag$` body); `:101-140` (line-anchored ALTER regex, `[\w.]+` excludes quotes);
`.github/workflows/ci.yml` `apply_with_retry` (retries any psql error; dump predicate
`xact_start IS NOT NULL`); `backend/migrations/20260706_demote_null_fiscal_period_duplicates.sql`
(correlated `UPDATE financial_fact` every deploy); `ops.yml:47-49` (push trigger on a branch that
no longer exists), `ops.yml:212-214` (same psql pattern, no lock_timeout); `cloud-sql-proxy`
downloaded without checksum in both workflows.
**Scope.**
1. Gate: a DO body containing `ALTER TABLE` must also contain `IF NOT EXISTS` or a catalog check
   (`information_schema|pg_catalog|pg_constraint|pg_indexes`); split on `;` instead of line anchors;
   accept quoted identifiers; compare on unqualified lowercase names. Extend to top-level
   `CREATE [UNIQUE] INDEX` on tables not created in-file with a second frozen shrink-only legacy list
   (~43 today) — or state the exclusion in the docstring if D1 = ledger makes it moot.
2. Dump: drop the `xact_start IS NOT NULL` predicate; add a `pg_locks` ⨝ `pg_class` dump for the
   relation; retry only on `55P03`/`57014` in stderr.
3. `ops.yml`: remove the stale push trigger; apply the same `PGOPTIONS`; share a `prod-db`
   concurrency group with `deploy-backend`; pin `cloud-sql-proxy` sha256 in both files.
4. Comment the 120 s risk on `20260706…` (ledger will skip it).
**Out.** The ledger itself (WS-2). Any migration rewrite.
**Gate.** `pytest tests/unit/test_migration_lock_safety.py` with new negative fixtures (unguarded DO,
same-line ALTER, quoted ident) failing before / passing after; `yaml.safe_load` both workflows;
full backend gate. **Size** ~0.5 day.

### WS-2 · Migration ledger + ADR-0007 + CI Postgres gate — owner: Database Specialist — blocked on D1

**Goal.** Applied files are skipped; converged DDL takes no lock; rule 3 wording is superseded.
**Evidence.** `ci.yml` migration loop (`for f in backend/migrations/*.sql`); `lessons/arch-migrations-no-alembic.md`
(equates idempotent with safe); `docs/adr/README.md` format; app. 01 §5b.5 design; app. 03 §D
(CI has no Postgres — SQLite only).
**Scope.** `schema_migrations(filename PK, sha256, applied_at)`; the deploy step applies a file only
when (filename, sha256) is unrecorded, records after success; seed by one full run under the #653
lock_timeout/retry (or pre-insert 32 rows — founder choice at seed time); an edited file → new hash
→ re-applies once (document). ADR-0007 supersedes rule 3's "re-applied on every deploy"; update
`CLAUDE.md` rule 3, `lessons/arch-migrations-no-alembic.md`, `docs/DEPLOYMENT.md`. Add a CI job with a
`postgres:15` service that applies all migrations **twice** (rule-12 gate for idempotency and for
the ledger skip). Cloud SQL flag `idle_in_transaction_session_timeout` (founder, D8) as backstop.
**Out.** Rewriting the 17 legacy files (ledger makes them one-shot). **Gate.** CI double-apply job green;
`test_migration_lock_safety.py` updated to the new step name; full backend gate. **Size** ~1 day.

### WS-3 · Dependency currency — owner: DevOps Automator + Frontend Developer — blocked on D6, D8 (Vercel Node)

**Order matters:**
1. After #653 merges: merge #635 #636 #639 #640 #641 #642; close #629 (`@dependabot ignore this major version`)
   + add `typescript` to `.github/dependabot.yml` semver-major ignore; close #570.
2. Split #651: (a) pandas 3.0.5 (3.0.4 is yanked — in the prod image today) + fastapi/lxml/posthog etc.
   → merge; (b) edgartools 5.40.1→5.51.0 **alone** through the eval gate (RUNBOOK; confirm
   `DEEPSEEK_API_KEY` is actually available on non-Dependabot PRs — `ci.yml:150-164` self-skips silently).
3. Next by hand to ≥16.3.4 (9 advisories on 16.2.10 incl. middleware bypass — `frontend/middleware.ts` is
   the UX gate): fix `components/GlobalErrorBoundary.tsx:52` (`window.location.href = '/'` → new
   `@next/next/no-location-assign-relative-destination` rule; bundle the WS-5 Sentry fix in the same touch)
   and `app/globals.css:408-411` (`::highlight(copilot-citation)` rejected by the 16.3 build — wrap in
   `@supports selector(::highlight(x))` or move to a JS-registered style); then `@dependabot recreate` #652.
   **#652 as-is would break the Vercel production build.**
4. Node 20 → 22: `frontend/.nvmrc`, `package.json engines`, `ci.yml:51,91,219`, Vercel project setting
   (founder) — one PR, lockstep.
5. Advisory-then-blocking audit steps: `pip-audit -r backend/requirements.txt`, `npm audit --omit=dev --audit-level=high`.
**Gate.** Frontend full gate + Playwright; backend full gate; eval gate for (2b). **Size** ~1 day + waits.

### WS-4 · Universe refresh + age gate — owner: Backend Developer — blocked on D2

**Evidence.** `.github/workflows/refresh-index-membership.yml` (monthly, `--source wikipedia`, opens a PR
with `GITHUB_TOKEN` so CI never runs on it); `backend/scripts/refresh_index_membership.py:47-48` (URLs),
`:99-124` (table heuristic), `:167` (`FMP_API_KEY`), `:210` (`--source auto|fmp|wikipedia`); committed
list `backend/app/data/index_membership.json` (515, 2026-07-07); `test_index_membership_service.py:60`
checks shape, not age. Runs 30694838077 / 33511750077 failed: Wikipedia Nasdaq-100 has no constituents
table any more (verified live 2026-09-04) — **do not "fix table selection"** (app. 03's proposal cannot work).
**Scope.** Source per D2 (FMP with secret, or S&P-only + Nasdaq-100 from another keyless source behind the
existing ≥500/unique/mega-cap sanity floor); workflow failure notification; unit test that fails when
the committed list is >100 days old (rule 12); seed `Company` rows for the 237 universe members without
one is WS-7. **Gate.** Workflow dry-run via `workflow_dispatch`; backend gate. **Size** ~0.5 day.

### WS-5 · Frontend observability + public-page fixes — owner: Frontend Developer (+ Accessibility Champion review) — Sentry env blocked on D8

**Read `frontend/DESIGN_SYSTEM.md` first; both-theme preview before done.**
**Evidence / scope (each its own small PR):**
1. `components/GlobalErrorBoundary.tsx:38-43` reads `window.Sentry` (never set → silent no-op; UI copy at
   `:67` claims it reported). Import `@sentry/nextjs`, `Sentry.captureException(error, { extra })`.
   Same file `:52` (WS-3 lint rule). `next.config.js:89-93` `withSentryConfig(..., { silent: true })`
   with no org/project/token → drop `silent`, add `widenClientFileUpload`, founder sets
   `SENTRY_AUTH_TOKEN/ORG/PROJECT` in Vercel. `instrumentation-client.ts:12` console levels → drop `"log"`.
2. `app/pricing/page.tsx:42` — move `useSearchParams` into a tiny Suspense child (or post-hydration
   read like `app/filing/[id]/page-client.tsx:47-58`) so H1/plans/prices/FAQ server-render; add
   Product/Offer JSON-LD; remove duplicate `<h2>Pricing</h2>` at `:241`. Verify with `curl` of `next start`.
3. `features/summaries/components/SummaryRisks.tsx:40` `title={risk.title || 'Risk Factor'}` → derive
   from the first clause of `summary` when absent, or drop the `h4`. Backend: `app/services/ai/normalize.py:119,152-153`
   emits `title` only when the model does; **any prompt change goes through the eval gate** (hand to AI Engineer).
4. Company-name casing (`app/company/[ticker]/page.tsx:28-34`, `page-client.tsx:399`;
   `app/filing/[id]/page.tsx:34,70,76`, `page-client.tsx:285-310`; `features/filings/components/TickerFilingsView.tsx:69`):
   one `formatCompanyName` helper with an exceptions list (INC., CORP, LLC, ticker-like tokens), unit-tested,
   used in title/description/H1/JSON-LD.
5. `app/sitemap.ts:45-53` — `cache: 'no-store'` and rely on `export const revalidate = 3600`; **only after
   #653's backend deploy shrinks the upstream**; vitest asserting entries are not from a cached body; fix
   `docs/SEO_AUDIT.md:63`; add `/terms`.
6. `app/contact/page.tsx:6` entity (`We&apos;re` in a JS string); canonical for `/contact`; `noindex`
   + canonical for `/login`, `/register`.
7. Mobile section jump-nav (`SummaryBlocks.tsx:104` TOC is `hidden lg:block`); live region for streaming
   progress (`StreamingSummaryDisplay.tsx:270-300`); skip-to-content link in `components/SiteChrome.tsx`.
8. Delete dead `lib/analytics.ts:50-57` `signupCompleted` (C4); delete `components/SentryTestButton.tsx`
   and its allowlist entry; `posthog-provider.tsx:60-75` pre-consent `persistence: 'memory'` (founder
   strategy call — propose, don't decide).
9. Rule-12 gate: ESLint `no-restricted-syntax` for raw `fetch(` with the 5 sanctioned sites allow-listed
   (`app/sitemap.ts`, `lib/serverApi.ts` ×2, `features/summaries/api/summaries-api.ts`, `features/filings/api/copilot-api.ts`,
   `features/analysis/api/analysis-api.ts`).
**Gate.** `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run && npm run build`;
Playwright; both-theme preview. **Size** ~2 days.

### WS-6 · Summary fidelity: parity → re-pin → measure → arm → resilience — owner: AI Engineer — blocked on D4, D5 for the arming/spend steps

**Read `backend/evals/RUNBOOK.md` and `lessons/ops-eval-gate-for-ai-changes.md` first.**
**Evidence.** `backend/evals/baseline_scores.json` (2026-07-13, 26×3, judge off; precision/coverage/recall
1.0 with 0 variance; citation_fidelity 0.689 WARN); `ci.yml:173-195` (`--runs 1`, no `--judge`,
`continue-on-error`); `config.py:431` `USE_STATEMENT_FINANCIALS=False` (prod on by hand; eval env off);
`evals/runner.py:161` no `stream_cb` (prod streams); RUNBOOK:61-72 G5 dormant;
`openai_service.py:80-92` `_fallback_models` = `[AI_DEFAULT_MODEL, "gemini-2.5-pro", "gemini-2.5-flash"]`
sent to DeepSeek → 404s; `:455` `max_retries = 1`; `section_recovery.py:143` reuses the chain;
`tests/unit/test_openai_service_retry.py:23` injects fake names; no `usage`/`response.model` logging;
`summary_pipeline.py:782-848` five audit counters INFO-only; `copilot_tools.py:210-231,264-277`
`_query_fact` company-scoped/`is_latest`; `copilot_service.py` no currency directive;
`evals/copilot_golden_set.json` 2 entries `verified:false`; `openai_service.py:242-255,391`
`previous_filings_context` dead (only caller `summary_pipeline.py:632` passes `None`);
`section_recovery.py:81-106,133-137` recovers from raw HTML / `excerpt[:6000]`; `openai_service.py:175`
`filing_text[:15000]` raw HTML when enrichment times out (`summary_pipeline.py:143` 18 s).
**Scope, in order (each step re-pins if scores move):**
1. Parity: `USE_STATEMENT_FINANCIALS` in the eval env (and graduate the code default with WS-7);
   restore G5 JPM facts; pass a `stream_cb` in the runner and pin streaming ≡ non-streaming;
   `--runs 2` or granularity-aware tolerance for the single-veto flake; fix `pin_baseline.py` dropping
   `note`. Re-pin.
2. Measure: add `mean_untraceable_dollar_figures` as a WARN dimension; scheduled judged run workflow
   (8 filings, `--runs 3`, judge on, weekly readout to the data-quality email); roll the five counters
   from persisted `raw_summary` audits into `data_quality_service.build_report`.
3. Resilience: delete the Gemini chain + comments; bounded backoff on the primary; env
   `AI_FALLBACK_BASE_URL`/`AI_FALLBACK_MODEL` (Settings, `docs/CONFIGURATION.md`); log `usage` and
   `response.model` per summary and expose on `/metrics`; rewrite the retry test with real names;
   hard `partial` reason when neither excerpt nor XBRL is present + a test for the `[:15000]` path.
4. Hygiene: delete `previous_filings` param + AST pin (rule 2); section-recovery context from labelled
   excerpt sections (~30k cap).
5. Copilot: currency directive (never bare `$` for CNY/TWD/EUR issuers); scope `_query_fact` to the
   viewed filing's period (bind to accession); grow the golden set to ~5 verified; run `evals.copilot_runner`.
6. After D5: arm `AI_EVIDENCE_SNAP` via the deploy env (`ci.yml` service `--update-env-vars`, so it is
   visible in-repo — C6); stale-refresh of pre-gate rows with the v1→v2 drain (D4, off-peak).
**Out.** Prompt-prose tuning (`lessons/arch-stop-tuning-prose-know-the-floor.md`). **Gate.** eval gate +
re-pin in the same PR; backend gate; `test_summary_stream_contract.py` is locked (rule 6). **Size** ~5 days.

### WS-7 · Data integrity + coverage reporting — owner: Backend Developer (+ Database Specialist) — pregeneration blocked on D4

**Evidence.** `scripts/backfill_facts.py --backfill-company-sic` exists; prod `Company.sic` NULL everywhere
(bank revenue-tag selection depends on it); `config.py:431` default; `internal.py:250` backfill-filing-history
(C, MS, WFC, GS outstanding); `facts_service.py:107-111` 10-Q per-filing `fiscal_period=None`
(`_classify_duration:1027` reusable); `_parse_company_facts` never fills `total_liabilities`/`cash_and_equivalents`;
`xbrl_service.py:566-631` never reads persisted `Filing.xbrl_data` (PS5); `edgar/compat.py:275 include_amended=False`,
`filing_history_service.py:57-68`, `filing_scan_service.py:33` (amendments never listed);
`data_quality_service.py:153-163` report has four sections, none for coverage/stub ratio/universe age/job health;
7 Cloud Run jobs with no heartbeat; `precompute_service.py:62-68` needs `ENABLE_FPI_FILINGS` in the **job**
env (`ci.yml` job `--update-env-vars` lacks it → BABA pregenerate no-ops); `pregenerate_examples.py:37-46`
8 tickers, 10-K only.
**Scope.** (1) SIC backfill run (founder triggers job) + graduate `USE_STATEMENT_FINANCIALS` default to
True in code; (2) `job_runs` heartbeat table (new migration → must pass the lock-safety gate) written by
every job script; weekly report gains coverage %, stub ratio, universe-list age, per-job last success;
(3) `fiscal_period` derivation for 10-Q per-filing facts + unit/decimals assertions; badge `reconciled=False`
on every surface; (4) amendments: list/ingest `/A`, mark superseded, prefer in Change Report; (5) PS5 read
persisted `xbrl_data` first; fill `total_liabilities`/`cash_and_equivalents`; (6) add `ENABLE_FPI_FILINGS`
and `10-Q` to the weekly pregenerate; seed `Company` rows for the 237 universe members; (7) after D4 and
steps 1–2: universe-wide latest 10-K + 10-Q via `precompute` in batches, off-peak.
**Gate.** Backend gate; new migration passes `test_migration_lock_safety.py`; eval re-pin if (1) moves
scores (coordinate with WS-6 step 1 — one re-pin). **Size** ~3 days + job runs.

### WS-8 · Security quick wins, rule gates, dead-integration teardown — owner: Backend Developer + Security Auditor — teardown blocked on D7

**Evidence.** `routers/hot_filings.py:86` `!=` token compare (vs `hmac.compare_digest` at `internal.py:35`);
`routers/trending.py:49-79` `refresh-prices` unauthenticated, unlimited, fans out to FMP;
`main.py:21,26,29` + `config.py:511,514` `os.getenv` (C3); `facts_service.py:449-475` raw `httpx.Client`
to `data.sec.gov` outside `sec_rate_limiter` (called from the `backfill-facts` job via `:628`), twin at
`xbrl_service.py:910-932`; `models/__init__.py:351-376` `before_insert` fabricates `…/edgar/data/0/{acc}/`
when `company` is not loaded (`:359-362`), listeners untested; three URL builders (`client.py:581-583`,
`sec_api.py:101-105`, `models/__init__.py:362`); `test_dead_integrations_allowlist.py:19-29`;
`hot_filings.py:11-12`, `trending_service.py:12-13`, routers mounted `main.py:353,355`; frontend consumers
`features/companies/components/TrendingTickers.tsx`, `companies-api.ts:82-87`, `queryKeys.ts:33`,
`serverApi.ts:169`; `integrations/fmp.py`; `TWITTER_BEARER_TOKEN`, `HOT_FILINGS_*`, `FMP_*` settings;
`auth.py:428,826` plaintext e-mail in logs.
**Scope.** (a) If D7 approved: teardown PR removes trending + hot_filings routers/services/tests, FMP
integration and settings, Twitter token, frontend consumers; shrink the dead-integrations allow-list to
empty; update `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `DEPLOYMENT.md` secret mounts. This moots
the compare-digest and refresh-prices fixes. If not approved: `compare_digest` + `RateLimiter` on
`refresh-prices` like `insiders.py:20,40`. (b) Rule-8: Sentry init from `settings` in `main.py`; AST
allow-list test for `os.getenv|os.environ` (five sanctioned files). (c) Rule-5: route
`_fetch_companyfacts_sync` and the `xbrl_service` twin through `sec_rate_limiter.execute`; AST test —
only `services/edgar/**` and `integrations/sec_api.py` may reference `sec.gov`. (d) Rule-10: one URL
builder; regex-validate `sec_url`/`document_url` at the Filing boundary; raise instead of fabricating
`cik="0"`; unit tests for both listeners. (e) Hash or drop e-mails in the two log lines; gate: no
authenticated side-effecting GET (AST over routers).
**Gate.** Backend gate; frontend gate for the teardown; `test_dead_integrations_allowlist.py` shrinks in
the same PR. **Size** ~2 days.

### WS-9 · Dark-surface flips — owner: Backend Developer + Frontend Developer — blocked on D3 and C6 confirmation

Notable filings: create Cloud Run job + Scheduler (founder, `docs/DEPLOYMENT.md:371-410`), seed `--days 7`,
one week of founder review, then `NOTABLE_FILINGS_ENABLED=true` **in `ci.yml`** (visible in repo).
Analysis: confirm prod value of `NEXT_PUBLIC_ENABLE_ANALYSIS`; warm companyfacts; flip in `vercel.json`.
Calendar: only after the Alpha Vantage licence decision (personal-use tier is live on a public surface today —
`config.py:290-293` vs live `/api/calendar` returning `eps_estimate`). Archive `tasks/fpi-support-roadmap.md`
with a status block (Phases 0–5 shipped; residual = 6-K classifier + post-flip `backfill_facts`).

### WS-10 · Docs and lessons hygiene (rolling) — owner: Knowledge Curator

`docs/SEO_AUDIT.md:139` (6 jobs) and `:63` (S4 not fixed in prod); `backend/evals/RUNBOOK.md:428` FPI
status; `docs/DATA_COMPLIANCE.md` processor table (DeepSeek, not Gemini); Gemini-era comments in
`openai_service.py:77-100`; `docs/CONFIGURATION.md` (47 undocumented settings, retired
`NEXT_PUBLIC_ENABLE_SECTION_TABS`); `tasks/homepage-sections-review-findings.md` → archive; dangling
"DEPLOYMENT.md section 12" pointer; `lessons/arch-migrations-no-alembic.md` after D1; pre-existing
CLAUDE.md violations to queue: `deploy-vercel.sh` executable at repo root, `scripts/test_resend_simple.py`
outside the test roots. Each doc fix lands in the PR that changes the code it describes (CLAUDE.md
"Docs vs code").

---

## 5. Definition of done for the programme

- PR #653 merged; `deploy-backend` green; API `robots.txt` → `Disallow: /`; `/health/detailed` healthy;
  31-burst to `/api/companies/AAPL/insiders` → 429 with `Retry-After`.
- Every "never again" from the audit has a machine gate (WS-1, WS-4, WS-5 §9, WS-8 b–e, WS-2 CI job).
- Eval baseline re-pinned on the honest bar (parity + streaming + statement financials) and a weekly
  judged readout exists before any guard is armed.
- Weekly report shows coverage, stub ratio, universe age and job health; something pages on API/job failure.
- Agent definitions refreshed to the current stack with a gate (queued as a separate task).

## 6. Dispatch log

**Wave 1 — 2026-09-04** (no deploy dependency; each on its own branch and draft PR):

| Branch | Brief | Base | Owner agent |
|---|---|---|---|
| `claude/ws1-gate-hardening` | WS-1 | PR #653 branch (edits its gate test) | DevOps Automator |
| `claude/ws2-migration-ledger` | WS-2 | PR #653 branch (edits its migration step) | Database Specialist |
| `claude/ws4-universe-refresh` | WS-4 | `main` + ported ruff pin | Backend Developer |
| `claude/ws8a-dead-integration-teardown` | WS-8 (a) | `main` + ported ruff pin | Backend Developer |
| `claude/ws8b-rule-gates` | WS-8 (b)–(e) | `main` + ported ruff pin | Backend Developer + Security Auditor |
| `claude/ws5a-observability-public-pages` | WS-5 items 1, 2, 6, 8, 9 | `main` + ported ruff pin | Frontend Developer |
| `claude/ws5b-reading-surface` | WS-5 items 3 (frontend half), 4, 7 | `main` + ported ruff pin | Frontend Developer |

Held for wave 2 (after #653 deploys and the eval key is available in a session): WS-3 Next/Node bumps
(needs WS-5a's two fixes first) and Dependabot merges; WS-5 item 5 (sitemap fetch); WS-6; WS-7; WS-9.
Founder console actions (D8) run in parallel and are not tracked here.
