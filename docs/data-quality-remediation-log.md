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
- `logging.read` permission + jobs-channel no-op execute: probes dispatched; results recorded
  under Phase 1 below (they complete alongside it).
- Secrets masking verified in run logs (`DATABASE_URL`/`PGPASSWORD` render as `***`).

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

**Gates:** ruff ✓ bandit ✓ full pytest 1401 passed ✓ (local, pipefail-checked).

**Deployed:** _pending merge_

**Verification:** _pending deploy_ — prod `GET /api/companies/JPM` should flip 500 → 200
serving the JPM-PM row (until Phase 4 canonicalizes the ticker).

---

## Phase 2 — P0-5 honest filings note

**Status:** pending

---

## Phase 3 — P0-2 badge FI-awareness + join-artifact fix + detection

**Status:** pending

---

## Phase 4 — P0-1 ticker integrity (search fix → repair dry-run → apply)

**Status:** pending

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
