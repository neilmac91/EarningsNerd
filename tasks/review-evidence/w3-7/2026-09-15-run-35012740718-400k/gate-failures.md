# Complete strong-judge readout, 2026-09-15 (400k excerpt bound): every judge gate failure verbatim

Generation run https://github.com/neilmac91/EarningsNerd/actions/runs/35012740718, source `962f2c7f775df3029d456e4f2ca4226b395c8191`, generator `deepseek-flash`, judge `cli:claude-fable-5-1`, judged at 2026-09-15T20:13:59.269041Z on judge-bound code `b4bb4e8f` (#886).
Status complete: judged 24/24, negative 14, deterministic vetoes 0, dimensions {'faithfulness': 3.5417, 'insight': 3.5833, 'clarity': 3.625, 'specificity': 4.2083}. Verdict text is the judge's own; figures were not re-verified by hand.

## AAPL 10-K run 0: PASS {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 5} (excerpt 124,125 chars)


## AAPL 10-K run 1: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 4, 'specificity': 4} (excerpt 124,125 chars)

- G3 hallucinated_facts: "Excluding the State Aid impact, the FY2025 effective tax rate of 15.6% compared to 24.1% in FY2024." — 15.6% and 24.1% are the REPORTED effective tax rates including the State Aid impact; the source provides no ex-State Aid rates, and the FY2024 rate excluding the $10.2B charge would be far lower than 24.1%. The claim is unsupported and misleading.
- G3 hallucinated_facts: supporting_evidence quote "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services." does not appear in the source; the filing only says this for the Americas segment, not total net sales. Fabricated source quotation.

## AAPL 10-K run 2: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 4, 'specificity': 4} (excerpt 124,125 chars)

- G3 hallucinated_facts: supporting_evidence for Total net sales row — "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services." — this sentence does not appear in the source; the only such attribution in the filing is for the Americas segment, so the commentary "Management attributes the increase primarily to higher net sales of iPhone and Services" for total net sales is a fabricated management attribution presented as a verbatim quote.

## JPM 10-K run 0: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 3, 'specificity': 4} (excerpt 170,233 chars)

- G3 hallucinated_facts: Total net revenue row — "Management attributes the increase to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compression and the impact of lower rates." The source attributes these drivers to net interest income only; management does not attribute the total net revenue increase to these factors, and the summary omits the separately disclosed NIR drivers (Markets NIR, asset management fees, First Republic gain, absence of Visa gain).

## JPM 10-K run 1: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 3, 'specificity': 4} (excerpt 170,233 chars)


## JPM 10-K run 2: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 3, 'specificity': 4} (excerpt 170,233 chars)


## NVDA 10-Q run 0: FAIL {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 5} (excerpt 102,206 chars)

- G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — 'accelerated' asserts the YoY growth rate rose versus a prior period, but the source provides no prior-period YoY growth rate (Q4 FY26 YoY is not disclosed in the excerpt); only the 85% YoY and 20% QoQ figures are supported.

## NVDA 10-Q run 1: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 4, 'specificity': 4} (excerpt 102,206 chars)

- G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period growth rate, so the claim that growth accelerated is an unsupported comparison to an undisclosed prior rate.
- G3 hallucinated_facts: "Reported net income of $58.3B included $16.0B of total other income, net, versus $272M a year ago" — the source reports total other income, net of $16,367M (~$16.4B); the $16.0B figure matches neither total other income nor Other income (expense), net ($15,929M). The same mis-figure appears in the executive summary as "$16.0B of investment gains in Other income (expense), net" (source: $15,929M).

## NVDA 10-Q run 2: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 4, 'specificity': 4} (excerpt 102,206 chars)

- G2 fabricated_comparatives: "Revenue growth accelerated to 85% YoY" — the source gives no prior-period YoY growth rate to support 'accelerated'; only the current 85% YoY and 20% QoQ figures are disclosed.
- G3 hallucinated_facts: "net income was amplified by $16.0B of investment gains" / "$16.0B of total other income, net" (repeated in bullets, table commentary, earnings-quality section and red flag) — source shows Total other income, net of $16,367M (~$16.4B) and Other income (expense), net of $15,929M (~$15.9B); $16.0B matches neither and is internally inconsistent with the summary's own $16,367M table figure; also mislabels total other income (which includes interest income/expense) as 'investment gains'.

## KO 10-Q run 0: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 4, 'specificity': 4} (excerpt 95,851 chars)

- G3 hallucinated_facts: Segments table states EMEA "42% operating margin" and A. Pacific "36% operating margin"; the filing explicitly reports EMEA operating margin of 44.8% and Asia Pacific of 37.6% for the quarter (the summary's figures are derived from XBRL segment revenue that includes intersegment amounts, contradicting the source's stated metric under the same label).
- G3 hallucinated_facts: Balance Sheet section claims "no total debt, net debt or debt-to-equity figure is stated" / "no debt balance under a concept whose scope can be verified"; the balance sheet in the source explicitly reports long-term debt $39,065M, current maturities of long-term debt $4,493M and loans and notes payable $332M, so the assertion misrepresents what the filing discloses.

## KO 10-Q run 1: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 3, 'specificity': 4} (excerpt 95,851 chars)

