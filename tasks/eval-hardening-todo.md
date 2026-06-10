# Eval Hardening — Artifacts 1-3 into backend/evals/

Layer the qualitative + gating + consistency dimensions onto the shipped
deterministic harness so it's ready to run as the one-time adoption gate for
`USE_STRUCTURED_OUTPUT` / `AI_QUALITY_GATE` / `AI_DEFAULT_MODEL`.

## Plan

- [x] **Artifact 1 — hard gates (deterministic veto).** `RubricScore` now carries
      `numeric_precision`, `gate_failures`, and a `passed_gates` veto property.
  - [x] G1 numeric fidelity: `score_numeric_precision` catches a labeled field
        that contradicts ground truth (precision, closing the recall-only gap).
  - [x] G4 output hygiene: `detect_hygiene_violations` flags leaked notices +
        placeholder filler.
  - [x] (G2/G3 → judge-side, since they need the source.)
- [x] **Artifact 2 — LLM judge (secondary).** `evals/judge.py`: pure
      `build_judge_messages` + `parse_judge_response` + lazy `judge_summary`.
      Off by default; gate failures force FAIL even if the model says PASS.
- [x] **Artifact 3 — consistency.** `runner.py --runs N` → `pass_rate` +
      `aggregate_stdev`; ranked by pass_rate; `--judge` / `--pass-threshold`
      flags. Backward compatible (default N=1).
- [x] Updated `README.md`: precision, hard gates, consistency, judge, and the
      upgraded adoption rule (tied to the AI_* flags).
- [x] Tests (offline): 26 passing across scorers / judge / consistency.

## Review
Layered the qualitative + gating + consistency dimensions onto the shipped
deterministic harness without rebuilding it. Aggregate weights unchanged; hard
gates are a separate veto. Judge needs anthropic SDK + key (can't run in
sandbox) so only its pure parts are unit-tested. Harness is now ready to run as
the one-time adoption gate for `USE_STRUCTURED_OUTPUT` / `AI_QUALITY_GATE` /
`AI_DEFAULT_MODEL`. Next (operator, needs network + keys): expand/verify the
golden set, baseline, then bake off.

## Notes
- Keep aggregate weights (0.30/0.45/0.25) unchanged — gates are a *separate*
  veto, matching Artifact 1's "PASS = all gates pass AND score ≥ threshold."
- Judge needs anthropic SDK + keys (kept out of core requirements) → lazy import,
  optional flag; cannot be exercised in this sandbox, so unit-test its pure parts.
