# E3 candidate run 1 — independent all-clause read, 2026-09-19

All 22 flags were read against the reconstructed verifier passages and the full retained grounding excerpt. The manual labels are **3 strict-rule correct prospective drops, 1 unsafe prospective drops, 5 unresolved drops, 11 confirmed full-source rescues and 2 unresolved rescues**. Recorded unknowns: **0**, retained as null classifications rather than counted as rescues or drops. Verification was on and deletion off; **no text was deleted**. These are manual assessments, not Fable judgments.

Artifact: `work/e3-candidate-run1/eval_20260919T192439Z.json`, SHA256 `3f0b4d9cb1ae239526b3302734dde06e3fa479c46f2ef088a0ff88cae077880f`. Recorded source: `d59b0b13fca0ea86a5fe3ade0832f78055b08635`. The artifact has70 scored attempts,0 errors,35 filings and2 repeats with DeepSeek Flash; harness `judge=false`. Run2 source equals the designated E3 worktree HEAD `8a8065b771f4a5d8a0366f1a3b1f535d7305fe19`. Run1 is synthetic merge `d59b0b13fca0ea86a5fe3ade0832f78055b08635`, with parents main `f6f84aa1` and candidate `8a8065b7`. Independently repeating `git diff --exit-code 8a8065b7 d59b0b13 -- backend/app backend/prompts backend/evals` exits0. All70 corresponding grounding excerpts are byte-identical between both E3 reports and both E2 reports. Generated summaries and therefore flagged clauses differ.

Every retained flag record (slot/connective/clause/coverage) exactly matches replay; no missing or extra candidates occur. All 18 flagged-attempt candidate counts match. One checked-count mismatch remains: **SE20-F repeat0 audit8 versus final-payload replay6**, with its sole flagged clause exact. Verification precedes statement binding, which can remove or replace model-authored earnings-quality fields. That stage difference is plausible, but the original pre-binding payload is not retained and the missing checked clauses cannot be reconstructed conclusively. The audit count remains authoritative.

The actual request also includes connective plus clause: an explicit attributed object may survive there even when the separate subject field reads The filing. The subject field alone must not be treated as the entire request. Pronoun antecedents from earlier sentences may still be absent.

The supplied passages and bounded subject/anchor fields are deterministic reconstructions using source-equivalent code, not saved provider request logs. Raw verifier quotes/reasons are not retained. All clauses have unique slots in these reports; no duplicate-slot verdict ambiguity was found.

## Decision denominators

- Recorded labels: 9 `not_stated`, 13 `stated`, 0 `unknown`.
- Confirmed correct-drop fraction: 3/9 = 33.3%.
- Classification bound if every unresolved drop were correct: 33.3%–88.9%. This is not a confidence interval.
- Correct fraction among decidable drops only: 75.0%, excluding 5 unresolved cases.
- Confirmed full-source rescues: 11/13 = 84.6%. Correct source truth does not establish sufficient selected evidence or correct unretained model reasoning.

## Every flagged clause

### 1. ASML 6-K repeat 0 — uncertain rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Total net sales rose from €8,767M in Q1 2026 to €9,326M in Q2 2026, gross margin rose from 53.0% to 54.0%, and net income rose from €2,757M to €2,918M. The filing attributes the Q2 result to higher than expected Installed Base Management sales, which rose from €2,488M to €2,762M. New lithography systems sold increased from 67 to 86 units, while used lithography systems sold decreased from 12 to 5 units. End-quarter cash and cash equivalents and short-term investments decreased from €8,376M to €7,582M.

Flagged cause: higher than expected Installed Base Management sales

Reconstructed request cause (connective plus clause): attributes the Q2 result to higher than expected Installed Base Management sales

Reconstructed request cause (connective plus clause): attributes the Q2 result to higher than expected Installed Base Management sales

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **supported narrower subject**. Full-excerpt assessment: **ambiguous subject**.

The CEO states Q2 revenue of EUR9.3B and gross margin 54.0%, both above guidance, driven by higher-than-expected Installed Base Management sales. The summary first lists revenue, gross margin and net income growth then says Q2 result. Its subject can include net income or sequential change, which the source does not explicitly explain. Preserve the E2 run 1 ambiguous-rescue classification; the presence of the correct driver does not establish that broader subject. The separate subject field is The filing, but the request connective retains the Q2 result; the ambiguity is the broad result label, not loss of that object.

