# Current E2 control miss study — 19 September 2026

**Revised 20 September 2026 after independent audit; independent and parent review complete.** This extends E4 using newly returned full Fable reasons. It does not replace the earlier #921 study of a different retained corpus with 12 misses and missing reasons.

All 35 selected attempts were read: 16 from control 1 and 19 from control 2, containing 52 G4 reason strings. Under the conservative assessment below, 15 attempts contain at least one independently witnessed unsupported source attribution; 20 remain unresolved. The 52 original reason strings have 17 unsupported and 35 unresolved manual assessments. None is classified wholly supported. Multiple allegations can occur in one reason or attempt. These are attempt counts, not clause-level recall or precision.

| Corpus | Attempts reviewed | Confirmed attribution mismatch | Unresolved |
|---|---:|---:|---:|
| Control 1 | 16 | 6 | 10 |
| Control 2 | 19 | 9 | 10 |

“Unsupported” means a witnessed source-ownership/scope mismatch, not proof that the economic relationship is impossible. “Unresolved” means this read does not independently confirm the alleged defect; it does not clear the output or overturn Fable. Within mixed attempts, the JSON records each reason’s assessment.

The independent audit downgraded four manual reason assessments to unresolved: C1-10 reason 0 (institutional volume drag), C2-10 reason 0 (ambiguous operating-segment offset), C2-13 reason 1 (repurchases), and C2-14 reason 1 (nested transaction-revenue bridge). Only C1-10 changes its attempt-level classification. Original Fable verdicts and reason text are unchanged; this correction changes neither finder replay nor historical #921 evidence. Reason indexes here are zero-based, as in the JSON.

## Evidence and method

The complete returned reports remain in retained task outputs at `claude-judge-results/e2/judged.json` and `claude-judge-results/e2-control2/judged.json`; these are task-artifact paths, not repository files. The [independent E2 audit](e2-fable-audit-2026-09-19.md) and [normalized original verdicts](e2-fable-verdicts-2026-09-19.json) are archived in this repository. Their SHA-256 hashes are respectively `d5c6a293aa7fb79b416f0df5c47bf90f67960601c8946b3180248838dbacb54d` and `15ec6a1c23cdaeda1a56432c152d45fc7c6a9c6e9cd790e073d63db58f207faa`. They retain the same `cli:claude-fable-5-1` contract 2 judging evidence reviewed in the existing E2 audit. This study makes no additional CLI invocation attestation.

The finder was reconstructed from frozen source `73cc31162c3dfe7ec497c8c88c43cf397afce4a7`; file hash `66924c25c4d73bac636e49ab5f0114c0b14ea584c71d93f937348c4545787d42`. Control 1’s synthetic source tree was already verified equal to 73cc for app/prompts/evals; control 2 used 73cc. Only stdlib-backed pure finder functions were replayed on the final retained `raw_sections`. No tests or model calls ran.

The recorded `unverified` list preserves lexical candidates regardless of subsequent verifier verdict. Therefore these 35 attempts genuinely have no recorded finder flags; they are not “stated” verdicts being mistaken for missing flags. Final replay also yields zero candidates for every selected attempt. Recorded checked counts agree with final replay for 32 non-null audits; two null audits (SE control 1, NVO control 1) replay zero. MELI control 1 records 13 checked versus 9 final-replayed clauses. Its pre/post-binding difference remains unresolved; no exact audit-stage trace is claimed.

Source checks use the full retained grounding excerpt, with targeted examination of the claimed metric and driver and adjacent context. A negative search is not proof of absence from the entire original filing. The companion JSON contains full judge reasons, exact selected output fields and owner rows, source witnesses with normalized character offsets, original excerpt hashes, and every reconstructed lexical clause. Local scratch includes the full retained 35 records and replay script.

Two refutation passes informed the confirmed findings: first check the actual output field and its metric/segment owner instead of trusting the judge’s compressed quote; then examine the source’s stated owner and possible alternative support. This corrected the witness location for COIN control 2 and ASML, and avoided adopting overstrong claims that rising costs cannot coexist with rising margin, or that any adjustment exclusion can never affect a reconciliation.

## Why no finder flag appeared

| Mechanism | Attempts containing it |
|---|---:|
| Allegation in an unscanned output field | 4 |
| Detected relation accepted by lexical overlap | 17 |
| Relation outside finite connective grammar | 21 |
| Contested tail lies beyond discovered clause | 3 |
| Judge relies on adjacency/implication | 1 |
| Recorded versus final replay stage differs | 1 |

These counts overlap. They identify mechanisms affecting the alleged text, not a count of all causal clauses. An attempt can contain many correctly detected other clauses while its alleged relation is not discovered. “Lexical accept” also includes unresolved accounting bridges; it is not automatically a confirmed false acceptance.

The four omitted-surface attempts are SE control 1 risk, TSLA control 1 red flag, PDD control 2 risk, and COIN control 2 risk. The finite grammar omits ordinary “as,” “reflects/reflected,” “in line with,” “driven in part by,” and some forecast or offset constructions. Broad source windows and a one-token subject match can accept a detected driver whose source actually concerns another metric or segment. Because these allegations never became verifier candidates, this study does not diagnose evidence-window ranking inside the model verifier.

## Bounded next work — proposals only

1. Design one source-to-candidate fixture around explicit wrong-owner transfers (AAPL Americas → total sales, BABA segment → consolidated EBITA, PLTR cost → margin). Preserve qualifying positive same-owner cases. Investigate whether lexical acceptance can require adequate metric/scope ownership while retaining the verifier’s one-call/candidate cap and unknown behavior. No change is selected here.
2. Study scanner coverage for risks/red_flags and finite variants such as “reflects” and “driven in part by.” Measure candidate count/cap displacement on retained data before widening surfaces or activating any deletion. Forecast language needs its own policy boundary.
3. Study coordinated offset tails and abbreviation boundaries (WMT “U.S.”; COIN institutional suffix). Preserve context and ownership rather than simply treating every tail as an independent cause.
4. Calibrate the arithmetic/co-movement boundary with human review, particularly EPS/NI, balance-sheet component bridges, NVO adjacency, WMT’s compressed two-year attribution and SE’s “as a result of the foregoing.” These 20 unresolved attempts are not validated automatic-deletion targets.

No implementation, flags, live measurement, retrieval fix, or quality/effect claim follows from this study. It cannot estimate clause-level recall, and comparisons with the older 12-miss corpus cannot establish causal improvement.

## Per-attempt evidence

Identity includes corpus, ticker/form and zero-based retained run. Full accessions, 52 original reasons and detailed lexical matches are in the [machine companion](e4-current-control-miss-study-2026-09-20.json). The excerpts below are shortened for reading; ellipses mark clipping, not contiguous source claims.

### C1-01 — SE 6-K, run 0: unsupported

Finder: recorded checked None; final replay 0; candidates 0. Mechanisms: allegation in an unscanned output field.

Source owns credit-business growth for Monee revenue/cost, while its credit-loss paragraph reports the change without that driver. The risk summary transfers the explanation to the provision. This confirms unsupported source attribution, not that credit growth cannot affect losses.

- Output `risks[0].summary`: “Provision for credit losses increased 71.5% to US$555.2 million, reflecting growth in the credit business.”

