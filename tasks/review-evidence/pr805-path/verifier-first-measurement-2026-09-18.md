# Judge-in-the-loop: first measurement of the verifier — 2026-09-18

The verification call built in [#908](https://github.com/neilmac91/EarningsNerd/pull/908) was run for
the first time on a real cohort and every decision it made was read against the filing. It improves
the drop decision and does not yet meet the arming bar.

## What was run

`AI_ATTRIBUTION_VERIFY` on, `AI_ATTRIBUTION_GATE` off, on a measurement-only branch
([#911](https://github.com/neilmac91/EarningsNerd/pull/911), never merged) so verdicts were recorded
while no clause was removed and the summaries stayed identical to an ordinary run. Artifact
`eval-report-35280067189` (35 verified golden filings × 2 attempts, generator `deepseek-flash`,
deterministic regression gate PASS). The verifier used the same cheap model as section recovery.

| | |
| --- | --- |
| Attempts | 70, no errors |
| Attempts carrying an attribution audit | 65 (five had no explanation clause to check at all) |
| Attempts where the gate flagged a clause | 17 |
| Clauses flagged | 23 |
| Verification calls made | 17, one per flagged generation, no failures, no timeouts |
| Verdicts | 20 "not stated", 3 "stated" |

## Every verdict read against the filing

All 23 clauses were checked against the retained excerpt, searching for the driver under several word
forms and reconstructing sentences broken across lines.

| | Verifier says drop | Verifier says keep |
| --- | --- | --- |
| The filing does **not** state the driver (drop is right) | 13 | 0 |
| The filing **does** state it (drop would delete sourced analysis) | 6 | 3 |
| Unclear | 1 | 0 |

**Precision of the drop decision: 13 of 20, about 65%**, against the lexical gate's 57% on this same
set of clauses — the gate alone would have dropped all 23. The three rescues were all correct: ASML's
"higher than expected Installed Base Management sales" (twice) and Intel's DCAI server-ASP sentence,
each stated verbatim in the filing and each one the lexical anchor could not reach. **The verifier
never wrongly rescued a clause**, which is the direction that matters least for harm but does show it
is not simply agreeing with whatever it is shown.

## Why the six wrong drops happened — and what it changes

Splitting them by whether the proving passage actually reached the verifier:

- **Three were never shown the evidence.** A long clause's content words recur in definitions and risk
  factors earlier in the filing, so many windows tied at full coverage and the tie broke by document
  order: the verifier received a "Trading Volume" definition and a cost-structure risk factor while
  the MD&A sentence stating the driver, further down, never arrived. Coinbase's consumer trading
  volume, Intel's Mobileye "higher demand for Eye Q" and Sea's net income line all failed this way.
  **Fixed in [#912](https://github.com/neilmac91/EarningsNerd/pull/912)** (`1ff0e823`): ties now break
  toward passages that state a cause, then toward the tightest match, and four passages are sent
  instead of three. Offline against this same run the proving passage now reaches the verifier for
  **8 of 9** clauses the filing does state, against 6 of 9 before.
- **Three were shown the evidence and still called it unstated.** Pfizer is the clearest: the summary
  wrote "Selling, informational and administrative expenses decreased $70M, primarily reflecting a
  decrease of $100 million in marketing and promotional spend…" and the filing says exactly that, same
  line, same amount, as a bullet under a causal lead-in. The passage was supplied and the verdict was
  still "not stated". The two Ford convertible-note clauses are the arguable pair: the filing's debt
  table carries the line and a footnote dating the settlement, but never writes the sentence.

If the ranking fix converts those three evidence failures into correct verdicts, precision lands near
**80%**, with the residue being the model's own judgement rather than what it was shown. That is the
next lever: the verify prompt reads "same line, measure and period" strictly enough to reject a
verbatim same-line restatement.

## What the strong judge adds

> **Re-judged on Fable the same day** ([results](fable-judge-results-2026-09-18.md)). In the contract
> frame: 12 of the 20 drop verdicts sit on attempts Fable failed for G4, and the gate surfaced 10 of 22
> Fable-G4 attempts. Fable and Opus agree on G4 for 87% of attempts (kappa 0.71). The section below
> is the Opus reading as first recorded.

The artifact was judged with `cli:claude-opus-5` under judge contract version 2, because the
contract's Fable judge had reached its usage limit
(`lessons/ops-the-subscription-judge-has-a-usage-limit.md`). **The G4 count below is therefore not
comparable to the Fable-judged runs of September 16 and 17**; only the within-artifact comparison is
used here.

The judge found an unsupported cause on 23 attempts; the gate flagged clauses on 17; they overlap on
8. So the gate **misses most of what the judge finds**: 15 attempts carry a cause defect the lexical
finder never surfaced. Recall, not just precision, is the open problem — a gate that acts on a third
of the defects and is right two thirds of the time is not yet worth arming.

## Position

Do not arm. The order of work is now clear: measure the ranking fix on a fresh run, then tighten the
verify prompt against the Pfizer failure shape, then look at recall. The advisory audit and the
`attribution_unverified` counter keep earning their place in the meantime, and nothing in production
has changed — both flags remain off on revision `earningsnerd-backend-00365-lkj`.
