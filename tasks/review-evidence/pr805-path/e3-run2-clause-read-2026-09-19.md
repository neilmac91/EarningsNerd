# E3 candidate run 2 — independent all-clause read, 2026-09-19

All 26 flags were read against the reconstructed verifier passages and the full retained grounding excerpt. The manual labels are **2 strict-rule correct prospective drops, 3 unsafe prospective drops, 12 unresolved drops, 8 confirmed full-source rescues and 0 unresolved rescues**. Recorded unknowns: **1**, retained as null classifications rather than counted as rescues or drops. Verification was on and deletion off; **no text was deleted**. These are manual assessments, not Fable judgments.

Artifact: `work/e3-candidate-run2/eval_20260919T192513Z.json`, SHA256 `2f4015e4921ecfcf198011db09b36dfd01ea5a69e15da85c31de583a4126e805`. Recorded source: `8a8065b771f4a5d8a0366f1a3b1f535d7305fe19`. The artifact has70 scored attempts,0 errors,35 filings and2 repeats with DeepSeek Flash; harness `judge=false`. Run2 source equals the designated E3 worktree HEAD `8a8065b771f4a5d8a0366f1a3b1f535d7305fe19`. Run1 is synthetic merge `d59b0b13fca0ea86a5fe3ade0832f78055b08635`, with parents main `f6f84aa1` and candidate `8a8065b7`. Independently repeating `git diff --exit-code 8a8065b7 d59b0b13 -- backend/app backend/prompts backend/evals` exits0. All70 corresponding grounding excerpts are byte-identical between both E3 reports and both E2 reports. Generated summaries and therefore flagged clauses differ.

Every retained flag record (slot/connective/clause/coverage) exactly matches replay; no missing or extra candidates occur. All 21 flagged-attempt candidate counts match. One checked-count mismatch remains: **SE20-F repeat0 audit11 versus final-payload replay10**, with its sole flagged clause exact. Verification precedes statement binding, which can remove or replace model-authored earnings-quality fields. That stage difference is plausible, but the original pre-binding payload is not retained and the missing checked clauses cannot be reconstructed conclusively. The audit count remains authoritative.

The actual request also includes connective plus clause: an explicit attributed object may survive there even when the separate subject field reads The filing. The subject field alone must not be treated as the entire request. Pronoun antecedents from earlier sentences may still be absent.

The supplied passages and bounded subject/anchor fields are deterministic reconstructions using source-equivalent code, not saved provider request logs. Raw verifier quotes/reasons are not retained. All clauses have unique slots in these reports; no duplicate-slot verdict ambiguity was found.

## Decision denominators

- Recorded labels: 17 `not_stated`, 8 `stated`, 1 `unknown`.
- Confirmed correct-drop fraction: 2/17 = 11.8%.
- Classification bound if every unresolved drop were correct: 11.8%–82.4%. This is not a confidence interval.
- Correct fraction among decidable drops only: 40.0%, excluding 12 unresolved cases.
- Confirmed full-source rescues: 8/8 = 100.0%. Correct source truth does not establish sufficient selected evidence or correct unretained model reasoning.

## Every flagged clause

### 1. ASML 6-K repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Total net sales rose from €8,767M in Q1 2026 to €9,326M in Q2 2026, gross margin rose from 53.0% to 54.0%, and net income rose from €2,757M to €2,918M. The filing attributes the Q2 revenue and margin levels to higher than expected Installed Base Management sales, and states that ongoing AI-related investments and continued progress in AI technologies are driving demand for advanced Logic and Memory chips.

Flagged cause: higher than expected Installed Base Management sales

Reconstructed request cause (connective plus clause): attributes the Q2 revenue and margin levels to higher than expected Installed Base Management sales

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **supported narrower comparison**. Full-excerpt assessment: **supported**.

Unlike the two broad Q2 result versions in run 1, this summary expressly limits the attribution to Q2 revenue and margin levels. The CEO passage gives 9.3B revenue and 54.0% margin above guidance due to higher Installed Base Management sales. Follow the E2 run 2 supported-rescue classification, retaining the caveat that source explains above-guidance performance rather than separately proving sequential growth causation. The separate subject field is The filing, but the request connective retains the explicit Q2 revenue and margin levels.

### 2. SE 6-K repeat 0 — uncertain drop

Slot: `results_that_matter.table[5].commentary`. Recorded verdict: `not_stated`.

