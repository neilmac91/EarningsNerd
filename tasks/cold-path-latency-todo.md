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
- [~] **A1** Background precompute. **Mechanism + pilot DONE** (`precompute_service.py`,
      `/internal/jobs/precompute`, `pregenerate_examples` delegates to it; 7 unit tests). **Fleet run
      still GATED** — awaiting owner go on the top-500 cohort + batch concurrency. Filing-scan
      auto-trigger for *new* filings = follow-up.
- [x] **A4** Filings list: default-expand the most recent 3 years that have filings; prefetch the
      latest 10-K's summary on company open (read-only, warms the next click). (`company/[ticker]`)
- [x] **A5** Progressive section reveal. **Backend** (PR #432): stream the extraction, push
      partial-markdown previews; `STREAM_SECTION_REVEAL` flag (default off); identical final output via
      shared `_assemble_structured_summary`; non-streaming fallback. **Frontend**: the filing page
      consumes the `preview` SSE event and replace-renders the growing markdown (final `chunk`
      supersedes). Verified: first paint ~10s vs ~60s (6.4× perceived); flag off ⇒ unchanged.
      **ACTIVATED**: `STREAM_SECTION_REVEAL=true` added to the Cloud Run *service* deploy env in CI
      (re-verified POWL 10-K: 10 preview frames, first content ~6s vs 31.6s final, output complete).
- [x] **A3** In-flight dedup: a process-local registry (`_inflight_generations`) in the SSE pipeline —
      concurrent first-requests for the same `filing_id` join the in-flight generation (wait with
      heartbeats) and serve the persisted result instead of running N redundant generations. Released
      in `finally` (incl. client disconnect). Verified: 3 dedup tests + 698 backend tests pass.

## Output quality (B1-protected, gated work)
- [x] **Baseline re-pinned** from the real full verified-set run (21×3, 0 errors): recall 0.905,
      precision 1.0, coverage 1.0, depth 0.947, stdev 0.082, gate_fail 0.0 (PR #441).
- [x] **Diluted-EPS recall fix** (PR #443). Root-caused the "weakest dimension": the recall misses
      were a measurement artifact — the golden set pinned *basic* EPS while the model correctly
      reports *diluted* EPS (NVDA 2.40 vs 2.39, AMZN 7.29 vs 7.17; BA's run-to-run wobble was the
      same coin-flip). Fix: `GroundTruthFact.alt_values` + scorer accepts basic **OR** diluted
      (recall and precision); enriched 13 golden EPS facts with the diluted alt; `build_golden_set`
      populates it durably (reusing the product's `DURATION_CONCEPTS["eps_diluted"]`). Re-pinned
      from a fresh 21×3 run (0 errors): **recall 0.905→0.963, pass_rate 0.762→0.937, stdev
      0.082→0.066**; gate_fail/precision/coverage unchanged (0.0/1.0/1.0). NVDA/AMZN/BA/AAPL/MSFT
      now 1.0 across all runs. **Residual real gap = BABA/FPI** (per-ADS vs per-share EPS,
      attributable vs consolidated net income).

## Phase B — structural (minimal-infra)
- [x] **B1** Harden `backend/evals` into a pinned baseline + CI regression gate (PRs #435/#441/#443).
      `regression_gate.py` (deterministic per-dimension diff, hard-fail vs warn), `scripts/pin_baseline.py`,
      `baseline_scores.json` (pinned bar, now reflecting the diluted-EPS fix), advisory path-filtered
      `eval-baseline` CI job (inert until owner adds a `DEEPSEEK_API_KEY` Actions secret; NOT in
      deploy-backend `needs:`), RUNBOOK section, unit tests. Gate logic runs free in `backend-tests`.
- [ ] **B2** Filings-list backend cache/refresh for popular tickers.
- [ ] **B3** Section-parse 15s-timeout tail fix for big financial filers (e.g. JPM).

## Forward plan (post-B1, A1 fleet held per owner)
Sequenced by value-to-effort; each a separate PR, gate-protected where it touches generation.
1. [~] **Activate A5** progressive reveal — `STREAM_SECTION_REVEAL=true` in CI service deploy. *(this PR)*
2. [ ] **S1 structured-output bake-off** — flip `USE_STRUCTURED_OUTPUT` off-vs-on through the gate;
       ship + re-pin only if it wins (schema_valid 0→1, no recall/precision/coverage regression).
3. [ ] **B2** filings-list backend cache (original cold-path #1: first company-page load).
4. [ ] **B3** parse-timeout tail for big filers (faster + higher-precision excerpts for JPM-class).
- Parked: **A1 fleet** (owner-held), **BABA/FPI per-ADS** (niche), **arm CI gate** (owner adds secret).

## Phase C — deferred (parked per owner)
Parallel-section generation, async-job decoupling, alt inference provider / `AI_FAST_MODEL`,
bulk `submissions.zip`, CDN mirror.

## Review log
- **A2 (done):** progress log now derives step status from the real streamed `stage`
  (`STAGE_ORDER`) and labels the first step with the actual `filing.filing_type`. Removed the
  fabricated "Vectorizing content for semantic analysis" step (no embedding on the summary path).
  No generation behavior change. Verified: `tsc --noEmit -p tsconfig.ci.json` exit 0; zero errors in
  the changed file. **Merged in PR #429.**
- **A1 mechanism (done, fleet run gated):** `precompute_service.precompute()/precompute_one()` reuse
  the idempotent `generate_summary_background` path; token-gated `POST /internal/jobs/precompute`
  (sync `dry_run` coverage report; real run = 202 + background); `pregenerate_examples` now delegates
  (DRY). `MAX_BATCH=1200` cost guard. 7 unit tests pass; ruff clean.
  Pilot (SQLite, POWL+AAON × 10-K/10-Q): 4/4 generated + persisted; idempotent re-run skipped all
  with **0 new LLM calls**; **$0.011/filing** → top-500 10-K ≈ **$5.56**, ×2 forms ≈ **$11.13**.
  Finding: serial batch ≈ 59s/filing (~16h for 1000) → needs bounded concurrency or multi-night
  spread before the fleet run.
- **A5 backend (done, flag off):** extracted `_assemble_structured_summary` (shared by both paths →
  identical final output); added a streaming early-path in `generate_structured_summary` +
  `_stream_collect`/`_partial_markdown_preview` that emit throttled partial-markdown previews;
  `summarize_filing` threads `stream_cb` with a non-streaming fallback; pipeline drains previews into
  a `preview` SSE event behind `STREAM_SECTION_REVEAL` (default off). Verified: full non-streaming run
  unchanged (status=complete, 4 sections); streaming run AAON 10-K → 9 preview frames, **first paint
  ~9.8s vs 62.4s final (6.4× perceived)**; 695 backend tests pass; 8 new unit tests; ruff clean.
  **Frontend progressive render (consume the `preview` event) = next PR.**
