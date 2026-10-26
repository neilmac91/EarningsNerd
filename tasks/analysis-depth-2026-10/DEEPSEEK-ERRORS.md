# DeepSeek flash's error gap: diagnosis and plan

Plan for the "AI trend analysis" in Multi-Period Analysis, 25 October 2026. Branch `claude/trend-analysis-depth-eval`.

**Decision (founder, 2026-10-25):** stay on DeepSeek flash. Claude Sonnet 5.5 is not adopted: it cost about
30 times as much ($0.21 against $0.007 an analysis) and took about a minute instead of 10 seconds. This
document explains why DeepSeek's error rate runs higher and how to close the gap at DeepSeek's cost.

**How it was made:** five analysts each took one error class (first-try gate failures, mislabelled numbers,
calibration, errors the judge named, and held-out robustness with settings). Each traced every recorded
instance to its root cause in the records, the evidence packs, the prompt and the checks. An independent
skeptic re-checked each claimed root cause against the records and packs, and the claims that did not hold
were dropped or corrected (§1.8). No model was called.

**Inputs:**
- Records of every generation: eval-v1 (20 companies, 10 of them held out), dev-v4 (5 development companies, same frozen prompt `d558d371`, byte-identical inputs), and the earlier prompts in dev-v1 to dev-v3.
- The audits and judge verdicts for those records.
- The prepared error inventory.
- The verified root-cause analyses, after their skeptics' corrections.

No model was called and no repository file was changed to write this.

## Summary

- **DeepSeek really does make more errors, but the gap is narrower and more specific than the headline.** On the frozen prompt across the 25 recorded generations:
  - **First-try gate failures.** DeepSeek has 17 real ones, Sonnet 1. The gate is the deterministic fact-check of every number. Sonnet's other first-try failures were all errors of the gate itself.
  - **Wrong metric, period or sign on a verified number.** In eval-v1, DeepSeek has about 14 such sentences and Sonnet 1.
  - **Interpretation marked as interpretation.** DeepSeek marks almost none of its interpretation as "judgement".
  - **Cause support is not a gap.** Whether the cited passages support the causes stated is the same for both models (Opus auditor: 76% fully supported for each).
- **Five mechanisms explain most of the gap. Each has a cheap, mostly deterministic fix.**
  1. **A figure stated without its own ID.** DeepSeek states a correct figure but cites only a value derived from it, or relies on an earlier sentence, or uses a red flag's threshold without the flag's ID. This is 7 of the 17 real first-try failures.
  2. **Pack gaps filled with the nearest number.** The pack has no typical level for operating cash flow / net income, so DeepSeek borrows the free-cash-flow median (5 to 6 sentences, plus 2 gate failures). Net cash comes on one signed basis only, so DeepSeek mixes "net debt" wording with net-cash signs and medians (7 sentences).
  3. **It types sentences by the literal section instruction.** It labels figure-only sentences "cause" without a passage (4 failures). Its share of judgement sentences collapsed when the frozen prompt dropped the words "one judgement on why it matters" from the red-flag section: from 8.4% to 0.4% of sentences outside the watch list, on the same 10 companies.
  4. **It fills fixed prompt slots even when the data does not fit.**
     - It writes a net-margin-versus-operating-margin sentence in 17 of 20 analyses (Sonnet 7). On DE it used two different years to do so.
     - It applies the "operating-cost growth against revenue growth" frame with "grew" when costs fell (CVX).
  5. **It does not notice data breaks the pack fails to flag.** In 6 packs the long-term debt line stops partway through the window. DeepSeek disclosed 1 of these breaks (USB, in passing) and stated broken net-cash figures as fact. Sonnet disclosed 4 of 6.
- **Most fixes cost no model call.**
  - Changes to the repair loop and the gate: rewrite the repair message, retype figure-only "cause" sentences, backstop checks, and patch-style repairs. Adding the missing ID by code (fix 1) was built, tested and removed: each review round found a new kind of wrong number it let through, and it made no failing first pass pass (§2, "As built").
  - Pack additions: an operating cash flow / net income median and low, net-debt wording, and suppressing net cash that is built on broken debt.
  - A few prompt lines in the cached system prompt.
  - **Expected cost and latency:** about the same or lower ($0.006–0.007 per analysis). p50 stays at about 9–10 s. p90 should fall from 16 s to about 10–13 s, because fewer and shorter repairs are needed.
- **Proof:** measure on the development half first and then the held-out half, with two generated runs per configuration. Deterministic metrics come first, then the Opus auditor and judge. Expected spend is about $2.4–2.8 of DeepSeek (at most about $4.6) and $30–43 of Opus (§3).

---

## 1. Diagnosis

### How each root cause is labelled
- **(a) DeepSeek-specific:** Sonnet read the same pack and prompt and did not make this error.
- **(b) Invited:** the pack or prompt invites this error from any model.
- **(c) Check artefact:** a false positive from the gate or an auditor, or a pack value that is itself wrong.

### Common terms

| Term | Meaning |
|---|---|
| Gate | The deterministic number check. "First-try" means the first attempt, before the one allowed repair. |
| ID | A value's label in the pack: F, X, S, D, R or P. |
| Frozen prompt | The prompt eval-v1 and dev-v4 both used, sha `d558d371`, archived at `tasks/analysis-depth-2026-10/prompts/frozen-d558d371.md`. `backend/prompts/trends-depth-analyst-agent.md` is now the candidate the `-q` and `-c` arms run. |

Counts are taken per auditor and per folder. The `semantics/` and `semantics-by-claude-opus-5-5/` folders hold the same Opus audit for DeepSeek, so it is counted once.

### 1.1 First-try gate failures

| Run (frozen prompt) | DeepSeek | Sonnet |
|---|---|---|
| eval-v1, 20 companies | 11 failing claims in 7 companies (12 as run; the CVX "$18-19 billion" scale bug has since been fixed in the gate) | 5 claims in 5 companies |
| dev-v4, 5 development companies, same inputs | 9 claims in 4 companies | 1 claim in 1 company |
| **Of these: real errors / check artefacts** | **17 / 3** | **1 / 5** |

Every first try that failed passed after its one repair under the current gate. Each repair costs about 6.5 s, 1,734 output tokens and $0.00145.

**Latency.** On eval-v1, p50 is 9.7 s and p90 16.1 s. Counting first attempts alone, p50 is 9.1 s and p90 9.9 s. The 16 s p90 therefore comes entirely from repairs: 7 of 20 analyses repaired.

The same 5 packs failed in 4 of 5 companies in dev-v4 but in 1 of 5 in eval-v1. Per-company results at temperature 0.2 are largely chance; only pooled rates mean anything.

**Root causes of DeepSeek's 17 real first-try failures:**

| Root cause | Count | Kind | Sonnet, same packs and prompt |
|---|---|---|---|
| Figure stated without its own ID | 7 | (a) | 1 (NVDA "190%" without R2) |
| "Cause" sentence citing no passage | 4 | (a) in rate; (b) under earlier prompts | 0 of 25 (Haiku 0 of 40); Sonnet made it 2 times in 14 under earlier prompts |
| Operating cash flow / net income "typical" level that the pack lacks | 2 | (a), lured by (b) | 0 |
| Truncated a dollar figure instead of rounding | 2 (one sentence) | (a), one-off: DeepSeek rounded 339 of 341 such figures correctly | 0 of 431 |
| Took the value from the adjacent peer row | 1 | (a), one-off | 0 |
| Wrong direction word | 1 | (a); the prompt's frame (b) invited it | 0 |

The 3 DeepSeek check artefacts are AMD 19.4%, CVX 9.2% and the borderline NVDA "65.5pp". All 5 of Sonnet's eval-v1 failures are check artefacts.

**Instances, with what the pack holds:**

- **Figure without its own ID.**
  - **CVX (held out):** "That 2.1% net cash position ranks in the 83rd percentile of six energy peers, whose median is -7.7% [D637][D638]."
    - 2.1% is D352, net cash % of revenue FY2025, 2.0965, which the sentence does not cite. D637 (percentile, 83.3) has D352 as its input.
    - The previous sentence cited D352.
    - Sonnet did not restate the percentage.
  - **DUK (held out):** "Cash of $245 million covers only 0.1 years of the latest $1.7 billion burn [F137][D356][R2]."
    - $1.7 billion is D355, the cash burn of $1,694m. D356 (0.14 years) has inputs [D350, D355].
    - R2's evidence is [D356] only.
  - **NVDA (development), in both eval-v1 and dev-v4, on the same 36,769-token input:** "Gross margin fell 3.9pp to 71.1% … [D462][D463][D478][D479]."
    - 71.1% is F30, gross margin FY2026, 71.068, which is not cited. D462 (−3.92pp) has inputs [F30, F29].
    - Sonnet framed the same move through the margin bridge (D477) and stated no level.
  - **ORCL (held out):** "Free cash flow has run below 80% of net income for two years, at -1.39x in FY2026 [D362][D409]."
    - "80%" exists only in R2's detail, and R2's evidence is [D362, D409]. R2 itself is not cited.
    - Sonnet cited [R2][D362][D409][D818].
  - **JPM (dev-v4):** "…the 52.4% efficiency ratio sits at the 0th percentile versus a 61.7% median…"
    - 52.4% is D207, which this sentence does not cite. It was cited in the previous sentence.
  - **SNAP (dev-v4):** "Net margin of -7.8% [F50] beat operating margin by 1.2pp…"
    - 1.2pp is F50 (−7.76) minus F30 (−8.97). F30 is cited earlier in the section but not in this sentence.
  - **Rates.**
    - Restating the company's own level in a peer-percentile sentence: DeepSeek omitted the level's ID in 2 of 29 sentences, Sonnet in 0 of 31.
    - "Fell Xpp to Y%": DeepSeek omitted the ID of Y in 2 of 11, Sonnet in 0 of 7.
    - Using a red flag's threshold: DeepSeek omitted the R ID twice (ORCL, and KO "below 80% … [D387][D437]"). KO passed the gate only because "below" accepts any cited percentage of 80 or less. Sonnet cited the R ID in 13 of 13.
