# A prompt change is accepted on two generated runs, never one

Date: 2026-09-17   Area: evals

**Context**: The `summary-2026-09-o` explanation candidate was compared with production `n` on one
judged 70-attempt run each and reported as "57 → 38 negative judgments, faithfulness 3.14 → 3.73".
A second `o` run, same prompt, same golden set, same judge and contract, generated fifteen minutes
later, returned 45 negatives of 68 and faithfulness 3.18. The candidate's own run-to-run spread
(54% versus 66% of attempts negative) was nearly as wide as its gap to the control it was being
credited against. Pooled over both runs the improvement is about a third of the negative population,
not a half, and the strongest single number in the first report — faithfulness 3.73 — was the high
end of a range whose low end is the control's own score.

**Rule**: Quote a prompt change's effect from at least two independent generated runs per
configuration, and report the range, not the better run. One run sets a direction; it does not size
an effect. An eval run costs about USD 0.30 of the CI-only provider key, so a second run is always
cheaper than a wrong release decision. The same applies to the control: a single control sample
cannot bound an improvement either. When only one run exists, say so in the same sentence as the
number.

**Evidence**: `tasks/review-evidence/pr805-path/acceptance-candidate-o-2026-09-16.md` (first run),
the second `o` artifact from run `35159806263` and the correction recorded on 2026-09-17;
`evals.judge_report` output for all three judged artifacts.
