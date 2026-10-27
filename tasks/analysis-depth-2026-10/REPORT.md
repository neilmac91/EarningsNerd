# The AI trend analysis: depth, grounding, pipeline and model

Study of the "AI trend analysis" section of Multi-Period Analysis, October 2026. Branch
`claude/trend-analysis-depth-eval`. Nothing in production was changed: the proposed prompt, the gate and the
harness live under `backend/evals/trend_depth/` and `backend/prompts/trends-depth-analyst-agent.md`, and the
grounding rule waits for approval (`GROUNDING-RULE.md`).

## Summary

- **The section cannot be deep today, by construction.** Code writes every sentence it can contain, and
  the model only picks sentence IDs, under a prompt that forbids causes. Of 705 sentences in 40 reproduced
  analyses:
  - 42% restate a figure and 58% derive a comparison;
  - none states a cause and none is a judgement;
  - 96% of the numeric sentences contain no figure the metrics table beside them lacks.

  Changing the model alone cannot fix this.
- **The filings can support much more,** and the evidence can be assembled by code:
  - segment and product revenue from each 10-K's XBRL;
  - the cost lines and the margin bridge;
  - cash conversion, net cash and capital returns;
  - peer percentiles from our own facts store;
  - MD&A and note passages that state causes, each with a link to the paragraph on EDGAR.

  Three hand-written gold analyses, Regeneron, Snap and JPMorgan, show the target: 698, 647 and 649 words,
  every number reconciled by the gate, and 27 causes each tied to a quoted passage.
- **Proposed.** An evidence pack, a prompt that writes typed sentences (fact, comparison, cause,
  judgement) under a four-tier grounding rule, and a deterministic gate that reconciles every number before
  anything is shown. The gate allows one repair, then falls back to today's narrative. **The rule needs
  your approval before any production work** (`GROUNDING-RULE.md`).
- **Result, 20 companies, 10 of them held out:**
  - judges preferred the proposal to the current analysis 19–0 (Sonnet 5.5), 20–0 (Haiku 5.5) and 15–2
    (DeepSeek flash), each verdict surviving a position swap;
  - after at most one repair, every proposed output reconciled every number (the three as-run failures
    were gate errors, since fixed; §7.2);
  - a quarter of sentences now state a cause, and an auditor from another model family found 76–78% of
    those fully supported by the cited passage and 0–1% unsupported. The hand-written gold scored 70% and 0%.
- **Model: DeepSeek flash (founder decision, 2026-10-25).** It costs $0.007 a fresh analysis and takes about
  10 seconds. Claude Sonnet 5.5 was more accurate but is not adopted: $0.21 an analysis (about 30 times as
  much) and about a minute's wait.
  - DeepSeek's gap is narrower and more specific than the headline (`DEEPSEEK-ERRORS.md`):
    - 17 real first-try gate failures against Sonnet's 1 on the same prompt, 7 of them a correct figure
      cited without its own ID;
    - about 14 numbers said about the wrong metric, period or sign against Sonnet's 1, most invited by two
      pack gaps: no typical operating-cash-flow level, and net cash on one signed basis only;
    - almost no interpretation marked as judgement, after the frozen prompt dropped the words "one judgement"
      from the red-flag section;
    - equal support for its causes (76% for both).
  - The fixes are code, pack and prompt changes that cost no model call. They were built on 25–26 October and
    measured on 26 October: two development rounds, then two runs on the 10 held-out companies, all off-peak.
    The candidate ran beside the frozen prompt and beside the version-1 procedure this report describes, the
    same evening (`DEEPSEEK-ERRORS.md` §5). Pack version 2 with the frozen prompt (P) ran twice more on those
    companies afterwards. On the held-out half:
    - **The numbers said about the wrong metric, period or sign did not fall.** Read by hand, every build made
      3–5 per 1,000 verified claims: the candidate 3.6, P 5.1, the frozen prompt 3.4 and the version-1
      procedure 4.1. Sonnet made 1.4 in eval-v1.
    - **The code and pack fixes did what they were for, at today's cost and a shorter wait.** P stated no
      broken net cash as fact, and no probe-detected mislabel reaches a reader. Its p50 was 10.9 s and its p90
      12.1 s pooled, at $0.0066–0.0067 an analysis, against the version-1 procedure's 12.8 s, 17.8 s and $0.0071.
      By run, its p50 was 10.54 and 10.9 s, just over the plan's 10.5 s target in both. It wrote as many cause
      sentences as the frozen prompt; no judge read it. In DeepSeek's peak hours, one run on 27 October, its p50
      was 11.1 s and its p90 12.1 s, at twice the price.
    - **The candidate prompt fixed calibration but cost depth.** It brought judgement share, evaluative words and
      watch forecasts within their targets, and the judge preferred it to the frozen prompt overall, 10 pairs
      to 5. It also wrote fewer cause sentences than the frozen prompt in every run, 1.0 fewer per analysis on
      average and under the plan's guard, and lost depth in 9 of 20 pairs.
    - **First tries:** 40% of P's analyses and 45% of the candidate's passed without a repair (target 85%).
  - **Proposed (§10):** once the grounding rule is approved, adopt the code and pack fixes as measured, with a
    deadline on each DeepSeek call.
    - Two judgements are in this. The pack is kept although the plan's guard rule, read strictly, fires on it
      once, within the frozen prompt's own spread from run to run. And the backstops go on without the net-debt
      prompt line the plan paired them with (`DEEPSEEK-ERRORS.md` §5.10).
    - Hold the candidate prompt back, as the plan's guard rule requires. Either run one calibration round that
      keeps the guard, or adopt the prompt under a recorded exception.
    - Then add deterministic checks for the error classes that remain.
  - The judge evidence on Sonnet against DeepSeek (§7.6) stays on record. Opus preferred Sonnet 18–1, mostly
    on grounding and calibration.
    - On the deterministic calibration measures, the candidate is now within its targets, where Sonnet's
      eval-v1 outputs on the same held-out companies were: judgement share 11.6% (Sonnet 3.8%), evaluative
      words in data sentences 0.0% (2.6%), forecasts in watch items 0 (2 per 60). P, the proposed build, is
      within target on evaluative words (2.8% pooled), but not on judgement share (1.5%) or watch forecasts (10
      per 60).
    - On wrong-metric numbers and first-try passes, no build is.
    - No judge compared the candidate or P with Sonnet.
