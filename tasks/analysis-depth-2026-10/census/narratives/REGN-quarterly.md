# REGN — quarterly (2023Q3..2026Q2)

Reproduced 2026-10-24T20:27:13.129929Z through `stream_trend_narrative(force=True)` at prompt `trends-v7-observations`, model `deepseek-flash` (served: deepseek-flash); local facts store built from live SEC companyfacts. Not a production `trend_analyses` row.

## The trajectory
Revenue was $4.3B in Q2 2026 [1].
Net income was USD 1,296,900,000 in Q2 2026 [2].
The earliest available revenue observation was $3.4B in Q3 2023 [3].

## Growth quality
Revenue growth in Q2 2026 was +16.7% [1] [4].
Net income growth in Q2 2026 was -6.8% [2] [5].
In Q2 2026, net income growth of -6.8% [2] [5] was below revenue growth of +16.7% [1] [4].
In Q2 2026, operating cash flow growth of -29.0% [6] [7] was below net income growth of -6.8% [2] [5].

## Margins
Operating margin was 30.1% in Q2 2026 [8].
Operating margin changed +0.8pp in Q2 2026 [8] [9].
Net margin changed -7.6pp in Q2 2026 [10] [11].

## Cash & balance sheet
In Q2 2026, free cash flow of $572.8M [12] was below net income of USD 1,296,900,000 [2].
The current ratio was 3.34× in Q2 2026 [13], above 1.00×.
Cash & equivalents was $2.5B in Q2 2026 [14].

## Red flags
Free-cash-flow conversion fell to 0.44× net income in Q2 2026 vs a 0.96× historical average — earnings and cash are diverging. Source operands: Free cash flow USD 938,300,000 in 2023Q3 [15]; Net income USD 1,007,800,000 in 2023Q3 [16]; Free cash flow USD 838,300,000 in 2023Q4 [17] (derived Q4); Net income USD 1,159,600,000 in 2023Q4 [18] (derived Q4); Free cash flow USD 1,378,600,000 in 2024Q1 [19]; Net income USD 722,000,000 in 2024Q1 [20]; Free cash flow USD 173,500,000 in 2024Q2 [21]; Net income USD 1,432,300,000 in 2024Q2 [22]; Free cash flow USD 1,049,300,000 in 2024Q3 [23]; Net income USD 1,340,600,000 in 2024Q3 [24]; Free cash flow USD 1,063,200,000 in 2024Q4 [25] (derived Q4); Net income USD 917,700,000 in 2024Q4 [26] (derived Q4); Free cash flow USD 815,800,000 in 2025Q1 [27]; Net income USD 808,700,000 in 2025Q1 [28]; Free cash flow USD 925,400,000 in 2025Q2 [29]; Net income USD 1,391,600,000 in 2025Q2 [5]; Free cash flow USD 1,417,300,000 in 2025Q3 [30]; Net income USD 1,460,000,000 in 2025Q3 [31]; Free cash flow USD 922,000,000 in 2025Q4 [32] (derived Q4); Net income USD 844,600,000 in 2025Q4 [33] (derived Q4); Free cash flow USD 848,300,000 in 2026Q1 [34]; Net income USD 727,200,000 in 2026Q1 [35]; Free cash flow USD 572,800,000 in 2026Q2 [12]; Net income USD 1,296,900,000 in 2026Q2 [2].

## What to watch next
Watch whether revenue growth in the next reporting update improves from +16.7% in Q2 2026 [1] [4].
Watch how net income in the next reporting update compares with USD 1,296,900,000 in Q2 2026 [2].
Watch how free cash flow in the next reporting update compares with $572.8M in Q2 2026 [12].

## Sources

[1] Revenue = 4,290,700,000 (2026Q2) — XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
[2] Net income = 1,296,900,000 (2026Q2) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
[3] Revenue = 3,362,700,000 (2023Q3) — XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax — https://www.sec.gov/Archives/edgar/data/872589/000180422024000040/
[4] Revenue = 3,675,600,000 (2025Q2) — XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
[5] Net income = 1,391,600,000 (2025Q2) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
[6] Operating cash flow = 813,000,000 (2026Q2) — Calculated · YTD6 - Q1
[7] Operating cash flow = 1,144,400,000 (2025Q2) — Calculated · YTD6 - Q1
[8] Operating margin = 30.1% (2026Q2) — Calculated · 100 * operating_income / revenue
[9] Operating margin = 29.4% (2025Q2) — Calculated · 100 * operating_income / revenue
[10] Net margin = 30.2% (2026Q2) — Calculated · 100 * net_income / revenue
[11] Net margin = 37.9% (2025Q2) — Calculated · 100 * net_income / revenue
[12] Free cash flow = 572,800,000 (2026Q2) — Calculated · operating_cash_flow - abs(capital_expenditures)
[13] Current ratio = 3.3353x (2026Q2) — Calculated · current_assets / current_liabilities
[14] Cash & equivalents = 2,455,800,000 (2026Q2) — XBRL · us-gaap:CashAndCashEquivalentsAtCarryingValue — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
[15] Free cash flow = 938,300,000 (2023Q3) — Calculated · operating_cash_flow - abs(capital_expenditures)
[16] Net income = 1,007,800,000 (2023Q3) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000180422024000040/
[17] Free cash flow = 838,300,000 (2023Q4) · derived Q4 — Calculated · operating_cash_flow - abs(capital_expenditures)
[18] Net income = 1,159,600,000 (2023Q4) · derived Q4 — Calculated · FY - YTD9
[19] Free cash flow = 1,378,600,000 (2024Q1) — Calculated · operating_cash_flow - abs(capital_expenditures)
[20] Net income = 722,000,000 (2024Q1) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258925000028/
[21] Free cash flow = 173,500,000 (2024Q2) — Calculated · operating_cash_flow - abs(capital_expenditures)
[22] Net income = 1,432,300,000 (2024Q2) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258925000028/
[23] Free cash flow = 1,049,300,000 (2024Q3) — Calculated · operating_cash_flow - abs(capital_expenditures)
[24] Net income = 1,340,600,000 (2024Q3) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258925000028/
[25] Free cash flow = 1,063,200,000 (2024Q4) · derived Q4 — Calculated · operating_cash_flow - abs(capital_expenditures)
[26] Net income = 917,700,000 (2024Q4) · derived Q4 — Calculated · FY - YTD9
[27] Free cash flow = 815,800,000 (2025Q1) — Calculated · operating_cash_flow - abs(capital_expenditures)
[28] Net income = 808,700,000 (2025Q1) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
[29] Free cash flow = 925,400,000 (2025Q2) — Calculated · operating_cash_flow - abs(capital_expenditures)
[30] Free cash flow = 1,417,300,000 (2025Q3) — Calculated · operating_cash_flow - abs(capital_expenditures)
[31] Net income = 1,460,000,000 (2025Q3) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258925000028/
[32] Free cash flow = 922,000,000 (2025Q4) · derived Q4 — Calculated · operating_cash_flow - abs(capital_expenditures)
[33] Net income = 844,600,000 (2025Q4) · derived Q4 — Calculated · FY - YTD9
[34] Free cash flow = 848,300,000 (2026Q1) — Calculated · operating_cash_flow - abs(capital_expenditures)
[35] Net income = 727,200,000 (2026Q1) — XBRL · us-gaap:NetIncomeLoss — https://www.sec.gov/Archives/edgar/data/872589/000087258926000025/
