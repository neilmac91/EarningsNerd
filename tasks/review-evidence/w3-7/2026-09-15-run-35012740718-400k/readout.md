# Weekly judged measurement: complete

All 24 attempts judged; negative judgments remain visible

Expected 24; generated 24; judged 24; errors 0; missing 0; negative judgments 14.

| filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|
| AAPL | 10-K | 0 | PASS | 4 | 4 | 4 | 5 |  |
| AAPL | 10-K | 1 | FAIL | 3 | 4 | 4 | 4 | G3 hallucinated_facts: "Excluding the State Aid impact, the FY2025 effective tax rate of 15.6% compared to 24.1% in FY2024." — 15.6% and 24.1% are the REPORTED effective tax rates including the State  |
| AAPL | 10-K | 2 | FAIL | 3 | 4 | 4 | 4 | G3 hallucinated_facts: supporting_evidence for Total net sales row — "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services." — this sentence  |
| JPM | 10-K | 0 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: Total net revenue row — "Management attributes the increase to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, |
| JPM | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| JPM | 10-K | 2 | PASS | 4 | 3 | 3 | 4 |  |
| NVDA | 10-Q | 0 | FAIL | 4 | 4 | 4 | 5 | G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — 'accelerated' asserts the YoY growth rate rose versus a prior period, but the source provides no prior-period YoY growth rate (Q4  |
| NVDA | 10-Q | 1 | FAIL | 3 | 4 | 4 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period growth rate, so the claim that growth accelerated is an unsupported comparison to an undisclosed  |
| NVDA | 10-Q | 2 | FAIL | 3 | 4 | 4 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period YoY growth rate to support 'accelerated'; only the current 85% YoY and 20% QoQ figures are disclo |
| KO | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: Segments table states EMEA "42% operating margin" and A. Pacific "36% operating margin"; the filing explicitly reports EMEA operating margin of 44.8% and Asia Pacific of 37.6% f |
| KO | 10-Q | 1 | FAIL | 3 | 3 | 3 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 12.1% YoY" — the source gives no prior-period growth rate, so 'accelerated' is an unsupported trend comparison.; G3 hallucinated_facts: Segme |
| KO | 10-Q | 2 | FAIL | 2 | 3 | 3 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 12%" — the source gives no prior-period growth rate, so 'accelerated' is an unsupported comparison.; G3 hallucinated_facts: "which management |
| BYND | 10-Q | 0 | PASS | 5 | 4 | 4 | 5 |  |
| BYND | 10-Q | 1 | PASS | 4 | 4 | 4 | 5 |  |
| BYND | 10-Q | 2 | PASS | 5 | 4 | 4 | 5 |  |
| ASML | 20-F | 0 | PASS | 4 | 3 | 4 | 4 |  |
| ASML | 20-F | 1 | PASS | 4 | 3 | 4 | 4 |  |
| ASML | 20-F | 2 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: "Interest and other, net increased to EUR 104.7M from EUR 19.8M, primarily due to higher interest income on cash and cash equivalents" — the source only says interest income 'ma |
| BABA | 20-F | 0 | FAIL | 4 | 4 | 4 | 4 | G3 hallucinated_facts: "sales and marketing expenses rose 70% on quick commerce and Qwen app user acquisition" (stated twice in the executive summary) — the source attributes the S&M increase to "the  |
| BABA | 20-F | 1 | PASS | 4 | 4 | 4 | 4 |  |
| BABA | 20-F | 2 | FAIL | 3 | 4 | 3 | 4 | G2 fabricated_comparatives: "interest and investment income swung to a CNY 87.5B gain from mark-to-market changes and investment disposals" — 'swung to a gain' implies the prior period was a loss; the |
| MELI | 10-K | 0 | PASS | 4 | 4 | 3 | 4 |  |
| MELI | 10-K | 1 | FAIL | 3 | 3 | 3 | 4 | G3 hallucinated_facts: "Net margin declined to 6.9% from 9.2%, primarily due to higher foreign exchange losses and income tax expense." — the source contains no such attribution; the filing attributes |
| MELI | 10-K | 2 | FAIL | 3 | 4 | 3 | 4 | G2 fabricated_comparatives: "the allowance for doubtful accounts on loans receivable rose to $3,179M from $1,678M" — $3,179M is the auditor's CAM figure (which is not the balance-sheet allowance; bala |

This report never automatically arms an AI feature.
