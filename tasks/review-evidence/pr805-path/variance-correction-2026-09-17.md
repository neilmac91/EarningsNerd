# Correction: the o-versus-n improvement is about a third, not a half — 2026-09-17

The [September 16 acceptance record](acceptance-candidate-o-2026-09-16.md) compared one judged run of
candidate `summary-2026-09-o` with one judged run of production `n` and reported "negative judgments
57 → 38". A second `o` run, judged under the same contract, does not reproduce that gap. This file is
the correction; the September 16 record stands as the first run's measurement, not as the effect size.

## What was measured

Four ordinary CI `eval-baseline` artifacts (35 verified golden filings × 2 attempts, generator
`deepseek-flash`), each judged locally on the founder's subscription with `evals.judge_report`
(`cli:claude-fable-5-1`, judge contract version 2). Denominators are complete verdicts, not attempts.

| Run | Artifact | Judged | Negative | G2 | G3 | G4 unsupported cause | G5 basis mismatch | faithfulness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `n` run 1 (control) | `35148035712` | 70 | 57 (81%) | 6 | 24 | 44 (63%) | 34 (49%) | 3.14 |
| `n` run 2 (control) | `35240242526` | — | — | — | — | — | — | — |
| `o` run 1 | `35146584090` | 70 | 38 (54%) | 1 | 15 | 19 (27%) | 17 (24%) | 3.73 |
| `o` run 2 | `35159806263` | 68 | 45 (66%) | 6 | 16 | 32 (47%) | 26 (38%) | 3.18 |
| `o` pooled | both | 138 | 83 (60%) | 7 | 31 | 51 (37%) | 43 (31%) | 3.46 |

`o` run 2 lost two attempts (MELI, both repeats) to an exhausted judge subscription, not to a
generation or content failure; they are excluded from its denominator.

## Reading

**The direction is consistent and the size is not.** Candidate `o` beat control `n` on every gate in
both runs, but its own run-to-run spread — 54% versus 66% of attempts judged negative, faithfulness
3.73 versus 3.18 — is nearly as wide as its gap to the control. Pooled over both runs the honest
statement is a **reduction of about a third in negative judgments (81% → 60%) and about 40% in
unsupported causes (63% → 37%)**, not a halving. Mean faithfulness rises 3.14 → 3.46 pooled; the 3.73
in the first report was the high end of a range whose low end (3.18) is the control's own score.

The release decision is unaffected: `o` is better than `n` on every gate in every run measured, the
deterministic regression gate was unchanged, and it is already live (revision `00361-6dx`, drain
complete). What changes is the claim attached to it, and the practice
(`lessons/evals-accept-a-prompt-change-on-two-runs-not-one.md`): quote two runs per configuration and
report the range.

## The second control is generated but not yet judged

A measurement-only branch ([#906](https://github.com/neilmac91/EarningsNerd/pull/906), never merged)
reverts the prompt to `n` so CI generates a second control cohort; its artifact
(`eval-report-35240242526`, 70 attempts, 0 errors, deterministic gate PASS) is retained. Judging it
returned zero usable verdicts because the subscription judge had reached its Fable usage limit — the
same failure that cost `o` run 2 its two MELI verdicts
(`lessons/ops-the-subscription-judge-has-a-usage-limit.md`). A retry probed the subscription every
ten minutes for ten hours and never found the limit reset; it is re-armed for a further twenty-four.
**Until it completes the control column above is one run**, and the pooled `o` figures are the firmer
half of the comparison.

Judging it with a different model would not serve the purpose: the point of a second control is to
bound variance inside the same judge frame as the runs it is compared with, and verdicts from two
judges are not comparable (the same reason the September 18 verifier measurement, judged on Opus 5,
carries its own warning against cross-run comparison). If the Fable limit stays out of reach, the
honest alternative is to re-judge **all four** artifacts in one frame rather than patch one column.
