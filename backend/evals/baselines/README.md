# Tracked eval baselines

Per-filing eval reports that a pinned `baseline_scores.json` was built from, kept in git so a
model or prompt change can be compared filing-by-filing (`python -m evals.compare_reports`).
`evals/reports/` stays ignored: only reports that back a pin, or a decision recorded in an ADR,
belong here.

| Report | Model | Runs | Source SHA | Provenance |
|---|---|---|---|---|
| `eval_20260905T111951Z.json` | `deepseek-v4-pro` (judge off) | 3 × 26 verified filings | `f5b46ba9` | GitHub Actions run 33962580838, artifact 9968531910 (`eval-report-33962580838`, zip sha256 `aa525d87…e09d`), downloaded 2026-09-10 before its 2026-09-19 expiry. Backs the `baseline_scores.json` pin of 2026-09-05. Predates per-attempt provider usage in the runner, so it has no token counts. |
