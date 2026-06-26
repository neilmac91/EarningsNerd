# Cold-Path Latency — Implementation Tracker

Branch: `claude/earningsnerd-cold-path-latency-6imswg`
(Separate from `tasks/todo.md`, which tracks the unrelated closed-beta roadmap.)

## Approved roadmap (Phase 3 decisions baked in)
- Precompute scope: **broad (~top-500 / S&P-500 + new filings + watched)**.
- Cold-path approach: **perceived + first-content fast, NO mega-call restructuring** (zero quality risk).
- Infra: **minimal — reuse single Cloud Run + Cloud Scheduler + `/internal/jobs`** (no new queue).
- Model: **stay on `deepseek-v4-pro`** (no provider/model change).

## 🚦 HARD GATE (owner instruction)
> Build the A1 precompute mechanism and validate on a **tiny local pilot**, but **do NOT run or
> enable generation across the 500+/S&P-500 fleet**. The bulk run stays gated until the owner
> reviews the pilot + a real cost/coverage projection and explicitly approves.

## Measured baseline (Phase-1 profiling — the bar to protect)
- Cold 10-K analysis ≈ 36–48s; 10-Q ≈ 27s. **LLM is 84–90%** of it (output-token bound, ~115 tok/s,
  ~3.7–4.9K output tokens for a 10-K). Upstream (fetch+parse+xbrl, parallel) ≈ 3–7s. Filings list ≈ 3–5s.
- Quality baseline: numeric_accuracy 0.92, precision 1.00, coverage 1.00, depth 0.83, 0 gate-fails;
  Claude-judge 4.0–4.5/5. Fragile dimension = cross-section numeric reconciliation.

## Phase A — quick wins
- [x] **A2** Wire summary progress to real backend stages; fix the "10-Q" mislabel; drop the false
      "vectorizing/semantic analysis" step. (`frontend/app/filing/[id]/page-client.tsx`)
- [ ] **A1** Background precompute mechanism (idempotent generator + `/internal/jobs` trigger +
      filing-scan hook + sweep script). **← stop at the gate before the 500+ run.**
- [ ] **A4** Filings list: 3-year default + prefetch latest 10-K on company open.
- [ ] **A5** Stream the existing single call's output → progressive section reveal (same call/output).
- [ ] **A3** In-flight dedup for concurrent same-`filing_id` requests.

## Phase B — structural (minimal-infra)
- [ ] **B1** Harden `backend/evals` into a pinned baseline + CI regression gate.
- [ ] **B2** Filings-list backend cache/refresh for popular tickers.
- [ ] **B3** Section-parse 15s-timeout tail fix for big financial filers (e.g. JPM).

## Phase C — deferred (parked per owner)
Parallel-section generation, async-job decoupling, alt inference provider / `AI_FAST_MODEL`,
bulk `submissions.zip`, CDN mirror.

## Review log
- **A2 (done):** progress log now derives step status from the real streamed `stage`
  (`STAGE_ORDER`) and labels the first step with the actual `filing.filing_type`. Removed the
  fabricated "Vectorizing content for semantic analysis" step (no embedding on the summary path).
  No generation behavior change. Verified: `tsc --noEmit -p tsconfig.ci.json` exit 0; zero errors in
  the changed file.
