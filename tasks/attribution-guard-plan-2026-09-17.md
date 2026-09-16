# Code-owned attribution guard — plan and offline calibration, 2026-09-17

The next slice after the `summary-2026-09-o` release
([acceptance record](review-evidence/pr805-path/acceptance-candidate-o-2026-09-16.md)). The prompt
condition halved unsupported causes; the remaining 19 of 70 attempts carry a model-authored "driven
by / reflecting / due to" clause the filing does not state. Prose instruction has reached its floor;
the rest is code, in the shape the repository already uses for quotes and evidence.

## Shape (the forward-quote-gate pattern)

`app/services/ai/attribution_gate.py`, a pure leaf like `forward_quote_gate.py`: walk the
model-authored explanation slots (`the_print.headline/key_takeaways/what_changed`, P&L row
`commentary` anchored on its `metric`, `earnings_quality.operating_vs_one_time`, segment
`commentary`, `balance_sheet_liquidity.leverage/liquidity/working_capital/maturities_covenants`),
find each causal clause (connective + driver phrase), and verify the driver against the excerpt the
model generated from: a source sentence about the same subject that carries the driver's content
tokens **and** itself states a cause. Measure always (audit on the row, greppable counter in
`summary_pipeline`, the `forward_quote_unverified` precedent); mutate only when a new
`AI_ATTRIBUTION_GATE` flag is armed, and then by dropping the clause and keeping the movement
("Revenue rose 25%, driven by strong demand." → "Revenue rose 25%."). No source text → measure and
drop nothing. Verbatim quotes and evidence fields are exempt (already owned).

## Offline calibration against the strong judge (prototype, scratch only)

Run over the two judged artifacts of 2026-09-16 (70 attempts each; judge contract v2). Recall is
measured at attempt level against the judge's G4 findings; "extra" is attempts the guard flags that
the judge did not fail for cause (a mix of judge misses and guard false positives; only a hand read
separates them).

| Prototype iteration | Candidate `o`: clauses / flagged / attempts flagged | Judge-G4 attempts caught | Extra attempts | Control `n`: caught / judge-G4 |
| --- | --- | --- | --- | --- |
| 1. Connectives, 60 % token coverage, source sentence must carry a connective | 570 / 132 / 48 | 16 of 19 | 32 | 35 of 44 |
| 2. + broader source-side connectives, subject anchoring on the clause's own sentence | 458 / 129 / 45 | 17 of 19 | 28 | 35 of 44 |
| 3. + "attributable to <owner>" excluded as a measure name, table commentary anchored on its `metric`, framing words dropped from subjects | 482 / 88 / 40 | 15 of 19 | 25 | 31 of 44 |

| 4. Production module (`app/services/ai/attribution_gate.py`, PR): lead-in adverbs in connectives, subject pool widened to the source sentence plus its predecessor (filings name the subject in one sentence and the cause in the next) | 452 / 81 / 35 | 11 of 19 | 24 | 27 of 44 |

The production module trades recall for fewer false drops on purpose: the two-sentence subject
window is what lets a stated driver verify when the filing splits subject and cause across
sentences (the KO case), and a gate that will one day drop text must first be trusted not to drop
a stated driver. Recall is recovered in calibration, not by narrowing the window blind. Run the
script on any judged artifact:

```bash
cd backend && python -m scripts.calibrate_attribution_gate <judged.json> --show 2
```

Read of the residual extras after iteration 3: about half are source-stated drivers the lexical
match misses because the filing phrases the cause differently ("primarily the result of",
"operational growth of 2%" versus the summary's "operational increase"), a quarter are drivers the
judge plausibly missed (JPM/NVDA "reflecting a lower share count" appears in judge-PASS attempts
too), and the rest are list-style clauses ("reflecting $351M of restructuring, $103M of …") whose
items are individually in the source. Diagnosed and fixed in the prototype: subject anchoring on
"management attributes" excluded the right sentence (KO's concentrate-volume driver is in the MD&A
verbatim and scored 0.11 until the framing words were dropped).

## Acceptance for the real PR

1. Advisory-first: ship unarmed with the audit and counter; no output changes.
2. Calibrate on the next two PR eval artifacts judged through `evals.judge_report`: report recall
   against G4 and a hand-read precision on a 30-clause sample of extras. Arm only when precision on
   the drop decision is at or above the forward-quote gate's bar (no genuine source-stated driver
   dropped in the sample).
3. One source-to-visible invariant with a mutation proof: an unsupported clause is measured and,
   armed, removed while the movement survives; a source-stated driver is never touched.
4. Locked contract tests untouched; the `o` stamp does not change (a gate is not a prompt change);
   `test_prod_flag_visibility` carries the new flag.

Separately, the three code-owned residuals the acceptance run isolated keep their own owners: KO
segment operating margins in the segments filler (intersegment revenue basis), issuer-defined free
cash flow in the cash card ([September 13 plan](financial-relationship-next-2026-09-13.md)), and
the cash-conversion line's net-income basis.
