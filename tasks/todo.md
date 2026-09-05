# Remediation plan — from the September 2026 engineering audit

## Wave 3 — GPT-6 Astra session (2026-09)

The chief engineer reviewed #705 and the standalone writeup on 2026-09-05: sound, with eleven
discrepancies (none invalidating the handover). The ordered plan, founder prerequisites and the
per-item gates live in [`handover-wave3-2026-09.md`](handover-wave3-2026-09.md); non-Claude
operating directives live in the root `AGENTS.md`. Work items (engineering unless marked founder):

- [x] W3-0 Additional #705 tail verification: 13 task docs, 43 links valid, 52 earlier archives and original §7/ledger preserved. Final manual-reviewed `34350292` tree equals `eddcfbb7`; only the GitHub bot stopped at `c660e9a1`.
- [x] W3-0 documentation correction: #707 merged `a7ad8f85` after three reviews and link/preservation checks; #706 history, agent count, refresh cause, environment assumptions and dependency evidence corrected.
- [x] W3-1 `ops.yml` exposes revision and pregenerate flags; #708 merged `6414e5bd`, actual run 33996220468 verified revision 00270-4k6 at 100% and matched #704 image/config. Service calendar=true differs from its false default; founder approved preserving this override.
- [ ] W3-2 Pin every prod guard flag explicitly in `ci.yml` (service + pregenerate job) with a bidirectional gate; pin `AI_FALLBACK_*` empty in all eval workflows with gates and pin-tool refusal; structural fail-loud gate for scheduled workflows
- [ ] W3-3 Universe refresh: founder supplied `FMP_API_KEY` in GitHub `Production` (metadata verified); after W3-2 binding/deployment, engineering dispatches, reviews the draft auto-PR, merges and closes any failure issue — before the 2026-10-01 cron / 2026-10-16 age gate
- [ ] W3-4 Daily production smoke workflow with a failure issue; one green and one deliberate red dispatch
- [ ] W3-5 Rewrite the seven engineering agent files to the real stack; grep gate with frozen allowlist
- [ ] W3-6 Replace `python-jose` with PyJWT (ecdsa advisory); locked auth contract test byte-identical; two non-locked test edits pre-approved 2026-09-05
- [ ] W3-7 **(founder)** first strong-judge readout → engineering reports the wrong-snap rate, pauses for the arm decision → arm `AI_EVIDENCE_SNAP` + listed re-pin → **(founder)** drain
- [ ] W3-8 Golden breadth (REIT/utility/insurer/small-cap, BRK.B) with its own re-pin; then the 6-K pre-classifier + 6-K scorer + goldens
- [ ] W3-9 Historical reconciliation-flag audit/repair script (dry-run default) → **(founder)** executes
- [ ] W3-10 **(founder)** Notable job + seed + one full week → flag PR; **(founder)** Analysis Vercel value + warm-up → `vercel.json` PR
- [ ] D8 **(founder OK)** delete the two stale remote branches with no PR

## W3-2 implementation — production parity (active)

Owner: AI engineer (plan_gates). Root owns GitHub publication, actual CI, merge and deployment.
Entry evidence: W3-1 run 33996220468/job 101387131600; source image #704/123f99e.
Founder correction: preserve service `CALENDAR_INDEX_FILTER_ENABLED=true` as an intentional
production override, pregenerate=false, Settings default=false. Both fallback fields must be
empty for new pins. Founder provided `FMP_API_KEY` in the GitHub `Production` environment;
bind the existing refresh job to that environment without reading or changing the secret.
Routine required CI evaluations are authorized; extra sweeps and strong-judge dispatch remain held.

- [x] Implement explicit service/job pins and three gate families: visibility/defaults/parity,
  measured fallback provenance and pin refusal, scheduled failure notification structure.
- [x] Preserve serving-revision/traffic and distinct job observation through executable offline
  ops renderer tests; extend existing eval tests without adding duplicate rules.