- **"Cause" without a passage.**
  - **MSFT:** "The FY2026 operating-margin gain came from R&D (+0.8pp) and other lines (+1.2pp), partly offset by cost of revenue (-0.9pp) [D501][D502][D500]."
    - All three values are margin-bridge arithmetic: D500 is −0.88pp, D501 +0.815pp, D502 +1.223pp.
    - Sonnet typed the same bridge "fact".
  - **NVDA:** "Stock-based compensation of $6.4 billion was only 6.2% of operating cash flow, so conversion is diluted by working capital rather than non-cash add-backs [X80][D438]."
    - X80 is $6,386m and D438 is 6.217%. The pack has no FY2026 cash-flow passage.
    - The repair only changed the type to "fact" and kept the uncited inference.
  - **COST (dev-v4):** "Buybacks and dividends of $3.3 billion consumed 35.2% of free cash flow… [D429][D430][X100]." The sentence contains no causal claim at all.
  - **JPM (dev-v4):** "…as higher rates lifted interest income from $92.8 billion to $170.6 billion [D149][D174][X124][X125]." Passages P36, P49 and P50 state this cause but are not cited.
  - In 6 of the 7 recorded no-passage "cause" sentences, from either model, the next sentence cites the passage. The model labels a two-sentence unit "cause" but cites the passage only in the second sentence.
- **Operating cash flow / net income level the pack lacks.**
  - **TGT:** "…1.77x net income in FY2025, down from the 2.01x window median [F84][F44][D404][D599]."
    - 2.01x is the true median of TGT's ten operating cash flow / net income values (2.012), but the pack holds no such value.
    - D599 is the free-cash-flow median, 1.008. The repair swapped in 1.01x, which makes "down from" false.
  - **NVDA (dev-v4):** "…below the 0.83x-to-0.91x window range's high and the 1.16x peer median [F100][F60][D435][D847]." D828 (0.835), D827 (0.908) and D847 (1.164) are all free-cash-flow / net income statistics.
- **Truncation.** JPM dev-v4: "$119 billion in FY2020, $121 billion in FY2021". D86 is $119,951.0m and D110 is $121,649.0m.
- **Wrong row.** COST dev-v4: "Net margin of 3.0% sits below the 5.0% retail peer median [F52][D712][D420]". D712, the net-margin peer median, is 3.54. The 5.0% is D710, the operating-margin peer median, two lines above it in the pack text.
- **Direction word.** CVX: "Operating costs grew 3.4% slower than revenue fell 4.6% [D373][D358][D379]." D373 is −3.42%.
  - The same sentence says "cost reduction", so DeepSeek read the sign correctly.
  - It forced the prompt's "operating-cost growth against revenue growth" frame onto a year in which both fell. On DE, in the same situation, it wrote "fell only 11.9%" correctly.
  - This is 1 slip in about 275 negative values.
- **Check artefacts (c).**
  - **AMD:** "19.4% matched the FY2021 high of 19.6% [D467][D803]". D467 is FY2025 19.443. The gate binds "FY2021" backwards onto 19.4%.
  - **CVX:** "…the FY2025 slide from 9.2% [D613][F29][F30]". F29 is FY2024 9.151, the start of the slide. The repair made the sentence worse: "from 6.7%".
  - **NVDA:** "60.2pp of the 65.5pp total [D448][D622]". D448 is 65.47% growth, written in pp.
  - **Sonnet:**
    - USB "improved 3.9pp" for a falling efficiency ratio (D195 → D220);
    - ORCL "costs grew 0.3pp faster": D443, "revenue growth minus operating-cost growth", is −0.35, so the sentence is true;
    - JPM "$-147.8 billion", which the gate parses wrongly;
    - VRTX "+37.7pp as the FY2024 Alpine charge" and COP "Debt after FY2020 … $1.0 billion": both are year-binding errors.

### 1.2 Verified numbers said about the wrong metric, period or sign

| eval-v1, final outputs | DeepSeek | Sonnet |
|---|---|---|
| Opus auditor, substantive flags | 14 of 1,457 verified claims | 5 of 1,458 |
| DeepSeek V4 Pro auditor, substantive flags | 13 of 1,459 | 4 of 1,458 |
| After reading every flag and adding deterministic probes for errors both auditors missed | **About 14 real sentences in 8 companies** (~9.6 per 1,000 claims; the RIVN and NEE "down from net cash" cases are borderline) | **1 real** (ORCL) plus 2 minor paraphrases |

Exposure is about equal: DeepSeek wrote 39 sentences about net cash, Sonnet 40.

**Against the current measures** (`python -m evals.trend_depth.report --label eval-v1`, all 20 companies, view-1 audits):
- The probes R1, R2a, R2c and R3 find 12 of DeepSeek's sentences (8.2 per 1,000 verified claims) and none of Sonnet's.
- With Opus's substantive flags, the report counts 15 DeepSeek sentences (10.3; probes 12, Opus 10) and 5 Sonnet
  sentences (3.4; Opus 5).
- Read by hand, 13 DeepSeek sentences in 8 companies are real (8.9): the 15 less VRTX's buybacks and RIVN's
  percentile, both true (check artefacts below). The fourteenth real sentence above, TGT's net debt, states a figure
  built on TGT's double-counted cash (§1.5), so the report counts it under broken net cash instead.
- Sonnet's one real sentence is ORCL's (0.7). Its other four flags are KO's 5.2% and DUK's basic EPS (twin values)
  and the NVDA and KO percentile ranks paraphrased as "net cash rank" (the two minor paraphrases), each in a sentence
  that discloses a break.
- §3 step 0 re-audits these outputs under the auditor's view 2.

**Root causes:**

1. **One-basis net cash: 7 DeepSeek sentences. Invited by the pack (b), with DeepSeek-specific rate (a).**
   - **Why the pack invites it.**
     - The pack prints net cash only as "cash and investments less debt", negative for indebted companies. Its peer medians and percentiles use the same basis.
     - The red-flag text says "Net cash fell N years in a row into net debt" even for companies that were in net debt all along (CAT R1, DUK R3, NEE R2).
     - The gate compares magnitudes only. The auditor sees the label and period but never the signed value.
   - **What DeepSeek does differently.**
     - It puts "net debt", the ratio, the peer median and the percentile into one sentence: 6 such sentences against Sonnet's 2, and 4 of DeepSeek's 6 are wrong.
     - It copies the minus signs under a "net debt" label.
     - Across three runs, Sonnet made no sign errors in 28 net-debt sentences.
   - **Other models make the same error:** Haiku 1, Haiku-low 2, Gemini 2.
   - **Instances:**
     - **CAT:** "Net debt is 38.8% of revenue, better than the -35.6% peer median but only the 43rd percentile of seven industrials peers [D457][D1152][D1151]." D457 is −38.81 and D1152 is −35.61, so CAT is worse than the median, not better. Sonnet wrote "negative 38.8% … near the peer median of negative 35.6%".
     - **CAT watch item:** "…beyond the FY2025 -$26.2 billion … toward the FY2023 -$22.1 billion [D456][D350]". D456 is −$26.23bn and D350 −$22.14bn, printed with net cash's sign under "net debt".
     - **TGT:** "Net debt was $4.3 billion, or 4.1% of revenue, better than the retail peer median of -3.5% net cash [D410][D411][D613][D612]." D411 is −4.10 and D613 −3.49, so TGT is worse than the median. Both auditors missed this one.
     - **DUK:** "Net debt has deepened for nine straight years, from -$50.0 billion to -$89.6 billion [D14][D352][R3]." D14 is −$49.99bn and D352 −$89.59bn.
     - **NEE, two sentences:** "from -$34.3 billion to -$92.2 billion [D9][D231][R2]" and "beyond -$92.2 billion [D231][D314]". Both auditors missed both.
     - **ORCL:** "Net debt widened to $97.6 billion … the 0th percentile against six software peers whose median is -0.5% [D414][D415][D815][D816]." D816 is −0.55 on the net-cash basis. Sonnet's single real flag is the same trap: "ranks in the 0th percentile [D815]" on a net-debt reading.

2. **No typical operating cash flow / net income level in the pack: 5 sentences, plus 1 invented range. Lured by (b), DeepSeek-specific (a).**
   - **The gap.** No pack holds a window or peer level for operating cash flow / net income; 15 of 20 hold one for free cash flow / net income. The prompt still asks for each ratio "latest and typical", and also says "never against a different ratio's median".
   - **Instances:**
     - **CVX:** "…2.76x net income, well above the 1.10x window median [F60][F20][D346][D622]". D622 is the free-cash-flow / net income median, 1.0975. The true operating cash flow median is 1.97.
     - **DE:** "…1.48x net income in FY2025 [F80][F40][D401], against a 0.91x window median [D1347]". D1347 is the free-cash-flow median, 0.905. The true operating median is 1.17.
     - **PG:** "…1.22x net income in FY2026, above the 1.02x window median [D660]". D660 is the free-cash-flow median, 1.017. The true operating median is 1.25, so operating cash flow is actually below its own median.
     - **TGT (after repair):** "…down from the 1.01x window median [D599]".
     - **CAT:** "…above the 0.96x median free-cash-flow conversion [D450][D1135]". Correctly labelled, but it compares unlike ratios.
     - **DUK:** "in line with the 2.19x to 3.48x range since FY2019 [D97][D268]". The real range is 2.12x (FY2021, D184) to 6.43x (FY2020, D142). Neither auditor flagged it.
   - **Frequency:** DeepSeek did this in 14 of its 41 recorded analyses, in every prompt version. Sonnet did it in 0 of 41, Haiku in 0 of about 60, Gemini in 1.

3. **Fixed slot, mixed years: 1 sentence. (a), in a prompt slot (b).**
   - **DE:** "…left net margin 6.5pp under operating margin [F30][F50]." F30 is operating margin FY2024, 17.48; F50 is net margin FY2025, 11.00.
   - DE's operating-margin row ends at FY2024, and DeepSeek wrote that itself two sentences earlier.
   - The prompt asks for net-versus-operating margin and gives the example "6.5pp above operating margin". DeepSeek fills that slot in 17 of 20 analyses, Sonnet in 7.
   - The gate passes cross-year pairs if either year is named.

4. **Passage misread: 1 sentence. (a).**
   - **NEE:** "The FY2021 trough reflected a $1.5 billion Mountain Valley Pipeline impairment … [P63][P68]."
   - P68 (FY2020 10-K) dates the impairment to 2020. P63 says 2021 results rose because of its absence.
   - The impairment also sits below operating income.

**Check artefacts (c) among the flags:**
- **DE, three flags:** "Net debt was $5.52 billion at FY2025 [D407], down from $35.8 billion in FY2021 [D226]". The sign is converted correctly. The pack value is wrong because long-term debt drops out of total debt after FY2021 (see 1.5).
- **VRTX, two flags:** "Buybacks of $2.02 billion [D441]". D441, "Buybacks plus dividends", has only the buybacks line X147 as input, and VRTX pays no dividend. The sentence is true.
- **RIVN:** "…above the peer median of 17.8% and the 75th percentile [D351]". This is true even if the 75th percentile is read as a peer threshold.
- **V4 Pro:** it flagged correct net-debt conversions (DeepSeek DUK ×3, Sonnet DUK ×4), raised 4 false "period unclear" flags on NEE passages, and flagged the "365" in "Microsoft 365".
- **Sonnet:** its KO 5.2% and DUK basic-EPS flags are twin values.