### 2. ASML 6-K repeat 1 — uncertain rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Total net sales rose from €8,767M in Q1 2026 to €9,326M in Q2 2026, gross margin rose from 53.0% to 54.0%, and net income rose from €2,757M to €2,918M. The filing attributes the Q2 result to higher than expected Installed Base Management sales, and states that order intake remained extremely strong in the first half of the year.

Flagged cause: higher than expected Installed Base Management sales

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **supported narrower subject**. Full-excerpt assessment: **ambiguous subject**.

Same scope ambiguity as clause 1: Q2 result follows revenue, gross margin and net income comparisons, while the CEO attributes revenue/gross-margin performance above guidance. The supplied windows contain that narrower source. The correct driver words do not resolve whether the summary transfers the cause to net income or sequential change; classify consistently with the E2 broad-result case.

### 3. PDD 6-K repeat 1 — correct prospective drop

Slot: `balance_sheet_liquidity.working_capital`. Recorded verdict: `not_stated`.

Summary context: Total current assets were RMB556.8 billion and total current liabilities were RMB212.7 billion as of June 30, 2026, versus RMB519.0 billion and RMB213.7 billion as of December 31, 2025; the increase in current assets was driven mainly by higher cash and cash equivalents and short-term investments.

Flagged cause: higher cash and cash equivalents and short-term investments

Reconstructed request cause (connective plus clause): driven mainly by higher cash and cash equivalents and short-term investments

Reconstructed prompt subject: `Total current assets were RMB556.8 billion and total current liabilities were RMB212.7 billion as of June 30, 2026, versus RMB519.0 billion and RMB213.7 billion as of December 31, 2025; the increase in current assets was`. Anchor: ``.

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

The full balance sheet supports current assets 518,981 to 556,780 million and higher cash 108,901 to 128,918 plus short-term investments 313,408 to 327,496. The prose reports aggregate cash/investments but does not explicitly state the cause of the current-assets increase. Following the identical E2 case, this is a strict issuer-stated-rule correct prospective drop, not an assertion that the arithmetic is false.

### 4. FIGS 10-Q repeat 1 — uncertain drop

Slot: `results_that_matter.table[5].commentary`. Recorded verdict: `not_stated`.

Summary context: Diluted EPS increased alongside net income; the diluted share count rose to 195.1 million from 172.9 million, reflecting the dilutive effect of stock options and restricted stock units.

Flagged cause: the dilutive effect of stock options and restricted stock units

Reconstructed request cause (connective plus clause): reflecting the dilutive effect of stock options and restricted stock units

Reconstructed prompt subject: `Diluted EPS increased alongside net income; the diluted share count rose to 195.1 million from 172.9 million,`. Anchor: `Diluted earnings per share`.

Supplied-passages assessment: **denominator components**. Full-excerpt assessment: **decomposition only**.

The EPS note labels effects of dilutive options 24,618,190 versus 8,978,297 and restricted units 4,053,819 versus 1,268,334, alongside basic shares 166,467,633 versus 162,683,329 and diluted shares 195,139,642 versus 172,929,960 for the quarter. Those dilution effects account for most of the diluted-share increase, but the basic-share increase also contributes. The source labels a denominator decomposition, not an explicit explanation of its year-over-year change. Keep the level/change and arithmetic-policy boundary unresolved rather than declaring the component evidence absent or the explanation false.

### 5. JPM 10-K repeat 0 — correct prospective drop

Slot: `results_that_matter.table[7].commentary`. Recorded verdict: `not_stated`.

Summary context: Diluted EPS increased 1.4% while net income declined 2.4%, reflecting a lower weighted-average diluted share count of 2,781.5 million versus 2,879.0 million.

Flagged cause: a lower weighted-average diluted share count of 2,781.5 million versus 2,879.0 million

Reconstructed request cause (connective plus clause): reflecting a lower weighted-average diluted share count of 2,781.5 million versus 2,879.0 million

