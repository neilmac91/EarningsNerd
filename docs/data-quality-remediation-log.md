# Data-Quality Remediation — Execution Log

**Spec:** `docs/data-quality-investigation.md` (2026-07-07) · **Executor:** Claude Code session, started 2026-07-07
**Scope executed:** Part-3 interim safeguards · P0-1..P0-5 · P1-6 · P1-8 · P1-9.
**Explicitly NOT executed:** P1-7 (separate approved track) and all P2 items (parked by the spec).

Each phase below is one merged PR (serial; branch `claude/earningsnerd-data-quality-fpg7bz`
reset from `origin/main` between phases). Production operations run through
`.github/workflows/ops.yml` (enum-selected committed operations; WIF auth identical to
`deploy-backend`). Per phase this log records: what changed (mapped to plan items), what was
deployed, which production operations ran (with their outputs), eval results where applicable,
and verification evidence against the spec's exact expected values.

## Hard sequencing gates honoured

1. Ticker repair script runs only AFTER the search-fix deploy is live (verified behaviorally).
2. Facts resync runs only AFTER the registry-change deploy is live.
3. The only P0 eval-baseline re-pin happens in P0-4; P0-2 shipped first.
4. `--dry-run` reviewed against the spec's predictions before any `--apply`.

## Founder pre-agreements (recorded before execution)

