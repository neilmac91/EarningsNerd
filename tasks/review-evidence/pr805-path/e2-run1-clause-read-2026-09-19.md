# E2 ranking run 1 — independent all-clause read, 2026-09-19

**Do not equate the 19 `not_stated` verdicts with 19 correct drops.** Of 25 flagged clauses, this
manual read finds 7 defensible prospective drops under the strict filing-stated-driver rule,
6 unsafe prospective drops,6 unresolved decomposition/ratio/basis cases,5 supported rescues and
1 rescue with a broad-subject ambiguity. No production text was dropped: verification was on,
the deletion gate was off. These are my hand-read classifications, not Fable labels or a measured
improvement over another configuration.

Artifact from [Actions 35461717484](https://github.com/neilmac91/EarningsNerd/actions/runs/35461717484): `work/e2-ranking-run1/eval_20260919T184629Z.json`, SHA256 `8574ee7ccac4976e66b20fe9ee2bc64a509d36d3275f1f400ec29f64408c5fee`.
The report records 70 scored attempts,0 errors, source `e1b52bafb18c4d1cb69f489ccbdfd8ebd7407deb`, DeepSeek Flash,
empty fallback, `AI_ATTRIBUTION_VERIFY=true`, `AI_ATTRIBUTION_GATE=false`, and no judge.
The reviewer used `/private/tmp/earningsnerd-verify-20260919` at 73cc 3116; after fetching the report
source, `git diff --exit-code 73cc3116 e1b52baf -- backend/app backend/prompts backend/evals`
returned 0. All 25 audit flags match replay slot/connective/clause-prefix/coverage exactly; all 17
flagged attempts have identical checked/candidate counts. There is **no audit-stage/raw replay
mismatch** in this run. PLD has two clauses in one slot: the slot-keyed verdict map alone is lossy,
but the retained counts say all 3 verdicts were `not_stated`, so their individual labels are known.

The recorded verdicts are 19 `not_stated`,6 `stated`,0 `unknown`; all 25 were sent and decided.
The report does not retain raw verifier quotes or rationale. Supplied passages below are a
**deterministic reconstruction** from identical source code, matching retained clauses and the
same excerpt; they are not claimed to be saved provider request logs. Model intent is not inferred.
The machine index [machine clause ledger](e2-run1-clause-read-2026-09-19.json) contains every audit flag, full replayed clause,
summary context, reconstructed passages, provenance, excerpt hash and assessment.

## Denominators and limits

| Quantity | This run |
| --- | --- |
| Flagged attempts / generated attempts |17/70|
| Flagged clauses / sent / decided |25/25/25|
| Recorded prospective drops / rescues / unknowns |19/6/0|
| Confirmed rule-specific correct prospective drops |7/19 (36.8%)|
| Unsafe prospective drops |6/19 (31.6%)|
| Unresolved prospective drops |6/19 (31.6%)|
| Correct-drop fraction on the 13 decidable cases only |7/13 (53.8%)|
| Correct-drop bound if all 6 unresolved cases proved correct |7–13/19 (36.8–68.4%)|
| Confirmed rescues / recorded rescues |5/6 (83.3%); one unresolved|
| Actual deletions |0|

These bounds express classification uncertainty, not confidence intervals. The decidable-only
fraction must not be presented without its 6 excluded cases. Several strict-rule correct drops
are mathematically plausible explanations of reported values (not numerically false statements).
The unresolved bucket keeps ratio identities, component bridges and level/change ambiguity from
being silently relabeled as hallucinations. A second reviewer/Fable may adjudicate these boundaries;
this read does not settle product policy or causal factual truth beyond the retained excerpt.
Negative findings mean no matching same-subject attribution in the retained excerpt after reading
its relevant comparison/note and targeted alternative phrases; they do not prove absence from
omitted pages of the original filing.

The run is one generated report with two repeats per filing. It is not two independent generated
reports/configuration and cannot alone size E2's effect. No Fable verdict was available to this
read. Same-judge judging and the separately dispatched second control remain outside this result.

## Concrete findings before the full ledger

- PDD6-K r 1: both actual causal sentences are in the full release, but the supplied windows are
  financial tables. Dropping that compound revenue/opex explanation is unsafe.
- PDD20-F r 0: the short-term-investment cause is explicitly stated, but clause parsing overruns a
  closing parenthesis into subsequent FX/other-income facts. This is a boundary defect as well as
  a source-selection miss, not evidence that the authored parenthetical attribution is invented.
- Ford both repeats: Note 12 anchors the 2.3B settlement to the convertible-debt component going
  to zero in the same current-debt table. Selected passages retain the settlement but lose the table.
- Sea 20-F: business-growth recaps have matching same-period business explanations in the Revenue
  section, while selected windows are generic background. Separately, the operating-income claim
  transfers an explicit as-result-of-foregoing formulation from pretax/net income to another measure.
- BABA's correct full-source rescue is supported only by a driver fragment in selected passages;
  the subject/lead-in is across a page break. A correct label does not prove adequate selected context.
- The 25 cases include no PFE flags. No conclusion about the prepared E3 Pfizer prompt candidate
  follows from this run, and the first-run absence of that case is not a measured fix.

## Every flagged clause


### 1. ASML 6-K repeat 0 — uncertain rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Claim: attributes the Q2 result to higher than expected Installed Base Management sales

Supplied-passages assessment: **partial scope**. Full-excerpt assessment: **ambiguous**.

The supplied ASML CEO passage attributes Q2 net sales and gross margin above guidance to higher-than-expected Installed Base Management sales. The full excerpt agrees. The summary first lists sequential revenue, margin and net-income movements, then calls this the Q2 result. That broad referent may imply a net-income/sequential-growth attribution not stated in the source. Do not count this as a clean successful rescue; the narrower revenue/margin reading is supportable.

### 2. ASML 6-K repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Claim: attributes the Q2 revenue and margin levels to higher than expected Installed Base Management sales

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Same source passage states Q2 sales EUR 9.3B and gross margin 54.0%, both above guidance, driven by Installed Base Management sales. Here the summary explicitly limits the claim to Q2 revenue and margin levels. Full source confirms the same period/metrics. This is a supported rescue, with the caveat that the source explains above-guidance performance, not a separately quantified QoQ-growth driver.

### 3. PDD 6-K repeat 0 — correct prospective drop

Slot: `balance_sheet_liquidity.working_capital`. Recorded verdict: `not_stated`.

Claim: driven mainly by short-term investments

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

The supplied passages show cash/investment balances and component rows, but no current-assets driver statement. Full release gives current assets 556,780 vs 518,981; cash+equivalents 128,918 vs 108,901 and short-term investments 327,496 vs 313,408. Their increases explain much of the arithmetic, but the issuer does not state this as the current-assets cause. Under the filing-stated attribution rule this is unsupported; correct numbers alone do not establish the declared driver. The clause parser cuts before the following cash clause.

### 4. PDD 6-K repeat 1 — unsafe prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: attributes the revenue increase primarily to the increase in revenues from transaction services and the operating expense increase primarily to the increase in sales and marketing expenses

Supplied-passages assessment: **missing counterpart**. Full-excerpt assessment: **supported**.

All four supplied passages are operating-statement tables. Full release explicitly says the revenue increase was primarily due to the increase in transaction-services revenue, and separately says the operating-expense increase was primarily due to sales/marketing expenses. Both causes, periods and measures match the summary. The single extracted clause combines two real attributions; selected passages omit both explanations. This is a wrong prospective drop, not a model verdict that establishes hallucination.

### 5. PDD 6-K repeat 1 — correct prospective drop

Slot: `balance_sheet_liquidity.working_capital`. Recorded verdict: `not_stated`.

Claim: driven mainly by cash and cash equivalents and short-term investments

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

As in id 3, the full source reports the balances but does not attribute total-current-assets growth to cash and short-term investments. The source components make this an intelligible derived bridge, but it is not an issuer-stated causal driver. Keep this qualification when reporting the rule-specific correct-drop count.

### 6. PLD 10-K repeat 0 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: primarily due to promote revenue falling to $2M from $139M

Supplied-passages assessment: **generic background**. Full-excerpt assessment: **decomposition only**.

The selected passages define promote revenue and generic reasons Strategic Capital revenues fluctuate, without the 2025 explanation. Full source provides recurring fees 521 vs 472, transaction fees 69 vs 61, promotes 2 vs 139, total 592 vs 672. The promote decline 137 is the dominant negative component, but no retrieved source sentence attributes this year total decline 80 to it. This is a sound arithmetic decomposition versus an unstated causal narration boundary; do not count it as a clean correct or wrong drop without a settled policy for bridges.

### 7. PLD 10-K repeat 0 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: driven by a $644M rise in rental revenues to $8.16B

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **decomposition only**.

Supplied windows concern same-store NOI reconciliation, not consolidated revenue growth. Full MD&A shows rental revenue 8,159 vs 7,515 and strategic-capital revenue 592 vs 672, plus development/other 39 vs 14. It explicitly calls higher rent on lease rollover a driver of rental income, but not the summary's consolidated 7.2% revenue increase phrased as driven by the computed 644 rental change. The component bridge is factual; whether this phrasing requires an issuer causal sentence is policy-sensitive.

### 8. PLD 10-K repeat 0 — uncertain drop

Slot: `results_that_matter.table[0].commentary`. Recorded verdict: `not_stated`.

Claim: driven by a $644M rise in rental revenues to $8.16B

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **decomposition only**.

Same 644 rental bridge as id 7, now commentary under the total-revenue table row. Source component amounts are real; supplied windows do not contain the table/period. Full source confirms component arithmetic, not the exact declared consolidated-revenue cause. Preserve as uncertain rather than inflating precision with a mechanically derived bridge.

### 9. JPM 10-K repeat 1 — correct prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: reflecting a reduction in the diluted share count to 2,781.5M from 2,879.0M

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

The four supplied windows list EPS and weighted-average shares. Full excerpt gives EPS 20.02 vs 19.75, net income 57,048 vs 58,471 and diluted shares 2,781.5 vs 2,879.0, but no issuer statement linking this EPS increase to the share decline. The denominator explanation is mathematically plausible; the narrower filing-stated-driver rule does not permit converting simultaneous reported changes into an attributed cause.

### 10. JPM 10-K repeat 1 — correct prospective drop

Slot: `the_print.key_takeaways[1]`. Recorded verdict: `not_stated`.

Claim: reflecting a lower diluted share count of 2,781.5M versus 2,879.0M

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

Same JPM denominator inference as id 9, repeated in a takeaway. Full retained excerpt and supplied passages disclose the values but do not state the causal EPS/share-count explanation. Count under the strict stated-driver rule, not as a claim that the financial arithmetic is wrong.

### 11. JPM 10-K repeat 1 — correct prospective drop

Slot: `results_that_matter.table[6].commentary`. Recorded verdict: `not_stated`.

Claim: reflecting the reduction in the diluted share count to 2,781.5M from 2,879.0M

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

Same JPM relation in diluted-EPS table commentary, adding that lower shares more than offset lower net income. The full source does not state that explanatory comparison; it is reverse-engineered from the table. The gate would remove the causal clause while leaving the observed EPS movement.

### 12. BRK.B 10-K repeat 0 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: attributes the change to lower investment gains

Supplied-passages assessment: **wrong subject or period**. Full-excerpt assessment: **decomposition only**.

Selected passages describe other earnings/insurance and an unrelated 2024vs 2023 energy/real-estate comparison. Full MD&A explicitly disaggregates Berkshire net earnings: investment gains after tax 30,737 vs 41,558 and impairment(8,255) vs zero, total 66,968 vs 88,995; it also says investment gains cause earnings volatility. These components support the economic bridge, but the full-source text does not explicitly attribute this particular total decline to lower gains in the summary's wording. Treat the table-bridge/attribution boundary as uncertain.

### 13. XOM 10-K repeat 0 — uncertain drop

Slot: `results_that_matter.table[3].commentary`. Recorded verdict: `not_stated`.

Claim: reflecting the decline in net income relative to total revenues and other income

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **ratio identity**.

Selected passages contain revenue table rows only. Full source shows attributable net income 28,844 vs 33,680 and revenues/other income 332,238 vs 349,585, yielding 8.68% vs 9.63%. The summary merely restates the net-margin ratio moving with numerator relative to denominator; it introduces no new economic driver. A blanket causal-connective interpretation can overflag this identity. This needs the ratio/decomposition policy, not a clean positive precision count.

### 14. F 10-Q repeat 0 — unsafe prospective drop

Slot: `balance_sheet_liquidity.maturities_covenants[0]`. Recorded verdict: `not_stated`.

Claim: reflecting the settlement of the $2.3 billion 0.00% Convertible Senior Notes on March 16, 2026

Supplied-passages assessment: **partial scope**. Full-excerpt assessment: **supported by anchored note**.

The verifier sees the explicit March 16 settlement of 2.3B notes and the note that cash was reduced after repayment, but lacks the current-debt table. Full Note 12 binds footnote(a) to convertible notes 2,300→zero within Company-excluding-Ford-Credit debt payable within one year 5,550→3,268. This is an explicit discharge of an identified component of the same debt balance, not unrelated co-movement. Removing the settlement explanation is unsafe. No inference that the full debt decline equals exactly 2.3B is needed.

### 15. F 10-Q repeat 1 — unsafe prospective drop

Slot: `balance_sheet_liquidity.maturities_covenants[0]`. Recorded verdict: `not_stated`.

Claim: reflecting the settlement of the $2.3 billion 0.00% Convertible Senior Notes

Supplied-passages assessment: **partial scope**. Full-excerpt assessment: **supported by anchored note**.

Same Ford settlement relation as id 14, with date omitted from the summary. The full source table and its attached footnote explicitly identify removal of the 2.3B debt component, for the same company scope and quarter. The selected windows lose the table anchor. This is a supported note-based explanation, not a fictional cause.

### 16. INTC 10-Q repeat 0 — confirmed rescue

Slot: `segments[3].commentary`. Recorded verdict: `stated`.

Claim: primarily driven by higher demand for Eye Q products

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Supplied passages explicitly state Mobileye revenue 558M, up 120M, primarily driven by higher EyeQ demand, under All other. The full source continues the Eye Q trademark/line break into products. The actual summary attaches this clause to the Mobileye increase, while separately assigning the All-other decline to Altera deconsolidation. Same subsubject and period; supported rescue.

### 17. INTC 10-Q repeat 1 — confirmed rescue

Slot: `segments[2].commentary`. Recorded verdict: `stated`.

Claim: attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The selected first two passages explicitly state DCAI revenue increased 926M, primarily driven by 696M higher server revenue due to 27% higher ASPs, and the 5% volume offset. Full source agrees. The segment label is DCAI and commentary refers to its increase. This is a supported rescue despite the old verifier prompt omitting that label.

### 18. INTC 10-Q repeat 1 — confirmed rescue

Slot: `segments[3].commentary`. Recorded verdict: `stated`.

Claim: primarily driven by higher demand for Eye Q products

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Same explicit Mobileye/ EyeQ relationship as id 16 in the second repeat. The pre-connective summary context locates the cause in Mobileye's 120M increase, not in the Altera-driven total All-other decline. Full source and selected passages support it.

### 19. BABA 20-F repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Claim: attributes the decrease primarily to the decrease in adjusted EBITA and increase in impairment of goodwill

Supplied-passages assessment: **truncated subject**. Full-excerpt assessment: **supported**.

Full BABA MD&A states income from operations 140,905→50,150 and says its decrease was primarily attributable to decreased adjusted EBITA and increased goodwill impairment, with offsets. Supplied passages begin after a page break with only the driver fragment, so they do not independently carry the complete subject/period. Full-source rescue is correct, but this is not proof the selected evidence or accepted quote alone justified the subject. Raw model quote/reason is not retained.

### 20. ASML 20-F repeat 0 — uncertain drop

Slot: `the_print.key_takeaways[3]`. Recorded verdict: `not_stated`.

Claim: primarily reflecting a EUR 5,450.0M increase in share repurchases

Supplied-passages assessment: **truncated counterpart**. Full-excerpt assessment: **level vs change**.

Full ASML cash-flow discussion says financing cash used INCREASED by 5,838.4M, primarily driven by a 5,450M increase in buybacks, plus bond repayment/dividends and offsets. The selected windows omit the start/amount of that statement. Summary attaches the buyback INCREASE to the annual financing-use LEVEL 8,670.5M rather than explicitly to its change. The source relationship exists but its numerical role is compressed; this is neither a clean correct drop nor a clean rescue without resolving the level/change reading.

### 21. SE 20-F repeat 0 — unsafe prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: attributes the revenue increase to growth across the e-commerce, digital financial services and digital entertainment businesses, including growth of GMV, growth of loans receivable and an increase in the active user base

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **supported segment synthesis**.

The selected windows are generic platform-synergy/revenue-recognition background. Full 2025vs 2024 Revenue section states total growth 36.4% then separately links Shopee growth 33.9% to GMV, finance growth 60.1% to credit/loan growth and Garena growth 26.1% to active-user/paying-user growth. The summary says growth across these businesses, including those respective mechanisms; it is a bounded synthesis of the filing section, not a lone segment driver asserted for every business. Passage ranking omitted the actual explanation. Avoid reading this as an exhaustive quantified group bridge.

### 22. SE 20-F repeat 0 — correct prospective drop

Slot: `results_that_matter.table[2].commentary`. Recorded verdict: `not_stated`.

Claim: as a result of the foregoing revenue, cost of revenue and operating expense movements

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **wrong measure attribution**.

Selected windows discuss currency risks and e-commerce costs, not operating-income 2.0B. Full source reports operating income 662,152→1,985,306 in a table, but the prose as-a-result-of-the-foregoing statement applies to PRETAX income 778.8M→2.3B and separately NET income 447.8M→1.6B. The summary explicitly claims the filing presents OPERATING income this way, transferring the source wording to another measure. The accounting identity may be true, but the attributed statement is not.

### 23. SE 20-F repeat 1 — unsafe prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Claim: attributes the revenue increase to growth across e-commerce, digital financial services and digital entertainment

Supplied-passages assessment: **generic background**. Full-excerpt assessment: **supported segment synthesis**.

Supplied passages identify the three businesses and their general revenue roles, but miss the annual comparison. Full 2025vs 2024 section narrates growth in each business immediately after the total revenue increase. The summary's broad growth-across-businesses recap preserves the subject hierarchy and same period. It does not claim that one business-specific driver applies wholesale to consolidated revenue. Dropping this sourced high-level recap is unsafe.

### 24. PDD 20-F repeat 0 — correct prospective drop

Slot: `results_that_matter.table[6].commentary`. Recorded verdict: `not_stated`.

Claim: reflecting the operating margin decline and a foreign exchange loss of CNY 2.0B in 2025 versus a foreign exchange gain of CNY 0.6B in 2024

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

Selected windows have FX labels and accounting policy, not the asserted net-margin explanation. Full source reports operating margin 27.5%→21.6%, net margin 28.5%→22.7%, FX gain 587.9M→loss 1,966.6M and an overall net-income as-result-of-foregoing discussion, but does not single out operating-margin decline+FX as the cause of net-margin contraction. This selectively constructed attribution is unsupported under the filing-stated rule; figures alone are not a stated cause.

### 25. PDD 20-F repeat 0 — unsafe prospective drop

Slot: `earnings_quality.operating_vs_one_time`. Recorded verdict: `not_stated`.

Claim: attributes to an increase of short-term investments), a foreign exchange loss of CNY 2.0B (versus a gain of CNY 0.6B in 2024), other income, net of CNY 2.7B

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **supported with parser overrun**.

