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

**Deployed:** nothing (no `backend/` paths → deploy-backend does not run).

**Probe results (recorded after merge):**
- `USE_STATEMENT_FINANCIALS` live state: _pending_
- `Company.sic` population: _pending_
- Detection SQL "before" snapshots: _pending_
- `logging.read` permission (safeguard-2 alerting feasibility): _pending_
- Jobs-channel args-override probe: _pending_
- Negative WIF probe (dispatch from non-main ref): _pending_

---

## Phase 1 — Interim safeguards 1+2 (miss-path hotfix + conflict logging)

**Status:** pending

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
