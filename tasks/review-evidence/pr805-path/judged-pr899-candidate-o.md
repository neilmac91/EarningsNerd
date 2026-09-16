# Judged eval report: complete

Source `d008c1e99aad830e96dd910134ddf169d0d75e5e`; generator `deepseek-flash`; judge `cli:claude-fable-5-1` (contract version 2); run local.

Attempts 70; judgeable 70; judged 70; errors 0; negative judgments 38.

| gate | attempts failing |
|---|---|
| G2 fabricated_comparatives | 1 |
| G3 hallucinated_facts | 15 |
| G4 unsupported_cause | 19 |
| G5 basis_mismatch | 17 |

## Every judged attempt

| candidate | filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|---|
| baseline | ASML | 6-K | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | ASML | 6-K | 1 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | SE | 6-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Provision for credit losses increased 71.5% YoY to US$555.2M, driven by growth in the credit business." — the source's provision-for-credit-losses section states only the increase with no driver; the 'growth of our credit business' cause is given for Monee revenue, and does no |
| baseline | SE | 6-K | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | PDD | 6-K | 0 | FAIL | 4 | 4 | 4 | 4 | G4 unsupported_cause: "Increased ecosystem investments, including sales and marketing expenses, may continue to pressure profitability" — the source never links Ms. Liu's "ecosystem investments" to sales and marketing expenses; the summary fuses two separate statements into an attribution the filing |
| baseline | PDD | 6-K | 1 | FAIL | 4 | 4 | 3 | 4 | G4 unsupported_cause: "the increase in current assets was driven mainly by cash and cash equivalents and short-term investments" — the source states no driver for the change in total current assets; this is a component moving with the total, presented as a cause. |
| baseline | PLD | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | PLD | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "The decrease [in net earnings attributable to controlling interests] was primarily due to lower gains on real estate dispositions and higher interest expense, partially offset by increased rental revenues" — the source states no driver for the net earnings decline; this is the |
| baseline | NEE | 10-Q | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | NEE | 10-Q | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | PGR | 10-K | 0 | PASS | 4 | 2 | 3 | 3 |  |
| baseline | PGR | 10-K | 1 | FAIL | 3 | 2 | 4 | 3 | G5 basis_mismatch: "Personal Lines premium revenue of $72.6B" — Schedule III shows Personal Lines premium revenue (earned) of $70,778M ($70.8B); $72,558M ($72.6B) is the Net premiums written column. The summary swaps written for earned, and the stated segment figures ($72.6B + $10.9B = $83.5B) excee |
| baseline | FIGS | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G4 unsupported_cause: "Diluted EPS increased, reflecting higher net income and a higher diluted share count" — the source states no driver for the EPS movement, and a higher diluted share count (195.1M vs 172.9M) mechanically reduces EPS rather than explaining its increase; the attribution is both u |
| baseline | FIGS | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: executive summary table states gross profit "+44.7%" — the source explicitly states 44.6% ($147,855 vs $102,246 = +44.6%); the summary's own financial_highlights table says 44.6%, so the figure is both unsupported and internally inconsistent.; G3 hallucinated_facts: executive  |
| baseline | GPRO | 10-K | 0 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | GPRO | 10-K | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | AAPL | 10-K | 0 | FAIL | 3 | 3 | 4 | 4 | G4 unsupported_cause: "Total net sales ... Management attributed the increase primarily to higher net sales of iPhone and Services." (executive summary table and financial_highlights) — the source states this driver only for Americas net sales ("Americas net sales increased during 2025 compared to 2 |
| baseline | AAPL | 10-K | 1 | PASS | 5 | 3 | 3 | 4 |  |
| baseline | MSFT | 10-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | MSFT | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NVDA | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G2/G3 fabricated_comparative: "accounts receivable, net increased to $40,710M from $38,466M, both growing faster than the 20% sequential revenue increase" — AR grew ~5.8% ($38,466M→$40,710M), well below the 20% sequential revenue growth; the 'both growing faster' claim is false (inventories +20.5% i |
| baseline | NVDA | 10-Q | 1 | FAIL | 3 | 4 | 4 | 4 | G3 hallucinated_facts: Risk #2 'supporting evidence' is presented as a verbatim quote but alters the source text — summary reads 'for our non-diluted data center products' whereas the filing says 'for our non-data center products'; the phrase 'non-diluted data center products' does not appear in the |
| baseline | JPM | 10-K | 0 | FAIL | 3 | 2 | 3 | 3 | G5 basis_mismatch (period): "The prior year included an estimated bargain purchase gain of $2.8 billion associated with the First Republic acquisition" — the source attributes the $2.8B bargain purchase gain to the year ended December 31, 2023, not the prior year (2024); the summary's own supporting |
| baseline | JPM | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Total net revenue increased 3% to $182.4B, driven by higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compression and the impact |
| baseline | KO | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: Segment table states "42% operating margin" for EMEA and "36% operating margin" for A. Pacific, computed from XBRL segment revenue (incl. intersegment scope) — the filing's own operating margin table reports EMEA 44.8% and Asia Pacific 37.6%; the summary relabels a ratio on a diff |
| baseline | KO | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch: Segments table states EMEA "42% operating margin" but the filing's own operating margin table reports EMEA at 44.8%; the summary computed a margin on a different (XBRL segment) revenue basis and presented it under the filing's named measure without caveat.; G5 basis_mismatch: Segm |
| baseline | TSLA | 10-K | 0 | PASS | 5 | 3 | 4 | 5 |  |
| baseline | TSLA | 10-K | 1 | FAIL | 4 | 3 | 4 | 4 | G4 unsupported_cause: "Operating income declined $2.72B YoY, reflecting a $1.87B or 41% increase in R&D expense to $6.41B, a $684M or 13% increase in SG&A to $5.83B, and $494M of restructuring and other charges in 2025" — restructuring and other fell from $684M to $494M (a $190M YoY tailwind), so th |
| baseline | AMZN | 10-K | 0 | FAIL | 4 | 4 | 3 | 4 | G5 basis_mismatch: "free cash flow of $7.7B (derived as operating cash flow minus the absolute selected capex cash-flow amount; not an issuer-defined or discretionary-cash measure)" — the filing defines and reconciles free cash flow as $11,194M (OCF less purchases of property and equipment net of pr |
| baseline | AMZN | 10-K | 1 | FAIL | 4 | 3 | 3 | 4 | G3 hallucinated_facts: Executive summary Results table states net income change as "+31.2%" ($77.7B vs $59.2B); source figures ($77,670M / $59,248M) yield +31.1% (XBRL: 31.09%), and the summary's own financial_highlights table says "up 31.1% YoY" — the 31.2% figure is unsupported and internally inco |
| baseline | BRK.B | 10-K | 0 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: "Premiums earned increased modestly, with growth at GEICO and BH Primary partially offset by lower property/casualty reinsurance premiums earned at BHRG" — BH Primary premiums earned declined ($18,713M vs $18,733M) and premiums written were 'slightly lower'; no growth at BH Pr |
| baseline | BRK.B | 10-K | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch: "Net earnings per average equivalent Class B share (diluted)" / "diluted equivalent Class B EPS of $31.04" — the source presents only 'Net earnings per average equivalent Class B share' with no diluted designation; the summary relabels the measure.; G5 basis_mismatch: "Sales and s |
| baseline | XOM | 10-K | 0 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: "short-term borrowings and noncurrent long-term debt are not separately reported in the provided excerpt" — the balance sheet in the source explicitly reports Notes and loans payable of $9,296M and Long-term debt of $34,241M (which the same bullet even cites), so the claim con |
| baseline | XOM | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | PFE | 10-Q | 0 | FAIL | 4 | 3 | 4 | 4 | G5 basis_mismatch: "from program start through March 29, 2026, total costs incurred were $4.3 billion, including $2.9 billion of restructuring charges" — the source states the $2.9 billion of restructuring charges is a component of the $3.3 billion Biopharma-segment portion ("of which $3.3 billion i |
| baseline | PFE | 10-Q | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | F | 10-Q | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | F | 10-Q | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | WMT | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | WMT | 10-K | 1 | FAIL | 3 | 3 | 4 | 4 | G4 unsupported_cause / G5 direction: "Consolidated net income attributable to Walmart ... The increase reflects higher consolidated net income, partially offset by net income attributable to noncontrolling interests." — the source states no driver for this line, and NCI actually fell from $721M to $ |
| baseline | COST | 10-Q | 0 | PASS | 4 | 3 | 4 | 5 |  |
| baseline | COST | 10-Q | 1 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | BA | 10-K | 0 | FAIL | 3 | 4 | 3 | 4 | G5 basis_mismatch: "excluding that gain, segment operating earnings were $6,267M against a $7,079M loss from operations at BCA" — the $6,267M Segment operating earnings figure in the source INCLUDES the $9,566M Digital Aviation Solutions gain (it is embedded in BGS's $13,474M); the filing defines no |
| baseline | BA | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | INTC | 10-Q | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | INTC | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch / G4 unsupported_cause: "The wider loss reflects the goodwill impairment and restructuring charges, a $1.1 billion net loss on the Escrowed Shares derivative liability, and a $553M net loss attributable to non-controlling interests." — the $553M NCI loss is subtracted from the $4,2 |
| baseline | PLTR | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Gross margin rose to 87% from 80%, which management linked to the revenue increase relative to cost of revenue, where the increase was primarily due to an increase of $39 million in third-party cloud hosting services" — the source states only that gross margin increased from 8 |
| baseline | PLTR | 10-Q | 1 | PASS | 4 | 4 | 3 | 5 |  |
| baseline | RIVN | 10-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | RIVN | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "A significant portion of automotive revenues has been from one customer that is an affiliate of one of Rivian's principal stockholders; approximately 37% and 36% of revenues in 2024 and 2025 were from new EV sales to Chase Bank." — the source never identifies Chase Bank as an |
| baseline | COIN | 10-Q | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | COIN | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G4 unsupported_cause: "total revenue of $1.41B, down 30.5% from $2.03B a year earlier, as trading volume fell 50%" — the source attributes the transaction-revenue decline to consumer (54%) and institutional (48%) Trading Volume decreases; it does not attribute the total revenue decline (which also i |
| baseline | BYND | 10-Q | 0 | PASS | 4 | 3 | 4 | 5 |  |
| baseline | BYND | 10-Q | 1 | FAIL | 4 | 4 | 4 | 5 | G3 hallucinated_facts (minor): Risk #4 states "The 2030 Notes Indenture and the Loan and Security Agreement include a minimum liquidity covenant of $15.0 million, tested quarterly" — the source attributes quarterly testing only to the 2030 Notes Indenture; the Loan and Security Agreement is describe |
| baseline | BABA | 20-F | 0 | FAIL | 3 | 4 | 4 | 4 | G4 unsupported_cause: Results table row 'Adjusted EBITA / CNY 76,416M / CNY 173,065M / −55.9% / The filing attributes the decrease to the investment in quick commerce, user experiences, and technology, while there is positive contribution from customer management service.' — the source states this c |
| baseline | BABA | 20-F | 1 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | ASML | 20-F | 0 | FAIL | 4 | 3 | 4 | 4 | G4 unsupported_cause: Segments table applies the source's driver for total net system sales to the 'New systems' segment line — "New systems / EUR 23.9B / +13.1% / The increase in system sales was primarily driven by higher EUV and DUV immersion system sales, partially offset by a decrease in ArF dr |
| baseline | ASML | 20-F | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | TSM | 20-F | 0 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: "no total debt, net debt or debt-to-equity figure is stated" / "reports no debt balance" — the source explicitly states "our short-term loans were nil and our aggregate long-term debts were NT$1,032,988 million (US$32,929 million), of which NT$136,926 million (US$4,365 million |
| baseline | TSM | 20-F | 1 | FAIL | 4 | 3 | 4 | 4 | G3 hallucinated_facts: "This filing's standardized financial data reports no debt balance under a concept whose scope can be verified... no total debt, net debt or debt-to-equity figure is stated" — the source explicitly states "our short-term loans were nil and our aggregate long-term debts were NT |
| baseline | JD | 20-F | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "The increase was driven by growth across all three reportable segments" — the source states total revenue rose 13.0% and separately reports each segment's growth, but never attributes the consolidated increase to the segments; inter-segment eliminations also rose (RMB59,123M t |
| baseline | JD | 20-F | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | SE | 20-F | 0 | FAIL | 3 | 2 | 3 | 4 | G3 hallucinated_facts (status misrepresentation): 'agreed to settle the New York class action at US$40 million and the Arizona class action at US$46 million, both subject to final approval by the court' — the source states both settlements received court final approval (July 11, 2025 and August 7, 2 |
| baseline | SE | 20-F | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NVO | 20-F | 0 | FAIL | 3 | 2 | 3 | 4 | G3 hallucinated_facts: "Effective 1 January 2025, Novo Nordisk reorganised its geographical areas, which affects comparability of segmented results." — the source only states the reorganisation occurred; it makes no claim about comparability of segmented results (which may have been restated).; G3 h |
| baseline | NVO | 20-F | 1 | FAIL | 4 | 3 | 4 | 4 | G3 hallucinated_facts: "Novo Nordisk reorganised its geographical areas effective 1 January 2025, affecting segment comparability." — the source only states the reorganisation occurred; it makes no statement about comparability impact (IFRS segment comparatives are typically restated), so the compar |
| baseline | PDD | 20-F | 0 | FAIL | 4 | 3 | 4 | 4 | G5 basis_mismatch (unit): "restricted net assets of the Chinese mainland subsidiaries, the VIE and subsidiaries of the VIE were RMB125,917,402 (US$18,005,949)" — the source figure is stated under a note header 'Amounts in thousands of RMB and US$', i.e. ~RMB125.9 billion (US$18.0 billion); the summa |
| baseline | PDD | 20-F | 1 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | MELI | 10-K | 0 | FAIL | 4 | 3 | 3 | 4 | G4 unsupported_cause: "Total assets grew 69.3% to $42.7B, driven by increases in restricted cash and cash equivalents and loans receivable, net." — the source balance sheet shows these line items rising (restricted cash $2,064M→$9,867M; loans receivable, net $4,716M→$8,855M) but nowhere attributes t |
| baseline | MELI | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |

## #805 negative controls

Filings whose September 9 outputs carried a false explanation over correct figures. The bar for a grounding candidate is abstention here (no G4/G5 failure), not a better average.

| candidate | filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|---|
| baseline | AAPL | 10-K | 0 | FAIL | 3 | 3 | 4 | 4 | G4 unsupported_cause: "Total net sales ... Management attributed the increase primarily to higher net sales of iPhone and Services." (executive summary table and financial_highlights) — the source states this driver only for Americas net sales ("Americas net sales increased during 2025 compared to 2 |
| baseline | AAPL | 10-K | 1 | PASS | 5 | 3 | 3 | 4 |  |
| baseline | AMZN | 10-K | 0 | FAIL | 4 | 4 | 3 | 4 | G5 basis_mismatch: "free cash flow of $7.7B (derived as operating cash flow minus the absolute selected capex cash-flow amount; not an issuer-defined or discretionary-cash measure)" — the filing defines and reconciles free cash flow as $11,194M (OCF less purchases of property and equipment net of pr |
| baseline | AMZN | 10-K | 1 | FAIL | 4 | 3 | 3 | 4 | G3 hallucinated_facts: Executive summary Results table states net income change as "+31.2%" ($77.7B vs $59.2B); source figures ($77,670M / $59,248M) yield +31.1% (XBRL: 31.09%), and the summary's own financial_highlights table says "up 31.1% YoY" — the 31.2% figure is unsupported and internally inco |
| baseline | BA | 10-K | 0 | FAIL | 3 | 4 | 3 | 4 | G5 basis_mismatch: "excluding that gain, segment operating earnings were $6,267M against a $7,079M loss from operations at BCA" — the $6,267M Segment operating earnings figure in the source INCLUDES the $9,566M Digital Aviation Solutions gain (it is embedded in BGS's $13,474M); the filing defines no |
| baseline | BA | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | JPM | 10-K | 0 | FAIL | 3 | 2 | 3 | 3 | G5 basis_mismatch (period): "The prior year included an estimated bargain purchase gain of $2.8 billion associated with the First Republic acquisition" — the source attributes the $2.8B bargain purchase gain to the year ended December 31, 2023, not the prior year (2024); the summary's own supporting |
| baseline | JPM | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Total net revenue increased 3% to $182.4B, driven by higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compression and the impact |
| baseline | MELI | 10-K | 0 | FAIL | 4 | 3 | 3 | 4 | G4 unsupported_cause: "Total assets grew 69.3% to $42.7B, driven by increases in restricted cash and cash equivalents and loans receivable, net." — the source balance sheet shows these line items rising (restricted cash $2,064M→$9,867M; loans receivable, net $4,716M→$8,855M) but nowhere attributes t |
| baseline | MELI | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NVDA | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G2/G3 fabricated_comparative: "accounts receivable, net increased to $40,710M from $38,466M, both growing faster than the 20% sequential revenue increase" — AR grew ~5.8% ($38,466M→$40,710M), well below the 20% sequential revenue growth; the 'both growing faster' claim is false (inventories +20.5% i |
| baseline | NVDA | 10-Q | 1 | FAIL | 3 | 4 | 4 | 4 | G3 hallucinated_facts: Risk #2 'supporting evidence' is presented as a verbatim quote but alters the source text — summary reads 'for our non-diluted data center products' whereas the filing says 'for our non-data center products'; the phrase 'non-diluted data center products' does not appear in the |
| baseline | PFE | 10-Q | 0 | FAIL | 4 | 3 | 4 | 4 | G5 basis_mismatch: "from program start through March 29, 2026, total costs incurred were $4.3 billion, including $2.9 billion of restructuring charges" — the source states the $2.9 billion of restructuring charges is a component of the $3.3 billion Biopharma-segment portion ("of which $3.3 billion i |
| baseline | PFE | 10-Q | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | PLTR | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Gross margin rose to 87% from 80%, which management linked to the revenue increase relative to cost of revenue, where the increase was primarily due to an increase of $39 million in third-party cloud hosting services" — the source states only that gross margin increased from 8 |
| baseline | PLTR | 10-Q | 1 | PASS | 4 | 4 | 3 | 5 |  |
| baseline | RIVN | 10-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | RIVN | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "A significant portion of automotive revenues has been from one customer that is an affiliate of one of Rivian's principal stockholders; approximately 37% and 36% of revenues in 2024 and 2025 were from new EV sales to Chase Bank." — the source never identifies Chase Bank as an |

This report never automatically arms an AI feature or re-pins a baseline.
