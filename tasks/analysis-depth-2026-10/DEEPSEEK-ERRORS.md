# DeepSeek flash's error gap: diagnosis, plan and results

Plan for the "AI trend analysis" in Multi-Period Analysis, 25 October 2026, with the experiment's results of
26 October (§5). Branch `claude/trend-analysis-depth-eval`.

**Decision (founder, 2026-10-25):** stay on DeepSeek flash. Claude Sonnet 5.5 is not adopted: it cost about
30 times as much ($0.21 against $0.007 an analysis) and took about a minute instead of 10 seconds. This
document explains why DeepSeek's error rate runs higher and how to close the gap at DeepSeek's cost. §5 reports
what the experiment found and recommends what to adopt.

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

**Outcome (built 25–26 October, measured 26 October, §5).** The candidate C was frozen after two development
rounds. It is pack version 2, the candidate prompt and the version-2 repair loop. It ran twice on the 10 held-out
companies, beside the frozen configuration (K0, also twice) and one run of the version-1 procedure that the founder's
decision priced (the production control), all off-peak on the same evening. P, the same build with the frozen prompt
in place of the candidate, ran twice more on those companies afterwards.
- **The error gap is not closed.** Read by hand, the final text states a verified number about the wrong metric,
  period or sign 3.4–5.1 times per 1,000 verified claims in every build: K0 3.4, C 3.6, P 5.1 and the control 4.1.
  Each rate rests on 3 to 7 sentences, so none can be told from the others. Sonnet scored 1.4 in eval-v1.
- **The code and pack fixes (P) did what they were for, at the control's cost and a shorter wait:**
  - no broken net cash stated as fact, where K0 stated it in 8 of 12 analyses of companies with a data break;
  - no probe-detected mislabel left for a reader: each goes to repair, and an output that keeps one fails the gate;
  - p50 10.9 s and p90 12.1 s pooled, at $0.0066–0.0067 an analysis, against the control's 12.8 s, 17.8 s and
    $0.0071. By run, P's p50 was 10.54 and 10.9 s, just over the 10.5 s target in both. That is off-peak; the
    peak-hour run has not happened yet;
  - the cause count kept: 6.6 cause sentences per analysis over six runs, the same as K0.
- **The candidate prompt (C) fixed calibration but cost depth.** Its judgement share was 11.6% (K0 1.0%), with no
  evaluative words in data sentences and no forecasts in watch items, and the judge preferred C to K0 overall in
  10 pairs to 5. But it wrote fewer cause sentences than K0 in every run, by 0.4 to 2.0 per analysis and 1.0 on
  average (5.6 over six runs). That is below §3's guard of 6, and K0 won depth in 9 of 20 held-out pairs.
- **First tries:** 40% of P's and 45% of C's analyses passed without a repair, against a target of 85%.
- **Recommendation, a proposal for the founder** (§5.10). Once the grounding rule is approved:
  - Adopt the code and pack fixes as measured in P, with a per-attempt deadline on each DeepSeek call. Two
    judgements are in this:
    - the pack is kept although a strict reading of §3's guard rule fires on it once, in one development round and
      within K0's own spread from run to run;
    - the backstops go on without the net-debt prompt line that §2 made one of their conditions.
  - Hold back the candidate prompt, as §3's pre-registered guard rule requires. Either run one prompt round for
    calibration that keeps the cause guard, or adopt C under a recorded exception to the guard.
  - Then add deterministic checks for the errors that remain, starting with "above or below a reference level".

  Nothing in production has changed. The peak-hour latency run (`eval-v2-peak`) is scheduled for 2026-10-27
  06:05 UTC and has not run.