- **Still open:**
  - the founder's decision on the grounding rule, on the proposed build and on the candidate prompt (§10);
  - the next DeepSeek fixes (`DEEPSEEK-ERRORS.md` §5.10);
  - the blind human pack (§9c), which is built but not yet rated, and holds no DeepSeek analysis yet;
  - the long-term-debt mapping breaks in 6 of 20 packs, which probably also affect production's metrics
    table (a separate production decision);
  - the Gemini arm and the Claude API run were set aside with the decision.

## 1. How the analysis is produced today

The full map, with links to the code, is `PIPELINE.md`. In short:

- **Facts.** SEC companyfacts are normalised to 26 concepts and stored with "latest filing wins"
  (`facts/companyfacts.py`, `upsert_facts_bulk`). The dataset behind the page (`trend_analysis/dataset.py`)
  aligns up to ten fiscal years, adds growth, CAGRs and percentage-point changes, and numbers every value
  `F1…Fn`.
- **Generator input.** Code writes every sentence the analysis can contain, from about 15 templates
  (`observations.py`). The model, `deepseek-flash` (DeepSeek V4.1 Flash, thinking off, temperature 0.2, per
  ADR-0008 and `app/config.py`), sees only that catalogue of about 2,000 tokens and returns up to three IDs
  per section. Its prompt forbids it to "infer causes … or relationships". It sees no filing text, no MD&A
  and no segment data.
- **Citations.** `resolve_narrative_citations` renumbers `[F#]` to `[1]…[n]` and attaches each value's XBRL
  tag or formula. `scan_numeric_fidelity` checks the figure before each marker. Because code wrote the
  sentence, the check passes by construction.
- **Cost, latency, caching.** Measured over 45 reproduced runs: $0.0002 per fresh analysis at the off-peak
  list price ($0.0004 at peak), p50 1.9 s and p90 2.2 s for the whole stream. Results are cached per company,
  window and dataset fingerprint while `PROMPT_VERSION` (`trends-v7-observations`) is unchanged; a forced
  regeneration is metered against the 100-a-month fair-use cap.

## 2. What it says today

The census (`census/README.md`, `census/results.md`) reproduced 40 annual and 5 quarterly analyses
through the production code path and classified every sentence twice: once by template kind, and once
blind by an LLM labeller. Cohen's κ between the two was 0.72.

| Annual sentences (n = 705) | Restated figure | Derived comparison | Causal claim | Judgement |
|---|---|---|---|---|
| By template kind | 41.6% | 58.4% | 0.0% | 0.0% |
| Blind LLM labelling | 32.5% | 66.5% | 0.0% | 1.0% |

- 662 of 692 numeric sentences (95.7%) contain no figure that the metrics table on the same page lacks.
- Only 36.5% of sentences are there because the model chose them; code requires the rest.
- An analysis mentions 7.6 of the 19.4 series in its dataset on average, in 17.6 sentences.

The pipeline's output is a property of its templates. A better model cannot add depth while the model may
only pick among code-written sentences that are forbidden to state causes.

## 3. What the filings can support

`drivers/README.md` builds the driver tree for REGN, SNAP, JPM, COST and NVDA: revenue by segment or
product, then gross margin, the operating cost lines and operating margin, then net income, operating cash
flow and free cash flow. It adds a common-size view (`drivers/*-common-size.csv`). Every node is classed by
where its evidence comes from:

| Company | Structured XBRL | Structured, partial | Filing text only | Not available |
|---|---|---|---|---|
| REGN | 12 | 3 | 3 | 2 |
| SNAP | 14 | 1 | 4 | 1 |
| JPM | 8 | 1 | 5 | 0 |
| COST | 12 | 2 | 5 | 1 |
| NVDA | 15 | 1 | 2 | 2 |

The pattern holds across the five companies:

- **Structured facts cover:** product and segment revenue (from each 10-K's own XBRL dimensions), the cost
  lines, stock-based compensation, cash conversion, capex, net cash, buybacks and dividends.
- **Only the text has:** price against volume, guidance, the causes of any movement, and bank capital
  ratios.
- **Neither has:** unit metrics that the company does not tag.

Building this evidence found defects in the facts layer that the current page inherits:

| Defect | Evidence | Effect today |
|---|---|---|
| Recast and original figures sit side by side ("latest filing wins") | Regeneron FY2018–FY2019 revenue are the FY2020 10-K's recast figures; FY2017 was never recast | The table shows FY2018 revenue −12.4% and a 49.3% operating margin. As first reported, revenue grew 14.3%. This is the screenshot in the brief. |
| Proxy-statement (DEF 14A) net income replaces the 10-K's | 29 of 78 companies in the harness store (JPM FY2021–FY2025: $48.3B rounded against $48,334M) | Rounded or differently scoped net income, and the margins built on it |
| Insurers and managed care get no annual window | UNH, PGR, ELV, CI, HUM, TRV, ALL: their top line is ingested as premiums, and `has_core` wants revenue | No annual analysis at all for these companies |
| Long-term debt disappears after FY2020–FY2021 | `long_term_debt` maps only `LongTermDebtNoncurrent` and `LongTermDebt`. Chevron and ConocoPhillips have tagged `LongTermDebtAndCapitalLeaseObligations` since then, and Deere's recent 10-Ks carry neither tag | The table's long-term debt row goes blank. Debt and net debt built on it fall to the current portion: Deere's total debt reads $43.8B in FY2021 and $13.8B in FY2025. One proposed analysis repeated the figure (§7.4); Sonnet flagged the break for CVX and COP |
| Chubb's top line reads "Net interest income −$764.0M" | census | A wrong label on an insurer |
| XOM resolves to a new CIK with 27 facts | SEC ticker map | ExxonMobil's history is unreachable by ticker |

Reading 10-K text also needs three fallbacks the app's section parser lacks:

- MD&A in the annual-report exhibit (USB's EX-13);
- MD&A after Item 16 (Deere);
- older 10-Ks found only through companyfacts accessions (JPM).

## 4. Content specification and gold examples

`SPEC.md` specifies seven sections:

1. the arc, with inflection points and their stated causes;
2. growth drivers and operating leverage;
3. margins and the cost-line bridge, each move tied to a filing passage;
4. cash conversion;
5. net cash or debt and liquidity against peer percentiles from our own store, and capital allocation;
6. red flags ranked by severity and persistence;
7. what to watch, with thresholds anchored on cited levels.

It also sets profiles for banks, loss-makers and insurers, and a length of 450 to 700 words.

Three gold analyses were written by hand to that specification, using only stored facts and quoted 10-K
passages, each passage with its EDGAR location (`gold/`):

| Gold example | Words | Numbers verified by the gate | Cause sentences | Passages cited (outside the pack's selection) |
|---|---|---|---|---|
| Regeneron FY2016–FY2025 (operating) | 698 | 67 of 67 | 7 | 10 (6) |
| Snap FY2016–FY2025 (loss-maker) | 647 | 68 of 68 | 9 | 19 (7) |
| JPMorgan Chase FY2016–FY2025 (bank) | 649 | 75 of 75 | 11 | 21 (16) |

The last column is the main limit on depth that this study found. The passage selector (`passages.py`)
picks up to 90 passages per company by causal language, recency and inflection years. Writing the gold
examples needed passages it had not picked: a minority for Regeneron and Snap, and three quarters for
JPMorgan. A bank's causes live in segment and credit discussions that read less like "increased …
due to". The generators can only cite what the pack contains, so better passage selection would deepen
every model's output at once.

## 5. The grounding rule (proposal, awaiting approval)

`GROUNDING-RULE.md` proposes four tiers:

| Tier | Sentence | Must cite | Checked by |
|---|---|---|---|
| 1 | Fact: a filed or calculated figure | the figure's ID | gate: the number equals the cited value at its printed precision |
| 2 | Comparison: growth, change, share, ranking | its inputs, or the derived value | gate: the number equals a cited value or a derivation of cited values; direction and year must agree |
| 3 | Cause: why something moved | a 10-K passage that states it, plus the figure | gate: a passage is cited and every number reconciles; audit: the passage states the cause |
| 4 | Judgement: what it means | the figures it interprets | gate: no number that does not reconcile; shown to the reader as *Analysis* |

The gate (`backend/evals/trend_depth/factcheck.py`) parses every number with its unit, scale and
qualifier. It reconciles each one against the values the sentence cites, their pairwise derivations and
the figures printed in cited passages, and it checks the year and the direction word. Its rules are pinned
by 36 unit tests (`backend/tests/unit/test_trend_depth_factcheck.py`). In production it would sit where
`scan_numeric_fidelity` sits. A failure gets one regeneration that names the failed sentences, and a second
failure falls back to the current code-written narrative.

The gate checks numbers, not the words around them. "Revenue grew 8.3%", citing an 8.3% growth in cash,
would pass it. §7.4 measures how often that happens. **No part of the rule is implemented in production;
§10 lists what approval would authorise.**

## 6. How the models were evaluated

- **Companies.** 20 companies in ten sector pairs, one company of each pair for development and the other
  held out:

  | Sector | Development | Held out |
  |---|---|---|
  | Biopharma | REGN | VRTX |
  | Loss-making consumer tech and autos | SNAP | RIVN |
  | Banks | JPM | USB |
  | Retail | COST | TGT |
  | Semiconductors | NVDA | AMD |
  | Energy | COP | CVX |
  | Staples | PG | KO |
  | Industrials | CAT | DE |
  | Utilities | NEE | DUK |
  | Software | MSFT | ORCL |

  The prompt was tuned on development companies only (runs `dev-v1` to `dev-v4`). It was then frozen
  (sha256 `d558d371…`, recorded in every output) before any held-out output was generated. The window is
  the page's "Last 10" fiscal years.
- **Evidence.** One pack per company (`packs/*.json.gz`), built through the app's own SEC transports. A
  pack holds:
  - the page's dataset (`F`);
  - extended companyfacts lines, first-reported against latest (`X`);
  - 10-K XBRL disaggregation (`S`);
  - derived driver metrics, window levels and peer percentiles from the store (`D`);
  - up to 90 10-K passages with EDGAR text-fragment links (`P`);
  - ranked red-flag candidates (`R`);
  - data checks.

  With the prompt, a pack is 24,000 to 53,000 input tokens (mean 37,000).
- **Systems.**
  - `current`: the production pipeline end to end, `stream_trend_narrative` with deepseek-flash, over the
    same window and the same facts.
  - The proposed prompt on:
    - deepseek-flash (thinking off, temperature 0.2);
    - Claude Sonnet 5.5 (medium effort);
    - Claude Haiku 5.5 (low and medium effort);
    - Gemini 3.8 Flash (see the caveats: quota).
- **Gate and repair.** Every proposed output went through the gate. A failure got one repair call naming the
  failed sentences, exactly as the production proposal would. Both the first-try and the final results are
  reported.
- **Rubric judge, position-swapped.**
  - Every pair of systems was judged for every company, once with each draft first. A judge's verdict
    counts only when both orders agree; otherwise it is a tie, and the disagreement is reported as
    position bias.
  - No judge ever comes from the family of either output. Claude Opus 5.5 judges pairs without a Claude
    output, and DeepSeek V4 Pro judges pairs without a DeepSeek output.
  - For Claude-against-DeepSeek pairs the intended neutral judge, Gemini 3.8 Flash, was out of quota. Those
    pairs got a consensus panel instead: Opus and V4 Pro, each biased only toward its own side, with a
    verdict only when both agree. The two model-choice pairs (DeepSeek against Sonnet and against Haiku)
    also got a neutral judge: Google's Gemma 4 31B.
  - The judge reads both drafts in one neutral reader format (`readable.py`), with the sources list quoting
    every cited passage, beside the metrics table the reader sees.
- **Causal-support audit** (`causes.py`). For every cause sentence, an auditor reads the full text of the
  cited passages and labels the sentence supported, partial or unsupported. By default the auditor comes
  from a family other than the generator's. Because DeepSeek's outputs were then audited by Opus and
  Claude's by V4 Pro, every system was also audited by both auditors (`causes-by-*`) for a like-for-like
  comparison.
- **Semantic audit** (`semantics.py`). For every number the gate verified, an auditor sees the sentence and
  what the number was matched to, and says whether the sentence attributes the number to that metric and
  period. It is the check the gate cannot make.
  - Planted errors validated it: three sentences had a metric swapped (revenue relabelled as operating cash
    flow) and two had a year swapped. Together the gate and the audit caught all 11 affected claims: the
    gate caught 2, the audit 9.
  - Its flags are split deterministically into substantive, bound ("below 1.0x", true of the cited value)
    and ambiguous (two quantities with different labels match the number; a figure cited beside what the pack
    computes it from is one quantity, not two).
- **Cost and latency** are measured from every call's real token usage and wall-clock time. Cost is the
  API list price of the measured tokens, including any repair call.

## 7. Results

The full generated tables are `runs/eval-v1/REPORT.md` and `runs/eval-v1/summary.json`, both from
`python -m evals.trend_depth.report`. All 20 companies generated on every arm, with no failed generations.

### 7.1 The proposal against the current analysis

| Pair, all 20 companies | Proposal wins | Current wins | Tie or position split | Judged by |
|---|---|---|---|---|
| Sonnet 5.5 vs current | 19 | 0 | 1 | consensus of Opus and V4 Pro, both agreeing |
| Haiku 5.5 (low) vs current | 20 | 0 | 0 | consensus of Opus and V4 Pro, both agreeing |
| DeepSeek flash vs current | 15 | 2 | 3 | Opus (neutral) |

Each judge's own verdict needs both position orders to agree.

- **Held-out half:** Sonnet 10–0, Haiku 10–0, DeepSeek 7–1.
- **Depth, coverage and clarity:** Opus scored all three for the proposal on all 20 companies, for each of
  the three models.
- **Grounding is the exception.** Opus gave grounding to the current analysis on 19 of 20 companies against
  DeepSeek, 14 against Haiku and 13 against Sonnet. Code writes every current sentence, so it cannot be
  wrong; it also says almost nothing.

### 7.2 The fact-check gate

| System | Gate pass, first try | After one repair | Claims checked per analysis | Cause sentences per analysis | Words (max) |
|---|---|---|---|---|---|
| DeepSeek flash | 13 of 20 | 19 of 20 as run · **20 of 20** current gate | 73 | 7.0 | 618 (735) |
| Claude Sonnet 5.5 | 15 of 20 | **20 of 20** | 73 | 7.6 | 612 (656) |
| Claude Haiku 5.5, low effort | 9 of 20 as run · 12 current gate | 19 of 20 as run · **20 of 20** current gate | 68 | 7.2 | 578 (641) |
| Claude Haiku 5.5, medium effort | 13 of 20 as run · 14 current gate | 19 of 20 as run · **20 of 20** current gate | 69 | 8.3 | 600 (674) |

"Current gate" is the same outputs re-checked by the gate after four fixes made after the run. Each fix
removed a false positive, and each comes with a unit test:

1. a word claim ("nearly doubled") displaced the figures in year binding (found on SNAP, development);
2. "$18-19 billion" lost its scale (CVX, held out);
3. the noun "growth" was read as a direction word (TGT, held out);
4. "dropping below the 65.5%" is a level, not a fall (NVDA, development).

The gold examples and every development output were re-checked after each fix, and no fix introduced a new
failure. Two of the fixes were found on held-out companies, and the outputs themselves were never changed.
Every proposed output therefore reconciles every number after at most one repair. The first-try failures
were "matches nothing", period and direction errors (DeepSeek 10, Sonnet 5, Haiku-low 17, as run), plus two
DeepSeek cause sentences that cited no passage.

Per company, in the form first try → after repair · claims checked (fail counts are failed checks;
† = passes under the current gate):

| Company | Split | deepseek-flash | claude-sonnet-5-5 | claude-haiku-5-5-low | claude-haiku-5-5 |
|---|---|---|---|---|---|
| REGN | dev | pass → pass · 82 | pass → pass · 85 | pass → pass · 79 | pass → pass · 71 |
| VRTX | holdout | pass → pass · 62 | 1 failed → pass · 77 | pass → pass · 63 | pass → pass · 65 |
| SNAP | dev | pass → pass · 86 | pass → pass · 67 | 4 failed → FAIL (pass †) · 72 | 3 failed → pass · 67 |
| RIVN | holdout | pass → pass · 73 | pass → pass · 58 | 1 failed → pass · 67 | 1 failed → pass · 60 |
| JPM | dev | pass → pass · 61 | 1 failed → pass · 61 | 1 failed → pass · 66 | pass → pass · 64 |
| USB | holdout | pass → pass · 66 | 1 failed → pass · 70 | 1 failed → pass · 71 | pass → pass · 74 |
| COST | dev | pass → pass · 83 | pass → pass · 77 | 2 failed → pass · 68 | 1 failed → pass · 74 |
| TGT | holdout | 1 failed → pass · 74 | pass → pass · 70 | 1 failed → pass · 68 | 1 failed → FAIL (pass †) · 72 |
| NVDA | dev | 3 failed → pass · 77 | pass → pass · 75 | pass → pass · 64 | 1 failed → pass · 63 |
| AMD | holdout | 1 failed → pass · 82 | pass → pass · 88 | 1 failed → pass · 77 | pass → pass · 88 |
| COP | dev | pass → pass · 65 | 1 failed → pass · 62 | pass → pass · 61 | pass → pass · 59 |
| CVX | holdout | 4 failed → FAIL (pass †) · 64 | pass → pass · 76 | pass → pass · 64 | pass → pass · 79 |
| PG | dev | pass → pass · 83 | pass → pass · 86 | pass → pass · 71 | 1 failed → pass · 68 |
| KO | holdout | pass → pass · 69 | pass → pass · 74 | 2 failed → pass · 66 | pass → pass · 75 |
| CAT | dev | pass → pass · 75 | pass → pass · 80 | pass → pass · 65 | pass → pass · 71 |
| DE | holdout | pass → pass · 72 | pass → pass · 69 | 1 failed → pass · 64 | pass → pass · 64 |
| NEE | dev | pass → pass · 60 | pass → pass · 72 | pass → pass · 66 | pass → pass · 64 |
| DUK | holdout | 1 failed → pass · 71 | pass → pass · 75 | pass → pass · 78 | pass → pass · 72 |
| MSFT | dev | 1 failed → pass · 78 | pass → pass · 70 | 2 failed → pass · 67 | 1 failed → pass · 63 |
| ORCL | holdout | 1 failed → pass · 77 | 1 failed → pass · 72 | 1 failed → pass · 62 | pass → pass · 66 |

### 7.3 Do the cited passages state the causes?

Every cause sentence was audited against the full text of the passages it cites. Results are shown under
each auditor; * marks a system audited by its own family.

| System (cause sentences) | Opus 5.5: supported / partial / unsupported | DeepSeek V4 Pro: supported / partial / unsupported |
|---|---|---|
| DeepSeek flash (140) | 76% / 23% / 1% | 84% / 11% / 6% * |
| Claude Sonnet 5.5 (152) | 76% / 22% / 1% * | 75% / 20% / 5% |
| Claude Haiku 5.5, low (144) | 78% / 22% / 0% * | 82% / 12% / 6% |
| Gold examples (27) | 70% / 30% / 0% | 59% / 37% / 4% |

- **Causal faithfulness does not separate the models.** Under the same auditor, all three sit within a few
  points of each other and of the hand-written gold.
- **"Partial" is the common failing, not invention.** A typical partial: a passage that explains one year
  cited for a multi-year trend, or a passage that covers one of the two causes a sentence gives.
- **Opus is the more reliable auditor.** V4 Pro marked the gold sentence "SG&A gave back 2.0 points because
  charitable contributions … fell" unsupported because it read "gave back" as a cost rise. It also marks
  "partial" when a passage lacks a figure, though it was told to judge causation only.
- **The audit catches real misreadings.** Example: DeepSeek wrote that Deere's "production costs stayed
  unfavorable", and its cited passage says they "were favorable in 2024"; both auditors marked it
  unsupported.

### 7.4 Is each verified number said about the right thing?

The semantic audit asks, for each of about 1,450 verified claims per system, whether the sentence gives
the number the metric and period it was matched to.

| System | Substantive flags, Opus auditor | Substantive flags, V4 Pro auditor | Bound / ambiguous flags (Opus) |
|---|---|---|---|
| DeepSeek flash | 14 of 1,457 | 13 of 1,459 * | 9 / 5 |
| Claude Sonnet 5.5 | 5 of 1,458 * | 4 of 1,458 | 5 / 4 |
| Claude Haiku 5.5, low | 4 of 1,356 * | 5 of 1,356 | 9 / 3 |

DeepSeek gives verified numbers the wrong metric, period or sign about three times as often as either
Claude model, and that holds under DeepSeek's own-family auditor too. Reading all 28 of DeepSeek's flags:

- **The commonest error (4 companies)** compares the operating-cash-flow-to-net-income ratio with the window
  median of *free* cash flow to net income. The pack has no operating-cash-flow median, so the model took the
  nearest one.
- **Net cash and net debt signs.** "Net debt is 38.8% of revenue, better than the −35.6% peer median" (CAT)
  gets the comparison backwards.
- **Mixed periods.** One margin difference took the two margins from different years (DE).
- **Data rather than wording.** Three Deere flags restate correctly a pack value that is wrong: the
  missing long-term debt in §3. Sonnet's output for Chevron and ConocoPhillips noticed the same kind of
  break and flagged it; DeepSeek's did not.
- **Not errors.** Bound flags are true statements ("the current ratio of 0.55x is below 1.0x"). Ambiguous
  flags are numbers that two cited values both match (JPM's EMEA and Asia-Pacific both added 1.2pp).

Planted errors confirm what the audit can and cannot see (`runs/plant-sem/`). Revenue relabelled as
operating cash flow in three sentences was caught on all 7 affected claims, and year swaps were caught on
all 4. The gate alone caught 2 of the 11.

### 7.5 What the judges and the gate do not measure

- **Marking judgements.** The rule requires interpretation to be shown as *Analysis*:
  - DeepSeek typed 4 of 590 sentences (0.7%) as judgement, and wrote interpretive wording ("structural",
    "pressure", "cushion") into 5.6% of its fact and comparison sentences.
  - Sonnet typed 11.6% as judgement and left such wording in 2.6% of the others; Haiku-low 8.8% and 1.8%.

  A DeepSeek analysis therefore presents most of its interpretation as if it were data. The gate cannot see
  this, and it is the main reason Opus scored calibration for Sonnet over DeepSeek on 19 of 20 companies.
- **Unsigned falls.** "The three years to FY2025 show a 5.3% CAGR" (COP, DeepSeek) states a −5.3% CAGR as
  growth. The gate accepts it because no direction word or minus sign is present. A rule that fails such
  claims was tried and rejected here, because all six claims it flagged were false positives (for example,
  "Revenue declined three years running: 16.5% …"). It is listed as a gate follow-up.
- **Thin red flags.** Haiku-low's REGN analysis listed two red flags and missed the high-severity
  recast-revenue break that Sonnet and DeepSeek both reported.
- **Errors only a careful reader finds.** Opus's rationales name concrete errors in DeepSeek's drafts for
  all 8 of the first 8 companies read, among them a misread CAGR sign, an
  invented tariff-refund cause and a cause the passage contradicts. For 2 of the 8 they also name errors in
  Sonnet's drafts, such as causes their passages do not state (AMD) and segment passages applied firm-wide
  (JPM). Two of the DeepSeek errors were checked by hand and confirmed (§9d).

### 7.6 Choosing the model

| Evidence | DeepSeek flash | Claude Haiku 5.5 (low) | Claude Sonnet 5.5 |
|---|---|---|---|
| Beats current (judge) | 15–2 | 20–0 | 19–0 |
| Gate, first try / after repair (the gate at `b3ed8ef`, when this report was written) | 13 / 20 | 12 / 20 | 15 / 20 |
| Cause sentences fully supported (Opus) | 76% | 78% | 76% |
| Mislabelled numbers per 1,000 verified (both auditors) | 9–10 | 3–4 | 3 |
| Judgements marked as analysis | 0.7% of sentences | 8.8% | 11.6% |
| Opus judge, head to head with DeepSeek | — | Haiku 16–1 | Sonnet 18–1 |
| V4 Pro judge, head to head with DeepSeek | — | DeepSeek 4–0, 16 position splits | DeepSeek 4–0, 16 position splits |
| Gemma 4 31B (neutral), head to head with DeepSeek | — | pending (follow-up) | Sonnet 2, DeepSeek 2, 1 position split (5 of 20 so far) |
| API list cost per fresh analysis, repairs included | $0.007 | $0.019 | $0.21 |
| Latency p50 / p90 (linear between the two nearest ranks) | 10 s / 16 s | 88 s / 114 s | 56 s / 66 s |

- **The consensus panels tie** on every DeepSeek-against-Claude pair. That is not evidence of equal quality:
  V4 Pro, one of the two panel judges, agreed with itself across the position swap on only 50% of pairs,
  against Opus's 92%, so the panel can rarely agree.
- **The two judges that discriminate:**
  - Opus is a Claude-family judge with a possible self-preference, but its rationales cite checkable errors,
    and its preference rests on grounding and calibration, not on depth, where it rated DeepSeek against
    Sonnet a tie on 13 of 20.
  - Gemma 4 31B is the neutral check. At the time of writing it had given 5 valid verdicts on the 20
    DeepSeek-against-Sonnet pairs: Sonnet 2 (VRTX and COST), DeepSeek 2 (SNAP and RIVN) and 1 position split
    (REGN). Its USB reply, 2,710 output tokens and under the 4,000-token cap then in force, held no verdict
    the harness could read. The record kept only the reply's first 4,000 characters, so how it ended is not
    known. The pair is re-judged in the follow-up, which keeps each reply's head, tail and finish reason, and
    allows 16,000 tokens.
    That is too few to settle anything, and so far it does not show Opus's margin. The free tier answers
    slowly, with
    intermittent server errors, so the remaining pairs and the DeepSeek-against-Haiku pairs complete in the
    scheduled follow-up (§11), which updates this section.

  The objective measures above point the same way as Opus.
- **Sonnet against Haiku** was judged by V4 Pro only (Sonnet 2–0, 18 position splits), which does not
  separate them. On the objective measures they are close. Haiku is a tenth of the cost, but slower, because
  it spends 18,000–27,000 tokens thinking, and it needs a repair more often.

## 8. Cost and latency at volume

Measured per fresh analysis over 20 companies, at API list prices for the measured tokens, including repair
calls, each priced as a company's first analysis would bill (`records.api_cost`). Latency quantiles are linear
between the two nearest ranks (`records.quantile`); `runs/eval-v1/REPORT.md` still shows the nearest-rank values it
was written with (Sonnet 57 s / 65 s, for example):

| System | Per analysis | 1,000 a month | 10,000 a month | Latency p50 / p90 | Input / output tokens |
|---|---|---|---|---|---|
| Current (production) | $0.0002 | $0.19 | $1.94 | 1.9 s / 2.3 s | 2,000 / 270 |
| DeepSeek flash, proposal | $0.0068 | $6.83 | $68.33 | 10 s / 16 s | 50,000 / 2,400 |
| Claude Haiku 5.5 low, proposal | $0.019 | $18.55 | $185.51 | 88 s / 114 s | 80,000 / 21,000 |
| Claude Haiku 5.5 medium, proposal | $0.021 | $21.19 | $211.90 | 115 s / 157 s | 68,000 / 29,000 |
| Claude Sonnet 5.5, proposal | $0.21 | $207.32 | $2,073.17 | 56 s / 66 s | 64,000 / 7,900 |

- **DeepSeek** is priced at the off-peak rate. The peak rate (weekdays 01:00–04:00 and 06:00–10:00 UTC) is
  double: $0.014 per analysis.
- **Cache reads count only where a first analysis would get them.**
  - DeepSeek recorded $0.0056 an analysis, with 46% of its input read from cache. Some of those hits came
    from the development runs sending the same packs again, which a company's first analysis would not
    repeat. The table keeps two kinds of hit. A first request keeps the system prompt every company shares
    (1,920 tokens). A repair keeps the prefix it re-sends seconds after its own first pass, as a fresh
    analysis would. On the held-out half, which no development run touched, this rule gives exactly what the
    recorded calls cost at list price: $0.0070.
  - Claude reads nothing from cache: the harness's API request sets no cache breakpoint. Claude ran through
    `claude -p`, not the API (§11), and the CLI billed $0.28 a Sonnet analysis, because it writes a one-hour
    cache that a one-shot call never reads back.
  - The first draft priced every cache read at the cache rate, which put Sonnet at $0.18. A later draft
    priced Claude's CLI cache reads as ordinary input ($0.21) and kept every DeepSeek hit ($0.0056). With no
    cache at all, DeepSeek would cost $0.009.
- **Volume.** Analyses are cached per company, window and dataset fingerprint, so a fresh generation happens
  only on a company's first view in a window, after a new filing changes its facts, after a prompt version
  change, or on a forced regeneration (capped at 100 a user a month). The production analytics needed to
  estimate the real monthly count (PostHog `analysis_inference_cost`) were not available to this study.
- **Latency** is the bigger product change. The current page shows the analysis about 2 seconds after the
  request. The proposal holds the output until the gate has passed, so the reader waits the full generation:
  10 seconds with DeepSeek, about a minute with Sonnet. A progress state is needed either way, and background
  generation after each 10-K for watched companies would hide most of it.

## 9. Independent verification

**(a) Gate results per model, all 20 companies.** §7.2 has the table: first try and after the one repair,
with the claims checked per analysis. The gate's code is `factcheck.py` and its rules are pinned by
`backend/tests/unit/test_trend_depth_factcheck.py` (38 tests, one per failure class and per accepted form).
To re-check any output: `python -m evals.trend_depth.report --label eval-v1 …`, or `factcheck.check` on a
record's `output`.

**(b) Pairwise preference matrix, with position-swap agreement.** Every pair ran in both orders for all 20
companies, and a judge's verdict counts only when both orders agree.

| Pair (x vs y), 20 companies | Verdict used (x wins · y wins · tie or split) | Opus 5.5 | DeepSeek V4 Pro | Gemma 4 31B |
|---|---|---|---|---|
| Current vs DeepSeek flash | 2 · 15 · 3 (claude-opus-5-5 (20)) | 2 · 15 · 3 | not run (own family) | not run |
| Current vs Sonnet 5.5 | 0 · 19 · 1 (consensus of claude-opus-5-5 + deepseek-v4-pro (20)) | 0 · 19 · 1 | 0 · 20 · 0 | not run |
| Current vs Haiku 5.5 low | 0 · 20 · 0 (consensus of claude-opus-5-5 + deepseek-v4-pro (20)) | 0 · 20 · 0 | 0 · 20 · 0 | not run |
| DeepSeek flash vs Sonnet 5.5 | 2 · 2 · 16 (gemma-4-31b (5); consensus of claude-opus-5-5 + deepseek-v4-pro (15)) | 1 · 18 · 1 | 4 · 0 · 16 | 2 · 2 · 1 |
| DeepSeek flash vs Haiku 5.5 low | 0 · 0 · 20 (consensus of claude-opus-5-5 + deepseek-v4-pro (20)) | 1 · 16 · 3 | 4 · 0 · 16 | not run |
| Sonnet 5.5 vs Haiku 5.5 low | 2 · 0 · 18 (deepseek-v4-pro (20)) | not run (own family) | 2 · 0 · 18 | not run |

Position-swap agreement on the overall verdict: Claude Opus 5.5 92% of 100 pairs, DeepSeek V4 Pro 50% of 100,
Gemma 4 31B 80% of 5 pairs. Raw verdicts, both orders, with rationales: `runs/eval-v1/judge/<judge>/`.

**(c) Blind preference pack for finance-literate raters.** `human-pack/` holds the pack: the current analysis
against the proposed one for REGN, SNAP, JPM, COST and VRTX.
- **What raters get:** `index.html` (the metrics table and the two analyses as A and B, with each quoted
  passage linked to its 10-K paragraph) and `scoring-sheet.csv` (preference, then usefulness, trust after
  spot-checking two sources, and clarity, each 1–5, plus any statement the rater believes is wrong).
- **Blinding:** the A/B order is drawn from a random seed recorded only in the unblinding key. The key is
  kept outside this public repository, and its SHA-256 is in `human-pack/README.md`.
- **Which proposal:** the pack uses Sonnet 5.5, the recommended model.
  `python -m evals.trend_depth.human_pack --proposed deepseek-flash …` rebuilds it for DeepSeek.
- **Status:** not yet run. Two or three raters, about 45 minutes each.

**(d) Every causal claim in the three gold examples, with the EDGAR passage it rests on.**
`gold/CAUSES.md` has 27 cause sentences and 40 sentence–passage rows. Each row carries the filing, the
accession, the item and heading, a link that opens the 10-K at the paragraph (text fragment), the quoted
text, and the label an Opus auditor gave it: 19 supported, 8 partial, 0 unsupported.

Two of the errors the judge attributed to DeepSeek were checked by hand against the pack:
- COP's "5.3% CAGR" is the pack's −5.31;
- Deere's passage P16 reads "Production costs were favorable in 2024".

**(e) Held-out against development.**

| System | Split | Gate first try | Gate after repair | Substantive mislabels (Opus) | Causes supported (Opus) | Beats current |
|---|---|---|---|---|---|---|
| DeepSeek flash | dev | 8 of 10 | 10 of 10 | 5 | 82% | 8–1 |
| DeepSeek flash | held out | 5 of 10 | 10 of 10 | 9 | 71% | 7–1 |
| Claude Sonnet 5.5 | dev | 8 of 10 | 10 of 10 | 1 | 79% | 9–0 |
| Claude Sonnet 5.5 | held out | 7 of 10 | 10 of 10 | 4 | 74% | 10–0 |
| Claude Haiku 5.5, low | dev | 6 of 10 | 10 of 10 | 0 | 80% | 10–0 |
| Claude Haiku 5.5, low | held out | 6 of 10 | 10 of 10 | 4 | 77% | 10–0 |

Gate figures here use the current gate.

- **Every system did a little worse on held-out companies,** as it should, since the prompt was tuned on the
  development half.
- **DeepSeek dropped the most:** first-try passes fell from 8 to 5 and mislabels rose from 5 to 9. That
  suggests the prompt's instructions hold less robustly for it.
- **Verdicts against current did not change** between the halves.

## 10. Recommendation

1. **Pipeline.** Replace the observation catalogue with the evidence pack (§6) and let the model write the
   analysis under the four-tier rule. The order: build the pack, then generate, then run the gate, then at
   most one repair naming the failed sentences, then fall back to today's code-written narrative if the
   repair also fails. Nothing reaches the cache or the page before the gate passes. The pack's inputs come
   through the existing SEC transports and are cached per accession.
2. **Prompt and pack.** The proposed build keeps the frozen prompt (sha256 `d558d371…`, archived at
   `prompts/frozen-d558d371.md`) and moves to pack version 2 (`packs-v2/`). The pack's fixes, from
   `DEEPSEEK-ERRORS.md` §2:
   - add a typical operating-cash-flow-to-net-income level;
   - explain net debt in the pack's legend and red flags;
   - give the net-versus-operating margin gap within one year;
   - withhold net cash built on a broken debt series, behind a data check.

   Keeping the pack is a judgement. The plan's guard rule, read strictly, fires on it once: in one development round
   it wrote fewer cause sentences than the frozen prompt's pack in both runs, by amounts within that prompt's own
   spread from run to run. Over six runs the two match (`DEEPSEEK-ERRORS.md` §5.2).

   The backstop checks (item 4) are a second judgement. They go on without the candidate's net-debt prompt line,
   which the plan named among their conditions. Measured on P, the cost was two repairs in 20 analyses for
   backstop hits alone, and one repair that removed a minus sign but left net cash's direction
   (`DEEPSEEK-ERRORS.md` §5.10).

   **The candidate prompt is held back.** It is `backend/prompts/trends-depth-analyst-agent.md` (sha256
   `fc5b808c…`). It restores a judgement slot, words net debt without a minus sign and keeps the margin
   comparison within one year.
   - On the held-out half it met its calibration targets, and the judge preferred it to the frozen prompt overall,
     10 pairs to 5.
   - But it wrote fewer cause sentences than the frozen prompt in every run, 1.0 fewer per analysis on average, and
     fewer than the plan's guard of 6 in every run.
     The plan's pre-registered rule drops a fix that does that.
   - You choose between one calibration round that keeps the guard and adopting it under a recorded exception
     (`DEEPSEEK-ERRORS.md` §5.10).

   A prompt ships under a new `PROMPT_VERSION` only with your approval.
3. **Grounding rule.** The four tiers in `GROUNDING-RULE.md`, enforced by the gate in the request path. Add
   the causal audit and the semantic audit as a weekly sampled check, the way `backend/evals/RUNBOOK.md` runs
   the Copilot citation audit. They cost about $0.01 a sample with V4 Pro, or about $0.14 with Opus at API
   list price, and Opus is the better auditor. The Opus figure is an estimate: the CLI billed $0.18, which
   includes writing each prompt to a one-hour cache, and the eval-v1 audit records kept no token counts. **This needs your approval before any of it is built.**
4. **Model: DeepSeek flash (founder decision, 2026-10-25),** at $0.007 a fresh analysis and about 10 seconds.
   Claude Sonnet 5.5 was more accurate on these measures but is not adopted: about 30 times the cost and a
   minute's wait (§7.6, §8). The work now goes into DeepSeek's errors:
   - **Code in the repair loop and the gate** (no model call):
     - a clearer repair message (adding a figure's missing own ID by code was built, tested and removed: it let
       wrong numbers through, `DEEPSEEK-ERRORS.md` §2);
     - retype a figure-only "cause" sentence;
     - narrow gate fixes;
     - backstop checks for the remaining mislabels;
     - a patch-style repair that returns only the failed sentences.
   - **Pack and prompt fixes,** tested against the frozen baseline, with each half tested apart as well.
   - **Expected:** companies needing a repair would fall from 7 of 20 to 1–4, and mislabelled numbers from about
     14 to 2–4, at about the same cost.
   - **Measured** on the held-out half, two runs per build, all off-peak, with the version-1 procedure as the
     same-day control:
     - Repairs became shorter but not rarer. A patch takes about 2.5 s, against the control's full repair of 7 s.
       60% of P's analyses and 55% of the candidate's needed a repair, against the control's 50%.
     - Mislabelled numbers in the final text stayed about where the control's are. Read by hand, P had 7 in 1,364
       verified claims (5.1 per 1,000) and the candidate 5 in 1,405 (3.6), against the control's 3 in 735 (4.1).
       Each figure rests on a handful of sentences.
     - p90 fell to 11.4–12.8 s, from the control's 17.8 s, and the cost to $0.0065–0.0067. In peak hours, one
       run each on 27 October, p90 was 12.1 s for P and 13.3 s for the candidate, at twice the price.
   - **Next:** deterministic checks in place of the prompt lines the model ignored, first "above or below a
     reference level". Then the calibration round, the bank profile, period slips and net-debt signs.
   - **Evidence and plan:** `DEEPSEEK-ERRORS.md`, §5 for the results.
5. **Fix the facts-layer defects in §3 regardless.** They affect today's page:
   - recast rows beside first-reported ones;
   - proxy-statement net income;
   - no annual window for insurers;
   - the unmapped long-term debt tags (6 of 20 packs lose long-term debt partway through the window);
   - the XOM CIK.
6. **Before switching on:**
   - your approval of the grounding rule (item 3), and your decision on the candidate prompt (item 2);
   - a per-attempt deadline on each DeepSeek call, with one retry. 8 of 442 recorded calls waited out a 600 s
     client timeout (`DEEPSEEK-ERRORS.md` §5.7);
   - run the human pack (§9c), rebuilt on the adopted build's outputs.

   The held-out measurements are done: two runs each of the candidate, the frozen prompt and P, with nothing
   changed after the results were seen (`DEEPSEEK-ERRORS.md` §5.2). So is the peak-hour latency run
   (`eval-v2-peak`, 27 October, one run each): P's p50 11.1 s and p90 12.1 s, the candidate's 10.9 s and 13.3 s,
   against 10.5 s and 13 s, about as off-peak (`DEEPSEEK-ERRORS.md` §5.7).

   The Claude API run (`eval-v2-api`) and the Gemini arm were set aside with the decision. The harness keeps
   both paths.

What approval would authorise is listed at the end of `GROUNDING-RULE.md`. Nothing in production has
changed.

## 11. Caveats

- **Claude through the CLI.** No `ANTHROPIC_API_KEY` was available to this session, so every Claude call went
  through `claude -p` on the logged-in subscription (the repository's judge pattern). Costs are list prices for
  the measured tokens. Latency includes the CLI's start-up, and `--effort` stands in for the API's thinking
  settings.
  - **The API path is built and checked.** It was verified offline against the real SDK (`anthropic` 2.3.0)
    through a mock transport, including streams that fail after they start, then reviewed independently four
    times for request validity, cost accounting and spend safety. It is pinned by
    `backend/tests/unit/test_trend_depth_{providers,records,stages}.py`. The tests that drive the real SDK run
    wherever it is installed, as in the harness's environment; CI does not install it and skips them.
  - **Spend is capped.** Every Claude API attempt goes to a spend ledger (`runs/spend.jsonl`); calls on other
    backends are logged when they return, and the production pipeline's (`current`) are not. Each attempt
    reserves its worst case there before it is sent, and is sent only if that fits under
    `TREND_DEPTH_ANTHROPIC_CEILING_USD` (default 75). A stream that fails after it starts is logged at its
    worst case (a reply whose `message_delta` had arrived is whole and is kept at its own cost), and an attempt
    stopped before its cost is on disk leaves its reservation counted, so the ledger can overstate spend but
    not understate it. One harness process at a time may spend on the key. A session in another
    checkout keeps a ledger of its own, so a spend limit on the key in the Anthropic Console is the stop that
    covers every session.
  - **The run starts when the key is set.** It needs `ANTHROPIC_API_KEY` in the environment.
- **Gemini partly missing.** The Gemini key is on the free tier: Pro and Gemini 4 Argon have no quota, and
  Gemini 3.8 Flash allows 20 requests a day. The Gemini 3.8 Flash arm generated only REGN, in a development
  run, before the quota ran out, so it is not in the comparison. A follow-up session is scheduled for 07:20 UTC
  on 25 October to generate its 20 companies over one or two days of quota, judge it against the other
  systems, and update this report. Gemma 4 31B, from the same free tier, stood in as the neutral judge; it
  had given 5 valid verdicts of its 40 pairs when this report was written, and the follow-up completes it.
- **Self-preference.** No judge from outside both families was available at full strength for the
  DeepSeek-against-Claude pairs. Opus's preference for Claude outputs may include self-preference. §7.6
  weighs it against the objective measures, which do not depend on a judge, and against Gemma.
- **Census reproductions.** The census reproduced production through its code path on a local copy of the
  facts. It did not read production rows, and no production logs or analytics were available.
- **Evidence quality bounds every model.** Passage selection missed most of the passages the bank gold
  example needed (§4). The packs inherit the facts-layer defects, and the missing Deere debt misled DeepSeek
  in §7.4.
- **The gate checks numbers, not meaning.** Its known gaps are counts of periods ("four years running"),
  unsigned falls, and attribution, which the semantic audit measures.
- **Twenty companies.** Differences of one or two companies in a split are noise. The robust results are
  proposal against current, the gate's after-repair pass rate, and DeepSeek's higher mislabel rate, which
  holds under both auditors and in both splits.

## 12. Re-running

`backend/evals/trend_depth/README.md` has the commands. In short:

1. `generate` with a new label;
2. `judge`;
3. `causes` and `semantics`;
4. `report`.

Packs and outputs are committed, so a prompt change re-runs against the same evidence, and the report puts
the development and held-out halves side by side. The README's "Claude through the API" section is the
`eval-v2-api` plan, step by step with its cost. A full run like `eval-v1` cost about USD 42. Total
spend for this study was about USD 53: USD 42.3 for `eval-v1` (judging 24.2, audits 11.5, generation 6.6),
USD 9.6 for the development runs and USD 0.6 for the census labelling. The Gemma judge and the Gemini
arm run on the free tier.