Reconstructed prompt subject: `Diluted EPS increased 1.4% while net income declined 2.4%,`. Anchor: `Diluted earnings per share`.

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

Full annual comparisons give net income 57,048 versus 58,471 million, diluted EPS20.02 versus 19.75 and diluted shares 2,781.5 versus 2,879.0. The selected EPS/share tables contain the numerical ingredients but no issuer sentence linking the EPS increase to lower shares. Same strict-rule classification as both E2 runs; this does not contest denominator arithmetic.

### 6. JPM 10-K repeat 0 — correct prospective drop

Slot: `results_that_matter.table[8].commentary`. Recorded verdict: `not_stated`.

Summary context: Basic EPS increased 1.3% while net income declined 2.4%, reflecting a lower weighted-average basic share count of 2,776.5 million versus 2,873.9 million.

Flagged cause: a lower weighted-average basic share count of 2,776.5 million versus 2,873.9 million

Reconstructed request cause (connective plus clause): reflecting a lower weighted-average basic share count of 2,776.5 million versus 2,873.9 million

Reconstructed prompt subject: `Basic EPS increased 1.3% while net income declined 2.4%,`. Anchor: `Basic earnings per share`.

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

The basic EPS counterpart is 20.05 versus 19.79 with basic shares 2,776.5 versus 2,873.9 million and lower net income. The retained excerpt supplies these figures, not an issuer-stated causal link explaining EPS growth. Apply the same strict issuer-stated rule as the diluted EPS case and E2, without alleging wrong arithmetic.

### 7. BRK.B 10-K repeat 0 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total revenues were $371.4B in 2025 versus $371.4B in 2024 and $364.5B in 2023. Net earnings attributable to Berkshire shareholders declined to $67.0B in 2025 from $89.0B in 2024 and $96.2B in 2023. The filing attributes the 2025 decline in part to lower investment gains and to other-than-temporary impairment losses recorded on the Kraft Heinz and Occidental equity method investments; it also states that investment gains and losses are generally meaningless in understanding reported periodic results or evaluating periodic economic performance.

Flagged cause: lower investment gains and to other-than-temporary impairment losses recorded on the Kraft Heinz and Occidental equity method investments

Reconstructed request cause (connective plus clause): attributes the 2025 decline in part to lower investment gains and to other-than-temporary impairment losses recorded on the Kraft Heinz and Occidental equity method investments

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **partial bridge**. Full-excerpt assessment: **decomposition only**.

Full MD&A decomposes Berkshire net earnings and discusses lower investment gains, the 2025 Kraft Heinz/Occidental impairment losses and investment-gain volatility. The supplied windows contain the impairments and generic volatility but not the whole annual net-earnings bridge. A contribution to the decline is plausible; the summary presents it as an explicit filing attribution. Consistent with E2, the component-bridge versus stated-causation boundary remains unresolved.

### 8. XOM 10-K repeat 1 — uncertain drop

Slot: `the_print.key_takeaways[1]`. Recorded verdict: `not_stated`.

Summary context: Diluted EPS declined to $6.70 from $7.84; the weighted-average share count rose to 4,305 million from 4,298 million, reflecting 545 million shares issued for the Pioneer acquisition on May 3, 2024.

Flagged cause: 545 million shares issued for the Pioneer acquisition on May 3, 2024

Reconstructed request cause (connective plus clause): reflecting 545 million shares issued for the Pioneer acquisition on May 3, 2024

Reconstructed prompt subject: `Diluted EPS declined to $6.70 from $7.84; the weighted-average share count rose to 4,305 million from 4,298 million,`. Anchor: ``.

Supplied-passages assessment: **footnote without change bridge**. Full-excerpt assessment: **level vs change**.

Note 2 attaches the 545 million Pioneer issuance footnote to the weighted-average shares row 4,305 versus 4,298 million. The acquisition was May 3,2024, so the shares are included for different portions of the two comparison years; the footnote says includes and does not quantify the net annual movement or buyback offsets. The source establishes an actual issuance and denominator inclusion, but not that the 7 million net change is explained by that issuance alone. Treat as unresolved timing/component shorthand, distinct from Ford extinguishing a specifically identified current-debt component.