Summary context: Operating income increased 33.3% year-on-year, reflecting the revenue increase partly offset by higher operating expenses.

Flagged cause: the revenue increase partly offset by higher operating expenses

Reconstructed request cause (connective plus clause): reflecting the revenue increase partly offset by higher operating expenses

Reconstructed prompt subject: `Operating income increased 33.3% year-on-year,`. Anchor: `Operating income`.

Supplied-passages assessment: **wrong period table fragment**. Full-excerpt assessment: **accounting relationship**.

The quarterly table reports operating income 650.329 versus 487.719 million, up 33.3%, higher revenue 7,787.779 versus 5,259.477 million, higher cost of revenue and higher operating expenses. Full prose discusses individual segment revenue and expense drivers, but no retained issuer sentence directly gives the stated total operating-income bridge. Selected passage 1 is a different six-month gross-profit table. The statement is an abbreviated accounting relationship that also omits the cost-of-revenue increase; keep uncertain under the E2 bridge-policy boundary, not a confirmed hallucination.

### 3. PDD 6-K repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Revenue growth of 8% was accompanied by a 13% increase in total operating expenses, to RMB36.6 billion, which the filing attributes primarily to an increase in sales and marketing expenses; net income attributable to ordinary shareholders decreased 12% to RMB27.2 billion. The filing states the revenue increase was primarily due to the increase in revenues from transaction services.

Flagged cause: the increase in revenues from transaction services

Reconstructed request cause (connective plus clause): primarily due to the increase in revenues from transaction services

Reconstructed prompt subject: `The filing states the revenue increase was`. Anchor: ``.

Supplied-passages assessment: **detached subject**. Full-excerpt assessment: **supported**.

Full press release explicitly says total revenues 112.4B, up 8%, followed by The increase was primarily due to the increase in revenues from transaction services. The selected first passage has that explanation but omits the antecedent amount/total-revenue sentence; other windows supply component values. Correct full-source rescue, though the selected detached increase leaves an evidence-context gap under the new instructions. The earlier expense clause is not this flagged cause.

### 4. PLD 10-K repeat 0 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Revenue growth was driven by rental revenues, which increased to $8.16B from $7.52B, while strategic capital revenues declined to $592M from $672M. Net earnings declined primarily due to lower gains on real estate transactions and higher interest expense. Gains on dispositions of development properties and land were $258M in 2025 versus $414M in 2024, and gains on other dispositions of investments in real estate were $686M versus $904M. Interest expense increased to $1.00B from $864M, which management attributes to the issuance of senior notes to finance acquisition and development activities with higher interest rates on new issuances.

Flagged cause: rental revenues

Reconstructed request cause (connective plus clause): driven by rental revenues

Reconstructed prompt subject: `Revenue growth was`. Anchor: ``.

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **decomposition only**.

Full MD&A supplies rental revenue 8,159 versus 7,515 million and strategic capital 592 versus 672 million, and separately explains rental-rate changes. Selected windows contain general NOI definitions. The summary compresses the total-revenue movement into its rental component without a retained explicit same-total attribution. Preserve the E2 PLD component-bridge uncertainty.

### 5. PLD 10-K repeat 0 — uncertain drop

Slot: `the_print.key_takeaways[1]`. Recorded verdict: `not_stated`.

Summary context: Net earnings attributable to controlling interests fell to $3.33B from $3.73B, and diluted EPS declined to $3.56 from $4.01, reflecting lower gains on dispositions ($944M combined in 2025 vs. $1.32B in 2024) and higher interest expense.