- [x] Wire refresh to `Production`; correct owning RUNBOOK/config/deployment/dark-surface/handover
  docs, including the founder-approved calendar exception and current entry evidence.
  Documentation source and local verification are complete; deployment remains pending.
- [x] Commit source; run one intended mutation proof per rule, restore exactly, run focused
  workflow gates and exact-runtime full backend gate. Locked tests and sole baseline stay unchanged.
  Local gate at `6a0e7174`: 105 exact pins, Ruff/Bandit clean, 2381 passed, 2 deselected,
  72 warnings (52.19s); 11 intended mutation proofs restored. Initial cache-path collection
  failures are retained and excluded; their four corrected reruns fail the intended assertions.
- [ ] Root: independent reviews, publish draft, inspect actual serialized CI evaluations, merge,
  verify deployment and effective pins. No refresh or judged-readout dispatch in this PR.

## WS-10 verified engineering handover — final synchronization

Documentation-stage checkboxes below record the 2026-09-05 pre-merge source checkpoint
`177f9ff4`. [PR #705](https://github.com/neilmac91/EarningsNerd/pull/705) is authoritative for
subsequent review, CI and merge outcomes; unchecked items do not assert those later results failed.

Verified backend checkpoint: #704 (`123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`).
Its deployment is healthy. Original handover §7 is not complete: the first actual strong-judge
readout, dependent activation and founder production operations still need evidence.

- [x] Knowledge Curator (plan_rules): synchronize the active handover, ledger, briefs, todo,
  dark-surface and launch checklists with observed merges, gates and deployments. Attribute
  independently merged #673 separately; preserve accepted D1–D8 and every outstanding boundary.
- [x] Knowledge Curator: archive finished implementation plans and the exact earlier ledger;
  preserve existing archives and the original definition of done verbatim. Keep mixed-stage
  readout, broader coverage and founder residuals active rather than marking them completed.
- [x] Chief engineer: verify archive bytes, local links/anchors, exact commit references and
  documentation-only scope. Root, plan_correctness and plan_gates independently review the
  final documentation; serious findings require two refuters before correction. *Done in #705 (`eddcfbb7`).*
- [x] Chief engineer: inspect required CI, merge with the freshly read head, and publish a
  standalone engineering handover with the evidence and a single founder action list. Pause
  the hourly check-in when no authorized work remains in flight. *Done in #705 (`eddcfbb7`); the
  handover was reviewed 2026-09-05 and its findings are tracked in wave 3 above.*

This stage changes only task documentation. The owning evaluation RUNBOOK was corrected in
#704. No backend path, feature flag, threshold, baseline, job, secret or production data changes.

## Prospective reporting-date wiring — archived

- [x] #704 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws7-period-wiring-2026-09.md).

## Filing-scoped Copilot — archived

- [x] #703 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-copilot-2026-09.md).

## Filing-only input and recovery hygiene — archived

- [x] #702 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-hygiene-2026-09.md).

Source: `docs/ENGINEERING_AUDIT_2026-09.md` (synthesis) + `docs/audit-2026-09/` (six workstream
appendices with file:line evidence). Lens: invite-only beta, product quality wins ties.
Each phase is one or a few reviewed PRs. Engineering merges are authorized for the chief
engineer; items marked **(founder)** still require the founder.

## Wave 2 execution — 2026-09-05

Owner: chief engineer (Codex); founder has authorized engineering merges and deployments.
Accepted D1–D8 remain in force. Existing unchecked decision rows below are historical tracking,
not requests to revisit accepted decisions. Founder-only actions remain founder-only.

Verified backend/code checkpoint #704: `123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`.
Deployment 33988401306: applied=0 skipped=34, revision `00270-4k6` at 100%, healthy.
The [ledger](wave2-ledger-2026-09.md) records all accepted code/actual gates; last verified frontend
remains #697. #673 was externally merged and preserved, not authored or merged by this task.
#684 closed as integrated by #701; #685 merged; #686 split/closed by #694/#695.
No usable strong-judge credential or actual first readout was available, so D5 remains held.
The unavailable Claude Workflow runtime was replaced by three independent Codex review lenses
and two refuters per serious finding; absent verifier output never counted as clearance.

- [x] Chief engineer: execution plan merged #689 (`47d65a2c`), reviewed and CI green.
- [x] Backend Developer + Database Specialist: WS-7 steps 1–2 merged #690 (`99e91ba7`); graduate statement
  financials default, prepare SIC backfill instructions, implement distinctive job heartbeat
  storage with a new lock-safe migration, instrument every job, report coverage/stubs/age/last success.
- [x] Chief engineer: backend deployments through #704 serialized and independently verified; retain this prerequisite for every future backend merge.
- [ ] Founder: trigger SIC backfill; supply observed completion before declaring SIC data backfilled.
- [x] Backend Developer: WS-7 remaining code steps merged #697 (`c925cfa8`): 10-Q periods/unit assertions and
  reconciliation labels; amendments/supersession/Change Report; persisted XBRL first and missing
  balance-sheet facts; FPI + 10-Q pregeneration and universe Company seeding preparation.
- [x] AI Engineer: parity and sole honest pin merged #698 (`d696f408`), deployed with healthy detailed health.
  Statement env, JPM G5 components, production streaming and safe baseline provenance are verified.
- [x] AI Engineer: measurement code merged #700 (`80314db6`): WARN figure-trace dimension,
  persisted audit counters and bounded weekly strong-judge workflow/readout handoff; deployed healthy.
- [ ] AI Engineer / founder credential boundary: obtain the first actual weekly strong-judge readout.
  An unavailable artifact and routine judge-off regression runs do not satisfy this prerequisite.
- [x] AI Engineer: resilience #701 integrated #684, optional real fallback, bounded retries, actual usage/model telemetry and missing-grounding protection; full backend and complete actual eval gates passed.
- [x] AI Engineer: #702 filing-only AST/context hygiene; #703 scoped/native-currency Copilot with six verified accessions/five issuers and three actual draws each. Latest #704 18/18 accepted; uncited-answer coverage remains advisory.
- [ ] Chief engineer: arm AI_EVIDENCE_SNAP in ci.yml only after first judged readout; founder triggers drain.
- [x] Frontend Developer: sitemap freshness + /terms + SEO correction merged #693 (`157e6a39`).
- [x] Frontend Developer: locate boundary and regression/mutation proof merged #691 (`a2c7fa70`).
- [x] Frontend Developer: #686 split/closed through #694 (`6e169de8`) and #695 (`919aa862`);
  full lint/typecheck/vitest/build and Playwright with no backend for each candidate.
- [x] Security/Backend Developer: #685 compatibility/backend gate and verified deployment (`5cb23b8a`).
- [x] Backend + Frontend Developers: WS-9 preparation merged #692 (`60d8015e`); activation remains held;
  Analysis requires confirmed Vercel value + warmed companyfacts; Notable requires founder-created
  job, seed and a week of review before repository flag flip. Calendar and Insiders stay off.
- [x] Owning PRs corrected migration/provider/report/eval/config docs and script placement; FPI plans archived with residuals. Final active-task synchronization and its review/CI/merge are tracked at the top.
- [ ] Founder: pregeneration off-peak only after WS-7 prerequisites; console/secrets/licence actions
  remain as listed in handover §6, with exact instructions in the relevant PR.
- [ ] Chief engineer: finish final docs review/CI/merge and standalone handover, then pause the hourly quiet check-in when no authorized work remains in flight. Report original §7 as incomplete; do not wait for founder-held operations to claim engineering handover.

Every implementation PR is draft immediately, uses a worktree under `.claude/worktrees/`,
and includes exact gate tails and mutation proofs. Locked contracts, migration allow-lists,
and AI baseline protections remain unchanged unless explicitly permitted by the mandate.

## Resilience and complete-report gate — archived

- [x] #701 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-resilience-2026-09.md).

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
- [x] Dependabot closes: #629 and #570 closed 2026-09-04; `typescript` major-ignore landed in #674; #662–#670 closed as superseded by #674 and #672 closed as superseded by #679 + #680; #659 closed so Dependabot re-creates the remaining 15 minors against Next 16.3.4 / Node 22 — *2026-09-05*; the fresh #686 group appeared and was resolved by #694/#695
- [x] #684 OpenAI 3.7 integrated and closed through #701 resilience/native SDK/full actual eval gates. #685/#683 merged; #686 superseded by #694/#695.
- [x] Split #672: non-edgartools bumps (pandas 3.0.5, fastapi, stripe, posthog, …) — *PR #679 merged 2026-09-05 (`fbbccc5`)*; edgartools 5.40.1→5.55.0 alone through the eval gate — *PR #680 merged (`083247d`, regression gate PASS, 0 warnings)*; #672 closed
- [x] Next.js 16.3.4 (+ transitive security patches, `npm audit --omit=dev` 10 → 0) — *PR #674 merged 2026-09-05 (`2f2e48d`); Vercel production deployment completed; `::highlight` lives in a constructed stylesheet; `next build` typechecks `tsconfig.ci.json`*
- [x] Dependency-audit gates in CI (advisory): `pip-audit -r backend/requirements.txt`, `npm audit --omit=dev --audit-level=high` — *PR #674*; cryptography 50 shipped #685. Audit posture remains advisory; unresolved audit-chain/ecdsa findings require separate review before any blocking transition.
- [ ] Backups: PITR + deletion protection on `earningsnerd-db`; monthly export to lifecycle-managed GCS; one-page rehearsed restore runbook **(founder: console)**
- [x] Universe refresh: FMP stable API first, loud partial-list abort, 100-day age gate — *PR #655 merged 2026-09-05 (`49dd399`), deploy green*; first scheduled run needs `FMP_API_KEY` **(founder: secret)**
- [x] Pricing page SSR (`useSearchParams` → Suspense-scoped child) + Product/Offer JSON-LD; contact meta-description entity; noindex auth pages — *PR #660 merged 2026-09-05*
- [x] Node 20 → 22.23.2 (`.nvmrc`, `engines`, CI ×3, lockstep gate `nodeVersionLockstep.spec.ts`) — *PR #674*; **(founder)** set the Vercel project Node.js Version to 22 so the dashboard matches the `engines.node` override that already governs the build
- [x] Quick wins: `ops.yml` push trigger removed + `cloud-sql-proxy` sha256 pinned (*#656*); `hot_filings.py` and the trending refresh route deleted outright (*#657*, so the admin-token compare and rate limit are moot)
- [x] Drop `"log"` from client Sentry console levels — *PR #660 merged 2026-09-05*
- [x] Rule-8 gate: env-access allow-list test — *PR #661 merged 2026-09-05 (`41abb26`), deploy green*

## Phase 2 — Priority 2: summary fidelity measurement, then arm the guards (≈7 engineer-days)

- [x] Add `mean_untraceable_dollar_figures` as a measured absolute WARN dimension — #700. The parity pin has no reference for it; no invented zero baseline or new hard floor.
- [x] #700 implemented the fixed 8 × 3 weekly strong-judge workflow and report receiver; judge remains off in routine PR CI.
- [ ] First actual strong-judge readout: founder credential/execution required; workflow also sends the report email.
- [x] Roll the five audit counters into the weekly data-quality report from persisted `raw_summary` audits — #700, with separate valid/missing/malformed denominators.
- [ ] Arm `AI_EVIDENCE_SNAP` only after the first judged readout (D5 accepted); figure-trace and forward-quote remain advisory. Strong-judge credential/readout currently unavailable
- [x] #701 retry/fallback: delete the dead Gemini chain in `openai_service.py`; bounded backoff on the primary; env-configured `AI_FALLBACK_BASE_URL`/`AI_FALLBACK_MODEL`; fix the retry unit test to use real names
- [x] #701 per-summary telemetry: log `usage` and `response.model`; surface on `/metrics`
- [x] Eval ↔ prod parity, restored JPM G5 components, actual production streaming, routine two-run gate and sole three-run baseline pin — #698.
- [x] #703 Copilot on verified live-source FPI filings: currency directive (never bare `$` for CNY/TWD/EUR); scope `_query_fact` to the filing being viewed (period from the filing, not `is_latest` company-wide); six verified accessions/five issuers, three actual draws each; older unverified entries remain pending
- [ ] Golden-set breadth: 6-K entries, one REIT/utility/insurer, small caps **(D4 spend approved; execution pending)**
- [x] Reading surface on the filing page: distinct risk headings, mobile section jump-nav, skip-to-content + live region, company-name casing — *PRs #671 + #676 merged 2026-09-05, casing verified live*
- [x] #702 section-recovery grounding: build context from labelled excerpt sections (~30k cap) instead of raw HTML with a 6,000-char cap
- [x] #702 deleted the latent `previous_filings` prompt path + AST pin (rule 2 hygiene)
- [ ] **D4 spend approved; founder execution pending:** drain cached v1 summaries → v2 via admin `refresh-stale` (~$0.05/filing), after D5's judged-readout and evidence-snap prerequisites
- [x] Owning #698–#704 PRs corrected RUNBOOK status, quality-plan headers, façade/provider and DATA_COMPLIANCE processor descriptions; historical quality-plan bodies preserved.

## Phase 3 — Priority 3: coverage and data integrity for the beta universe (≈8 engineer-days)

- [ ] **D4 spend approved; founder execution pending (~$25–50 one-time):** universe-wide pregeneration, latest 10-K + 10-Q for the 515-name universe in batches via `precompute`; weekly 10-Q and Company seed tooling merged #697; founder seed/SIC enrichment and off-peak generation still pending (237 missing rows was the audit snapshot)
- [x] Weekly coverage/stub/universe-age/job-heartbeat report implementation — #690. Live report/backfill evidence remains required.
- [ ] **(founder)** Execute SIC backfill and retain completion/report evidence. Code default True shipped #690; pregenerate FPI env shipped #697; neither proves data was backfilled.
- [x] Amendments: list/ingest 10-K/A and 10-Q/A; supersession and Change Report — #697; existing rows link on refresh/backfill.
- [x] Fiscal periods, unit/decimals assertions and reconciliation UI/exports — #697.
- [x] #704 wires actual ORM reporting date into prospective reconciliation; existing-identity skips/cross-check policy preserved.
- [ ] Engineering: design an explicit historical flag audit/repair capability before founder production repair. Ordinary backfill or freshness `--force` does not re-reconcile existing identities.
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
- [ ] GCP console: PITR + deletion protection; uptime/alert policies; Turnstile keys; confirm effective `REGISTRATION_MODE` in the console (`ops.yml describe-service` withholds its value); inspect other permitted flags

## Deferred (tracked in appendix 06, not scheduled)

SEO phases 2–3; dashboard "later" tier (8-K rows, weekly brief, sparklines, 13F); competitive roadmap
A4/A7/A8; cold-path Phase C; MFA/TOTP; retention purge jobs (policy promise — schedule before public
launch); Turnstile fail-closed; T5 depth ledger; cheaper-model routing flags; waitlist/contact route tests;
`SUMMARY_SELF_VERIFY`; prompt-prefix caching; off-peak cron windows.

## Parity and the sole measured baseline — archived

- [x] #698 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-parity-2026-09.md).

## WS-7 implementation — archived

Steps 1–6 are merged (#690/#697). [Completed steps 3–6 and proof](archive/ws7-completeness-2026-09.md).
Founder execution and live data evidence remain unchecked above and in the ledger; #697 deployment is verified.

## WS-10 — configuration and script placement hygiene

- [x] Implementation and current-main local gates complete in PR #696; [archived proof](archive/ws10-hygiene-2026-09.md).
- [x] WS-7 default/docs integrated; 1910-test gate, independent review and CI passed; #696 merged (`0e0e7762`), deployment verified.

## Measurement implementation — archived

- [x] #700 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-measurement-implementation-2026-09.md).
