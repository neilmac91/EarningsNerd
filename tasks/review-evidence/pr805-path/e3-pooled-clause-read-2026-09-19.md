# E3 all-clause manual comparison with E2 — 2026-09-19

E3 does not establish readiness to enable deletion. Across two reports,4 of26 prospective drops are definitely unsafe,17 remain unresolved and5 are strict-rule correct. The unknown case is a full-source-supported Pfizer explanation with a missing lead-in in its selected evidence. No text was deleted and no Fable judgments are included.

| Quantity | E2 run1 | E2 run2 | E2 pooled | E3 run1 | E3 run2 | E3 pooled |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Generated/scored attempts |70|70|140|70|70|140|
| Flagged attempts |17|12|29|18|21|39|
| Flagged clauses |25|13|38|22|26|48|
| Recorded not_stated |19|9|28|9|17|26|
| Strict-rule correct drops |7|2|9|3|2|5|
| Unsafe drops |6|4|10|1|3|4|
| Unresolved drops |6|3|9|5|12|17|
| Recorded stated |6|4|10|13|8|21|
| Confirmed full-source rescues |5|4|9|11|8|19|
| Unresolved rescues |1|0|1|2|0|2|
| Recorded unknown (unclassified) |0|0|0|0|1|1|
| Confirmed correct-drop fraction |36.8%|22.2%|32.1%|33.3%|11.8%|19.2%|
| Classification bounds |36.8–68.4%|22.2–55.6%|32.1–64.3%|33.3–88.9%|11.8–82.4%|19.2–84.6%|
| Correct among decidable drops only |53.8%|33.3%|47.4%|75.0%|40.0%|55.6%|
| Unresolved cases excluded above |6|3|9|5|12|17|
| Unsafe-drop fraction |31.6%|44.4%|35.7%|11.1%|17.6%|15.4%|
| Confirmed full-source rescue fraction |83.3%|100%|90.0%|84.6%|100%|90.5%|
| Actual deletions |0|0|0|0|0|0|

Observed E3 ranges over the two reports are22–26 flags,9–17 prospective drops,11.8–33.3% confirmed correct-drop fraction,11.1–17.6% unsafe-drop fraction and84.6–100% confirmed full-source rescue fraction. E2 ranges were13–25 flags,9–19 prospective drops,22.2–36.8%,31.6–44.4%, and83.3–100%, respectively. These are descriptive ranges, not statistical confidence intervals. The separate classification bounds treat every unresolved drop as wrong at the lower end and correct at the upper end; they are not estimates of label probability.

The lower observed unsafe fraction in E3 is not a measured causal improvement: each run regenerated summaries and changed which claims were flagged, so the comparison is not paired at the fixed-claim level. E3 has substantially more unresolved component/ratio cases. Both reports use the same35 filings with2 repeats, and all70 corresponding source excerpts match E2 byte-for-byte, but repeated and overlapping claims are correlated. No sentence-level recall or production quality estimate follows from this selected flagged population.

## Concrete observations

- Run1 PDD20-F flag19 catches the negated phrase without attributing ... a single driver. The full operating-profit context describes collective foregoing movements. Treating the isolated a single driver as an asserted cause would delete a source-consistent caution.
- Run2 KO10-Q flag10 is a source-owned consolidated growth-factor table:8% volume,2% price/mix,3% FX and(1)% acquisitions/divestitures. Selected windows retain only definitions, and the verifier rejects the valid bridge.
- Ford's note-supported current-debt settlement and Sea's detailed business-specific revenue-driver synthesis remain unsafe prospective drops in run2, consistent with E2 findings.
- E3's new subject field often reads The filing or Management, but the connective sent alongside it retains explicit objects such as operating income decline and Q2 result. This is not global loss of the attribution object. BABA run2 uses the decrease without the preceding sentence's operating-income antecedent, and the DCAI anchor names an entity rather than a revenue metric. For example, ASML's two broad Q2 result rescues in run1 remain ambiguous while run2 expressly limits the source to revenue/margin. BABA's two operating-income rescues are full-source correct, but selected fragments omit the subject lead-in. A correct retained label is not proof that the request supplied adequate context or that the model obeyed the new unknown rule.
- Pfizer run2 flag13 is unknown with a correct SIA subject/anchor but only a detached source driver bullet. Full excerpt supports the claim; abstention is consistent with the new instruction. It is neither a drop nor a rescue and is excluded from both denominators.
- New FIGS, XOM, AAPL, JD, Boeing and Coinbase cases illustrate unresolved denominator/component, level/change or ratio-policy boundaries. The reports keep these out of the confirmed precision numerator. Generic aggregate growth bridges are distinguished from detailed same-business causal restatements.

## Provenance and refutations

All48 exact audit flag records and candidate counts match deterministic replay. Run1 SE20-F repeat0 records8 checked versus6 in final-payload replay; run2 records11 versus10. Original pre-binding checked payloads and verifier quotes/reasons are not retained. Later statement binding is a plausible stage explanation, not a proven reconstruction. The audit denominators remain authoritative. Run1 synthetic merge and run2 candidate have identical application/prompt/eval trees; this was independently verified with git diff. These reports reconstruct evidence, not provider request logs.

Review lens1 checked source measure, period, amount, business and accounting basis. Lens2 checked source passage selection and summary context/parsing/stage delivery. Lens3 checked denominators, correlated samples, unresolved classifications and absent judge evidence. Two independent refutations of an E3 improvement claim are (a) regenerated, non-identical claims and (b) the rise from9 to17 unresolved prospective drops. Two independent refutations of treating every rejection as correct are (a) the explicit KO bridge table and (b) PDD's negated assertion. Conversely, matching driver words alone does not establish a rescue: ASML scope and BABA's missing selected lead-in were checked independently.

The same five E2 categories are reused; the sole recorded unknown has a null classification with a full rationale. These manual categories are not Fable labels. No tests, model calls, cloud reads, production actions or tracked-code changes were performed. Full clause notes and reconstructed selected windows are in `work/e3-run1-clause-read.md/json` and `work/e3-run2-clause-read.md/json`; pooled machine totals are in `work/e3-pooled-clause-read.json`.
