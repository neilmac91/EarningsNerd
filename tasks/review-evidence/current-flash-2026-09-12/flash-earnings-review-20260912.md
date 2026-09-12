# Current-Flash earnings explanation review — 2026-09-12

This is a bounded review of twelve retained baseline outputs, not a production acceptance or a review of upcoming #808. The artifact is `work/pr818-summary/eval_20260912T094019Z.json`; its harness records source SHA `f2c8a635c681fe106bb84d88d036d51a6713083f`, model `deepseek-flash`, candidate `baseline`, two runs per filing, judge disabled. Zero new provider or SEC calls were made. No source, test, or repository ledger was changed.

All twelve raw-section objects were inspected, focusing on earnings causes, signs and bases. Relevant retained source passages and XBRL records were cross-checked. This is **targeted source coverage**, not a claim that every line of the six large retained excerpts was read. The paired runs have byte-identical retained grounding and XBRL. Retained grounding is not necessarily the exact downstream model input: prompt caps and section selection were not reconstructed here. Accordingly, findings below establish contradictions against retained evidence or the output's own stated numbers; they do not attribute the cause to missing versus ignored input. No source-omission finding is asserted. Final web rendering was not checked.

## Identity

Indices below are zero-based `results` indices; run numbers are the artifact's own values. Source anchors below refer to extracted `work/flash-earnings-review-20260912/{ticker}-0-grounding.txt`. Equivalent run-1 source files are identical. Output quotes can be located in `{ticker}-{run}-sections.json` by the named JSON field.

| Filing | Results indices / runs | Current period |
| --- | --- | --- |
| AAPL | 0/0, 1/1 | FY ended 2025-09-27 |
| NVDA | 4/0, 5/1 | quarter ended 2026-04-26 |
| PFE | 16/0, 17/1 | quarter ended 2026-03-29 |
| BA | 24/0, 25/1 | FY ended 2025-12-31 |
| INTC | 26/0, 27/1 | quarter ended 2026-03-28 |
| RIVN | 30/0, 31/1 | FY ended 2025-12-31 |

## Must-fix quality survivors

These are output-quality findings for the explanation workstream. They do not identify a newly proven deterministic code regression in #818.

**E1 — AAPL run 0: the State Aid swing is labelled as the change excluding State Aid.** `earnings_quality.operating_vs_one_time`: “Excluding this item, the year-over-year change in the provision for income taxes was $10.7B.” The preceding sentences identify FY2024's $10.2B charge and FY2025's $486M benefit. Source lines 748–768 show the exact State Aid amounts `(486)` and `10,246` and total provisions `20,719` and `29,749`; line 1511 explicitly calls $10.7B the decrease **related to** the decision. The reader is told the opposite of the source's normalized-tax interpretation. Correct arithmetic in millions: total change −9,030; State Aid change −10,732; change excluding it +1,702.

Refutation 1: checked whether $10.7B could be a legitimate adjusted tax change; the reconciliation computes +$1.702B instead. Refutation 2: checked the narrative rather than relying only on arithmetic; MD&A explicitly assigns $10.7B to the item itself. Both failed. Keep the current/prior charge and benefit, then distinguish their contribution from the residual change.

**E2 — AAPL run 0: shareholder-return coverage and funding sign are wrong.** `value_drivers.capital_allocation`: “Capital return remained the primary use of cash, with share repurchases and dividends exceeding operating cash flow and funded partly by a $4.5B term debt issuance and a $2.0B net repayment of commercial paper.” Source lines 316–344: OCF111,482; dividends15,421; repurchases90,711; term-debt issuance4,481; commercial-paper repayment(2,032). Returns total106,132, **$5,350M below OCF**. Repaying paper consumes cash rather than supplying it.

Refutation 1: checked whether free cash flow was intended: FCF98,767 is below returns, but the sentence explicitly names operating cash flow; its own structured OCF/return numbers also disprove it. Refutation 2: checked cash-flow presentation for net issuance versus repayment: the paper line is negative and financing is a net use. Neither rescues the sentence. Separate OCF coverage from post-capex coverage and preserve sources/uses signs.

**E3 — AAPL run 1: a valuation-allowance charge is grouped with tax-reduction drivers.** `earnings_quality.operating_vs_one_time`: “FY2025's lower provision reflects the absence of that charge plus a $2.1B change in valuation allowance and a $486M State Aid-related benefit.” Source lines 756–758 record a positive2,091 valuation-allowance contribution; line1511 says the tax decrease was “partially offset by a change in valuation allowance”. This gives the allowance the wrong directional role in explaining earnings.

Refutation 1: checked whether the allowance change was a benefit; the statutory-rate reconciliation records a positive charge. Refutation 2: read the rest of the generated paragraph: it repeats the $2,091M amount but never corrects the direction, while MD&A expressly says “partially offset”. Keep as a material sign error, with the caveat that the sentence does not literally use the word “benefit” for the allowance. The correction is to say the charge partly offset the tax reduction.

**E4 — INTC run 1: the operating and non-operating adjustment bases are merged.** `earnings_quality.operating_vs_one_time`: “The reported operating loss of $(3,136)M and net loss attributable to Intel of $(3,728)M include $4,070M of restructuring and other charges ... and a $1,090M mark-to-market loss on the Escrowed Shares derivative within interest and other, net. Excluding these non-cash and one-time items, gross profit rose 14% YoY to $5,347M and Intel Products operating income rose to $4,058M.” The derivative is below operating income; gross profit5,347 is an unadjusted reported subtotal above restructuring. This presents different scopes as one exclusion bridge.

