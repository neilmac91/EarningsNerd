# Judged eval report: partial

Source `44fd9c4425c7139dbaef1b8707327d3561bab0ce`; generator `deepseek-flash`; judge `cli:claude-fable-5-1` (contract version 2); run local.

Attempts 70; judgeable 70; judged 60; errors 10; negative judgments 29.

| gate | attempts failing |
|---|---|
| G2 fabricated_comparatives | 0 |
| G3 hallucinated_facts | 10 |
| G4 unsupported_cause | 16 |
| G5 basis_mismatch | 18 |

## Every judged attempt

| candidate | filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|---|
| baseline | ASML | 6-K | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | ASML | 6-K | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | SE | 6-K | 0 | FAIL | 3 | 2 | 3 | 4 | G5 basis_mismatch: "loans receivable, net, rose to US$8.9 billion from US$7.4 billion at December 31, 2025" (repeated in Red flag and Risk 1) presents only the current-asset line (8,904,181 / 7,405,741) as if it were total loans receivable; the balance sheet also carries non-current loans receivable |
| baseline | SE | 6-K | 1 | PASS | 5 | 3 | 3 | 4 |  |
| baseline | PDD | 6-K | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | PDD | 6-K | 1 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | PLD | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Net earnings attributable to controlling interests fell 10.8% to $3.33B... The decline was primarily due to lower gains on real estate dispositions and higher interest expense" — the source states a cause only for the interest-expense increase, not for the net earnings decline |
| baseline | PLD | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: incorrect/internally inconsistent change figures — Results table states operating income change '−1.4%' (source/XBRL: 4,358 vs 4,416 = −1.3%, and the summary itself says −1.3% elsewhere) and net earnings change '−10.7%' (source: 3,328 vs 3,732 = −10.8%, and the summary itself  |
| baseline | NEE | 10-Q | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NEE | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch (entity scope): risk #3 states "NEE's and FPL's ability to meet financial obligations depends on subsidiaries' net income, cash flows and ability to pay upstream dividends" — the source says "NEE’s and NEECH’s ability to meet their financial obligations are primarily dependent on t |
| baseline | PGR | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | PGR | 10-K | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | FIGS | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G4 unsupported_cause: "Net income increased primarily due to higher gross profit, partially offset by higher operating expenses and income tax expense." — the source states drivers for gross profit and opex individually but never attributes the net income movement; this transfers line-item causes to |
| baseline | FIGS | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts / G4 unsupported_cause: "Inventory purchase obligations of approximately $63.1M as of June 30, 2026 could be impacted by the CBP withhold release order against a Jordanian manufacturing partner" — the source (Note 10) says purchase obligations can be impacted by 'the timing of  |
| baseline | GPRO | 10-K | 0 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | GPRO | 10-K | 1 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | AAPL | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | AAPL | 10-K | 1 | FAIL | 4 | 4 | 4 | 5 | G4 unsupported_cause: "Total net sales increased 6% in FY2025 compared to FY2024, with management attributing the increase across segments primarily to higher net sales of iPhone and Services" — the source gives no driver for the consolidated net sales increase; it attributes drivers only segment-by |
| baseline | MSFT | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Microsoft Cloud revenue increased 23% to $168.9B, driven by Azure and other cloud services revenue growth of 34%" — the source attributes the 34% Azure growth as the driver of *Server products and cloud services* revenue (+23%), not of the separately defined Microsoft Cloud me |
| baseline | MSFT | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | NVDA | 10-Q | 0 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | NVDA | 10-Q | 1 | PASS | 5 | 3 | 3 | 4 |  |
| baseline | JPM | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Total net revenue increased 3% to $182.4B, which management attributes to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compr |
| baseline | JPM | 10-K | 1 | FAIL | 2 | 3 | 3 | 3 | G4 unsupported_cause: "Net income decreased 2% to $57.0B, primarily due to a higher provision for credit losses, partially offset by higher revenue." — the source never attributes the net income decline to the provision (or nets it against revenue); it only reports the components separately, and non |
| baseline | KO | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: Segments table states EMEA "42% operating margin" and A. Pacific "36% operating margin", but the filing explicitly reports EMEA operating margin of 44.8% and Asia Pacific of 37.6% for the quarter; the summary's figures are computed on a different revenue basis than the source's na |
| baseline | KO | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch: Segments table states EMEA "42% operating margin" but the filing explicitly reports EMEA operating margin of 44.8% for the quarter; the summary's derived ratio (OI $1,259M / XBRL revenue $3,012M) is on a different revenue basis than the source's named measure and contradicts it.;  |
| baseline | TSLA | 10-K | 0 | FAIL | 4 | 4 | 4 | 5 | G4 unsupported_cause: Segments table states energy generation and storage 'gross margin improved primarily due to lower raw material costs and lower manufacturing costs for Megapack in part from the ramp of Shanghai Megafactory, partially offset by higher tariffs.' The source attributes the margin i |
| baseline | TSLA | 10-K | 1 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | AMZN | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "free cash flow of $7.7B (derived as operating cash flow minus the absolute selected capex cash-flow amount...)" — the filing defines and reconciles free cash flow as $11.2B (OCF less purchases of PP&E net of proceeds/incentives); the summary elsewhere reports FCF as $11.2B, then  |
| baseline | AMZN | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | BRK.B | 10-K | 0 | FAIL | 4 | 3 | 3 | 4 | G5 basis_mismatch: "Net earnings per average equivalent Class B share (diluted)" — the source presents only "Net earnings per average equivalent Class B share"; no basic/diluted distinction or diluted measure is disclosed, so the summary relabels the source's named measure. |
| baseline | BRK.B | 10-K | 1 | FAIL | 4 | 3 | 3 | 4 | G5 basis_mismatch: "Net earnings per average equivalent Class B share (diluted)" — the source reports only "Net earnings per average equivalent Class B share" ($31.04 / $41.27) with no diluted measure; the summary relabels the source's named measure as diluted. |
| baseline | XOM | 10-K | 0 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch / direction reversal: "The decline reflects lower sales and other operating revenue, which fell to $323.9B from $339.2B, partly offset by income from equity affiliates and other income." — the source shows income from equity affiliates fell (6,194→5,064) and other income fell (4,14 |
| baseline | XOM | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | PFE | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch (sign/direction reversal): "partly offset by a $13M loss from discontinued operations in the current period" — the $13M discontinued-operations loss reduces net income further (2,709 → 2,696); it worsens the decline rather than offsetting it.; G5 basis_mismatch (component scope): " |
| baseline | PFE | 10-Q | 1 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | F | 10-Q | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "a one-time IEEPA tariff benefit of about $700 million in Ford Blue and about $500 million in Ford Pro, which management states was offset by higher sourcing costs, including tariffs, associated with the disruption in aluminum supply and higher commodity prices" — the source st |
| baseline | F | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Ford Blue's higher EBIT reflects a one-time IEEPA tariff benefit of about $700 million recognized in the first quarter of 2026" — the source attributes Ford Blue's higher EBIT to "favorable market factors, higher parts and accessories profit, and lower regulatory compliance ex |
| baseline | WMT | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "return on assets 7.7% (prior 7.5%) (period net income / period-end assets, not annualized)" — the filing defines and reports ROA as 8.2% and 7.9% (consolidated net income / average total assets); the summary restates the filing's named measure on a different numerator and denomin |
| baseline | WMT | 10-K | 1 | FAIL | 4 | 3 | 4 | 4 | G5 basis_mismatch: "The effective income tax rate was 24.4%, which management attributes to the PhonePe share-based compensation charge providing no tax benefit" — the source attributes only the INCREASE in the rate (23.4%→24.4%) to the PhonePe charge, not the 24.4% level; a rate level and a change  |
| baseline | COST | 10-Q | 0 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | COST | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch: Segments table (Q3 basis, revenue $9.7B) states for Other International that "SG&A expenses as a percentage of net sales was lower in the Other International segment" — the source's quarterly discussion says SG&A % was "higher in our Canadian and Other International segments"; 'lo |
| baseline | BA | 10-K | 0 | PASS | 4 | 4 | 3 | 4 |  |
| baseline | BA | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | INTC | 10-Q | 0 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | INTC | 10-Q | 1 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | PLTR | 10-Q | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | PLTR | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Gross margin rose to 87% from 80%, which management linked to cost of revenue growth of 25% (primarily a $39 million increase in third-party cloud hosting services) trailing revenue growth" — the MD&A states cost of revenue rose 25% (cloud hosting) and separately that gross ma |
| baseline | RIVN | 10-K | 0 | FAIL | 3 | 4 | 3 | 4 | G3 hallucinated_facts: "Customer concentration: approximately 36% of 2025 revenues were from new EV sales to Chase Bank, an affiliate of a principal stockholder" — the source states 36% of revenues were from Chase Bank leasing sales, but nowhere identifies Chase Bank as an affiliate of a principal s |
| baseline | RIVN | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | COIN | 10-Q | 0 | PASS | 4 | 4 | 4 | 5 |  |
| baseline | COIN | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "The filing attributes the transaction revenue decline primarily to a 54% decrease in consumer Trading Volume ... and to a 48% decrease in institutional Trading Volume" — the source attributes the decline to consumer revenue falling, offset by an INCREASE in institutional trans |
| baseline | BYND | 10-Q | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | BYND | 10-Q | 1 | PASS | 4 | 3 | 4 | 5 |  |
| baseline | BABA | 20-F | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "income from operations dropped 64% to CNY 50.2B, as sales and marketing expenses rose 70% to CNY 245.0B" — the filing attributes the income-from-operations decline to the decrease in adjusted EBITA and higher goodwill impairment (offset by lower one-time provisions and SBC); i |
| baseline | BABA | 20-F | 1 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch / G3 hallucinated_facts: "Income from operations of CNY 50.2B includes a CNY 87.5B interest and investment income, net (up from CNY 20.8B)" — the source income statement presents interest and investment income, net (RMB87,512m) BELOW income from operations (RMB50,150m); it is a non |
| baseline | ASML | 20-F | 0 | FAIL | 4 | 4 | 4 | 5 | G5 basis_mismatch: "current portion of long-term debt of EUR 1.7B" — Note 16 of the source states the current portion of long-term debt is €990.2M; the €1,681.9M figure includes the €691.7M Euro Commercial Paper short-term borrowings, so the summary relabels a combined balance as the current portion |
| baseline | ASML | 20-F | 1 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | TSM | 20-F | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | TSM | 20-F | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | JD | 20-F | 0 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | JD | 20-F | 1 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | SE | 20-F | 0 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | SE | 20-F | 1 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | NVO | 20-F | 0 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | NVO | 20-F | 1 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | PDD | 20-F | 0 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | PDD | 20-F | 1 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | MELI | 10-K | 0 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | MELI | 10-K | 1 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |

## #805 negative controls

Filings whose September 9 outputs carried a false explanation over correct figures. The bar for a grounding candidate is abstention here (no G4/G5 failure), not a better average.

| candidate | filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|---|
| baseline | AAPL | 10-K | 0 | PASS | 4 | 3 | 4 | 4 |  |
| baseline | AAPL | 10-K | 1 | FAIL | 4 | 4 | 4 | 5 | G4 unsupported_cause: "Total net sales increased 6% in FY2025 compared to FY2024, with management attributing the increase across segments primarily to higher net sales of iPhone and Services" — the source gives no driver for the consolidated net sales increase; it attributes drivers only segment-by |
| baseline | AMZN | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G5 basis_mismatch: "free cash flow of $7.7B (derived as operating cash flow minus the absolute selected capex cash-flow amount...)" — the filing defines and reconciles free cash flow as $11.2B (OCF less purchases of PP&E net of proceeds/incentives); the summary elsewhere reports FCF as $11.2B, then  |
| baseline | AMZN | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | BA | 10-K | 0 | PASS | 4 | 4 | 3 | 4 |  |
| baseline | BA | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | JPM | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Total net revenue increased 3% to $182.4B, which management attributes to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compr |
| baseline | JPM | 10-K | 1 | FAIL | 2 | 3 | 3 | 3 | G4 unsupported_cause: "Net income decreased 2% to $57.0B, primarily due to a higher provision for credit losses, partially offset by higher revenue." — the source never attributes the net income decline to the provision (or nets it against revenue); it only reports the components separately, and non |
| baseline | MELI | 10-K | 0 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | MELI | 10-K | 1 | FAIL | - | - | - | - | RuntimeError: claude CLI exit 1:  |
| baseline | NVDA | 10-Q | 0 | PASS | 4 | 4 | 4 | 4 |  |
| baseline | NVDA | 10-Q | 1 | PASS | 5 | 3 | 3 | 4 |  |
| baseline | PFE | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G5 basis_mismatch (sign/direction reversal): "partly offset by a $13M loss from discontinued operations in the current period" — the $13M discontinued-operations loss reduces net income further (2,709 → 2,696); it worsens the decline rather than offsetting it.; G5 basis_mismatch (component scope): " |
| baseline | PFE | 10-Q | 1 | PASS | 5 | 3 | 4 | 4 |  |
| baseline | PLTR | 10-Q | 0 | PASS | 4 | 3 | 3 | 4 |  |
| baseline | PLTR | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G4 unsupported_cause: "Gross margin rose to 87% from 80%, which management linked to cost of revenue growth of 25% (primarily a $39 million increase in third-party cloud hosting services) trailing revenue growth" — the MD&A states cost of revenue rose 25% (cloud hosting) and separately that gross ma |
| baseline | RIVN | 10-K | 0 | FAIL | 3 | 4 | 3 | 4 | G3 hallucinated_facts: "Customer concentration: approximately 36% of 2025 revenues were from new EV sales to Chase Bank, an affiliate of a principal stockholder" — the source states 36% of revenues were from Chase Bank leasing sales, but nowhere identifies Chase Bank as an affiliate of a principal s |
| baseline | RIVN | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |

This report never automatically arms an AI feature or re-pins a baseline.
