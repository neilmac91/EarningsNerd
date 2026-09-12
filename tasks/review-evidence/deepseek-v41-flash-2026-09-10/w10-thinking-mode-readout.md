# W10 — Thinking mode at low effort on the summary path: measured, not adopted

Date: 2026-09-10. Code: `main` after #812 (`AI_SUMMARY_THINKING_EFFORT` switch). Model: `deepseek-flash`.
Arms: the tracked non-thinking reference `backend/evals/baselines/eval_20260910T153541Z.json`
(3 × 26, thinking disabled, production configuration) vs a 3 × 26 run with
`AI_SUMMARY_THINKING_EFFORT=low` (primary call only; recovery and fallback non-thinking; `temperature`
dropped; `max_tokens` 24,000). Deterministic scorers, judge off. Same CI eval env otherwise.
Paired deltas: `flash-nonthinking-vs-thinking-low.md`; per-attempt data: `eval_20260910T184455Z-thinking-low-slim.json`.

## Result

| | non-thinking | thinking `low` | delta |
|---|---:|---:|---:|
| scored / errors (of 78) | 78 / 0 | 76 / 2 | 2 attempts exhausted the 75 s budget (JPM 10-K, ASML 20-F) |
| attempts needing a timeout retry | 0 | 11 | +11 |
| gate_fail_rate, numeric precision, accuracy, coverage | 0.0 / 1.0 / 1.0 / 1.0 | 0.0 / 1.0 / 1.0 / 1.0 | none |
| forward_quote_fidelity | 0.910 | **0.980** | +0.070 |
| citation_fidelity | 0.906 | **0.965** | +0.058 |
| redundancy | 0.902 | 0.913 | +0.011 |
| financial_depth / specificity / delta_consistency | 0.932 / 0.995 / 0.852 | 0.930 / 0.994 / 0.855 | flat |
| latency per summary (s) | 14.5 | **36.8** | ×2.5 |
| completion tokens per summary | 3,894 | **8,749** (4,712 reasoning + 4,037 answer) | ×2.25 |
| per-summary cost, warm cache, off-peak | $0.0044 | $0.0072 | ×1.6 (output-only ×2.25) |
| prompt cache | 68% hit | 70% hit | a thinking request has its own cache identity; first run of each filing missed |

`reasoning_tokens` arrived on the wire for 76 of 76 scored attempts (`completion_tokens_details.reasoning_tokens`, mean 4,712, max 8,029), which also confirms the W7 capture path.

## Reading

The model does reason its way to more faithful verbatim quotes: forward-quote and citation fidelity
improve by a clear margin, and the answer body itself is not longer (4,037 vs 3,894 answer tokens).
Everything the hard gates measure is already saturated on both arms, so the gain is confined to two
advisory dimensions.

The costs are structural, not tunable: reasoning tokens add ~120% to output, first token moves from
~2 s to ~7 s, and the 45 s attempt / 75 s summary budgets that the SSE path is built around start
failing (14% of attempts retried, 2.6% lost). Adopting it for the interactive summary would need a
budget redesign and the progressive-reveal UX would show nothing for the first 7 s.

## Recommendation

Do not adopt thinking mode on the interactive summary path. Keep `AI_SUMMARY_THINKING_EFFORT` empty
in production. If the verbatim-fidelity gain is wanted, the cheaper route is on the deterministic
side (the W11 normaliser fold already recovered one class of misses) or a thinking arm restricted to
the background pregenerate path with its own budget — a separate, re-pinned change if ever proposed.
No further spend is planned on this question.

Spend for this measurement: about $0.60 (79 provider calls, ~$0.0072 per summary).

## September 12 audit qualification — retained usage is not complete spend

The [migration audit](../../audit-astra-2026-09-11.md) found that the runner omitted observer usage on failed generations and discarded earlier outer-attempt usage on retry. The frozen report has78 outcomes,76 scored,11 outer retries and79 recorded provider calls; two terminal errors have no usage row, while three recorded calls have unknown usage. Consequently the recorded call/cost totals cannot establish complete billing. The36.779-second mean describes final attempts and excludes earlier timeout/backoff time. No missing calls, tokens or charges are invented, and the frozen JSON and original readout above remain unchanged. Future incurred-work accounting is being corrected separately. This limitation does not reverse the decision to leave thinking off.