- Retained source: “[…] 025, primarily driven by the growth of GMV and improved monetization. Monee: GAAP revenue increased by 58.9% to US$1.4 billion in the second quarter of 2026 from US$882.8 million in the second quarter of 2025, primarily driven by the growth of our credit business as our lending activities increased. Garena: GAAP revenue increased by 33.5% to US$746.6 million in the second quarter of 2026 from US$559.1 million in the second quarter of 2025. This increase was primarily due to t […]”
- Retained source: “[…]  quarter of 2026 from US$323.3 million in the second quarter of 2025. Provision for Credit Losses Our provision for credit losses increased by 71.5% to US$555.2 million in the second quarter of 2026 from US$323.7 million in the second quarter of 2025. Research and Development Expenses Our research and development expenses increased by 5.6% to US$314.2 million in the second quarter of 2026 from US$297.4 million in the second quarter of 2025. Non-operating Income or Losses, Net […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C1-02 — PLD 10-K, run 1: unresolved

Finder: recorded checked 4; final replay 4; candidates 0. Mechanisms: detected relation accepted by lexical overlap, relation outside finite connective grammar.

All three allegations are component bridges: earnings/disposal gains/interest, operating income/disposals, and total revenue/rental revenue. The source has the line items and an interest-expense-specific cause; the reproduced matcher also accepts generic unconsolidated-earnings discussion. No exact management attribution for the totals was located. That does not by itself prove the bridges financially false or settle the strict G4 policy boundary.

- Output `results_that_matter.table[2].commentary`: “Net earnings declined primarily due to lower gains on real estate dispositions and higher interest expense.”
- Output `results_that_matter.table[1].commentary`: “Operating income declined as gains on real estate dispositions decreased to $944M from $1.32B, partially offset by higher rental revenues.”
- Output `the_print.what_changed`: “Total revenues increased 7.2% to $8.79B in 2025 from $8.20B in 2024, primarily due to rental revenues increasing 8.6% to $8.16B, partially offset by strategic capital revenues declining 11.9% to $592M. Net earnings attributable to controlling interests decreased 10.8% to $3.33B, as gains on real estate transactions declined to $944M from $1.32B in 2024. Operating income decreased 1.3% to $4.36B.”

- Retained source: “[…]  Weighted average effective interest rate during the year 3.2 % 3.1 % Interest expense increased in 2025, as compared to 2024, principally due to the issuance of senior notes to finance acquisition and development activities with higher interest rates on new issuances. We issued $3.4 billion of senior notes during 2025 and $4.2 billion during 2024, with a weighted average interest rate of 4.2% and 4.8%, respectively, at the issuance date. See Note 7 to the Consolidated Financ […]”
- Retained source: “[…] ded in our same store portfolio. Other Components of Income (Expense) Earnings from Unconsolidated Entities, Net We recognized net earnings from unconsolidated entities, which are primarily accounted for using the equity method, of $403 million and $354 million during 2025 and 2024, respectively. The earnings we recognize from unconsolidated entities can be impacted by: (i) the size, rental rates and occupancy of the portfolio of properties owned by each venture; (ii) interes […]”

G4 reasons reviewed: 3. reason 1: unresolved; reason 2: unresolved; reason 3: unresolved.

### C1-03 — NEE 10-Q, run 0: unsupported

Finder: recorded checked 6; final replay 6; candidates 0. Mechanisms: relation outside finite connective grammar.

The revenue row reuses higher results across FPL/NEER, which the source expressly owns for net income. Its later NEER revenue clause is separately supported and does not validate that opening. Operating-income/expense and EPS/net-income co-movement allegations remain unresolved accounting bridges.

- Output `results_that_matter.table[0].commentary`: “The increase reflects higher results across FPL and NEER; NEER operating revenues for the quarter increased $618 million primarily due to the impact of non-qualifying commodity hedges and revenues from new investments of $213 million.”
- Output `results_that_matter.table[1].commentary`: “Operating income rose with the increase in operating revenues, partly offset by higher total operating expenses - net, which increased to $5,289M from $4,807M.”
- Output `results_that_matter.table[3].commentary`: “Diluted EPS rose in line with the increase in net income attributable to NEE.”

- Retained source: “[…]  fuel clause or base rates. See Note 2. RESULTS OF OPERATIONS Summary Net income attributable to NEE increased $1,116 million and $2,464 million for the three and six months ended June 30, 2026, respectively, reflecting higher results at FPL, NEER and Corporate and Other. FPL's increase in net income for the three and six months ended June 30, 2026 was primarily driven by continued investments in plant in service and other property. NEER's results increased for the three mont […]”
- Retained source: “[…] erating Revenues During the three and six months ended June 30, 2026, operating revenues increased $188 million and $462 million, respectively. Retail base revenues during the three and six months ended June 30, 2026 increased by approximately $276 million and $561 million, respectively, reflecting additional revenues of $251 million and $451 million, respectively, related to new retail base rates under the 2025 rate agreement. Retail base revenues for the three and six month […]”

G4 reasons reviewed: 3. reason 1: unresolved; reason 2: unsupported; reason 3: unresolved.

### C1-04 — AAPL 10-K, run 0: unresolved

Finder: recorded checked 10; final replay 10; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The total-sales explanation combines true category/segment movements. Exact source wording found is segment-specific; broad lexical overlap accepts the total-level clause. Unlike the explicit Americas-to-total management attribution in C2-07, this general composition statement remains an unresolved arithmetic/source-attribution boundary.

- Output `results_that_matter.table[0].commentary`: “The increase was driven by higher net sales across most reportable segments and product categories, with Services net sales up 14% and iPhone net sales up 4%.”

- Retained source: “[…] 58 4 %29,615 Total net sales$416,161 6 %$391,035 2 %$383,285 Americas Americas net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services. The weakness in foreign currencies relative to the U.S. dollar had an unfavorable year-over-year impact on Americas net sales during 2025. Europe Europe net sales increased during 2025 compared to 2024 primarily due to higher net sales of Services, iPhone and Mac. Greater China Greater China n […]”
- Retained source: “[…] imarily due to lower net sales of Accessories and Wearables. Services Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services. Apple Inc. | 2025 Form 10-K | 23 Gross Margin Products and Services gross margin and gross margin percentage for 2025, 2024 and 2023 were as follows (dollars in millions): 202520242023 Gross margin: Products$112,887 $109,633 $108,803 Services82,314 71,050 60,345 Tot […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C1-05 — MSFT 10-K, run 1: unsupported

Finder: recorded checked 7; final replay 7; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The source assigns impairments to investment losses and equity-derivative losses to derivatives, not the primary decrease in total other income/expense. Its Other, net line changes from -1,319 to -4,725 and explicitly concerns equity-method investments including OpenAI. The summary promotes component causes to the aggregate primary driver.

- Output `earnings_quality.operating_vs_one_time`: “Other income (expense), net was $(4,901) million, a decrease of $3,255 million from $(1,646) million in the prior year, primarily due to higher impairments on investments and higher losses on equity derivatives. The effective tax rate was 18% for both fiscal years 2025 and 2024.”

- Retained source: “[…] Other, net (4,725 ) (1,319 ) (223 ) Total $ (4,901 ) $ (1,646 ) $ 788 Other, net primarily reflects net recognized losses on equity method investments, including OpenAI. Net Recognized Gains (Losses) on Investments Net recognized gains (losses) on debt investments were as follows: (In millions) Year Ended June 30, 2025 2024 2023 Realized gains from sales of available-for-sale securities $ 40 $ 22 $ 36 Realized losses from sales of available-for-sale securities (65 ) (98 ) (12 […]”
- Retained source: “[…] est expense, offset in part by higher finance lease interest expense. Net recognized losses on investments increased primarily due to higher impairments, offset in part by higher gains on equity investments in the current period. Net losses on derivatives increased primarily due to higher losses on equity derivatives in the current period. Other, net primarily reflects net recognized losses on equity method investments, including OpenAI. INCOME TAXES Effective Tax Rate Our ef […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C1-06 — NVDA 10-Q, run 1: unresolved

Finder: recorded checked 14; final replay 14; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

Repurchases are real, but the source diluted-share bridge also changes the dilutive equity-award increment from 170 to 105. The matcher accepts share repurchases as complete lexical support without establishing ownership of the diluted-count movement. A partial economic contribution is plausible; no exact attribution was located.

- Output `results_that_matter.table[4].commentary`: “Diluted weighted average shares fell to 24,391M from 24,611M, reflecting share repurchases.”

- Retained source: “[…] 8,321 $18,775 Denominator: Basic weighted average shares24,286 24,441 Dilutive impact of outstanding equity awards105 170 Diluted weighted average shares24,391 24,611 Net income per share: Basic (1)$2.40 $0.77 Diluted (2)$2.39 $0.76 Anti-dilutive equity awards excluded from diluted net income per share47 62 (1) Net income divided by basic weighted average shares. (2) Net income divided by diluted weighted average shares. Diluted net income per share was computed using the wei […]”
- Retained source: “[…]  2026, our Board of Directors approved an additional $80.0 billion in share repurchase authorization, without expiration. 18 NVIDIA Corporation and Subsidiaries Notes to Condensed Consolidated Financial Statements (Continued) (Unaudited) We paid cash dividends to our shareholders of $243 million and $244 million during the first quarter of fiscal years 2027 and 2026, respectively. On May 18, 2026, we increased our quarterly cash dividend from $0.01 per share to $0.25 per shar […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C1-07 — KO 10-Q, run 1: unresolved

Finder: recorded checked 8; final replay 8; candidates 0. Mechanisms: relation outside finite connective grammar.

Reflects is not a discovered connective. The NI explanation composes operating/equity/other-income line movements; the prior $331m CCEP gain is documented. No same-line NI attribution was located, but a partial accounting bridge is not disproved merely by omitted items.

- Output `results_that_matter.table[3].commentary`: “The increase reflects the higher operating income and equity income, partly offset by lower other income — net, which included a $331 million gain on the prior-year sale of a portion of the ownership interest in CCEP.”

- Retained source: “[…]  which we received cash proceeds of $741 million and recognized a net gain of $331 million, which was recorded in the line item other income (loss) — net in our consolidated statement of income. Assets and Liabilities Held for Sale In October 2025, the Company entered into a definitive agreement to sell a portion of our interest in our bottling operations in Africa to Coca-Cola HBC AG (“CCHBC”), an equity method investee. Closing is subject to various regulatory approvals and […]”
- Retained source: “[…] ting Income4,359 3,659 Interest income222 180 Interest expense375 387 Equity income (loss) — net384 351 Other income (loss) — net21 254 Income Before Income Taxes4,611 4,057 Income taxes 645 722 Consolidated Net Income3,966 3,335 Less: Net income (loss) attributable to noncontrolling interests42 5 Net Income Attributable to Shareowners of The Coca-Cola Company$3,924 $3,330 Basic Net Income Per Share1 $0.91 $0.77 Diluted Net Income Per Share1 $0.91 $0.77 Average Shares Outstan […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C1-08 — TSLA 10-K, run 0: unsupported

Finder: recorded checked 13; final replay 13; candidates 0. Mechanisms: allegation in an unscanned output field, relation outside finite connective grammar.

The red flag expressly attributes the NI-versus-OCF divergence to a source explanation for the $176m OCF decrease alone. That changes the explained quantity. The gross-margin/mix and operating-income/opex as-bridges are separately unresolved; they are not discovered.

- Output `earnings_quality.red_flags[0]`: “Net income attributable to common stockholders decreased 46.5% to $3,794M while net cash provided by operating activities decreased only 1.2% to $14,747M, a divergence the filing attributes primarily to a decrease in net income excluding non-cash expenses, gains and losses of $737M, partially offset by favorable changes in net operating assets and liabilities of $561M.”
- Output `results_that_matter.table[5].commentary`: “Total gross margin was 18.0% in 2025 compared to 17.9% in 2024, as energy generation and storage gross margin increased to 29.8% from 26.2%, partially offset by a decline in total automotive gross margin to 17.8% from 18.4%.”
- Output `results_that_matter.table[1].commentary`: “Operating income declined as total operating expenses increased to $12.74B from $10.37B, including a $1.87B increase in research and development expense.”

- Retained source: “[…] 31, 2025 from $14.92 billion during the year ended December 31, 2024. This decrease was primarily due to a decrease in net income excluding non-cash expenses, gains and losses of $737 million, partially offset by favorable changes in net operating assets and liabilities of $561 million. Cash Flows from Investing Activities Net cash flows from investing activities and their variability across each period related primarily to capital expenditures, which were $8.53 billion and $ […]”

G4 reasons reviewed: 3. reason 1: unsupported; reason 2: unresolved; reason 3: unresolved.

### C1-09 — PLTR 10-Q, run 1: unsupported

Finder: recorded checked 7; final replay 7; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The adjacent source sentences give $39m hosting as the cost-of-revenue increase driver, then state gross margin increased 80% → 87%. The summary attributes margin expansion to hosting. Token overlap and adjacent subject words accept the wrong measure. Refutation: increasing costs can coexist with expanding margin when sales grow faster; the defect is attribution ownership, not that impossible-arithmetic assertion in the judge reason.

- Output `the_print.what_changed`: “Revenue increased by $749 million, or 85%, for the three months ended March 31, 2026 compared to the same period in 2025. Management attributed the increase to increased adoption of products and services within existing customer organizations, noting that of the government increase, $367 million was from government customers existing as of December 31, 2025, and of the commercial increase, $352 million was from commercial customers existing as of December 31, 2025. Gross margin increased from 80% to 87%, which management attributed primarily to an increase of $39 million in third-party cloud hosting services within cost of revenue.”

- Retained source: “[…] Gross profit$1,416,785 $710,885 $705,900 99 % Gross margin87 %80 %7 % Cost of revenue for the three months ended March 31, 2026 increased by $43 million, or 25%, compared to the same period in 2025. The increase was primarily due to an increase of $39 million in third-party cloud hosting services. Our gross margin for the three months ended March 31, 2026 increased from 80% for the same period in 2025 to 87%. Operating Expenses Three Months Ended March 31,Change 20262025Amoun […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C1-10 — COIN 10-Q, run 0: unresolved

Finder: recorded checked 3; final replay 3; candidates 0. Mechanisms: contested tail lies beyond discovered clause, relation outside finite connective grammar.

The source expressly includes the $37.5m institutional spot-volume drag in its total transaction-revenue bridge, alongside the larger institutional derivatives increase. The summary does not say institutional net revenue declined. Omitting that positive offset does not independently prove its stated partial drag is unsupported; reason 0 is unresolved. The suffix still lies past the discovered consumer-clause boundary, a coverage observation rather than a confirmed bad cause. The headline total-revenue/volume as-bridge also remains unresolved.

- Output `the_print.what_changed`: “Total revenue decreased 30.5% YoY to $1.41B from $2.03B, and the company swung to a net loss of $394.1M from net income of $65.6M. Management attributed the transaction revenue decline primarily to a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading, and to a 48% decrease in institutional Trading Volume. Subscription and services revenue decreased 14% YoY to $583.5M, which management attributed to lower blockchain rewards and lower average interest rates, offset in part by higher average USDC balances.”
- Output `the_print.headline`: “Coinbase reported a Q1 2026 net loss of $394.1M (-$1.49 diluted EPS) on total revenue of $1.41B, down 30.5% YoY from $2.03B, as trading volume fell 50% to $202B.”

- Retained source: “[…] ction revenue$755,825 $1,262,208 $(506,383)(40) % of net revenue56 65 Transaction revenue decreased for the three months ended March 31, 2026 as compared to 2025, primarily reflecting: •a decrease in consumer transaction revenue driven by $591.6 million attributed to a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading; and 31 •an increase in institutional transaction revenue driven by:  […]”

G4 reasons reviewed: 2. reason 1: unresolved; reason 2: unresolved.

### C1-11 — COIN 10-Q, run 1: unresolved

Finder: recorded checked 3; final replay 3; candidates 0. Mechanisms: detected relation accepted by lexical overlap, relation outside finite connective grammar.

The three allegations compose total opex from technology/development, operating loss from expenses, and revenue from transaction/subscription lines. The lines support directions but not explicit management attribution. Lexical matches elsewhere in the discussion do not validate the totals. No independent proof that these partial accounting bridges are false was found.

- Output `the_print.what_changed`: “Total revenue decreased 30.5% to $1.41B from $2.03B, and the company swung to a net loss of $394.1M from net income of $65.6M. Management attributed the transaction revenue decline primarily to a $591.6M decrease in consumer transaction revenue tied to a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading. Total operating expenses rose 8.0% to $1.43B, driven by a 48% increase in technology and development expenses.”
- Output `results_that_matter.table[0].commentary`: “Total revenue declined 30.5% YoY, reflecting lower transaction revenue and lower subscription and services revenue.”
- Output `results_that_matter.table[2].commentary`: “The operating result swung to a loss of $21.4M from income of $705.8M, as total operating expenses rose 8.0% to $1.43B.”

- Retained source: “[…]  net35,151 34,365 Other operating expense (income), net34,925 (5,899) Total operating expenses1,434,403 1,328,489 Operating (loss) income(21,421)705,806 Interest expense22,569 20,511 Losses on crypto assets held for investment, net482,356 596,651 Other (income) expense, net(61,641)6,188 (Loss) income before income taxes(464,705)82,456 (Benefit from) provision for income taxes(70,588)16,848 Net (loss) income$(394,117)$65,608 Net (loss) income attributable to common shareholder […]”
- Retained source: “[…] ,982 2,034,295 Operating expenses: Transaction expense195,859 303,026 Technology and development525,648 355,368 Sales and marketing266,726 247,283 General and administrative376,094 394,346 Losses on crypto assets held for operations, net35,151 34,365 Other operating expense (income), net34,925 (5,899) Total operating expenses1,434,403 1,328,489 Operating (loss) income(21,421)705,806 Interest expense22,569 20,511 Losses on crypto assets held for investment, net482,356 596,651  […]”

G4 reasons reviewed: 3. reason 1: unresolved; reason 2: unresolved; reason 3: unresolved.

### C1-12 — BYND 10-Q, run 0: unresolved

Finder: recorded checked 7; final replay 7; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The source separately records the 317,834,446-share exchange and weighted-average shares 455,272,616 versus 76,194,916. Issuance can affect weighted averages; timing and the full weighting bridge were not reconstructed. The lexically accepted causal statement is not independently established as either source-stated or false.

- Output `results_that_matter.table[4].commentary`: “Weighted average common shares outstanding—basic and diluted increased to 455,272,616 from 76,194,916, reflecting share issuance including 317,834,446 New Shares issued in the Exchange Offer and 5,315,857 shares issued on 2030 Notes conversions.”

- Retained source: “[…] ipal amount of 2030 Notes as payment of the SteerCo Premium) and (ii) 317,834,446 New Shares. The tendered and accepted 2027 Notes together represented 97.44% of the aggregate principal amount of 2027 Notes outstanding prior to the Exchange Offer. As of March 28, 2026 and December 31, 2025, $29,459,000 in aggregate principal amount of the 2027 Notes remained outstanding. In addition, in connection with the Exchange Offer, we completed the Consent Solicitation and entered into […]”
- Retained source: “[…] are available to common stockholders—basic and diluted $(0.06)$(0.80) Weighted average common shares outstanding—basic and diluted 455,272,616 76,194,916 The accompanying notes are an integral part of these unaudited condensed consolidated financial statements. 3 BEYOND MEAT, INC. AND SUBSIDIARIES Condensed Consolidated Statements of Comprehensive Loss (In thousands) (unaudited) Three Months Ended March 28, 2026March 29, 2025 Net loss $(28,482)$(61,087) Other comprehensive in […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C1-13 — BABA 20-F, run 0: unresolved

Finder: recorded checked 4; final replay 4; candidates 0. Mechanisms: relation outside finite connective grammar.

The as-link places S&M growth next to operating-income decline. The source explicitly explains operating income through adjusted EBITA and goodwill impairment, with offsets; S&M is a component inside operating results. The summary is incomplete as an explanation, but the economic contribution and whether as asserts a source attribution remain unresolved.

- Output `the_print.headline`: “Alibaba's FY2026 revenue rose 3% to CNY 1,023.7B while net income fell 19% to CNY 102.1B and operating income dropped 64% to CNY 50.2B, as sales and marketing expenses increased 70%.”

- Retained source: “[…] on expense 156,482 64,971 9,419 (58 )% Percentage of revenue 16 % 6 % Our income from operations decreased by 64% from RMB140,905 million, or 14% of revenue, in fiscal year 2025 to RMB50,150 million (US$7,270 million), or 5% of revenue, in fiscal year 2026. The year-over-year decrease was primarily attributable to the 142 Table of Contents decrease in adjusted EBITA and increase in impairment of goodwill, partly offset by the decrease in one-time provisions and non-cash share […]”
- Retained source: “[…] n expense 141,884 242,702 35,184 71 % Percentage of revenue 14 % 24 % Our sales and marketing expenses increased by 70% from RMB144,021 million in fiscal year 2025 to RMB245,023 million (US$35,521 million) in fiscal year 2026. Without the effect of share-based compensation expense, sales and marketing expenses as a percentage of revenue would have increased from 14% in fiscal year 2025 to 24% in fiscal year 2026, primarily attributable to the investment in user experiences of […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C1-14 — ASML 20-F, run 1: unsupported

Finder: recorded checked 9; final replay 9; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The source causal paragraph owns total net system sales (24,474.3m, +12.4%). The final summary attaches it to the New systems row (23.9bn, +13.1%), alongside a separate Used systems row. The finder sees shared system/sales words and accepts it. This is a scope transfer; it does not prove new-system economics contradict the driver.

- Output `segments[0].commentary`: “The increase in system sales was primarily driven by higher EUV and DUV immersion system sales, partially offset by a decrease in ArF dry, KrF and i-line sales volumes; ASML recognized four EXE and 44 NXE systems in sales in 2025 compared to two EXE and 42 NXE systems in 2024.”

- Retained source: “[…] 24 Year ended December 31 (€, in millions) 2024 % 1 2025 % 1 % Change Net system sales 21,768.7 77.0 24,474.3 74.9 12.4 Net service and field option sales 6,494.2 23.0 8,193.0 25.1 26.2 Total net sales 28,262.9 100.0 32,667.3 100.0 15.6 Cost of system sales (10,406.9) (36.8) (11,384.0) (34.8) 9.4 Cost of service and field option sales (3,364.0) (11.9) (4,025.3) (12.3) 19.7 Total cost of sales (13,770.9) (48.7) (15,409.3) (47.2) 11.9 Gross profit 14,492.0 51.3 17,258.0 52.8 19 […]”
- Retained source: “[…] in net service and field option sales of 26.2% compared to 2024. T he increase in system sales was primarily driven by higher EUV and DUV immersion system sales – this was partially offset by a decrease in ArF dry, KrF and i-line sales volumes. The increase in net service and field option sales was primarily due to the growing installed base, higher levels of lithography tool use for certain customers and more NXE field upgrades. Our gross profit and gross margin increased in […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C1-15 — NVO 20-F, run 0: unresolved

Finder: recorded checked None; final replay 0; candidates 0. Mechanisms: judge relies on adjacency/implication.

The summary separately states margin contractions and a filing-attributed US after-rebate price decline. The source expressly supports rebates → US prices. No grammatical assertion in the quoted output expressly makes that the margin driver; Fable itself calls the reading borderline. Adjacency alone is not enough for this study to confirm an unsupported cause.

- Output `the_print.what_changed`: “Revenue increased 6.4% YoY to DKK 309.1B while operating income declined 0.5% to DKK 127.7B, producing an operating margin contraction of 2.9 percentage points to 41.3%. Gross margin fell 3.7 percentage points to 81.0%. The filing states that average prices after rebates for the Novo Nordisk portfolio in 2025 in the United States declined, and that US payers continue to leverage their size and control to demand higher rebates, particularly in the insulin segment but increasingly in the GLP-1 category.”

- Retained source: “[…] egment, but increasingly in the GLP-1 category, as well. As a result, average prices after rebates for the Novo Nordisk portfolio in 2025 in the United States declined. Ultimately, pricing pressure is expected to continue in the future, driven by: increasing rebates in the commercial segment, the effect of payer consolidation, increasing exposure to high rebate channels such as Medicare and Medicaid, increasing sales in direct-to-patient cash channel as well as increasing com […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C1-16 — MELI 10-K, run 1: unresolved

Finder: recorded checked 13; final replay 9; candidates 0. Mechanisms: relation outside finite connective grammar, recorded versus final replay stage differs.

Driven in part by is outside the finite connective grammar. Assets and restricted cash both rise in the balance sheet; the source does not supply an explicit total-assets cause in the reviewed context. This partial balance-sheet bridge remains unresolved. Audit checked 13 versus final raw replay 9 prevents treating the reconstructed stage as an exact audit-stage trace.

- Output `the_print.key_takeaways[3]`: “Total assets grew to $42.7B from $25.2B, driven in part by restricted cash and cash equivalents of $9.9B versus $2.1B.”

- Retained source: “[…] s 1,541 802 Other assets 426 182 Total non-current assets 9,094 5,054 Total assets $ 42,667 $ 25,196 Liabilities Current liabilities: Accounts payable and accrued expenses $ 4,502 $ 3,196 Funds payable to customers 13,029 6,954 Amounts payable due to credit and debit card transactions 3,584 1,923 Salaries and social security payable 916 727 Taxes payable 1,140 525 Loans payable and other financial liabilities 4,623 2,828 Operating lease liabilities 430 241 Other liabilities 4 […]”
- Retained source: “[…] 2024 Assets Current assets: Cash and cash equivalents $ 3,670 $ 2,635 Restricted cash and cash equivalents 9,867 2,064 Short-term investments 2,629 4,485 Accounts receivable, net 369 255 Credit card receivables and other means of payments, net 6,893 5,288 Loans receivable, net of allowances of $ 3,057 and $ 1,630 (Note 5) 8,855 4,716 Inventories 570 296 Other assets 720 403 Total current assets 33,573 20,142 Non-current assets: Long-term investments 1,764 1,203 Credit card re […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-01 — SE 6-K, run 1: unresolved

Finder: recorded checked 1; final replay 1; candidates 0. Mechanisms: relation outside finite connective grammar.

The alleged as-links are not discovered; the sole checked clause concerns non-operating interest income. The release enumerates expenses/tax and says net income rose as a result of the foregoing. This weakens a blanket no-causal-decomposition allegation, but does not precisely attribute the revenue/NI growth gap or operating-income movement to the selected expenses.

- Output `the_print.what_changed`: “Revenue growth of 48.1% outpaced net income growth of 10.6% as total operating expenses increased 50.9% to US$2.9 billion, including a 64.5% increase in sales and marketing expenses to US$1.7 billion and a 71.5% increase in provision for credit losses to US$555.2 million. Income tax expense rose 74.0% to US$250.6 million.”
- Output `results_that_matter.table[2].commentary`: “Operating income increased 33.3% year-on-year as total operating expenses increased 50.9% to US$2.9 billion.”

- Retained source: “[…] the second quarter of 2026 and 2025, respectively. Net Income or Loss As a result of the foregoing, our net income increased by 10.6% to US$458.1 million in the second quarter of 2026 from US$414.2 million in the second quarter of 2025. 6 Basic and Diluted Earnings or Loss Per Share Attributable to Sea Limited’s Ordinary Shareholders Basic earnings per share attributable to Sea Limited’s ordinary shareholders was US$0.72 in the second quarter of 2026, compared to basic earnin […]”
- Retained source: “[…] 5,155) 71.5 Research and development expenses (297,428) (314,160) 5.6 Total operating expenses (1,922,091) (2,899,557) 50.9 Operating income 487,719 650,329 33.3 Non-operating income, net 83,299 65,537 (21.3 Income tax expense (144,056) (250,604) 74.0 Share of results of equity investees (12,758) (7,146) (44.0 Net income 414,204 458,116 10.6 Earnings per share attributable to Sea Limited’s ordinary shareholders: Basic 0.68 0.72 5.9 Diluted 0.65 0.70 7.7 Change in deferred rev […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-02 — PDD 6-K, run 0: unsupported

Finder: recorded checked 5; final replay 5; candidates 0. Mechanisms: allegation in an unscanned output field, relation outside finite connective grammar.

The source executive quote states stepped-up ecosystem investment and a long-term development priority. The summary adds that higher S&M is included and may continue pressuring profitability. The separate S&M expense statement does not establish that classification or the forecast. Risks is outside finder surfaces; may continue to pressure is also not a recognized connective.

- Output `risks[1].summary`: “Increased ecosystem investments, including higher sales and marketing expenses, may continue to pressure profitability.”

- Retained source: “[…] mitted to safeguarding consumer rights and building lasting trust. ” “We stepped up our ecosystem investments in the second quarter,” said Ms. Jun Liu, VP of Finance of PDD Holdings. “At this stage, our priority is helping merchants thrive and strengthening the broader industry ecosystem. We will continue to focus on these fundamentals to drive the platform’s sustainable development over the long term. ” 1 This announcement contains translations of certain Renminbi (“RMB”) am […]”
- Retained source: “[…] se was primarily due to the increase in sales and marketing expenses. Sales and marketing expenses were RMB29.7 billion (US$4.4 billion), compared with RMB27.2 billion in the same quarter of 2025. General and administrative expenses were RMB2.3 billion (US$345 million), compared with RMB1.5 billion in the same quarter of 2025. Research and development expenses were RMB4.6 billion (US$673 million), compared with RMB3.6 billion in the same quarter of 2025. Operating profit in t […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C2-03 — PLD 10-K, run 0: unresolved

Finder: recorded checked 1; final replay 1; candidates 0. Mechanisms: relation outside finite connective grammar, detected relation accepted by lexical overlap.

Net earnings/disposal/interest, operating income/disposals, and total revenue/rental are component bridges as in C1-02. Reflects/as are undiscovered; rental-driven revenue is detected and accepted against rental discussion. The source supports component movements, not an exact aggregate management cause in reviewed passages; financial falsity is not established.

- Output `results_that_matter.table[2].commentary`: “The decline reflects lower gains on real estate dispositions and higher interest expense, partly offset by higher rental revenues.”
- Output `the_print.key_takeaways[1]`: “Net earnings attributable to controlling interests declined 10.8% to $3.33B and diluted EPS fell to $3.56 from $4.01, with operating income of $4.36B roughly flat versus $4.42B as gains on real estate dispositions decreased.”
- Output `the_print.key_takeaways[0]`: “Total revenues rose 7.2% to $8.79B, driven by rental revenues of $8.16B (up 8.6% from $7.51B) and development management and other revenues of $38.9M (up from $15.0M), partly offset by strategic capital revenues declining to $592M from $672M.”

- Retained source: “[…]  Weighted average effective interest rate during the year 3.2 % 3.1 % Interest expense increased in 2025, as compared to 2024, principally due to the issuance of senior notes to finance acquisition and development activities with higher interest rates on new issuances. We issued $3.4 billion of senior notes during 2025 and $4.2 billion during 2024, with a weighted average interest rate of 4.2% and 4.8%, respectively, at the issuance date. See Note 7 to the Consolidated Financ […]”
- Retained source: “[…] ded in our same store portfolio. Other Components of Income (Expense) Earnings from Unconsolidated Entities, Net We recognized net earnings from unconsolidated entities, which are primarily accounted for using the equity method, of $403 million and $354 million during 2025 and 2024, respectively. The earnings we recognize from unconsolidated entities can be impacted by: (i) the size, rental rates and occupancy of the portfolio of properties owned by each venture; (ii) interes […]”

G4 reasons reviewed: 2. reason 1: unresolved; reason 2: unresolved.

### C2-04 — NEE 10-Q, run 0: unsupported

Finder: recorded checked 9; final replay 9; candidates 0. Mechanisms: relation outside finite connective grammar.

Reflects higher results across segments is applied to operating revenue. The matching source statement expressly explains net income attributable to NEE. A subsequent supported NEER revenue driver does not establish the preceding consolidated revenue claim.

- Output `results_that_matter.table[0].commentary`: “The increase reflects higher results across the segments; NEER operating revenues for the three months ended June 30, 2026 increased $618 million primarily due to the impact of non-qualifying commodity hedges and revenues from new investments of $213 million.”

- Retained source: “[…]  fuel clause or base rates. See Note 2. RESULTS OF OPERATIONS Summary Net income attributable to NEE increased $1,116 million and $2,464 million for the three and six months ended June 30, 2026, respectively, reflecting higher results at FPL, NEER and Corporate and Other. FPL's increase in net income for the three and six months ended June 30, 2026 was primarily driven by continued investments in plant in service and other property. NEER's results increased for the three mont […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C2-05 — FIGS 10-Q, run 0: unresolved

Finder: recorded checked 7; final replay 7; candidates 0. Mechanisms: relation outside finite connective grammar.

The undiscovered as-link compares revenue growth and opex growth to explain operating income. Source gross-profit discussion additionally emphasizes tariff refunds/COGS. Omitting that factor makes the bridge incomplete, but is not enough to prove the partial relation false; exact management attribution is not located.

- Output `results_that_matter.table[3].commentary`: “Operating income increased as net revenues grew 28.8% while total operating expenses rose 21.9%.”

- Retained source: “[…] tariff refunds, partially offset by higher unit sales and tariffs. 25 Gross profit increased by $45.6 million, or 44.6%, for the three months ended June 30, 2026, compared to the prior year period. The increase in gross profit was primarily due to IEEPA tariff refunds, higher unit sales, and positive impact from price increases, partially offset by tariffs. Gross margin increased 8.2 percentage points for the three months ended June 30, 2026, compared to the prior year period […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-06 — GPRO 10-K, run 1: unresolved

Finder: recorded checked 3; final replay 3; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

R&D and S&M decreased materially and are components of total opex; their own causal descriptions supply lexical words that accept the total-level statement. The omitted goodwill offset matters to completeness. Under strict source-stated-cause policy this is suspect, but a partial arithmetic contribution is not independently disproved.

- Output `results_that_matter.table[4].commentary`: “Total operating expenses decreased 25.6% to $302.5M from $406.3M, driven by decreases in research and development and sales and marketing expenses.”

- Retained source: “[…] 0,178 681,886 Gross profit219,166 271,295 323,573 Operating expenses: Research and development126,796 185,897 165,688 Sales and marketing100,756 160,635 169,578 General and administrative56,355 59,796 63,770 Goodwill impairment18,600 — — Total operating expenses302,507 406,328 399,036 Operating loss(83,341)(135,033)(75,463) Other income (expense): Interest expense(8,452)(3,329)(4,699) Other income, net345 5,273 12,429 Total other income (expense), net(8,107)1,944 7,730 Loss b […]”
- Retained source: “[…] 00,756 160,635 169,578 General and administrative56,355 59,796 63,770 Goodwill impairment18,600 — — Total operating expenses302,507 406,328 399,036 Operating loss(83,341)(135,033)(75,463) Other income (expense): Interest expense(8,452)(3,329)(4,699) Other income, net345 5,273 12,429 Total other income (expense), net(8,107)1,944 7,730 Loss before income taxes(91,448)(133,089)(67,733) Income tax expense (benefit)2,039 299,222 (14,550) Net loss$(93,487)$(432,311)$(53,183) Basic  […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-07 — AAPL 10-K, run 1: unsupported

Finder: recorded checked 9; final replay 9; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

An explicit Management attributes claim for total net sales is supported in the output by a quotation about Americas net sales. Both the retained source and output evidence name Americas. Shared sales/iPhone/Services tokens cause a wrong-scope lexical acceptance.

- Output `results_that_matter.table[0].commentary`: “Management attributes the increase primarily to higher net sales of iPhone and Services, with Services net sales up 14% to $109.2B and iPhone net sales up 4% to $209.6B.”

- Retained source: “[…] 58 4 %29,615 Total net sales$416,161 6 %$391,035 2 %$383,285 Americas Americas net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services. The weakness in foreign currencies relative to the U.S. dollar had an unfavorable year-over-year impact on Americas net sales during 2025. Europe Europe net sales increased during 2025 compared to 2024 primarily due to higher net sales of Services, iPhone and Mac. Greater China Greater China n […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C2-08 — MSFT 10-K, run 0: unresolved

Finder: recorded checked 15; final replay 15; candidates 0. Mechanisms: relation outside finite connective grammar.

The headline as-link places Cloud growth alongside revenue, NI and EPS. The source states revenue growth across each segment and Cloud growth, but does not explicitly own all headline results with that driver. The scope of as is ambiguous and Cloud is a material revenue component; this is not independently confirmed as false attribution.

- Output `the_print.headline`: “Microsoft's FY2025 revenue rose 15% to $281.7B with net income of $101.8B and diluted EPS of $13.64, as Microsoft Cloud revenue increased 23% to $168.9B.”

- Retained source: “[…] Compared with Fiscal Year 2024 Revenue increased $36.6 billion or 15% with growth across each of our segments. Intelligent Cloud revenue increased driven by Azure. Productivity and Business Processes revenue increased driven by Microsoft 365 Commercial cloud. More Personal Computing revenue increased driven by Gaming and Search and news advertising. Cost of revenue increased $13.7 billion or 19% driven by growth in Microsoft Cloud. Gross margin increased $22.9 billion or 13%  […]”
- Retained source: “[…] ights from fiscal year 2025 compared with fiscal year 2024 included: •Microsoft Cloud revenue increased 23% to $168.9 billion. •Microsoft 365 Commercial products and cloud services revenue increased 14% driven by Microsoft 365 Commercial cloud revenue growth of 15%. •Microsoft 365 Consumer products and cloud services revenue increased 11% driven by Microsoft 365 Consumer cloud revenue growth of 11%. •LinkedIn revenue increased 9%. •Dynamics products and cloud services revenue […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-09 — KO 10-Q, run 0: unresolved

Finder: recorded checked 8; final replay 8; candidates 0. Mechanisms: relation outside finite connective grammar.

Same undiscovered reflects NI/component bridge as C1-07. Source confirms the other-income prior CCEP gain and equity/operating changes, without an exact aggregate NI attribution in reviewed context. Omitted income-statement lines do not alone establish false partial causality.

- Output `results_that_matter.table[3].commentary`: “The increase reflects the higher operating income and equity income, partially offset by lower other income (loss) — net, which included a $331 million gain on the sale of a portion of the ownership interest in CCEP in the prior-year period.”

- Retained source: “[…]  which we received cash proceeds of $741 million and recognized a net gain of $331 million, which was recorded in the line item other income (loss) — net in our consolidated statement of income. Assets and Liabilities Held for Sale In October 2025, the Company entered into a definitive agreement to sell a portion of our interest in our bottling operations in Africa to Coca-Cola HBC AG (“CCHBC”), an equity method investee. Closing is subject to various regulatory approvals and […]”
- Retained source: “[…] ting Income4,359 3,659 Interest income222 180 Interest expense375 387 Equity income (loss) — net384 351 Other income (loss) — net21 254 Income Before Income Taxes4,611 4,057 Income taxes 645 722 Consolidated Net Income3,966 3,335 Less: Net income (loss) attributable to noncontrolling interests42 5 Net Income Attributable to Shareowners of The Coca-Cola Company$3,924 $3,330 Basic Net Income Per Share1 $0.91 $0.77 Diluted Net Income Per Share1 $0.91 $0.77 Average Shares Outstan […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-10 — BRK.B 10-K, run 1: unsupported

Finder: recorded checked 4; final replay 4; candidates 0. Mechanisms: relation outside finite connective grammar, detected relation accepted by lexical overlap.

The first allegation is unresolved: operating earnings excluding investment gains/impairment decrease in aggregate, but higher operating segment earnings can refer to the BNSF/BHE/MSR segments expressly named immediately afterward, each of which genuinely rises. The output does not unambiguously claim that aggregate operating earnings rose. The source can include market/FX gains is generic, not a specific 2025 decline cause, but the finder accepts it. Consolidated 199.5bn sales/services and the 214.3bn MSR schedule have different scope, so the component-driver transfer is not validated. Reflected/offset/with relations are not independently discovered.

- Output `the_print.what_changed`: “Total revenues were essentially unchanged at $371.4B versus $371.4B in 2024, while net earnings attributable to Berkshire shareholders declined 24.8% to $67.0B from $89.0B. The decline reflected lower investment gains and an $8.3B after-tax other-than-temporary impairment on Kraft Heinz and Occidental, partially offset by higher operating segment earnings. Insurance underwriting after-tax earnings fell to $7.3B from $9.0B, BNSF rose to $5.5B from $5.0B, BHE rose to $4.0B from $3.7B, and manufacturing, service and retailing rose to $13.6B from $13.1B.”
- Output `results_that_matter.table[7].commentary`: “Investment gains declined versus 2024, reflecting changes in market prices of equity securities and foreign currency exchange rates.”
- Output `results_that_matter.table[5].commentary`: “Sales and service revenues declined, with lower service and retailing revenues partly offset by higher manufacturing revenues.”

- Retained source: “[…] ttributable to noncontrolling interests (in millions). 2025 2024 2023 Insurance – underwriting $ 7,258 $ 9,020 $ 5,428 Insurance – investment income 12,513 13,670 9,567 BNSF 5,476 5,031 5,087 Berkshire Hathaway Energy (“BHE”) 3,979 3,730 2,331 Manufacturing, service and retailing 13,647 13,072 13,362 Investment gains (losses) 30,737 41,558 58,873 Other-than-temporary impairment of investments in Kraft Heinz and Occidental (8,255 ) — — Other 1,613 2,914 1,575 Net earnings attr […]”
- Retained source: “[…] sses. K-34 Management’s Discussion and Analysis Results of Operations Investment gains (losses) can include significant unrealized gains and losses from changes in market prices of our investments in equity securities and in foreign currency exchange rates applicable to certain of our investments. We believe that investment gains and losses, whether realized from dispositions or unrealized from changes in market prices and exchange rates, are generally meaningless in understa […]”
- Retained source: “[…] rance and Other: Insurance premiums earned $ 88,902 $ 88,257 $ 83,403 Sales and service revenues 199,524 202,334 207,148 Leasing revenues 10,034 9,227 8,416 Interest, dividend and other investment income 23,261 21,825 15,764 321,721 321,643 314,731 Railroad, Utilities and Energy: Railroad transportation revenues 23,330 23,355 23,791 Utility and energy operating revenues 21,856 21,518 21,232 Service revenues and other income 4,537 4,917 4,728 49,723 49,790 49,751 Total revenue […]”
- Retained source: “[…] s for sale and high home prices. Manufacturing, Service and Retailing A summary of revenues and earnings of our manufacturing, service and retailing businesses follows (dollars in millions). Percentage change 2025 2024 2023 2025 vs 2024 2024 vs 2023 Revenues: Manufacturing $ 78,487 $ 77,231 $ 75,405 1.6 % 2.4 % Service and retailing 135,843 138,672 144,342 (2.0 ) (3.9 ) $ 214,330 $ 215,903 $ 219,747 (0.7 ) (1.7 ) Pre-tax earnings: Manufacturing $ 12,571 $ 11,895 $ 11,445 5.7  […]”

G4 reasons reviewed: 3. reason 1: unresolved; reason 2: unsupported; reason 3: unsupported.

### C2-11 — WMT 10-K, run 0: unresolved

Finder: recorded checked 14; final replay 14; candidates 0. Mechanisms: contested tail lies beyond discovered clause.

Source explicitly links the margin changes to factors above and strong global membership growth, but covers two years together without saying offset. Its preceding gross-profit improvement is omitted by the summary. The claimed membership sign error is not decisively established from that compressed sentence. The checked what_changed clause ends at U.S.; the other checked row ends before the offset, so neither verifies the contested membership tail.

- Output `the_print.what_changed`: “Total revenues increased $32.2B or 4.7% for fiscal 2026, which management attributes primarily to increases in net sales, which increased $31.9B or 4.7%, driven by positive comparable sales across the U.S. segments and international markets. Operating income as a percentage of net sales decreased 13 basis points, which management attributes to higher self-insured general liability claims expense in the U.S. of approximately $0.9B, a $0.7B charge related to modification of certain share-based compensation arrangements for the PhonePe subsidiary, and increased depreciation related to capital investments, partly offset by growth in membership in […]”
- Output `results_that_matter.table[2].commentary`: “Operating income as a percentage of net sales decreased 13 basis points to 4.2%, which management attributes to higher self-insured general liability claims expense, the PhonePe share-based compensation modification charge, and increased depreciation, partly offset by growth in membership income globally.”

- Retained source: “[…] ed performance, increased marketing and higher depreciation expenses. Operating income as a percentage of net sales decreased 13 basis points for fiscal 2026 and increased 15 basis points for fiscal 2025, respectively, primarily due to the factors described above and strong growth in membership income globally. Returns As we execute our financial framework, we believe our return on capital will improve over time. We measure return on capital with our return on investment and  […]”
- Retained source: “[…] sales less cost of sales. Gross profit as a percentage of net sales ("gross profit rate") increased 8 and 40 basis points for fiscal 2026 and 2025, respectively, when compared to the previous fiscal year. The increase in fiscal 2026 was primarily driven by the Walmart U.S. segment, due to disciplined inventory management, as well as growth in higher margin businesses globally. The increase in fiscal 2025 was primarily driven by the Walmart U.S. segment, due to managing prices […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-12 — PLTR 10-Q, run 1: unsupported

Finder: recorded checked 8; final replay 8; candidates 0. Mechanisms: relation outside finite connective grammar, detected relation accepted by lexical overlap.

Margin attribution uses said reflected, outside discovery, while the nested cost-of-revenue cause is correctly detected. That does not validate a margin cause. Separately the source says Generally about existing-customer adoption; the summary promotes it to a management attribution for this quarter total revenue including new customers. Lexical matching accepts that generic/specific and part/whole transfer. The judge claim that rising cost cannot accompany rising margin is unnecessary and not adopted.

- Output `the_print.what_changed`: “Revenue increased by $749 million, or 85%, for the three months ended March 31, 2026 compared to the same period in 2025. Management attributed the increase to increased adoption of its products and services within existing customer organizations, noting that of the government increase $367 million was from government customers existing as of December 31, 2025 and of the commercial increase $352 million was from commercial customers existing as of December 31, 2025. Gross margin rose to 87% from 80%, which management said reflected the change in cost of revenue, which increased 25% primarily due to an increase of $39 million in third-party cl […]”
- Output `results_that_matter.table[0].commentary`: “Revenue increased by $749 million, or 85%, for the three months ended March 31, 2026 compared to the same period in 2025, which management attributed to increased adoption of its products and services within existing customer organizations.”

- Retained source: “[…] Gross profit$1,416,785 $710,885 $705,900 99 % Gross margin87 %80 %7 % Cost of revenue for the three months ended March 31, 2026 increased by $43 million, or 25%, compared to the same period in 2025. The increase was primarily due to an increase of $39 million in third-party cloud hosting services. Our gross margin for the three months ended March 31, 2026 increased from 80% for the same period in 2025 to 87%. Operating Expenses Three Months Ended March 31,Change 20262025Amoun […]”
- Retained source: “[…] ompared to $255 million for the same period in 2025, a 133% increase. Generally, increases in revenue from our existing customers are related to increased adoption of our products and services within their organizations. Cost of Revenue and Gross Profit Three Months Ended March 31,Change 20262025Amount% Cost of revenue$215,798 $172,970 $42,828 25 % Gross profit$1,416,785 $710,885 $705,900 99 % Gross margin87 %80 %7 % Cost of revenue for the three months ended March 31, 2026 i […]”

G4 reasons reviewed: 2. reason 1: unsupported; reason 2: unsupported.

### C2-13 — COIN 10-Q, run 0: unsupported

Finder: recorded checked 6; final replay 6; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The explicit total-revenue management attribution borrows consumer/transaction drivers. The diluted-share explanation is unresolved: the source documents actual common-stock repurchases, while basic shares rise 253,878 → 264,775 and prior dilution 17,373 disappears. Those other changes do not establish that repurchases made no contribution to the diluted-count movement. An exact weighted-average causal bridge is not demonstrated. Both relations pass lexical matching. EBITDA revenue/opex is an unresolved component bridge. Refutation: buybacks occurred, so do not claim they had zero effect; the retained excerpt lacks the full anti-dilution note needed to assert the judge’s sole explanation.

- Output `the_print.what_changed`: “Total revenue decreased 30.5% YoY to $1.41B, which management attributes primarily to a 40% decline in transaction revenue driven by a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading. Net income swung to a $394.1M loss from $65.6M of income, and operating income swung to a $21.4M loss from $705.8M of income.”
- Output `results_that_matter.table[4].commentary`: “Diluted EPS swung to a $1.49 loss from $0.24 of income; the diluted share count fell to 264,775 thousand from 271,251 thousand, reflecting share repurchases.”
- Output `results_that_matter.table[5].commentary`: “Adjusted EBITDA decreased 67.4% YoY, reflecting the decline in revenue and higher operating expenses.”

- Retained source: “[…] ction revenue$755,825 $1,262,208 $(506,383)(40) % of net revenue56 65 Transaction revenue decreased for the three months ended March 31, 2026 as compared to 2025, primarily reflecting: •a decrease in consumer transaction revenue driven by $591.6 million attributed to a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading; and 31 •an increase in institutional transaction revenue driven by:  […]”
- Retained source: “[…] e shares of common stock used to compute net (loss) income per share: Basic264,775 253,878 Diluted264,775 271,251 The accompanying notes are an integral part of these Condensed Consolidated Financial Statements. Coinbase Global, Inc. Condensed Consolidated Statements of Comprehensive Income (In thousands) (Unaudited) Three Months Ended March 31, 20262025 Net (loss) income$(394,117)$65,608 Other comprehensive (loss) income: Translation adjustment(18,282)8,018 Income tax effect […]”
- Retained source: “[…]  stock issued in connection with equity awards2,312 — 9,235 — — 9,235 Common stock repurchased(6,278)— (1,062,234)— — (1,062,234) Common stock withheld for net share settlement of equity awards(632)— (118,925)— — (118,925) Stock-based compensation (inclusive of capitalized stock-based compensation)— — 252,452 — — 252,452 Other comprehensive loss— — — (18,282)— (18,282) Net loss— — — — (394,117)(394,117) Balance at March 31, 2026263,411 $3 $7,666,768 $(13,309)$5,827,111 $13,48 […]”
- Retained source: “[…] hree months ended March 31, 2026, our net loss was $394.1 million and Adjusted EBITDA was $303.3 million. For the three months ended March 31, 2025, our net income was $65.6 million and Adjusted EBITDA was $929.9 million. For 2026, with growing regulatory clarity, we believe we are well-positioned to drive crypto’s role in the global economy, through the Everything Exchange and by advancing stablecoin adoption with USDC, including scaling payments. We are working to further g […]”

G4 reasons reviewed: 3. reason 1: unsupported; reason 2: unresolved; reason 3: unresolved.

### C2-14 — COIN 10-Q, run 1: unsupported

Finder: recorded checked 6; final replay 6; candidates 0. Mechanisms: detected relation accepted by lexical overlap, contested tail lies beyond discovered clause, allegation in an unscanned output field, relation outside finite connective grammar.

The revenue-row allegation is unresolved. Its wording explicitly nests lower transaction revenue as consumer Trading Volume falls, rather than directly attributing all consolidated revenue to that consumer driver or claiming a management attribution. Transaction revenue falls $506.383m of the $621.313m total decline, approximately 81.5%, so the component bridge has substantial arithmetic support. This does not establish an exhaustive source-stated aggregate explanation. The what_changed paragraph also preserves transaction scope. Risks applies investment-price causation to operations losses; operations MD&A states no material changes and supplies no price cause. EBITDA offset wording is outside the checked clause; both-period investment-loss addbacks mean the asserted YoY offset is not established. An exclusion can affect an absolute reconciliation, so the judge’s categorical impossibility claim is not adopted.

- Output `results_that_matter.table[5].commentary`: “Adjusted EBITDA decreased 67.4% YoY, reflecting lower revenue and higher operating expenses, partly offset by the exclusion of $482.4M of crypto asset investment losses.”
- Output `results_that_matter.table[0].commentary`: “Total revenue decreased 30.5% YoY, driven by lower transaction revenue as consumer Trading Volume fell 54%, partly offset by growth in derivatives trading volume and the launch of prediction markets trading.”
- Output `risks[0].summary`: “Crypto asset price declines drove $482.4M of losses on crypto assets held for investment, net, and $35.2M of losses on crypto assets held for operations, net.”

- Retained source: “[…] ction revenue$755,825 $1,262,208 $(506,383)(40) % of net revenue56 65 Transaction revenue decreased for the three months ended March 31, 2026 as compared to 2025, primarily reflecting: •a decrease in consumer transaction revenue driven by $591.6 million attributed to a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction markets trading; and 31 •an increase in institutional transaction revenue driven by:  […]”
- Retained source: “[…] osses on crypto assets held for operations, net$35,151 $34,365 $786 2 There were no material changes to note within losses on crypto assets held for operations, net. Other operating expense (income), net Three Months Ended March 31,Change (in thousands, except %) 20262025$% Other operating expense (income), net$34,925 $(5,899)$40,824 (692) There were no material changes to note within other operating expense (income), net. Interest expense Three Months Ended March 31,Change ( […]”
- Retained source: “[…]  Operating (loss) income(21,421)705,806 Interest expense22,569 20,511 Losses on crypto assets held for investment, net482,356 596,651 Other (income) expense, net(61,641)6,188 (Loss) income before income taxes(464,705)82,456 (Benefit from) provision for income taxes(70,588)16,848 Net (loss) income$(394,117)$65,608 Net (loss) income attributable to common shareholders: Basic$(394,117)$65,608 Diluted$(394,117)$65,608 Net (loss) income per share: Basic$(1.49)$0.26 Diluted$(1.49)$ […]”
- Retained source: “[…] 88 36,838 37 Other transaction revenue, net53,200 67,814 (14,614)(22) Total transaction revenue$755,825 $1,262,208 $(506,383)(40) % of net revenue56 65 Transaction revenue decreased for the three months ended March 31, 2026 as compared to 2025, primarily reflecting: •a decrease in consumer transaction revenue driven by $591.6 million attributed to a 54% decrease in consumer Trading Volume, offset in part by growth in derivatives trading volume and the launch of prediction mar […]”
- Retained source: “[…]  Revenue: Net revenue$1,339,348 $1,936,821 Other revenue73,634 97,474 Total revenue1,412,982 2,034,295 Operating expenses: Transaction expense195,859 303,026 Technology and development525,648 355,368 Sales and marketing266,726 247,283 General and administrative376,094 394,346 Losses on crypto assets held for operations, net35,151 34,365 Other operating expense (income), net34,925 (5,899) Total operating expenses1,434,403 1,328,489 Operating (loss) income(21,421)705,806 Intere […]”

G4 reasons reviewed: 3. reason 1: unresolved; reason 2: unresolved; reason 3: unsupported.

### C2-15 — BABA 20-F, run 1: unsupported

Finder: recorded checked 5; final replay 5; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

The row is consolidated adjusted EBITA 76,416m versus 173,065m; its exact supporting quotation names Alibaba China E-commerce Group 107,509m versus 193,223m. Shared EBITA and driver terms pass lexical matching. The source cause belongs to the segment, not the consolidated row; All others has a separate technology-investment loss explanation.

- Output `results_that_matter.table[6].commentary`: “The filing attributes the decrease primarily to the investment in quick commerce, user experiences, and technology, while there is positive contribution from customer management service.”

- Retained source: “[…] dded services provided to paying members. (ii) Segment adjusted EBITA Alibaba China E-commerce Group adjusted EBITA decreased by 44% to RMB107,509 million (US$15,586 million) in fiscal year 2026, compared to RMB193,223 million in fiscal year 2025, primarily due to the investment in quick commerce, user experiences, and technology, while there is positive contribution from customer management service. 139 Table of Contents Alibaba International Digital Commerce Group (i) Segme […]”
- Retained source: “[…] a loss of RMB9,499 million in fiscal year 2025 , primarily due to the increased investment in technology businesses, partly offset by the improved results of Hujing Digital Media and Entertainment Group and other businesses. 140 Table of Contents Cost of Revenue Year ended March 31, 2025 2026 RMB RMB US$ YoY % Change (in millions, except percentages) Cost of revenue 598,285 616,136 89,321 3 % Percentage of revenue 60 % 60 % Share-based compensation expense included in cost of […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C2-16 — ASML 20-F, run 0: unsupported

Finder: recorded checked 10; final replay 10; candidates 0. Mechanisms: detected relation accepted by lexical overlap.

Same total-net-system-sales → New systems transfer as C1-14. The broader what_changed passage is correctly scoped and is not the allegation witness. The New systems anchor in the actual segment row distinguishes it from total systems; lexical overlap still accepts the clause.

- Output `segments[0].commentary`: “The increase in system sales was primarily driven by higher EUV and DUV immersion system sales, partially offset by a decrease in ArF dry, KrF and i-line sales volumes; four EXE and 44 NXE systems were recognized in sales in 2025 compared to two EXE and 42 NXE systems in 2024.”

- Retained source: “[…] 24 Year ended December 31 (€, in millions) 2024 % 1 2025 % 1 % Change Net system sales 21,768.7 77.0 24,474.3 74.9 12.4 Net service and field option sales 6,494.2 23.0 8,193.0 25.1 26.2 Total net sales 28,262.9 100.0 32,667.3 100.0 15.6 Cost of system sales (10,406.9) (36.8) (11,384.0) (34.8) 9.4 Cost of service and field option sales (3,364.0) (11.9) (4,025.3) (12.3) 19.7 Total cost of sales (13,770.9) (48.7) (15,409.3) (47.2) 11.9 Gross profit 14,492.0 51.3 17,258.0 52.8 19 […]”
- Retained source: “[…] in net service and field option sales of 26.2% compared to 2024. T he increase in system sales was primarily driven by higher EUV and DUV immersion system sales – this was partially offset by a decrease in ArF dry, KrF and i-line sales volumes. The increase in net service and field option sales was primarily due to the growing installed base, higher levels of lithography tool use for certain customers and more NXE field upgrades. Our gross profit and gross margin increased in […]”

G4 reasons reviewed: 1. reason 1: unsupported.

### C2-17 — TSM 20-F, run 1: unresolved

Finder: recorded checked 9; final replay 9; candidates 0. Mechanisms: relation outside finite connective grammar.

In line with is not a connective. Both EPS rows describe co-movement with parent NI; source financial ratios support its increase but no EPS attribution was located in the retained excerpt. Whether this observational/accounting statement asserts an unsupported causal explanation requires a rubric boundary decision.

- Output `results_that_matter.table[5].commentary`: “Basic EPS increased in line with the rise in net income attributable to shareholders of the parent.”
- Output `results_that_matter.table[6].commentary`: “Diluted EPS increased in line with the rise in net income attributable to shareholders of the parent.”

- Retained source: “[…] ,047) 39.6% Net income 851,028 1,157,524 36.0% 1,695,125 54,036 46.4% Net income attributable to shareholders of the parent 851,740 1,158,380 36.0% 1,697,604 54,116 46.5% Net margin attributable to shareholders of the parent 39.4% 40.0% — 44.6% 44.6% — Income tax expenses increased by NT$98,214 million in 2025, or 39.6%, from 2024. The increase was mainly attributed to higher taxable income in 2025. Liquidity and Capital Resources Our sources of liquidity include cash flow fr […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-18 — JD 20-F, run 1: unresolved

Finder: recorded checked 3; final replay 3; candidates 0. Mechanisms: relation outside finite connective grammar.

Reflects same period-over-period movement describes direction, not necessarily equal percentages or an explicit management driver. Attributable and consolidated NI both decline, with NCI changing. The source table supports the direction; whether phrasing implies unsupported causality remains unresolved.

- Output `results_that_matter.table[3].commentary`: “Reported as a secondary figure below consolidated net income; the decline reflects the same period-over-period movement in consolidated net income.”

- Retained source: “[…] 23 3,621 Income tax expenses 19 ( 8,393 ) ( 6,878 ) ( 2,181 ) ( 312 ) Net income 23,257 44,660 23,142 3,309 Net (loss)/income attributable to non-controlling interests shareholders ( 910 ) 3,301 3,511 502 Net income attributable to the Company’s ordinary shareholders 24,167 41,359 19,631 2,807 The accompanying notes are an integral part of these consolidated financial statements. F-7 Table of Contents JD.com, Inc. Consolidated Statements of Operations and Comprehensive Income […]”
- Retained source: “[…] trolling interests shareholders (910 ) (0.1 ) 3,301 0.3 3,511 502 0.3 Net income attributable to the Company’s ordinary shareholders 24,167 2.2 41,359 3.6 19,631 2,807 1.5 Net income per share Basic 7.69 13.83 6.89 0.99 Diluted 7.61 13.43 6.45 0.92 Net income per ADS(3) Basic 15.37 27.67 13.79 1.97 Diluted 15.23 26.86 12.90 1.84 Weighted average number of shares Basic 3,144,233,160 2,989,701,855 2,847,199,686 2,847,199,686 Diluted 3,170,542,396 3,076,061,616 2,978,037,127 2,9 […]”

G4 reasons reviewed: 1. reason 1: unresolved.

### C2-19 — MELI 10-K, run 1: unresolved

Finder: recorded checked 6; final replay 6; candidates 0. Mechanisms: relation outside finite connective grammar.

Driven in part by is undiscovered. Source balance-sheet assets, restricted cash and loans increase; no express aggregate cause was located. It is a plausible partial component bridge whose strict G4 status remains unresolved.

- Output `the_print.key_takeaways[3]`: “Total assets grew to $42.7B from $25.2B, driven in part by increases in restricted cash and cash equivalents and loans receivable.”

- Retained source: “[…] s 1,541 802 Other assets 426 182 Total non-current assets 9,094 5,054 Total assets $ 42,667 $ 25,196 Liabilities Current liabilities: Accounts payable and accrued expenses $ 4,502 $ 3,196 Funds payable to customers 13,029 6,954 Amounts payable due to credit and debit card transactions 3,584 1,923 Salaries and social security payable 916 727 Taxes payable 1,140 525 Loans payable and other financial liabilities 4,623 2,828 Operating lease liabilities 430 241 Other liabilities 4 […]”
- Retained source: “[…] 2024 Assets Current assets: Cash and cash equivalents $ 3,670 $ 2,635 Restricted cash and cash equivalents 9,867 2,064 Short-term investments 2,629 4,485 Accounts receivable, net 369 255 Credit card receivables and other means of payments, net 6,893 5,288 Loans receivable, net of allowances of $ 3,057 and $ 1,630 (Note 5) 8,855 4,716 Inventories 570 296 Other assets 720 403 Total current assets 33,573 20,142 Non-current assets: Long-term investments 1,764 1,203 Credit card re […]”
- Retained source: “[…]  Credit card receivables and other means of payments, net 6,893 5,288 Loans receivable, net of allowances of $ 3,057 and $ 1,630 (Note 5) 8,855 4,716 Inventories 570 296 Other assets 720 403 Total current assets 33,573 20,142 Non-current assets: Long-term investments 1,764 1,203 Credit card receivables and other means of payments, net 153 — Loans receivable, net of allowances of $ 86 and $ 48 (Note 5) 510 179 Property and equipment, net 2,303 1,380 Operating lease right-of-us […]”

G4 reasons reviewed: 1. reason 1: unresolved.
