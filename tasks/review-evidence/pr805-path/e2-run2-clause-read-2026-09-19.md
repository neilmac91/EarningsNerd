# E2 ranking run 2 — independent all-clause read, 2026-09-19

Of 13 flagged clauses, this manual read finds **2 strict-rule correct prospective drops, 4 unsafe drops, 3 unresolved drops, and 4 supported rescues**. All judgments distinguish the supplied passages from the full retained excerpt. These are manual labels, not Fable results. The deletion gate was off: no text was actually dropped.

Artifact from [Actions 35462609093](https://github.com/neilmac91/EarningsNerd/actions/runs/35462609093): `work/e2-ranking-run2/eval_20260919T190325Z.json`, SHA256 `2c1fb37fae2c719fa016b8c55c53d3532973afeb7229d9c4218bf3424e1053e9`. It records 70 scored attempts and 0 errors, source `73cc31162c3dfe7ec497c8c88c43cf397afce4a7`, DeepSeek Flash, verification on and deletion off. The unchanged E2 worktree HEAD is the exact recorded source. All 70 grounding excerpts are byte-identical to their matching run 1 excerpts.

All **13 flag records match exactly** (slot/connective/truncated clause/coverage), with no missing or extra candidates. Candidate counts match in all 12 flagged attempts. Checked counts match in 11 of 12: **SE 20-F repeat 1 records 5 checked versus 4 on final-payload replay**. Its sole flagged clause still matches exactly. The pipeline verifies before statement binding, and binding can remove model-authored `operating_vs_one_time`; the final SE section has the bound statement and no original field. This is a plausible stage difference, not a demonstrated reconstruction of the missing checked clause. Preserve the audit denominator and this uncertainty.

All 13 flags were sent and decided: 9 `not_stated`, 4 `stated`, 0 `unknown`. Raw verifier quotes and reasons were not retained. The supplied passages in the machine index are a deterministic reconstruction using identical code and the same retained excerpt, not saved provider request logs. Clause labels use exact retained audit verdicts, not a model replay.

## What the second run adds

- **Intel spelling sensitivity:** repeat 0's `Eye Q` retrieves and rescues the Mobileye source statement. Repeat 1's faithful `EyeQ` spelling retrieves unrelated DCAI/client passages and is rejected. The full excerpt supports both.
- **Pfizer's two full-source rescues retain a context gap:** both SIA table comments are supported by the full lead-in and marketing bullet, but supplied windows contain only the detached bullet. Their correct labels do not demonstrate sufficient supplied subject context, or a measured E3 fix.
- **Ford's two note-supported explanations are still rejected.** The selected windows omit the table anchor; the full debt note identifies the actual convertible-debt extinguishment.
- **Sea's compound explanation is partially supplied:** this time one current-year finance-business explanation is retrieved, but the Shopee counterpart is missing. The full annual section supports the business-specific synthesis.
- PLD's selected net-earnings component bridge, ASML's financing level/change shorthand and PDD's operating-to-net relationship remain unresolved. Do not force these into the precision numerator.

## Denominators, pooled counts and observed ranges

| Quantity | Run 1 | Run 2 | Pooled |
| --- | ---: | ---: | ---: |
| Generated attempts | 70 | 70 | 140 |
| Flagged attempts | 17 | 12 | 29 |
| Flagged clauses | 25 | 13 | 38 |
| Recorded prospective drops (`not_stated`) | 19 | 9 | 28 |
| Strict-rule correct prospective drops | 7 | 2 | 9 |
| Unsafe prospective drops | 6 | 4 | 10 |
| Unresolved prospective drops | 6 | 3 | 9 |
| Confirmed full-source rescues / recorded rescues | 5/6 | 4/4 | 9/10 |
| Ambiguous rescues | 1 | 0 | 1 |
| Correct-drop fraction, with unresolved cases kept in denominator | 7/19 = 36.8% | 2/9 = 22.2% | 9/28 = 32.1% |
| Classification bound if every unresolved drop proved correct | 36.8–68.4% | 22.2–55.6% | 32.1–64.3% |
| Correct-drop fraction among decidable cases only | 7/13 = 53.8% | 2/6 = 33.3% | 9/19 = 47.4% |
| Unsafe-drop fraction | 6/19 = 31.6% | 4/9 = 44.4% | 10/28 = 35.7% |
| Actual deletions | 0 | 0 | 0 |

Observed per-report ranges are 13–25 flagged clauses, 9–19 prospective drops, 22.2–36.8% confirmed correct-drop fraction, 31.6–44.4% unsafe-drop fraction, and 83.3–100% confirmed full-source rescue fraction. These are descriptive ranges over two reports, not statistical confidence intervals. The classification bounds separately represent unresolved judgments. The decidable-only figures exclude 6, 3 and 9 cases respectively and must not be presented without those exclusions.

Both reports test the same E2 configuration and source-equivalent application/evaluation trees, on the same 35 filings with two repeats each. Pooled counts include repeated subjects and correlated claims, including duplicate explanations across slots; they are not 38 independent factual examples. This is not a measured improvement over the old verifier or E3. No same-judge Fable comparison is included here, and the study does not estimate recall over unflagged clauses.

## Every flagged clause

### 1. ASML 6-K repeat 1 — confirmed rescue

Slot: `the_print.what_changed`. Recorded verdict: `stated`.

Summary context: On the filing's own sequential basis, total net sales rose from €8,767M in Q1 2026 to €9,326M in Q2 2026, gross margin rose from 53.0% to 54.0%, and net income rose from €2,757M to €2,918M. The filing attributes the Q2 revenue and gross margin levels to higher than expected Installed Base Management sales, which rose from €2,488M in Q1 2026 to €2,762M in Q2 2026. The filing does not provide prior-year comparative figures.

Flagged cause: higher than expected Installed Base Management sales

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The supplied CEO passage and full excerpt explicitly state Q2 net sales of EUR 9.3B and gross margin of 54.0%, both above guidance, driven primarily by higher-than-expected Installed Base Management sales. The summary limits the attributed Q2 levels to revenue and gross margin; its earlier net-income comparison is not the attributed subject. Supported rescue, with the same caveat as run 1: the source explains performance above guidance, rather than separately quantifying a sequential-growth cause.

### 2. PLD 10-K repeat 1 — uncertain drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total revenues increased 7.2% to $8.79B, as rental revenues rose $644M to $8.16B and development management and other revenues increased to $39M from $15M, partly offset by strategic capital revenues declining to $592M from $672M. Net earnings attributable to controlling interests fell to $3.33B from $3.73B, and diluted EPS declined to $3.56 from $4.01, reflecting lower gains on real estate dispositions ($944M combined in 2025 versus $1.32B in 2024) and higher interest expense of $1.00B versus $864M.

Flagged cause: lower gains on real estate dispositions ($944M combined in 2025 versus $1.32B in 2024) and higher interest expense of $1.00B versus $864M

Supplied-passages assessment: **table fragments**. Full-excerpt assessment: **decomposition only**.

Selected passages are four disposition table fragments without the full net-earnings or EPS bridge. Full retained MD&A reports disposition gains of 258 + 686 = 944 million versus 414 + 904 = 1,318 million and interest expense of 1,002 versus 864 million. It explains the origin of the gains and why interest expense increased, but does not explicitly assign the total net-earnings/EPS decline to these two selected components. The numerical decomposition is plausible, though it omits other moving components and EPS denominator effects. As with the component bridges in run 1, this is unresolved under the boundary between arithmetic explanation and issuer-stated causation, not counted as a clean correct drop.

### 3. JPM 10-K repeat 1 — correct prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total net revenue increased 3% to $182.4B, which management attributes to higher Markets net interest income, higher revolving balances in Card Services, higher wholesale deposit balances, and the impact of investment securities activity, largely offset by deposit margin compression and the impact of lower rates. Net income decreased 2% to $57.0B, and the provision for credit losses increased 33% to $14.2B. Diluted EPS rose 1% to $20.02 while net income fell, reflecting a lower weighted-average diluted share count.

Flagged cause: a lower weighted-average diluted share count

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

Supplied passages report EPS and weighted-average shares. Full excerpt reports diluted EPS of 20.02 versus 19.75, net income of 57,048 versus 58,471 million, and diluted shares of 2,781.5 versus 2,879.0 million. No same-subject issuer sentence linking EPS growth to the denominator decline was found in the retained comparison. This repeats the run 1 JPM inference: correct prospective drop under the strict issuer-stated-driver rule, not a finding that the financial arithmetic is false.

### 4. JPM 10-K repeat 1 — correct prospective drop

Slot: `results_that_matter.table[7].commentary`. Recorded verdict: `not_stated`.

Summary context: Diluted EPS rose 1.4% YoY while net income declined, reflecting a lower weighted-average diluted share count (2,781.5 million versus 2,879.0 million).

Flagged cause: a lower weighted-average diluted share count (2,781.5 million versus 2,879.0 million)

Supplied-passages assessment: **facts only**. Full-excerpt assessment: **not stated**.

The same JPM denominator inference is repeated in the diluted-EPS table row, now giving both share counts. The selected passages and full retained excerpt contain the values but not an issuer-stated explanation that the share decline drove the EPS increase. Classification follows the same strict rule as run 1 and clause 3; it should not be represented as a numerical error.

### 5. PFE 10-Q repeat 0 — confirmed rescue

Slot: `results_that_matter.table[5].commentary`. Recorded verdict: `stated`.

Summary context: Management attributes the decrease primarily to a $100 million decrease in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements, and lower spending of $60 million in corporate enabling functions.

Flagged cause: a $100 million decrease in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements

Supplied-passages assessment: **detached driver bullet**. Full-excerpt assessment: **supported**.

The table row anchor is Selling, informational and administrative expenses, 2,961 versus 3,031 million. Full retained source explicitly says these expenses decreased 70 million in Q1 2026, primarily reflecting the contiguous 100 million marketing/promotional-spend bullet and 60 million corporate-function bullet. The flagged marketing clause is supported for the correct measure and period. Reconstructed supplied passage 1 contains only the detached marketing bullet; the other three passages are unrelated. Thus the full-source rescue is correct, but the retained label does not prove the supplied context or model reasoning established the SIA subject. The old prompt omits the table anchor; raw quote/reason was not saved.

### 6. PFE 10-Q repeat 1 — confirmed rescue

Slot: `results_that_matter.table[6].commentary`. Recorded verdict: `stated`.

Summary context: Management attributed the decrease primarily to a $100 million reduction in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements, and lower spending of $60 million in corporate enabling functions.

Flagged cause: a $100 million reduction in marketing and promotional spend on various products from more targeted investments and ongoing productivity improvements

Supplied-passages assessment: **detached driver bullet**. Full-excerpt assessment: **supported**.

Same full-source SIA explanation as clause 5, at table row 6 rather than row 5. Replacing decrease with reduction is a faithful restatement. The full retained source links the 100 million marketing reduction to the same SIA decrease in Q1 2026. Supplied windows still omit the SIA lead-in, so this is a correct full-source rescue with incomplete supplied subject context, not evidence that the existing prompt supplies or reasons over that context.

### 7. F 10-Q repeat 0 — unsafe prospective drop

Slot: `balance_sheet_liquidity.maturities_covenants[0]`. Recorded verdict: `not_stated`.

Summary context: Company excluding Ford Credit debt payable within one year declined to $3,268 million at March 31, 2026 from $5,550 million at December 31, 2025, reflecting the settlement of the $2.3 billion 0.00% Convertible Senior Notes.

Flagged cause: the settlement of the $2.3 billion 0.00% Convertible Senior Notes

Supplied-passages assessment: **partial scope**. Full-excerpt assessment: **supported by anchored note**.

Selected windows contain the explicit March 16 settlement of 2.3B convertible notes and the cash repayment but omit the current-debt table. Full Note 12 attaches footnote (a) to convertible notes falling from 2,300 million to zero within Company-excluding-Ford-Credit debt payable within one year, whose total falls from 5,550 to 3,268 million. The actual extinguishment of this identified component supports the settlement explanation for the same debt scope and quarter. It does not assert that the exact total movement equals 2.3B. Removing the explanation is unsafe; this repeats the note-supported cases in run 1.

### 8. F 10-Q repeat 1 — unsafe prospective drop

Slot: `balance_sheet_liquidity.maturities_covenants[0]`. Recorded verdict: `not_stated`.

Summary context: Company excluding Ford Credit debt payable within one year was $3,268 million at March 31, 2026, down from $5,550 million at December 31, 2025, reflecting the settlement of the $2.3 billion 0.00% Convertible Senior Notes.

Flagged cause: the settlement of the $2.3 billion 0.00% Convertible Senior Notes

Supplied-passages assessment: **partial scope**. Full-excerpt assessment: **supported by anchored note**.

Same Ford note-anchored settlement as clause 7 and both run 1 repeats. The source table and attached footnote identify removal of the 2.3B component from the same current-debt balance. Selected windows lose the table anchor, while the full excerpt supplies it. The small wording change from declined to was/down does not change the relationship or make this a fictional cause.

### 9. INTC 10-Q repeat 0 — confirmed rescue

Slot: `segments[3].commentary`. Recorded verdict: `stated`.

Summary context: 16% operating margin — All other revenue was $628 million, down $315 million from Q1 2025, primarily driven by lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue of $558 million, up $120 million, primarily driven by higher demand for Eye Q products.

Flagged cause: higher demand for Eye Q products

Supplied-passages assessment: **supported**. Full-excerpt assessment: **supported**.

The summary correctly attaches higher Eye Q product demand to the Mobileye revenue increase of 120 million to 558 million, within the All other segment explanation. Supplied passages 1 and 2 explicitly contain that relationship; the full source continues Eye Q across a trademark/line break to products. This cause is not being assigned to the separate Altera-driven decline in total All other revenue. Supported rescue.

### 10. INTC 10-Q repeat 1 — unsafe prospective drop

Slot: `segments[3].commentary`. Recorded verdict: `not_stated`.

Summary context: 16% operating margin — Revenue decreased primarily due to lower revenue resulting from the deconsolidation of Altera in Q3 2025, partially offset by higher Q1 2026 Mobileye revenue of $558M, up $120M, primarily driven by higher demand for EyeQ products.

Flagged cause: higher demand for EyeQ products

Supplied-passages assessment: **wrong subject**. Full-excerpt assessment: **supported**.

The summary uses EyeQ as one word, but the filing spells Eye Q with a trademark/line break. Full source states exactly the Mobileye relationship: revenue of 558 million, up 120 million, primarily driven by higher demand for Eye Q products. The supplied four windows instead concern DCAI networking, client volume, supply constraints and server ASPs; none contains the Mobileye explanation. Comparing clause 9 isolates an observed tokenization/ranking sensitivity: the faithful joined spelling loses the relevant passage. This is an unsafe prospective drop. No inference about an unretained model rationale is needed.

### 11. ASML 20-F repeat 1 — uncertain drop

Slot: `the_print.key_takeaways[3]`. Recorded verdict: `not_stated`.

Summary context: Net cash provided by operating activities of EUR 12,658.5M; net cash used in financing activities of EUR 8,670.5M, reflecting a EUR 5,450.0M increase in share repurchases.

Flagged cause: a EUR 5,450.0M increase in share repurchases

Supplied-passages assessment: **truncated counterpart**. Full-excerpt assessment: **level vs change**.

Full financing discussion says cash used in financing activities increased by EUR 5,838.4M, primarily driven by a EUR 5,450.0M increase in share repurchases, with bond/dividend outflows and financing offsets. Selected passages are truncated fragments without that starting subject/amount. The summary attaches the buyback increase to the annual cash-use level of EUR 8,670.5M, not explicitly to its change. The relationship exists but the level-versus-change role is compressed. Retain as unresolved, consistent with run 1, rather than treating source omission or a not_stated label as proof of a false attribution.

### 12. SE 20-F repeat 1 — unsafe prospective drop

Slot: `the_print.what_changed`. Recorded verdict: `not_stated`.

Summary context: Total revenue increased 36.4% from US$16.8 billion in 2024 to US$22.9 billion in 2025, and net income rose from US$447.8 million to US$1.6 billion. The filing attributes the revenue increase to growth across its businesses, including e-commerce service revenue growth of 33.9% on GMV growth of 26.8%, digital financial services revenue growth of 60.1% on loans receivable growth, and digital entertainment revenue growth of 26.1% on higher active and paying users.

Flagged cause: growth across its businesses, including e-commerce service revenue growth of 33.9% on GMV growth of 26.8%, digital financial services revenue growth of 60.1% on loans receivable growth

Supplied-passages assessment: **partial compound support**. Full-excerpt assessment: **supported segment synthesis**.

Supplied passage 2 correctly states the current-year digital-financial-services growth and loan-growth explanation, but other passages are generic, prior-year or expense context; they omit the Shopee counterpart. Full 2025-versus-2024 Revenue section starts with total revenue growth of 36.4%, then explicitly links Shopee service growth of 33.9% to GMV growth of 26.8%, finance growth of 60.1% to increased lending/loans, and Garena growth of 26.1% to active/paying users. The summary preserves these individual business relationships, not a single segment cause transferred to all group revenue. The extracted flagged clause stops before the Garena conjunction. Dropping the retained compound business explanation is unsafe. Its exact audit record matches replay despite the separate checked-count mismatch.

### 13. PDD 20-F repeat 0 — uncertain drop

Slot: `earnings_quality.operating_vs_one_time`. Recorded verdict: `not_stated`.

Summary context: Net income of RMB 97.8B in 2025 included interest and investment income, net of RMB 25.6B (up from RMB 20.6B in 2024), other income, net of RMB 2.7B, a foreign exchange loss of RMB 2.0B, income tax expenses of RMB 21.7B and share of profits of equity investees of RMB 129.0M. Operating profit of RMB 93.1B was lower than net income, reflecting the contribution of non-operating income lines. Share-based compensation expenses totaled RMB 7.9B in 2025, down from RMB 9.9B in 2024.

Flagged cause: the contribution of non-operating income lines

Supplied-passages assessment: **partial bridge**. Full-excerpt assessment: **accounting relationship**.

The summary says operating profit of 93.1B is lower than net income of 97.8B, reflecting the contribution of non-operating income lines. Full source places net interest/investment income of 25.6B, FX loss of 2.0B and other income of 2.7B between operating profit and pretax income, followed by tax expense of 21.7B and investee profit of 0.129B before net income. Its narrative says net income is a result of the foregoing. The supplied windows include interest income and the final net-income statement, but not the whole bridge. This is a broadly true accounting relationship rather than a newly asserted operating driver; the wording compresses the tax offset. As with run 1 ratio/decomposition cases, product policy should settle whether such restatements need a separately stated causal sentence. Do not classify it as a confirmed hallucination or clean safe drop.

## Review method and limits

Each potential unsafe drop was checked against the actual filing counterpart and then challenged for subject, period, amount and business-scope transfer. This second check confirms the Ford note, Intel Mobileye cause and Sea business-specific synthesis. It does not resolve ASML level/change wording or the general accounting-bridge policy. Strict-rule correct JPM drops mean the causal sentence is not issuer-stated in the retained excerpt; the share-count arithmetic is not alleged to be wrong.

The full source means the retained grounding excerpt, not omitted pages of the original filing. Negative findings combine the relevant retained comparison/note with searches for alternative explanatory wording; they cannot establish absence from material outside that excerpt. Quotes/reasons and the pre-binding SE checked clause are unavailable. The all-flagged-clause scope does not validate any unflagged neighboring commentary.

Machine evidence is in [machine clause ledger](e2-run2-clause-read-2026-09-19.json); reconstructed windows are also in `work/e2-run2-read/passages.txt`. Bounded full-excerpt contexts are retained in `work/e2-run2-read/full-source-context.txt`. The original artifact remains authoritative. The scripts perform pure reconstruction and write this manual assessment; no repository code, tests or configuration was changed, and no models were called.
