# Judged eval report: partial

Source `6af1393efc923b141397e84f91830515ebb50f89`; generator `deepseek-flash`; judge `cli:claude-fable-5-1` (contract version 2); run local.

Attempts 70; judgeable 70; judged 50; errors 20; negative judgments 27.

| gate | attempts failing |
|---|---|
| G2 fabricated_comparatives | 0 |
| G3 hallucinated_facts | 13 |
| G4 unsupported_cause | 14 |
| G5 basis_mismatch | 15 |

## Every judged attempt

| candidate | filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|---|
| baseline | ASML | 6-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | ASML | 6-K | 1 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | SE | 6-K | 0 | FAIL | 4 | 4 | 4 | 5 | G5 basis_mismatch: "Sales of goods consists of sales of products owned and sold by the company on its Shopee platform" — the summary applies the Shopee-specific footnote (Shopee sales of goods US$655,716k) to the consolidated Sales of goods line (US$657,726k), which includes US$2,010k not attributab |
| baseline | SE | 6-K | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "The increase was driven by growth across the reported revenue lines, with service revenue up 48.6% ... and sales of goods up 42.8%" — the source states no driver for consolidated revenue; components summing to the total is arithmetic decomposition, not a cause.; G4 unsupported |
| baseline | PDD | 6-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | PDD | 6-K | 1 | FAIL | 3 | 4 | 4 | 4 | G3 hallucinated_facts: "indicating a current ratio above 2.6x at both dates" — Dec 31, 2025 ratio is 518,981/213,738 = 2.43x, not above 2.6x; only the June 30, 2026 ratio (2.62x) exceeds 2.6x. |
| baseline | PLD | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "The company reports a classified balance sheet." — the consolidated balance sheet in the source is unclassified (no current assets/current liabilities subtotals); the summary asserts the opposite while simultaneously noting current items are not disclosed.; G5 basis_mismatch: |
| baseline | PLD | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NEE | 10-Q | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | NEE | 10-Q | 1 | FAIL | 4 | 3 | 4 | 4 | G4 unsupported_cause: "Operating revenues ... The increase reflects higher results across the consolidated businesses" — the source attributes the NET INCOME increase to 'higher results at FPL, NEER and Corporate and Other'; it states no consolidated driver for the operating revenue increase (the su |
| baseline | PGR | 10-K | 0 | FAIL | 4 | 2 | 4 | 3 | G3 hallucinated_facts: "Progressive’s balance sheet is unclassified, so current assets and current liabilities are not separately reported" — the source excerpt nowhere states the balance sheet is unclassified; this explanatory assertion about the filing is unsupported. |
| baseline | PGR | 10-K | 1 | PASS | 5 | 2 | 4 | 4 |  |
| baseline | FIGS | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Operating income increased as total operating expenses grew 21.9% to $112.6M while net revenues rose 28.8%" — the source states no driver for operating income; this is a summary-constructed explanation (and the wrong mechanism, since operating income = gross profit − opex and  |
| baseline | FIGS | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: executive summary table states gross profit "+44.7%" but source states 44.6% (147,855/102,246 = +44.6%); the summary's own financial_highlights table says 44.6%, so the figure is internally inconsistent and unsupported.; G3 hallucinated_facts: executive summary table states ne |
| baseline | GPRO | 10-K | 0 | FAIL | 4 | 4 | 4 | 4 | G3 hallucinated_facts: "non-GAAP net loss of $47.9M for 2025" — the source reports non-GAAP net loss of $(47,977) thousand, which rounds to $48.0M, not $47.9M (truncation rather than rounding; a figure the source does not contain). |
| baseline | GPRO | 10-K | 1 | FAIL | 4 | 4 | 4 | 5 | G4 unsupported_cause: "Total operating expenses decreased 25.5% to $302.5M from $406.3M, which management attributes primarily to decreases in research and development and sales and marketing expenses." — the source discusses R&D and S&M line-item declines individually but never attributes the total |
| baseline | AAPL | 10-K | 0 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | AAPL | 10-K | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | MSFT | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | MSFT | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NVDA | 10-Q | 0 | PASS | 5 | 4 | 4 | 5 |  |
| baseline | NVDA | 10-Q | 1 | FAIL | 4 | 4 | 4 | 5 | G4 unsupported_cause: "Revenue increased 85% YoY to $81.6B and 20% sequentially, which management attributes to the ramp of Blackwell 300 products and demand for InfiniBand, Spectrum-X Ethernet, and NVLink solutions" (also repeated in the Results table Revenue row) — the source attributes that drive |
| baseline | JPM | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Total net revenue increased 3% to $182.4B, which management attributes to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compr |
| baseline | JPM | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "Return on equity was 15.7% (prior 17.0%) ... return on assets 1.3% (prior 1.5%)" — the filing reports ROE of 17% (2025) and 18% (2024) and ROA of 1.29% and 1.43% under its own definitions (net income applicable to common / average common equity; net income / average assets). The  |
| baseline | KO | 10-Q | 0 | PASS | 5 | 3 | 4 | 5 |  |
| baseline | KO | 10-Q | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | TSLA | 10-K | 0 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | TSLA | 10-K | 1 | FAIL | 4 | 3 | 4 | 4 | G5 basis_mismatch: "management attributes the decrease in total automotive gross margin to a decrease in regulatory credits revenue, partially offset by an improvement in services and other margins" — the source attributes the 'total automotive' gross margin decline (18.4%→17.8%) to regulatory credi |
| baseline | AMZN | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "$1.1 billion related to the resolution of tax disputes associated with its stores business in Italy" — the source states the $1.1 billion related to the Italy tax disputes "and the settlement of a lawsuit"; the summary narrows the full amount to the Italy tax disputes alone, miss |
| baseline | AMZN | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Free cash flow decreased to $11.2B from $38.2B, which the filing attributes to the increase in purchases of property and equipment, net of proceeds from sales and incentives" — the filing presents only the FCF reconciliation table; it contains no sentence attributing the FCF d |
| baseline | BRK.B | 10-K | 0 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch: "Net earnings per average equivalent Class B share (diluted) / $31.04 / $41.27" — the source presents only "Net earnings per average equivalent Class B share"; no basic/diluted distinction is stated, so labeling the measure 'diluted' renames the source's measure.; G4 unsupported_c |
| baseline | BRK.B | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "a $1.1B decline in sales and service revenues to $199.5B" — source shows sales and service revenues of $199,524M vs $202,334M, a $2.8B decline; $1.1B appears nowhere in the source.; G5 basis_mismatch (direction reversed): "Premiums earned increased modestly, with growth at GE |
| baseline | XOM | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | XOM | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "Not separately reported in this filing's standardized data: short-term borrowings; noncurrent long-term debt. Total debt, net debt and debt-to-equity are therefore not stated." and "short-term borrowings and noncurrent long-term debt are not separately reported in the provide |
| baseline | PFE | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch (direction reversed): "partly offset by a $13M loss from discontinued operations in the current period" — a $13M loss from discontinued operations increases the net income decline (2,709 → 2,696 → 2,687); it does not offset it. Also the $2,709M figure is income from continuing oper |
| baseline | PFE | 10-Q | 1 | FAIL | 4 | 3 | 4 | 4 | G3 hallucinated_facts: "The filing does not provide full-year 2026 financial guidance" — the source excerpt never states this; the MD&A is truncated and the filing itself repeatedly references "our financial guidance" (e.g., tariff and policy risk language), so an assertion of absence is unsupported |
| baseline | F | 10-Q | 0 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | F | 10-Q | 1 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | WMT | 10-K | 0 | FAIL | 4 | 3 | 4 | 4 | G5 basis_mismatch: "return on assets 7.7% (prior 7.5%)" — the filing explicitly reports Return on Assets as 8.2% and 7.9% (consolidated net income / average total assets); the summary presents a differently-constructed figure (attributable NI / period-end assets) under the same named measure, contra |
| baseline | WMT | 10-K | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch (direction reversed): "The increase reflects higher consolidated net income, partially offset by a decrease in net income attributable to noncontrolling interest." — NCI attribution fell from $721M to $377M, which reduces the deduction and therefore ADDS to income attributable to W |
| baseline | COST | 10-Q | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | COST | 10-Q | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | BA | 10-K | 0 | PASS | 4 | 4 | 3 | 4 |  |
| baseline | BA | 10-K | 1 | PASS | 4 | 4 | 3 | 4 |  |
| baseline | INTC | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch / G3 hallucinated_facts — Segments table, Intel Products: "Management attributes the increase to higher DCAI revenue on a 22% increase in server ASPs". The source states DCAI revenue increased 22% and server ASPs increased 27%; the summary relabels the DCAI revenue growth rate as t |
| baseline | INTC | 10-Q | 1 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | PLTR | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "remaining performance obligations of $4.5 billion are subject to cancellation" — the source states RPO "represents noncancelable contracted revenue" and that "Cancelable contracted revenue, which includes customer deposits, is not considered a remaining performance obligation |
| baseline | PLTR | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Revenue increased by $749 million, or 85%... which management attributes to increases from both government and commercial customers" — the source only decomposes the increase by segment ($371M government, $377M commercial); segments moving with the total is not a cause and the |
| baseline | RIVN | 10-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | RIVN | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: Risk #3 states 'A significant portion of automotive revenues has been from one customer that is an affiliate of one of the Company's principal stockholders; approximately 37% and 36% of revenues in 2024 and 2025, respectively, were from new EV sales to Chase Bank' — the source |

## #805 negative controls

Filings whose September 9 outputs carried a false explanation over correct figures. The bar for a grounding candidate is abstention here (no G4/G5 failure), not a better average.

| candidate | filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|---|
| baseline | AAPL | 10-K | 0 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | AAPL | 10-K | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | AMZN | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "$1.1 billion related to the resolution of tax disputes associated with its stores business in Italy" — the source states the $1.1 billion related to the Italy tax disputes "and the settlement of a lawsuit"; the summary narrows the full amount to the Italy tax disputes alone, miss |
| baseline | AMZN | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Free cash flow decreased to $11.2B from $38.2B, which the filing attributes to the increase in purchases of property and equipment, net of proceeds from sales and incentives" — the filing presents only the FCF reconciliation table; it contains no sentence attributing the FCF d |
| baseline | BA | 10-K | 0 | PASS | 4 | 4 | 3 | 4 |  |
| baseline | BA | 10-K | 1 | PASS | 4 | 4 | 3 | 4 |  |
| baseline | JPM | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Total net revenue increased 3% to $182.4B, which management attributes to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compr |
| baseline | JPM | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "Return on equity was 15.7% (prior 17.0%) ... return on assets 1.3% (prior 1.5%)" — the filing reports ROE of 17% (2025) and 18% (2024) and ROA of 1.29% and 1.43% under its own definitions (net income applicable to common / average common equity; net income / average assets). The  |
| baseline | NVDA | 10-Q | 0 | PASS | 5 | 4 | 4 | 5 |  |
| baseline | NVDA | 10-Q | 1 | FAIL | 4 | 4 | 4 | 5 | G4 unsupported_cause: "Revenue increased 85% YoY to $81.6B and 20% sequentially, which management attributes to the ramp of Blackwell 300 products and demand for InfiniBand, Spectrum-X Ethernet, and NVLink solutions" (also repeated in the Results table Revenue row) — the source attributes that drive |
| baseline | PFE | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch (direction reversed): "partly offset by a $13M loss from discontinued operations in the current period" — a $13M loss from discontinued operations increases the net income decline (2,709 → 2,696 → 2,687); it does not offset it. Also the $2,709M figure is income from continuing oper |
| baseline | PFE | 10-Q | 1 | FAIL | 4 | 3 | 4 | 4 | G3 hallucinated_facts: "The filing does not provide full-year 2026 financial guidance" — the source excerpt never states this; the MD&A is truncated and the filing itself repeatedly references "our financial guidance" (e.g., tariff and policy risk language), so an assertion of absence is unsupported |
| baseline | PLTR | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "remaining performance obligations of $4.5 billion are subject to cancellation" — the source states RPO "represents noncancelable contracted revenue" and that "Cancelable contracted revenue, which includes customer deposits, is not considered a remaining performance obligation |
| baseline | PLTR | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Revenue increased by $749 million, or 85%... which management attributes to increases from both government and commercial customers" — the source only decomposes the increase by segment ($371M government, $377M commercial); segments moving with the total is not a cause and the |
| baseline | RIVN | 10-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | RIVN | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: Risk #3 states 'A significant portion of automotive revenues has been from one customer that is an affiliate of one of the Company's principal stockholders; approximately 37% and 36% of revenues in 2024 and 2025, respectively, were from new EV sales to Chase Bank' — the source |

This report never automatically arms an AI feature or re-pins a baseline.
