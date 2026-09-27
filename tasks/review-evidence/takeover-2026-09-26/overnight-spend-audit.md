# Overnight DeepSeek spend audit — final bounded receipt

Observed 2026-09-27. This receipt covers retained ordinary hosted application telemetry for PRs 963–970. It is a hosted-only lower bound, not a provider invoice or a complete overnight spend total.

## Ordinary PR963–970 subtotal

The retained evidence contains **1,800 recorded application provider calls** across 35 provider-producing runs: **1,799 successes and one error**. Pricing telemetry is known for 1,729 calls and sums to **USD 3.000625**. Cost remains unknown for 71 recorded calls: 70 successful calls in PR963's baseline and one PR969 prior-head error.

| PR | Calls | Known-cost | Unknown-cost | Known estimated USD | Boundary |
| --- | ---: | ---: | ---: | ---: | --- |
| 963 | 105 | 35 | 70 | 0.007550 | Baseline pricing absent |
| 964 | 427 | 427 | 0 | 0.764475 | Superseded, cancelled, and final heads included |
| 965 | 106 | 106 | 0 | 0.187150 | Final CI/Copilot |
| 966 | 0 | 0 | 0 | 0.000000 | Frontend-only eval job scope-skipped |
| 967 | 211 | 211 | 0 | 0.367071 | Superseded and corrected heads included |
| 968 | 105 | 105 | 0 | 0.187215 | Final CI/Copilot |
| 969 | 318 | 317 | 1 | 0.555938 | Superseded and corrected heads included |
| 970 | 528 | 528 | 0 | 0.931226 | Five physical CI and five physical Copilot generations; three zero-call cancelled/skipped workflows |

PR964 CI `36279709143` was cancelled after five emitted successful events; an interrupted request before telemetry emission cannot be excluded. PR969 CI `36287000069` emitted 70 successes and one error with unknown usage/cost; its replacement success is a separate event. Application telemetry cannot expose transport retries hidden within one SDK call.

## PR970 run accounting and quality boundary

All five physical CI runs produced 70/70 scored outputs and 70 successful `summary_primary` calls, with zero reported errors, retries, hard-gate failures, or judge calls. Together they account for 350 calls and USD 0.892725. All five physical Copilot runs produced 18/18 completed/scored/passed outputs and 178 successful `copilot_chat` calls, with zero reported errors, hard-gate failures, or judge calls. Together they account for USD 0.038501. Sanitized telemetry identifies the actual model as `deepseek-flash` and fingerprint `aeb56401ca74e127821c4f9126dcb669` for every physical PR970 call.

The PR970 physical run IDs are CI `36290649266`, `36291471420`, `36292268882`, `36293228553`, and `36294511807`; Copilot `36290677310`, `36291471357`, `36292268663`, `36293325534`, and `36294511938`. Cancelled/skipped Copilot workflows `36292268873`, `36293227110`, and `36293228546` made zero provider calls: retained job metadata shows no steps and no runner/provider artifact. Review-gate workflows are excluded because they do not run DeepSeek.

Final-head CI `36294511807` recorded 70 calls and USD 0.180235; its soft advisory was 164 untraceable dollar figures across 70 measured outputs, mean 2.3429. Final-head Copilot `36294511938` recorded 36 calls and USD 0.007779; six figures were uncited across five outputs. The exact-tree hosted artifacts are green, but PR970 remains **unmerged DRAFT/HOLD**. Review `5328823266`, comment `4114089923`, found that `technical_attempts` completeness is self-authenticating, so green status is not quality or release acceptance.

## Separate p/q measurement and exclusions

PR942 p/q remains outside the ordinary subtotal: **246 calls**, 176 known-cost calls totaling **USD 0.439544**, and 70 unknown-cost p-control calls. No Fable call occurred. This audit includes zero formal E7 calls, zero formal E8 calls, and zero Fable calls.

Root's signed-in production acceptance observed one fresh AAPL FY2024/FY2025 request and one fresh AAPL 2026Q2/2026Q3 request, followed by cached repeats. No per-provider call or cost telemetry was recovered, so these product requests are excluded. Two user requests do not prove exactly two provider calls, and cached repeats do not prove zero incremental cost. PR969 post-merge main CI scope-skipped eval generation and adds no paid call row.

## Deduplication and custody

GitHub workflow run ID is the primary identity. Each run contributes at most one row even when receipts, summaries, raw logs, or copied artifacts repeat its events. Raw event identity is run ID plus retained sequence position because sanitized `ai_call` records expose no provider event ID. SHA-256 binds evidence; artifact copies never add spend independently.

Machine-readable run rows, absolute retained paths, byte counts, hashes, outcomes, costs, advisories, and limitations are in:

- `outputs/takeover-2026-09-26/overnight-spend-audit.json`
- `outputs/takeover-2026-09-26/pr970-hosted-final/inventory.json`
- `outputs/takeover-2026-09-26/pr970-hosted-final/files.sha256`

Known USD values are application telemetry estimates. Billed/provider invoice cost remains unknown.

The paths above identify the external operator workspace, not committed raw bundles. This repository retains a compact [run-level copy](overnight-spend-audit.json) with host paths normalized; original source bytes and hashes remain unchanged. Across the two distinct subtotals, known application estimates sum to **USD 3.440169**, with **141 recorded calls of unknown cost**, plus the separately excluded live-product and unobserved-attempt limits. This is still not a complete invoice.
