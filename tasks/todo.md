# Remediation plan — from the September 2026 engineering audit

Source: `docs/ENGINEERING_AUDIT_2026-09.md` (synthesis) + `docs/audit-2026-09/` (six workstream
appendices with file:line evidence). Lens: invite-only beta, product quality wins ties.
Founder merges; each phase is one or a few PRs. Items marked **(founder)** need the founder.

## Phase 0 — this PR: make releases safe, land the audit

- [x] Explicit ruff rule set (`select = ["E4","E7","E9","F"]`) + pinned `requirements-dev.txt`; CI and the local gate install from it
- [x] `timeout-minutes: 30` on `deploy-backend`
- [x] Migration step: `lock_timeout=10s` / `statement_timeout=120s`, 5 bounded retries, `pg_stat_activity` dump on final failure
- [x] Gate test `backend/tests/unit/test_migration_lock_safety.py` (workflow knobs, toolchain pin, explicit select, filename convention, frozen shrink-only allow-list of 17 legacy unguarded ALTERs)
- [x] Lessons: `ops-migrations-need-lock-timeout.md`, `ops-pin-ci-toolchain.md` (+ index)
- [x] Doc sync: `DEPLOYMENT.md` (7 jobs, `/health/detailed`, `pdx1`, migrations automatic, only backend pushes deploy), `CLAUDE.md` (7 jobs, rule-3 lock note, gate install line)
- [x] `frontend/package.json`: `"postcss": "$postcss"` override (unblocks Dependabot; lockfile-neutral, `npm ci` verified)
- [x] Archive finished SEO plan → `tasks/archive/seo-audit-quick-wins-todo.md`
- [x] **(founder)** Pre-flight: run the `pg_stat_activity` query in `ENGINEERING_AUDIT_2026-09.md` §2; terminate any idle-in-transaction session — *skipped by decision 2026-09-04 (no Cloud SQL access from the merging session; the new `lock_timeout` bounded the worst case to a failed, diagnosable job). The migration step applied all 32 files on the first attempt, so no blocker was present.*
- [x] **(founder)** Merge this PR → watch `deploy-backend` complete → verify API `robots.txt` is `Disallow: /`, `/health/detailed` healthy, 31-burst to `/api/companies/AAPL/insiders` → 429 — *done 2026-09-04 22:36–22:42Z: merge `df9c893`, CI run 1840 success; robots `Disallow: /` live after 319 s; `/health/detailed` healthy (db 7.8 ms, circuit closed); burst → 30×200 then 429 with `Retry-After: 36`.*
- [ ] **(founder)** Check Cloud Run 5xx/latency + Sentry for 2026-07-16 18:40Z → 07-17 00:38Z; if degraded, add a lesson

## Phase 1 — Priority 1: reliability floor (≈4 engineer-days + founder console time)

