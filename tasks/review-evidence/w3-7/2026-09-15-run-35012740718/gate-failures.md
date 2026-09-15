# First strong-judge readout, 2026-09-15: every judge gate failure verbatim

Generation run https://github.com/neilmac91/EarningsNerd/actions/runs/35012740718, source `962f2c7f775df3029d456e4f2ca4226b395c8191`, generator `deepseek-flash`, judge `cli:claude-fable-5-1`, judged at 2026-09-15T19:27:05.109086Z.
Fifteen attempts judged; nine (ASML, BABA, MELI) exceeded the 200,000-character judge excerpt bound and are explicit errors, not verdicts. Verdict text is the judge's own; figures were not re-verified by hand.

## AAPL 10-K run 0: FAIL {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 5}

- G3 hallucinated_facts: "Total net sales ... Management attributes the increase primarily to higher net sales of iPhone and Services." — the source contains no management attribution for total net sales; that sentence is made only about Americas segment net sales (the summary's own supporting_evidence cites the Americas passage). The consolidated-level attribution is an inference presented as a management statement.

## AAPL 10-K run 1: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 4, 'specificity': 4}

- G3 hallucinated_facts: "Excluding the State Aid impact, the FY2025 effective tax rate of 15.6% compared to 24.1% in FY2024" — 15.6% and 24.1% are the REPORTED rates that INCLUDE the State Aid impact (2024's 24.1% is inflated by the $10.2B charge; 2025's 15.6% includes a $486M benefit). The source provides no ex-State-Aid ETR, and the actual ex-State-Aid rates would be roughly 15.8% (2024) and 16.0% (2025), so the sentence is false and inverts the analytical point.
- G3 hallucinated_facts: supporting_evidence quote "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services." does not appear anywhere in the source excerpt; the MD&A only makes this statement at the segment (Americas) level. Presented as a verbatim filing quote.
- G3 hallucinated_facts (minor): "Not separately reported in this filing's standardized data: short-term borrowings" — the balance sheet and Note 9 explicitly report commercial paper of $7,979M / $8.0B, which the summary itself quotes elsewhere; the claim that short-term borrowings are not reported is contradicted by the source.

## AAPL 10-K run 2: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 4, 'specificity': 4}

- G3 hallucinated_facts: supporting_evidence quote "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services." does not appear anywhere in the source; the MD&A only makes that attribution for the Americas segment, so the repeated claim "Management attributes the increase primarily to higher net sales of iPhone and Services" for total net sales is a fabricated management attribution.
- G2 fabricated_comparatives: Provision for income taxes row states "The lower effective tax rate was primarily due to a lower effective tax rate on foreign earnings, including the impact of changes in unrecognized tax benefits, the U.S. federal R&D credit, and tax benefits from share-based compensation..." as the prior-period comparison driver; the source gives those as reasons the 2025 rate was below the 21% statutory rate, and for the YoY comparison actually cites the $10.7B State Aid decrease and says it was "partially offset by ... a higher effective tax rate on foreign earnings" — the opposite direction.

## JPM 10-K run 0: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 3, 'specificity': 4}


## JPM 10-K run 1: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 3, 'specificity': 4}


## JPM 10-K run 2: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 3, 'specificity': 4}


## NVDA 10-Q run 0: FAIL {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 5}

- G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period growth rate, so the claim that growth 'accelerated' is an unsupported trend comparison.

## NVDA 10-Q run 1: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 4, 'specificity': 4}

- G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period YoY growth rate against which 85% could be an acceleration; the only comparatives provided are the current 85% YoY and 20% sequential.
- G3 hallucinated_facts: "net income was additionally lifted by $16.0B of investment gains in Other income (expense), net versus a $180M expense a year ago" — Other income (expense), net is $15,929M ($15.9B), not $16.0B.
- G3 hallucinated_facts: "Reported net income of $58.3B included $16.0B of total other income, net, versus $272M a year ago" — Total other income, net is $16,367M ($16.4B); $16.0B matches neither that line nor the $15,929M Other income (expense), net line.

## NVDA 10-Q run 2: FAIL {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 5}

- G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source excerpt gives no prior-period YoY growth rate, so 'accelerated' is an unsupported trend comparison (source states only +85% YoY and +20% sequential).
- G3 hallucinated_facts: "Net income of $58.3B included $16.0B of total other income, net" (repeated in bullets, Earnings Quality, Red flag, and Net income table row) — the source reports Total other income, net of $16,367M (~$16.4B); $16.0B is the sum of the two unrealized-gain items ($13.4B + $2.6B), not total other income, net, and the summary itself elsewhere states $16,367M, so the figure is mislabeled and internally inconsistent.

## KO 10-Q run 0: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 4, 'specificity': 4}

- G3 hallucinated_facts: Segments table states EMEA "42% operating margin" — the source explicitly reports EMEA operating margin of 44.8% for the quarter; the summary's derived figure contradicts the filing.
- G3 hallucinated_facts: Segments table states A. Pacific "36% operating margin" — the source explicitly reports Asia Pacific operating margin of 37.6%; the summary's derived figure contradicts the filing.

## KO 10-Q run 1: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 4, 'specificity': 4}

- G2 fabricated_comparatives: "Revenue growth accelerated to 12.1% YoY" — the source provides only the current quarter's 12% growth rate; no prior-period growth rate is given, so 'accelerated' is an unsupported trend comparison.
- G3 hallucinated_facts: Segment table states EMEA "42% operating margin" and A. Pacific "36% operating margin"; the filing explicitly reports EMEA operating margin of 44.8% and Asia Pacific of 37.6% for the quarter. The summary's derived figures contradict the source's stated margins.
- G3 hallucinated_facts (misleading negative claim): "no total debt, net debt or debt-to-equity figure is stated" / "reports no debt balance" — the source balance sheet plainly shows long-term debt $39,065M, current maturities of long-term debt $4,493M and loans and notes payable $332M; the leverage statement misrepresents what the filing discloses.

## KO 10-Q run 2: FAIL {'faithfulness': 2, 'insight': 3, 'clarity': 4, 'specificity': 4}

- G2 fabricated_comparatives: "Revenue growth accelerated to 12%" — the source gives no prior-period growth rate, so 'accelerated' is an unsupported comparison.
- G3 hallucinated_facts: "which management attributes to the net change in operating assets and liabilities" and "a $6,258M swing that management identifies as the driver of the operating cash flow change" — the excerpt contains no management attribution for the operating cash flow change (the MD&A cash-flow section is not in the source); only the cash flow statement line items appear.
- G3 hallucinated_facts: Segment table states EMEA "42% operating margin" and A. Pacific "36% operating margin" — the filing explicitly reports EMEA operating margin of 44.8% and Asia Pacific of 37.6%; the summary's figures contradict the source.
- G3 hallucinated_facts: "no total debt, net debt or debt-to-equity figure is stated" / "reports no debt balance under a concept whose scope can be verified" — the balance sheet in the source states long-term debt of $39,065M, current maturities of long-term debt of $4,493M and loans and notes payable of $332M, so this leverage statement misrepresents the source.
- G3 hallucinated_facts (minor): "Captive insurance companies held total equity and debt securities of $2,667 million" — the source attributes the $2,667M to a single captive's solvency capital funds ('This captive's'), not to the captive insurance companies collectively.

