# Remediation plan — from the September 2026 engineering audit

Source: `docs/ENGINEERING_AUDIT_2026-09.md` (synthesis) + `docs/audit-2026-09/` (six workstream
appendices with file:line evidence). Lens: invite-only beta, product quality wins ties.
Founder merges; each phase is one or a few PRs. Items marked **(founder)** need the founder.

## Wave 2 execution — 2026-09-05

Owner: chief engineer (Codex); founder has authorized engineering merges and deployments.
Accepted D1–D8 remain in force. Existing unchecked decision rows below are historical tracking,
not requests to revisit accepted decisions. Founder-only actions remain founder-only.

Current checkpoint: main `c925cfa83647f521583b6fa4dd257ac9027461db` (#697).
[Interim ledger](wave2-ledger-2026-09.md) records exact merges and observed gates. #697 deployment
33962267301 is verified: `applied=1 skipped=33`, revision `00263-kzt`, detailed health healthy.
Vercel production also succeeded for #697.
#673 remains untouched; #684 is held for resilience; #685 merged and #686 split/closed.
CI's authorized DeepSeek runner produced #698's corrected 52-output parity pass; final 26 × 3
run 33962580838 is in progress on integrated `f5b46ba9`; the baseline is unchanged.
No usable strong-judge credential is available for the first weekly readout,
so evidence-snap activation stays held. This macOS host differs from the historical cloud host.
The saved Claude Workflow runtime is unavailable in Codex; reproduce its three independent
review lenses and two independent refuters per serious finding with Codex subagents.
Missing verifier output is unverified and must be hand-verified before merge.

- [x] Chief engineer: execution plan merged #689 (`47d65a2c`), reviewed and CI green.
- [x] Backend Developer + Database Specialist: WS-7 steps 1–2 merged #690 (`99e91ba7`); graduate statement
  financials default, prepare SIC backfill instructions, implement distinctive job heartbeat
  storage with a new lock-safe migration, instrument every job, report coverage/stubs/age/last success.
- [ ] Chief engineer: serialize backend merges; verify deploy-backend, exact migration summary,
  and healthy detailed health after each merge before the next backend merge.
- [ ] Founder: trigger SIC backfill; supply observed completion before declaring SIC data backfilled.
- [x] Backend Developer: WS-7 remaining code steps merged #697 (`c925cfa8`): 10-Q periods/unit assertions and
  reconciliation labels; amendments/supersession/Change Report; persisted XBRL first and missing
  balance-sheet facts; FPI + 10-Q pregeneration and universe Company seeding preparation.
- [ ] AI Engineer: #698 draft; corrected two-run measurement passed; final merged-state three-run pin pending. Read eval RUNBOOK;
  parity (statement env, JPM G5, streaming, tolerance, note preservation), then one honest re-pin.
- [ ] AI Engineer: WARN figure-trace dimension, persisted audit counters, weekly judged readout
  workflow and first observed readout; resilience with #684, real fallback configuration,
  bounded retries, usage/model telemetry and empty-grounding protection; full backend + live eval gates.
- [ ] AI Engineer: delete previous_filings with AST pin; labelled recovery context; copilot currency,
  accession-scoped facts, at least five verified golden entries and observed copilot gate.
- [ ] Chief engineer: arm AI_EVIDENCE_SNAP in ci.yml only after first judged readout; founder triggers drain.
- [x] Frontend Developer: sitemap freshness + /terms + SEO correction merged #693 (`157e6a39`).
- [x] Frontend Developer: locate boundary and regression/mutation proof merged #691 (`a2c7fa70`).
- [x] Frontend Developer: #686 split/closed through #694 (`6e169de8`) and #695 (`919aa862`);
  full lint/typecheck/vitest/build and Playwright with no backend for each candidate.
- [x] Security/Backend Developer: #685 compatibility/backend gate and verified deployment (`5cb23b8a`).
- [x] Backend + Frontend Developers: WS-9 preparation merged #692 (`60d8015e`); activation remains held;
  Analysis requires confirmed Vercel value + warmed companyfacts; Notable requires founder-created
  job, seed and a week of review before repository flag flip. Calendar and Insiders stay off.
- [ ] Knowledge Curator (rolling, owners fix docs with their code): correct migration stack truth,
  report/eval/config/deployment docs; resolve script/test placement; archive completed FPI plans
  with explicit residuals. Do not archive unfinished work as complete.
- [ ] Founder: pregeneration off-peak only after WS-7 prerequisites; console/secrets/licence actions
  remain as listed in handover §6, with exact instructions in the relevant PR.
- [ ] Chief engineer: hourly quiet check-in while work is in flight; close-out only on handover §7
  evidence, update todo and briefs dispatch log on fresh main branch, report SHAs and held items.

Every implementation PR is draft immediately, uses a worktree under `.claude/worktrees/`,
and includes exact gate tails and mutation proofs. Locked contracts, migration allow-lists,
and AI baseline protections remain unchanged unless explicitly permitted by the mandate.

## WS-6 resilience implementation — after #700

Base: measurement merged `80314db6`; root owns its deployment verification. Parity #698
and measurement implementation #700 are complete; the first strong-judge readout remains
credential-held. This stage does not re-pin, arm a guard, or perform founder operations.

- [ ] Integrate exact OpenAI 3.7.0 / jiter 0.16 / native httpx2 lock, preserving cryptography 50.
- [ ] Own one bounded call-local deadline and retry policy across primary, stream fallback,
  optional independently authenticated provider fallback, and section recovery; close streams.
- [ ] Record actual response model and usage per attempt, including empty-choice usage chunks;
  expose bounded summary aggregates and preserve unknown values.
- [ ] Require usable excerpt or numeric XBRL for full quality; preserve locked SSE/quota contracts.
- [ ] Update fallback Settings/inventory/deployment instructions, processor and stale routing docs.
- [ ] Prove native SDK request/retry/SSE/cancellation behavior offline, kill each new-test mutant,
  run exact full backend gate, inspect actual full CI evaluation artifact, and obtain three lenses.

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
- [ ] Remaining major #684 `openai` 2.44 → 3.7: take with WS-6 resilience and live eval gates. #685 merged; #683 merged; #686 closed as superseded by #694/#695.
- [x] Split #672: non-edgartools bumps (pandas 3.0.5, fastapi, stripe, posthog, …) — *PR #679 merged 2026-09-05 (`fbbccc5`)*; edgartools 5.40.1→5.55.0 alone through the eval gate — *PR #680 merged (`083247d`, regression gate PASS, 0 warnings)*; #672 closed
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
- [ ] Arm `AI_EVIDENCE_SNAP` only after the first judged readout (D5 accepted); figure-trace and forward-quote remain advisory. Strong-judge credential/readout currently unavailable
- [ ] Retry/fallback: delete the dead Gemini chain in `openai_service.py`; bounded backoff on the primary; env-configured `AI_FALLBACK_BASE_URL`/`AI_FALLBACK_MODEL`; fix the retry unit test to use real names
- [ ] Per-summary telemetry: log `usage` and `response.model`; surface on `/metrics`
- [ ] Eval ↔ prod parity: `USE_STATEMENT_FINANCIALS` in eval env; restore JPM bank-gate facts (G5 re-arm); exercise the streaming branch in `evals/runner.py`; re-pin baseline; fix `--runs 1` single-veto flakiness (granularity-aware tolerance or `--runs 2`)
- [ ] Copilot on live FPI filings: currency directive (never bare `$` for CNY/TWD/EUR); scope `_query_fact` to the filing being viewed (period from the filing, not `is_latest` company-wide); grow the Copilot golden set from 2 unverified entries; run `evals.copilot_runner`
- [ ] Golden-set breadth: 6-K entries, one REIT/utility/insurer, small caps **(D4 spend approved; execution pending)**
- [x] Reading surface on the filing page: distinct risk headings, mobile section jump-nav, skip-to-content + live region, company-name casing — *PRs #671 + #676 merged 2026-09-05, casing verified live*
- [ ] Section-recovery grounding: build context from labelled excerpt sections (~30k cap) instead of raw HTML with a 6,000-char cap
- [ ] Delete the latent `previous_filings` prompt path + AST pin (rule 2 hygiene)
- [ ] **D4 spend approved; founder execution pending:** drain cached v1 summaries → v2 via admin `refresh-stale` (~$0.05/filing), after D5's judged-readout and evidence-snap prerequisites
- [ ] Docs: RUNBOOK:428 FPI status, report-quality plan header, Gemini-era comments in `openai_service.py`, `DATA_COMPLIANCE.md` processor table (DeepSeek, not Gemini)

## Phase 3 — Priority 3: coverage and data integrity for the beta universe (≈8 engineer-days)

- [ ] **D4 spend approved; founder execution pending (~$25–50 one-time):** universe-wide pregeneration, latest 10-K + 10-Q for the 515-name universe in batches via `precompute`; weekly 10-Q and Company seed tooling merged #697; founder seed/SIC enrichment and off-peak generation still pending (237 missing rows was the audit snapshot)
- [x] Weekly coverage/stub/universe-age/job-heartbeat report implementation — #690. Live report/backfill evidence remains required.
- [ ] **(founder)** Execute SIC backfill and retain completion/report evidence. Code default True shipped #690; pregenerate FPI env shipped #697; neither proves data was backfilled.
- [x] Amendments: list/ingest 10-K/A and 10-Q/A; supersession and Change Report — #697; existing rows link on refresh/backfill.
- [x] Fiscal periods, unit/decimals assertions and reconciliation UI/exports — #697; old snapshots need deliberate re-extraction.
- [x] Rule-5 gate: `_fetch_companyfacts_sync` through the SEC limiter via the app-loop bridge (`app/services/event_loop.py`); `sec.gov` allow-list test — *PRs #661 + #675 merged 2026-09-05*
- [x] Rule-10 gate: `app/utils/sec_urls.py::build_sec_archive_url` + listener tests — *PR #661 merged 2026-09-05*
- [x] Sitemap: hourly ISR with uncached upstream fetch, regression tests, `/terms` and SEO doc — #693.
- [ ] 6-K classifier (earnings vs governance vs press release): the 6-K summary path exists behind `ENABLE_FPI_FILINGS` (`prompts/6k-*.md`, `summary_pipeline.py:358-489`) but every 6-K gets one prompt; add 6-K golden-set entries
- [x] Dead-integration teardown: trending, hot_filings, fmp, finnhub, stocktwits and their consumers removed — *PR #657 merged 2026-09-05 (`9ff8da6`), deploy green, old routes 404*
- [ ] Clear the four standing weekly-report anomalies: `backfill-filing-history` for C, MS, WFC, GS; grant deployer SA access to `INTERNAL_JOB_TOKEN`
- [x] Liabilities/cash fallback and persisted accession-specific XBRL first — #697.
- [ ] **D3 accepted; execution pending:** founder creates/seeds the Notable job and reviews one week of output before `NOTABLE_FILINGS_ENABLED` activation per `DEPLOYMENT.md`; homepage findings archive completed #692
- [x] FPI roadmap archive and status block — #692. Residual 6-K classifier and founder backfill remain open.

## Accepted policies — execution and verification pending

- [x] Migration design (guard-only vs ledger) — *ledger, 2026-09-04*
- [ ] **D5 accepted:** obtain the first judged readout, then arm `AI_EVIDENCE_SNAP`; figure-trace and forward-quote remain advisory. The strong-judge credential/readout prerequisite is outstanding.
- [ ] **Execution pending; D4 spend approved:** universe pregeneration, v1→v2 drain and golden-set runs; FMP secret remains founder-owned
- [ ] **D3 accepted:** confirm the Analysis production flag and warm companyfacts before activation; complete Notable job/seed/one-week review prerequisites. Calendar remains off pending the licence decision; Insiders remains off.

## Remaining founder decisions and console actions

- [ ] Alpha Vantage: licence or EDGAR-only
- [ ] Legal: Terms §7e counsel pass; processor DPAs; legal entity / governing law
- [ ] `WAITLIST_MODE` intent; LAUNCH_CHECKLIST founder-only actions (GSC, Bing, apex 307→308, Vercel plan, `NEXT_PUBLIC_EXAMPLE_FILING_ID`)
- [ ] Pro trial timing; delete retired reverse-trial code?
- [ ] `USE_STRUCTURED_OUTPUT`: bake-off or delete
- [ ] GCP console: PITR + deletion protection; uptime/alert policies; Turnstile keys; confirm `REGISTRATION_MODE` and flags via `ops.yml describe-service`

## Deferred (tracked in appendix 06, not scheduled)

SEO phases 2–3; dashboard "later" tier (8-K rows, weekly brief, sparklines, 13F); competitive roadmap
A4/A7/A8; cold-path Phase C; MFA/TOTP; retention purge jobs (policy promise — schedule before public
launch); Turnstile fail-closed; T5 depth ledger; cheaper-model routing flags; waitlist/contact route tests;
`SUMMARY_SELF_VERIFY`; prompt-prefix caching; off-peak cron windows.

## WS-6 step 1 — eval parity and one measured baseline (2026-09-05)

- [x] Audit production/eval configuration and streaming calls; explicitly pin statement-financials parity, restore JPM bank-component ground truth, and test streaming/non-streaming final-result equivalence without touching locked contracts.
- [x] Use two runs for routine CI evaluation, retain hard tolerances, and provide a bounded three-run CI measurement using the existing provider secret; preserve baseline notes and provenance.
- [ ] Prove new tests by mutation and run the exact full backend gate.
- [x] Observe the actual CI runner and regression logs/artifact on the complete parity candidate, investigate any regression, then make one honest full-set three-run baseline pin with preserved notes.
- [ ] Record artifact provenance and independent review; merge/deploy remains with the chief engineer. Later WS-6 measurement/resilience/hygiene/Copilot/arming steps remain separate PRs in that order.

Authoritative evidence: [run 33962580838](https://github.com/neilmac91/EarningsNerd/actions/runs/33962580838)
measured source `f5b46ba96b3023f93554087e431937ed9daba3c4` after #697 deployed. Artifact
`9968531910`, `eval_20260905T111951Z.json`, contains 26 × 3 = 78 unique filing runs,
zero execution errors and hard vetoes; the old-baseline gate passed with zero warnings.
The sole pin records that report's actual harness (judge off), source/golden hashes and measured
statistics; citation fidelity is 0.7012. All 78 requested streaming and yielded 518 previews;
no fallback warning was observed, which does not prove transport never fell back.
The final pin-helper change only rejects vetoed/incomplete gate evidence before overwriting an
existing baseline. Its seven new CLI cases pass; removing result/summary checks causes four/three
real assertion failures. Generation/scorer source is unchanged from the measured commit.
Final full gate and review of the pin commit remain pending. First strong-judge readout remains
unavailable without its credential; this deterministic measurement does not authorize evidence-snap.

## WS-7 implementation — archived

Steps 1–6 are merged (#690/#697). [Completed steps 3–6 and proof](archive/ws7-completeness-2026-09.md).
Founder execution and live data evidence remain unchecked above and in the ledger; #697 deployment is verified.

## WS-10 — configuration and script placement hygiene

- [x] Implementation and current-main local gates complete in PR #696; [archived proof](archive/ws10-hygiene-2026-09.md).
- [x] WS-7 default/docs integrated; 1910-test gate, independent review and CI passed; #696 merged (`0e0e7762`), deployment verified.

## WS-6 step 2 — advisory measurement and weekly judged readout

- [ ] Measure untraceable dollar figures on actual raw v2 sections with explicit numeric-grounding availability; preserve hard gates, aggregate weights and the single parity pin.
- [ ] Add stored audit-snapshot counts with per-family valid/missing/malformed denominators to the operational report and both email formats.
- [ ] Schedule an exact eight-filing, three-repeat strong-judge readout with provenance, complete/error/missing denominators and a bounded validated handoff to the existing report job.
- [ ] Check generator and strong-judge credentials before any model calls; missing credentials mean unavailable and do not constitute the first readout.
- [ ] Prove new tests with mutations, run exact full backend gates, inspect actual CI evaluation and obtain independent review.
- [ ] First actual strong-judge readout remains held for the founder credential; no live weekly email dispatch, evidence-snap activation, or cosmetic baseline pin in this implementation PR.
