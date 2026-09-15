# Weekly judged measurement: partial

Incomplete generation or judge evidence; not a completed readout

Expected 24; generated 24; judged 15; errors 9; missing 0; negative judgments 9.

| filing | form | run | verdict | faithfulness | insight | clarity | specificity | gate failures / error |
|---|---|---|---|---|---|---|---|---|
| AAPL | 10-K | 0 | FAIL | 4 | 4 | 4 | 5 | G3 hallucinated_facts: "Total net sales ... Management attributes the increase primarily to higher net sales of iPhone and Services." — the source contains no management attribution for total net sale |
| AAPL | 10-K | 1 | FAIL | 3 | 4 | 4 | 4 | G3 hallucinated_facts: "Excluding the State Aid impact, the FY2025 effective tax rate of 15.6% compared to 24.1% in FY2024" — 15.6% and 24.1% are the REPORTED rates that INCLUDE the State Aid impact ( |
| AAPL | 10-K | 2 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: supporting_evidence quote "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services." does not appear anywhere in the sour |
| JPM | 10-K | 0 | PASS | 4 | 3 | 3 | 4 |  |
| JPM | 10-K | 1 | PASS | 4 | 3 | 3 | 4 |  |
| JPM | 10-K | 2 | PASS | 4 | 3 | 3 | 4 |  |
| NVDA | 10-Q | 0 | FAIL | 4 | 4 | 4 | 5 | G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period growth rate, so the claim that growth 'accelerated' is an unsupported trend comparison. |
| NVDA | 10-Q | 1 | FAIL | 3 | 4 | 4 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period YoY growth rate against which 85% could be an acceleration; the only comparatives provided are th |
| NVDA | 10-Q | 2 | FAIL | 4 | 4 | 4 | 5 | G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source excerpt gives no prior-period YoY growth rate, so 'accelerated' is an unsupported trend comparison (source states only  |
| KO | 10-Q | 0 | FAIL | 3 | 3 | 4 | 4 | G3 hallucinated_facts: Segments table states EMEA "42% operating margin" — the source explicitly reports EMEA operating margin of 44.8% for the quarter; the summary's derived figure contradicts the fi |
| KO | 10-Q | 1 | FAIL | 3 | 3 | 4 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 12.1% YoY" — the source provides only the current quarter's 12% growth rate; no prior-period growth rate is given, so 'accelerated' is an uns |
| KO | 10-Q | 2 | FAIL | 2 | 3 | 4 | 4 | G2 fabricated_comparatives: "Revenue growth accelerated to 12%" — the source gives no prior-period growth rate, so 'accelerated' is an unsupported comparison.; G3 hallucinated_facts: "which management |
| BYND | 10-Q | 0 | PASS | 5 | 4 | 4 | 5 |  |
| BYND | 10-Q | 1 | PASS | 4 | 4 | 4 | 4 |  |
| BYND | 10-Q | 2 | PASS | 5 | 4 | 4 | 4 |  |
| ASML | 20-F | 0 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| ASML | 20-F | 1 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| ASML | 20-F | 2 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| BABA | 20-F | 0 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| BABA | 20-F | 1 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| BABA | 20-F | 2 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| MELI | 10-K | 0 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| MELI | 10-K | 1 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |
| MELI | 10-K | 2 | FAIL | - | - | - | - | Judge input exceeds full-coverage bounds |

This report never automatically arms an AI feature.