## BYND 10-Q run 0: PASS {'faithfulness': 5, 'insight': 4, 'clarity': 4, 'specificity': 5}


## BYND 10-Q run 1: PASS {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 4}


## BYND 10-Q run 2: PASS {'faithfulness': 5, 'insight': 4, 'clarity': 4, 'specificity': 4}


## ASML 20-F run 0: error

Judge input exceeds full-coverage bounds (excerpt 260,154 chars)

## ASML 20-F run 1: error

Judge input exceeds full-coverage bounds (excerpt 260,154 chars)

## ASML 20-F run 2: error

Judge input exceeds full-coverage bounds (excerpt 260,154 chars)

## BABA 20-F run 0: error

Judge input exceeds full-coverage bounds (excerpt 231,089 chars)

## BABA 20-F run 1: error

Judge input exceeds full-coverage bounds (excerpt 231,089 chars)

## BABA 20-F run 2: error

Judge input exceeds full-coverage bounds (excerpt 231,089 chars)

## MELI 10-K run 0: error

Judge input exceeds full-coverage bounds (excerpt 250,076 chars)

## MELI 10-K run 1: error

Judge input exceeds full-coverage bounds (excerpt 250,076 chars)

## MELI 10-K run 2: error

Judge input exceeds full-coverage bounds (excerpt 250,076 chars)