The auditor is shown "ID = label, period" and never the signed value (`semantics._describe`).

### 1.3 Interpretation not marked as judgement

| eval-v1 | DeepSeek | Sonnet | Haiku-low |
|---|---|---|---|
| Judgement sentences, all | 4 of 590 (0.7%) | 68 of 587 (11.6%) | 50 of 565 (8.8%) |
| Judgement, excluding the watch list | 4 of 530 (0.8%) | 20 of 527 (3.8%) | 31 of 506 (6.1%) |
| Evaluative words ("structural", "cushion", "pressure", …) in fact or comparison sentences, excluding arc and watch | 18 of 330 (5.5%) by hand; the lexicon (`calibration.py`, §3's measure) finds 19 (5.8%) | 7 of 312 (2.2%) | — |
| Watch items with forecast or consequence wording ("would keep", "will likely remain") | 11 of 60 (about 7 real) | 1 of 60 | 1 of 59 |

Opus scored calibration for Sonnet over DeepSeek on 19 of 20 companies.

**Root causes:**

1. **The prompt dropped a word. (b), with DeepSeek-specific literalness (a).**
   - The earlier prompt said "one judgement on why it matters" in the red-flag section; the frozen prompt says "why it matters". This comes from the reconstructed earlier prompt: the dev-v3 records carry no prompt hash.
   - **On the same 10 development companies:**
     - judgement outside the watch list fell from 8.4% (dev-v3) to 0.4% for DeepSeek, and from 9.3% to 3.8% for Sonnet;
     - DeepSeek's evaluative words in fact and comparison sentences rose from 3.2% to 6.2%;
     - dev-v4 DeepSeek had 0 judgements in 145 sentences.
   - So when the prompt names a judgement slot, DeepSeek uses it; when it does not, the interpretation stays inside data sentences.
2. **Watch typing is mostly a convention. Part (c) as a measure.**
   - 48 of Sonnet's 68 judgements are watch items, and 28 of its judgements cite figures not cited earlier. That breaks the prompt's own "must not introduce a new number".
   - DeepSeek types every watch item "comparison", which honours that rule literally.
   - The grounding rule (Tier 4) actually allows numbers the sentence cites. The gate does not enforce the judgement tier at all, even though its documentation describes it.
   - Compare judgement share excluding the watch list.
3. **Uncited "so / as / on" inferences in fact and comparison sentences. (a).** About 10 in DeepSeek's eval-v1 outputs against 2–3 in Sonnet's.
   - REGN: "SBC of $994 million equalled 20.0% of operating cash flow [X77][D431], so cash conversion leans on a non-cash add-back". X77 is $993.7m and D431 is 19.96%.
   - COST: "…median is 5.0%, so the model runs on volume rather than margin [F32][D709][D710]".
   - DE: "…so fixed costs spread over a smaller base [D394][D304][D393][D303]".
   - Watch item, MSFT: "If capex as a share of revenue stays above the FY2026 34.9%, free cash flow margin will likely remain under the 20.2% window low [D455][D456][D982]". D455 is 34.94% and D982 is 20.19%. This is a forecast.

### 1.4 Logic slips that only a careful reader finds

These are not caught by the gate or by either audit. In DeepSeek's eval-v1 outputs there are about 7, against 0 for Sonnet. The probes that found them were written after reading DeepSeek's eval-v1. On the development runs they find 1 DeepSeek slip (JPM dev-v3, the same shape as below) and no real Sonnet slip, so this gap is uncertain.

- **SNAP:** "Debt rose to $3,536.8 million as … [D398][P1][P2]." D350, total debt FY2024, is $3,643.9m; D398 is $3,536.8m. Debt fell.
- **DUK:** "Diluted shares rose 0.6% … so EPS growth of 10.5% outpaced net income growth of 9.8% [X115][D374][D361][D360]." D374 is +0.65%. D361 is basic EPS growth. Rising diluted shares cannot explain EPS growing faster than net income.
- **JPM:** "Per-share growth outran net income over the window … as the diluted share count fell 3.4% in FY2025 [F115][F113][D224]." A one-year share change is used to explain a ten-year CAGR gap (13.9% against 9.7%).
- **COST (watch):** "…recovers toward the 0.99x median from 1.02x [D422][D701]". D422 is 1.017 and D701 0.992. "Recovering toward" a lower level is backwards.
- **COST:** "currency moves added $126 of expense [P9]" and "add about $370 [P25]". The passage tables are in millions, and the gate matched the raw literal. This is pack-invited (b): DeepSeek did it 3 times across runs, Sonnet 0.
- **COP:** "the three years to FY2025 show a 5.3% CAGR [D844]". D844 is −5.31. The unsigned-fall rule fires once in 6,530 recorded sentences, always on this case.

### 1.5 Data breaks not noticed: pack defect (c), DeepSeek-specific blindness (a)

In 6 packs the long-term debt line ends before the window does:

| Company | Long-term debt line ends |
|---|---|
| COP | FY2020 |
| CVX | FY2021 |
| DE | FY2021 |
| KO | FY2023 |
| ORCL | FY2022 (window to FY2026) |
| USB | FY2022 |

The pack still computes total debt, net cash and peer percentiles. The data checks do not mention it. Debt components also change across years: DE has long-term only, then long-term plus current, then current only.

- **DeepSeek stated broken values as fact:**
  - **COP:** "Net cash was $7.1 billion, or 12.1% of revenue, in FY2025 … [D337][D338][D850][D851]", on a debt line that stops after FY2020.
  - **KO:** "Net cash was $8.8 billion at FY2025 … [D442][D443][D440]" and "That ranks at the 100th percentile … [D793][D794]". KO's long-term debt was $35.5bn at FY2023 [F208].
  - **CVX:** "Net cash turned positive at $4.0 billion … [D351][D352][D309]".
  - **DE:** "…down from $35.8 billion in FY2021", presenting a dropped debt line as deleveraging.
- **Sonnet:**
  - flagged KO's net cash as "unreliable" and CVX's net cash as likely overstated;
  - wrote of USB: "Data gap: long-term debt is reported only through FY2022 [F104]";
  - wrote of COP: "Debt after FY2020 shows only a $1.0 billion current portion".
- **Tally:** DeepSeek disclosed 1 of 6 breaks (USB: "the last year the pack reports it"); Sonnet 4 of 6.
- The same mapping gap probably also affects peers' net cash, and so the peer medians.

**Against the current measures.** Version 2's data checks (`packs-v2/README.md`) name more breaks than this table:
- **Debt breaks in 7 companies:** COP, CVX, DE, KO, ORCL, TGT and USB. ORCL's long-term debt is reported as zero in
  FY2022 alone, and DE's FY2016–FY2019 total debt is long-term debt only. TGT's FY2016–FY2018 total debt counts its
  current portion twice (review 8): its long-term line is its debt note's "Total notes and debentures", which already
  holds the current line total debt adds again ($13,433m [D14] against $11,715m of notes at FY2016).
- **Liquidity breaks in 5 companies:** a cash or investment line is missing in one year (COP, MSFT, NVDA, ORCL), or
  the short-term investments already sit inside cash (TGT).

The report's broken-net-cash rows read these breaks for every arm (`report --label eval-v1`, all 20 companies). TGT's
debt double count adds one company to the debt-break denominator and no sentence: no recorded output states a figure
it makes broken (TGT's FY2016–FY2018 total debt or its growth, or the two lines' sum).

| | DeepSeek | Sonnet |
|---|---|---|
| Stated a broken figure as fact | 6 of 9 companies, in 13 sentences | 2 of 9, in 6 sentences |
| By kind | Debt break 4 of 7 (COP, CVX, DE, KO); liquidity break 2 of 5 (NVDA, TGT) | Debt break 1 of 7 (DE); liquidity break 1 of 5 (TGT) |
| Disclosed | 1 (USB) | 5: USB, COP, CVX and KO (the 4 of 6 above), and NVDA |
| Silent | MSFT, ORCL | MSFT, ORCL |

A disclosure in one sentence does not excuse another sentence that states a broken figure without one. Sonnet's
CVX and NVDA net cash sentences are counted that way among its 6.

### 1.6 Cause support: not a gap

| Opus auditor | Supported | Partial | Unsupported | Cause sentences |
|---|---|---|---|---|
| DeepSeek | 76% | 23% | 1% | 140 |
| Sonnet | 76% | 22% | 1% | 152 |

The failures are the same kind for both models: a passage covering one year cited for several, or one of two causes. Specific DeepSeek misreads exist, but no fix aimed at DeepSeek is justified here:
- **DE:** "production costs stayed unfavorable", against P16's "Production costs were favorable in 2024".
- **NEE:** the "absence of" misread in 1.2.

### 1.7 Development against held-out, and noise

**DeepSeek fell further on the held-out half than Sonnet did:**

| Model | First-try passes, development | First-try passes, held out | Opus mislabels, development | Opus mislabels, held out |
|---|---|---|---|---|
| DeepSeek | 8 of 10 | 5 of 10 | 5 | 9 |
| Sonnet | 8 of 10 | 7 of 10 | 1 | 4 |

Part of the gap is exposure. 6 held-out companies have net debt in at least 7 of 10 years (CVX, DE, DUK, KO, ORCL, TGT), against 3 development companies (CAT, NEE, PG). Four of the six debt-break packs are also held out. The net-cash and data-break errors concentrate there. Run-to-run noise is also large: on identical inputs, 4 of 5 failed in one run and 1 of 5 in another. Prompt overfitting cannot be ruled out.

### 1.8 Root causes dropped or corrected after skeptic review

- **"Negative growth written as a rise"** is dropped as a class. It is 1 slip in about 275 negative values (CVX), produced by the prompt's frame. A blanket "negative = fell" rule would break gap and contribution rows.
- **"Render transcription load"** is dropped. Under the frozen prompt it accounts for 3 of 21 failed claims, all in one run.
  - The proposed "$119.95bn" dollar format would create a double-rounding trap: 141 of 8,646 dollar values would fail when rounded correctly from the printed figure.
  - Sorting derived rows chronologically is kept as a harmless tidy-up.
- **"The repair regenerates everything"** does not cause errors. It is kept only as a latency fix. The repair instruction "use the cited value exactly" did cause the TGT regression.
- **"Percentile read as a threshold"** is dropped. It is mostly auditor artefact: Sonnet drew 3 such flags, DeepSeek 1, and RIVN's sentence is true.
- **Gate binding and parse artefacts are real, but they explain Sonnet's failures, not DeepSeek's excess.** Removing them widens the measured gap: DeepSeek 6 companies and 8 claims, Sonnet 1 and 1.
- **Letting a cited derived value license its own inputs is rejected.**
  - It changes Tier 1 of the grounding rule.
  - It would pass wrong values for 287 of 1,406 DeepSeek claims and 248 of 1,455 Sonnet claims in a substitution test. Example: CAT "Net margin fell 3.5pp to 16.7%", where 16.7% is the FY2024 level.

---

## 2. The fixes, ranked by expected errors removed per unit of risk

Unless noted, counts refer to DeepSeek on the frozen prompt.

**DeepSeek prices** (off-peak; peak doubles all three):

| Token type | Price per million |
|---|---|
| Input | $0.15 |
| Cached input | $0.003 |
| Output | $0.60 |

Latency is about 3.2 ms per output token.

| # | Fix | Where | Errors it should remove | Cost and latency | Risk to other outputs |
|---|---|---|---|---|---|
| 1 | Add the missing own ID by code before any repair. **Built, tested and removed** (see "As built") | Repair loop (`generate.py`, before `_repair`) | Planned: 7 of 17 real first-try failures (CVX 2.1%, DUK $1.7bn, NVDA 71.1% ×2, ORCL 80%, JPM 52.4%, SNAP 1.2pp), with DUK and ORCL to stop repairing. As built, it fixed 3 of 17 (NVDA 71.1% ×2, JPM 52.4%) and made no failing first pass pass; now each omission goes to the patch repair | Planned $0, about 2 fewer repairs in 20 (−$0.00015 and −0.65 s per analysis). Removed: an omission costs a patch repair, about $0.0005 and 1–3 s | Realised: a wrong but matching number got an ID, in a new form in each of reviews 6, 7 and 8 |
| 2 | Rewrite the repair message | Repair loop | Wrong-metric substitutions (TGT 1.01x, NVDA dev-v4 0.91x) and type-only escapes (NVDA) | $0 | Low |
| 3 | Operating cash flow / net income window median and low | Pack (`derived._window_figures`, new IDs appended) | 5 mislabelled sentences (CVX, DE, PG, TGT, CAT), the DUK range, and 2 first-try failures (TGT, NVDA dev-v4) | About 100 input tokens, about $0.00002 | Low to medium |
| 4 | Net-debt wording and sign handling | Pack text, red-flag wording, one prompt line | 7 DeepSeek sentences (CAT ×2, TGT, DUK, NEE ×2, ORCL), Sonnet's ORCL flag, Haiku and Gemini cases | About 100–300 input tokens, about $0.00005 | Medium |
| 5 | Sentence-type handling for "cause" | Repair loop (code) and prompt | First-try failures: MSFT (eval-v1), COST (dev-v4). Catches NVDA-style escapes. | $0; about 60 cached prompt tokens | Low to medium |
| 6 | Calibration: restore the judgement slot, put meaning in judgements, no forecasts in watch items | Prompt | Judgement share outside watch from 0.8% to about 5–9%. Evaluative words in data sentences from 5.8% (the lexicon's count; 5.5% by hand) to 3% or less. About 7 watch forecasts down to about 1. | About 80 cached tokens; output about ±100 tokens (±$0.00006, ±0.3 s) | Medium |
| 7 | Narrow fixes to gate artefacts | Gate (`factcheck.py`) | DeepSeek CVX 9.2% (AMD with a narrowed rule). Sonnet USB, ORCL, JPM, VRTX, COP. Stops repairs that make correct sentences worse. | $0 | Medium: looser year binding |
| 8 | Do not compute net cash on broken debt; add a data check | Pack data (`derived.py`, debt components; `evidence.py` data checks) | KO and CVX broken net cash stated as fact, DE "deleveraging", DE's three auditor flags, broken 100th-percentile ranks, for every model | $0 at run time | Medium: peer ranks change, gold examples need remapping |
| 9 | Net-versus-operating margin within one year | Prompt, pack (same-year derived value), gate check R3 | DE 6.5pp | About 30 tokens | Low |
| 10 | Reword the drivers instruction | Prompt | CVX "grew 3.4%" | About 30 cached tokens | Low |
| 11 | Small render items: passage table units; derived rows in year order | Pack text (`render.py`, passages) | COST "$126" and "$370"; perhaps the DUK range | Negligible | Low |
| 12 | Backstop checks | Gate | Whatever remains of fixes 3, 4, 9 and 11, plus the unsigned fall and logic slips | Each hit costs one repair | Medium: false positives cause repairs |
| 13 | Patch-style repair | Repair loop | None; latency only | A repair drops from about 6.5 s to about 1–3 s and from $0.00145 to about $0.0005. p90 falls from 16 s to about 11–13 s at today's repair rate | Medium: patch format |
| 14 | Auditor sees the signed value, the bound and twin values, and, for a figure matched in a 10-K passage, the passage sentences that print it | Measurement only (`semantics.py`) | About 10 false DeepSeek flags and 6 false Sonnet flags | $0 | None to the product |

### The fixes in detail

**1. Add the missing own ID by code. Built, tested and removed** (see "As built").
- **The plan.** For each "matches nothing" claim, look for one ID that makes the number reconcile, from three sources:
  - an ID cited elsewhere in the same analysis;
  - an input of a derived value the sentence cites, for the same period;
  - the red flag whose evidence the sentence cites.

  Accept it only if exactly one candidate fits, its period agrees with the sentence's years, and its label's metric words appear in the clause. Then append the ID and run the gate again; repair only if failures remain.
- **Why it was thought safe.** The output still carries every figure's own ID, so the grounding rule does not change.
- **Expected effect, by replay on eval-v1.** With fix 5's code retyping (MSFT), the companies needing a repair fall from 7 to 4 (AMD, CVX, NVDA, TGT).
- **Before adopting.** Run the substitution test: put wrong-year and wrong-metric values in verified slots across all records. Adopt only if almost nothing new passes.
- **What happened.** Once each round's rules were in, the substitution test found no leak in the forms it held, yet each of reviews 6, 7 and 8 found a wrong number the rules let through in a form it did not hold, and the next review found another after each patch. On the records it fixed 3 of the 7 omissions and made no failing first pass pass. It was removed in wave 5: an omission now goes to the patch repair (fix 13), in every arm alike.

**2. Repair message.**
- **Drop** "use the cited value exactly".
- **For "matches nothing":** list each cited ID's label, period and value. Say: "If the number you meant is not in the pack, delete it; never replace it with a cited value of a different metric or year."
- **For a cause sentence without a passage:** give three ways out:
  - cite, in this sentence, the passage that states the cause;
  - retype it as judgement if it states no uncited figure;
  - delete the causal clause.

**3. Typical operating cash flow / net income level.**
- **Change.** Append a window median and low for `ocf_to_ni` as new IDs after the existing ones, so no current ID is renumbered.
- **Exclusions.** Skip bank and insurer profiles (JPM would otherwise gain a 0.19x median). Leave out the window high, which comes from years of depressed net income (CVX 9.34x, CAT 7.52x). Leave out peer levels for now: they need peer data through the bootstrap.
- **No new SEC calls.** All of this comes from each pack's own series.

**4. Net-debt wording.**
- **Net-cash rows:** a legend saying "below zero = net debt; a higher percentile = more net cash than peers".
- **Red flag:** "Net debt rose N years in a row to $X", replacing "fell into net debt". As built, the level is quoted only where no `unmapped_line` data check names a year of the run: CAT R1 quotes none ("its level is left out, as total debt and net cash omit long-term debt due within one year").
- **One prompt line:** "Net cash below zero is net debt: write 'net debt of $26.2 billion', with no minus sign. Compare with peers on the pack's net-cash basis ('net cash of −38.8% of revenue against a −35.6% median'). Never set a net-debt figure beside a net-cash median as if they were on one scale."
- **Leave out** positive "twin" values for now: peers on the other side of zero and series that cross zero break them.

**5. "Cause" typing.**
- **Code:** a "cause" sentence with no passage and no explanatory clause beyond figures (MSFT's bridge, COST's capital-return sentence) is retyped to comparison before the gate decides whether to repair.
- **Repair rule:** a retype-only repair counts as still failing only when it keeps an uncited "because / so / as / due to" clause (NVDA). An absolute "changing the type is not a fix" rule would have failed 3 correct repairs on record.
- **Prompt:** "Cite the passage in the same sentence as the figure it explains." Also: "A margin bridge with no passage is a comparison."

**6. Calibration.**
- Red flags: "Close each flag with one judgement sentence on why it matters." This restores the words under which DeepSeek used judgements at Sonnet's rate.
- "A sentence that says what figures mean (structural, cushion, pressure, durable, likely, a sign of) is a judgement. Keep the figures in the comparison sentence and put the meaning in a judgement sentence."
- Align the number rule with the grounding rule's Tier 4: "A judgement may restate figures it cites in the same sentence; it never states a figure it does not cite."
- Watch items: "State the threshold and the direction that would confirm or reverse the trend, and the filing. Do not say what would follow ('would keep', 'will likely')." Fix one type convention for watch items so the judgement share is comparable across models.
- The gate should enforce the judgement tier that its documentation already describes.

**7. Gate artefacts, narrow forms only.**
- Parse "$-X" correctly.
- Improvement words: invert their direction for metrics where lower is better (efficiency ratio, cost ratios), keyed on the matched value's label.
- Reversed-difference labels ("revenue growth minus operating-cost growth"). As built, the sign is checked only in the forms the gate reads with certainty, and every other form is read by magnitude (see "As built").
- A figure after "<year> <noun> from" binds to the year before.
- "Since FY…'s X" keeps binding forward.
- "Xpp of the Ypp total" matches only the cited revenue growth.
- AMD's backward binding needs a narrowed rule that still catches the planted mutation. If none passes, leave AMD failing.
- Rerun the planted year-swap and relabel errors (`runs/plant-sem`) and the gold check after every change.

**8. Broken debt.**
- **Change.** Emit total debt, net cash, net cash % of revenue, debt growth and the peer percentile only for years whose debt components match the window's fullest set. Otherwise, add a data check naming the span: "Long-term debt not reported after FY2021; total debt and net cash after that omit it." A second test: an implied interest rate above about 12% (DE: 16–23%).
- **Separate decision for you.** The concept mapping is a production data fix: the metrics table also shows the shortened long-term-debt rows.

**9–11.**
- **Margins bullet:** "…for the latest year in which both margins are in the pack". Replace the "6.5pp above operating margin" example with a single-year example not taken from any of the 20 companies.
- **Same-year derived value:** add "net margin minus operating margin (pp)".
- **Drivers:** "Compare operating-cost growth with revenue growth, each with its own direction (rose / fell); when both fell, say which fell more."
- **Passage units:** passages from tables in millions carry their unit, so "$126" reads "$126 million".

**12. Backstop gate checks.** Turn these on only together with fixes 3, 4 and 13.

| Check | What it catches | Precision on all recorded outputs |
|---|---|---|
| R1 | A reference level of another ratio attached to this ratio | 15 of 15 DeepSeek hits true; 0 hits on Sonnet, Haiku and gold; misses coincident values |
| R2a | A minus sign under "net debt"; made asymmetric, which drops 3 of 4 synthetic false positives | 7 DeepSeek hits all true; 0 Sonnet hits. Reading the hyphenated "net-debt" (review 7) adds an eighth, dev-v3 DeepSeek CAT's final "net-debt ratio … -35.6%", also true |
| R2c | "Better" or "worse" across net-cash bases; extended to words after both numbers | Included in the 7 above |
| R3 | A cross-year difference of two margins | 1 hit in all runs (DE), true |
| U1 | An unsigned fall | 1 hit, true (COP) |
| Unitless dollars | A dollar figure matched only to a raw table literal from a passage | 3 DeepSeek hits |
| Logic checks | Direction word against the cited series; "from X" order; "recover toward" a lower level | Written on eval-v1, so dry-run before use |

**13. Patch-style repair.**
- The repair returns only the failed sentences: section, original text, new type, new text, or a deletion.
- Code applies them, keyed on the original text, then gates the whole analysis again.
- An invalid patch falls back to today's full repair.
- In all 12 recorded eval-v1 repairs only the failed sentences changed, so patching should keep everything else identical.

### As built

Where the built fixes differ from the plan above, after reviews 5 to 8. The code is the harness (`backend/evals/trend_depth/`, README there). The packs are `packs-v2/` (its README) and the candidate prompt is `backend/prompts/trends-depth-analyst-agent.md`. Each figure below is reproduced by the command named beside it, run with the code at this commit; none calls a model. Fix 1's figures of what auto-citation did are those of its last build (e505700), before it was removed.

**Fix 1: built, tested and removed** (wave 5, after review 8). The code step before a repair is fix 5's retyping
alone (`retype.py`; `retype.first_pass` is the retyping, then the gate with its backstops). A figure stated without its
own ID is a gate failure ("matches nothing the sentence cites"), which the patch repair fixes, in every arm alike.
- **What was built** (`autocite.py`, now gone). An ID was appended only when it was the one candidate that reconciled
  exactly at the figure's printed precision, had every word of its label in the figure's clause, fitted the years (no
  level the metric moved from, no comparison's base year), fitted the sign (a negative level printed unsigned got no
  ID unless the gate read the sign from the sentence), and changed no other claim's verdict. Passages and red flags
  were never candidates.
- **Why it was removed.** Each review round found a new class of wrong number its rules let through, and each patch
  was followed by another class:
  - review 6: a wrong metric through a difference (capex printed as free cash flow, a peer gap printed as the margin),
    a red flag's threshold taken as the metric's level, a label's denominator and "window median" words dropped from
    the match, and an appended ID verifying the sentence's other failing claims unchecked;
  - review 7: a level the metric moved from, or a comparison's base year ("since FY2021"), dated as the figure's own
    year, so the wrong year's value got its ID (12,537 of 15,183 substitutes in each shape before the fix); and a
    negative level printed unsigned (29 of 490);
  - review 8: the end year's ID for a from-level when "from" is not right before the figure or the level is dated only
    by a cited change, and the base year's level read as the current one after "compared with", "relative to",
    "against", "after" or "from its FY2021 level" (12 sentences on CVX, each wrong, each given an ID); and the sign
    rule refused the candidate prompt's own wording, "net debt of $26.2 billion" for CAT's net cash of -$26.2 billion.
- **What it did on the records.** Over all 187 recorded outputs it appended 3 IDs: NVDA's 71.1% in eval-v1 and dev-v4
  [F30] and JPM's 52.4% [D207]. It made none of the 25 DeepSeek first passes of eval-v1 and dev-v4 pass: each of the
  three still failed on another claim. The one first pass of eval-v1's 20 the code step makes pass (MSFT) is the
  retyping's.
- **What its removal costs.** A patch repair per omission, about $0.0005 and 1–3 s by fix 13's estimate; §3 step 1
  measures it.
- **Code-only replay** (`python -m evals.trend_depth.retype`, eval-v1's and dev-v4's DeepSeek first passes). eval-v1:
  6 of 20 fail the gate as written and 5 after retyping (CVX, DUK, NVDA, ORCL, TGT); with the backstops, 12 and 11.
  dev-v4: 4 of 5 either way. These are the counts auto-citation gave: eval-v1's NVDA keeps its 71.1% (2 failures),
  dev-v4's JPM its 52.4% (4) and NVDA its 71.1% (3). The plan expected 4 in eval-v1 (AMD, CVX, NVDA, TGT): AMD passes
  after fix 7, while DUK and ORCL stay.
- **Records made with it.** A version-2 record made before the removal carries `autocite` and is another build ("v2
  with auto-citation", `records.pipeline_of`): generate never resumes or copies it beside the version 2 of now, and
  the report warns when a label pools the two. `runs/` holds none.

**Fix 6: calibration in the candidate prompt.**
- **Red flags** are two sentences each, up to three flags: one sentence on what, how big, for how long and the stated cause, then one judgement sentence on why it matters. Where none applies, one sentence says what was screened. That gives the section 1 to 6 sentences, within the prompt's 30-sentence budget (`tests/unit/test_trend_depth_prompt_examples.py` checks every section count against the budget).
- **A verdict on what a data check does to a figure** ("unreliable", "overstated") is a judgement sentence.
- **Watch items are typed `comparison`.** This is DeepSeek's own convention, so the judgement share outside the watch list compares across arms and models unchanged.
- **The gate still does not enforce the judgement tier** (§4).

**Fix 7: a growth gap's sign, only where the gate reads it with certainty** (`factcheck.compared_sides`; wave 5,
review 8). A value labelled "revenue growth minus operating-cost growth" has its sign checked only where the clause
compares its two sides in one of these forms. The side named first is the subject: its nouns stand right before its
verb, with at most "of <figure>" and one adverb ("also", "only", "still", "just", "again") between, and never after a
preposition. The other side follows the comparative in the same clause.
- **A move.** A bare side with a rise or fall verb right before the figure, then "faster", "more", "further",
  "deeper", "steeper" or their opposites and "than" the other side ("costs fell 1.2pp less than revenue": costs minus
  revenue is +1.2), or the comparative before "than Y by" the figure. The sign is the verb's direction times the
  comparative's.
- **A standing.** A side named with "growth", placed by a verb that only places ("was", "ran", "came in"), then a
  position ("ahead of", "behind", "above", "over", "short of") or "more than" / "less than"; or an active outpacing
  verb before "Y by" the figure ("beat", "trailed", "lagged"). A side named without "growth" counts only in a year the
  pack shows the two lines did not both fall (`factcheck.both_fell`, from the gap's revenue inputs; both fell in 22 of
  144 gap values in each pack version, CVX, DE and TGT in FY2025 among them, all three held out); "outgrew" counts in
  any year.
- **Every other form is read by magnitude, with no direction verdict:** an appositive after a comma, a participle, the
  passive, a side named as its fall, a move of a growth rate, one side unnamed, a side another metric names. The match
  stays "cited", so the semantic audit sees the stored signed value (view 2). For a gap of two margins of one year,
  only standings are read; `gap_direction` reads the same forms (fix 12).
- **Effect.** On the 101 sentences of reviews 6 to 8 and the candidate prompt's forms (wave 5's working files, run on
  both pack versions with the backstops), the 54 true ones all pass; the reader before failed 20 of them, each a repair
  message that could push the model to the false mirror. 11 of the 47 false ones pass by magnitude (10 before), among
  them CVX's "Revenue fell 4.6% in FY2025, 1.2pp less than operating costs" (D379 is -1.22pp) and its mirrors on DE and
  TGT, ORCL's passive and CAT's passive margin standing (§4). `tests/unit/test_trend_depth_factcheck.py` holds 74
  certain-form sentences and 49 read by magnitude on the committed values (`CERTAIN`, `BY_MAGNITUDE`).
- **On the records.** `python -m evals.trend_depth.replay --base e505700` flips no recorded sentence and moves no pass
  count, with or without the backstops. Over every recorded output (377 outputs, 11,284 sentences: eval-v1, dev-v3,
  dev-v4, plant-sem and the gold examples) no probe verdict changes either. One match label does: Sonnet's dev-v4 REGN
  "operating costs outgrew it by 4.4pp" is now read by magnitude ("it" names no side), still verified.

**Fix 10: the drivers instruction asks for both growths, not their gap** (after wave 5). The plan's wording, "when
both fell, say which fell more", invited the appositive "Revenue fell 4.6% in FY2025, 1.2pp less than operating
costs", whose false mirror fix 7 can only read by magnitude (§4). The candidate now says: "Compare operating-cost
growth with revenue growth by stating both, each with its own figure and direction ('revenue fell 9.4% while
operating costs fell 6.1%'), citing both; do not restate the gap between them as 'Xpp more' or 'less'." Each growth
then carries its own direction word, which the gate has always checked against the cited growth's sign. The frozen
prompt (K0, P) keeps its wording, so a gap mirror there is measured by the Opus audit alone.

**Fix 8: debt and cash breaks in pack version 2** (`packs-v2/README.md`).
- **Withheld, not dropped.** Every ID built on a broken year stays in the pack, so a version-1 output still checks against it, but the render does not show it (`withheld`).
- **Debt breaks.** These are found by line tests:
  - `debt_break`: the long-term debt line is missing or zero while debt is still evident;
  - a debt onset: a smaller debt line first appears and total debt jumps while interest expense does not follow. DE's FY2016–FY2019 total debt is long-term debt only;
  - a debt double count (review 8): the long-term line already holds the current line total debt adds to it. The filer's own figure decides: its noncurrent debt and leases, less the noncurrent leases its same 10-K reports, equal the long-term line less the current line within a quarter of the current line (had the long-term line left the current portion out, the two would differ by the whole current line). Only a long-term tag that may hold its current portion is read, beside a current line above 1% of it. It names TGT FY2016–FY2018 as a `debt_break` check and withholds TGT's total debt and its growth there (D14, D33, D82; D62, D109, D156; its net cash was already withheld). Among the peers it names BA, PH and UPS, so CAT's checked industrials median leaves out BA FY2025, PH FY2026 and UPS FY2025 and moves from -38.0% (n=6) to -59.4% (n=3).
- **The implied-rate test detects no break.** It fires on none of the 20 outside the break spans, and inside them it misses most first years.
- **Liquidity breaks** (`liquidity_break`): a cash or investment line missing in one year (COP, MSFT, NVDA, ORCL), or short-term investments already inside cash (TGT).
- **Checked peer ranks.** A version-1 net-cash peer rank or median built on a peer's broken year is withheld (`peer_break`). Where three or more peers pass the same tests it is replaced by a checked rank under a new ID: PG, CAT, COST, AMD, DUK and NEE; RIVN keeps none.
- **A new data check, `unmapped_line`** (review 7). It names a line the filer reports and the pack sums nowhere, at 10% or more of the total it is missing from, in a year no break check of the same kind (debt or cash) names: CAT's long-term debt due within one year ($7.1 billion at FY2025, so its net debt reads $26.2 billion [D456] against $33.4 billion), and KO's cash and investments total above the pack's (FY2016–FY2017, FY2021–FY2025; FY2024–FY2025 are debt-break years, whose cash and investments [D440] stay shown).
  - It withholds nothing. Lines it cannot see are listed in the packs-v2 README under "Not detected": TGT's FY2019 double count, AMD's FY2023 and FY2025 current portion tagged twice, CVX's FY2016–FY2017 short-term debt that holds its current maturities and its FY2020–FY2021 long-term line, COP's FY2017–FY2020 long-term line above its own total, and PG's available-for-sale securities, among others. Every arm sees them alike, and the broken-net-cash measure does not count them (§4).
  - The broken-net-cash measure does not count these lines. P and C see the check; K0 and Q do not.
- **ORCL's FY2022 long-term debt line, reported as zero [F185, X213], is withheld** (review 7).

**Fix 12: two backstops beyond the plan** (`probes.py`; each a gate failure under `--pipeline v2`).
- **`gap_direction`.** Net margin said to be above or below operating margin against the sign of the same year's gap: the cited "net margin minus operating margin" value, or the difference of the two margins the gate matched.
  - It reads only the forms the gate reads a gap's sides in with certainty (`factcheck.compared_sides`, fix 7: net margin the subject, in the active voice, operating margin after the comparative, "3.4pp more than" and "over" included). A passive ("net margin was exceeded by operating margin by 3.4pp") or any other form is left alone (review 8).
  - The gate reads no direction into a same-year gap, so this is its sign check on either pack version. A sign error on packs-v2's cited gap therefore falls in the same row for P and C as for K0.
  - It finds no hit in eval-v1.
- **`broken_debt`.** A figure version 2 withholds, cited by its ID, or the same figure rebuilt from the lines version 2 shows: a line of a break year under a total's name, or beside a total of another year. Plain "debt" is the total, but debt named by a maturity after it ("debt due within one year", "debt maturities", "$1.0 billion of debt matured") is that line, and so is a figure said to fall due ("Of Deere's debt, $13.8 billion falls due within a year"; review 8). In a double count only a figure on both lines is broken, their sum whatever it is called: TGT's cash with its short-term investments, and TGT's FY2016–FY2018 long-term line with its current line, where the long-term line alone is the right total under any name ("Debt was $11.7 billion in FY2016 [X175]" passes; wave 5's integration, since without it that check failed this true sentence in P's and C's gate, with a repair message pointing at the double count). It is excused only by a disclosure in a clause about debt or cash (`probes.discloses`, the one rule that the gate, the stated sentences and the analysis's state all read): the data checks' words, or the break said plainly of the line it is about, as the candidate prompt asks ("long-term debt is absent", "not available", "has no value", "disappears", "ignores long-term debt", "the pack carries no long-term debt", "carries FY2025 short-term investments but none for FY2026"; review 8). The same words about another line or about the company ("with buybacks absent", "as Coca-Cola carries no long-term debt") disclose nothing.
  - The gate's backstop reads the arm's own pack, so it fires only for P and C, as `packs/` records no break.
  - The report's measure reads `packs-v2/`'s breaks for every arm.
  - Review 7's 42 broken sentences are all caught. Its 3 false failures, and 59 correct sentences on the 9 break companies' packs, pass (re-run on wave 5's code and packs). Review 8's six sentences on debt that falls due (DE, CVX, COP) and its plain disclosures now pass.
  - Over every recorded output, wave 5 moves no `broken_debt` hit; one sentence's disclosure changes, dev-v3 Sonnet NVDA's "the pack carries FY2025 short-term investments [X188] but none for FY2026", which states no broken figure.
- **The logic checks are measures, never failures** (`MEASURE_KINDS`).

**The measurement nonce** (not in the plan). Under `--pipeline v2`, each user message opens with a nonce of the label, arm and ticker (`generate.analysis_nonce`, recorded as `nonce`), and its repair repeats it.
- **Why:** so no run's first request reads an earlier run's pack from DeepSeek's prompt cache. A company's first analysis in production would not.
- **Cost:** a first request then reads only the system prompt from cache. In eval-v1, 5 of 20 DeepSeek first attempts read more, and §3's cost prices them cold.

**Fix 13: step 1's replay bills each call once** (`repair_replay.py`, review 8). Its calls run with no client retry
within a call (`providers.Arm.max_retries`: 0 for the replay, 2 for every arm, as before). A retried call can bill
again, and the OpenAI client's retries sit inside the harness's own re-sends after a 429 or a 5xx, so a multiplier would
not have bounded the dry run's ceiling. Now a timeout or a dropped connection ends the call as a `repair_error`, which
the next run retries in the open, and the ceiling holds as long as a 429 or 5xx reply bills nothing. Step 1's latency
therefore leaves out the in-call retries the arms' runs keep.

**Fix 14: the auditor's view 2** (`semantics.py`, `VIEW = 2`).
- **Sign rule.** Values are shown signed, and the auditor is told that the sentence must give the value's sign, by a minus sign or in words. "Net debt of $26.2 billion" for a net cash of -$26.2 billion is consistent; a minus sign under "net debt" is a mismatch.
- **Period rule.** An input's twin is shown only when every input is of the value's own period. AMD's FY2019 total debt growth [D170] has an FY2019 input equal to long-term debt but no such FY2018 one, so as a twin it would have licensed "long-term debt fell 61.1%"; long-term debt fell 56.4% [D157].
- **Withheld twins.** An ID a version-2 pack withholds is never a twin: COP's FY2025 "Total debt" [D336] is its current portion alone.
  - On `packs/`, which shows K0 that total under its own label, the twin stays.
  - The recorded outputs that read `packs/` hold 6,746 verified claims of the 15 companies whose version-2 pack withholds IDs (eval-v1, dev-v3, dev-v4 and plant-sem; review 7 measures [5], checked again on this commit's packs). 1,202 of them are shown a twin, and no twin is an ID that `packs-v2/` withholds.
- **Passage text.** A figure the gate matched in a 10-K passage is shown with the passage sentences that print it, with the 10-K's fiscal year and section: at most 3 sentences, each cut to 400 characters around the figure. View 1 said only "a figure in a FY2025 10-K passage".
  - On eval-v1 this changes the view of 126 of DeepSeek's 1,459 verified claims and 120 of Sonnet's 1,458.
  - It adds about 7% to view 2's audit message: 18,810 to 20,169 characters on average over eval-v1's 40 DeepSeek and Sonnet audits.
- **Message size against view 1** (measured on the same 40 audits, review 8 measures [1]). View 2's user message is about 22% longer than the one Opus read under view 1 (20,169 against 16,596 characters on average, with the same 73 items), and its SYSTEM is 2,900 characters against 786, so the whole input is about 33% longer (23,069 against 17,382). By a fit of 80 recorded Opus audits' cost on their characters and items ($0.0165 an audit, $2.58 per million characters, $0.00104 an item; R² 0.91), input is about a third of an audit's cost, so view 2 adds about $0.015 an audit.
- **One quantity, one flag label** (review 8 measures [0]). `classify_flag` counts a mismatch flag as ambiguous only when two differently labelled quantities match the figure. A cited derived value whose inputs, unit and signed value are those of another matching calculation is that calculation: packs-v2's same-year gap [D693] is PG's net margin [F50] less its operating margin [F30]. Before, an Opus flag on C's sentence that cites [D693], as the candidate prompt asks, was dropped as ambiguous, while the same flag on K0's sentence without it counted. None of the 146 recorded mismatch flags changes class.
- **No record carries a view yet.** Step 0's re-audit is the first under view 2.

### Tested separately, not in the candidate
- **Sentence key order: "text" before "type"** in the output schema. Both models currently write the type first, so the expected effect is unclear.
- **Temperature 0.** This might reduce run-to-run spread, but there is no evidence either way.

### Not recommended
- DeepSeek's thinking mode. Reasoning tokens bill as output: 1,000 of them add about 3 s and $0.0006, and Sonnet used 2,000–12,000.
- A blanket "negative means fell" rule, and "(fall)" tags on rows.
- The "$119.95bn" dollar format.
- A "k of n peers" percentile wording, which the gate cannot check.
- Moving every reference level inline beside its series.
- Gate rules on passage years (about 50% precision).
- Letting a cited value license its inputs.

### Expected combined effect

These are expectations; section 3 measures them.

| Measure | Today (eval-v1) | Expected |
|---|---|---|
| Companies needing a repair | 7 of 20 | 4 with code-only fixes (replayable today); 1–3 with pack and prompt fixes |
| Real mislabelled sentences | About 14 | 2–4 |
| Judgement share outside watch | 0.8% | 5–9% |
| Cost per analysis | About $0.0068 | $0.006–0.0068 |
| p50 latency | 9.7 s | About 9.2–9.6 s |
| p90 latency | 16.1 s | About 10–13 s |

As built, the code-only replay of eval-v1's DeepSeek first passes leaves 5 companies failing the gate (CVX, DUK, NVDA, ORCL, TGT) and 11 with the backstops, which the arms run under. The code step is the retyping alone (see "As built", fix 1): auto-citation, before its removal, gave the same counts.

---

## 3. The experiment

### Step 0: no model calls

1. **Build the code fixes and the measures.**
   - The code fixes: 2, the code part of 5, 7, 12 and 14. Fix 1 was built, tested and removed (§2, "As built").
   - Move the deterministic probes into the harness with unit tests (`backend/tests/unit/`), per CLAUDE.md rule 12. The probes are R1, R2a, R2c, R3, U1, unitless dollars, the logic checks, the interpretation lexicon and the watch-forecast lexicon.
   - `report.py` prints every metric below.
2. **Replay every recorded output through the new gate and the retyping:** eval-v1, dev-v1 to dev-v4, plant-sem and the gold examples. Report:
   - every change from failing to passing, read by hand (`python -m evals.trend_depth.replay`, and `python -m evals.trend_depth.retype` for DeepSeek's first passes through the code step);
   - that all planted year swaps and relabels are still caught;
   - that the gold examples still pass.
3. **Build the pack fixes (3, 4, 8, 9, 11).** Append IDs rather than renumber. Run `gold check`, and `gold remap` if any ID moves. Check rendered token counts.
4. **Prompt examples:** none may be copied from the 20 companies. That would spoil the re-test, as NVDA's own sentence would have.
5. **Re-audit eval-v1 under the auditor's view 2**, then run the report on it. Opus re-audits DeepSeek's and Sonnet's 40 outputs under the label `eval-v1-view2`, and `report --label eval-v1-view2` prints the like-for-like mislabel baseline for K0 and C, whose audits run under view 2. The commands are in the harness README.

### Step 1: patch-style repair, tested on its own

- **What is replayed.** Every recorded DeepSeek first pass that version 2 would still repair after its retyping goes through the patch repair, twice each (`repair_replay.py`). "Would still repair" means it fails `generate.fix_first_pass`, which runs `retype.first_pass`: the retyping, then the gate with its backstops, on `packs/`.
- **The cases.** From eval-v1, dev-v4 and dev-v3 that is 21 cases:
  - eval-v1 11: CAT, COP, COST, CVX, DE, DUK, NEE, NVDA, ORCL, PG, TGT;
  - dev-v4 4: COST, JPM, NVDA, SNAP;
  - dev-v3 6: CAT, COST, MSFT, NVDA, PG, REGN.

  Of eval-v1's 7 repaired analyses, AMD and MSFT no longer need a repair. CAT, COP, COST, DE, NEE and PG join on backstop hits alone. `repair_replay --dry-run` lists the cases and why each first pass not listed needs no repair. With auto-citation removed the list is the same, and three cases each hold the omission it used to fix: eval-v1 NVDA's 71.1% (2 failures), dev-v4 JPM's 52.4% (4) and dev-v4 NVDA's 71.1% (3).
- **Calls.** 42 repairs make 42 to 84 calls: a patch, and a full repair when the patch is unusable. Cold is the expected state: the recorded first passes are days old, and a case's two repeats may run at once.
- **Cost:**
  - about $0.26 off-peak if every patch is read cold and none falls back;
  - $0.56 off-peak ($1.12 at peak) if every prompt is read cold and every patch falls back;
  - at most $2.38 off-peak ($4.75 at peak), the dry run's ceiling: every prompt at one token per byte, every reply at `max_tokens`, and each call billed at most once, as the replay's client retries nothing within a call (§2, "As built", fix 13). The first two estimates calibrate tokens on the recorded first attempts and repairs.
- **Measures.** Repair latency (p50 and p90 on the report's basis, `records.quantile`), full repairs, the final gate result, and whether untouched sentences stay byte-identical.

### Step 2: development half (label `dev-v5`)

Ten development companies, two independent generated runs per arm. All arms use the new gate and repair code, so they differ only in pack and prompt.

| Arm | Pack | Prompt | Measured with |
|---|---|---|---|
| K0 (control) | Current | Frozen (`d558d371`) | Deterministic measures; Opus audits (semantic audit with the fixed view, plus causes); V4 Pro second auditor |
| P | Fixed | Frozen | Deterministic measures only |
| Q | Current | Fixed | Deterministic measures only |
| C (candidate) | Fixed | Fixed | Everything K0 gets, plus the Opus judge C against K0 in both orders |
| S, T (optional) | Fixed | Fixed; S writes "text" before "type", T runs at temperature 0 | Deterministic measures only |

- P and Q show which half of the candidate moved each measure, and catch interactions: for example, judgements crowding out causes.
- K0 is also scored under the old gate, for continuity with eval-v1.
- The judge compares DeepSeek with DeepSeek, so Opus's possible preference for its own family's writing does not apply.
- At most one further development round (`dev-v6`), and only to fix what `dev-v5` shows.

### Step 3: freeze, then the held-out half (label `eval-v2`)

- Record the prompt sha and the pack snapshot ids.
- Run K0 and C on the 10 held-out companies, two runs each. eval-v1's DeepSeek held-out outputs serve as a third K0 reference after re-audit.
- Opus audits all runs; the Opus judge compares C with K0.
- Optionally, judge C against eval-v1 Sonnet on the 10 held-out companies, to see how much of the gap closed.
- Then one more held-out run of C under its own label (`eval-v2-peak`), started and finished inside DeepSeek's peak window (01–04 or 06–10 UTC on a weekday). Only its latency counts, against the p50 and p90 targets; it needs no audit or judge. The report prices it at the off-peak list price, and its bill is twice that. The command is in the harness README (step 4).
- Nothing is changed after held-out results are seen.

### Measures

All measures are reported per split (development, held out) and per run, as a range, never the better run alone.

| Measure | How | DeepSeek, eval-v1 | Sonnet, eval-v1 | Target for C |
|---|---|---|---|---|
| Passes without a model repair | Each arm's own pipeline: under `--pipeline v2`, the gate with its backstops after retyping. A failed generation (invalid replies, a refusal) counts as not passing and has its own row (target 0). So does a record whose repair generate still owes (`records.awaiting_repair`), since generate repairs only a first pass that failed. A generation lost to a provider error is in no row; a warning heads the report until generate makes it | 13 of 20 as run, under eval-v1's gate of its day (7 repaired); 0 failed. On the arms' basis: 9 of 20 | 15 of 20 as run (5 repaired); 0 failed. On the arms' basis: 18 of 20 | At least 85% pooled; no run below 80% |
| Repairs sent for broken net cash alone | Repairs sent or owed whose first-pass verdict failed only on the gate's broken_debt backstop. The backstop reads the arm's own pack, so only P and C, reading `packs-v2/`, can have one; K0's and Q's same figures count under broken net cash. Read it beside the pass row before calling a pack fix harmful | 0 of 7 repairs | 0 of 5 repairs | — |
| Real first-try gate errors per analysis | Distinct failing claims (and causes without a passage) of the model's own first output, before the code's retyping, under the gate now without backstops; known artefacts subtracted by hand. A figure stated without its own ID counts here in every arm, as no code adds it | 0.68 (17 in 25, frozen prompt): eval-v1 0.40 (8 in 20; development half 3 in 10), dev-v4 1.8 (9 in 5) | 0.04 (1 in 25; eval-v1's 2 are artefacts) | 0.15 or less |
| First-try backstop hits per analysis | Distinct claims the backstops fail beyond the gate's, broken net cash apart (its own row); each one a repair under `--pipeline v2` | 0.90 (18 in 20) | 0 (0 in 20) | — |
| Mislabels per 1,000 verified claims, probes alone | Distinct sentences with a probe hit R1, R2a, R2c or R3, over every output. This is the basis every arm shares, as P and Q have no Opus audit. A sentence stating broken net cash is counted there instead | 8.2 (12 sentences in 1,459 claims) | 0.0 (0 in 1,458) | — (read beside the next row) |
| Real mislabels per 1,000 verified claims | Distinct sentences, over the outputs Opus read (K0 and C): probe hits R1, R2a, R2c and R3 plus Opus substantive flags, read by hand. A sentence stating broken net cash is counted there instead; U1, unitless dollars and the margin-gap direction have rows of their own | About 8.9 (13 sentences in 1,459 claims after reading; 15 before, 10.3). §1.2's 14 included TGT's net-debt sentence, now counted under broken net cash. These are view-1 audits; step 0 gives view 2's | About 0.7 (1 after reading; 5 before, 3.4) | 3.5 or less in each run |
| Judgement share, outside watch | Sentence types | 0.8% (4 of 530) | 3.8% (20 of 527) | 3–12% |
| Evaluative words in fact and comparison sentences | Lexicon (`backend/evals/trend_depth/calibration.py`), outside arc and watch | 5.8% (19 of 330) | 2.2% (7 of 312) | 3% or less |
| Watch items with forecast wording | Lexicon, read by hand | 11 of 60 by the lexicon; about 7 after reading (§1.3) | 1 of 60 | 2 or fewer per 60 |
| Unsigned falls | U1 | 1 | 0 | 0 (guard) |
| Unitless dollars; net margin's direction against operating margin | Probes `unitless_dollars`; `gap_direction`, the sign check on a same-year margin gap, cited or as two margins' difference. The gate leaves that gap unsigned, so a sign error on it lands in this row for every arm | 2 (COST); 0 | 0; 0 | — |
| Broken net cash stated as fact | Analyses of a company whose `packs-v2/` pack names a debt or liquidity break (COP, CVX, DE, KO, ORCL, TGT, USB; MSFT and NVDA liquidity only). Its breaks are read for every arm: a withheld figure cited by its ID, or rebuilt from the lines `packs-v2/` still shows (a line of a break year under a total's name, plain "debt" included but not debt named by a maturity or a figure said to fall due, or beside a total of another year; in a double count, TGT's cash with its short-term investments and its FY2016–FY2018 long-term line with its current line, only the two lines' sum). A sentence discloses a break only in a clause about debt or cash, in the data checks' words or the break said plainly of its line (`probes.discloses`). The lines version 2 names only in an `unmapped_line` check (CAT's current portion of long-term debt, KO's investments), and those no test names (`packs-v2/README.md`, "Not detected"), are outside this measure | 6 of 9 stated as fact (debt break 4 of 7: COP, CVX, DE, KO; liquidity break 2 of 5: NVDA, TGT); 1 disclosed (USB) | 2 of 9 stated as fact (debt break 1 of 7: DE; liquidity break 1 of 5: TGT); 5 disclosed | 0 stated as fact |
| Sentences stating a broken figure | The same, each sentence that states one without disclosing the break in that sentence, whatever the analysis says elsewhere | 13 | 6 | 0 |
| Version-1 peer ranks on a peer's broken year | `peer_break`: only an arm reading `packs/` can cite one, so informational | 7 sentences in 7 analyses | 7 in 7 | — |
| Cause support | Opus causes audit | 76% / 23% / 1% | 76% / 22% / 1% | Guard: at least 72% supported, at most 2% unsupported, at least 6 cause sentences per analysis |
| Judge, C against K0 | Opus, both orders must agree. The report prints each criterion, and the pairs whose grounding and calibration a side each won or tied, per run and summed | Against Sonnet, for reference: grounding won or tied in 17 of 20, calibration in 18, both in the same pair in 16; depth lost in 1 | Against DeepSeek: both in 20 of 20; depth lost in 2 | C wins or ties both grounding and calibration in the same pair on at least 12 of 20 per split (the joint reading; each criterion apart is printed beside it); loses depth on no more than 5 |
| Form | Words, sentences, sections | 618 words average (735 max); 29.5 sentences (31 max); all 7 sections in 20 of 20 | 612 (656); 29.4 (32); 20 of 20 | 700 words or fewer, 30 sentences or fewer, all 7 sections |
| Cost and latency | `records.api_cost` and latency. A first request reads its prompt's shared prefix from cache: what most first requests of that prompt read over every label in `runs/` (1,920 tokens for the frozen prompt). So a warm repeat is priced cold, and warm first attempts are counted. Latency quantiles are linear between the two nearest ranks (`records.quantile`) | $0.0068 (5 of 20 first attempts warm); 9.7 s p50; 16.1 s p90 | $0.2073; 55.6 s p50; 66.1 s p90 | At most $0.0075 off-peak; p50 at most 10.5 s; p90 at most 13 s. Also measure one run at peak hours (step 3's `eval-v2-peak`) |

**Where each baseline comes from.** Every figure above is printed by
`python -m evals.trend_depth.report --label eval-v1 --systems deepseek-flash,claude-sonnet-5-5` with the code at this
commit, in the §3 measures table of its "all: 20 companies" section. dev-v4's come from the same command with
`--label dev-v4`. Five baselines are derived from those rows:
- **Passes as run.** The pass row prints 13 and 15 of 20, as does the "Gate at b3ed8ef" continuity row.
- **Passes on the arms' basis:**
  - DeepSeek: 20 less the 11 eval-v1 cases that `repair_replay --dry-run` lists;
  - Sonnet: the arm table's current gate, 18 of 20. Sonnet has no first-try backstop hit, and its two failures (VRTX and COP, year bindings) are not sentences the retyping, the only code step before a repair, changes.
- **Real first-try gate errors.** DeepSeek's 17 in 25 are eval-v1's printed 8 in 20 (development half 3 in 10) plus dev-v4's 9 in 5; none is a known artefact under the gate now. Sonnet's 1 in 25 is the printed 2 in 20 and 1 in 5, less eval-v1's VRTX and COP year bindings (§1.1's artefacts).
- **Mislabels after reading.** For DeepSeek, the printed 15 sentences less VRTX's and RIVN's flags, both true (§1.2). For Sonnet, the printed 5 less two twin values and two paraphrases (§1.2). Step 0's `report --label eval-v1-view2` prints the same rows from view-2 audits.
- **Watch forecasts after reading.** The printed 11 of 60, read as in §1.3.

Wave 5 (review 8) changed one printed baseline: the broken-net-cash row's debt-break denominator, 6 to 7, as TGT's
FY2016–FY2018 double count is a debt break (DeepSeek 4 of 7, Sonnet 1 of 7; the held-out half 3 of 6 and 1 of 6).
Every other row prints as before: the gate's new gap reading and disclosure forms, the double count's sum rule and the
flag merge (none of 146 recorded flags changes class) move no recorded verdict, and the removal of auto-citation
touches no baseline record, as eval-v1 and dev-v4 ran version 1 (the report's own-ID row went with it).

### When to stop

- **From development to held-out.** Move on when C meets every target in both runs, or misses one by less than K0's own run-to-run spread, and no guard measure has worsened in both runs.
- **When the two runs disagree.** If the runs of an arm disagree on pass or fail against a target, run a third (about $0.07 of DeepSeek and $1.8 of audits).
- **When C misses on development.** Use P and Q to find which fix failed. Allow one more development round only, then freeze anyway and report.
- **When a fix does harm.** Drop any fix whose arm worsens a guard measure in both runs.
- **Held-out runs once.** Its range is the result. If it misses by more than development did, report that and stop: no tuning on held-out.
- **Code fixes ship on their own evidence.** Fixes 2, the code part of 5, 7 and 13 are proven by replay and the C runs, and can ship even if the prompt and pack candidate stalls. Fix 1 was removed (§2, "As built").

### Expected spend

Opus figures are eval-v1's per-output rates as billed through the command-line tool:

| Item | Rate |
|---|---|
| Opus semantic audit | $0.136 per output |
| Opus causes audit | $0.045 per output |
| Opus judge | $0.25 per pair, both orders |

API list price would be somewhat lower. These are view 1's rates. Under view 2 a semantic audit's input is about a
third longer (§2, "As built", fix 14), which a fit of the recorded Opus audits' cost prices at about $0.015 more an
audit: about $0.6 on step 0's 40 and about $1.0–1.2 on steps 2 and 3's 70–80, in the rows below. If every dollar of
an audit grew with its input instead, step 0 would cost about $7.2.

| Item | DeepSeek | Opus |
|---|---|---|
| Step 0: re-audit eval-v1 DeepSeek and Sonnet with the fixed auditor view (40 outputs), for a like-for-like baseline | — | About $6.0: $5.40 recorded under view 1, plus about $0.6 for view 2's longer input |
| Step 1, patch-repair replay (21 cases, 42 repairs, 42–84 calls) | About $0.26–0.56 off-peak; at most $2.38 (the dry run's ceiling) | — |
| Step 2: 4 arms × 2 runs × 10 companies, plus optional S and T (about 120 analyses) | About $0.85 | — |
| Step 2: audits of K0 and C (40 outputs) and the judge, C against K0 (20 pairs) | — | $7.8 + $5.1 |
| Optional second development round (20 analyses, audits, judge) | $0.15 | $8.9 |
| Step 3: K0 and C × 2 runs × 10 held-out (40 analyses) | $0.30 | — |
| Step 3: audits (30–40 outputs), judge (20 pairs), optional C against Sonnet (10 pairs) | — | $5.9–7.8 + $5.1 + $2.5 |
| Step 3: C at peak hours, one held-out run for latency (10 analyses) | About $0.14 (peak price) | — |
| V4 Pro second auditor, all audited outputs | About $0.8 | — |
| **Total** | **About $2.4–2.8**: $2.35 without the optional round, $2.80 with it and step 1 at its high estimate; at most about $4.6 with step 1 at the dry run's ceiling. Every row but the peak run is off-peak, and a row run at peak doubles | **About $30–43**: $29.9 without the optional items and with step 3's fewest audits, $43.2 with all of them |

---

## 4. What could not be explained, and what to watch

- **Why DeepSeek drops a figure's own ID.** The prompt has said "every sentence carries the IDs of all its own figures" since its second version. Under the frozen prompt DeepSeek still omitted an ID 8 times, Sonnet once. Possible causes: no thinking pass, writing the type before the text, long figure chains. None has been tested.
  - With auto-citation removed, no code hides an omission: it is a first-try gate error ("matches nothing the sentence cites") in every arm, counted in §3's row of those, and each one costs a patch repair (about $0.0005 and 1–3 s).
- **Model or thinking?** Every Claude arm thought first (Sonnet 2,000–12,000 reasoning tokens); DeepSeek wrote 0. Model and thinking cannot be separated on these records, and thinking does not fit the latency budget.
- **Noise.** Identical inputs failed in 4 of 5 companies in one run and 1 of 5 in another. Ten companies with two runs size large effects only. Per-company stories are not evidence.
- **The held-out drop.** Net-debt exposure (6 held-out companies against 3 development) and prompt overfitting cannot be separated with these data.
- **The logic-slip gap is uncertain.** It was found with probes written after reading DeepSeek's eval-v1 outputs. On the development runs the probes find 1 DeepSeek slip and no real Sonnet slip.
- **Auditor noise runs both ways.**
  - Opus flagged DeepSeek's correct DE conversion; V4 Pro flagged correct DUK conversions from both models.
  - About half of the raw flags are artefacts.
  - Count mislabels from probes plus hand reading, and fix the auditor's view before comparing runs.
- **Calibration may not move the judge as far as the measures suggest.** Opus's calibration notes also cite uncited "so / as" inferences, and the word lexicon is only a proxy. DeepSeek's sentence-type mix also turns on single words in section instructions, so any prompt edit can shift types elsewhere. Watch the full type mix every run.
- **Unconfirmed record.** The earlier prompt texts in `calibration/prompt_v*.md` are reconstructions; the dev-v3 records carry no prompt hash. The "one judgement" finding rests on that reconstruction.
- **The gate's judgement tier** is described in `factcheck.py` but not enforced, and the prompt's rule is stricter than the grounding rule's Tier 4. This needs a decision.
- **Growth-gap mirrors the gate passes by magnitude** (fix 7). A false sign in a form the gate does not read with certainty passes it, for every arm alike: "Revenue fell 4.6% in FY2025, 1.2pp less than operating costs" on CVX (the gap is -1.22pp), and its mirrors on DE and TGT, all held out. The plan's drivers wording ("when both fell, say which fell more") invited that appositive; the candidate prompt now asks for both growths instead (As built, fix 10), and the frozen prompt keeps it. Only the Opus audit of K0 and C, which sees the signed value under view 2, can catch them; P and Q have no audit. Older, and untouched: a false sign in any form passes when the sentence also cites both growth rates, as their unsigned difference settles the claim.
- **Production data.** Long-term debt mapping breaks in 6 of 20 packs, and TGT's long-term tag already holds the current portion its total debt adds (FY2016–FY2018, which version 2 names). It probably also affects peers' net cash, the peer medians and the production metrics table. Version 2 also finds lines the pack never sums:
  - CAT's long-term debt due within one year and KO's short-term investments (`unmapped_line`);
  - others no test sees, among those `packs-v2/README.md` lists under "Not detected": TGT's FY2019 double count, AMD's FY2023 and FY2025 current portion counted twice (its FY2025 net cash reads $6,456m against $7,330m), CVX's and COP's long-term lines (CVX FY2016–FY2017 and FY2020–FY2021, COP FY2017–FY2020), and PG's available-for-sale securities. Every arm sees them alike, and the broken-net-cash measure does not count them. A test that reads one tag's meaning fails on another filer, so only the shape the filer's own figures decide is named.

  ORCL's FY2022 long-term debt reads zero. This is a separate production decision.
- **The DeepSeek service.**
  - The model may change silently under the same alias.
  - Peak hours double the price (about $0.014 per analysis).
  - Latency varies with load: measure p90 at production hours before launch.
- **Outside the deterministic net.** Thin or stale red flags (TGT's burn-coverage flag refers to FY2022) and errors only a careful reader finds remain partly unmeasured. Keep a hand-read sample of Opus judge rationales in each round.

---

---

## Evidence

The analysis scripts and intermediate tables were working files of the session that wrote this plan. They
are not committed, because the probes they contain move into the harness, with unit tests, in step 0 of §3
(CLAUDE.md rule 12). Every instance above names its company, its sentence and its pack IDs, so it can be
re-checked against the committed records in `runs/` and the packs in `packs/`.

**Opus spend in §3** is the rate billed through `claude -p`. It runs on the Claude subscription, not the
Anthropic API key.
