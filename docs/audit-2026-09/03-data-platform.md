# EarningsNerd — Data Platform Audit (read-only)

> Appendix 03 of `docs/ENGINEERING_AUDIT_2026-09.md`. Workstream report reproduced as written; hypotheses are labelled by the author.

Auditor: data-platform lens · Repo: `/home/user/EarningsNerd` @ `e8ea339` (main, 2026-07-16) · Audit date: 2026-09-04
Method: code + git read-only; GitHub Actions run history/logs via API; 13 read-only GETs against `api.earningsnerd.io`
(sitemap, recent filings, health, calendar, 8 summary reads, /metrics) + 1 GET to `www.earningsnerd.io/sitemap.xml`.
No sec.gov traffic. Anything not verified in code/logs is labelled **[hypothesis]**.

---

## Headline findings

> **Lead correction (PR #653 review, 2026-09-04):** a 6-K summary path DOES exist — `backend/prompts/6k-analyst-agent.md`, `6k-structured-agent.md` and `summary_pipeline.py:358-489` (`get_sixk_text` EX-99 grounding) behind `ENABLE_FPI_FILINGS`, which prod sets. Read "no summary path exists for 6-K" below as "no 6-K classifier and no 6-K golden-set coverage"; the coverage numbers stand.


1. **Production has been frozen on the 2026-07-13 image (`4994360`) for 7 weeks, and the cause is a data-platform defect.**
   CI run `29524625738` (push of `e8ea339`, 07-16): all test jobs green; `deploy-backend` step "Apply database migrations"
   started 18:40:23Z and was **cancelled at 00:38:50Z next day — exactly GitHub's 6-hour default job timeout**
   (`deploy-backend` has no `timeout-minutes`; only `e2e-tests` does — `.github/workflows/ci.yml:213`). Job log tail:
   `== applying 20260122_add_markdown_cache_columns.sql ==` … 6 h later … `psql:…20260122_add_markdown_cache_columns.sql:7:
   server closed the connection unexpectedly`. That file (`backend/migrations/20260122_add_markdown_cache_columns.sql:4-7`) is
   `ALTER TABLE filing_content_cache ADD COLUMN IF NOT EXISTS …` — a converged no-op that **still takes an ACCESS EXCLUSIVE lock**
   on a hot table, re-applied on **every** deploy (`ci.yml:366-369`), with no `lock_timeout`/`statement_timeout`. It queued
   behind a long-lived lock holder and never acquired. **[hypothesis]** the holder was an app transaction pinned open (a session
   held across an SSE generation — `routers/summaries.py` takes `db: Session = Depends(get_db)` for the streaming endpoint and
   `database.py:46-51` closes it only at dependency teardown — or a leaked idle-in-transaction pooled connection).
   Corollary **[hypothesis]**: while the ALTER waited, every new query touching `filing_content_cache` (e.g.
   `GET /api/summaries/filing/{id}` joinedloads it — `routers/summaries.py:442-447`) queued behind the pending ACCESS EXCLUSIVE,
   i.e. a multi-hour partial outage on 07-16 with no record. "Deploy Cloud Run service", both job-image updates and
   "Verify health" were skipped. **The next push to main re-runs the same ALTERs with the same exposure.**

2. **The live sitemap is not what the brief believed.** `api.earningsnerd.io/sitemap.xml` (old code — static entries stamped with
   today's date; cf. `git show 4994360:backend/app/routers/sitemap.py`) lists **635 companies and 36,140 filings** — every Company
   and every Filing row. `www.earningsnerd.io/sitemap.xml` returns **510 companies / 1,429 filings with `lastmod=2026-07-16`** — a
   snapshot frozen on the Vercel build day, never regenerated (`frontend/app/sitemap.ts:5-6` revalidates hourly; **[hypothesis]**
   regeneration fails because the upstream document is now 6.3 MB — beyond Next's fetch data-cache / Vercel response limits — so
   ISR keeps the last good copy). So "511 companies / 1,429 filings" was the **entire DB on 07-16**, not "summarised filings".
   Since then the DB grew 25× to ~36k filings via the on-visit EFTS deep backfill (`routers/filings.py:246` →
   `filing_history_service.py`), spread 2001→2026 (812 filings dated 2001 … 3,515 dated 2026).

3. **Summary coverage is thin and user-driven.** 0 of 7 sampled recent 10-Q/10-K/6-K filings have a summary
   (`GET /api/summaries/filing/{36139,36136,36134,35880,35748,35733,36140}` → `id:0`); the AAPL example (`/filing/3`) is
   `tier=full`. The only scheduled generation is the weekly pregenerate of **8 tickers, 10-K only**
   (`scripts/pregenerate_examples.py:37-46`). Of the last 50 filing rows, 27 are 6-Ks (no summary path exists for 6-K — FPI
   Phase 4 deferred), 21 10-Q, 1 10-K, 1 8-K.

4. **Universe list is stale and its refresh is broken.** `backend/app/data/index_membership.json` (515 tickers) was last committed
   2026-07-07 (`db47315`). Both scheduled refreshes (08-01 run `30694838077`, 09-01 run `33511750077`) failed in <1 s:
   `fetch failed (wikipedia): no constituents table found at https://en.wikipedia.org/wiki/Nasdaq-100` (table-picking heuristic
   `scripts/refresh_index_membership.py:99-124`). The S&P quarterly rebalance lands in the third week of September; the calendar
   will silently miss it. Only **278/515 (54 %)** universe members have a Company row; 357 of the 635 company rows are outside
   the universe (OTC/ADR names such as ABCFF, AKZOY, AZBLY). The universe bounds only the calendar/reporting-this-week; company
   and filing pages fail open to any SEC ticker (`index_membership_service.py:86-97`, `routers/companies.py:436-496`).

---

## (A) Pipeline + jobs map

### Data flow (as built)

```
SEC EDGAR ──edgartools──▶ edgar/client.py (get_filings_multi :339-470; _transform_filing :542-603 ⇒ sec_url/document_url)
   │  breaker: 5 failures→OPEN, 30s half-open (edgar/circuit_breaker.py:46-70); per-process token bucket 10 req/s (sec_rate_limiter.py:37-95)
   ├─▶ routers/filings.py:170-260  DB-first list; first view = bounded live fetch; on-visit EFTS deep backfill enqueued (:246)
   ├─▶ filing_scan_service.py       hourly watched-company scan: 10-K/10-Q/8-K (+20-F/6-K/40-F behind ENABLE_FPI_FILINGS) :33-51
   ├─▶ filing_history_service.py    EFTS 2001→ walk, 10-K/10-Q only, amendments skipped :34-35,:55-78; stamps history_backfilled_at :140
   ├─▶ summary_pipeline.py          THE orchestrator: text + accession-aware XBRL (instance_extractor) → AI → Summary
   │        └─▶ facts_service.process_filing_facts hook (summary_pipeline.py:389) → financial_fact (per-filing comparatives)
   ├─▶ facts_service.backfill_facts (weekly job) only over filings that already carry xbrl_data :599-687
   ├─▶ facts_service.ingest_companyfacts (lazy, on Multi-Period coverage request) routers/analysis.py:84-124
   ├─▶ earnings_calendar_service.run_refresh  AV bulk CSV + EFTS 8-K 2.02 sweep → earnings_events :413-478
   └─▶ notable_filings_service.run_scan       EFTS market-wide → notable_filings (serving flag-gated, config.py:410)
```

Integrations (`app/integrations/`): `sec_api` (EFTS, keyless, routed through `sec_rate_limiter`) — live, feeds `/api/search`,
calendar sweep, notable scan, history backfill; `alpha_vantage` — live (prod calendar returns `eps_estimate`, so
`ALPHA_VANTAGE_API_KEY` is set despite `config.py:290-293` "stays unset until licensed"); `fmp`, `finnhub` — tombstoned; `stocktwits`
— ToS-barred, "unused pending a license" but still imported by `trending_service.py:12`.

### Jobs

**Correction, 2026-09-06:** The paragraphs and table below preserve the original audit
snapshot. Current filing scan/digest entrypoints use `job_run_service.track_job`, which records
attempts and returned failure counters in independent transactions. This replaces their original
"None" failure-visibility description; it does not undo the business transaction. The table's
"unique key blocks dupes" refers only to log rows: `filing_scan_service` sends before inserting
the unique `NotificationLog`, so concurrent external sends can duplicate, and logged failures
currently suppress retries. The former CLI dry-run used a successful no-op sender through that
same mutating service. The dry-run safety change rejects both modes before application work;
it creates no preview and repairs no historical logs. See
[`scripts/filing_scan.py`](../../backend/scripts/filing_scan.py),
[`job_run_service.py`](../../backend/app/services/job_run_service.py), and
[`filing_scan_service.py`](../../backend/app/services/filing_scan_service.py).

Schedules are created out-of-band (Cloud Scheduler) per `docs/DEPLOYMENT.md` §9–§12; CI only bumps images (`ci.yml:392-415`).
No job has a heartbeat, dead-man switch or Sentry (`sentry_sdk.init` exists only in `backend/main.py:24`; scripts never initialise
it). Failure visibility = Cloud Run job execution history + Cloud Logging. Scheduler retry policy is out-of-band and
**unverifiable from the repo**.

| Job (Cloud Run) | Entrypoint | Cadence | What it does | Failure visibility | Risk / notes |
|---|---|---|---|---|---|
| `earningsnerd-pregenerate` | `scripts/pregenerate_examples.py` → `precompute_service.precompute_one` | Mon 06:00 UTC | Latest **10-K** summary for 8 hardcoded tickers (BABA → 20-F) | None (job status only) | Covers 8/515 names; 10-Q gap is a prose TODO (`docs/OPERATIONS.md` "Keep the recommended filing warm"). 20-F needs `ENABLE_FPI_FILINGS` in the **job** env (`precompute_service.py:62-68`) but CI sets it only on the service (`ci.yml:386`) → **[hypothesis]** BABA returns `unsupported_form` weekly. |
| `earningsnerd-filing-scan` | `scripts/filing_scan.py` → `filing_scan_service.run_filing_scan` | hourly | Fetch latest 10 filings per watched company (cadence guard :183-213), upsert `Filing` (:76-126), real-time Pro alerts | None; `NotificationLog` unique key blocks dupes | One SEC call per watched company per hour; 6-K flood from foreign banks (HSBC 3× in 2 days) creates unsummarisable stub rows. |
| `earningsnerd-filing-digest` | `scripts/filing_scan.py --digest` | daily 08:00 UTC | Free/digest email batch | None | Also hosts the weekly data-quality report (only job with RESEND + DB). |
| `earningsnerd-backfill-facts` | `scripts/backfill_facts.py --only-new` → `facts_service.backfill_facts` | Mon 07:00 UTC | Normalise `xbrl_data` → `financial_fact`; cross-check vs companyfacts | None | Only filings with `xbrl_data` (already summarised) — coverage bounded by headline #3. Cross-check uses **raw httpx to data.sec.gov outside the limiter** (`facts_service.py:449-478`, 0.2 s sleep) — rule 5 violation. |
| `earningsnerd-earnings-calendar-refresh` | `scripts/earnings_calendar_job.py` → `run_refresh` | daily 05:30 ET | AV estimates + EFTS 8-K 2.02 flip (timing-guarded `:101-125`, flip-only `:277-375`) + stale downgrade + rescore | `commit_failed` logged, never raised (`:466-477`) | AV licence personal-use; sweep page cap 40 (`:479`) only logs when hit. |
| `earningsnerd-earnings-day-alerts` | `scripts/earnings_calendar_job.py --alerts` → `earnings_alert_service.send_earnings_day_alerts` | daily 06:00 ET | One digest per opted-in user | None | Depends on the refresh 30 min earlier having succeeded. |
| `earningsnerd-notable-filings` (7th, in CI loop `ci.yml:404`) | `scripts/notable_filings_job.py` | 08:30 + 18:30 ET | EFTS market-wide notable scan | None | Serving gated by `NOTABLE_FILINGS_ENABLED` (default False, not set in ci.yml). |
| GitHub `data-quality-weekly.yml` | fires `filing-digest` job with `scripts/data_quality_report.py` | Mon 13:00 UTC | 4 detections → email founder | GitHub run status (8/8 green 07-13→08-31) | Only repo-visible health signal in the platform. |
| GitHub `refresh-index-membership.yml` | `scripts/refresh_index_membership.py --source wikipedia` | 1st of month 08:00 UTC | Regenerate universe, open PR on diff | GitHub run status — **2/2 failed** | Universe frozen at 2026-07-07. |

**Impact of the incomplete 07-16 deploy on jobs:** `git diff --stat 4994360 e8ea339 -- backend/` touches only
`routers/{hot_filings,insiders,search,sitemap}.py`, `main.py` and tests — **no job code**, so jobs on the 07-13 image behave
identically to HEAD. What is missing in prod is service-side: the truthful sitemap (`d5ce7ac`), API-host robots Disallow
(`4a55150`), per-IP limits on `/api/companies/{t}/insiders` and `/api/search/full-text` (always-live-EDGAR endpoints) and removal
of the anonymous `hot_filings force_refresh` cache bypass (`b8cb847`). Those are open crawler→SEC cost/ban holes. **[inferred]**
service image = job images = `4994360` (deploy step skipped + old-code sitemap behaviour observed live).

Other DDL/lock hazards: `ensure_additive_columns` runs DDL at API startup (`main.py:93`, `database.py:54-60`) — sanctioned by
rule 3 but in tension with `lessons/ops-no-ddl-in-startup-path.md`; `/internal/jobs/*` triggers still run work in
`BackgroundTasks` (`routers/internal.py`), which DEPLOYMENT.md §11 documents as unreliable on Cloud Run.

Per-process SEC budget (lesson `arch-per-process-state-on-cloud-run`): API (≤2 instances) + up to 7 job processes, each with its
own 10 req/s bucket, plus one un-metered fetcher (`facts_service.py:449-478`) and the on-visit EFTS backfill running inside the API
process. **[hypothesis]** aggregate can exceed SEC's 10 req/s/IP in the Monday 06:00–07:00 UTC window.

---

## (B) Coverage findings (numbers)

| Metric | Value | Source |
|---|---|---|
| Company rows (prod) | 635 | api sitemap (old code lists every Company) |
| Filing rows (prod) | ≈36,140 (ids 1…36140 contiguous) | api sitemap |
| Filings by filing-year | 2001: 812 · 2010: 1,104 · 2020: 1,473 · 2024: 2,117 · 2025: 3,097 · 2026: 3,515 | api sitemap lastmod |
| DB on 2026-07-16 | 510 companies / 1,429 filings | www sitemap frozen snapshot (`lastmod 2026-07-16`) |
| Universe members with a Company row | **278 / 515 = 54 %** | index_membership.json ∩ sitemap companies (dash→dot normalised) |
| Universe members with no row at all | 237 (e.g. ADBE, BMY, CMCSA, COP, CVS, DUK, EBAY, CME, ADP, AIG…) | same |
| Company rows outside the universe | 357 / 635 | same |
| Recent filings with a summary | **0 / 7** sampled (LULU, MDT, NTAP 10-Q; JKHY 10-K; WMT, CRM 10-Q; BABA 6-K) | `GET /api/summaries/filing/{id}` |
| Known-good example | `/filing/3` AAPL FY2025 10-K: `tier=full`, 7,050-char overview | same |
| Form mix of last 50 filing rows | 27 × 6-K, 21 × 10-Q, 1 × 10-K, 1 × 8-K | `GET /api/filings/recent/latest?limit=50` |
| Summarised-filing count | **unknown from public surfaces** (truthful sitemap not deployed); brief's "1,429" = total filings on 07-16, not summaries | — |
| Health | `healthy`; breaker `closed`, 197 requests, 98.5 % success; Redis disabled | `/health/detailed` |
| Calendar | `universe: sp500_nasdaq100` (filter ON in prod), AV `eps_estimate` populated | `GET /api/calendar?from=2026-09-07&to=2026-09-11` |

Interpretation:
- The 1,429 → 36k growth is the P1-6 on-visit deep backfill (`filings.py:246`, `filing_history_service.py`) plus hourly scans.
  It fixed the JPM "4 filings" bug but turned the filing table into ~36k pages, only a small fraction of which can ever be
  summarised on demand; the frontend noindexes summary-less stubs (07-16 build) but the API sitemap still advertises all of them
  and www's copy is stale.
- Universe coverage is the product-quality gap: nearly half of S&P 500 ∪ NDX has never been touched, and the touched half is
  mostly unsummarised. Generation is account-gated and user-triggered (#619), so coverage grows only with logged-in traffic.
- The weekly report measures none of this (`data_quality_service.py:27-33` covers ticker integrity, cash/equity/OCF FY lag,
  deep-facts-vs-≤2-10-K anomaly, partial reasons) and cannot detect the frozen universe or the failed deploy.

---

## (C) Unfinished data work

| Item | Evidence | Status | Size | Quality impact |
|---|---|---|---|---|
| Migration step hangs on hot-table ALTER; no `lock_timeout`, no job timeout, no migration ledger | `ci.yml:329-369`; `migrations/20260122_add_markdown_cache_columns.sql:4-7`; run `29524625738` log | **Blocking all deploys since 07-16** | S | Everything below cannot ship |
| Truthful sitemap + crawler protections | `routers/sitemap.py:97-126` (HEAD) vs prod old code; `b8cb847`, `4a55150` | Merged, **not deployed** | S (deploy) | 36k stub URLs advertised; unmetered EDGAR-backed endpoints exposed |
| www sitemap frozen at 07-16 snapshot | `frontend/app/sitemap.ts:44-52`; live www `lastmod 2026-07-16` | Live defect | S–M (sitemap index / size cap) | Crawlers see a 7-week-old inventory |
| Pregeneration scale-out (S&P 500 latest 10-K + 10-Q ≈1,000 summaries) | `docs/SEO_ROADMAP.md:24-44`; `pregenerate_examples.py:37-46` = 8 tickers; `precompute_service.py:26` | Not started | M | Largest lever on "which filings have summaries" |
| Include 10-Q in the weekly pregenerate payload | `docs/OPERATIONS.md` "Keep the recommended filing warm" (prose TODO) | Not done | S | Recommended-filing banner points at a cold 10-Q |
| Universe refresh workflow broken (Nasdaq-100 Wikipedia table heuristic) | `scripts/refresh_index_membership.py:99-124`; runs `30694838077`, `33511750077` | Broken since Aug | S | Calendar misses rebalance; no age gate (`test_index_membership_service.py:60` checks shape, not age) |
| Universe coverage: 237 members with no Company row | (B) | Not addressed | M (seed via precompute cohort) | Discovery surfaces look empty for large caps |
| Weekly report lacks coverage / freshness / job-health sections | `data_quality_service.py:27-33,160-170` | Gap | S | The umbrella misses the biggest data issues |
| FPI Phase 4 (6-K interim) | `tasks/fpi-support-roadmap.md` §Phase 4 unchecked; 27/50 recent rows are 6-K | Deferred | L | Majority of new filing rows are unsummarisable stubs; 6-K alert spam risk |
| FPI Phase 5 (FPI-aware feed/scan/peers, insiders message, EFTS chips, evals) | roadmap §Phase 5 unchecked; only unsupported-name guard shipped (`company_coverage.py`) | Partial | XL | Peers may mix currencies |
| Earnings calendar P3 (pattern estimator, submissions backfill, EntityPublicFloat, habitual bmo/amc) | strategy §4; `earnings_calendar_service.py:10` describes a `pattern` source with no code path in `run_refresh:413-478` | Not started | M–L | Estimates end at AV's 3-month horizon; AV dependency hardens |
| Earnings calendar P5 (month view, per-day SEO pages) | strategy §4 | Not started | M | — |
| **Launch licensing gate for Alpha Vantage** (personal-use tier live in prod) | `config.py:290-293`; live `eps_estimate`; strategy §3.6/§4 | Open | S (decision) | Legal/ToS exposure on a public surface |
| Dead-integration teardown (fmp/finnhub/stocktwits consumers + routers) | `test_dead_integrations_allowlist.py:19-29`; `hot_filings.py:11-12`, `trending_service.py:12-13`; routers mounted `main.py:353,355`; endpoints `routers/hot_filings.py:12`, `routers/trending.py:25` | Pending since 07-06 | S | Public `GET /api/trending_tickers` still triggers Stocktwits+FMP calls (fail-soft) |
| Remediation P1-7: SIC backfill (prod `Company.sic` NULL for all) | `docs/data-quality-remediation-log.md` "Deferred"; `scripts/backfill_facts.py --backfill-company-sic` exists | Deferred | S (one job run) | Peers cohorts collapse; weekly report SIC buckets read `null` |
| Remediation follow-ups: backfill C/MS/WFC/GS history; deployer SA access to `INTERNAL_JOB_TOKEN` | log "Founder notes" | Open | S | 4 standing anomalies in every weekly report |
| Unify the two companyfacts fetchers on the limiter | `docs/ARCHITECTURE.md` "Known residual debt"; `facts_service.py:449-478` vs `xbrl_service.py:910-932` | Open | S | Rule-5 violation in a scheduled job |
| `_parse_company_facts` never fills `total_liabilities`/`cash_and_equivalents` | ARCHITECTURE "Known residual debt" | Open | S | Fallback-path metrics silently thinner |
| Amendments (10-K/A, 10-Q/A) never listed or ingested | `edgar/compat.py:275 include_amended=False`; `filing_history_service.py:57-58,68`; `filing_scan_service.py:33` | Open (noted in DQ investigation §2) | M | Restated financials invisible; summaries can cite superseded numbers |
| Retention policy implementation (inactivity deletion, daily cleanup jobs) | `docs/DATA_RETENTION_POLICY.md` §3.2-3.3, "DRAFT – Pending Implementation", target 2026-03-31 | Not implemented | M | Compliance promise vs reality (see §7) |

---

## (D) Risks

| Risk | Evidence | Severity | Mitigation |
|---|---|---|---|
| **Deploy pipeline blocked / next deploy can stall prod again** — every deploy re-runs `ALTER TABLE` on hot tables (`filing_content_cache`, `filings`, `users`, `watchlist`, `companies`, `user_usage`) with no lock timeout; a waiting ACCESS EXCLUSIVE blocks all new readers behind it | run `29524625738` log; `ci.yml:366-369`; `migrations/20260122…sql:4-7`, `20260620_filing_processed_facts_at.sql:9`, `20260615_oauth…sql:14,23`, `20260618_phase2_alerts.sql:9,14` | **P0** | `PGOPTIONS='-c lock_timeout=15s -c statement_timeout=10min'` on the psql loop + bounded retry; `timeout-minutes: 30` on `deploy-backend`; a `schema_migrations` ledger so converged files are skipped, or `information_schema`-guarded `DO $$` blocks that take no lock when converged; a Postgres service container in CI applying all migrations twice (rule-12 gate for rule 3) |
| **Undeployed crawler/cost protections** — unmetered always-live-EDGAR endpoints, anonymous `force_refresh`, crawlable API host | `git diff 4994360 e8ea339`; `test_public_edgar_rate_limits.py` not in prod | P0 (SEC ban = product down) | Fix the P0 above and deploy; interim: manual `gcloud run deploy` of the already-built `e8ea339` image |
| **36k stub filing pages advertised; www sitemap frozen** | (B); `frontend/app/sitemap.ts` | P1 | Deploy truthful sitemap; sitemap index past the 45k cap (`sitemap.py:44-46`); consider excluding 6-K/8-K from company-page listings until Phase 4 |
| **Universe frozen since 07-07, refresh silently failing** | runs `30694838077`, `33511750077`; `refresh_index_membership.py:99-124` | P1 | Fix table selection (match header text containing "Ticker"/"Symbol" across all tables; fall back to S&P-only + alert); add an age-gate test (fail if file >100 days old) so CI, not a scheduled workflow, surfaces staleness |
| **No job observability**: any of 7 jobs can fail for weeks unnoticed | `main.py:24` only; `scripts/*.py`; `data_quality_service.py` | P1 | `job_runs` table written by each script; weekly-report section "jobs stale >2× cadence"; Cloud Monitoring alert on job failures (pattern in `tasks/archive/beta-monitoring.md:73-84`) |
| **Alpha Vantage personal-use data on a public commercial surface** | `config.py:290-293`; live `/api/calendar` estimates; strategy §3.6 | P1 (legal) | License AV, or switch to EDGAR-only + P3 estimator before launch |
| **Silent wrong URL via listener fallback**: `before_insert` fabricates `…/edgar/data/0/{acc}/` when `company` isn't loaded | `models/__init__.py:355-366` | P1 | Raise instead of fabricate; regex-validate both URLs at the boundary; unit-test the listeners (none exist) |
| **Raw sec.gov httpx outside the limiter in a scheduled job** | `facts_service.py:449-478` | P1 | Route through `sec_rate_limiter.execute`; AST importer gate: only `services/edgar/**` and `integrations/sec_api.py` may reference `sec.gov` |
| **Amendments ignored** → restated numbers never surface | `compat.py:275`; `filing_history_service.py:57-68` | P2 | Ingest `/A` rows, mark superseded originals, prefer amendment in change report |
| **Scale/period pitfalls only heuristically guarded**: no explicit "in thousands" handling (relies on edgartools raw units); >10× swing only *flags* (`reconciled=False`) yet rows are stored/served | `facts_service.py:92-93,191-300`; `statement_parser.py` (no scale logic) | P2 | Unit/decimals assertions on the statement path; ensure `reconciled=False` is badged on every surface |
| **10-Q per-filing facts carry `fiscal_period=None`** | `facts_service.py:107-111`; `test_facts_service.py:57` | P2 | Derive the Q label from the duration window (reuse `_classify_duration`) |
| Dead integrations reachable on public endpoints | `main.py:353,355`; `trending_service.py:12-13` | P2 | Land the teardown PR; shrink allowlist to empty |
| Retention promises unimplemented; compliance doc names Gemini while prod sends filing text and user copilot questions to DeepSeek | `DATA_RETENTION_POLICY.md` §3.2-3.3 + "Implementation Blockers"; `DATA_COMPLIANCE.md` processors table vs `ci.yml:386` | P2 | See §7 |
| BABA weekly pregenerate likely no-ops (`ENABLE_FPI_FILINGS` absent from job env) **[hypothesis]** | `precompute_service.py:62-68`; `ci.yml:392-399` | P2 | Add the flag to the job `--update-env-vars` |
| `ensure_additive_columns` DDL in API startup path | `main.py:93`; `lessons/ops-no-ddl-in-startup-path.md` | P2 | Keep additive-only; prefer the migration ledger |

---

## (E) Ranked top-5 data investments

1. **Make deploys safe and unblock the pipeline (S).** `lock_timeout`/`statement_timeout` + retry on the psql loop,
   `timeout-minutes` on `deploy-backend`, a `schema_migrations` ledger (or `information_schema`-guarded `DO $$` blocks) so
   converged ALTERs take no lock, and a Postgres twice-apply CI gate. Nothing else ships until this does, and the 07-16
   evidence suggests the current design can stall production reads for hours.
2. **Universe-wide summary coverage program (M).** Run `POST /internal/jobs/precompute` (or a Cloud Run job) over the 515-name
   universe for latest 10-K **and** 10-Q in batches (`MAX_BATCH=1200` caps blast radius), add `"10-Q"` to the weekly pregenerate,
   and add a "summary coverage of universe / stub ratio" section to the weekly report. Converts "0/7 recent filings summarised,
   46 % of universe untouched" into the product's core asset and feeds the truthful sitemap.
3. **Inventory hygiene: truthful sitemap + stub containment (S–M).** Deploy the merged sitemap/robots/rate-limit work; add a
   sitemap index for >45k URLs and fix www regeneration; stop advertising/listing forms that cannot be summarised (6-K/8-K) until
   FPI Phase 4 — or ship a light 6-K path since 6-Ks are now >50 % of new rows.
4. **Universe + calendar integrity (S).** Fix the Nasdaq-100 table heuristic, add a committed-list age gate, decide the AV
   licence (or start the P3 estimator so EDGAR-only is viable), clear the four standing anomalies (C/MS/WFC/GS).
5. **Structural gates for data integrity (S each, rule 12).** (a) URL regex validation at the Filing boundary + remove the
   `cik="0"` fabrication + listener unit tests; (b) `sec.gov` importer allowlist test (catches `facts_service.py:449`);
   (c) job heartbeat table + weekly "stale job" section; (d) `/A` ingestion policy; (e) dead-integration teardown PR.

---

## Detailed notes by brief item

### 1. Pipeline + jobs — verified specifics
- Rate limiter: token bucket at `settings.SEC_RATE_LIMIT_PER_SECOND` (10) with backoff and Retry-After cap 120 s
  (`sec_rate_limiter.py:29,46-95`); module singleton, per process.
- Circuit breaker: `failure_threshold=5`, `success_threshold=2`, `recovery_timeout=30` s; trips only on network-shaped
  exceptions (`edgar/circuit_breaker.py:46-70`).
- Listing fetch: one `EdgarCompany`, one `get_filings(form=[base], amendments=False, trigger_full_load=False)`
  (`edgar/client.py:339-470`; `compat.py:271-277`); cheap fields only in `_transform_filing` (`client.py:542-603`).
- Jobs are plain scripts with `python` as container entrypoint (`ops.yml` "describe-jobs"; `DEPLOYMENT.md` §10-12).
- 07-16 deploy: `Build and push image` succeeded (image for `e8ea339` exists, tagged `latest`), but service and jobs were never
  updated.

### 2. Universe & coverage — see (B). `index_membership_service._load` fails open below 450 tickers (`:29,51-71`); filter
applied only in `reporting_this_week_service.py:150-161` and `earnings_calendar_service.py:157-162`; dash→dot normalisation
(`:32-42`).

### 3. Data-quality tooling
- `data-quality-weekly.yml` (Mon 13:00 UTC) executes `scripts/data_quality_report.py` inside the `filing-digest` job
  (`--args`, `--wait`); emails `settings.DATA_QUALITY_REPORT_EMAIL` (`config.py:119` = `neil@earningsnerd.io`) via Resend
  (`data_quality_service.py:173-193`). No artifact/issue; stdout in Cloud Run logs. 8/8 runs green.
- Sections: ticker mismatch vs SEC primary ticker (`:40-52`); FY coverage lag ≥2 y for cash/equity/OCF vs total_assets
  (`:55-90`); ≥5 FY of facts but ≤2 stored 10-K (`:93-125`); partial-tier reasons by SIC prefix (`:128-157`).
- Remediation log: P0-1…P0-5, P1-6, P1-8, P1-9 shipped (#585–#598) with gates; still open: P1-7 (SIC backfill; prod
  `USE_STATEMENT_FINANCIALS=true` already), all P2 (cash component-sum fallback, `ticker_aliases`), 4 anomalies (C/MS/WFC/GS),
  `INTERNAL_JOB_TOKEN` unreadable by deployer SA, no consolidated rollback runbook, `_is_rate_limit_error` substring match.
  Verified still open in code (no `ticker_aliases` model; `Company.sic` only via the manual `--backfill-company-sic`).

### 4. Earnings calendar & integrations — see (C). Shipped: `20260703_create_earnings_events.sql`, AV client, EFTS 2.02 sweep
with timing guard (tested in `test_earnings_calendar_engine.py`), flip-only sweep, stale downgrade, anticipation score,
`GET /api/calendar`, alerts, universe filter + purge script (`test_purge_non_index_earnings.py`), repair script
(`test_repair_false_reported_earnings.py`). `earnings_whispers.py` is gone. Keys: `FINNHUB_API_KEY`, `FMP_API_KEY`,
`ALPHA_VANTAGE_API_KEY` all optional (`config.py:277,285,293`); `DEPLOYMENT.md` bootstrap still mounts `FINNHUB_API_KEY`.
Dead-integration consumers: `hot_filings.py:11-12` (fmp, finnhub), `trending_service.py:12-13` (stocktwits, fmp); both routers
public (`main.py:353,355`); frontend hides Market Movers behind `ENABLE_MARKET_MOVERS` (`featureFlags.ts:93-94`).

### 5. XBRL correctness
- Period-selection lesson in code and tested: `DURATION_WINDOWS` (`instance_extractor.py:24-34`), anchor at
  `period_of_report` (`:338-360`), decimals-aware duplicate resolution (`:308-336`), currency vote (`:252-283`); tests
  `test_accession_xbrl_extraction.py:130,141,168,177,257,295,314,367-399`. Companyfacts fy/fp trap: `facts_service.py:935-955`,
  `_classify_duration:1027`, `_label_quarters:1137`, latest-filed-wins `:1040-1110`, Q4 = FY − YTD9 (`:1367`), shares-based Q4 EPS
  (`:1449`); tests `test_companyfacts_ingest.py:93,101,119,136,144,156,182,197,239`.
- FPI: currency-correct (Phase 3) — `_unit_for` (`:114-125`), non-USD skip in cross-check (`:404-425`), `test_fpi_currency.py`.
- Gaps: amendments; no explicit scale handling; 10-Q per-filing `fiscal_period=None`; `fiscal_year = period_end.year` (`:178`)
  is a convention, not SEC `fy`; 6-K has no financial path; `_parse_company_facts` USD-only with missing buckets.

### 6. Integrity gates
- NOT NULL columns `models/__init__.py:198-199`; listeners `:351-376` (insert, fabricated-CIK fallback) and `:379-385` (update).
  **No test exercises either listener.** URL builders: `client.py:581-583` (canonical), `sec_api.py:101-105` (mirror, tested at
  `test_sec_full_text_search.py:160`), `models/__init__.py:362` (fallback) — rule 10 says one. Prose-only rules deserving gates:
  URL format (10), sec.gov-only-via-edgar-layer (5), migrations re-applicable (3 — CI is SQLite-only), `os.getenv` outside config
  (8 — currently clean apart from `config.py:511,514`), universe freshness. Existing gates to model on:
  `test_naive_utcnow_allowlist.py`, `test_dead_integrations_allowlist.py`, `test_index_membership_service.py:60`,
  `test_sitemap.py`, `test_edgar_get_filings_multi.py`.

### 7. Retention / compliance
- Promised but absent: inactivity deletion (§3.2), daily cleanup of `user_searches`, `contact_submissions`, `waitlist_signups`,
  expired tokens, `audit_logs` (§3.3), monitoring (§8). `grep purge|prune|cleanup|expired` in `backend/app` finds no scheduled
  deletion; `login_attempts` are cleared only on successful login (`login_lockout.py:104-112`). `UserSearch` appears to have
  **no writer** (grep `UserSearch(` in routers/services → none) **[hypothesis]**. Orphan `guest_daily_usage` kept by design.
- Implemented: `DELETE /api/users/me` (`routers/users.py:422-543`: cascade, Stripe subscription cancel, customer kept for 7-y
  tax rule `:467-468`, PostHog `$delete` `:479-482`), `GET /api/users/export`, audit log on deletion.
- Doc drift: contact IPs already hashed (`routers/contact.py:26-40`, `models/contact.py:16`) though the policy says "TO BE
  REMOVED"; `DATA_COMPLIANCE.md` lists Google Gemini as AI processor while prod uses DeepSeek (`ci.yml:386`, ADR-0006) — filing
  text is public, but copilot questions are user-authored; DPAs open. `DATA_RETENTION_POLICY.md` is DRAFT with all four
  implementation blockers unchecked (target 2026-03-31 missed).

### Live probe log (all GET, cached/DB-only)
api: `/sitemap.xml`, `/api/filings/recent/latest?limit=50`, `/health/detailed`, `/api/calendar?from=2026-09-07&to=2026-09-11`,
`/api/summaries/filing/{36139,36136,36134,35880,35748,35733,36140,3}`, `/metrics` (401). www: `/sitemap.xml`.