- [x] **(founder decision)** Migration design: DO-block guard only (status quo, gated) vs `schema_migrations` ledger (recommended; ADR supersedes rule-3 wording) — *decided 2026-09-04: ledger (PR #658, ADR-0007)*
- [x] Implement the chosen migration design — *PR #658 merged 2026-09-05 (`c6eaddf`); its first deploy failed because prod already had a foreign `schema_migrations` table, fixed by hotfix PR #678 (`f8e7728`, ledger renamed `migration_ledger`, CI decoy gate, ADR-0007 amendment, lesson `ops-deploy-owned-state-needs-a-distinctive-name.md`); seed deploy verified `applied=32 skipped=0`, health green*; Cloud SQL flag `idle_in_transaction_session_timeout` as DB-side backstop **(founder: flag)**; **(founder)** inspect and drop the legacy prod `schema_migrations` table
- [x] Extend the lock gate: plain `CREATE INDEX IF NOT EXISTS` on pre-existing tables (second frozen legacy list; `CONCURRENTLY` for new files) — *PR #656 merged 2026-09-05 (`f340bb0`), deploy green*
- [x] Ledger-skip the re-run `UPDATE` in `20260706_demote_null_fiscal_period_duplicates.sql` — *ledger live since #678; the file ran once at seed and is now skipped*
- [ ] Alerting minimum: uptime check on `/health/detailed`; Cloud Run job-failure alert; log-based alerts (SEC circuit open, generation failures); Actions failure notifications for `refresh-index-membership` / `data-quality-weekly` **(founder: GCP console)**
- [ ] Scheduled workflow running `tests/e2e/prod-smoke.spec.ts` against production (`SMOKE_BASE_URL`), daily
- [x] Frontend observability: `GlobalErrorBoundary` imports the Sentry SDK; delete the dead frontend `signup_completed` helper; pre-consent PostHog proposal — *PR #660 merged 2026-09-05 (`ffb0b61`)*; Sentry source-map env in Vercel **(founder)**
- [x] Dependabot triage: merge #635 #636 #639 #640 #641 #642 — *all merged 2026-09-04, deploys green*
- [x] Dependabot closes: #629 and #570 closed 2026-09-04; `typescript` major-ignore landed in #674; #662–#670 closed as superseded by #674 and #672 closed as superseded by #679 + #680; #659 closed so Dependabot re-creates the remaining 15 minors against Next 16.3.4 / Node 22 — *2026-09-05*; **(founder)** if no fresh group PR appears at the next Dependabot run, trigger a recreate from the Dependabot UI
- [ ] New Dependabot majors after the wave-1 baseline (2026-09-05): #684 `openai` 2.44 → 3.7 (the AI client façade — take through the eval gate with WS-6, check the OpenAI-compatible DeepSeek path and streaming), #685 `cryptography` 49 → 50 (PYSEC-2026-3552; check `python-jose[cryptography]` compat, then merge); #683 `actions/setup-python` 7 and #686 (14 frontend minors re-created from #659) merge on green CI
- [x] Split #672: non-edgartools bumps (pandas 3.0.5, fastapi, stripe, posthog, …) — *PR #679 merged 2026-09-05 (`fbbccc5`)*; edgartools 5.40.1→5.55.0 alone through the eval gate — *PR #680 in review (regression gate PASS, 0 warnings)*; close #672 after #680
- [x] Next.js 16.3.4 (+ transitive security patches, `npm audit --omit=dev` 10 → 0) — *PR #674 merged 2026-09-05 (`2f2e48d`); Vercel production deployment completed; `::highlight` lives in a constructed stylesheet; `next build` typechecks `tsconfig.ci.json`*
- [x] Dependency-audit gates in CI (advisory): `pip-audit -r backend/requirements.txt`, `npm audit --omit=dev --audit-level=high` — *PR #674*; flip to blocking once `cryptography` 49→50 and the `@lhci/cli` chain are resolved
- [ ] Backups: PITR + deletion protection on `earningsnerd-db`; monthly export to lifecycle-managed GCS; one-page rehearsed restore runbook **(founder: console)**
- [x] Universe refresh: FMP stable API first, loud partial-list abort, 100-day age gate — *PR #655 merged 2026-09-05 (`49dd399`), deploy green*; first scheduled run needs `FMP_API_KEY` **(founder: secret)**
- [x] Pricing page SSR (`useSearchParams` → Suspense-scoped child) + Product/Offer JSON-LD; contact meta-description entity; noindex auth pages — *PR #660 merged 2026-09-05*
- [x] Node 20 → 22.23.2 (`.nvmrc`, `engines`, CI ×3, lockstep gate `nodeVersionLockstep.spec.ts`) — *PR #674*; **(founder)** set the Vercel project Node.js Version to 22 so the dashboard matches the `engines.node` override that already governs the build
- [x] Quick wins: `ops.yml` push trigger removed + `cloud-sql-proxy` sha256 pinned (*#656*); `hot_filings.py` and the trending refresh route deleted outright (*#657*, so the admin-token compare and rate limit are moot)
- [x] Drop `"log"` from client Sentry console levels — *PR #660 merged 2026-09-05*
- [x] Rule-8 gate: env-access allow-list test — *PR #661 merged 2026-09-05 (`41abb26`), deploy green*

## Phase 2 — Priority 2: summary fidelity measurement, then arm the guards (≈7 engineer-days)

- [ ] Pin `mean_untraceable_dollar_figures` (figure-trace) as an eval dimension — WARN first, floor after one re-pin cycle
- [ ] Scheduled judged eval run (8 filings, `--runs 3`, judge on) with a weekly readout; keep judge off in PR CI
- [ ] Roll the five audit counters (figure-trace, forward-quote, evidence-snap, machine-sections-only, quality gate) into the weekly data-quality report from persisted `raw_summary` audits
- [ ] **(founder decision)** Arm `AI_EVIDENCE_SNAP` (measured +0.17 citation fidelity) after the first readout; then decide `AI_FIGURE_TRACE_GATE`, `AI_FORWARD_QUOTE_GATE`
- [ ] Retry/fallback: delete the dead Gemini chain in `openai_service.py`; bounded backoff on the primary; env-configured `AI_FALLBACK_BASE_URL`/`AI_FALLBACK_MODEL`; fix the retry unit test to use real names
- [ ] Per-summary telemetry: log `usage` and `response.model`; surface on `/metrics`
- [ ] Eval ↔ prod parity: `USE_STATEMENT_FINANCIALS` in eval env; restore JPM bank-gate facts (G5 re-arm); exercise the streaming branch in `evals/runner.py`; re-pin baseline; fix `--runs 1` single-veto flakiness (granularity-aware tolerance or `--runs 2`)
- [ ] Copilot on live FPI filings: currency directive (never bare `$` for CNY/TWD/EUR); scope `_query_fact` to the filing being viewed (period from the filing, not `is_latest` company-wide); grow the Copilot golden set from 2 unverified entries; run `evals.copilot_runner`
- [ ] Golden-set breadth: 6-K entries, one REIT/utility/insurer, small caps **(founder: ~$10 model spend)**
- [x] Reading surface on the filing page: distinct risk headings, mobile section jump-nav, skip-to-content + live region, company-name casing — *PRs #671 + #676 merged 2026-09-05, casing verified live*
- [ ] Section-recovery grounding: build context from labelled excerpt sections (~30k cap) instead of raw HTML with a 6,000-char cap
- [ ] Delete the latent `previous_filings` prompt path + AST pin (rule 2 hygiene)
- [ ] **(founder spend call)** Drain cached v1 summaries → v2 via admin `refresh-stale` (~$0.05/filing)
- [ ] Docs: RUNBOOK:428 FPI status, report-quality plan header, Gemini-era comments in `openai_service.py`, `DATA_COMPLIANCE.md` processor table (DeepSeek, not Gemini)

## Phase 3 — Priority 3: coverage and data integrity for the beta universe (≈8 engineer-days)

- [ ] **(founder spend call ~$25–50 one-time)** Universe-wide pregeneration: latest 10-K + 10-Q for the 515-name universe in batches via `precompute`; add `10-Q` to the weekly pregenerate; seed Company rows for the 237 members without one
- [ ] Weekly report: summary coverage of universe, stub ratio, universe-list age, per-job last-success (`job_runs` heartbeat table written by every job script)
- [ ] SIC backfill (`backfill_facts.py --backfill-company-sic`) and graduate `USE_STATEMENT_FINANCIALS` default to True in code; add `ENABLE_FPI_FILINGS` to the pregenerate job env
- [ ] Amendments: list/ingest 10-K/A and 10-Q/A; mark superseded originals; prefer amendment in the Change Report
- [ ] Derive `fiscal_period` for 10-Q per-filing facts; unit/decimals assertions on the statement path; badge `reconciled=False` on every surface
- [x] Rule-5 gate: `_fetch_companyfacts_sync` through the SEC limiter via the app-loop bridge (`app/services/event_loop.py`); `sec.gov` allow-list test — *PRs #661 + #675 merged 2026-09-05*
- [x] Rule-10 gate: `app/utils/sec_urls.py::build_sec_archive_url` + listener tests — *PR #661 merged 2026-09-05*
- [ ] Sitemap: `app/sitemap.ts` stops fetch-caching the upstream document (or sitemap index past 45k URLs); regression test; correct `docs/SEO_AUDIT.md`; add `/terms`
- [ ] 6-K classifier (earnings vs governance vs press release): the 6-K summary path exists behind `ENABLE_FPI_FILINGS` (`prompts/6k-*.md`, `summary_pipeline.py:358-489`) but every 6-K gets one prompt; add 6-K golden-set entries
- [x] Dead-integration teardown: trending, hot_filings, fmp, finnhub, stocktwits and their consumers removed — *PR #657 merged 2026-09-05 (`9ff8da6`), deploy green, old routes 404*
- [ ] Clear the four standing weekly-report anomalies: `backfill-filing-history` for C, MS, WFC, GS; grant deployer SA access to `INTERNAL_JOB_TOKEN`
- [ ] `_parse_company_facts`: populate `total_liabilities` / `cash_and_equivalents`; PS5: read persisted `Filing.xbrl_data` before live SEC
- [ ] **(founder decision)** Notable filings: flip `NOTABLE_FILINGS_ENABLED` after a one-week quality look (job + seed + flag per `DEPLOYMENT.md`), or kill the slot; archive the homepage-sections findings doc
- [ ] Archive `tasks/fpi-support-roadmap.md` with a status block (Phases 0–5 shipped, flag on); residual: 6-K classifier, post-flip `backfill_facts` run

## Founder decisions (engineering is blocked on these)

- [x] Migration design (guard-only vs ledger) — *ledger, 2026-09-04*
- [ ] Arm/keep-advisory per trust gate after readout — Phase 2
- [ ] Spend: universe pregeneration, v1→v2 drain, golden-set runs, FMP key
- [ ] Dark surfaces for beta: Multi-Period Analysis (prod flag state unknown — confirm), Notable filings, Calendar (+ Alpha Vantage licence), Insiders
- [ ] Alpha Vantage: licence or EDGAR-only
- [ ] Legal: Terms §7e counsel pass; processor DPAs; legal entity / governing law
- [ ] `WAITLIST_MODE` intent; LAUNCH_CHECKLIST founder-only actions (GSC, Bing, apex 307→308, Vercel plan, `NEXT_PUBLIC_EXAMPLE_FILING_ID`)
- [ ] Pro trial timing; delete retired reverse-trial code?
- [ ] `USE_STRUCTURED_OUTPUT`: bake-off or delete
- [ ] Close #570 and #629; merge the six safe Dependabot PRs; approve dead-integration teardown
- [ ] GCP console: PITR + deletion protection; uptime/alert policies; Turnstile keys; confirm `REGISTRATION_MODE` and flags via `ops.yml describe-service`

## Deferred (tracked in appendix 06, not scheduled)

SEO phases 2–3; dashboard "later" tier (8-K rows, weekly brief, sparklines, 13F); competitive roadmap
A4/A7/A8; cold-path Phase C; MFA/TOTP; retention purge jobs (policy promise — schedule before public
launch); Turnstile fail-closed; T5 depth ledger; cheaper-model routing flags; waitlist/contact route tests;
`SUMMARY_SELF_VERIFY`; prompt-prefix caching; off-peak cron windows.
