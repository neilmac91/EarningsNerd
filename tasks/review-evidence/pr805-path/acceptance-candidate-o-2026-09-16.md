# Acceptance measurement of candidate `summary-2026-09-o` (PR #899) against production prompt `n` — 2026-09-16

Instrument: `python -m evals.judge_report` (#898 + #900 identity fix, `fec8d4d7`), judge
`cli:claude-fable-5-1` on the founder's subscription, **judge contract version 2** (G2 fabricated
comparatives, G3 hallucinated facts, G4 unsupported cause, G5 basis mismatch). Both reports are the
ordinary `eval-baseline` artifacts of a pull request's CI run (35 verified golden filings × 2 attempts,
generator `deepseek-flash`, retained payload + grounding excerpt + XBRL + statement evidence), judged
locally with every carried verdict discarded. No re-fetch, no regeneration, no API credit.

| | Candidate `o` (PR #899) | Control `n` (production prompt, PR #900 run) |
| --- | --- | --- |
| Eval artifact | run `35146584090`, `eval_20260916T203714Z.json`, source `d008c1e9` | run `35148035712`, `eval_20260916T205119Z.json`, source `48269618` |
| Deterministic regression gate | PASS, no hard regressions (one standing advisory: untraceable dollar figures 2.014) | PASS (same advisory class) |
| Judged / judgeable | 70 / 70 | 70 / 70 |
| Negative judgments | 38 | 57 |
| Attempts with any G4/G5 failure | 28 | 56 |
| G2 fabricated comparatives (attempts) | 1 | 6 |
| G3 hallucinated facts | 15 | 24 |
| G4 unsupported cause | 19 | 44 |
| G5 basis mismatch | 17 | 34 |
| Mean faithfulness / insight / clarity / specificity | 3.73 / 3.09 / 3.60 / 4.03 | 3.14 / 3.31 / 3.66 / 4.03 |
| #805 negative controls (9 filings, 18 attempts) with a G4/G5 failure | 9 attempts, 8 of 9 filings | 17 attempts, 9 of 9 filings |

Full per-attempt records: [candidate](judged-pr899-candidate-o.md), [control](judged-control-prompt-n.md).
Judge precision on this class: [six-verdict hand check](judge-spot-check-2026-09-16.md), 6/6.

## Acceptance bar (from the [assessment](../../pr805-assessment-2026-09-16.md))

The #805 negative controls move from a false explanation to abstention (no G4/G5 failure), no new
G2/G3 failure, deterministic gate unchanged. **Not met by the candidate.** Nine of eighteen control
attempts still carry an unsupported cause or a basis change, on eight of the nine filings.

## What the candidate's 44 G4/G5 failure strings are

Read one by one (owner classification by where the failing text lives):

- **Model-authored prose, the slots the prompt condition targets — 39 of 44.** The dominant pattern is
  exactly G4's definition: a "driven by / reflecting / as" clause inferred from two figures moving
  together (SE 6-K provision "driven by growth in the credit business"; JPM and NVDA EPS "reflecting a
  lower share count"; MELI total assets "driven by increases in restricted cash"; JD and SE revenue
  "driven by growth across all segments"; FIGS EPS "reflecting higher net income and a higher diluted
  share count", which is mechanically backwards). Basis changes in prose: BA computes an ex-gain
  segment figure the filing does not define (the exact behaviour the narrowed reconciliation forbids);
  JPM places a 2023 bargain-purchase gain in "the prior year"; PFE nests a component under the wrong
  subtotal; BRK.B relabels a per-share measure "(diluted)"; SE 20-F reports an in-period court order as
  a subsequent event.
- **Code-owned or machine-derived text — 5 of 44.** KO segment operating margins (42% / 36%) are the
  deterministic segment table computed on XBRL segment revenue that includes intersegment amounts
  (known from the September 15 readout; segments filler owner). AMZN "free cash flow of $7.7B (derived
  …)" is the code-owned cash card versus the issuer-defined $11.2B (the issuer-FCF residual in the
  [September 13 plan](../../financial-relationship-next-2026-09-13.md)). SE 20-F "3.2x net income" is
  the machine cash-conversion line on XBRL net income while the prose reports consolidated net income.
  These are not reachable by any prompt text.

## Reading

Like for like (same golden set, same generator, same judge and contract, artifacts fourteen minutes
apart), the candidate roughly halves every gate's failing population: negative judgments 57 → 38;
attempts carrying any G4/G5 failure 56 → 28; G4 unsupported cause 44 → 19; G5 basis mismatch 34 → 17;
G3 hallucinated facts 24 → 15; G2 fabricated comparatives 6 → 1. On the nine #805 controls, attempts
with a G4/G5 failure fall from 17 of 18 to 9 of 18. Mean faithfulness rises 3.14 → 3.73; insight falls
3.31 → 3.09, which is the expected price of abstaining from unsupported drivers; clarity and
specificity are flat. The deterministic regression gate is unchanged in both runs.

So the corrected condition does move the generator, and by more than any prior prose slice measured
here, but it does not reach the abstention bar: 39 model-authored "driven by / reflecting" clauses
survive in 70 attempts, and five failures sit in code-owned text no prompt can reach.

**Disposition.** Not merged on this evidence alone: the bar the assessment set is not met, and a
release advances the stamp so every stored summary becomes version-stale (a founder-run D4 drain
follows). Two honest options, founder's call:

1. **Release `o` as a measured improvement, not a closure** — the halving is real, deterministic
   scores are unchanged, and the drain is the same job that ran on September 16 (47 rows, USD 0.36).
   The ledger would carry "improvement released; abstention bar open".
2. **Hold `o`** and go straight to the code-owned slice.

Either way the next slice is code-owned, not prose: a deterministic attribution guard on the
model-authored explanation slots (a "driven by / reflecting / due to / as" clause must be traceable to
a source sentence naming that driver for that line, or the clause is dropped and the movement kept),
plus the three code-owned residuals this run isolates (KO segment margin basis in the segments filler,
issuer-defined free cash flow in the cash card, cash-conversion net-income basis).

## What this does not show

One judge, one generator, two attempts per filing; the judge's recall on this class is unmeasured
(its precision on six hand-checked verdicts is 6/6). The candidate and control artifacts were generated
about fourteen minutes apart on the same golden set; source excerpts are the retained ones, not
re-fetched. Nothing here regenerates a stored summary, re-pins the baseline or arms a flag.