Flagged cause: lower gains on dispositions ($944M combined in 2025 vs

Reconstructed request cause (connective plus clause): reflecting lower gains on dispositions ($944M combined in 2025 vs

Reconstructed prompt subject: `Net earnings attributable to controlling interests fell to $3.33B from $3.73B, and diluted EPS declined to $3.56 from $4.01,`. Anchor: ``.

Supplied-passages assessment: **table fragment and wrong subject**. Full-excerpt assessment: **decomposition only**.

Full source contains disposition gains 258+686=944 million versus 414+904=1,318 million and interest 1,002 versus 864 million, but does not explicitly assign the consolidated net-earnings/EPS fall to those selected components. Selected windows are tax discussion and one gain table fragment. The parser also stops at vs. before the comparison/interest continuation. Consistent with E2, retain uncertainty around accounting synthesis and EPS denominator effects.

### 6. PLD 10-K repeat 0 — uncertain drop

Slot: `results_that_matter.table[5].commentary`. Recorded verdict: `not_stated`.

Summary context: Net margin declined due to lower gains on dispositions and higher interest expense relative to revenue.

Flagged cause: lower gains on dispositions and higher interest expense relative to revenue

Reconstructed request cause (connective plus clause): due to lower gains on dispositions and higher interest expense relative to revenue

Reconstructed prompt subject: `Net margin declined`. Anchor: `Net margin`.

Supplied-passages assessment: **wrong subject**. Full-excerpt assessment: **accounting relationship**.

The PLD full financial bridge supports lower disposition gains and higher interest costs relative to rising revenue; the source does not explicitly assign the derived net-margin decline to those components. Supplied passages explain unconsolidated-entity earnings and tax, not the consolidated ratio. This is the same unresolved ratio/component policy boundary as E2 margin and net-earnings cases.

### 7. PLD 10-K repeat 1 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Rental revenues increased 8.6% to $8.16B, which management attributes to significant rent change due to higher rental rates on the rollover of leases during both periods. Strategic capital revenues decreased 11.9% to $592M, primarily due to promote revenue declining to $2M from $139M. Gains on dispositions of development properties and land decreased to $258M from $414M, and gains on other dispositions of investments in real estate decreased to $686M from $904M. Interest expense increased to $1.00B from $864M, which management attributes principally to the issuance of senior notes to finance acquisition and development activities with higher interest rates on new issuances.

Flagged cause: promote revenue declining to $2M from $139M

Reconstructed request cause (connective plus clause): primarily due to promote revenue declining to $2M from $139M

Reconstructed prompt subject: `Strategic capital revenues decreased 11.9% to $592M,`. Anchor: ``.

Supplied-passages assessment: **generic component definition**. Full-excerpt assessment: **decomposition only**.

Full strategic-capital table shows revenue 592 versus 672 million and promote revenue 2 versus 139 million, with recurring/transactional fees partly offsetting the promote decline. The source explains how promotes arise and fluctuate, but does not explicitly link the total decline to that component in a same-period causal sentence. Selected windows are generic promote definitions. Keep the same unresolved classification as E2 PLD promote bridges.

### 8. AAPL 10-K repeat 1 — uncertain drop

Slot: `results_that_matter.table[0].commentary`. Recorded verdict: `not_stated`.

Summary context: Management attributes the increase in total net sales to higher net sales across most categories and segments, with Services net sales up 14% and iPhone net sales up 4%.

Flagged cause: higher net sales across most categories and segments

Reconstructed request cause (connective plus clause): attributes the increase in total net sales to higher net sales across most categories and segments

Reconstructed prompt subject: `Management`. Anchor: `Total net sales`.

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **decomposition only**.

Full 2025 segment and category tables support growth in four of five geographic segments and four of five product/service categories, including Services 14% and iPhone 4%; Greater China and Wearables declined. The summary says most, so it does not falsely claim universal growth. However Management attributes total growth is stronger than the retained separate component discussion; selected windows only define segment accounting. Treat this as unresolved aggregate decomposition, consistently with PLD, not a proven false statement.

### 9. JPM 10-K repeat 0 — correct prospective drop

Slot: `the_print.key_takeaways[1]`. Recorded verdict: `not_stated`.

Summary context: Net income declined 2% to $57.0B, while diluted EPS increased 1% to $20.02, reflecting a lower diluted share count of 2,781.5M versus 2,879.0M.

Flagged cause: a lower diluted share count of 2,781.5M versus 2,879.0M

Reconstructed request cause (connective plus clause): reflecting a lower diluted share count of 2,781.5M versus 2,879.0M

Reconstructed prompt subject: `Net income declined 2% to $57.0B, while diluted EPS increased 1% to $20.02,`. Anchor: ``.

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

Same JPM strict-rule inference as E2 and run 1: lower diluted shares 2,781.5 versus 2,879.0 million plus EPS20.02 versus 19.75 and lower net income are disclosed, but a same-subject issuer sentence attributing EPS growth to the denominator is not retained. Correct prospective drop under that rule, without alleging numerical falsity.

### 10. KO 10-Q repeat 1 — unsafe prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Net operating revenues increased $1,343M, or 12%, to $12,472M for the three months ended April 3, 2026 from $11,129M for the three months ended March 28, 2025. Management's table attributes the consolidated change to 8% volume, 2% price/mix, 3% foreign currency fluctuations and (1)% acquisitions and divestitures. Operating income increased $700M, or 19%, to $4,359M, which management attributes to an increase in concentrate sales volume of 8%, favorable price/mix, lower operating expenses, lower other operating charges and a favorable foreign currency exchange rate impact of 4%, partially offset by increased marketing spending and higher commodity costs.

Flagged cause: 8% volume, 2% price/mix, 3% foreign currency fluctuations and (1)% acquisitions and divestitures

Reconstructed request cause (connective plus clause): attributes the consolidated change to 8% volume, 2% price/mix, 3% foreign currency fluctuations and (1)% acquisitions and divestitures

Reconstructed prompt subject: `Management's table`. Anchor: ``.

Supplied-passages assessment: **generic definition without bridge**. Full-excerpt assessment: **supported by explicit table**.

The full MD&A explicitly introduces factors resulting in net operating revenue changes, then labels the consolidated 2026-versus 2025 row Volume 8%, Price/Mix 2%, FX3%, acquisitions/divestitures(1)%, total 12%. The summary transcribes that exact source-owned bridge. Supplied passages discuss definitions and omit the table. Refutation 1: these are the consolidated figures, not a regional row. Refutation 2: the table introduction explicitly assigns growth factors; this is not an analyst-created arithmetic cause. Prospective deletion is unsafe.

### 11. BRK.B 10-K repeat 1 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Net earnings attributable to Berkshire shareholders declined 24.8% to $66.968B in 2025 from $88.995B in 2024. The filing attributes the decline to lower investment gains, which fell to $39.078B pre-tax from $52.799B, and to $8.255B of after-tax other-than-temporary impairment losses recorded on the equity-method investments in Kraft Heinz and Occidental. Insurance underwriting after-tax earnings declined to $7.258B from $9.020B, which management states reflected lower earnings from each of its underwriting groups.

Flagged cause: lower investment gains

Reconstructed request cause (connective plus clause): attributes the decline to lower investment gains

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **wrong subject**. Full-excerpt assessment: **decomposition only**.

The full Berkshire annual earnings decomposition supports lower investment gains and specified impairments, but the flagged lower investment gains is attached to the overall net-earnings decline through The filing attributes. Selected windows instead concern other earnings, recognition policy and a different year/business. Keep the same unresolved component-bridge classification as E2 and run 1; an isolated supported component amount is not proof of an explicit total attribution.

### 12. PFE 10-Q repeat 0 — confirmed rescue

Slot: `the_print.headline`. Recorded verdict: `stated`.

Summary context: Pfizer reported Q1 2026 total revenues of $14.5B (up 5% YoY) and net income attributable to Pfizer Inc. common shareholders of $2.7B ($0.47 diluted EPS), with the revenue increase reflecting an operational increase of $304 million, or 2%, as well as a favorable impact of foreign exchange of $431 million, or 3%.

Flagged cause: an operational increase of $304 million, or 2%, as well as a favorable impact of foreign exchange of $431 million, or 3%

Reconstructed request cause (connective plus clause): reflecting an operational increase of $304 million, or 2%, as well as a favorable impact of foreign exchange of $431 million, or 3%

Reconstructed prompt subject: `common shareholders of $2.7B ($0.47 diluted EPS), with the revenue increase`. Anchor: ``.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Selected passage 1 explicitly reports Q12026 total-revenue growth 736 million/5% to 14.5B, reflecting 304 million/2% operational growth and 431 million/3% favorable FX. Full source is identical. Summary preserves revenue as the cause subject despite preceding NI/EPS and the Inc. sentence-boundary artifact. Supported rescue.

### 13. PFE 10-Q repeat 0 — recorded unknown — unclassified abstention

Slot: `results_that_matter.table[6].commentary`. Recorded verdict: `unknown`.

Summary context: Selling, informational and administrative expenses decreased $70 million in the first quarter of 2026, primarily reflecting a decrease of $100 million in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements; and lower spending of $60 million in corporate enabling function.

Flagged cause: a decrease of $100 million in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements

Reconstructed request cause (connective plus clause): primarily reflecting a decrease of $100 million in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements

Reconstructed prompt subject: `Selling, informational and administrative expenses decreased $70 million in the first quarter of 2026,`. Anchor: `Selling, informational and administrative expenses`.

Supplied-passages assessment: **detached driver bullet**. Full-excerpt assessment: **supported**.

Recorded unknown is an abstention, not a rescue or prospective drop, so classification remains null. Full SIA paragraph explicitly links the 70 million Q12026 decrease to the contiguous 100 million marketing bullet and 60 million corporate-function reduction. Supplied windows contain only the detached marketing bullet and unrelated text. The summary subject/anchor are correct, but model-authored context is not source proof. Abstention is consistent with the new missing-lead-in instruction; it is not evidence that the true claim is unsupported or was deleted.

### 14. F 10-Q repeat 0 — unsafe prospective drop

Slot: `balance_sheet_liquidity.maturities_covenants[0]`. Recorded verdict: `not_stated`.

Summary context: Company excluding Ford Credit total debt payable within one year was $3,268 million at March 31, 2026, down from $5,550 million at December 31, 2025, reflecting the settlement of the $2.3 billion 0.00% Convertible Senior Notes.

Flagged cause: the settlement of the $2.3 billion 0.00% Convertible Senior Notes

Reconstructed request cause (connective plus clause): reflecting the settlement of the $2.3 billion 0.00% Convertible Senior Notes

Reconstructed prompt subject: `Company excluding Ford Credit total debt payable within one year was $3,268 million at March 31, 2026, down from $5,550 million at December 31, 2025,`. Anchor: ``.

Supplied-passages assessment: **partial scope**. Full-excerpt assessment: **supported by anchored note**.

Full Note 12 links footnote(a) to convertible notes falling 2,300 million to zero inside Company-excluding-Ford-Credit debt payable within one year, whose total falls 5,550 to 3,268 million. Footnote states March 16 cash settlement; selected passages contain settlement but not the table anchor. Refutation 1: same entity/debt maturity scope. Refutation 2: actual extinguishment of the identified component, not a claim the full 2,282 million movement equals 2,300 million. Same unsafe prospective drop as E2.

### 15. BA 10-K repeat 1 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: The FY2025 swing to profitability was driven by segment operating earnings of $6,267M versus a $9,764M segment operating loss in FY2024. Management attributes the BGS increase primarily to a gain on the Digital Aviation Solutions Divestiture, the BDS improvement primarily to lower net unfavorable cumulative contract catch-up adjustments, and the BCA improvement primarily to higher deliveries partially offset by higher combined reach-forward losses on the 777X and 767 programs. The Spirit Acquisition closed December 8, 2025, and the Digital Aviation Solutions Divestiture closed October 31, 2025, both affecting the 2025 financial position, results of operations and cash flows.

Flagged cause: segment operating earnings of $6,267M versus a $9,764M segment operating loss in FY2024

Reconstructed request cause (connective plus clause): driven by segment operating earnings of $6,267M versus a $9,764M segment operating loss in FY2024

Reconstructed prompt subject: `The FY2025 swing to profitability was`. Anchor: ``.

Supplied-passages assessment: **narrower measure**. Full-excerpt assessment: **ambiguous subject**.

Full MD&A explains consolidated operating earnings turning positive and the segment contributions; selected passages explicitly attribute core operating earnings change to segment operating earnings, and give 6,267 versus(9,764)million. The summary uses broad swing to profitability, which can mean net profit after non-operating items/tax, rather than the source core-operating subject. This is a plausible accounting bridge but leaves measure scope compressed. Keep unresolved, not a proven invented cause or a confirmed safe deletion.

### 16. INTC 10-Q repeat 0 — confirmed rescue

Slot: `segments[2].commentary`. Recorded verdict: `stated`.

Summary context: 31% operating margin — Management attributes the increase primarily to higher server revenue on a 27% increase in server ASPs, with other DCAI product revenue up on higher networking customer-related demand.

Flagged cause: higher server revenue on a 27% increase in server ASPs

Reconstructed request cause (connective plus clause): attributes the increase primarily to higher server revenue on a 27% increase in server ASPs

Reconstructed prompt subject: `Management`. Anchor: `Datacenter and AI`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

DCAI source explicitly reports revenue up 926 million, principally 696 million higher server revenue due to 27% higher ASPs, with volume down 5%. The segment anchor is Datacenter and AI and the retained segment revenue values identify the increase. Same source-supported DCAI rescue as E2. The prompt subject is merely Management; the machine-generated 31% margin prefix is excluded from causal context and is not being validated here.

### 17. INTC 10-Q repeat 0 — confirmed rescue

Slot: `segments[3].commentary`. Recorded verdict: `stated`.

Summary context: 16% operating margin — Management attributes the decrease primarily to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue of $558 million, up $120 million from Q1 2025, primarily driven by higher demand for Eye Q products.

Flagged cause: higher demand for Eye Q products

Reconstructed request cause (connective plus clause): primarily driven by higher demand for Eye Q products

Reconstructed request cause (connective plus clause): primarily driven by higher demand for Eye Q products

Reconstructed prompt subject: `Management attributes the decrease primarily to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue of $558 million, up $120 million from Q1 2025,`. Anchor: `Other`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Both the selected window and full source state Mobileye revenue 558 million, up 120 million, primarily from higher Eye Q demand. The full source continues across the trademark break to products. The commentary preserves this Mobileye-specific cause within the separate Altera-driven All other decline. This supports the flagged cause, not the adjacent machine-generated margin.

### 18. INTC 10-Q repeat 1 — confirmed rescue

Slot: `segments[2].commentary`. Recorded verdict: `stated`.

Summary context: 31% operating margin — Management attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs, partially offset by a 5% decrease in volume; other DCAI product revenue was $935 million, up $230 million, primarily driven by higher networking customer-related demand.

Flagged cause: $696 million of higher server revenue due to a 27% increase in server ASPs

Reconstructed request cause (connective plus clause): attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs

Reconstructed prompt subject: `Management`. Anchor: `Datacenter and AI`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The source explicitly links the DCAI revenue increase to 696 million higher server revenue and 27% higher ASPs, with the 5% volume offset. This repeats clause 10 with a harmless wording change in the separate networking explanation. Supported flagged cause; the extracted Management subject alone does not establish complete prompt context and the margin prefix is outside this judgment.

### 19. INTC 10-Q repeat 1 — confirmed rescue

Slot: `segments[3].commentary`. Recorded verdict: `stated`.

Summary context: 16% operating margin — Management attributes the decrease primarily to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue of $558 million, up $120 million, primarily driven by higher demand for Eye Q products.

Flagged cause: higher demand for Eye Q products

Reconstructed prompt subject: `Management attributes the decrease primarily to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue of $558 million, up $120 million,`. Anchor: `Other`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Both the selected window and full source state Mobileye revenue 558 million, up 120 million, primarily from higher Eye Q demand. The full source continues across the trademark break to products. The commentary preserves this Mobileye-specific cause within the separate Altera-driven All other decline. This supports the flagged cause, not the adjacent machine-generated margin.

### 20. COIN 10-Q repeat 0 — uncertain drop

Slot: `results_that_matter.table[5].commentary`. Recorded verdict: `not_stated`.

Summary context: Net margin moved to -27.9% from 3.2%, reflecting the swing to a net loss on lower revenue.

Flagged cause: the swing to a net loss on lower revenue

Reconstructed request cause (connective plus clause): reflecting the swing to a net loss on lower revenue

Reconstructed prompt subject: `Net margin moved to -27.9% from 3.2%,`. Anchor: `Net margin`.

Supplied-passages assessment: **partial ratio ingredients**. Full-excerpt assessment: **accounting relationship**.

The full statements report total revenue 1,412.982 versus 2,034.295 million and net loss 394.117 versusincome 65.608 million, consistent with margins-27.9% versus 3.2%. Selected windows give rounded net revenue, a different denominator, and NI values. The summary describes a ratio sign change, not a new operating driver; the issuer does not separately state that derived net-margin explanation. Following E2 XOM margin arithmetic, leave the ratio-policy boundary unresolved rather than equate not_stated with a false calculation.

### 21. COIN 10-Q repeat 1 — uncertain drop

Slot: `results_that_matter.table[7].commentary`. Recorded verdict: `not_stated`.

Summary context: Net margin moved to -27.9% from 3.2%, reflecting the net loss against lower revenue.

Flagged cause: the net loss against lower revenue

Reconstructed request cause (connective plus clause): reflecting the net loss against lower revenue

Reconstructed prompt subject: `Net margin moved to -27.9% from 3.2%,`. Anchor: `Net margin`.

Supplied-passages assessment: **partial ratio ingredients**. Full-excerpt assessment: **accounting relationship**.

Same net-margin identity as clause 20: full total-revenue and NI values support-27.9% versus 3.2%, but selected windows give net revenue and no issuer causal margin statement. The phrase against lower revenue is an accounting relationship. Consistent with E2, keep unresolved rather than count a strict clean safe deletion.

### 22. BABA 20-F repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Income from operations decreased 64% from CNY 140.9B, or 14% of revenue, in fiscal year 2025 to CNY 50.2B, or 5% of revenue, in fiscal year 2026. The filing attributes the decrease primarily to the decrease in adjusted EBITA and increase in impairment of goodwill, partly offset by the decrease in one-time provisions and non-cash share-based expenses. Net income decreased 19% or CNY 23.8B to CNY 102.1B, primarily attributable to the decrease in income from operations, partly offset by the year-over-year increase in net gain from mark-to-market changes of equity investments, as well as net gains from disposal of investments, including local consumer service business of Trendyol in fiscal year 2026, compared to losses on disposal of Sun Art and Intime in fiscal year 2025.

Flagged cause: the decrease in adjusted EBITA and increase in impairment of goodwill

Reconstructed request cause (connective plus clause): attributes the decrease primarily to the decrease in adjusted EBITA and increase in impairment of goodwill

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **detached driver fragment**. Full-excerpt assessment: **supported**.

Full source explicitly reports operating income 140,905 to 50,150 million, down 64%, followed across page 142/Table of Contents by lower adjusted EBITA and higher goodwill impairments with offsets. The summary retains the correct operating-income subject. Selected passages start only at the driver fragment and generic EBITA definition, so this correct full-source rescue does not prove the request supplied enough subject context; the request includes attributes the decrease primarily to, but omits the preceding sentence that identifies operating income; the entity-free pronoun is a distinct context limitation.

### 23. JD 20-F repeat 1 — uncertain drop

Slot: `results_that_matter.table[0].commentary`. Recorded verdict: `not_stated`.

Summary context: The increase was driven by growth across all three reportable segments, with New Businesses net revenues up 157.3% and JD Logistics net revenues up 18.8%.

Flagged cause: growth across all three reportable segments

Reconstructed request cause (connective plus clause): driven by growth across all three reportable segments

Reconstructed prompt subject: `The increase was`. Anchor: `Total net revenues`.

Supplied-passages assessment: **segment definitions**. Full-excerpt assessment: **decomposition with eliminations**.

Full annual Net Revenues discussion gives total growth 13.0%, Retail 10.9%, Logistics 18.8% and New Businesses 157.3%, each with its own underlying drivers. Selected windows only define the segments. The summary preserves correct growth directions but turns component growth into an aggregate attribution; segment revenues include internal business and consolidation eliminations, so they are not an unqualified additive group bridge. Treat as unresolved accounting synthesis, not an explicit source total-growth causal sentence or a demonstrated false amount.

### 24. SE 20-F repeat 0 — unsafe prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total revenue increased 36.4% from US$16.8 billion in 2024 to US$22.9 billion in 2025, and net income increased from US$447.8 million to US$1.6 billion. The filing attributes the revenue increase to growth across its businesses, including e-commerce service revenue growth of 33.9% driven by GMV growth of 26.8% and an increase in the rate of monetization on GMV, digital financial services revenue growth of 60.1% mainly due to growth of the credit business, and digital entertainment revenue growth of 26.1% primarily due to an increase in active user base and deepened paying user penetration.

Flagged cause: growth across its businesses, including e-commerce service revenue growth of 33.9% driven by GMV growth of 26.8% and an increase in the rate of monetization on GMV, digital financial services revenue growth of 60.1% mainly due to growth of the credit business

Reconstructed request cause (connective plus clause): attributes the revenue increase to growth across its businesses, including e-commerce service revenue growth of 33.9% driven by GMV growth of 26.8% and an increase in the rate of monetization on GMV, digital financial services revenue growth of 60.1% mainly due to growth of the credit business

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **supported segment synthesis**.

Full 2025 Revenue section explicitly links Shopee 33.9% growth to GMV26.8% and improved monetization, finance 60.1% to increased credit, and Garena 26.1% to active/paying users, immediately after total revenue 36.4%. The summary preserves the distinct business-driver relationships; the flagged clause ends before Garena. Selected windows are generic synergies/revenue policy, so they omit the real counterpart. Refutation 1: exact 2025-versus 2024 scope. Refutation 2: no single segment cause is transferred to all group revenue; this is the same supported business-specific synthesis rejected in E2.

### 25. SE 20-F repeat 1 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total revenue increased 36.4% from US$16.8 billion in 2024 to US$22.9 billion in 2025, and net income increased from US$447.8 million in 2024 to US$1.6 billion in 2025. The filing attributes the revenue increase to growth in e-commerce service revenue, digital financial services revenue, digital entertainment revenue and sales of goods.

Flagged cause: growth in e-commerce service revenue, digital financial services revenue, digital entertainment revenue and sales of goods

Reconstructed request cause (connective plus clause): attributes the revenue increase to growth in e-commerce service revenue, digital financial services revenue, digital entertainment revenue and sales of goods

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **generic revenue composition**. Full-excerpt assessment: **decomposition only**.

Full 2025 section confirms e-commerce, finance, entertainment and goods revenue all increased, with separate underlying explanations. The selected windows describe revenue composition, not current-year movements. The flagged summary only says total growth came from these components, unlike the explicit underlying business-driver synthesis in clause 24. Preserve aggregate-bridge uncertainty consistently with PLD, JD and run 1 Sea rather than treating component arithmetic as a clean correct deletion.

### 26. PDD 20-F repeat 1 — correct prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Revenue increased 9.7% from CNY 393,836.1 million in 2024 to CNY 431,845.7 million in 2025, which the filing attributes to interrelated factors including a stronger brand and market position, more active merchants offering a greater breadth of products, and continued focus on offering a wide selection of merchandise at attractive prices. Net income decreased to CNY 97,842.5 million from CNY 112,434.5 million, and operating profit decreased to CNY 93,102.1 million from CNY 108,422.9 million, as costs of revenues and operating expenses increased.

Flagged cause: interrelated factors including a stronger brand and market position, more active merchants offering a greater breadth of products

Reconstructed request cause (connective plus clause): attributes to interrelated factors including a stronger brand and market position, more active merchants offering a greater breadth of products

Reconstructed prompt subject: `Revenue increased 9.7% from CNY 393,836.1 million in 2024 to CNY 431,845.7 million in 2025, which the filing`. Anchor: ``.

Supplied-passages assessment: **supports different scope**. Full-excerpt assessment: **wrong subject transfer**.

The full annual revenue paragraph and selected windows explicitly attach stronger branding/merchant breadth/merchandise factors to online marketing services and others, which rose 197,934.2 to 217,783.0 million. Transaction services have a separate explanation: revenue per active merchant and number of merchants. The summary attaches the online-marketing explanation to total revenue 393,836.1 to 431,845.7 million without that scope. This is a strict-rule correct prospective drop for measure transfer, unlike the same-slot run 1 text which retains separate drivers for both components.

## Review method and limits

Three review lenses were applied: source truth (same measure, amount, period, entity and basis); delivery/reconstruction (selected windows, summary context, parsing boundaries and pre/post-binding stages); and measurement validity (clauses versus attempts, uncertain cases, correlated repeats, and absent judge evidence). Every potential unsafe drop was challenged first against the claimed source counterpart and then for whether it transferred a driver between measures, entities or periods. Exact witness/refutation notes are included for the definite unsafe cases. Other arithmetic/component and scope cases are deliberately unresolved.

The five existing E2 manual categories are retained exactly. The historical strict-rule JPM share-denominator and PDD current-assets cases stay comparable; this does not mean their arithmetic is false. New component bridges and ratio identities remain unresolved where the boundary between faithful accounting description and issuer-stated causation is not settled. Detailed business-driver syntheses are distinguished from generic aggregate component-growth claims. These choices are disclosed because a looser policy would change the precision numerator.

Full source means the retained grounding excerpt, not omitted filing pages. The all-flagged scope does not assess recall over unflagged clauses or validate all neighboring commentary. The summaries predate the separate E5 segment-margin fix; an incidental machine-generated margin prefix is not certified by a causal-clause rescue. No Fable call, model replay, cloud action, test, application-code edit or production mutation was performed for this review.

Machine evidence, all four selected windows and full-excerpt hashes are in the adjacent `e3-run2-clause-read.json` report. Pure reconstruction scripts, readable windows and full-source excerpts are retained under `work/e3-*`. The original eval artifact is authoritative; the manual assessments do not replace it.