**Diagnosis (25 October, §1–§3):**

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
- **Proof:** measure on the development half first and then the held-out half, with two generated runs per configuration. Deterministic metrics come first, then the Opus auditor and judge. Expected spend is about $2.1–2.5 of DeepSeek (at most about $4.3) and $30–43 of Opus (§3). Spent: $2.79 of DeepSeek and $52.01 of Opus at the CLI's notional rates, P's held-out runs included (§5.1).

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
| Evaluative words ("structural", "cushion", "pressure", …) in fact or comparison sentences, excluding arc and watch | 18 of 330 (5.5%) by hand; the lexicon (`calibration.py`, §3's measure) finds 20 (6.1%), DE's "slightly understated" among them | 7 of 312 (2.2%) | — |
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
| 6 | Calibration: restore the judgement slot, put meaning in judgements, no forecasts in watch items | Prompt | Judgement share outside watch from 0.8% to about 5–9%. Evaluative words in data sentences from 6.1% (the lexicon's count; 5.5% by hand) to 3% or less. About 7 watch forecasts down to about 1. | About 80 cached tokens; output about ±100 tokens (±$0.00006, ±0.3 s) | Medium |
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

Where the built fixes differ from the plan above, after reviews 5 to 9, and what round 2 changed after dev-v5 (last
entry). The code is the harness (`backend/evals/trend_depth/`, README there). The packs are `packs-v2/` (its README) and the candidate prompt is `backend/prompts/trends-depth-analyst-agent.md`. Each figure below is reproduced by the command named beside it, run with the code at this commit; none calls a model. Fix 1's figures of what auto-citation did are those of its last build (e505700), before it was removed.

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

**Fix 7: a growth gap's sign, only where the gate reads it with certainty** (`factcheck.compared_sides`; waves 5
and 6, reviews 8 and 9). A value labelled "revenue growth minus operating-cost growth" has its sign checked only where
the clause compares its two sides in one of these forms. The side named first is the subject: its nouns stand right
before its verb, with at most "of <figure>", its year ("in FY2026"), its figure in brackets ("(3.3%)") and one adverb
("also", "only", "still", "just", "again") between, and never after a preposition. The other side follows the
comparative in the same clause.
- **A move.** A bare side with a rise or fall verb right before the figure, after "has", "have" or "had" or none,
  then "faster", "more", "further", "deeper", "steeper" or their opposites and "than" the other side ("costs fell 1.2pp
  less than revenue": costs minus revenue is +1.2), or the comparative before "than Y by" the figure. The sign is the
  verb's direction times the comparative's.
- **A standing.** A side named with "growth", placed by a verb that only places ("was", "ran", "came in") or by none
  ("with revenue growth 2.1pp ahead of operating-cost growth"), then a position ("ahead of", "behind", "above", "over",
  "short of") or "more than" / "less than"; or an active outpacing verb before "Y by" the figure ("beat", "trailed",
  "lagged"). A side named without "growth" counts only in a year the pack shows the two lines did not both fall
  (`factcheck.both_fell`, from the gap's revenue inputs; both fell in 22 of 144 gap values in each pack version, CVX, DE
  and TGT in FY2025 among them, all three held out; `tests/unit/test_trend_depth_both_fell.py` pins the 22, years in
  which costs fell further than revenue, and a year revenue fell while costs rose); "outgrew" counts in any year.
- **In a certain form the cited gap settles the claim** (review 9). Where the clause compares a cited gap's sides in
  one of these forms, the figure is that gap: the unsigned difference of the two growths cited beside it ("pp
  D373-D358", the same quantity) no longer settles a sign the clause gives the other way. At 09a5b1a all 188 false
  mirrors of today's drivers form (fix 10) with both growths added passed.
- **Every other form is read by magnitude, with no direction verdict:** an appositive after a comma, a participle, the
  passive, a side named as its fall, a move of a growth rate, one side unnamed, a side another metric names. The match
  stays "cited", so the semantic audit sees the stored signed value (view 2).
- **A gap of two levels of one year** (net margin minus operating margin; `factcheck._level_standing`, review 9) has no
  both-fell reading, so it is read as e505700 read it, in any wording: the margin named last before a position after
  the figure, or before an outpacing verb, and not after a preposition, is placed against the other margin after it
  ("held net margin at 31.4%, 6.5pp below the 24.9% operating margin", "left net margin 6.5pp under operating margin",
  the verbless "net margin 5.2pp below operating margin"). Wave 5 had read only a standing whose subject, right before
  its verb, is one margin, so these wordings went unchecked, among them the appositive the frozen prompt's own example
  invites ("..., 6.5pp above operating margin"), which K0 and P read (review 9).
  Two forms stay unread: the passive ("net margin was exceeded by operating margin by 3.4pp"), where "by", not the
  other side, follows the verb, and a move of two levels ("net margin fell 3.4pp more than operating margin"), which
  is not their gap; e505700 read both, and failed the true passive and that move. The gate leaves this gap unsigned:
  `gap_direction` checks its sign by this reading (fix 12).
- **Effect.** On the 127 sentences of reviews 6 to 9 and the candidate prompt's forms (101 of reviews 6 to 8, 26 of
  review 9; the waves' working files, run on both pack versions with the backstops), the 67 true ones all pass; the
  reader before wave 5 failed 20 of reviews 6 to 8's 54, each a repair message that could push the model to the false
  mirror. 11 of the 60 false ones pass by magnitude, the same 11 as in wave 5, among them CVX's "Revenue fell 4.6% in
  FY2025, 1.2pp less than operating costs" (D379 is -1.22pp) and its mirrors on DE and TGT, ORCL's passive and CAT's
  passive margin standing (§4). A generated sweep gives no wrong verdict: every growth gap of every pack in 12
  certain forms (3,360 true sentences and their 3,360 mirrors), and every same-year margin gap in 10 forms, cited on
  packs-v2 and as the two margins on packs (3,020 true sentences and 3,020 mirrors). At 09a5b1a 1,960 of those
  growth-gap mirrors and 1,812 of the margin-gap ones passed.
- **Tests.** `tests/unit/test_trend_depth_factcheck.py` holds 92 certain-form sentences (44 true, 48 false mirrors)
  and 49 read by magnitude, on fixtures of the committed values (`CERTAIN`, `BY_MAGNITUDE`; wave 5 said 74, but
  `CERTAIN` held 69, review 9); a true sentence and its false mirror for every word of every certain form, 192 pairs
  (`WORD_MIRRORS`), with a test that each top-level alternative of each pattern has a word there; and 20 sentences of
  the level reading.
- **On the records.** `python -m evals.trend_depth.replay --base e505700` flips no recorded sentence and moves no pass
  count, with or without the backstops; nor does `--base 09a5b1a`. Over every recorded output (377 outputs, 11,284
  sentences: eval-v1, dev-v3, dev-v4, plant-sem and the gold examples) no probe verdict changes either. One match
  label does against e505700: Sonnet's dev-v4 REGN "operating costs outgrew it by 4.4pp" is now read by magnitude
  ("it" names no side), still verified. Of the 31 recorded same-year margin-gap sentences, no true one is hit and
  every mirror fails (09a5b1a missed 2: dev-v3 DeepSeek REGN, eval-v1 Sonnet NEE).

**Fix 10: the drivers comparison is one form the gate reads with certainty** (wave 6, review 9). The candidate (Q and
C) now says: "Compare operating-cost growth with revenue growth in this one form, using the pack's 'revenue growth
minus operating-cost growth' value where it has one: 'operating costs grew 1.4pp faster than revenue' (or 'slower'),
or, if operating costs fell, 'operating costs fell 2.3pp less than revenue' (or 'more'). Cite the value and print it
without its sign: a negative value means operating costs grew faster, or fell less, than revenue; one that rounds to
0.0pp means they moved in line with it. Where the pack also gives operating-cost growth, you may add it after the
comparison ('..., at 7.2%'). Write the comparison in no other form."
- **Why this form.** It is fix 7's move, whose sign is the verb's direction times the comparative's. "Grew ...
  faster" and "fell ... less" both put costs ahead of revenue, so a wrong choice of verb (costs that fell said to
  have "grown ... slower") still gives the right sign: only the English suffers, never the figure (§4). No committed
  pack prints a gap of 1.4 or 2.3pp, or a revenue or operating-cost growth of 7.2%, so no example is a company's.
- **Verified on every pack** (`tests/unit/test_trend_depth_prompt_examples.py` reads the form from the prompt and runs
  it on all 40 packs, 658 sentences; wave 6's working table runs `check` with and without the backstops). On the 17
  packs with a gap value (COP, JPM and USB have none), in both versions and every year, the form as prescribed passes
  282 of 282 and its mirror (the comparative flipped) fails 282 of 282; with the pack's operating-cost growth added,
  188 of 188 and 188 of 188, and with both growths added, the same. Six pack-years print 0.0pp and state no sign (COST
  FY2018 and FY2022 and SNAP FY2023, in each version). In the latest year, the same on both versions, operating costs
  grew slower than revenue at AMD, COST, DUK, MSFT, NVDA, RIVN and SNAP, grew faster at CAT, NEE, ORCL, PG and REGN,
  fell less at CVX, DE and TGT, and fell more at KO and VRTX.
- **Tried and withdrawn: both growths** (09a5b1a). After wave 5 the candidate asked for both growths instead, each
  with its own figure and direction word, both cited, and not the gap ("revenue fell 9.4% while operating costs fell
  6.1%"). Four packs carry no operating-cost growth, in either version: PG and COST (development) and KO and TGT (held
  out), whose gap is built from revenue less operating income. There the true sentence failed the gate ("matches
  nothing the sentence cites"), a repair K0 never pays, while a cost-of-revenue or SG&A growth said as operating costs
  passed. Its premise, that each growth's direction word is checked against the cited growth, held only where the
  pack has that growth.
- **Before that,** the candidate at e505700 said "Compare operating-cost growth with revenue growth, each with its own
  direction (rose / fell); when both fell, say which fell more", which invited the appositive "Revenue fell 4.6% in
  FY2025, 1.2pp less than operating costs", whose false mirror fix 7 reads by magnitude only (§4).
- **The frozen prompt (K0, P) keeps its own wording,** "(operating leverage: incremental margin, operating-cost growth
  against revenue growth)" (`prompts/frozen-d558d371.md`), beside its rule that a difference "needs both figures cited
  in that sentence". A gap mirror there fails the gate in a certain form; in any other form it passes, for every arm,
  and only the Opus audit of K0 measures it, a flag on it counting even where the sentence cites the gap with both
  growths, K0's recorded form (fix 14). P has no audit, so a P gap mirror outside the certain forms is not measured.

**Fix 8: debt and cash breaks in pack version 2** (`packs-v2/README.md`).
- **Withheld, not dropped.** Every ID built on a broken year stays in the pack, so a version-1 output still checks against it, but the render does not show it (`withheld`).
- **Debt breaks.** These are found by line tests:
  - `debt_break`: the long-term debt line is missing or zero while debt is still evident;
  - a debt onset: a smaller debt line first appears and total debt jumps while interest expense does not follow. DE's FY2016–FY2019 total debt is long-term debt only;
  - a debt double count (review 8): the long-term line already holds the current line total debt adds to it. The filer's own figure decides: its noncurrent debt and leases, less the noncurrent leases its same 10-K reports, equal the long-term line less the current line within a quarter of the current line (had the long-term line left the current portion out, the two would differ by the whole current line). Only a long-term tag that may hold its current portion is read, beside a current line above 1% of it. It names TGT FY2016–FY2018 as a `debt_break` check and withholds TGT's total debt and its growth there (D14, D33, D82; D62, D109, D156; its net cash was already withheld). Among the peers of the 20 it names BA, PH and UPS (and, outside them, T in the media group, which no evaluation company reads), so CAT's checked industrials median leaves out BA FY2025, PH FY2026 and UPS FY2025 and moves from -38.0% (n=6) to -59.4% (n=3).
- **The implied-rate test detects no break.** It fires on none of the 20 outside the break spans, and inside them it misses most first years.
- **Liquidity breaks** (`liquidity_break`): a cash or investment line missing in one year (COP, MSFT, NVDA, ORCL), or short-term investments already inside cash (TGT).
- **Checked peer ranks.** A version-1 net-cash peer rank or median built on a peer's broken year is withheld (`peer_break`). Where three or more peers pass the same tests it is replaced by a checked rank under a new ID: PG, CAT, COST, AMD, DUK and NEE; RIVN keeps none.
- **A new data check, `unmapped_line`** (review 7). It names a line the filer reports and the pack sums nowhere, at 10% or more of the total it is missing from, in a year no break check of the same kind (debt or cash) names: CAT's long-term debt due within one year ($7.1 billion at FY2025, so its net debt reads $26.2 billion [D456] against $33.4 billion), and KO's cash and investments total above the pack's (FY2016–FY2017, FY2021–FY2025; FY2024–FY2025 are debt-break years, whose cash and investments [D440] stay shown).
  - It withholds nothing. Lines it cannot see are listed in the packs-v2 README under "Not detected": TGT's FY2019 double count, AMD's FY2023 and FY2025 current portion tagged twice, CVX's FY2016–FY2017 short-term debt that holds its current maturities and its FY2020–FY2021 long-term line, COP's FY2017–FY2020 long-term line above its own total, and PG's available-for-sale securities, among others. Every arm sees them alike, and the broken-net-cash measure does not count them (§4).
  - The broken-net-cash measure does not count these lines. P and C see the check; K0 and Q do not.
- **ORCL's FY2022 long-term debt line, reported as zero [F185, X213], is withheld** (review 7).

**Fix 12: two backstops beyond the plan** (`probes.py`; each a gate failure under `--pipeline v2`).
- **`gap_direction`.** Net margin said to be above or below operating margin against the sign of the same year's gap: the cited "net margin minus operating margin" value, or the difference of the two margins the gate matched.
  - It reads a gap of two levels as the gate does (`factcheck.compared_sides`, `_level_standing`, fix 7; review 9): the margin named last before a position after the figure, or before an outpacing verb, against the other margin after it, in any wording, as e505700 read it ("held net margin at 31.4%, 6.5pp below the 24.9% operating margin", "left net margin 6.5pp under operating margin", "Net margin of 13.1% trailed operating margin by 3.4pp"). The passive ("net margin was exceeded by operating margin by 3.4pp") and a move of two levels ("net margin fell 3.4pp more than operating margin") are left alone. Wave 5's narrowing to a margin named as the subject had let the false mirrors of the other wordings pass, among them the appositive the frozen prompt's example invites.
  - Review 9's 28 wordings on both pack versions, each true and mirrored (112 verdicts), are all right (09a5b1a passed 44 mirrors). Of the 31 recorded same-year gap sentences no true one is hit and all 31 mirrors are caught (09a5b1a 29).
  - The gate reads no direction into a same-year gap, so this is its sign check on either pack version. A sign error on packs-v2's cited gap therefore falls in the same row for P and C as for K0.
  - It finds no hit in eval-v1.
- **`broken_debt`.** A figure version 2 withholds, cited by its ID, or the same figure rebuilt from the lines version 2 shows: a line of a break year under a total's name, or beside a total of another year. Plain "debt" is the total, but debt named by a maturity after it ("debt due within one year", "debt maturities", "$1.0 billion of debt matured") is that line, and so is a figure said to fall due ("Of Deere's debt, $13.8 billion falls due within a year"; review 8), unless the sentence names an explicit total as the figure's own ("Total debt of $13.8 billion is due within one year", "Net debt of $5.5 billion matures by FY2026" state the total; review 9), not as the whole it is part of ("Of Deere's total debt, $13.8 billion falls due" is the line). In a double count only a figure on both lines is broken, their sum whatever it is called: TGT's cash with its short-term investments, and TGT's FY2016–FY2018 long-term line with its current line, where the long-term line alone is the right total under any name ("Debt was $11.7 billion in FY2016 [X175]" passes; wave 5's integration, since without it that check failed this true sentence in P's and C's gate, with a repair message pointing at the double count). It is excused only by a disclosure in a clause about debt or cash (`probes.discloses`, the one rule that the gate, the stated sentences and the analysis's state all read): the data checks' own words, so that an echo of any clause of a packs-v2 debt or liquidity check discloses its break (`_CHECK_WORDS`: "not reported", "reported as zero", "omit them", "this pack leaves them out", "already inside long-term debt", TGT's "tags ... together" and "the long-term line less the current portion", "count it twice"; review 9), or the break said plainly of the data about the line, as the candidate prompt asks: "long-term debt is absent from the pack", "disappears from the data", "has no value in the pack", "has no reported value", "no long-term debt reported", "goes unreported", "no long-term debt figure", "not available", "ignores long-term debt", "the pack carries no long-term debt", "which the pack drops", "is not in the data", "carries FY2025 short-term investments but none for FY2026" (reviews 8 and 9). The same words about another line or about the company disclose nothing: "with buybacks absent", "as Coca-Cola carries no long-term debt", and "as long-term debt disappeared from the balance sheet", a misread deleveraging that review 8's forms had counted as a disclosure. So, since wave 6, "absent", "gone", "disappears" or "has no value" with no word of the data ("long-term debt has no value after FY2023") disclose nothing either: the company may be the one without debt.
  - The gate's backstop reads the arm's own pack, so it fires only for P and C, as `packs/` records no break.
  - The report's measure reads `packs-v2/`'s breaks for every arm.
  - Review 7's 42 broken sentences are all caught. Its 3 false failures, and 59 correct sentences on the 9 break companies' packs, pass (re-run on wave 5's code and packs). Review 8's six sentences on debt that falls due (DE, CVX, COP) pass, and so do its plain disclosures, except "has no value" with no word of the data (wave 6).
  - Review 9's 44 debt and disclosure cases are all right (27 wrong at 09a5b1a, 23 at e505700): the misread deleveraging counts again on KO, CVX, DE and COP, a total that falls due counts on DE, and every clause of every packs-v2 debt or liquidity check (29 clauses on 9 companies) discloses, on its own and echoed after its company's broken figure.
  - Over every recorded output, wave 5 moves no `broken_debt` hit; one sentence's disclosure changes, dev-v3 Sonnet NVDA's "the pack carries FY2025 short-term investments [X188] but none for FY2026", which states no broken figure. Wave 6 moves no gate, probe, `broken_debt` or disclosure verdict against 09a5b1a.
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
- **One quantity, one flag label** (review 8 measures [0]; review 9 measures [0], arm-fairness [3]). `classify_flag` counts a mismatch flag as ambiguous only when two quantities with different labels match the figure. Two candidates are one quantity only by the pack's own record of how a value is built, with the same unit and signed value, never by the value alone:
  - a window low, high or median is the point of its series it equals (`_selected`): packs-v2's appended operating cash flow / net income window low [D721] is COST's FY2022 value [D225];
  - a cited value is the gate's calculation over what the pack computes it from (`_operands`, `_computed_as`): its inputs (packs-v2's same-year gap [D693] is PG's net margin [F50] less its operating margin [F30]); for the growth gap, the two growths where the pack holds the operating-expense growth (95 of 144 gaps in each version; its recorded inputs are revenue and operating income, its fallback basis), so CVX's [D379] is the gate's "pp D358-D373"; for a metrics-table value, the series its formula names in its period, or, for a CAGR, its series at the window's two ends (AMD's [F231] is "CAGR F1->F10 over 9y");
  - or the inverse of a sum or difference it is an operand of: ORCL's operating cash flow [F84] is its free cash flow [F104] plus its capex [F94]. This one goes beyond what review 9 named; without it a flag on ORCL's eval-v1 sentence of the three figures would count on free cash flow but not on operating cash flow.

  Before, a sentence that also cited what a figure is computed from shielded every flag on the figure, while the same sentence citing less counted: K0's recorded gap sentence with both growths (eval-v1 DeepSeek CVX "...outran cost reduction by 1.2pp [D373][D358][D379]") and its false mirror, a CAGR cited with its two levels, a margin with its numerator and denominator, and C's year value beside the window low packs-v2 appends; wave 5 had merged only a cited value into a calculation over exactly its recorded inputs. Different metrics that print one number stay two labels: USB's two 2.8% CAGRs, VRTX's buybacks and its buybacks plus dividends (it pays none), MSFT's bridge residual, PG's and TGT's gap against cost-of-revenue growth. Of the 146 recorded mismatch flags one changes class: plant-sem's planted relabel at REGN, "Operating cash flow compounded at 12.8% a year" [F1][F10][F198], flagged by V4 Pro, from ambiguous to substantive; no eval-v1 flag moves. Over every recorded output 315 of 9,755 verified claims would class differently if flagged, all from ambiguous to substantive (eval-v1 DeepSeek's ambiguous claims 163 to 114 of 1,459, Sonnet's 157 to 118 of 1,458).
- **No record carries a view yet.** Step 0's re-audit is the first under view 2.

**Round 2: from dev-v5's first-try failures** (after §3 step 2's first development round; from 17c5d4b, then narrowed
after an independent verification against 17c5d4b). Every first-try failure of dev-v5 (`dev-v5-r1` and `dev-v5-r2`,
all four arms: the gate with its backstops on the model's own first output) was read by hand, 116 in all: 10 false
positives of the gate, 63 induced by a prompt line, 43 true errors. C holds 23 of them, in 13 failing analyses (5 in
run 1, 8 in run 2): 3 false positives, 16 prompt-induced, 4 true errors. Two of the 116 (P's COST, Q's NVDA) are
retyped by `retype.first_pass` and never sent a repair. The round adds six prompt lines to the candidate and one gate
rule, G1. It first built seven gate, probe and retype rules; two independent verifications found six of them passing
false sentences 17c5d4b catches or failing true ones it passes (five in the first, G7 in the second), and those six were
withdrawn rather than narrowed again. The true errors keep their repair. The frozen prompt is not edited, so K0 and P are unchanged.
- **The candidate's new lines** (sha256 `05f799a8…` → `fc5b808c…`, about 140 words longer; every section count is
  unchanged, and `copied()` finds no new example figure in any committed pack):
  - **P1, net debt in one form** (38 rows, 13 of C's 23: CAT, NEE ×3 and PG ×2 in run 1; CAT, COP, NEE ×2, PG ×2 and
    SNAP in run 2). Every R2a hit was the old line's two examples merged into "net debt of $X, or -Y% of revenue". The
    line now gives one form: the amount as net debt with no sign, and every share of revenue, window level or peer
    median as net cash with its sign ("net debt of $12.6 billion, net cash of -27.4% of revenue against a -19.2% peer
    median"); a minus sign never follows "net debt", and a watch item's metric is "net cash as a share of revenue".
    `tests/unit/test_trend_depth_prompt_examples.py` reads the form from the prompt and runs it on every committed pack
    whose latest net cash is shown (18 of `packs/` and 17 of `packs-v2/`: JPM and USB have none, version 2 withholds
    TGT's): the form and the watch item pass the gate with and without the backstops, the merged form fails on R2a on
    all 8 and 10 packs in net debt, and the example's three figures are no pack's net cash.
  - **P2, no operating-cost comparison without the gap** (rows 33, 50, 88 and 105, all COP; C's 50 and 105): "Where
    the pack has no 'revenue growth minus operating-cost growth' value, write no operating-cost comparison." Without
    the value C filled the drivers slot with cost-of-revenue growth called operating costs (and, in run 2, cut 6.689 to
    6.6pp). Only COP, JPM and USB lack the value, in both versions; the drivers form of the other 17 is unchanged (its
    test pins the three).
  - **P3, a contribution with no passage is a comparison** (rows 12, 23, 44, 67, 84, 100 and 114, all REGN's
    REGEN-COV; C's 114): "A margin bridge, or a product's or segment's contribution to growth, with no passage is a
    comparison." It is the only fix for all seven: G6, the code backstop built for six of them, was withdrawn (below),
    and Q's row 44 keeps an explanatory "as" clause no retyping would reach.
  - **P4, rounded, never cut** (JPM's truncated revenue in K0, P and Q: rows 3, 16, 37 and 91; none of C's):
    "rounded, never cut ('$46,782 million' is '$46.8 billion')".
  - **Depth: give the stated cause.** In a section that asks for causes, where a passage that states the cause of a
    move for that line and year explains a move the analysis describes, the line asks for that cause, cited in that
    sentence. The judge gave K0 depth over C in 11 of 20 pairs (4 in run 1, 7 in run 2; §3 allows 5), and most of
    those rationales credit K0's causes or drivers (NVDA's H20 charge, NEE's NEER, REGN's mix inversion, COST's
    product mix); C wrote 5.8 cause sentences per analysis in both runs, under the guard of 6 (K0 6.2–7.3, Q
    5.5–5.9).
    The line is tied to "such a passage", and the sentence after it still says to describe a move no passage explains
    and not to guess why, so it invites no cause a passage does not state.
  - **Above or below a reference, by its numbers.** "Before you write that a value is above or below a reference
    level (a window median, high or low, or a peer median), compare the two numbers with their signs, and write the
    smaller as below the larger, however close they are ('1.48x, below the 1.52x window median')." Opus found C's COST
    in both runs ("1.71x net income in FY2026, above the 1.75x window median's level") and its PG in run 1 ("1.22x net
    income, above the 1.25x window median only marginally below it"); the judge also caught K0's REGN in run 2 ("0.91x
    'below' a 0.88x median"). No gate check reads the side: R1 checks only whose reference it is.
- **The gate rule kept** (`tests/unit/test_trend_depth_dev_v5_rules.py`: its recorded sentence, its false mirrors and a
  true sentence for each word it reads, on the committed packs; and, for each guard, a true sentence and a false mirror
  whose verdicts flip when the test takes the guard out):

  | Rule | Where | Rows | Recorded sentence, now passing | Mirror that fails (passed before where marked) |
  |---|---|---|---|---|
  | G1: a figure's own movement noun after it, after "a" or "an", overrides a direction word before it, which belongs to another noun. Read only where such a word stands before (unrestricted, it failed eval-v1 Haiku CVX's true "…from 58.8%, a 1.6pp gain"), only for a percentage, and with no stop word ("despite", "in", "of", …) between the figure and the noun | `factcheck._direction` | 49 (C) | "Rising debt alongside a 14.7% operating-income decline is the balance-sheet pressure to watch [R1][D464]" | "Falling debt alongside a 14.7% operating-income rise" (passed before); "…a 14.7% operating-income rise" |

  G1's percentage guard is this round's narrowing after the verification: as first built, G1 read a pp figure's noun
  too, so it failed KO's true "Gross margin improved with a 0.6pp decline in the cost-of-revenue share in FY2025
  [D462]" (the verifier's) and "Operating margin widened with a 0.6pp drop in the cost-of-revenue share [D475]", which
  17c5d4b passes: a pp figure may be a cost line's share move cited as the margin's change, whose sign is the inverse.

  **Not built:** G5 (a net-cash label between a level and its reference governs the reference; row 80, P's NEE),
  low priority, as P1 removes the form; the sentence still fails R2a. Nor, as the reading advised against them, the
  "from X to Y in FYn" chain (13, 85, both false), "on" and "over" as base words (69), ratios built from a passage's
  figures (14), skipping an "as" clause in the retyping (17, frozen prompt only), or any citing by a neighbouring
  sentence or by code.
- **Withdrawn after verification** (each function back to its 17c5d4b text, its tests removed; the verifier's
  counter-example, which 17c5d4b gets right and the build got wrong):
  - **G2**, a position against the year before right after a change gives its direction (`factcheck._direction`; row
    51, C's COP): it read "over" as "above" after a fall verb, so it failed true sentences: KO "Operating margin fell
    3.5pp over the prior year to 21.2% in FY2024 [D413][F49]".
  - **G3**, "collapse", "plummet" and "tumble" as fall words (`probes._FALL_WORDS`; row 72, P's CAT): U1 reads a fall
    word to the end of the sentence, so another figure's fall spared an unsigned one: CAT "…a 22.4% rebound in FY2020
    to $41.7 billion [F5][D198] was followed by a 22.1% collapse in FY2021 [F6][D251]" passed.
  - **G4(a)**, a bare from-level may be the year before's (`factcheck.bind_periods`; rows 36 and 109, Q's COST and C's
    NEE): its source-verb guard read only the word before "from", so KO "In FY2025 the margin gain came largely from
    1.5pp of cost of revenue [D425]", FY2024's effect, passed.
  - **G4(b)**, a year before "and", "but", "while" or "whereas" binds nothing forward (`factcheck.bind_periods`; row
    24, P's REGN): it untied figures the year governs: REGN "R&D reached 40.8% of revenue, the highest since FY2016 and
    above that year's 32.6% [D420][D72]" (FY2018's 32.6%; FY2016's is 42.2%) passed.
  - **G6**, REGEN-COV's contribution words as figure talk (`retype._FIGURE_TALK`; rows 114 (C), 12, 23, 67, 84 and
    100): "sale" also covers a divestiture, so a cause with no passage was retyped to a comparison and passed: REGN "The
    FY2022 reversal came from the sale of REGEN-COV [D585]".
  - **G7**, a cost line's operating-margin effect said through the line's own move reads the inverse of the direction
    word (`factcheck.line_moved`; row 25, P's SNAP; withdrawn after the second verification): it inverted whatever
    direction word stood in the figure's clause once the line's name and a move verb appeared there, the margin's own
    word included, so it failed true sentences and passed false ones: VRTX "SG&A decreased operating margin by 1.3pp
    in FY2025 [D467]" (D467 = -1.32) failed, and "SG&A increased operating margin by 1.3pp in FY2025 [D467]" passed.
    None of the 24 such sentences is in the records, but the models write that transitive shape.

  One of their tests stays, as it also pins G1: CAT's false "a 22.4% rebound in FY2020" still fails U1 (G1 reads no
  noun with no direction word before). The three G4(a) test cases the verification found unable to fail went with
  G4(a).
- **Guard mutations.** The first build said a hand mutation of each rule and of each of its guards failed a test.
  The verification found that wrong: G1's article guard, its stop-word guard and its noun "gain" (with G7's clause
  split and guards of the other withdrawn rules) survived every mutation it ran. Each of G1's three, and its
  percentage guard, now has a true sentence and a false mirror in `test_each_guard_decides_its_sentences`, which also
  runs them with the guard taken out, and every hand mutation of G1, P1 and R2a (each rule off, each guard off or
  loosened, each noun dropped, the prompt's form reverted or merged) fails at least one test.
- **On the records** (`python -m evals.trend_depth.replay --base 17c5d4b`, with its default labels and with every
  label; and a replay of the gate with and without the backstops, every probe, `broken_debt` with the packs-v2
  reference and `retype.first_pass`, at 17c5d4b and now, over every recorded output: all nine labels under `runs/`,
  finals, first outputs and recorded first passes, and the gold examples, 472 outputs and 6,148 distinct sentences):
  - 1 sentence goes from failing to passing, true, and nothing else moves: C's CAT in dev-v5-r1, "Rising debt
    alongside a 14.7% operating-income decline…" (G1: D464 is -14.7%; the rise is debt's).
  - Nothing passing starts failing. No probe, `broken_debt`, disclosure or retyping verdict moves; every planted
    sentence of `plant-sem` keeps its verdict, and the gold examples pass. `bind_periods` binds every claim of every
    recorded sentence as at 17c5d4b, and `probes.py` and `retype.py` are 17c5d4b's files.
  - One analysis moves, from failing to passing: C's CAT in run 1 as its final output (its repair had kept the false
    positive); its first output passes the gate alone but still fails R2a (P1's row). C's first passes through the
    code step stay at 5 and 2 of 10.
- **What it can do for C.** On C's recorded first outputs, with the new lines obeyed and G1 in, 8 of 10 would
  pass in run 1 and 6 of 10 in run 2 (14 of 20, 70%). The 6 left: the 4 true errors the repair fixes (SNAP's "That
  -10.1%" without D400 in run 1; COP's D342 and COST's D238 uncited, and JPM's "higher rates lifted interest income"
  with no passage, in run 2), and the 2 false positives of withdrawn rules, which the repair rewrites (COP's "net margin
  of 15.4% sat 3.3pp below the prior year", a U1 hit, run 1, G2's; NEE's "D&A rose to 25.5% of revenue from 23.2%",
  run 2, G4(a)'s). A new run regenerates every sentence, so this is a ceiling for these outputs, below §3's 85%.
- **Limits left** (each checked on the committed packs, as at 17c5d4b):
  - G1 reads no pp figure's noun: "Higher debt came with a 3.7pp operating-margin decline in FY2025 [D476]" (CAT)
    fails.
  - G1 reads six words back, as the gate does: MSFT's false "Rising free cash flow came alongside a 20.8%
    operating-income decline [D473]" passes, as "Rising" is the seventh word.
  - A margin bridge said through a cost line's own move, citing the line's margin effect, fails as at 17c5d4b: P's
    SNAP "Cost of revenue fell 1.1pp to 45.0% of revenue…" [D431] (+1.14, the share fell) reads "fell" as the
    effect's direction. The candidate asks for bridges, so C may pay a repair for one.
  - The withdrawn rules' sentences fail as at 17c5d4b: a from-level bound to its sentence's year ("as D&A rose to
    25.5% of revenue from 23.2%" in FY2025), a change placed against the year before (a U1 hit), "a 22.4% collapse"
    (U1), a year before "and" that binds the figure after it, and REGEN-COV's contributions typed as causes. A
    from-level that no year binds passes ("In FY2025 operating margin rose to 28.7% from 24.7%", KO, 24.7% FY2023's).

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
| S, T (not built) | Fixed | Fixed; S would write "text" before "type", T would run at temperature 0 | Left out of this experiment: `providers.py` has no such arm (§2, "Tested separately") |

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
| Real mislabels per 1,000 verified claims | Distinct sentences, over the outputs Opus read (K0 and C): probe hits R1, R2a, R2c and R3 plus Opus substantive flags, read by hand; a flag on a figure cited beside what the pack computes it from counts as on the figure alone (§2, "As built", fix 14). A sentence stating broken net cash is counted there instead; U1, unitless dollars and the margin-gap direction have rows of their own | About 8.9 (13 sentences in 1,459 claims after reading; 15 before, 10.3). §1.2's 14 included TGT's net-debt sentence, now counted under broken net cash. These are view-1 audits; step 0 gives view 2's | About 0.7 (1 after reading; 5 before, 3.4) | 3.5 or less in each run |
| Judgement share, outside watch | Sentence types | 0.8% (4 of 530) | 3.8% (20 of 527) | 3–12% |
| Evaluative words in fact and comparison sentences | Lexicon (`backend/evals/trend_depth/calibration.py`), outside arc and watch | 6.1% (20 of 330) | 2.2% (7 of 312) | 3% or less |
| Watch items with forecast wording | Lexicon, read by hand | 11 of 60 by the lexicon; about 7 after reading (§1.3) | 1 of 60 | 2 or fewer per 60 |
| Unsigned falls | U1 | 1 | 0 | 0 (guard) |
| Unitless dollars; net margin's direction against operating margin | Probes `unitless_dollars`; `gap_direction`, the sign check on a same-year margin gap, cited or as two margins' difference, in any wording that places one margin against the other (the passive and a move of two levels aside; §2, "As built", fix 12). The gate leaves that gap unsigned, so a sign error on it lands in this row for every arm | 2 (COST); 0 | 0; 0 | — |
| Broken net cash stated as fact | Analyses of a company whose `packs-v2/` pack names a debt or liquidity break (COP, CVX, DE, KO, ORCL, TGT, USB; MSFT and NVDA liquidity only). Its breaks are read for every arm: a withheld figure cited by its ID, or rebuilt from the lines `packs-v2/` still shows (a line of a break year under a total's name, plain "debt" included but not debt named by a maturity, nor a figure said to fall due unless a total is named as its own, or beside a total of another year; in a double count, TGT's cash with its short-term investments and its FY2016–FY2018 long-term line with its current line, only the two lines' sum). A sentence discloses a break only in a clause about debt or cash, in the data checks' own words or the break said plainly of the data about its line, never of the company (`probes.discloses`). The lines version 2 names only in an `unmapped_line` check (CAT's current portion of long-term debt, KO's investments), and those no test names (`packs-v2/README.md`, "Not detected"), are outside this measure | 6 of 9 stated as fact (debt break 4 of 7: COP, CVX, DE, KO; liquidity break 2 of 5: NVDA, TGT); 1 disclosed (USB) | 2 of 9 stated as fact (debt break 1 of 7: DE; liquidity break 1 of 5: TGT); 5 disclosed | 0 stated as fact |
| Sentences stating a broken figure | The same, each sentence that states one without disclosing the break in that sentence, whatever the analysis says elsewhere | 13 | 6 | 0 |
| Version-1 peer ranks on a peer's broken year | `peer_break`: only an arm reading `packs/` can cite one, so informational | 7 sentences in 7 analyses | 7 in 7 | — |
| Cause support | Opus causes audit | 76% / 23% / 1% | 76% / 22% / 1% | Guard: at least 72% supported, at most 2% unsupported, at least 6 cause sentences per analysis |
| Judge, C against K0 | Opus, both orders must agree. The report prints each criterion, and the pairs whose grounding and calibration a side each won or tied, per run and summed | Against Sonnet under Opus, for reference: grounding won or tied in 2 of 20, calibration in 1, both in the same pair in 1; depth lost in 5. (eval-v1's panel, Opus and V4 Pro counted only where they agree with Gemma on 5 pairs, printed 17, 18 and 16, depth lost 1; its ties are mostly the two judges disagreeing, so it is not this row's basis) | Against DeepSeek under Opus: grounding 19, calibration 20, both 19; depth lost in 2 (the panel: both in 20 of 20) | C wins or ties both grounding and calibration in the same pair on at least 12 of 20 per split (the joint reading; each criterion apart is printed beside it); loses depth on no more than 5 |
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
flag merge (none of 146 recorded flags changed class then) move no recorded verdict, and the removal of auto-citation
touches no baseline record, as eval-v1 and dev-v4 ran version 1 (the report's own-ID row went with it).

Wave 6 (review 9) changes no baseline. The eval-v1 and dev-v4 reports print a `summary.json` identical, byte for
byte, to wave 5's; only the report's wording of the ambiguous class changes. The gate's certain forms (the subject's
year or bracketed figure, a verbless standing, a cited gap that settles a certain form), its level reading, the
disclosures tied to the data and the total that falls due move no gate, probe, `broken_debt` or disclosure verdict on
any recorded output (377 outputs, 11,284 sentences). Of the 146 recorded mismatch flags the one that changes class
(§2, "As built", fix 14) is plant-sem's, under the V4 Pro auditor, which no row reads. `repair_replay --dry-run` lists
the same 21 cases, 11 of them eval-v1's, and `python -m evals.trend_depth.retype` prints the same counts (eval-v1:
20 first passes, 12 failing, 11 after retyping, 6 and 5 by the gate alone; dev-v4: 5, 4, 4, 4, 4).

Round 2 (§2, "As built") changes no baseline. `report --label eval-v1 --systems deepseek-flash,claude-sonnet-5-5`
and `report --label dev-v4 --systems deepseek-flash` print a `summary.json` and a `REPORT.md` identical, byte for
byte, to 17c5d4b's: the one sentence the round turns to passing is C's in dev-v5, and `repair_replay --dry-run` and
`python -m evals.trend_depth.retype` print the same as at 17c5d4b. Development rows move in run 1 only, as the round
reads dev-v5's first outputs: in `report --labels dev-v5-r1,dev-v5-r2`, first-try gate failures per analysis fall for C
from 0.30 to 0.20 (CAT), and C's verified claims go from 715 to 716 (CAT's 14.7%), which leaves both mislabel rows where
they were.
The pass row is the record as run, so it does not move.

**The pull request's review (Codex, after the results).** Its fixes to the harness move no reported verdict:
- **The judge's forfeit:** no recorded pair had a failed generation.
- **Partial audits:** none of the 1,191 recorded audits holds an unlabelled item.
- **The production arm's ingest:** the recorded current-arm outputs (dev-v3 and eval-v1) were generated in a store
  that already held the companies, so the fix changes none of them; no run since has generated the arm.
- **Cut Claude attempts' cost:** no recorded call used the Claude API.
- **Overload retries' latency:** the records cannot show whether any call retried (§5.7).
- **Worded multiples beside figures** ("more than doubled to $1.2 billion"). The gate now reads these, and a
  passage's own "doubled" licenses only a sentence's "doubled", never a ratio or a bare number (no passage in
  `packs/` or `packs-v2/` holds one). A replay of every recorded output, first and final, with and without
  backstops, changes no verdict and no failure. Four sentences gain one verified claim each: dev-v4 K0's SNAP
  ("revenue more than doubled in FY2017"), eval-v1 Haiku 5.5 low's SNAP ("operating loss nearly doubled"), eval-v2-r1
  K0's CVX ("interest expense more than doubled") and eval-v2-r1 C's AMD (its first output only). A report re-run
  today prints one more verified claim for two of them:
  - eval-v2-r1 K0: 752 becomes 753 (CVX), so the held-out pool reads 1,479 and all six runs 4,442. Every rate in §5
    rounds the same: 1.3, 3.4 and 4.5;
  - eval-v1 Haiku 5.5 (low effort): 677 becomes 678 on the development half (its rate there prints 2.9, not 3.0),
    and 1,356 becomes 1,357 in all.

  C's AMD sentence is in a first output, which the report's verified claims do not count. dev-v4's re-run report also
  counts one more claim (SNAP's), which moves none of the rows this section takes from it. The committed reports keep
  the earlier counts, and no auditor read the added claims.

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
| Step 2: 4 arms × 2 runs × 10 companies (80 analyses) | About $0.57 | — |
| Step 2: audits of K0 and C (40 outputs) and the judge, C against K0 (20 pairs) | — | $7.8 + $5.1 |
| Optional second development round (20 analyses, audits, judge) | $0.15 | $8.9 |
| Step 3: K0 and C × 2 runs × 10 held-out (40 analyses) | $0.30 | — |
| Step 3: audits (30–40 outputs), judge (20 pairs), optional C against Sonnet (10 pairs) | — | $5.9–7.8 + $5.1 + $2.5 |
| Step 3: C at peak hours, one held-out run for latency (10 analyses) | About $0.14 (peak price) | — |
| V4 Pro second auditor, all audited outputs | About $0.8 | — |
| **Total** | **About $2.1–2.5**: $2.07 without the optional round, $2.52 with it and step 1 at its high estimate; at most about $4.3 with step 1 at the dry run's ceiling. Every row but the peak run is off-peak, and a row run at peak doubles | **About $30–43**: $29.9 without the optional items and with step 3's fewest audits, $43.2 with all of them |

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
- **Growth-gap mirrors the gate passes by magnitude** (fix 7). A false sign in a form the gate does not read with certainty passes it, for every arm alike: "Revenue fell 4.6% in FY2025, 1.2pp less than operating costs" on CVX (the gap is -1.22pp), and its mirrors on DE and TGT, all held out. The candidate prompt's drivers wording at e505700 ("when both fell, say which fell more") invited that appositive; the candidate now prescribes fix 7's move, which the gate reads with certainty (As built, fix 10). The frozen prompt never had that wording: it asks only for "operating-cost growth against revenue growth", so K0 and P may write the gap in any form. Only the Opus audit of K0 and C, which sees the signed value under view 2, can catch such a mirror, and since wave 6 a flag on it counts even where the sentence also cites both growths, K0's recorded form (fix 14); P and Q have no audit, so their mirrors outside the certain forms are not measured. Narrowed in wave 6: a false sign in a certain form now fails even when the sentence also cites both growth rates, whose unsigned difference used to settle the claim; outside the certain forms the gap is read by magnitude either way.
- **Lines moving opposite ways** (fix 10). Where revenue rose and operating costs fell (KO FY2025, VRTX FY2025), the prescribed true sentence reads "operating costs fell 9.7pp more than revenue", odd English beside a revenue that grew. "Grew 9.7pp slower" also passes: its verb is wrong for costs that fell, but no figure or sign is. A wrong sign fails in either wording. The judge may mark the English down.
- **Plain disclosures that fail closed** (fix 12, wave 6). "Long-term debt has no value after FY2023" or "is absent after FY2023", with no word of the data, no longer disclose a break, since the same words describe a company that repaid its debt: P and C get a repair for such a sentence, and the measure counts it as stated. The words the checks themselves use, and any plain form that names the data ("absent from the pack", "has no reported value"), still disclose.
- **Known, not fixed (older than e505700).** "$13.8 billion of total debt is due within a year", the total named after the figure as the whole, still counts as a broken figure. The generic words "missing", "unavailable" and "drops out" still disclose without a word of the data, so "went missing from the balance sheet" excuses a broken figure.
- **Production data.** Long-term debt mapping breaks in 6 of 20 packs, and TGT's long-term tag already holds the current portion its total debt adds (FY2016–FY2018, which version 2 names). It probably also affects peers' net cash, the peer medians and the production metrics table. Version 2 also finds lines the pack never sums:
  - CAT's long-term debt due within one year and KO's short-term investments (`unmapped_line`);
  - others no test sees, among those `packs-v2/README.md` lists under "Not detected": TGT's FY2019 double count, AMD's FY2023 and FY2025 current portion counted twice (its FY2025 net cash reads $6,456m against $7,330m), CVX's and COP's long-term lines (CVX FY2016–FY2017 and FY2020–FY2021, COP FY2017–FY2020), and PG's available-for-sale securities. Every arm sees them alike, and the broken-net-cash measure does not count them. A test that reads one tag's meaning fails on another filer, so only the shape the filer's own figures decide is named.

  ORCL's FY2022 long-term debt reads zero. This is a separate production decision.
- **The DeepSeek service.**
  - The model may change silently under the same alias.
  - Peak hours double the price (about $0.014 per analysis).
  - Latency varies with load: measure p90 at production hours before launch.
- **Limits recorded at the final review (review 10), not fixed before the experiment.** None changes a verdict on a recorded output or a prescribed form.
  - Two margin-gap wordings are read by magnitude only, beside the passive and a move of two levels: the outpacing form with the other margin's figure after it ("operating margin of 16.5% exceeded net margin of 13.1% by 3.4pp").
  - "has not been reported" does not disclose a break, while "was/is not reported" does; P and C would pay a repair for it.
  - Some rules have no test that pins them: the level-gap reading's "margin named last", a few wave-6 subject and verb alternatives of the gate's certain forms, several wave-6 disclosure words, and `classify_flag`'s guards (unit, exact operand set, inputs in the pack, tagged keys, cited only).
  - `report` scores the first try under the gate at b3ed8ef, so it needs that commit in the local git history.
  - The committed `runs/eval-v1/REPORT.md` and `summary.json` were written by older report code (nearest-rank latencies, rows since renamed); `report --label eval-v1 --out <folder>` prints today's.
- **Outside the deterministic net.** Thin or stale red flags (TGT's burn-coverage flag refers to FY2022) and errors only a careful reader finds remain partly unmeasured. Keep a hand-read sample of Opus judge rationales in each round.

---

## 5. Results

The experiment of §3 ran on Monday 26 October 2026. Every number below names its source:
- the reports, `runs/<label>/REPORT.md` and `summary.json`, whose counts are before hand reading, and the pooled
  reports in `runs/<a>+<b>/`;
- the spend ledger, `runs/spend.jsonl`;
- three hand readings made for this section, with no model call:
  - **the mislabel reading** read all 98 mislabel items that the reports list for K0, C and the control (52
    counted and 46 "not counted"), each against its record and the pack its arm reads;
  - **the failure, depth and latency reading** classified every first-try failure of eval-v2, read the 17 pairs in
    which the Opus judge gave K0 depth over C, and timed every recorded DeepSeek call;
  - **the third reading**, of P's held-out runs `eval-v2-p-r1` and `eval-v2-p-r2`, by the same rules and by a
    different reader: their 11 mislabel items (8 counted, 3 "not counted"), their logic slip, their 19 first-try
    failures and their calls' latency.

Their working files are not committed (see Evidence). This branch changes no production code, and nothing in this
section is implemented in production.

**Arms** (§3, step 2):

| Arm | Prompt | Pack |
|---|---|---|
| K0 | frozen, `d558d371` | `packs/` |
| P | frozen | `packs-v2/` |
| Q | candidate | `packs/` |
| C | candidate | `packs-v2/` |

- All four run under `--pipeline v2`: the retyping, the gate with its backstops, one patch repair (or a full repair
  if the patch is unusable), then the fallback.
- **The production control** is `eval-v2-v1control`: K0 under `--pipeline v1`. That is eval-v1's procedure (the gate
  without backstops, one full repair), the procedure behind the founder's "about $0.007 and 10 seconds".
- Production itself still runs today's code-written narrative (REPORT.md §1).

### 5.1 What ran, and what it cost

| Label | Step | What ran | Analyses | Start (UTC, 26 Oct) |
|---|---|---|---|---|
| `eval-v1-view2` | 0 | Opus re-audited eval-v1's 20 DeepSeek and 20 Sonnet outputs under view 2. No generation | 40 audits | committed 08:26 |
| `step1-r1` | 1 | The patch repair, twice each, on the 21 recorded DeepSeek first passes that version 2 still repairs | 42 repairs | 10:02, off-peak |
| `dev-v5-r1`, `dev-v5-r2` | 2, round 1 | K0, P, Q and C on the 10 development companies, with candidate `05f799a8` | 80 | 10:03 and 10:14, off-peak |
| — | round 2 | Six candidate lines and gate rule G1, from dev-v5's first-try failures. No model call (§2, "As built") | — | — |
| `dev-v6-r1`, `dev-v6-r2` | 2, the one further round | The same four arms, with candidate `fc5b808c` | 80 | from 15:19, off-peak |
| `eval-v2-r1`, `eval-v2-r2` | 3 | K0 and C, frozen at `fc5b808c` and the gate of 3115165, on the 10 held-out companies | 40 | from 16:11, off-peak |
| `eval-v2-v1control` | 3, added | The production control on the 10 held-out companies, the same evening | 10 | 16:40, off-peak |
| `eval-v2-p-r1`, `eval-v2-p-r2` | 3, added after eval-v2's results were seen | P on the 10 held-out companies: the build §3's guard rule leaves once it drops the candidate prompt (§5.2). Frozen prompt and `packs-v2/` at the same commit; nothing was changed | 20 | from 17:39, off-peak |
| `eval-v2-peak` | 4 (harness README) | C, one held-out run inside DeepSeek's peak window, for latency only; P now runs beside it (`--arms deepseek-flash-p,deepseek-flash-c`) | — | **scheduled for 2026-10-27 06:05 UTC, not yet run** |

- The start times come from the runs' commit messages.
- Every generation finished. No generation failed, no repair is owed and there was no provider error (each report's
  rows).
- **Audits.** Opus audited every K0, C and control output: the semantic audit under view 2, and the cause audit.
  DeepSeek V4 Pro audited K0 and C as the second auditor.
- **Judge.** The Opus judge compared C with K0 in both orders in every development and held-out run.
- P and Q have deterministic measures only on development, as §3 planned. On held out, Opus also audited P's 20
  outputs (semantic and causes). No judge read P: the judge compares arms within one run, and P ran apart.

**Spend** (`runs/spend.jsonl`). The ledger's audit rows carry no label. Each is assigned by its place in the ledger,
between a run's generation rows and its judge rows. The first 40 rows are step 0's. The control's 20 audits are rows
1,041–1,060, and the last 72 rows are P's: 32 generation calls and 40 Opus audits.

| Label | DeepSeek flash | DeepSeek V4 Pro (second auditor) | Opus through `claude -p` (notional) |
|---|---|---|---|
| Step 0 (`eval-v1-view2`) | — | — | $6.18 (40 semantic audits) |
| Step 1 (`step1-r1`) | $0.02 (42 patches) | — | — |
| dev-v5, 2 runs | $0.54 | $0.43 | $13.59 |
| dev-v6, 2 runs | $0.54 | $0.42 | $13.44 |
| eval-v2, 2 runs | $0.27 | $0.42 | $13.13 |
| Control | $0.02 | — | $2.01 |
| P on held out, 2 runs (`eval-v2-p`) | $0.13 | — | $3.67 |
| **Total** | **$1.53** | **$1.26** | **$52.01** |

- **DeepSeek: $2.79 billed.** §3 estimated about $2.1–2.5, and at most about $4.3. The peak run is not in the
  ledger yet; §3 prices C's at about $0.14, so with P beside it about $0.28.
- **Opus: $52.01**, at the CLI's notional rates. It runs on the Claude subscription, not the API key. §3 estimated
  about $30–43. Most of the difference has three sources:
  - the second development round audited and judged all of K0 and C ($13.44, against the $8.9 planned for an
    optional round of 20 analyses);
  - the control's audits ($2.01) and P's held-out audits ($3.67) were not in the plan.
- **The control's DeepSeek bill is not its cost.** It recorded $0.0020 an analysis (`summary.json`,
  `cost_recorded_mean`). Version 1 sends no nonce, so the control's prompts read from cache the packs that earlier
  runs had sent. The report prices each analysis as a company's first analysis would bill: $0.0071.

**Step 1, the patch repair alone** (`runs/step1-r1/repair-replay/summary.json`):
- 42 patch repairs, with 0 provider errors and 0 falling back to a full repair;
- every untouched sentence kept byte for byte in 42 of 42;
- 37 of 42 pass the gate after one patch;
- latency p50 2.5 s and p90 3.2 s, at $0.00054 a repair. A full repair takes about 6.5 s and costs $0.00145 (§1.1).

### 5.2 The held-out result

The rows of §3's Measures table. Three rows are read by hand (P's by the third reading):
- **the real first-try gate errors**, by the failure reading. They are the gate's failures on the model's own first
  output, less the gate's false positives;
- **the real mislabels**, by the mislabel reading;
- **the logic slips**, each named in its run's report.

The watch-forecast row is the lexicon's count. §3 asks for it to be read by hand, and this section did not do so.

Every other value is printed by `runs/eval-v2-r1`, `runs/eval-v2-r2`, `runs/eval-v2-p-r1`, `runs/eval-v2-p-r2`,
their pooled reports and `runs/eval-v2-v1control`. The pooled latencies come from the failure reading and P's reading,
as the pooled reports print none. P's hand-read rows are the third reading's.

| Measure | Target for C | C: run 1 · run 2 (pooled) | C against target | K0: run 1 · run 2 (pooled) | P: run 1 · run 2 (pooled), run later | Production control (one run) |
|---|---|---|---|---|---|---|
| Passes without a model repair | at least 85% pooled; no run below 80% | 60% · 30% (45%) | **missed** | 20% · 40% (30%) | 50% · 30% (40%) | 50% under version 1's gate; 30% on the arms' basis (VRTX's and DUK's first passes also carry backstop hits) |
| Final outputs passing the gate after one repair (the rest fall back) | — | 10 · 10 of 10 | — | 9 · 9 of 10 (CVX in both) | 10 · 9 of 10 (DE in run 2: a gate false positive on its corrected sentence) | 9 of 10 |
| Real first-try gate errors per analysis (failure reading) | 0.15 or less | 0.70 · 0.70 (0.70); printed 0.70 · 0.90 | **missed** | 1.00 · 0.70 (0.85); printed 1.30 · 0.70 | 0.50 · 0.60 (0.55); printed 0.50 · 0.80 | printed 0.60; not read by hand |
| First-try backstop hits per analysis | — | 0.00 · 0.10 (0.05) | — | 0.20 · 0.70 (0.45) | 0.20 · 0.40 (0.30), all net-debt signs (R2a) | 0.40 |
| Repairs sent for broken net cash alone | — | 0 of 4 · 0 of 7 | — | 0 of 8 · 0 of 6 | 0 of 5 · 0 of 7 | 0 of 5 |
| Mislabels per 1,000 verified claims, probes alone | — | 0.0 · 0.0 | — | 0.0 · 0.0 | 0.0 · 0.0 | 4.1 (3 in 735) before reading; 2.7 (2) after, as DUK's "-0.62x" is correctly labelled |
| Real mislabels per 1,000 verified claims (mislabel reading) | 3.5 or less in each run | 5.9 · 1.4 (3.6: 5 in 1,405); printed 7.4 · 2.7 | **missed** in run 1 | 1.3 · 5.5 (3.4: 5 in 1,478); printed 4.0 · 5.5 | 5.7 · 4.5 (5.1: 7 in 1,364); printed 7.2 · 4.5 | 4.1 (3 in 735); printed 5.4 |
| Judgement share outside the watch list | 3–12% | 12.0% · 11.2% (11.6%) | met | 1.1% · 0.8% (1.0%) | 1.5% · 1.5% (1.5%) | 0.8% |
| Evaluative words in fact and comparison sentences | 3% or less | 0.0% · 0.0% | met | 5.6% · 3.5% (4.6%) | 3.3% · 2.2% (2.8%) | 5.4% |
| Watch items with forecast wording, per 60 | 2 or fewer | 0 · 0 | met | 4.0 · 8.0 (6.0) | 12.0 · 8.0 (10.0) | 2.0 |
| Unsigned falls (U1) | 0 (guard) | 0 · 0 | met | 0 · 0 | 0 · 0 | 1 (VRTX) |
| Unitless dollars; margin-gap direction | — | 0; 0 | — | 0; 0 | 0; 0 | 0; 0 |
| Broken net cash stated as fact | 0 | 0 of 6 · 0 of 6 (5 and 3 disclosed) | met | 4 of 6 · 4 of 6 | 0 of 6 · 0 of 6 (5 and 5 disclosed) | 4 of 6 |
| Sentences stating a broken figure | 0 | 0 · 0 | met | 9 · 10 | 0 · 0 | 10 |
| Version-1 peer ranks on a peer's broken year | — | 0 · 0 | — | 2 · 3 | 0 · 0 | 3 |
| Cause support, Opus: supported; unsupported | at least 72%; at most 2% (guard) | 71% · 69% (70%); 0% | **missed** (supported) | 70% · 78% (74%); 2% · 0% | 70% · 77% (74%); 2% · 0% (1%) | 68%; 0% |
| Cause sentences per analysis | at least 6 (guard) | 5.2 · 5.2 | **missed** | 5.6 · 6.3 (6.0) | 6.0 · 6.2 (6.1) | 6.9 |
| Judge, C against K0: grounding and calibration each won or tied in the same pair | C on at least 12 of 20 | 7 · 9 of 10 (16 of 20) | met | 5 · 2 of 10 (7 of 20) | not judged | not judged |
| Judge: pairs in which K0 won depth | no more than 5 of 20 | 4 · 5 (9 of 20) | **missed** | — | not judged | not judged |
| Words per analysis, mean (max) | 700 or fewer | 589 (700) · 619 (689) | met | 626 (707) · 613 (762) | 595 (681) · 577 (690) | 634 (787) |
| Sentences per analysis, mean (max) | 30 or fewer | 29.7 (30) · 29.8 (31) | met on the mean; two analyses have 31 (DUK and RIVN, run 2) | 29.1 (30) · 29.1 (30) | 29.9 (33) · 29.8 (31): met on the mean, as C's is; four analyses have more than 30 (KO 33 and TGT 31 in run 1, DUK and RIVN 31 in run 2) | 29.2 (31) |
| Analyses with all 7 sections | all | 10 · 10 of 10 | met | 10 · 10 of 10 | 10 · 10 of 10 | 10 of 10 |
| API list cost per analysis, off-peak | at most $0.0075 | $0.0065 · $0.0067 | met | $0.0068 · $0.0067 | $0.0066 · $0.0067 | $0.0071 |
| Latency p50 (s) | at most 10.5 | 10.1 · 12.0 (11.2) | **missed** in run 2 | 12.3 · 11.3 (11.8) | 10.54 · 10.9 (10.9) | 12.8 |
| Latency p90 (s) | at most 13 | 12.5 · 12.8 (12.5) | met | 13.7 · 613.7 (74.5; 14.1 with each stall's 600 s taken out) | 12.2 · 11.4 (12.1) | 17.8 |
| Latency at peak hours (`eval-v2-peak`) | the same targets | scheduled for 2026-10-27 06:05 UTC, not yet run | open | — | scheduled with C, not yet run | — |
| Logic slips (probe measures, read by hand) | — | 0 · 0 | — | 1 · 0 | 0 · 1 (DUK's "conversion fell to 2.32x": it rose from 2.12x, a real error) | 0 |

- **C missed seven of its targets and guards:**
  - passes without a repair;
  - real first-try errors;
  - real mislabels in run 1;
  - cause support;
  - cause count;
  - depth;
  - p50 in run 2.
- **The stopping rule** (§3, "When to stop"):
  - The held-out half ran once per arm, and nothing was changed after its results.
  - C missed by more than it did on development. Passes fell from dev-v6's 60% to 45%, and first-try gate failures
    rose from a printed 0.35 to 0.80 per analysis. So this is reported, and the candidate is not tuned on these
    companies.
- **The guard rule** (§3, "When a fix does harm": drop any fix whose arm worsens a guard measure in both runs). The
  guards are cause support (at least 72% supported, at most 2% unsupported), at least 6 cause sentences per analysis,
  and no unsigned fall. The cause count is the one that moved. Cause sentences per analysis, run by run:

  | Arm | dev-v5-r1 | dev-v5-r2 | dev-v6-r1 | dev-v6-r2 | eval-v2 run 1 | eval-v2 run 2 | Mean |
  |---|---|---|---|---|---|---|---|
  | K0 | 7.3 | 6.2 | 7.7 | 6.7 | 5.6 | 6.3 | 6.6 |
  | P (pack) | 6.8 | 7.2 | 6.9 | 6.6 | 6.0 | 6.2 | 6.6 |
  | Q (prompt) | 5.9 | 5.5 | 5.8 | 5.5 | — | — | 5.7 |
  | C (both) | 5.8 | 5.8 | 5.7 | 5.9 | 5.2 | 5.2 | 5.6 |

  - **The prompt.** Q and C wrote fewer cause sentences than K0 in every run they ran, ten of ten, and fewer than
    the guard's 6 in every one. C's gap to K0 ran from 0.4 to 2.0 per analysis, 1.0 on average. Under any reading of
    the rule, the prompt is dropped. Its fixes are the prompt lines of fixes 4, 5, 6, 9 and 10 and round 2's lines
    (§2), which the arms test only together.
  - **When the rule should first have fired.** Q and C were already below K0 and below 6 in both dev-v5 runs. The
    rule was not applied then. Round 2, §3's one further development round, tried instead to restore the cause count
    with the "give the stated cause" line (§5.3). C's count did not move (5.8 in both rounds), and the prompt was
    carried to held out on that attempt. Applied after dev-v5, the rule would have dropped the prompt then. Applied
    now, it drops the same prompt.
  - **The pack.** P stayed at or above 6 in all six runs, and over the six runs it matches K0 (6.6 and 6.6). Read
    strictly, as "below K0 in both runs of a round", the rule fires once, in dev-v6 (6.9 and 6.6 against 7.7 and 6.7),
    and not in dev-v5 or on held out. Both gaps are within K0's own spread from run to run (5.6–7.7). I read that
    as noise and keep the pack; the founder should know that this is a judgement.
  - **Cause support** moved in neither direction for the pack. P read 70.0% and 77.4% against K0's 69.6% and 77.8% on
    the same companies, with 2% and 0% unsupported. For C it was 71% and 69%, against K0's 70% and 78%.
  - **No unsigned fall** in any P or C run. Q wrote one in dev-v6-r1.
- **P against C's targets.** Measured on held out after eval-v2's results were seen, P met the targets for broken net
  cash, cost and p90, and evaluative words in run 2 only (3.3% and 2.2%). It missed passes (40%), first-try errors
  (0.55), mislabels in both runs (5.7 and 4.5), judgement share (1.5%), watch forecasts (10 per 60) and p50 in both
  runs (10.54 and 10.9 s; run 1 by 0.04 s). It kept the cause-count and
  unsigned-fall guards in
  every run; its cause support was 70% in run 1, under the 72% guard, as K0's was (70%). No judge read it.

**The judge on the held-out half** (the overall verdict from each run's report, the criteria from the pooled report;
both orders agreeing; K0 wins · C wins · ties or splits):

| Criterion | eval-v2-r1 | eval-v2-r2 | Pooled |
|---|---|---|---|
| Overall | 3 · 4 · 3 | 2 · 6 · 2 | 5 · 10 · 5 |
| Grounding | 3 · 5 · 2 | 1 · 5 · 4 | 4 · 10 · 6 |
| Calibration | 2 · 4 · 4 | 0 · 8 · 2 | 2 · 12 · 6 |
| Depth | 4 · 0 · 6 | 5 · 1 · 4 | 9 · 1 · 10 |
| Coverage | 3 · 0 · 7 | 3 · 2 · 5 | 6 · 2 · 12 |
| Clarity | 4 · 1 · 5 | 2 · 1 · 7 | 6 · 2 · 12 |

**Against eval-v1.** The same 10 held-out companies, read under view 2:
- `eval-v1-view2`'s report prints 9 DeepSeek mislabels in 711 verified claims (12.7 per 1,000), and 1 of Sonnet's in
  724 (1.4).
- Step 0's hand reading (its commit, e4ba4cd) found 16 of DeepSeek's 18 flags over the 20 companies real. The two
  false ones are RIVN's and KO's, both held out, which leaves 7 in 711: 9.8 per 1,000.
- Today K0 reads 3.4, C 3.6, P 5.1 and the production control 4.1. The control repeats eval-v1's configuration, so
  the fall from eval-v1 is between days or runs, not between arms.
- Three readers did these readings, so the comparison is approximate. At this sample size a twofold spread between
  two runs of one configuration is the noise floor.
- **Calibration against Sonnet.** On the same held-out companies, `eval-v1-view2` prints Sonnet's judgement share at
  3.8%, its evaluative words at 2.6% and its watch forecasts at 2.0 per 60. C's 11.6%, 0.0% and 0 are within §3's
  targets, where Sonnet's were. P's evaluative words are within target pooled (2.8%; run 1 read 3.3%), but its
  judgement share (1.5%) and watch forecasts (10.0) are not. No judge compared C with Sonnet: §3's optional
  pairing was not run.

### 5.3 The development rounds and the four arms

Pooled over each round's two runs (`runs/dev-v5-r1+dev-v5-r2`, `runs/dev-v6-r1+dev-v6-r2`). The real mislabel rates
are the mislabel reading's; P and Q have no Opus audit.

| Measure | K0 v5 | P v5 | Q v5 | C v5 | K0 v6 | P v6 | Q v6 | C v6 |
|---|---|---|---|---|---|---|---|---|
| Passes without a model repair (run 1 · run 2) | 15% (1 · 2) | 15% (2 · 1) | 10% (1 · 1) | 35% (5 · 2) | 30% (3 · 3) | 30% (4 · 2) | 15% (2 · 1) | 60% (7 · 5) |
| First-try gate failures per analysis, printed | 0.70 | 0.90 | 0.80 | 0.45 | 0.80 | 0.75 | 1.15 | 0.35 |
| First-try backstop hits per analysis | 0.65 | 0.55 | 0.95 | 0.70 | 0.65 | 0.30 | 0.55 | 0.25 |
| Mislabels per 1,000, probes alone | 1.3 | 0.7 | 0.0 | 0.0 | 0.7 | 0.0 | 0.7 | 0.0 |
| Real mislabels per 1,000 (mislabel reading) | 6.0 | — | — | 6.8 | 4.1 | — | — | 5.6 |
| Judgement share outside watch | 1.5% | 0.6% | 10.1% | 11.1% | 2.5% | 1.5% | 9.8% | 10.4% |
| Evaluative words | 3.1% | 4.0% | 1.0% | 1.0% | 4.4% | 5.6% | 1.6% | 1.0% |
| Watch forecasts per 60 | 3.0 | 10.0 | 0.0 | 0.0 | 5.0 | 5.0 | 1.0 | 0.0 |
| Sentences stating broken net cash | 9 | 0 | 10 | 0 | 11 | 0 | 11 | 0 |
| Cause sentences per analysis | 6.8 | 7.0 | 5.7 | 5.8 | 7.2 | 6.8 | 5.7 | 5.8 |
| Cause support, Opus | 75% | — | — | 83% | 74% | — | — | 85% |
| Latency p50, run 1 · run 2 (s) | 14.2 · 15.9 | 14.5 · 16.2 | 14.2 · 16.0 | 12.8 · 15.5 | 14.0 · 13.8 | 13.8 · 14.3 | 12.9 · 14.7 | 10.5 · 13.4 |
| Cost per analysis | $0.0068 | $0.0068–0.0069 | $0.0068–0.0069 | $0.0067–0.0068 | $0.0067 | $0.0067–0.0068 | $0.0068–0.0069 | $0.0066 |

The judge, C against K0 (K0 wins · C wins · ties or splits):

| Round | Overall | Depth | Grounding and calibration each won or tied: K0 · C |
|---|---|---|---|
| dev-v5 | 2 · 12 · 6 | 11 · 0 · 9 | 2 · 18 of 20 |
| dev-v6 | 3 · 8 · 9 | 8 · 1 · 11 | 4 · 18 of 20 |

On the round-2 gate, C's dev-v5-r1 gate failures fall from 0.30 to 0.20, one sentence on CAT (§3's note on round 2).
The table prints the reports as committed.

**What each half of the candidate did** (P against K0 shows the pack; Q against K0 shows the prompt):
- **The pack, version 2:**
  - It removed broken net cash stated as fact: 0 sentences for P and C in every run, against 9–11 per round for K0
    and Q.
  - It removed the version-1 peer ranks built on broken years (P 0, K0 8 per round).
  - It halved the backstop hits in dev-v6 (P 0.30 against K0's 0.65), but not in dev-v5 (0.55 against 0.65).
  - Alone, it did not lower first-try gate failures on development (P 0.90 and 0.75, against K0's 0.70 and 0.80). On
    held out, run later, P's were 0.50 and 0.80 against K0's 1.30 and 0.70, and it passed 40% against K0's 30%.
  - It did nothing for calibration. P's watch forecasts were the most of the four arms in dev-v5 (10.0 per 60) and
    tied K0's in dev-v6 (5.0); on held out they were 12.0 and 8.0.
  - It cost no causes: P wrote 6.6 cause sentences per analysis over six runs, as K0 did (§5.2, the guard rule).
- **The prompt, the candidate:**
  - It moved calibration on either pack: judgement 9.8–11.1%, evaluative words 1.0–1.6%, watch forecasts 0–1
    per 60.
  - On `packs/` it raised the first-try failures: Q's backstop hits were 0.95 in dev-v5, and its gate failures 1.15
    in dev-v6. Q's passes were the lowest of the four arms (10% and 15%).
  - The likely reason is that its lines are written for version 2's pack: the net-debt wording and the typical
    operating cash flow / net income level are there, not in `packs/`. Q's backstop hits, in each run's list, are
    mostly R1 (another ratio's reference level) and R2a (a minus sign under net debt).
  - It cost causes: 5.7–5.8 cause sentences per analysis for Q and C, against 6.8–7.2 for K0 and P. The prompt costs
    depth, not the pack.
- **Together (C):** C is the only arm whose first try improved. Its gate failures were 0.45 and 0.35, and it passed
  35% and 60% of analyses. It kept Q's calibration and P's clean net cash.

**Round 2** (dev-v5 to dev-v6; C's prompt changed, and K0 changed only by G1):
- **C improved:**
  - passes went from 35% to 60%;
  - gate failures from 0.45 to 0.35;
  - backstop hits from 0.70 to 0.25;
  - depth lost from 11 to 8 pairs;
  - real mislabels from 6.8 to 5.6 per 1,000.
- **K0 improved too, with no change of its own.** Its passes went from 15% to 30% and its real mislabels from 6.0
  to 4.1. The round-2 replay flipped no K0 sentence (§2, "As built"). So part of C's improvement is run-to-run
  variation.
- **Lines that did not hold** (from the first two readings):
  - "Above or below a reference, by its numbers": C still wrote COST's "1.71x … above the 1.75x window median" in
    dev-v6-r1, and NVDA's "60.4% … above the 62.4% window high" in dev-v6-r2.
  - "No operating-cost comparison without the gap value" (P2): C wrote one in all 6 analyses of the three companies
    without that value (COP and JPM in dev-v6, USB in eval-v2). Both JPM sentences have the wrong direction.
  - "The efficiency ratio's complement" is new in both dev-v6 runs, and wrong in both.
  - "Give the stated cause" left C's cause count at 5.8 per analysis on development, and 5.2 on held out.
  - "Both margins from that one year": C mixed years on DE in both held-out runs. It was caught first try in
    run 2, and is a mislabel in run 1's final output.
- **A line that held on development only:** the net-debt line (P1) took C's net-debt sign errors from 2 to 0 on the
  development half. KO's "net debt was $32.4 billion, -70.7% of revenue" in eval-v2-r2 is one more.

### 5.4 Mislabels, read by hand

**Verdicts:**
- **Counted:** 46 of the 52 counted items are real errors.
- **The 6 false counted items:**
  - SNAP's "$2.6bn": the level is $2.6bn too;
  - RIVN's 75th percentile;
  - three "80%" red-flag thresholds (ORCL K0, KO C, DUK C), which the gate verified through an unrelated computed
    bound, so Opus judged that match, not the sentence;
  - the control's DUK "-0.62x", which is correctly labelled. Counted the way §1.2 counted CAT's similar sentence,
    it would make the control's rate 5.4.
- **Not counted:** all 46 "not counted" Opus flags are false (twin values, bounds, or the gate's own match misread),
  so the classifier's class held.
- **P on held out** (the third reading): 7 of its 8 counted items are real. The false one is a fourth "80%" threshold
  of the same kind (DUK, run 1: free cash flow was below 80% of net income in each year named). Its 3 "not counted"
  flags are false: TGT's 0.3pp margin change beside a 0.28pp cost effect (both runs) and TGT's 0.94x current ratio
  beside a 0.94x median, each pair equal at the precision written.
- **Minor errors** are sentences that are wrong as written but still give a careful reader the right picture: a sign
  under "net debt", the rounding of a difference, an ambiguous phrase, a one-year slip between nearly equal values.

**Real errors per 1,000 verified claims, per run.** The verified claims are each report's `audited_verified_claims`.

| Arm | dev-v5-r1 | dev-v5-r2 | dev-v6-r1 | dev-v6-r2 | eval-v2-r1 | eval-v2-r2 | Runs at 3.5 or less |
|---|---|---|---|---|---|---|---|
| K0 | 8.0 | 3.9 | 1.4 | 6.9 | 1.3 | 5.5 | 2 of 6 |
| C | 11.2 | 2.7 | 6.8 | 4.4 | 5.9 | 1.4 | 2 of 6 |
| P (run later, `eval-v2-p`) | — | — | — | — | 5.7 | 4.5 | 0 of 2 |
| Production control | — | — | — | — | 4.1 (its one run) | — | — |

| Pool | K0 | C | P | Control |
|---|---|---|---|---|
| Development, 4 runs | 15 in 2,963 (5.1); 3.7 with minor errors left out | 18 in 2,886 (6.2); 4.5 | not audited | — |
| **Held out, 2 runs** | **5 in 1,478 (3.4); 2.7** | **5 in 1,405 (3.6); 2.1** | **7 in 1,364 (5.1); 4.4** | **3 in 735 (4.1); 2.7** |
| All 6 runs | 20 in 4,441 (4.5) | 23 in 4,291 (5.4) | — | — |

Each held-out figure rests on 3 to 7 sentences, so none of the four can be told from the others.

**Error classes among the real errors** (six runs for K0 and C, the two held-out runs for P, one for the control):

| Class | K0 | C | P | Control |
|---|---|---|---|---|
| A. Above or below a reference level, or a value named as a level it is not (window median, high or low, or peer median) | 2 | 6 (1 minor) | 4 (1 minor) | 0 |
| B. Another ratio's reference level (the free-cash-flow median used for operating cash flow / net income) | 3 | 0 | 0 | 1 |
| C. Period slips | 2 | 4 (2 minor) | 2 | 0 |
| D. Passage figures misattributed (wrong year or basis, wrong line, a change stated as a level) | 5 | 2 | 1 (AMD) | 1 (minor) |
| E. A minus sign under net debt, or net cash's sign dropped | 3 (all minor) | 3 (all minor) | 0 | 1 |
| F. Sign or direction of another value | 2 (DE twice) | 1 (CVX) | 0 | 0 |
| G. Wrong metric (a component named as the total, or a component's move named as the ratio's) | 1 (USB) | 1 (RIVN) | 0 | 0 |
| Bank profile (JPM): cost against revenue in the wrong direction (3); "the efficiency ratio's complement" (2) | 0 | 5 | 0 | 0 |
| H. Rounding of a difference | 2 (minor) | 0 | 0 | 0 |
| I. Label slip on a recast value | 0 | 1 (minor) | 0 | 0 |
| **Total** | **20 (5 minor)** | **23 (7 minor)** | **7 (1 minor)** | **3 (1 minor)** |

- **C fixed class B.** Version 2's operating cash flow / net income median works: there were 3 for K0 on
  development and 1 for the control, and none for C. C also misread fewer passages (2 against K0's 5).
- **C added class A and the bank errors.**
  - Five of C's six class-A errors are against version 2's new operating-cash-flow medians or window levels. COST's
    "1.71x above the 1.75x median" is in 3 of 4 development runs. There are none on the held-out half.
  - All five bank errors are JPM's, on the development half. C also wrote USB's operating-cost comparison in
    eval-v2-r2, with the right sign.
- **Class A is not only version 2's new medians.** Four of P's seven held-out errors are class A, all against window
  levels that version 1's pack also has:
  - RIVN's "operating margin of -66.5% … far below the -129.4% median", in both runs;
  - USB's efficiency ratio "59.0%, just above the 59.3% window median" (58.99% against 59.33%);
  - DUK's current ratio "0.55x in FY2025, the window low", where the low is FY2020's 0.53x (minor).

  Neither the frozen prompt nor version 2's pack prevents this class. The candidate prompt's line against it did not
  hold either (§5.3).
- **Net-debt signs persist equally** (3 for K0, 3 for C, all minor). Probe R2a misses 4 of the 6 "minus sign under
  net debt" sentences, because it takes "net cash" anywhere earlier in the sentence as the label (the `probes.py`
  docstring). R2a is also the gate's backstop, so what it misses reaches the final outputs; Opus found these.
- **Held out, C's 5 errors fall in 5 different classes:** VRTX I, RIVN G, CVX F, DE C and KO E. K0's 5 are DE F
  twice, RIVN D, USB G and ORCL E. No class holds more than one of C's. P's 7 are RIVN A twice, USB A, DUK A,
  VRTX C (diluted EPS "rose to $15.32 from $13.89", FY2023's figure, over FY2024's loss of $2.08), DE C (an
  operating-income growth rate to FY2024 set against a revenue growth rate to FY2025) and AMD D (the $103 million
  total tax benefit given as the uncertain-tax-position release, which was $853 million).
- **No minus sign under "net debt" reached P's final text on held out.** Its backstop caught 6 at first try (DUK and
  ORCL, R2a), and each repair removed the sign.
  - One repair left the direction behind. ORCL's run-2 watch item read "a move back above zero from -$97.6 billion"
    under "net debt". It now reads "a move back above zero from the FY2026 net debt of $97.6 billion would confirm
    deleveraging". That is net cash's direction set under a net-debt figure.
  - Neither R2a nor Opus flagged it, so it is outside the counted rate. That is true of any unflagged error, in every
    arm.

### 5.5 First-try failures and the repair (eval-v2)

The failure reading ran the gate with its backstops on each model's own first output. Its counts match the reports:
K0 has 20 gate claims and 9 backstop claims over the two runs, and C has 16 and 1.

It sorts each failing claim into one of three kinds:
- **True error:** the pack supports the right sentence, and the model miscited, miscomputed, cut a figure or guessed a
  cause.
- **Prompt-induced:** a slot or example in the arm's prompt asks for what its pack cannot supply, or copying the
  prescribed form produces the failure.
- **False positive:** a true, grounded sentence the gate cannot read.

| | K0 run 1 | K0 run 2 | C run 1 | C run 2 | K0 | C |
|---|---|---|---|---|---|---|
| True error | 9 | 4 | 5 | 4 | 13 | 9 |
| Prompt-induced | 3 | 10 | 2 | 4 | 13 | 6 |
| False positive | 3 | 0 | 0 | 2 | 3 | 2 |
| Analyses failing first try | 8 | 6 | 4 | 7 | 14 of 20 | 11 of 20 |
| Final outputs passing the gate | 9 | 9 | 10 | 10 | 18 | 20 |

**K0's prompt-induced failures** are the input gaps C was built to fix:
- net-debt signs (8);
- the typical operating cash flow / net income level (2);
- the 100% payout threshold (3).

C had none of the first two kinds.

**C's prompt-induced failures** have four sources:
- the drivers form on USB, which has no gap value (2);
- buybacks as a share of ORCL's negative free cash flow (2);
- the margin example's FY2025 frame on DE (1);
- the 100% threshold (1).

No pack ID holds the 100% payout threshold. The first outputs of eval-v2 write it 6 times. Twice it passes, as a bound
the cited value satisfies: K0's KO "the third straight year above 100%" (run 1) and C's CVX "stay above 100% of free
cash flow, against 149.7%" (run 1). The other 4 fail (3 by K0, 1 by C): each is a watch item reading "below 100% from
X", with X above 100%. In each, the repair swapped in some year's payout level, and the "self-funded" meaning was
lost. P's first outputs, run later, follow the same pattern: KO's "stay above 100%" passes as a bound (run 1), and
KO's "back under 100% of free cash flow" fails (run 2).

**C's 9 true errors:**
- 5 figures without their own ID, 4 of them a red flag's figure;
- 2 wrong IDs;
- 2 figures cut instead of rounded.

With every prompt-induced failure and false positive removed, C would pass first try in only 6 of 10 per run (60%),
against the 85% target.

**The repair:**
- The patch repair fixed 15 of C's 17 failing claims cleanly. The other two:
  - VRTX's buyback figure became "the restatement" (a run-1 mislabel);
  - USB's "fell 6.4pp more than revenue" passes the gate, but revenue rose.
- All 20 of C's final outputs pass the gate.
- Two of K0's do not (CVX, both runs), so in production they would fall back to today's narrative.

**P on held out** (the third reading, the same rules). P has 13 gate claims and 6 backstop claims over its two runs,
as its reports print:

| | P run 1 | P run 2 | P |
|---|---|---|---|
| True error | 5 | 5 | 10 |
| Prompt-induced | 2 | 5 | 7 |
| False positive | 0 | 2 | 2 |
| Analyses failing first try | 5 | 7 | 12 of 20 |
| Final outputs passing the gate | 10 | 9 | 19 |

- **Prompt-induced:** 6 net-debt signs (DUK and ORCL, R2a). Pack version 2 words net debt for every arm, but only the
  candidate prompt carries the net-debt line (fix 4's prompt part). The seventh is KO's 100% threshold.
- **True errors:**
  - 5 figures without their own ID, 2 of them a red flag's threshold (ORCL's 80%, both runs);
  - 3 computations the pack does not hold or that are wrong: AMD's -21.3pp change in the tax rate, TGT's 4.8% capex
    forecast, and DE's "4.6pp below the FY2023 high" (it is 5.6pp);
  - 2 margin bridges typed "cause" with no passage (AMD, both runs).
- **False positives** (both VRTX, run 2): "contribution … fell from 26.3pp in FY2022 to 0.7pp" is read as the
  value's own direction, and "fell 300.7pp to 14.9% after the FY2024 Alpine distortion" binds FY2024 to the FY2025
  rate.
- **The repair** fixed every failing claim. P's 7 counted mislabels and its logic slip were all in its first outputs,
  in sentences the gate passed. One repair traded a sign error for a direction error: ORCL's run-2 watch item
  (§5.4). The one final output that fails is DE's in run 2, and its repaired sentence is right: "2.7pp lower than FY2024 and 5.6pp below the FY2023 high of 16.6%". The gate binds FY2024 to the
  5.6pp, a false positive. In production this analysis would fall back to today's narrative.

### 5.6 Depth

The failure reading read the 17 pairs in which K0 won depth in eval-v2 (9) and dev-v6 (8), against a limit of 5 per
split. In those 17 pairs the judge's overall verdict was C 8, K0 5, ties 4. Every figure in the table is over those
17 pairs only, not over all analyses.

| In the 17 pairs | K0 | C |
|---|---|---|
| Cause sentences, all 17 analyses | 118 | 98 |
| Cause audit of those: supported / partial / unsupported | 88 / 29 / 1 (75% supported) | 81 / 17 / 0 (83%) |
| Causes in the margins section, per analysis (eval-v2 / dev-v6) | 1.9 / 2.2 | 1.1 / 1.4 |
| Red-flag sentences, per analysis | 3.9 / 3.8 | 5.9 / 5.0 (of which judgements 2.9 / 2.5) |
| Words, per analysis | 652 / 665 | 598 / 608 |
| Passages cited, per analysis | 7.9 / 9.5 | 6.2 / 7.0 |
| Peer sentences, per analysis | 2.0 / 1.8 | 1.2 / 1.9 |
| Segment or product sentences, per analysis | 3.0 / 2.4 | 2.4 / 1.9 |

- **What C lacked** (in the judge's rationales): mostly causes in the margins section, then segment drivers and peer
  comparisons.
- **Why.** Both arms write 29–30 sentences, at the 30-sentence cap. C's two-sentence red flags take about 2 more
  sentences, mostly the closing judgements, and that space is what K0 spends on margin causes and drivers.
- **K0's extra depth was only partly grounded.**
  - K0 wrote 20 more cause sentences than C. Of those, 7 more are fully supported, 12 more partial and 1 more
    unsupported.
  - In 6 of the 17 pairs, part of K0's depth was a balance-sheet reading built on net-cash figures that `packs-v2`
    withholds as broken (CVX, KO twice, TGT, COP, NVDA).
- **Cause sentences** were not lifted by round 2's "give the stated cause" line: 5.2 per analysis in eval-v2 and 5.8 in
  dev-v6 (§5.3).

### 5.7 Latency and cost against the production control

From the failure reading, and P's from the third reading: linear quantiles as in `records.quantile`; the per-token
speed is the median over first attempts.

| Group | First attempt p50 / p90 (s) | ms per output token | Repairs | Repair p50 / p90 (s) | Total p50 / p90 (s) |
|---|---|---|---|---|---|
| C, eval-v2, both runs | 9.3 / 10.4 | 5.21 | 11 patch | 2.5 / 3.1 | 11.2 / 12.5 |
| K0, eval-v2, both runs | 9.8 / 10.6 | 5.33 | 14 patch | 2.9 / 3.4 | 11.8 / 74.5 (11.8 / 14.1 with 600 s taken out per stall) |
| P, eval-v2-p, both runs (run later) | 9.1 / 9.7 | 5.18 | 12 patch | 2.4 / 2.7 | 10.9 / 12.1 |
| Production control (version 1) | 8.9 / 10.3 | 5.07 | 5 full | 7.0 / 7.8 | 12.8 / 17.8 |

- **What drives latency.**
  - A least-squares fit over the 78 eval-v2 and control generation calls without a stall gives about 1.8 s plus
    4.1 ms per output token (R² 0.95). With P's 32 calls it is 1.7 s plus 4.2 ms (R² 0.96).
  - Input of 24,000–56,000 tokens, cached or not, adds nothing measurable. So the control's warm cache does not
    flatter its latency.
  - A patch repair costs at least about 2 s.
- **p50 follows the repair rate, and the first attempt's length.** C's run 1, with 4 repairs, had a p50 of 10.1 s;
  its run 2, with 7, had 12.0 s. P's run 2 also repaired 7 analyses but had a p50 of 10.9 s: its first attempts were
  shorter (p50 8.7 s, about 1,740 output tokens) and its patches quicker (2.4 s). At the 85% pass target, p50 would
  be about 9.5 s and p90 about 11–12 s.
- **Against the production control** (off-peak, the same evening), C is about 1.6 s faster at p50 pooled (11.25
  against 12.81 s: 2.7 s in run 1, 0.85 s in run 2) and about 5 s faster at p90 (12.5 against 17.8 s). P, run about
  an hour later, is about 1.9 s faster at p50 (10.91 s) and 5.7 s at p90 (12.09 s). Both are cheaper:
  $0.0065–0.0067 an analysis against $0.0071 (K0 $0.0067–0.0068). At DeepSeek's peak price, every cost doubles.
  Pooled, no arm reaches the founder's "about 10 s" at p50 off-peak (C 11.25, P 10.91, K0 11.75 s). Only C's run 1
  did (10.1 s).
- **The development runs were slower per token.**
  - Their first attempts ran at a median of 5.5–6.4 ms per output token (10.1–11.7 s), against 5.2–5.3 ms
    (9.3–9.7 s) in eval-v2. These figures are from the ledger: its generation calls with more than 1,000 output
    tokens and under 60 s.
  - So the development p50s (12.8–16.2 s, apart from C's 10.5 s in dev-v6-r1) sit above eval-v2's (10.1–12.3 s).
- **Stalls.**
  - 8 of the 410 recorded DeepSeek generation calls (2.0%), in 8 of 245 analyses (3.3%), took 600 s plus a call of
    normal length. All 8 are in the labels since dev-v5, and there are none in eval-v2-r1, the control or step 1.
    P's 32 calls on held out, made later, had none. With them it is 8 of 442 calls (1.8%), in 8 of 265 analyses
    (3.0%).
  - **The cause.** The harness client calls DeepSeek with `timeout_s=600.0` and `max_retries=2`
    (`providers.py`, `_call_openai_compat`). It cut a request that never answered at 600 s and sent it again, and
    the retry ran at normal speed.
  - **The effect.** K0's eval-v2-r2 p90 of 613.7 s is two of these stalls (AMD's repair and KO's first attempt). C's
    one stall was NVDA's first attempt, in dev-v6-r2.
  - The records carry no wall-clock time, so the stalls cannot be tied to a time of day.
- **Overload retries, found in Codex's review of this branch.**
  - Until the fix that followed the review, the harness's own retry on a 429 or 5xx answer restarted the clock. That
    retry waits 30, 90 and 180 s, and was written for Gemini's free tier. So a call that retried recorded only its
    last attempt.
  - The client logged no failed request, so the records cannot show whether any call in these runs retried.
  - The stalls above are a different path, the client's own timeout and retry, and their full time is recorded.
  - Since the fix, a call records its whole wait, with its retries and its last attempt's time in its meta. The
    peak-hour run is measured that way.
- **Peak hours:** not measured. `eval-v2-peak` is scheduled for 2026-10-27 06:05 UTC and has not run. It now runs
  P beside C (one held-out run each), since P is the build §5.10 proposes.

### 5.8 What the experiment resolved, and what it did not

Held out unless said. "The code and pack" are the version-2 loop and pack version 2, which P and C share. "The
prompt" is the candidate prompt, which only Q and C carry.

**Resolved by the code and pack** (P and C alike):
- **Broken net cash and data breaks** (§1, mechanism 5):
  - Neither P nor C stated a broken figure as fact: 0 of 12 analyses of companies with a break, and 0 sentences.
    K0 stated them in 8 of 12 analyses (19 sentences) and the control in 4 of 6 (10 sentences).
  - P disclosed the break in 5 and 5 of the 6, and C in 5 and 3.
  - P and C stated none on development either.
- **The free-cash-flow median used for operating cash flow** (mechanism 2's first part, class B): 0 for P and C,
  against 3 for K0 on development and 1 for the control. Mechanism 2's second part, net cash on one signed basis, is
  not resolved (below).
- **Probe-detectable mislabels reaching a reader.** The backstops send each one to the patch repair. An output that
  still holds one fails the gate, so production would show today's narrative instead.
  - On held out, no version-2 final output holds one (K0, P and C). The control's hold 3 probe hits in 735 verified
    claims (4.1 per 1,000), of which 2 are real after reading (2.7).
  - On development, K0 kept 3 after its repair (dev-v5 1.3 and dev-v6 0.7 per 1,000), P one and Q one. Each of
    those outputs fails the final gate.
- **The repair's latency.**
  - A patch takes 2.4–2.9 s at p50 on held out (2.5 s in step 1), against 7.0 s for the control's full repair. It
    kept every untouched sentence in step 1 (42 of 42).
  - After one repair, 20 of C's outputs passed the gate, 19 of P's (DE: a gate false positive), 18 of K0's and 9 of
    the control's 10.
- **Cost and p90, off-peak:** P and C cost $0.0065–0.0067 an analysis, with a p90 of 11.4–12.8 s. The same evening's
  control cost $0.0071, with a p90 of 17.8 s. Peak hours are not measured yet.

**Resolved by the prompt only** (C, not P):
- **Calibration** (mechanism 3, as to judgements):
  - judgement share 11.6%, against P's 1.5%, K0's 1.0% and the control's 0.8%;
  - evaluative words in data sentences 0.0%, against 2.8%, 4.6% and 5.4%;
  - no watch forecasts, against 10, 6 and 2 per 60;
  - the judge's calibration verdicts, C 12 and K0 2.
- **Fewer net-debt signs at first try.**
  - C's first outputs had 1 backstop hit in 20 analyses, against P's 6, which were all net-debt signs.
  - In the final text, though, C kept one that R2a misses (KO). P kept no minus sign under net debt, but one
    net-cash direction slip (ORCL, run 2; §5.4).

**Not resolved:**
- **Wrong metric, period or sign in the final text.**
  - After hand reading, per 1,000 verified claims: K0 3.4, C 3.6, P 5.1 and the control 4.1. Sonnet scored 1.4 in
    eval-v1.
  - C met the 3.5 target in 2 of its 6 runs, as K0 did, and P in neither of its 2. The fixes changed which errors
    occur, not how many.
  - Net-debt sign errors (mechanism 2's second part) persist in C's and K0's final text: 3 each over six runs, all
    minor, where R2a misses them. P had none counted on held out, and the one uncounted direction slip (§5.4).
- **Figures without their own ID, and filled prompt slots** (mechanisms 1 and 4).
  - These still cause most first-try failures. P passed first try in 40% of analyses and C in 45%, against the 85%
    target.
  - Real first-try gate errors were 0.55 and 0.70 per analysis, against a target of 0.15.
  - The repair hides them from the reader, at about 2.5 s each.
- **p50 off-peak:** P 10.54 and 10.9 s, over the 10.5 s target in both runs (run 1 by 0.04 s). C 10.1–12.0 s. The
  founder's figure is "about 10 s".
- **Peak-hour latency:** not yet measured.
- **Stalls:** 8 of 442 recorded calls (1.8%) waited out a 600 s timeout. The harness keeps that timeout; a production call cannot.

**Made worse by the prompt: depth.**
- C wrote 5.6 cause sentences per analysis over six runs, against 6.6 for K0 and P (guard 6).
- K0 won depth in 9 of 20 held-out pairs (limit 5).
- Cause support on held out was 70% for C and 74% for P and for K0 (guard 72%). The control read 68%, so that part
  is not C's alone. C's 83–85% on development did not carry over.

**Noise:**
- With 10 companies and 2 runs, the experiment can only separate large effects.
- Two runs of one configuration differ about twofold in mislabels (eval-v1's held-out reading against the control:
  9.8 and 4.1).
- K0's passes doubled between dev-v5 and dev-v6 with no change of its own.

### 5.9 Bottom line

**The error gap is not closed.**
- On held-out companies, DeepSeek's final text still states a verified number about the wrong metric, period or sign
  3–5 times per 1,000 verified claims, whatever the build: K0 3.4, C 3.6, P 5.1, the control 4.1. Sonnet scored 1.4
  in eval-v1.
- Every build measured today is below eval-v1's 9.8, the control included. So that fall is between days or runs,
  not the fixes' doing, and the comparison is approximate (§5.2).
- The fixes changed which errors occur, not how many.

**What the fixes did achieve, at the founder's cost:**
- **The code and pack (P):**
  - no broken net cash stated as fact (K0: 8 of 12 analyses);
  - no probe-detected mislabel left for a reader;
  - a shorter tail: p90 12.1 s, against the control's 17.8 s;
  - $0.0066–0.0067 an analysis;
  - K0's cause count: 6.6 cause sentences per analysis over six runs. No judge read P, so its depth itself is not
    judged.

  These were measured off-peak on the same evening. The peak-hour run is pending.
- **The prompt (C, over P):**
  - It brought calibration within target.
  - The judge preferred C to K0: overall in 10 pairs to 5, calibration 12 to 2, grounding 10 to 4.
  - It wrote fewer cause sentences than K0 in every run, by 0.4 to 2.0 per analysis and 1.0 on average (5.6 over
    six runs). That is below §3's guard of 6, and K0 won depth in 9 of 20 pairs.

**Against §1's five mechanisms:**
- The code and pack fix the unnoticed data breaks (mechanism 5).
- They fix half of the pack gaps (mechanism 2): the operating cash flow / net income level, but not the net-debt
  signs.
- The prompt adds the judgement side of the literal typing (mechanism 3).
- Figures without their own ID (mechanism 1) and filled prompt slots (mechanism 4) remain. The repair hides them from
  the reader, at about 2.5 s each.

**What remains is spread thin, except one class.**
- "Above or below a reference level" holds 4 of P's 7 held-out errors and 6 of C's 23 over six runs.
- Prompt lines did not stop it (§5.3), and each case contradicts two numbers the gate has already matched.
- That class, and most of what remains, needs deterministic checks proven by replay, not more runs.

### 5.10 Recommendation (a proposal for the founder)

The grounding rule (`GROUNDING-RULE.md`) needs the founder's approval before any production work. This branch changes
no production code, and nothing below is built in production.

**Adopt as one build, once the rule is approved: the code and pack fixes as measured in P, plus a call deadline.**
This is what §3's rules leave standing, with two judgements of mine. They are stated here so that the founder can
overrule them:
- **The pack is kept,** although a strict reading of the guard rule fires on it once. In dev-v6, P wrote 6.9 and 6.6
  cause sentences per analysis against K0's 7.7 and 6.7. Both gaps are within K0's own spread from run to run, and P
  matches K0 over six runs (§5.2).
- **The backstops (fix 12) go on without fix 4's prompt line,** which §2 names among their conditions. What that
  costs is measured in item 1.

1. **The version-2 repair loop and gate.**
   - **Fixes 2, the code part of 5, 7 and 13,** which §3 lets ship on their own evidence:
     - the rewritten repair message;
     - the retyping of figure-only causes;
     - the narrowed gate fixes;
     - the patch repair, with the full repair as its fallback.
   - **Fix 12, the backstops** (R1, R2a, R2c, R3, U1, `gap_direction`, `broken_debt`), as repair triggers.
     - §2 turns them on only together with fixes 3, 4 and 13. This build has 3 and 13, and fix 4's pack part, but not
       fix 4's prompt line.
     - The cost of that gap is measured. P's 6 backstop hits on held out were all net-debt signs, the prompt line's
       subject, in 4 analyses.
     - Two of those analyses (ORCL, both runs) needed a repair anyway, for a red flag's threshold. The other two
       (DUK, both runs) were repaired for the hits alone, at 2.1 and 2.5 s. P's p50 was 10.54 and 10.9 s.
     - One of these repairs, ORCL's in run 2, removed the sign but left net cash's direction (§5.4).
   - *Evidence:* the step-1 replay (§5.1) and §5.7's latency. Under version 2, no probe-detected mislabel reaches a
     reader (§5.8).
2. **Pack version 2:** fixes 3, 4's pack part, 8, 9's pack part and 11. These are:
   - the operating cash flow / net income median and low;
   - the net-debt wording;
   - the same-year margin gap;
   - broken debt and cash withheld behind data checks;
   - the render items.

   *Evidence:* no broken figure stated as fact in any P or C run, class B gone (§5.4), and P's cause count is K0's.
3. **A per-attempt deadline on the DeepSeek call, with one retry.** This is new, and not in the harness.

   *Evidence:* 8 of 442 recorded calls (1.8%) waited out the harness's 600 s timeout and then ran at normal speed (§5.7).
   Cutting at a time-to-first-token deadline and retrying once would cost that deadline plus about 10 s. Production's
   Copilot stream has a 75 s overall deadline (`copilot_chat._CHAT_SECONDS`), and the analysis needs its own.

**This build keeps the cause-count and unsigned-fall guards in every run.** Its cause support fell under the 72%
guard in one held-out run (70%), as K0's did on the same companies (70%), and was never below K0's in both runs. It
misses §3's targets for:
- first-try passes (40%);
- real first-try gate errors (0.55 per analysis, against 0.15);
- wrong-metric numbers (5.1 per 1,000 on held out, against the control's 4.1, within noise);
- calibration: judgement share 1.5%, watch forecasts 10 per 60, and evaluative words in run 1 (3.3%; 2.8% pooled);
- p50 in both runs (10.54 and 10.9 s).

The founder decides with that in view.

**Hold back the candidate prompt (`fc5b808c`).** §3's guard rule drops it. It wrote fewer cause sentences than K0 in
all ten of its runs (C by 0.4 to 2.0 per analysis), and fewer than the guard's 6 in every one (§5.2). There are two ways forward, and the choice is
the founder's:
- **Recommended: one prompt round for calibration that keeps the cause guard.**
  - **What to keep:** the calibration lines and the net-debt line. The net-debt line would also remove P's net-debt
    repairs.
  - **What to change:** free the sentences that the closing judgements take (§5.6). Either write one closing
    judgement for the red-flag section instead of one per flag, or raise §3's form target to 32 sentences (about 90
    more output tokens, about 0.4 s at §5.7's fit).
  - **How to measure it:** on the development half, two runs, against P, the build it would join, with K0 for the
    guard. The cause guard is the bar, and the judge reads it against P.
  - **Cost:** about $0.27 of DeepSeek flash for its 40 analyses, plus about $0.42 if V4 Pro audits again as the
    second auditor. Opus would be about $13 at notional rates, as dev-v6's audits and judge were.
  - **The held-out limit:** K0, C and P have now all been read on the held-out half. A new prompt measured on the same
    ten companies is no longer a blind test. Add companies, or state that limit.
- **Or adopt C now, under a recorded exception to the guard.**
  - It gains calibration and the judge's preference over K0 (overall 10 pairs to 5).
  - It costs about one cause sentence per analysis on average (0.4 to 2.0 by run), and K0 won depth in 9 of 20
    held-out pairs.
  - No judge has compared C with P.

**Do not adopt:**
- **The frozen configuration as the production build** (K0, or the control). On held out, K0:
  - stated broken net cash as fact in 8 of 12 analyses with a break (19 sentences; the control, 10 sentences);
  - left 2 of its 20 outputs failing after repair (the control, 1 of 10).
- **Prompt lines as the only enforcement of a rule the model ignored** (§5.3):
  - P2, "no operating-cost comparison without the gap value";
  - "above or below a reference, by its numbers";
  - "give the stated cause";
  - "both margins from that one year".

  They can stay in a prompt, but the rules need code.
- **What this branch already withdrew or advised against:**
  - auto-citation (fix 1);
  - gate rules G2–G7;
  - the items under "Not recommended" in §2, DeepSeek's thinking mode among them.

**Banks are the founder's call.**
- C's five JPM errors on development come from its prompt's drivers form: the prescribed cost-against-revenue sentence
  and "the efficiency ratio's complement". K0, on the frozen prompt, made none of that kind.
- P made one bank error on held out: USB's efficiency ratio "just above" a median it is below (class A).
- The bank profile (next work, item 3) applies to either build. Until it lands, banks could keep today's narrative.

**Next work, ranked by the errors it is expected to remove.** The counts are real mislabels from the readings: K0's 20
and C's 23 over six runs, and P's 7 over its two held-out runs.

1. **A deterministic backstop for "above or below a reference level"** (class A: P 4 of 7, C 6 of 23, K0 2 of 20).
   - **Why it is checkable.** Each case sets a comparison word, or the name of a level, beside two numbers the gate
     has already matched to cited IDs: a value, and a window median, high or low, or a peer median. Either the word
     contradicts their signed order, or the value is not the level it is named:
     - RIVN's "-66.5% … far below the -129.4% median";
     - USB's "59.0%, just above the 59.3% window median";
     - DUK's 0.55x "the window low", which is 0.53x;
     - NVDA's 0.86x, which is the very window low it is said to be below.
   - **Why a check is needed.** COST's case recurred in 3 of 4 development runs, one of them after round 2's prompt
     line against it, and RIVN's recurred in both of P's held-out runs.
   - **Proof:** replay on the recorded outputs, with no model call. Every recorded class-A sentence must fail, and no
     true comparison may.
   - **Cost:** a hit costs one patch repair (about 2.5 s and $0.0005).
2. **The calibration round above.** It removes no error class. It targets the calibration targets and the cause
   guard.
3. **The bank profile** (C: 5 of 23, all JPM: the cost-against-revenue direction 3 times, "the efficiency ratio's
   complement" twice). USB's prompt-induced first-try failures in both of C's held-out runs add to it.
   - Give banks a "revenue growth minus operating-cost growth" value (noninterest expense against revenue), so that
     fix 7's certain form checks its sign.
   - As a backstop in place of P2, fail any operating-cost comparison in a pack without that value (COP, JPM, USB).
   - Take "complement" out of the form.
   - Widen the bank passages: the JPM gold example needed passages the selector missed (REPORT.md §4).
4. **Period slips** (class C: P 2 of 7, C 4 of 23 with 2 minor, K0 2).
   - **The cases:**
     - "prior year" put on the latest year's figure (JPM's $48.2 billion, in both K0 and C);
     - a year's debt given the year before's label, between nearly equal values (NVDA's $8.47 billion, twice);
     - a margin gap from one year beside another year's tax rate (DE's 3.7pp);
     - a "from" figure two years back that skips a loss year (P's VRTX: diluted EPS "rose to $15.32 from $13.89",
       which is FY2023's figure, over FY2024's -$2.08);
     - two growth rates over different windows set against each other (P's DE: operating income to FY2024, revenue
       to FY2025).
   - **Candidate checks:** compare "prior year", or a bare "from", against the cited ID's period. Growth rates set
     against each other must share their window. These checks are narrow.
   - **Caution:** wider year binding has failed review before (G4, §2), so this needs the replay and planted tests
     before any gate change.
5. **R2a's label reading** (class E: K0 3 and C 3, all minor; the control 1; P none on held out).
   - R2a reads "net cash" anywhere earlier in the sentence as the figure's label. So it misses 4 of the 6 "minus sign
     under net debt" sentences (§5.4).
   - Reading the label in the figure's own clause should catch them, and as a backstop it sends them to the patch
     repair.
6. **Fewer repairs, for the wait.** The repair fixes these, so the reader never sees them.
   - **Own IDs.** First-try true errors are mostly a figure without its own ID: 5 of P's 10 (2 of them a red flag's
     threshold) and 5 of C's 9 (4 of them a red flag's figure).
   - **The 100% payout threshold.** No pack ID holds it, so "below 100% from X" fails. It failed in 4 of the 6 uses
     in K0's and C's first outputs, and in 1 of P's 2.
   - **Gate false positives.** Two bind a year named earlier in the sentence to the next figure:
     - P's VRTX: "after the FY2024 … distortion";
     - P's DE: "lower than FY2024 and 5.6pp below the FY2023 high". This one made P's DE final output fail.
   - **The fixes:**
     - write "100% of free cash flow" into that red flag's text;
     - cite each flag's figures by their own IDs;
     - for C's prompt, leave the free-cash-flow-use slot empty when free cash flow is negative;
     - for the false positives, only a narrow gate fix proven by the replay and planted tests, for the reason in
       item 4.
   - **Why it matters for the wait:** p50 is about 10–11 s when fewer than half the analyses repair (§5.7).

**Before switching on** (REPORT.md §10, item 6, as it now stands):
- the founder's approval of the grounding rule;
- the peak-hour run, `eval-v2-peak`, now P and C (scheduled for 2026-10-27 06:05 UTC, not yet run), against p50
  10.5 s and p90 13 s;
- the per-attempt deadline above;
- the blind human pack (REPORT.md §9c), rebuilt on the adopted build's outputs. It has not been rated, and it holds
  Sonnet's analyses, not DeepSeek's.

The long-term-debt mapping in production's facts layer is a separate decision (REPORT.md §10, item 5; §4 here).

**How to measure the next round.**
- Prove each deterministic check by replaying it over every recorded output, with no model call. Release it only if
  it fails each recorded case and no true sentence.
- New generated runs at 10 companies and 2 runs cannot separate error rates of 3–5 per 1,000 (§5.2).

---

## Evidence

The analysis scripts and intermediate tables were working files of the session that wrote this plan. They
are not committed, because the probes they contain move into the harness, with unit tests, in step 0 of §3
(CLAUDE.md rule 12). Every instance above names its company, its sentence and its pack IDs, so it can be
re-checked against the committed records in `runs/` and the packs in `packs/`.

§5's three hand readings were made the same way, with no model call, and their working files are not committed
either. Each mislabel item and first-try failure they read is listed in its run's `REPORT.md` under "For hand
reading", with its company and its sentence; that list prints the sentence without its citation IDs, which are in the
run's `summary.json` and in the records under `runs/<label>/<arm>/`. The judge's verdicts and rationales are in
`runs/<label>/judge/`. §5 gives the class counts and names the false counted items and the errors it discusses; it
does not list every item's class.

**Opus spend in §3** is the rate billed through `claude -p`. It runs on the Claude subscription, not the
Anthropic API key.