### 9. WMT 10-K repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Total revenues increased $32.2B, or 4.7%, for fiscal 2026, primarily due to a $31.9B, or 4.7%, increase in net sales. The filing attributes the net sales increase primarily to positive comparable sales across the U.S. segments and international markets, with fiscal 2026 growth primarily driven by increases in average ticket and transactions and also reflecting growth in unit volumes. Net sales were negatively impacted by $2.8B of fluctuations in currency exchange rates. Operating income as a percentage of net sales decreased 13 basis points, which the filing attributes primarily to higher self-insured general liability claims expense in the U.S. of approximately $0.9B, a $0.7B charge related to modification of certain share-based compensation arrangements for the PhonePe subsidiary, and increased depreciation related to capital investments, partially offset by growth in membership income globally.

Flagged cause: positive comparable sales across the U.S

Reconstructed request cause (connective plus clause): attributes the net sales increase primarily to positive comparable sales across the U.S

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The same MD&A sequence explicitly links total revenue growth to net sales and net-sales growth to strong positive comparable sales across U.S. segments and international markets. Supplied passages 2/3 retain that linkage. The parser truncates U.S. at the abbreviation, but the complete summary and full source agree on entity and fiscal 2026 scope. Supported full-source rescue; no endorsement of unrelated neighboring causes is implied.

### 10. INTC 10-Q repeat 0 — confirmed rescue

Slot: `segments[2].commentary`. Recorded verdict: `stated`.

Summary context: 31% operating margin — Management attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs, partially offset by a 5% decrease in volume; other DCAI product revenue was $935 million, up $230 million, primarily driven by higher networking customer-related demand.

Flagged cause: $696 million of higher server revenue due to a 27% increase in server ASPs

Reconstructed request cause (connective plus clause): attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs

Reconstructed request cause (connective plus clause): attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs

Reconstructed prompt subject: `Management`. Anchor: `Datacenter and AI`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

DCAI source explicitly reports revenue up 926 million, principally 696 million higher server revenue due to 27% higher ASPs, with volume down 5%. The segment anchor is Datacenter and AI and the retained segment revenue values identify the increase. Same source-supported DCAI rescue as E2. The prompt subject is merely Management; the machine-generated 31% margin prefix is excluded from causal context and is not being validated here.

### 11. INTC 10-Q repeat 0 — confirmed rescue

Slot: `segments[3].commentary`. Recorded verdict: `stated`.

Summary context: 16% operating margin — Management attributes the decrease primarily to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue, which totaled $558 million, up $120 million, primarily driven by higher demand for Eye Q products.

Flagged cause: higher demand for Eye Q products

Reconstructed request cause (connective plus clause): primarily driven by higher demand for Eye Q products

Reconstructed prompt subject: `Management attributes the decrease primarily to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue, which totaled $558 million, up $120 million,`. Anchor: `Other`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Both the selected window and full source state Mobileye revenue 558 million, up 120 million, primarily from higher Eye Q demand. The full source continues across the trademark break to products. The commentary preserves this Mobileye-specific cause within the separate Altera-driven All other decline. This supports the flagged cause, not the adjacent machine-generated margin.

### 12. INTC 10-Q repeat 1 — confirmed rescue

Slot: `segments[2].commentary`. Recorded verdict: `stated`.

Summary context: 31% operating margin — Management attributes the increase primarily to $696 million of higher server revenue due to a 27% increase in server ASPs, partially offset by a 5% decrease in volume; other DCAI product revenue was $935 million, up $230 million on higher networking customer-related demand.

Flagged cause: $696 million of higher server revenue due to a 27% increase in server ASPs

Reconstructed prompt subject: `Management`. Anchor: `Datacenter and AI`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The source explicitly links the DCAI revenue increase to 696 million higher server revenue and 27% higher ASPs, with the 5% volume offset. This repeats clause 10 with a harmless wording change in the separate networking explanation. Supported flagged cause; the extracted Management subject alone does not establish complete prompt context and the margin prefix is outside this judgment.

