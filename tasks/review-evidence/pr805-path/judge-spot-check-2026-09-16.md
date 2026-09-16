# Hand spot-check of the strong judge on causal and basis claims — 2026-09-16

Precondition from the [#805 assessment](../../pr805-assessment-2026-09-16.md) before the judge is used as
an acceptance gate on explanation faithfulness: check about five of its September 15 verdicts by hand.
Source: the retained generation artifact `weekly-judged-readout-35012740718` (`report.json`, each
attempt's `grounding_excerpt` and `payload`) and the judged
[gate failures](../w3-7/2026-09-15-run-35012740718-400k/gate-failures.md). Method: for each verdict,
search the exact retained excerpt the judge saw for the source text the verdict relies on. No model call.

| # | Attempt | Judge's finding | Retained excerpt says | Verdict correct? |
| --- | --- | --- | --- | --- |
| 1 | AAPL 10-K run 1 | 15.6% / 24.1% are the reported effective tax rates including the State Aid impact; no ex-State-Aid rate exists | Rate reconciliation lists "Impact of the State Aid Decision (486) 10,246" as a line inside the reported rates 15.6% / 24.1% / 14.7%; no ex-item rate anywhere | Yes |
| 2 | AAPL 10-K run 2 | The evidence quote "Total net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services" does not exist; the filing says this for the Americas segment only | 0 hits for the quoted sentence; 1 hit for the clause, inside "Americas net sales increased during 2025 …" | Yes |
| 3 | NVDA 10-Q run 0 | "Revenue growth accelerated to 85% YoY" has no prior-period growth rate in the source | Source gives "up 85% from a year ago and up 20% sequentially"; no prior-period YoY rate and no "growth rate/accelerat" text | Yes |
| 4 | KO 10-Q run 0 | Segment table's EMEA 42% / Asia Pacific 36% operating margins contradict the filing's stated 44.8% / 37.6% | Operating-margin table: "EMEA 44.8 42.9 … Asia Pacific 37.6 47.1" | Yes |
| 5 | KO 10-Q run 2 | "which management attributes to the net change in operating assets and liabilities" and the "$6,258M swing that management identifies as the driver" are invented attributions | The only occurrence is the cash-flow statement line "Net change in operating assets and liabilities (2,263) (8,521)"; no attribution sentence; "6,258" does not occur (it is the computed difference) | Yes |
| 6 | ASML 20-F run 2 | "increased … primarily due to higher interest income" is not what the source says; it only says income "mainly relates to" cash balances, and interest expense fell too | Note text: interest income €223.0M vs €182.4M "mainly relates to interest income on cash and cash equivalents"; interest expense €118.3M vs €162.6M; no sentence attributes the increase | Yes |

Also checked in passing: AAPL run 1's "revenue growth accelerated to 6.4% from 2.0% in FY2024" was **not**
flagged, and correctly so: the net-sales table carries both year-over-year rates ("$416,161 6 % $391,035
2 %"), so that acceleration claim has a prior rate in the source. The judge distinguished the supported
acceleration (AAPL) from the unsupported one (NVDA, KO) under contract version 1, before G4/G5 existed.

Result: 6/6 verdicts hold against the retained source, including the two subtle ones (5 and 6, where the
number is right and only the attribution is invented). Under judge contract version 2 these would be
G4 (2, 5, 6) and G5 (1, 3, 4) failures rather than G2/G3. The judge is fit to gate explanation
faithfulness on the #805 negative controls; its recall (defects it misses) is not measured by this check.
