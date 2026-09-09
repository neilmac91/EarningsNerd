# Docs evaluation scope incident — retrospective correction, 2026-09-09

Read-only review of all ten CI runs returned for `codex/wave3-quality-execution`, PR #783, from 2026-09-08 22:11 UTC through 2026-09-09 00:35 UTC. GitHub run metadata and complete downloaded logs are retained in `work/docs-eval-incident/`; `summary.json` contains exact scope, skip, cancellation, error and gate line references. This is an appended correction, not a replacement for earlier ledger records. No provider call, billing access, account action or repository write was performed during this investigation.

The documentation branch unexpectedly launched seven evaluations. Logs establish 343 recorded primary summary call outcomes: 196 successful DeepSeek generations and 147 HTTP 402 failures. Three earlier CI runs genuinely skipped evaluation. The canceled run recorded 31 successful calls before cancellation; an unlogged in-flight request remains possible. These are recorded outcomes, not a certified count of all provider requests or charges.

| CI run (UTC start) | GitHub conclusion | Observed evaluation | Success / 402 | Known total tokens |
|---|---|---|---:|---:|
| [34284624378](https://github.com/neilmac91/EarningsNerd/actions/runs/34284624378) (2026-09-08T22:11:44Z) | success | Scope skipped | 0 / 0 | Unavailable / not exercised |
| [34285864127](https://github.com/neilmac91/EarningsNerd/actions/runs/34285864127) (2026-09-08T22:25:52Z) | success | Scope skipped | 0 / 0 | Unavailable / not exercised |
| [34286311047](https://github.com/neilmac91/EarningsNerd/actions/runs/34286311047) (2026-09-08T22:31:07Z) | success | Scope skipped | 0 / 0 | Unavailable / not exercised |
| [34287930866](https://github.com/neilmac91/EarningsNerd/actions/runs/34287930866) (2026-09-08T22:51:14Z) | success | 52 outcomes; regression gate passed | 52 / 0 | 2279028 |
| [34290178750](https://github.com/neilmac91/EarningsNerd/actions/runs/34290178750) (2026-09-08T23:20:17Z) | cancelled | Canceled; no completed cohort report | 31 / 0 | 1205000 |
| [34290723182](https://github.com/neilmac91/EarningsNerd/actions/runs/34290723182) (2026-09-08T23:27:26Z) | success | 52 outcomes; regression gate passed | 52 / 0 | 2277820 |
| [34291767706](https://github.com/neilmac91/EarningsNerd/actions/runs/34291767706) (2026-09-08T23:41:30Z) | success | 52 outcomes; regression gate passed | 52 / 0 | 2282302 |
| [34293873159](https://github.com/neilmac91/EarningsNerd/actions/runs/34293873159) (2026-09-09T00:10:37Z) | success | 52 outcomes; hard regression gate red | 9 / 43 | 334306 |
| [34294673892](https://github.com/neilmac91/EarningsNerd/actions/runs/34294673892) (2026-09-09T00:21:40Z) | success | 52 outcomes; hard regression gate red | 0 / 52 | Unavailable / not exercised |
| [34295464681](https://github.com/neilmac91/EarningsNerd/actions/runs/34295464681) (2026-09-09T00:32:43Z) | success | 52 outcomes; hard regression gate red | 0 / 52 | Unavailable / not exercised |

## Scope defect and refutations

Every scope step used event base `08632e4d8ec49296c54808f75accef1bbc54b5f2` and compared it directly with the checked-out synthetic merge HEAD. The first three runs merged the docs head into that same base and skipped. Beginning with run 34287930866, checkout merged into newer main `e5a0af80fa4bd4b8dc3f6ba852bbf89e8c572203` while the scope comparison retained the old base (log lines 2606, 2614–2616). Thus upstream application changes entered the apparent PR scope. This repeats across all seven launched runs.

In the last run, checkout merged docs head `2d72142ed8d4c365dc944479192a636d5a19608b` into main `3e0c256cf1cb38f9a28f9c3c333d12a359fcace1` as logged abbreviated merge `9ea7a03` (4779). The scope command still used the old base (4787–4789). A local read-only diff from old base to that docs head contains exactly eight Markdown files, while old base to the newer main includes ten paths under `backend/app` or `backend/evals`, satisfying the scope regex. The PR did not need an AI evaluation to validate these documentation edits.

Refutation 1: a misleading echoed shell branch could look like a skipped run. Only the actual emitted “No AI-relevant backend changes — skipping eval-baseline” lines were counted as skips; the other seven logs contain structured `ai_call` outcomes and provider responses. Refutation 2: these might have been legitimate application edits on the documentation branch. The branch-head diff is eight Markdown files, while checkout and scope logs identify the different main parents and stale comparison base. The mechanism is upstream scope contamination, not an application edit in the final docs diff.

## Usage and measurement limits

The 196 successful `summary_primary` outcomes identify actual model `deepseek-v4-pro`. Their provider-reported usage sums to 7,879,531 prompt tokens and 498,925 completion tokens, total 8,378,456; prompt usage divides into 7,867,776 cache-hit and 11,755 cache-miss tokens. All 196 success records contain these counters. The 147 error outcomes have no token usage; absence does not establish zero billing. These counters are usage evidence, not a dollar invoice.

The first HTTP 402 in this branch history is run 34293873159 at 2026-09-09T00:13:14.5107476Z (line 5227); that run had nine successes and 43 rejections. The subsequent two runs had 52 rejections each. The canceled run 34290178750 ended with “The operation was canceled” at 23:27:39.7901436Z (line 5290), after 31 logged successes. No complete canceled-run report or complete in-flight accounting is established.

Baseline runner code hardcodes `cost_usd: 0.0` for the production baseline route (`backend/evals/runner.py`, source-provenance checkout line 282), then sums it into aggregate cost (line 369). Therefore a report cost of zero is not measured zero spend. No provider billing ledger, balance history or rate reconciliation was accessed. The unintended successful runs consumed provider-reported tokens, but the exact debit and their share of the overall balance depletion remain unknown; other runs existed outside this bounded audit.

The final three CI workflows were marked successful even though the advisory regression gate logged hard failures and exit 1. The application fallback was retained as scored output with no runner error, explaining misleading scored-count/error-count summaries. Neither workflow success nor “52 scored” establishes 52 usable generated analyses. The application-error instrumentation fix is a separate local candidate; this report does not claim it is released.

## Dated process correction and next boundary

Record that documentation updates unintentionally triggered provider work before the scope flaw was recognized. Earlier statements implying all documentation CI was no-spend need this dated qualification; do not rewrite them. Avoid further pushes that can invoke the same unsafe scope detector. Repair the comparison to describe the actual PR change set with committed workflow tests covering a moved main base, and verify actual skip logs before treating a docs run as no-generation. Any retained successful analyses may be evidence, but their incidental execution is not an authorized substitute for the planned final prompt regression. Exact financial reconciliation requires a provider usage/billing artifact; do not infer an amount from these logs.

## Exact run heads

- 34284624378: `9c570030944ed7879916224252b1e37165e6e941`; evidence `work/docs-eval-incident/34284624378.log`.
- 34285864127: `a4ec579f485c0b31b0566df9eb4aae0eb57dc08f`; evidence `work/docs-eval-incident/34285864127.log`.
- 34286311047: `1310bdb4f268fd4b9b433a53ae864a0ba4c4d0aa`; evidence `work/docs-eval-incident/34286311047.log`.
- 34287930866: `dbbc0ca43caa9e861e2e622c0e81259652dc8157`; evidence `work/docs-eval-incident/34287930866.log`.
- 34290178750: `ccd60ac559c4ae10d5767df537a0ab0808b87c4f`; evidence `work/docs-eval-incident/34290178750.log`.
- 34290723182: `7fee683c78f81ebc1efca7e000b880b5d42519c2`; evidence `work/docs-eval-incident/34290723182.log`.
- 34291767706: `f6a0ec847578d1726f2ab44361197ad8208f5e94`; evidence `work/docs-eval-incident/34291767706.log`.
- 34293873159: `d04f5b7fe4fa40c86a81e9780f0e4121865ee364`; evidence `work/docs-eval-incident/34293873159.log`.
- 34294673892: `8265d2ebacedb971f7759d3b8d8a3a5e24e98ab4`; evidence `work/docs-eval-incident/34294673892.log`.
- 34295464681: `2d72142ed8d4c365dc944479192a636d5a19608b`; evidence `work/docs-eval-incident/34295464681.log`.