### 13. COIN 10-Q repeat 0 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Total revenue decreased 30.5% YoY to $1.41B from $2.03B, and the company reported a net loss of $394.1M versus net income of $65.6M in the prior-year quarter. The filing attributes the transaction revenue decline primarily to a $591.6M decrease in consumer transaction revenue driven by a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading. Subscription and services revenue decreased 14% YoY, reflecting lower blockchain rewards and lower average interest rates, offset in part by higher stablecoin revenue.

Flagged cause: a $591.6M decrease in consumer transaction revenue driven by a 54% decrease in consumer Trading Volume

Reconstructed request cause (connective plus clause): attributes the transaction revenue decline primarily to a $591.6M decrease in consumer transaction revenue driven by a 54% decrease in consumer Trading Volume

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **supported contiguous leadin**. Full-excerpt assessment: **supported**.

The selected passage includes the transaction-revenue-decrease lead-in and its contiguous consumer-revenue bullet, with 591.6 million decrease attributed to 54% lower consumer Trading Volume. Full source matches the quarter and offsets. This is a supported transaction-revenue explanation, not a transfer of the driver to the preceding net loss.

### 14. BABA 20-F repeat 0 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: Revenue increased 3% to CNY 1,023.7B while net income decreased 19% to CNY 102.1B and income from operations decreased 64% to CNY 50.2B. The filing attributes the operating income decline primarily to the decrease in adjusted EBITA and increase in impairment of goodwill, partly offset by the decrease in one-time provisions and non-cash share-based expenses.

Flagged cause: the decrease in adjusted EBITA and increase in impairment of goodwill

Reconstructed request cause (connective plus clause): attributes the operating income decline primarily to the decrease in adjusted EBITA and increase in impairment of goodwill

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **detached driver fragment**. Full-excerpt assessment: **supported**.

Full source explicitly reports operating income 140,905 to 50,150 million, down 64%, followed across page 142/Table of Contents by lower adjusted EBITA and higher goodwill impairments with offsets. The summary retains the correct operating-income subject. Selected passages start only at the driver fragment and generic EBITA definition, so this correct full-source rescue does not prove the request supplied enough subject context; the request connective retains operating income decline, but the selected source does not retain its causal lead-in.

### 15. TSM 20-F repeat 0 — confirmed rescue

Slot: `earnings_quality.operating_vs_one_time`. Recorded verdict: `stated`.

Summary context: Net other operating income and expenses in 2025 increased by TWD 1,677 million from 2024 to a net gain of TWD 447 million (US$14 million), which the filing attributes mainly to lower loss on disposal of property, plant and equipment and reversal of impairment losses in 2025. Net non-operating income increased 26.0% to TWD 105,563 million, mainly due to higher interest income of TWD 18,526 million compared to 2024. The filing also discloses earthquake losses of approximately TWD 3 billion in the second quarter of 2024 and TWD 5.3 billion in the first quarter of 2025, net of insurance claims.

Flagged cause: higher interest income of TWD 18,526 million compared to 2024

Reconstructed request cause (connective plus clause): attributes mainly to higher interest income of TWD 18,526 million compared to 2024

Reconstructed request cause (connective plus clause): mainly due to higher interest income of TWD 18,526 million compared to 2024

Reconstructed prompt subject: `Net non-operating income increased 26.0% to TWD 105,563 million,`. Anchor: ``.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The same full-source table identifies net non-operating income 105,563 million and 26.0% growth; the immediately following sentence explicitly attributes the 21,776 million increase to 18,526 million higher interest income. Selected passages include this sentence. The summary accurately retains the measure, year and driver; TWD versus NT$ is a currency-name restatement.

### 16. TSM 20-F repeat 1 — confirmed rescue

Slot: `earnings_quality.operating_vs_one_time`. Recorded verdict: `stated`.

Summary context: Net other operating income and expenses in 2025 increased by TWD 1,677 million from 2024 to a net gain of TWD 447 million (US$14 million), which the filing attributes mainly to lower loss on disposal of property, plant and equipment and reversal of impairment losses in 2025. Net non-operating income in 2025 increased by TWD 21,776 million, or 26.0%, from 2024, which the filing attributes mainly to higher interest income of TWD 18,526 million compared to 2024. The filing does not define an adjusted or ex-item earnings total.

