# Tracked eval baselines

Per-filing eval reports that a pinned `baseline_scores.json` was built from, kept in git so a
model or prompt change can be compared filing-by-filing (`python -m evals.compare_reports`).
`evals/reports/` stays ignored: only reports that back a pin, or a decision recorded in an ADR,
belong here.

| Report | Model | Runs | Source SHA | Provenance |
|---|---|---|---|---|
| `eval_20260905T111951Z.json` | `deepseek-v4-pro` (judge off) | 3 × 26 verified filings | `f5b46ba9` | GitHub Actions run 33962580838, artifact 9968531910 (`eval-report-33962580838`, zip sha256 `aa525d87…e09d`), downloaded 2026-09-10 before its 2026-09-19 expiry. Backs the `baseline_scores.json` pin of 2026-09-05. Predates per-attempt provider usage in the runner, so it has no token counts. |
| `eval_20260910T153541Z.json` | `deepseek-flash` (judge off) | 3 × 26 | `a811faf` | Local run 10 Sept 2026 with the CI eval env (W3 of the cutover plan). Backs the `baseline_scores.json` re-pin of 2026-09-10 (ADR-0008). Tracked copy omits the bulky grounding fields (`grounding_excerpt`, `preview_frames`, `xbrl_grounding`, `source_provenance`, `coverage_inventory`); scores, payloads, raw sections and `provider_usage` are intact. |
| `eval_20260910T154318Z.json` | `deepseek-v4-pro` (judge off) | 1 × 26 | `f134983` | Same-code Pro token-count arm run 10 Sept 2026, minutes before the Flash run and days before Pro's retirement; the paired reference for the output-token ratio (Flash/Pro ×1.42). Same tracked-copy trimming. |