Refutation 1: read source statement lines12–42: gross profit5,347 less operating expenses8,483 gives operating loss3,136; interest and other(738) occurs below it. The derivative therefore cannot be included in operating loss. Refutation 2: checked segment policy/reconciliation at479–566: segment income excludes additional corporate costs, and consolidated gross profit already equals the reported5,347; the quoted outcomes are not a computed ex-these-items consolidated result. Keep each item attached to its true subtotal and report segment results independently. No valid adjusted net-income number can be inferred by simply adding gross charges to attributable loss; minority interests/tax also matter.

## Should-fix explanation survivors

**E5 — NVDA both runs: truthful commentary is attached to the wrong metric.** Gross-profit row commentary: “Gross margin increased primarily due to the prior year's $4.5 billion charge associated with H20 excess inventory and purchase obligations.” Operating-income row commentary begins “Operating expenses rose 52% YoY”. These are true statements about other metrics, not complete explanations of gross-profit dollars or operating-income growth. Source NVDA lines20/30 give GP61,157 vs26,668 and operating income53,536 vs21,638; line1413 is explicitly a gross-margin-rate explanation.

Refutation 1: attempted the old material allegation that the model says $4.5B primarily caused all $34.489B GP growth. It does **not**: both current outputs explicitly say “Gross margin”; therefore downgrade from that old allegation. Refutation 2: checked whether the matching supporting quote justifies row placement: it verifies the rate statement, not the row's dollar-change explanation. Retain a should-fix metric-owner mismatch. State both revenue growth and margin contribution where the evidence permits; do not rewrite the source's rate explanation as a dollar-growth cause.

**E6 — PFE run 0: the net-income row cites a pretax-increase explanation.** Commentary: “Decline reflects higher Cost of sales and Research and development expenses and a higher effective tax rate, partly offset by higher revenues and lower restructuring charges.” Its supporting evidence begins “The increase in Income from continuing operations before provision/(benefit) for taxes on income ...”. Source lines52–56 show pretax3,170 vs2,785 and tax461 vs(189); line652 gives the tax-rate explanation.

Refutation 1: attempted the old material allegation that the tax reversal was omitted. It is now included in both runs, and run1 separately reports the $650M tax swing and rising pretax result; do not repeat the old material verdict. Refutation 2: checked whether the quoted source directly supports the net-income decline: it describes the opposite-direction pretax subtotal. Retain a should-fix evidence-owner mismatch for run0, and improve the plain-language bridge in both runs: pretax earnings rose, but the tax swing more than offset the increase. Reported table rounding yields385 rather than management's386; do not fabricate precision or force reconciliation of rounded figures.

**E7 — PFE both runs: cash coverage conflates OCF and FCF.** `balance_sheet_liquidity.liquidity`: “operating cash flow of $2.6B and free cash flow of $2.2B covered $2.4B of dividends paid in the quarter.” Source lines346/350/378 and XBRL say OCF2,615, capex436, dividends2,445: FCF2,179 is short by266. Refutation 1: OCF alone does cover dividends, so the entire liquidity claim is not false and severity is lower. Refutation 2: FCF is OCF less capex, not a second additive pot; the coordinated wording cannot establish FCF coverage. Say OCF covered dividends but FCF did not. The raw numbers already permit the correct explanation.

## Old findings refuted or not reproduced

BA both: no recurrence of the old claim that $3,236M core operating earnings excludes the divestiture gain. Both explicitly tie core to FAS/CAS; source1404–1408 agrees. Independently,4,281−1,045=3,236; subtracting9,566 would instead produce a loss. Run0 also explicitly says operating results excluding the disposition gain were negative. Both debt narratives correctly total8,461+45,637=54,098 (source326/338); the retained generic XBRL long_term_debt53,848 still lacks qualified provenance, but the generated prose did not repeat the previous62.3B double count. This does not prove #808 is unnecessary: it demonstrates this pair resisted the ambiguity.

RIVN both: no recurrence of the reversed litigation/gain explanation. Both identify186M as expense and101M as gain; source1311 independently states expense partly offset by investment gain, and source586 establishes101M gain ownership. Neither manufactures an adjusted net-loss figure. The source evidence is sufficient for these labels, but a similarly valued payments tag alone would still not prove an expense event.

AAPL both: old prior-year tax charge falsely inserted into current net income does not recur; both name FY2024 explicitly. Note7 source710 confirms the year, and their current earnings numbers match XBRL. The new E1/E3 errors are different transformations of the same tax story. The old omitted-commercial-paper net-cash claim also does not recur: both debt narratives include paper.

INTC run0: “Excluding these charges, segment operating income was $4,058M for Intel Products and $(2,437)M for Intel Foundry” is incomplete scope explanation, but not the old fabricated consolidated adjusted number. Refutation1: source policy479–495 really excludes restructuring from segments. Refutation2: output explicitly labels the numbers as segment income, not consolidated income; therefore no material finding retained for this phrase. Source-qualified explanations should nevertheless avoid implying these are the only reconciling items.

PFE and NVDA: old material causal allegations are conservatively narrowed to E5/E6 as described above. Adding the correct tax discussion and explicitly naming gross margin are meaningful improvements; the recurrence counts must not ignore them.

## Consequence for the plan

The source-qualified explanation work remains justified: four material issue groups survive in three of the twelve outcomes (AAPL0, AAPL1, INTC1), despite the old BA/RIVN errors not recurring. This is not a complete twelve-output defect census. Prioritize (1) signed, period-qualified event ownership and valid subtotal bridges; (2) arithmetic checks for coverage/exclusion claims; (3) matching each evidence sentence to the metric it actually explains. Accept “not disclosed in supplied evidence” when ownership is unavailable; do not infer an earnings charge from a cash-flow payment or append guessed adjusted earnings. Preserve successes and compare the exact same twelve identities on the eventual explanation candidate. Upcoming #808 changes source provenance; assess its separate report before claiming that it fixes or worsens these baseline findings.