- **P0-2 fallback (chosen via AskUserQuestion, 2026-07-07):** if prod runs
  `USE_STATEMENT_FINANCIALS` OFF, ship the neutral-wording badge stopgap (spec safeguard #5) and
  leave the flag/SIC rollout to P1-7 — do not pull it forward.
- **P0-4 fallback (pre-agreed in the spec):** if the eval gate fails past the one-day timebox,
  land (a) alone; defer (b)+(c) one week.

---

## Phase 0 — Ops workflow + detection SQL + prod-state probes

**Status:** in progress
**Plan items:** execution enablement for all "run against prod" steps; interim safeguard #4
(manual detection runbook — first run).

**Changed:**
- `.github/workflows/ops.yml` — enum-operation dispatch workflow (describe-service/jobs,
  detection-sql via cloud-sql-proxy+psql, logs probe, jobs-channel probe, ticker repair
  dry-run/apply, sync-companyfacts with jobs-channel fallback, emergency traffic rollback).
- `ops/detection/*.sql` — committed read-only detection queries: `cash_coverage_gap` (spec P0-3
  step 3, verbatim), `filing_count_anomaly` (P1-6 detection), `sic_null_count`,
  `ticker_corruption_proxy`, `companies_snapshot` (named issuers before/after).
- This log.

**Deployed:** nothing (no `backend/` paths → deploy-backend does not run). PR #585 merged
2026-07-07 (`e6121e1`) after all CI checks green.

**Execution-arm adjustment (recorded):** this session's GitHub tokens have no `actions:write`
scope, so `workflow_dispatch` is not callable from here (403). Added a request-file trigger:
committing `ops/requests/current.json` to the remediation branch runs the same enum-validated
operations; `workflow_dispatch` remains for manual use. Each operation is an auditable commit.

**Probe results (2026-07-07, ops runs #1-#4 on the remediation branch):**
- **`USE_STATEMENT_FINANCIALS = 'true'` in prod** (set out-of-band on the Cloud Run service;
  survives deploys because CI uses `--update-env-vars`). The statement-financials rollout HAS
  happened → P0-2's component-based badge fix is live for banks; the pre-agreed neutral-wording
  stopgap is not load-bearing (ships anyway as belt-and-braces). `INTERNAL_JOB_TOKEN`,
  `RESEND_API_KEY` exist as secret-refs on the service. Serving revision at probe time:
  `earningsnerd-backend-00208-d4m` (rollback anchor).
- **`Company.sic`: NULL for all 442 companies** (`sic_null_count`: 442 total / 0 with sic) —
  the runbook's SIC backfill was NOT run. SIC-band predicate branch stays dormant (by design);
  the flag-ON component path carries the bank badge fix. No SIC backfill in this execution
  (founder pre-agreement; P1-7's territory).
- **Detection "before" snapshots** (prod, 2026-07-07 19:30 UTC):
  - `cash_coverage_gap`: **JPM-PM (last_cash_fy=2018, last_assets_fy=2025)** — the exact
    ASU 2016-18 signature the spec predicts — and **BIIB (no cash facts at all, assets to
    2024)** — the spec's predicted non-financial exposure class. BAC absent because it has no
    `financial_fact` rows yet (never companyfacts-synced); it will be force-synced and verified
    in Phase 5 regardless.
  - `companies_snapshot`: **JPMorgan's live ticker is `JPM-PM`** (id 11, cik 0000019617) —
    corruption confirmed in prod. BAC/WFC/C/GS/MS/BRK-B/GOOGL currently hold their common
    tickers. `exchange`/`sic` empty everywhere.
  - `filing_count_anomaly`: JPM-PM — facts span FY2007–FY2025 with **1** stored 10-K (the
    mega-filer ingestion-cap signature). No other company matches yet.
  - `ticker_corruption_proxy`: exactly 1 preferred-suffix ticker (JPM-PM); 0 duplicate CIKs.
- **Negative WIF probe: non-main refs CAN authenticate.** The ops workflow ran successfully
  from the remediation branch (push-triggered). Posture: WIF trust is repo-scoped, not
  ref-scoped — anyone with push access to any branch can exercise deployer-SA operations.
  Acceptable for a solo-founder repo; noted for the founder (tighten the WIF provider's
  attribute condition to `refs/heads/main` if collaborators are ever added).
- **Jobs channel:** all Cloud Run jobs use `command: ['python']` → the documented
  `jobs execute --args` override works shape-wise. `earningsnerd-filing-digest` carries
  `DATABASE_URL` + `RESEND_API_KEY` + `RESEND_FROM_EMAIL` → chosen as Phase 9's execution
  target. `earningsnerd-backfill-facts` carries `DATABASE_URL` + `USE_STATEMENT_FINANCIALS` →
  Phase 5's resync fallback target. (`earningsnerd-notable-filings` does not exist; skipped
  gracefully, matching ci.yml's tolerance.)
- **`logging.read`: DENIED** for the deployer SA → the safeguard-2 Cloud Run log-based ALERT
  cannot be created/verified from this session. The structured `company_upsert_conflict` line
  ships regardless (Phase 1); recurrence visibility comes from the P1-9 weekly report.
  **Founder action (optional):** grant `roles/logging.viewer` (+ `roles/monitoring.editor` for
  an alert policy) to the deployer SA, or create the log-based alert once in the console.
  Side-effect accepted: Cloud Run *job* stdout is unreadable from here too — hence all
  operation verification is SQL/API-based, and the ticker repair runs on the Actions runner
  (stdout in the workflow log), not as a job.
- **Jobs-channel no-op execute: PERMITTED** (`gcloud run jobs execute earningsnerd-backfill-facts
  --args="-c,print(…)" --wait` created, ran, and completed) → the documented jobs channel works
  end-to-end as Phase 5's fallback and Phase 9's trigger.
- Secrets masking verified in run logs (`DATABASE_URL`/`PGPASSWORD` render as `***`).

**Phase 0 exit criteria: met.** All operational unknowns the later phases depend on are now
recorded facts.

---

## Phase 1 — Interim safeguards 1+2 (miss-path hotfix + conflict logging)

**Status:** in progress
**Plan items:** Part-3 safeguards 1 (CIK-fallback + SAVEPOINT at the three miss-path inserts)
and 2 (structured `company_upsert_conflict` log line).

**Changed:**
- New `app/services/company_resolution.py::resolve_or_create_company_by_cik` — CIK-first
  lookup (padded + stripped forms), SAVEPOINT insert with IntegrityError re-query (template:
  `earnings_alert_service.py:85-96`), `company_upsert_conflict cik=… ticker=… path=…` warning
  on conflict.
- The three blind-insert sites now use it: `routers/companies.py` (`get_company` miss),
  `routers/filings.py` (`get_company_filings` miss), `services/precompute_service.py`
  (`precompute_one` miss). No ticker rewriting here — canonicalization is P0-1 (Phase 4).
- Guardrail tests `tests/integration/test_company_miss_path_cik_fallback.py` (5 tests): the
  three routes reuse the JPM-PM-stored row for /JPM lookups (200, one row, no insert); the
  forced-race path returns the surviving row + emits the structured log line; padded/stripped
  CIK matching.

**Gates:** ruff ✓ bandit ✓ full pytest 1401 passed ✓ (local, pipefail-checked). Pre-merge
adversarial review (3 lenses: txn semantics / HTTP contract / test adequacy): zero confirmed
findings; two test-hygiene minors fixed before merge (teardown hardening, explicit
no-ticker-rewrite assertion).

**Deployed:** PR #586 merged 2026-07-07 (`e6514a6`); `deploy-backend` succeeded (image built,
migrations re-applied, Cloud Run serving, health check green).

**Verification (prod, 2026-07-07 ~20:10 UTC):** `GET /api/companies/JPM` **500 → 200**,
serving `{id: 11, cik: 0000019617, ticker: "JPM-PM"}` with the preferred share's quote
(**$17.24** — the spec's ~$17.29 symptom, live). Exactly the intended interim state: the page
works again; the wrong ticker/quote is P0-1's to fix (Phase 4) and this snapshot is the
"before" for that verification.

**Status: complete.**

---

## Phase 2 — P0-5 honest filings note

**Status:** in progress
**Plan items:** P0-5 / interim safeguard 3 ("ships regardless of everything else") — moved
ahead of the heavier phases per the execution review.

**Changed:** new `frontend/features/filings/components/FilingsHistoryNote.tsx` ("Showing
filings since {oldest filing_date}. Full history on SEC EDGAR →" with the CIK-scoped
browse-edgar link), rendered under the filings year list in `page-client.tsx`
(`oldestFilingDate` derived from the full list, not the active filter). Permanent by design —
after P1-6 only {oldest} moves. Guardrail: `filings-history-note.spec.tsx`.

**Gates:** frontend full gate green (lint, tsc, vitest 347, build).

**Deployed:** PR #587 merged 2026-07-07 (`e01672c`); frontend ships via Vercel (preview build
green pre-merge). Review-bot fixes taken before merge: `parseISO` + invalid-date guard (a
date-only string in `new Date()` renders the previous day for viewers behind UTC) and a
lexicographic oldest-date compare; the EDGAR link params kept per the spec (type=10-K avoids
the structured-note flood on mega-filers).

**Verification:** note rendering pinned by `filings-history-note.spec.tsx` (since-date +
CIK-scoped external link); preview deployment built green. **Deviation:** the planned
both-themes browser eyeball could not run from this environment (headless Chromium cannot
complete TLS through the egress proxy — ERR_CONNECTION_RESET; curl to the same URL is fine).
Risk accepted as near-zero: the note reuses existing text/link tokens verbatim
(`text-text-tertiary-*`, `text-brand-strong` + hover:underline — same pair as FilingViewer).
Founder: one glance at any company page confirms.

**Status: complete.**

---

## Phase 3 — P0-2 badge FI-awareness + join-artifact fix + detection

**Status:** in progress
**Plan items:** P0-2 (A) bank-blind grounding check + (D) join artifacts; the badge
de-escalation from safeguard #5 (founder-chosen; belt-and-braces since prod runs flag-ON);
rule-12 detection (partial-by-SIC SQL + structured log counter).

**Changed:**
- `services/ai/markdown_render.py`: all 8 `"; ".join` sites → true GFM bullets
  (`_append_bullet_group` label + nested items; exec key_points as top-level bullets under the
  prose headline) — parity with the PDF serializer. String-payload guards added (review).
- `services/ai/normalize.py`: the 9th, undeclared join (risk supporting-evidence lists) → " · "
  separator (found by the adversarial review — the artifact class, not just the 8 cited sites).
- New `services/ai/fi_signals.py`: `fi_components_present` + `is_financial_sic` (band pinned
  equal to instance_extractor's by test). Consumed by `xbrl_narrative` NOTE emitter,
  `bank_guards._is_no_total_bank` (semantics unchanged), and `assess_quality`.
  `provenance_service`'s deliberately-independent copy left alone (founder note).
- `summary_generation_service.assess_quality`: keyword-only `sic` param; three-way revenue
  rule (literal OR both-components-ground OR FI-with-unextracted-components → N/A);
  `net_income` unchanged; non-FI byte-identical. Caller passes `company.sic`;
  `summary_quality_partial` log line added (detection).
- `SummaryDisplay.tsx`: `partialBadgeLabel` — sole-grounding-reason renders neutral
  "Partial coverage" (tooltip keeps details). `serverApi.ts` excerpt strips list markers
  (review: hero excerpt would have shown literal "- ").
- `ops/detection/partial_reason_by_sic.sql` (rule 12, same PR).

**Guardrails:** `test_markdown_render_bullets.py` (no `".;"`, no `"; "` runs, bullets per
field, numbers substring-matchable, no orphan labels), `test_assess_quality_bank.py` (6 cases),
`test_fi_predicate_single_source.py` (shared-predicate identity + SIC-band no-drift),
`summary-quality-badge.spec.tsx`. Locked tests untouched and green
(`test_xbrl_narrative_section.py` byte-for-byte, background-generation characterization,
stream contract).

**Review:** adversarial workflow (3 lenses × find→verify). First pass: 6 minors adjudicated —
4 fixed (hero-excerpt list markers in `serverApi.ts`, string-payload char-iteration guards,
the 9th undeclared `"; "` join on risk evidence → " · ", docstring + cross-boundary
breadcrumbs). Verdict-logic lens re-run (an API-500 killed it first pass) surfaced and CONFIRMED
one **major** bug in my own new code: `assess_quality` skipped the top-line grounding check
entirely for a no-total bank (BAC/C/WFC — components tagged, no `revenue` total), so a
hallucinated bank top line still earned `tier=full`. Fixed: the top-line check now evaluates the
component pair whenever a bank has both components extracted, independent of whether a `revenue`
literal exists; the flag-off "no components extracted → N/A" skip is preserved. Added
`test_no_total_bank_components_grounded_is_full` + `..._hallucinated_components_is_partial` (the
untested cell that hid the gap). This is the single most important correctness fix in P0-2 — it
is exactly the majority-bank population the badge protects, and BAC is the Phase-5 spot-check.

**Eval expectation (constraint 3):** zero delta — bullets keep every number
substring-matchable (pinned by test). **Confirmed empirically: the eval-baseline CI job passed
on PR #588** (backend/frontend/e2e/eval all green). No re-pin here; the only P0 re-pin is P0-4's.

**Deployed:** PR #588 merged 2026-07-07 (`3a1910c`); `deploy-backend` running.

**Status: complete.**

---

## Phase 4 — P0-1 ticker integrity (search fix → repair dry-run → apply)

**Status:** in progress
**Plan items:** P0-1 — search-fix + `primary_ticker_for_cik` + miss-path canonical inserts +
the repair script (Part-1 §1). Hard gate 1: repair runs only AFTER this deploy is live.

**Changed:**
- `services/edgar/compat.py`: `primary_ticker_for_cik(cik)` — first file-order entry per CIK
  from the cached tickers dict (SEC lists the common/primary listing first).
- `routers/companies.py` search loop: dedupe by CIK (one response row per company, not per
  listed security); never assign ticker from per-entry `sec_data`; new rows get the primary;
  existing rows update ticker only TO the primary (permits renames, forbids preferred
  downgrades); `begin_nested()` + IntegrityError re-query around the flush/commit (race guard).
- The three miss-path inserts (companies/filings/precompute) now pass the primary ticker on
  insert.
- New `backend/scripts/repair_ticker_by_cik.py` — `--dry-run` default / `--apply`; primary
  per CIK from the SEC file via the edgar layer; reports old→new, not-in-file, collisions;
  padded+stripped CIK matching.
- Frontend: dropdown duplicate-key fix falls out of one-row-per-CIK (the `router.replace`
  canonicalization was dropped — with the repair, stored tickers become canonical, so a stale
  /company/JPM-PM URL resolves via the Phase-1 CIK path and no redirect is needed).

**Guardrails:** `test_company_search_ticker_integrity.py` (q="jpm"→1 row, primary; q="goog"→
GOOGL not GOOGN; repeat-search no mutation; corrupted-row upgraded; first-contact single
insert; /JPM-PM→canonical; get_company self-heal; primary-map memoized; IntegrityError→200;
primary=first-file-order), `test_repair_ticker_by_cik.py` (first-entry map; padded+stripped
match; dry-run writes nothing; apply repairs only mismatches).

**Adversarial review (5 agents, opus-4-8, find→verify) — 2 CONFIRMED major, both fixed:**
1. **Efficiency:** `primary_ticker_for_cik` re-scanned the ~10k-entry ticker dict once per CIK
   on the hot `/search` path (~16ms/req worst case, blocking the event loop). Fixed with a
   memoized CIK→primary map (`_get_primary_ticker_map`, rebuilt only when the tickers cache
   refreshes); each per-CIK lookup is now O(1). Guarded by `test_primary_ticker_map_is_memoized`.
2. **Self-heal gap:** `get_company` (the price endpoint) resolved a corrupted JPM-PM row by CIK
   but returned it unchanged → served the preferred's ~$17 quote until the repair ran. Added a
   `canonical_ticker` param to `resolve_or_create_company_by_cik` that reconciles a found row's
   ticker to the primary; all three resolve paths (companies/filings/precompute) pass it. So no
   endpoint serves a quote under a stale ticker post-deploy, and any row the repair misses heals
   on first touch. (This updated the Phase-1 "no rewrite" test assertion to the new self-heal.)

**Prod prediction (verified live against `company_tickers.json`, 2026-07-07):** primary = the
common ticker for all 8 named issuers (JPM/BAC/WFC/C/GS/MS/GOOGL/BRK-B); combined with the
Phase-0 snapshot (only JPM-PM corrupted), the repair dry-run should report **exactly 1 change
(JPM-PM→JPM), 0 collisions, 0 not-in-file** among the named set.

**Deploy / prod operations:** _pending merge → repair dry-run → compare vs the prediction above
→ apply → verify JPM ~$300 quote, single search row, sitemap, /JPM-PM canonical._

---

## Phase 5 — P0-3 cash registry + resync

**Status:** pending

---

## Phase 6 — P0-4 bank prompt carve-out (eval-gated)

**Status:** pending

---

## Phase 7 — P1-6 historical filings backfill + filters

**Status:** pending

---

## Phase 8 — P1-8 chart missing-data + axis fixes

**Status:** pending

---

## Phase 9 — P1-9 weekly data-quality report

**Status:** pending

---

## Open items / paused / deferred

_(filled at wrap-up: anything paused on, anything deferred, assumptions that didn't hold,
founder notes for out-of-scope observations.)_