Full 2025 MD&A explicitly says net interest/investment income increased 20,553.5M→25,583.8M and the increase was primarily attributable to increased short-term investments. In the summary that attribution is parenthesized; subsequent FX/other-income amounts are separate facts. The clause parser overruns the closing parenthesis and includes those unrelated amounts in its driver clause, leading selected windows toward FX policy. A drop would remove the valid investment explanation and unrelated true facts. Treat this as candidate-boundary corruption and unsafe deletion, not a confirmed hallucination.

## Review process and artifacts

Each proposed unsafe drop was checked twice: first for an actual source counterpart under the
correct annual/quarterly comparison or note, then for subject, period, amount and scope transfer.
Ford passed through the attached debt note; PDD's real parenthetical cause survived that check
while its extracted-clause boundary did not; the Sea recap preserves a multi-business hierarchy
rather than applying one business's mechanism to every business. ASML's level/change ambiguity
and generic component/ratio arguments remained unresolved instead of being forced into a win.

`work/e2-run1-read/passages.txt` holds all reconstructed candidate passages. The saved source
context JSON/text records bounded full-excerpt searches; the original artifact is authoritative.
`reconstruct.py` performs pure gate replay; `classify.py` writes this hand assessment and counts.
No code/tests/config changed, no model call, no new judge labels, no production action.