Flagged cause: higher interest income of TWD 18,526 million compared to 2024

Reconstructed prompt subject: `Net non-operating income in 2025 increased by TWD 21,776 million, or 26.0%, from 2024, which the filing`. Anchor: ``.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

As in clause 15, source explicitly states 2025 non-operating income/expenses increased 21,776 million or 26.0%, mainly due to 18,526 million higher interest income. This version preserves the increase amount directly. Selected and full source support the same subject and period.

### 17. SE 20-F repeat 0 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total revenue increased 36.4% from US$16.8 billion in 2024 to US$22.9 billion in 2025, and net income increased from US$447.8 million to US$1.6 billion over the same period. The filing attributes the revenue increase to growth across the e-commerce, digital financial services and digital entertainment businesses, and states that the higher net income resulted from the foregoing changes in revenue, cost of revenue and operating expenses.

Flagged cause: growth across the e-commerce, digital financial services and digital entertainment businesses

Reconstructed request cause (connective plus clause): attributes the revenue increase to growth across the e-commerce, digital financial services and digital entertainment businesses

Reconstructed prompt subject: `The filing`. Anchor: ``.

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **decomposition only**.

Full 2025 Revenue section starts with total revenue growth 36.4% and then details Shopee 33.9%, finance 60.1%, Garena 26.1%, and sales of goods 30.0% growth. The flagged sentence gives only a broad aggregate attribution to three businesses, without their issuer-stated underlying drivers. Selected windows instead show generic synergies and 2024 marketing expenses. Unlike the detailed E2 segment-driver synthesis, this is a component-growth bridge; keep uncertain consistently with PLD rather than infer an explicit total-revenue causal sentence.

### 18. PDD 20-F repeat 0 — uncertain drop

Slot: `results_that_matter.table[0].commentary`. Recorded verdict: `not_stated`.

Summary context: Revenue growth was driven by both reported revenue lines; the filing attributes the increase in online marketing services and others to interrelated factors including branding campaigns, more active merchants offering a greater breadth of products, and a focus on offering a wide selection of merchandise at attractive prices, and attributes the increase in transaction services primarily to the increase in average transaction services revenues per active merchant and the increase in the number of active merchants.

Flagged cause: both reported revenue lines

Reconstructed request cause (connective plus clause): driven by both reported revenue lines

Reconstructed prompt subject: `Revenue growth was`. Anchor: `Total revenues`.

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **decomposition only**.

The full annual discussion says total revenue consists of online marketing/other and transaction services and both increased, with separate drivers stated for each. The summary retains those separate source-supported drivers after the flagged both reported revenue lines. That flagged phrase is a component bridge, not an explicit issuer total-growth attribution. Selected windows only discuss revenue recognition. Consistent with PLD component bridges, preserve policy uncertainty rather than call this numerical error or a clear safe deletion.

### 19. PDD 20-F repeat 0 — unsafe prospective drop

Slot: `results_that_matter.table[1].commentary`. Recorded verdict: `not_stated`.

Summary context: Operating profit declined as costs of revenues and total operating expenses increased; the filing states the operating profit result as a consequence of the foregoing revenue and expense movements without attributing the decline to a single driver.

Flagged cause: a single driver

Reconstructed request cause (connective plus clause): attributing the decline to a single driver

Reconstructed prompt subject: `Operating profit declined as costs of revenues and total operating expenses increased; the filing states the operating profit result as a consequence of the foregoing revenue and expense movements without`. Anchor: `Operating profit`.

Supplied-passages assessment: **wrong context**. Full-excerpt assessment: **negated attribution supported context**.

The scanner flags attributing to a single driver inside without attributing the decline to a single driver. This is a negated assertion, not a claim that one driver caused the result. Full source says operating profit 93,102.1 versus 108,422.9 million is as a result of the foregoing, after revenue/cost/expense discussion. Removing this explanatory caution would be unsafe. Refutation 1: read the full sentence, including without, rather than the isolated clause. Refutation 2: the full operating-profit paragraph confirms the source presents the collective foregoing bridge, not a single cause.

### 20. PDD 20-F repeat 1 — confirmed rescue

