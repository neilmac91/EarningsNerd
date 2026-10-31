# How the AI trend analysis is produced today (main at a41c6e4)

This is a map of the current pipeline, from the facts up, with each link to the code that implements it.
The measurements come from the census (`census/README.md`): 40 annual and 5 quarterly analyses
reproduced through the production code path. Every claim about production configuration below is read
from the repository. This session had no access to the production database, logs or PostHog.

## 1. Raw facts

- **Source.** SEC companyfacts (`data.sec.gov/api/xbrl/companyfacts`), fetched through
  `app/services/facts/transport.py` with the shared SEC rate limiter. Per-filing XBRL extraction
  (`app/services/edgar/xbrl_instance.py`) also writes facts when a filing summary is generated.
- **Normalisation.** `app/services/facts/companyfacts.py::normalize_companyfacts` maps us-gaap tags to 26
  standardized concepts (`app/services/facts/concepts.py`). Each concept takes a priority list of tags,
  merged per period, so that for each period the first tag with a value wins. Annual (10-K, 320–390 day)
  and discrete-quarter facts are kept; Q4 values are derived from annual less the first nine months.
  Banks and insurers (SIC 6000–6799) skip the generic revenue tags and carry net interest income,
  noninterest income, premiums earned and net investment income instead.
- **Storage.** `financial_fact`. `upsert_facts_bulk` keeps the **latest-filed** value per (concept,
  period end, fiscal period, unit) as `is_latest`, so a later 10-K's recast replaces the original figure.
- **Same-period calculations.** `app/services/facts/derive.py` computes margins (×100), free cash flow
  (operating cash flow less the absolute value of capex), working capital and current ratio, with
  operand provenance (`app/services/fact_provenance.py`).

## 2. The dataset the page shows

`app/services/trend_analysis/dataset.py::build_dataset` reads the latest facts and builds the period axis
(at most 10 fiscal years or 12 quarters). It aligns 26 concepts and attaches year-over-year or
quarter-over-quarter growth: relative growth for amounts, which is not meaningful across a sign change,
and a percentage-point delta for margins. It computes a CAGR and a window percentage-point change over
each series' valued endpoints, and assigns every non-null value a stable marker `F1…Fn` in
series-by-period order, with CAGRs numbered after them.
`detectors.py` adds deterministic signals: growth deceleration, margin compression of at least 2pp over
three periods, FCF/net income divergence, debt build and liquidity squeeze. `data_notes.py` adds the
"needs review" and "unavailable" notes. The fingerprint (sha256 of the canonical dataset) keys the cache.

## 3. The generator sees an ID catalogue, not figures or filing text

`app/services/trend_analysis/observations.py::build_observation_catalogue` writes every sentence the
analysis can contain, in code, from about 15 templates: "Revenue was $14.3B in FY2025 [F10].",
"Operating margin changed -3.2pp in FY2025 [F29][F30].", "Watch how free cash flow … compares with …".
Each sentence gets an ID and a section. Some are `required`: the latest top line, its CAGR, the latest
growth, the first margin, the FCF/net income level comparison, the current-ratio threshold, every
detector signal, and the first watch item.

The model (`prompts/trends-analyst-agent.md`, `narrative.py::_selection_messages`) receives only that
catalogue, compacted to about 2,000 tokens. It returns a JSON object of at most three optional IDs per
section. The prompt forbids it "to infer causes, forecasts, comfort, risk, issuer reporting behavior, or
relationships that are absent from a catalogue entry". It sees no filing text, no MD&A and no segment data.

- **Model and provider.** `openai_service.stream_chat` uses the OpenAI-compatible client against DeepSeek
  (`OPENAI_BASE_URL=https://api.deepseek.com/v1`), with `AI_DEFAULT_MODEL=deepseek-flash` (DeepSeek
  V4.1 Flash), thinking disabled, temperature 0.2 and `ANALYSIS_MAX_TOKENS=3200` (`app/config.py`;
  ADR-0008 records the choice and the 14 September 2026 cutover). Production sets these through
  environment variables and Secret Manager, which this session cannot read, so "production runs
  deepseek-flash" is what the code, ADR-0008 and `ci.yml`'s deploy environment say, not an observed log line.
- **Validation.** `parse_observation_selection` accepts only the six keys, known IDs in their own
  section, unique IDs and the per-section and total limits. One malformed reply gets one retry; a second
  fails closed.

## 4. Rendering, citations and the fidelity check

