# Multi-Period Analysis depth harness

An offline research harness for the "AI trend analysis" section. It builds evidence packs from SEC
filings, generates analyses with a proposed prompt on several models, checks every number with a
deterministic gate, judges outputs pairwise with a model from neither output's family, audits causes and
number attribution, and writes a report. None of it runs in production or CI; its unit tests do (`tests/unit/test_trend_depth_factcheck.py`).
The findings and recommendation are in `tasks/analysis-depth-2026-10/REPORT.md`.

## Re-run after a prompt change

```bash
cd backend
# 1. Tune on the development half only, never reading held-out outputs. A draft prompt can be pointed at with
#    TREND_DEPTH_PROMPT=/path/to/draft.md without touching the checked-in one (each output records the prompt's sha256).
python -m evals.trend_depth.generate --label dev-v5 --arms deepseek-flash,claude-sonnet-5-5 --split dev
python -m evals.trend_depth.report --label dev-v5 --systems deepseek-flash,claude-sonnet-5-5
# 2. Freeze the prompt, then run everything, the production pipeline included as "current".
python -m evals.trend_depth.generate --label eval-v2 --arms current,deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low,gemini-3.8-flash --split all
# 3. Judge every pair in both orders. Add --exclude-judges gemini-3.8-flash when the Gemini quota is spent
#    (Gemma 4 31B then judges the Claude-vs-DeepSeek pairs), or gemini-3.8-flash,gemma-4-31b for consensus panels.
python -m evals.trend_depth.judge --label eval-v2 --systems current,deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low
# 4. Audit causes against their passages and verified numbers against their labels, by default with an auditor
#    from another family; --auditor <arm> repeats the audit with one auditor for every system.
python -m evals.trend_depth.causes --label eval-v2 --systems deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low,gold
python -m evals.trend_depth.semantics --label eval-v2 --systems deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low
python -m evals.trend_depth.causes --label eval-v2 --systems deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low,gold --auditor claude-opus-5-5
python -m evals.trend_depth.semantics --label eval-v2 --systems deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low --auditor claude-opus-5-5
# 5. The report: development and held-out side by side, gate results as run and under the current gate.
python -m evals.trend_depth.report --label eval-v2 --systems current,deepseek-flash,claude-sonnet-5-5,claude-haiku-5-5-low
```

The packs in `tasks/analysis-depth-2026-10/packs/` are committed, so every step reads the same evidence and
needs no SEC access, except the `current` arm, which ingests companyfacts into the local store. A file that
exists is skipped, so use a new label per run. A record holding a provider error (a quota, an outage) is
retried by the next run with the same label.

Keys are read by name: `DEEPSEEK_API_KEY`, `GEMINI_API_KEY` (or the cloud container's `OPENAI_API_KEY` with
a Google base URL), and `ANTHROPIC_API_KEY`. Without an Anthropic key, Claude runs through `claude -p` (the
repository's judge pattern), which bills the logged-in subscription; with the key, it runs through the
Anthropic SDK. A free-tier Gemini key reaches only the Flash models and Gemma: Pro and Gemini 4 Argon answer
with a quota of zero, Gemini 3.8 Flash allows 20 requests a day, and Gemma 4 31B is slow (about a minute per
judge call, with intermittent 500s).

Spend: `eval-v1` (20 companies, four proposed arms plus current, judging, and both audits under both
auditors) cost USD 42.3 in October 2026: Opus judging USD 23.4, Opus audits USD 10.7, Sonnet generation
USD 5.6, and everything else under USD 1 each. A run with only the default audits and without the Haiku arms
costs about USD 25. `tasks/analysis-depth-2026-10/REPORT.md` §8 has the per-analysis costs.

## Rebuild the evidence

```bash
python -m evals.trend_depth.evidence REGN SNAP JPM            # packs (SEC traffic through the app's transports)
python -m evals.trend_depth.drivers REGN SNAP JPM COST NVDA   # driver tree, common-size view, availability
python -m evals.trend_depth.census run && python -m evals.trend_depth.census report   # the current pipeline
python -m evals.trend_depth.gold check REGN SNAP JPM          # gold examples against the gate
```

Rebuilding a pack can renumber its IDs. `python -m evals.trend_depth.gold remap TICKER <old pack.json>`
moves a gold example's citations to the new IDs, and `gold check` then re-verifies every number.

## Modules

| Module | Job |
|---|---|
| `bootstrap.py` | environment, the private SQLite facts store filled by the production ingest, cached SEC inputs |
| `companies.py` | the 20-company evaluation set (10 development, 10 held out), the census set, peer groups, the human-pack companies |
| `sec_inputs.py` | 10-K list, documents (with the EX-13 and Item 7 fallbacks), XBRL dimensional facts, full-text search |
| `xfacts.py` | extended companyfacts lines (cost lines, cash uses, balances, bank and insurer lines), first-reported against latest |
| `dimensions.py` | revenue and segment-profit disaggregation from each 10-K's instance, subtotals, coverage |
| `derived.py` | the driver tree as values: common-size, margin bridge, operating leverage, cash conversion, net cash, capital returns, bank metrics, window levels, red-flag candidates |
| `passages.py` | MD&A and note passages that state causes or guidance, with EDGAR locations |
| `evidence.py` | assembles a pack, including data checks and peer percentiles from the store |
| `render.py` | the pack as the generator reads it |
| `factcheck.py` | the gate |
| `providers.py` | model arms, usage, latency and list-price cost |
| `generate.py` | proposed and current generations, the one-repair step, the gate |
| `judge.py`, `readable.py` | pairwise position-swapped judging in a neutral reader format |
| `causes.py` | does each cited passage state the cause its sentence gives? |
| `semantics.py` | is each verified number said about the metric and period it matched? |
| `report.py` | the bake-off report |
| `human_pack.py` | the blind preference pack and scoring sheet |
| `gold.py`, `drivers.py`, `census.py` | gold examples, driver evidence, the census of the current pipeline |
