# Attribution gate: measured precision of the drop decision — 2026-09-17

The arming bar from the [plan](../../attribution-guard-plan-2026-09-17.md) is that no driver the filing
actually states may be dropped. This is the measurement of that bar on the tuned gate
(`app/services/ai/attribution_gate.py` at `9c67adda`, advisory, flag off).

## Method

Every clause the gate flags on the two judged `o`-prompt artifacts — 34 clauses across 29 attempts of
70 each (`eval-report-35146584090` and `eval-report-35159806263`) — was read against the retained
excerpt the model generated from, searching the excerpt for the driver under several word forms and
reconstructing sentences broken across lines. Each clause was classified:

- **not_stated** — the filing never attributes that movement to that driver for that subject, or
  attributes it to a different line, segment or period. The gate is right to flag it.
- **stated** — the filing does state it; a drop here would delete true, sourced analysis.

Per-clause verdicts and the gate's own coverage score for each are retained alongside this file.

## Result: 16 of 34 flags are right (47%)

| | Flags | Right to flag | Would be a wrong drop |
| --- | --- | --- | --- |
| `o` run 1 | 19 | 11 | 8 |
| `o` run 2 | 15 | 5 | 10 |
| **Both** | **34** | **16 (47%)** | **18 (53%)** |

**The gate cannot be armed.** Arming it would delete a driver the filing states in about half of all
cases it acts on. The wrong drops are not marginal readings: several are verbatim filing sentences
(Intel's "DCAI revenue increased $926 million … primarily driven by $696 million of higher server
revenue due to a 27% increase in server ASPs"; Nvidia's "Revenue growth in the first quarter was
driven by data center products for accelerated computing and AI solutions"; a Pfizer bullet under a
causal lead-in). They fail because the filing's own wording is reachable only through a label the
lexical anchor does not connect to the slot — an abbreviation against a segment label, a sentence
split across lines, a driver stated for a component the summary is aggregating.

## No coverage threshold rescues it

The obvious fix — arm only below some coverage score — does not exist in this data. Right flags sit at
both ends and the relation is not monotonic:

| Gate coverage | Right to flag | Wrong |
| --- | --- | --- |
| 0.00 | 6 | 3 |
| 0.14–0.25 | 2 | 8 |
| 0.33 | 7 | 1 |
| 0.40–0.67 | 1 | 6 |

By slot, wrong drops concentrate in segment commentary (5 of 7) where the machine-authored margin
prefix and the segment label fight the anchor; the print and P&L slots are close to even.

## What is reliable: the gate agreed with the strong judge

Cross-tabulating each flag against whether the strong judge independently failed that attempt for an
unsupported cause (G4, contract v2):

| | Gate flag right | Gate flag wrong | Precision |
| --- | --- | --- | --- |
| Judge also flagged G4 on the attempt | 12 | 4 | **75%** |
| Judge did not | 4 | 14 | 22% |

The lexical gate and a strong model disagree in exactly the places the gate gets wrong. That is the
quantified case for the **judge-in-the-loop** design in the plan: keep the gate as the cheap
candidate-finder (it reads every clause in every generation for free) and let one short model call
decide the ones it flags. Only about a quarter of generations carry any flagged clause and the call
needs the clause plus the two or three source windows the gate already located, not the filing — so
the added generation cost is small. Sizing that call, its provider and its failure behaviour is a
founder decision; nothing here changes the pipeline.

## Limits of this measurement

One reader classified all 34 clauses. An independent multi-agent adjudication with adversarial
refutation was built and launched twice for exactly this reason, and could not run: the account's
model quota was exhausted the same afternoon
(`lessons/ops-the-subscription-judge-has-a-usage-limit.md`). That pass remains queued work, and it
would sharpen the 47% rather than overturn the conclusion — the majority of the wrong drops are
verbatim source sentences, which no second reader is going to reclassify. The sample is also two runs
of one prompt on 35 filings; a different cohort would move the number.
