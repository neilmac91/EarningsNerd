# Fable judge results: the second control and the verifier run in the contract frame — 2026-09-18

A second agent with Fable capacity judged the two artifacts that were blocked on this session's
exhausted quota, following [the handover](../../handover-fable-judge-2026-09-18.md) and reporting on
[#915](https://github.com/neilmac91/EarningsNerd/pull/915). Both tasks returned complete verdicts with
no errors. Every figure below was then recomputed by this session along a second, independent code
path from the primary sources — the judged reports on disk and the raw text of the two PR comments —
and all of them reproduced exactly. Per-attempt data for all six judged runs is retained alongside
this file ([JSON](fable-judge-per-attempt-2026-09-18.json)).

**How the judging was done.** `backend/evals/judge_report.py` unmodified at `93c0d2e`, the default
contract judge `cli:claude-fable-5-1`, judge contract version 2, concurrency 2. The second agent ran
on its own session's Fable access rather than the founder's subscription login: same model, same CLI
path, same judge code and prompt, so the same judge frame. It checked each downloaded artifact's
SHA-256 against GitHub's digest before judging.

## 1. The comparison now rests on five runs, and it holds

| Run | Prompt | Judged | Negative | Unsupported cause (G4) | Basis mismatch (G5) | Faithfulness |
| --- | --- | --- | --- | --- | --- | --- |
| Control 1 | `n` | 70 | 57 (81.4%) | 44 (63%) | 34 (49%) | 3.14 |
| **Control 2 (new)** | `n` | 70 | **55 (78.6%)** | **41 (59%)** | **31 (44%)** | **3.17** |
| Candidate 1 | `o` | 70 | 38 (54.3%) | 19 (27%) | 17 (24%) | 3.73 |
| Candidate 2 | `o` | 68 | 45 (66.2%) | 32 (47%) | 26 (38%) | 3.18 |
| **Candidate 3 (new)** | `o` | 70 | **33 (47.1%)** | **22 (31%)** | **19 (27%)** | **3.71** |
| **Control pooled** | `n` | 140 | **112 (80.0%)** | **85 (61%)** | **65 (46%)** | **3.16** |
| **Candidate pooled** | `o` | 208 | **116 (55.8%)** | **73 (35%)** | **62 (30%)** | **3.54** |

Candidate 3 is the verifier measurement run: it was generated on the `o` prompt with verification
recording verdicts and the gate off, so its summaries are ordinary `o` output and it is a third
independent candidate sample.

- **The `o` release is confirmed.** Every candidate run beats every control run on negative
  judgments, unsupported causes and basis mismatches — the worst candidate run is better than the
  best control run on all three (66.2% against 78.6%, 47% against 59%, 38% against 44%; G5 is the
  thinnest margin). Pooled, `o` produces **30% fewer negative judgments and 42% fewer attempts with
  an unsupported cause**.
- **The size claim is now honest.** The first report said the improvement halved negatives; the
  September 17 correction said about a third from one control run. With two controls and three
  candidates the figure is 80.0% → 55.8% of attempts judged negative.
- **Faithfulness gains in two of three candidate runs, not all.** Candidate 2 (3.18) is level with the
  controls (3.14, 3.17). Pooled it rises 3.16 → 3.54; insight falls 3.29 → 3.09, the expected cost of
  abstaining from unsupported drivers.

## 2. The candidate is noisy and the control is not

The two control runs sit 2.9 points apart on negative rate; the three candidate runs span 19.0.
Against a binomial yardstick — the spread sampling alone would produce at these rates and sizes — the
controls come in under it (2.9 against about 5.4 points expected for two runs) while the candidates
come in at roughly twice it (19.0 against about 10.1 for three). Because one judge scored every run,
this **suggests the prompt condition makes generation less consistent from run to run**: it works on
average and bites harder on some runs than others. Two and three runs are a small base for a claim
about variance, and filings repeat across runs so attempts are not independent draws; treat this as a
lead worth testing rather than a finding. It does sharpen the standing rule — a prompt change needs at
least two runs, and a candidate this variable needs three.

## 3. First cross-judge agreement: Fable and Opus on the same artifact

Candidate 3 had already been judged on Opus 5 when Fable was unavailable. Judging it again on Fable
gives this project its first measurement of whether the acceptance instrument depends on which strong
model is the judge.

| Per attempt | Opus 5 | Fable 5.1 | Both | Agreement | Cohen's kappa |
| --- | --- | --- | --- | --- | --- |
| Verdict FAIL | 37 | 33 | 28 | 80.0% | 0.60 |
| **Unsupported cause (G4)** | 23 | 22 | 18 | **87.1%** | **0.71** |
| Basis mismatch (G5) | 22 | 19 | 13 | 78.6% | 0.48 |

**The judges agree most on G4, the gate this whole line of work targets**, at a level usually read as
substantial agreement, and least on basis mismatch, which is a fuzzier judgement. The acceptance
instrument is therefore reasonably robust to the choice of judge for unsupported causes, and the rule
against mixing judges across runs stays: 20% of overall verdicts still differ.

## 4. The verifier, re-read in the contract frame

The [first verifier measurement](verifier-first-measurement-2026-09-18.md) had to use Opus as its
judge. Under Fable its conclusions stand and firm up slightly:

- Of the verifier's 20 "not stated" verdicts, **12 sit on attempts Fable failed for an unsupported
  cause** (10 under Opus).
- The lexical gate surfaced **10 of the 22 attempts** Fable failed for G4; **12 carried a cause defect
  the gate never flagged**. Recall remains the larger gap, as the Opus reading found.
- The clause-level precision of the drop decision — 13 of 20 correct, read by hand against the filing
  — does not depend on the judge and is unchanged.

Position unchanged: **do not arm**. The order of work stays re-measure with the ranking fix
([#912](https://github.com/neilmac91/EarningsNerd/pull/912)), tighten the verify prompt against the
Pfizer failure shape, then attack recall.

## What the handover itself showed

The split of work did what it was designed to do: the judging was the only step gated on Fable, the
brief named two artifacts and exact commands, and both came back complete, within the boundaries,
with the judge frame and artifact integrity stated in the results rather than left implicit. The one
instruction the second agent could not follow — a per-attempt Fable-versus-Opus comparison, because
the Opus verdicts were not in the repository — is completed in section 3.
