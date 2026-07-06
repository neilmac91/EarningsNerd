# Gate every AI/prompt/model change on the eval regression gate — and re-pin the baseline in the same PR

Date: 2026-07-06   Area: ops

**Context**: `backend/evals/` pins production summary quality as `baseline_scores.json`
(26-filing verified golden set) with a deterministic per-dimension regression gate. The
`eval-baseline` CI job is ARMED (a `DEEPSEEK_API_KEY` Actions secret exists) and runs the
real pipeline on AI-relevant PRs (~$0.15–0.30, ~6 min), diffing against the pinned bar —
this is what cleared the S1 flip when a prod traffic soak had nothing to observe
(zero users). Hard dimensions: gate_fail_rate (never regresses), numeric precision,
coverage, recall.

**Rule**: Any change to prompts, models, provider flags, or extraction that feeds the
model runs the gate before merge (CI does it automatically on path-filtered PRs; use
`workflow_dispatch` for the authoritative full set). When you INTENTIONALLY move the bar,
re-pin via `scripts/pin_baseline.py` in the same PR. Copilot / analysis-narrative changes
have their own gates — see `backend/evals/RUNBOOK.md` (citation-fidelity audit, `--runs 3`
aggregates, never a single draw).

**Evidence**: `backend/evals/RUNBOOK.md`; PR #565's recorded eval evidence (full-set PASS
on the exact merge candidate); ADR-0006 (re-pin requirement on provider changes).