`render_observation_selection` adds the required observations to the model's picks. Where the model
picked nothing for a section, it falls back to that section's first observation.
`citations.py::resolve_narrative_citations` renumbers `[F#]` to `[1]…[n]` in order of first appearance
and builds each citation from its dataset point: the excerpt, the XBRL tag or calculation formula, and the
source URL. A marker the dataset never issued is dropped and counted as `unverified`.
`fidelity.py::scan_numeric_fidelity` checks that a figure in the 48 characters before each `[n]` matches
that point's value or its growth. Because code writes every sentence, the scan passes by construction; a
failure would mean a code bug, and the run fails closed (`narrative.py::_publish`).
`presentation.py` adds data-note marks; `NarrativePane.tsx` renders the sections, the chips and the
Sources list.

## 5. Cache, metering and cost

- **Cache.** `trend_analyses`, keyed on (company, mode, period key). A row is served again with no model
  call while `PROMPT_VERSION` (`trends-v7-observations`), the dataset fingerprint and the presentation
  format are unchanged (`cache.py`, `narrative.py::_assemble`). `force` regenerates and is metered
  against the 100-a-month fair-use cap; a system-invalidated regeneration is not metered (`routers/analysis.py`).
- **Telemetry.** Every fresh generation emits the PostHog `analysis_inference_cost` event: model, tokens
  (cache hit and miss), estimated cost and `grounded`. Each provider call also logs an `ai_call` line.
- **Measured cost and latency** (census; deepseek-flash at the off-peak list price, where the peak doubles
  it): prompts average 2,049 tokens, 1,782 of them cache hits, with 265 completion tokens. Cost is
  **$0.0002** per fresh analysis ($0.0004 at peak). Latency is p50 1.9 s / p90 2.2 s for the whole stream
  and p50 1.6 s for the model call. In 45 runs there were no selection retries and no empty selections.

## 6. What the generator contributes

The census measured the result. Of 705 annual sentences, 41.6% restate a figure and 58.4% are derived
comparisons; 0% are causal claims and 0% are judgements. An independent LLM labelling agrees, with κ =
0.72. Of the numeric sentences, 95.7% contain no figure the metrics table on the same page lacks.
Only 36.5% of sentences exist because the model chose them; the rest are required by code.
The pipeline's quality is a property of the catalogue templates, not of the model: replacing the model
cannot add depth while the model may only choose among code-written sentences that are forbidden to state
causes.

## 7. Defects found while mapping (not fixed in this branch)

| Defect | Evidence | Effect on the analysis |
|---|---|---|
| Recast and original figures sit side by side in one series ("latest filing wins") | Regeneron FY2018 and FY2019 revenue are the FY2020 10-K's recast figures ($5,145.6M and $6,557.6M); the 10-Ks for those years reported $6,710.8M and $7,863.4M. FY2017 was never recast. | The table shows FY2018 revenue −12.4% and an operating margin of 49.3%; as first reported, revenue grew 14.3%. The screenshot in the brief shows these figures. |
| Insurers and managed-care companies get no annual window | UNH, PGR, ELV, CI, HUM, TRV and ALL ingest their top line as `premiums_earned`; `available_periods.has_core` requires revenue or net interest income. | The page offers no annual analysis for these companies at all. |
| Proxy-statement figures replace 10-K net income | Proxy statements (DEF 14A) tag net income, rounded, in the pay-versus-performance table and are filed after the 10-K, so "latest filing wins" stores them. In the harness store, 29 of 78 companies show a proxy figure as their latest-year net income (JPM FY2021–FY2025: $48.3B against the 10-K's $48,334M). The largest gaps are MRK 5.4%, GM 3.1% and TSLA 2.3%. | The metrics table, the margins built on it and the narrative carry rounded or differently scoped net income. Fix: exclude DEF 14A (and other non-financial-statement forms) at ingest, `facts/companyfacts.py`. |
| Long-term debt stops after FY2020–FY2021 for some filers | `concepts.py` maps `long_term_debt` to `LongTermDebtNoncurrent` and `LongTermDebt` only. Chevron and ConocoPhillips have tagged `LongTermDebtAndCapitalLeaseObligations` since then, and Deere's recent 10-Ks carry neither tag (found during the evaluation; see REPORT.md §3). | The long-term debt row is blank for recent years, and debt-based signals (debt build, net debt) read only the current portion. |
| Chubb's top line renders as "Net interest income −$764.0M" | census, CB | A wrong label on an insurer. |
| XOM resolves to a new CIK | The SEC ticker map now points XOM at "ExxonMobil Holdings Corp" (CIK 2115436), which has 27 facts from Q2 2026. | ExxonMobil's history is unreachable by ticker. |
| Quarterly narrative states year-over-year growth over a quarter-over-quarter table | census: 59% of quarterly numeric sentences are visible in the table, against 97% for annual. | The reader cannot find the stated figures in the table. |
| Uncompacted amounts | 41 sentences print figures like "USD 8,884,000,000" (red-flag operand tails). | Readability. |
