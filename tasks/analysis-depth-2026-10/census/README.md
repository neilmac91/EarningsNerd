# Census of the current "AI trend analysis" section (Multi-Period Analysis), 2026-10-24

A diagnosis census of what the CURRENT pipeline writes: 40 annual analyses plus 5 quarterly ones, each
reproduced through the production code path, with every sentence classified two independent ways.

**What these are:** reproductions through the production code path at commit `a41c6e4`
(`trend_analysis.narrative.stream_trend_narrative(..., force=True)`, `PROMPT_VERSION = trends-v7-observations`,
production model `deepseek-flash` at `https://api.deepseek.com/v1` through the app's own `openai_service`). The
facts come from a local SQLite store filled by the production companyfacts ingest (`normalize_companyfacts` ->
`upsert_facts_bulk`), using live SEC companyfacts fetched through the app's SEC transport on 2026-10-24.

**What these are not:** rows read from the production `trend_analyses` table (this session has no production DB
access). Production facts can also include per-filing XBRL extraction, so a few values, and occasionally a whole
series, may differ from what production would show for the same company and window.

Script: `backend/evals/trend_depth/census.py` (`run` -> `classify` -> `label` -> `report`; usage in its docstring).

## Method

1. **Companies.** `companies.census_companies()` gives 40 companies (20 eval + 20 extra). Failures were replaced from
   the same `PEERS` group until 40 annual analyses succeeded. See "Failures and substitutions" below.
2. **Window.** Annual mode uses the UI's "Last 10" window: `PeriodPicker.latestRange`, in which years without core
   data count toward the cap of 10. This deliberately departs from `bootstrap.latest_annual_window`. That function
   takes the newest ten *core* years, so a gap year makes the range span more than ten fiscal years. In the first
   pass that broke NEE (FY2011..FY2025, 15 years) and DUK (FY2015..FY2025, 11 years), and `build_dataset` refused
   both ("Too many periods selected"). A production user clicking "Last 10" would have received FY2018..FY2025 and
   FY2016..FY2025. Those are the only two companies whose window differs. Quarterly mode uses the UI's "Last 12"
   (the newest 12 quarters).
3. **Generation.** Each run consumed the event stream as the router does. The router's own metering and PostHog
   call were not executed, but the complete event's `usage` is exactly what the router hands to PostHog. Ingest ran
   3 companies at a time. Streams ran one at a time, so no other run's synchronous DB work shared the event loop
   during a measured stream. Three in-process wrappers on `trend_analysis.narrative` recorded what each run used:
   the dataset (`build_dataset`), the catalogue (`build_observation_catalogue`), and every raw model reply with its
   validated selection (`parse_observation_selection`). No file under `backend/app` was changed.
   `ai_metrics.observe_ai_calls()` captured each provider call's `ai_call` record. These runs were labelled trigger
   `eval`; production labels them `user`.
4. **Sentences.** Each narrative line under a `## ` heading is one rendered observation. A line splits into
   sentences at `. ` followed by a capital letter, so a red-flag signal line yields a detail sentence plus its
   `Source operands: …` tail. Every line was matched back to its catalogue observation by text, with citation
   markers stripped and the production display formatting re-applied (`compact_narrative_text` with the
   narrative's currency precision plan), in the production renderer's order. **785 sentences in 45 narratives; 0
   unmatched.**
5. **Two independent labellings.**
   - (a) **Deterministic:** each sentence's template kind maps to a class through the fixed table below.
   - (b) **Blind LLM:** Claude Sonnet (served as `claude-sonnet-5-5`) labels sentences through the repo judge's CLI
     invocation (`claude -p --model sonnet --output-format json --system-prompt <rubric> --tools ""
     --strict-mcp-config --no-session-persistence`, input on stdin, run from a temp dir, billing env vars
     removed). There is one call per narrative. The labeller sees the numbered sentences and their section
     headings, but never template kinds or IDs, and must return strict JSON. The rubric is `LLM_RUBRIC` in the
     script and uses the same class definitions as below.
   - The template table was fixed before the full labelling run. Three test narratives were labelled first to
     measure cost; their one systematic disagreement (`watch_next.metric`) was visible then, and the table was
     not changed.

## Class definitions

Exactly one primary class per sentence. When a sentence mixes classes, the highest present wins:
causal_claim > judgement > derived_comparison > restated_figure.

| Class | Definition |
|---|---|
| `restated_figure` | States one stored or calculated value at one point or period: a level, margin, ratio or per-share amount. A plain list of such values that asserts no relation also counts, as does a statement that a value is unavailable. |
| `derived_comparison` | Relates two or more values. That covers a growth rate or pp change between periods, a **CAGR** (decision: it relates the window's two endpoint values, so it is the same kind of claim as a growth rate), an above/below/equal ordering, a threshold comparison, or a multi-period sequence. |
| `causal_claim` | Asserts why something happened: a reason, driver or mechanism. |
| `judgement` | Evaluates or interprets: good/bad, quality, risk, sustainability, outlook or forecast, advice-like language. |

Secondary flags: `directive` marks "Watch …" sentences and `missingness` marks "not available" / "Not enough data" sentences.

### Template -> class table (deterministic method)

| Template (`section.kind`) | Example (rendered) | Class | Flag |
|---|---|---|---|
| `trajectory.latest` | Revenue was $14.3B in FY2025. | restated_figure | |
| `trajectory.first` | The earliest available revenue observation was $3.4B in Q3 2023. | restated_figure | |
| `trajectory.cagr` | Revenue CAGR was +12.8% over FY2016..FY2025. | derived_comparison | |
| `growth_quality.growth` | Revenue growth in FY2025 was +1.0%. | derived_comparison | |
| `growth_quality.comparison` | In FY2025, net income growth of +2.1% was above revenue growth of +1.0%. | derived_comparison | |
| `growth_quality.latest-eps` | EPS (basic) was -$0.10 per share in Q2 2026. | restated_figure | |
| `margins.latest` | Operating margin was 24.9% in FY2025. | restated_figure | |
| `margins.change` | Operating margin changed -3.2pp in FY2025. | derived_comparison | |
| `cash_balance_sheet.level-comparison` | In FY2025, free cash flow of $4.1B was below net income of $4.5B. | derived_comparison | |
| `cash_balance_sheet.latest` | Cash & equivalents was $343.3B in FY2025. | restated_figure | |
| `cash_balance_sheet.ratio-threshold` | The current ratio was 4.13× in FY2025, above 1.00×. | derived_comparison | |
| `*.selected-gap` | Gross margin is not available in this selected dataset for FY2025. | restated_figure | missingness |
| section fallback (no observation) | Not enough data is available for this section in the selected periods. | restated_figure | missingness |
| `red_flags.signal.*` detail (5 detectors) | Operating margin compressed 5.9pp over three periods: 30.9% → 28.1% → 24.9%. | derived_comparison | |
| `red_flags.signal` operand tail | Source operands: Operating margin 30.9% in FY2023; … | restated_figure | |
| `red_flags.no-signals` | No trend flags detected in the selected data. | derived_comparison (every threshold test negative) | |
| `watch_next.growth` | Watch whether revenue growth in the next reporting update improves from +1.0% in FY2025. | derived_comparison | directive |
| `watch_next.level`, `watch_next.metric` | Watch how free cash flow in the next reporting update compares with $4.1B in FY2025. | restated_figure (one stated figure; the other side does not exist yet) | directive |

The operand tail is a sentence in the `narrative` text, which is also what the PDF export renders. The web UI renders
it as a "Figures behind this finding" list via `narrative_presentation.evidence`, so the results are shown with and
without tails. No template asserts a cause. The FCF/NI divergence detail ("… — earnings and cash are diverging.") is
the only template with an interpretive clause, and it was mapped to derived_comparison.

## Results — 40 annual analyses, 705 sentences

### Headline proportions

| Method | Sentences | restated_figure | derived_comparison | causal_claim | judgement |
|---|---|---|---|---|---|
| Deterministic (template) | 705 | 41.6% (293) | 58.4% (412) | 0.0% (0) | 0.0% (0) |
| Blind LLM | 705 | 32.5% (229) | 66.5% (469) | 0.0% (0) | 1.0% (7) |
| Deterministic, without operand tails | 658 | 37.4% (246) | 62.6% (412) | 0.0% (0) | 0.0% (0) |
| Blind LLM, without operand tails | 658 | 27.7% (182) | 71.3% (469) | 0.0% (0) | 1.1% (7) |

Flags: 115 directive sentences (16.3%) and 5 missingness sentences, identical under both methods (kappa 1.0 for
each flag).

### By section

| Section | Sentences | Det: restated / derived / causal / judgement | LLM: restated / derived / causal / judgement |
|---|---|---|---|
| The trajectory | 118 | 67.8% / 32.2% / 0 / 0 | 67.8% / 32.2% / 0 / 0 |
| Growth quality | 131 | 1.5% / 98.5% / 0 / 0 | 4.6% / 95.4% / 0 / 0 |
| Margins | 113 | 57.5% / 42.5% / 0 / 0 | 57.5% / 42.5% / 0 / 0 |
| Cash & balance sheet | 126 | 19.1% / 81.0% / 0 / 0 | 19.1% / 81.0% / 0 / 0 |
| Red flags | 102 | 46.1% / 53.9% / 0 / 0 | 52.9% / 40.2% / 0 / 6.9% |
| What to watch next | 115 | 65.2% / 34.8% / 0 / 0 | 0.0% / 100.0% / 0 / 0 |

### By profile

| Profile (companies) | Sentences | Det: restated / derived / causal / judgement | LLM: restated / derived / causal / judgement |
|---|---|---|---|
| operating (32) | 578 | 40.7% / 59.3% / 0 / 0 | 30.8% / 68.2% / 0 / 1.0% |
| loss_making (3: SNAP, RIVN, BA) | 59 | 44.1% / 55.9% / 0 / 0 | 32.2% / 66.1% / 0 / 1.7% |
| bank (4: JPM, USB, BAC, GS) | 56 | 46.4% / 53.6% / 0 / 0 | 42.9% / 57.1% / 0 / 0 |
| insurer (1: CB, substitute for PGR) | 12 | 50.0% / 50.0% / 0 / 0 | 66.7% / 33.3% / 0 / 0 |

### Agreement between the two methods

| Scope | n | Cohen's kappa (class) | Raw agreement | Kappa without `watch_next.metric` |
|---|---|---|---|---|
| Annual | 705 | **0.723** | 86.8% | 0.939 |
| All (annual + quarterly) | 785 | 0.714 | 86.2% | 0.925 |

The 93 annual disagreements break down as follows:
- **75** `watch_next.metric`: "Watch how X … compares with $Y in FY2025." The LLM reads "compares with" as a
  comparison (derived), while the table treats it as one stated figure. This is a definitional ambiguity, not a
  labelling error by either side.
- **8** `red_flags.no-signals`: the LLM said restated_figure 7 times and judgement once.
- **6** `red_flags.signal.fcf-ni-divergence`: the LLM labelled judgement because of "earnings and cash are
  diverging". Under the precedence rule this is defensible. If counted that way, deterministic judgement would be
  6/705 (0.9%).
- **4** `growth_quality.growth` sentences labelled restated_figure by the LLM. The other 77 growth sentences were
  labelled derived.

The LLM's 7 judgement labels are exactly those 6 FCF/NI divergence sentences plus 1 "No trend flags detected".
Neither method found a causal claim.

### Other measures (annual)

| Measure | Value |
|---|---|
| Sentences containing any cause word (because, due to, driven by, reflect*, impact*, contribut*, since, amid, …; regex `CAUSE_WORDS`) | **0 of 705** (0 of 785 in all modes) |
| Mean sentences per analysis | 17.6 (range 12–22) |
| Mean distinct metrics mentioned per analysis | 7.6, of a mean 19.4 series in the dataset |
| Restated figures whose value is a cell of the "Metrics by period" table | 288 of 705 sentences (40.9%), i.e. every numeric restated figure |
| Numeric sentences stating no figure the metrics table lacks | 662 of 692 (95.7%) |
| … the 30 that do | debt-build total growth (18), margin-compression pp total (6), FCF/NI conversion ratios (6) |
| Restated figures visible in the KPI strip | 151 of 705 (21.4%) |
| Numeric sentences stating no figure the KPI strip lacks | 222 of 692 (32.1%) |

**Page placement.** On the results page the "Metrics by period" table renders directly *below* the narrative pane
(`AnalysisPageClient.tsx`). *Above* the narrative are the KPI strip, the data notes and the trend charts. The
visibility test uses the rendering rules at this commit:
- `MetricsTable.tsx`, default "All" window: every series × period value, the change under it (YoY in annual mode;
  in quarterly mode QoQ wherever a QoQ exists), and the annual CAGR column for non-percent series.
- `KpiStrip.tsx`: the latest top line, net income, FCF and net margin, with CAGR / window pp (annual) or YoY
  (quarterly).

Charts are not counted. The test is computed from the template structure and the cited points, not by rendering the
page.

### Selector behaviour (the model's only job)

| Measure (40 annual runs; 45 runs gave the same picture) | Value |
|---|---|
| Invalid-selection retries | **0 of 40** (0 of 45 in all modes); no stream errors |
| Runs with all six lists empty | 0 |
| Runs with no optional pick at all | 0 |
| Sections returned empty | margins in 5 runs: the 4 banks and CB, which have no margin series and render "Not enough data …" |
| IDs returned per run | 15.7 on average: 9.3 required IDs (redundant, since required items always render) + 6.4 optional |
| Optional candidates per run | 26.7 (catalogue 36.6 observations on average) |
| Rendered observations per run | 16.3: required 396 (60.6%), model-selected 257 (39.4%), fallback 0 |
| Optional picks by kind (picked / offered) | watch metric 75/104, growth comparison 48/256, margin change 48/228, OCF-vs-NI 34/40, other margin level 25/44, balance-sheet level 24/151, EPS 2/40, older-period growth 1/160, earliest top-line value **0/40** |

At the sentence level, 257 of 705 annual sentences (36.5%) exist because the model picked them. The rest are required
observations, deterministic signals with their operand tails, or section fallback text.

Run-to-run stability (side measurement): the census was generated twice about 1.5 minutes apart because of the window
fix. For the 42 runs whose window and catalogue were identical in both passes, the model's selection was identical in
15 and the rendered narrative text in 19 (temperature 0.2). The first-pass rows are not kept in this directory.

### Annual vs quarterly (same 5 companies: REGN, SNAP, JPM, COST, CB)

| | Annual | Quarterly |
|---|---|---|
| Mean sentences | 16.2 | 16.0 |
| Det: restated / derived | 44.4% / 55.6% | 47.5% / 52.5% |
| LLM: restated / derived / judgement | 38.3% / 61.7% / 0 | 43.8% / 53.8% / 2.5% |
| Numeric sentences fully visible in the metrics table | 97.4% | 59.2% |
| Red-flag signals rendered | 3 | 4 |
| Sentences carrying "(derived Q4)" | 0 | 17 |

In quarterly mode every growth sentence states YoY (vs the year-ago quarter), but the table shows QoQ under each
cell wherever QoQ exists. The narrative's growth figures are therefore mostly absent from the table, though the
KPI strip shows the latest headline YoY.

## Cost and latency

| Measure (40 annual runs; one provider call each) | Value |
|---|---|
| Prompt tokens | mean 2,049 (1,415–2,630); cache hits mean 1,782, misses mean 267 |
| Completion tokens | mean 265 (196–292); `reasoning_tokens` null on every call (thinking disabled) |
| Logged `estimated_cost_usd` per analysis | mean **$0.00020** (range $0.000142–$0.000462); all off-peak (`peak: false`, Saturday 2026-10-24 20:26–20:27 UTC) |
| Same tokens in the peak window (×2.0) | mean $0.00041 |
| Total for the 40 annual runs | $0.0082 off-peak ($0.0164 at peak); all 45 runs $0.0093 |
| Uncached worst case (all prompt tokens at the miss price) | about $0.00047 off-peak per analysis |
| Total stream latency | p50 **1.88 s**, p90 **2.17 s** (max 4.56 s, the first run) |
| Dataset assembly (local SQLite) | p50 0.19 s, p90 0.43 s |
| Model phase wall clock (catalogue + call + parse) | p50 1.63 s, p90 1.82 s |
| Provider call `latency_ms` | p50 1,631 ms, p90 1,811 ms |
| First token | p50 380 ms, p90 441 ms |

**What production logs for one analysis.**
- One `ai_call` JSON log line per physical provider call (`ai_metrics.record_ai_call`). It carries
  `operation: analysis_chat`, `provider: primary`, `trigger: user`, the requested and actual model
  (`deepseek-flash`), `system_fingerprint`, `outcome`, `latency_ms`, `first_token_ms`, and `usage` (prompt,
  completion, total, cache hit, cache miss and reasoning tokens). It also carries `estimated_cost_usd` and `peak`,
  priced by `llm_pricing.estimate_call_cost_usd` with the per-model `deepseek-flash` rates (0.003 / 0.15 / 0.60 per
  1M, equal to the Settings constants), ×2.0 in the UTC 01–04 and 06–10 weekday windows.
- The complete event's `usage` is the `merge_chat_usage` sum over calls plus `model` and `estimated_cost_usd`. The
  router sends it to PostHog as `analysis_inference_cost` (`cost_usd = usage.estimated_cost_usd`) for every fresh
  completion.
- Every record is in `runs.jsonl` (`ai_calls`, `complete.usage`, `cost`).

**Harness spend.**
- DeepSeek: about $0.03 across both census passes and the tests (about 100 calls). The first pass cost $0.018
  for 44 calls with a colder prompt cache; the final pass cost $0.0093 for 45.
- Claude CLI labelling: $0.5752 for the 45 narratives (45 calls, $0.004–$0.016 each), plus $0.046 for tests. Total
  about **$0.62**, against a $6 ceiling. The projection after the first three narratives was $0.47.

## Failures and substitutions

| Company | Mode | Outcome | Reason |
|---|---|---|---|
| XOM | annual | failed -> **COP** | The SEC ticker map now resolves XOM to CIK 2115436 ("ExxonMobil Holdings Corp", a new registrant). Its companyfacts hold 27 facts, all from Q2 2026, so no fiscal year has core data. |
| UNH | annual | failed -> ELV, CI, HUM also failed -> **CVS** | SIC 6324. No fiscal year has `revenue` or `net_interest_income`, because the top line ingests as `premiums_earned`. The coverage rule `has_core` therefore disables every annual year. |
| PGR | annual | failed -> TRV, ALL also failed -> **CB** | SIC 6331, same cause (`premiums_earned` top line). |
| PLD | annual | failed -> **SO** | SIC 6798 (REIT). No `revenue` or NII fact (only net income and operating income). SO comes from PLD's `PEERS` group, which is "utilities" in `companies.py`. |
| PGR | quarterly | `not_enough_data` -> **CB** | Same cause. CB was used because it has an annual run. |

None of these is a harness artifact. Each is what the production code path does with the facts the production
ingest builds. Production could differ only if per-filing XBRL extraction supplies a revenue fact, or, for XOM, if
the production `companies` row still carries the old CIK (34088) from before the ticker map changed. Neither can be
checked from here.

## Observations made while reading the outputs

- **CB's top line is a negative "net interest income".** "Net interest income was -$764.0M in FY2025", followed by
  a growth rate on it. For an insurer this is almost certainly a mis-mapped concept, and it is the only insurer in
  the census, so the insurer profile row is effectively this one company.
- **Some amounts are not compacted.** 41 sentences in 25 narratives carry the full form "USD 8,884,000,000". 30
  of them are operand tails, which are never compacted on the wire. The other 11 are prose sentences where the
  currency precision plan kept full precision because two different amounts (for example FCF $8.918B and NI
  $8.884B) would display identically.
- **Content is fixed by the templates.** Every sentence is a code-rendered template. The selector's choices only
  vary which of about 27 optional templates appear. Within this design, no sentence can explain a cause or offer
  an interpretation beyond the deterministic red-flag wording.

## Caveats

- These are reproductions through the production code path at this commit, with the production model ID, against
  a local facts store built from live SEC companyfacts. They are **not** rows read from the production
  `trend_analyses` table. Production facts can also include per-filing XBRL extraction, so a few values may differ
  from production.
- Each company has one sample. The selection varies run to run (see stability above), so per-company narratives
  are draws, not fixed outputs. Proportions are stable mainly because about 60% of sentences are required.
- Latency was measured from this container with a local SQLite store, sequential runs, and a warm DeepSeek prompt
  cache, since back-to-back runs share the system prompt. Production assembly reads Postgres on Cloud Run, and the
  first call after a cache expiry pays the miss price on about 2k tokens. Cost was logged off-peak; on a weekday in
  a peak window it doubles.
- The LLM labelling is a single labeller (Sonnet) in a single pass. It shares the class definitions, so kappa
  measures how the definitions are applied, not whether they are right. Most of the disagreement is one ambiguous
  template.
- The profile groups are small: insurer 1 company, loss-making 3, banks 4.
- The cause-word count is a lexical screen. The LLM labelling is the semantic check, and it found no causal claims
  either.
- `runs.jsonl` is 2.7 MB because each complete event is kept whole, including citation provenance and
  `narrative_presentation`.

## Files

- `runs.jsonl`: one row per run, failures and substitutions included (55 rows; 45 succeeded). Each row holds the
  window, timings, `ai_calls` records, `cost`, raw model replies (`attempts`), the validated `selection` and
  `selection_stats`, the full `catalogue` (ID, section, required, markdown), the `rendered` order with each
  observation's origin, a compact `table` of the dataset as the page shows it, and the whole `complete` event.
- `narratives/<TICKER>-<mode>.md`: the rendered narrative and its sources list (45 files).
- `sentences.jsonl`: one row per sentence, with template, deterministic class, flags, cause words, cited concepts
  and table/KPI visibility.
- `llm_labels.jsonl`: one row per narrative, with the blind labels, the exact sentences labelled, and the CLI's
  reported cost and usage.
- `results.json` / `results.md`: every number above, generated by `python -m evals.trend_depth.census report`.