- G2 fabricated_comparatives: "Revenue growth accelerated to 12.1% YoY" — the source gives no prior-period growth rate, so 'accelerated' is an unsupported trend comparison.
- G3 hallucinated_facts: Segment table states EMEA "42% operating margin" and A. Pacific "36% operating margin", but the filing explicitly reports EMEA operating margin of 44.8% and Asia Pacific of 37.6% for the quarter; the summary's figures contradict the source.
- G3 hallucinated_facts: "no total debt, net debt or debt-to-equity figure is stated" / "reports no debt balance under a concept whose scope can be verified" — the balance sheet in the source clearly states long-term debt $39,065M, current maturities of long-term debt $4,493M and loans and notes payable $332M; the leverage claim misrepresents the source.

## KO 10-Q run 2: FAIL {'faithfulness': 2, 'insight': 3, 'clarity': 3, 'specificity': 4} (excerpt 95,851 chars)

- G2 fabricated_comparatives: "Revenue growth accelerated to 12%" — the source gives no prior-period growth rate, so 'accelerated' is an unsupported comparison.
- G3 hallucinated_facts: "which management attributes to the net change in operating assets and liabilities" and "a $6,258M swing that management identifies as the driver of the operating cash flow change" — the excerpt's MD&A cash-flow discussion is not included; no management attribution exists in the source (the number is on the cash flow statement, the attribution is invented).
- G3 hallucinated_facts: segment table states EMEA "42% operating margin" and A. Pacific "36% operating margin" — the filing explicitly reports EMEA 44.8% and Asia Pacific 37.6%; the summary's derived figures contradict stated source values.
- G3 hallucinated_facts: "no total debt ... figure is stated" — the balance sheet in the source states long-term debt $39,065M, current maturities of long-term debt $4,493M and loans and notes payable $332M; the leverage disclaimer is factually wrong against the source.

## BYND 10-Q run 0: PASS {'faithfulness': 5, 'insight': 4, 'clarity': 4, 'specificity': 5} (excerpt 177,945 chars)


## BYND 10-Q run 1: PASS {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 5} (excerpt 177,945 chars)


## BYND 10-Q run 2: PASS {'faithfulness': 5, 'insight': 4, 'clarity': 4, 'specificity': 5} (excerpt 177,945 chars)


## ASML 20-F run 0: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 4, 'specificity': 4} (excerpt 260,154 chars)


## ASML 20-F run 1: PASS {'faithfulness': 4, 'insight': 3, 'clarity': 4, 'specificity': 4} (excerpt 260,154 chars)


## ASML 20-F run 2: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 4, 'specificity': 4} (excerpt 260,154 chars)

- G3 hallucinated_facts: "Interest and other, net increased to EUR 104.7M from EUR 19.8M, primarily due to higher interest income on cash and cash equivalents" — the source only says interest income 'mainly relates to' cash balances; it never attributes the increase to higher interest income. Note 16 shows interest income rose €40.6M (223.0 vs 182.4) while interest expense fell €44.3M (118.3 vs 162.6), so the larger driver was lower expense — the 'primarily' attribution is unsupported and contradicted by the figures.

## BABA 20-F run 0: FAIL {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 4} (excerpt 231,089 chars)

- G3 hallucinated_facts: "sales and marketing expenses rose 70% on quick commerce and Qwen app user acquisition" (stated twice in the executive summary) — the source attributes the S&M increase to "the investment in user experiences of Alibaba China E-commerce Group and user acquisition of Qwen app"; 'quick commerce' is never given as a driver of S&M expense (quick commerce subsidies are disclosed as contra revenue, and quick commerce is cited only as a driver of segment adjusted EBITA and operating cash flow decline).

## BABA 20-F run 1: PASS {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 4} (excerpt 231,089 chars)


## BABA 20-F run 2: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 3, 'specificity': 4} (excerpt 231,089 chars)

- G2 fabricated_comparatives: "interest and investment income swung to a CNY 87.5B gain from mark-to-market changes and investment disposals" — 'swung to a gain' implies the prior period was a loss; the source shows FY2025 interest and investment income, net was already a gain of RMB20,759 million (FY2026 was an increase, not a sign reversal).

## MELI 10-K run 0: PASS {'faithfulness': 4, 'insight': 4, 'clarity': 3, 'specificity': 4} (excerpt 250,076 chars)


## MELI 10-K run 1: FAIL {'faithfulness': 3, 'insight': 3, 'clarity': 3, 'specificity': 4} (excerpt 250,076 chars)

- G3 hallucinated_facts: "Net margin declined to 6.9% from 9.2%, primarily due to higher foreign exchange losses and income tax expense." — the source contains no such attribution; the filing attributes margin compression to the Brazil free-shipping threshold reduction, higher provision for doubtful accounts and cost of net revenues (operating margin fell 1.6pp of the 2.3pp net-margin decline), while FX losses and tax together account for only ~0.6pp. The quoted supporting evidence addresses only other expenses, not net margin.

## MELI 10-K run 2: FAIL {'faithfulness': 3, 'insight': 4, 'clarity': 3, 'specificity': 4} (excerpt 250,076 chars)

- G2 fabricated_comparatives: "the allowance for doubtful accounts on loans receivable rose to $3,179M from $1,678M" — $3,179M is the auditor's CAM figure (which is not the balance-sheet allowance; balance sheet shows $3,057M + $86M = $3,143M), while $1,678M is the prior-year balance-sheet allowance ($1,630M + $48M). The source contains no prior-period value for the $3,179M measure, so the YoY comparison is constructed across inconsistent bases and is not supported by the source.