Slot: `results_that_matter.table[1].commentary`. Recorded verdict: `stated`.

Summary context: The filing states operating profit was CNY 93,102.1 million (US$13,313.4 million) in 2025, compared to CNY 108,422.9 million in 2024, as a result of the foregoing revenue and expense movements.

Flagged cause: the foregoing revenue and expense movements

Reconstructed request cause (connective plus clause): as a result of the foregoing revenue and expense movements

Reconstructed prompt subject: `The filing states operating profit was CNY 93,102.1 million (US$13,313.4 million) in 2025, compared to CNY 108,422.9 million in 2024,`. Anchor: `Operating profit`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The full source and supplied passage 1 explicitly say operating profit 93,102.1 versus 108,422.9 million is as a result of the foregoing, immediately after revenue and expense discussion. The summary preserves the operating-profit subject rather than transferring a net-income sentence. Supported faithful restatement.

### 21. PDD 20-F repeat 1 — confirmed rescue

Slot: `results_that_matter.table[2].commentary`. Recorded verdict: `stated`.

Summary context: The filing states net income was CNY 97,842.5 million (US$13,991.3 million) in 2025, compared to CNY 112,434.5 million in 2024, as a result of the foregoing items.

Flagged cause: the foregoing items

Reconstructed request cause (connective plus clause): as a result of the foregoing items

Reconstructed prompt subject: `The filing states net income was CNY 97,842.5 million (US$13,991.3 million) in 2025, compared to CNY 112,434.5 million in 2024,`. Anchor: `Net income`.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

Source and supplied passages 2/3 explicitly state net income 97,842.5 versus 112,434.5 million as a result of the foregoing. The summary uses the same measure and year with no invented single driver. The referent includes operating and non-operating items, tax and investees, consistent with foregoing items.

### 22. MELI 10-K repeat 0 — confirmed rescue

Slot: `the_print.key_takeaways[3]`. Recorded verdict: `stated`.

Summary context: Provision for doubtful accounts increased 66.4% to $3.1B, driven by 61% growth in loan originations.

Flagged cause: 61% growth in loan originations

Reconstructed request cause (connective plus clause): driven by 61% growth in loan originations

Reconstructed prompt subject: `Provision for doubtful accounts increased 66.4% to $3.1B,`. Anchor: ``.

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The provision table reports 3,091 versus 1,858 million, a 66.4% increase. Its immediately following annual explanation attributes the 1,233 million increase mainly to 61% originations growth for credit card, consumer and merchant products. Supplied passage 1 contains that link. The summary states the increase, not an unsupported stock-level explanation.

## Review method and limits

Three review lenses were applied: source truth (same measure, amount, period, entity and basis); delivery/reconstruction (selected windows, summary context, parsing boundaries and pre/post-binding stages); and measurement validity (clauses versus attempts, uncertain cases, correlated repeats, and absent judge evidence). Every potential unsafe drop was challenged first against the claimed source counterpart and then for whether it transferred a driver between measures, entities or periods. Exact witness/refutation notes are included for the definite unsafe cases. Other arithmetic/component and scope cases are deliberately unresolved.

The five existing E2 manual categories are retained exactly. The historical strict-rule JPM share-denominator and PDD current-assets cases stay comparable; this does not mean their arithmetic is false. New component bridges and ratio identities remain unresolved where the boundary between faithful accounting description and issuer-stated causation is not settled. Detailed business-driver syntheses are distinguished from generic aggregate component-growth claims. These choices are disclosed because a looser policy would change the precision numerator.

Full source means the retained grounding excerpt, not omitted filing pages. The all-flagged scope does not assess recall over unflagged clauses or validate all neighboring commentary. The summaries predate the separate E5 segment-margin fix; an incidental machine-generated margin prefix is not certified by a causal-clause rescue. No Fable call, model replay, cloud action, test, application-code edit or production mutation was performed for this review.

Machine evidence, all four selected windows and full-excerpt hashes are in the adjacent `e3-run1-clause-read.json` report. Pure reconstruction scripts, readable windows and full-source excerpts are retained under `work/e3-*`. The original eval artifact is authoritative; the manual assessments do not replace it.
