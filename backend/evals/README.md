# Summary-Quality Eval Harness (roadmap S3)

A golden-set + deterministic-scorer harness so changes to AI summarization (prompts, models,
pipeline) are **measured against a baseline**, not assumed. This is the proof mechanism that
must exist *before* the prompt/schema rewrite (S1) and model bake-off — changing prompts
without a measurement loop is how the current "hit and miss" state arose.

## What it measures

Every candidate produces the same canonical summary shape (`schema.EVAL_SUMMARY_JSON_SCHEMA`)
and is scored by three **deterministic** metrics (no LLM-judge needed for the verdict):

| Metric | What it catches | Source |
|---|---|---|
| **schema validity** (+ `repaired` flag) | "enforced, not requested" structured output — the S1 thesis | `scorers.validate_schema` / `parse_model_json` |
| **numeric accuracy** | hallucinated/missing financials vs XBRL ground truth | `scorers.score_numeric_accuracy` |
| **coverage** | sections that are present *and substantive* (not "Not disclosed") | `scorers.score_coverage` |

`RubricScore.aggregate()` combines them (0.30 schema · 0.45 numeric · 0.25 coverage). These
scorers are pure functions, unit-tested offline in `tests/unit/test_eval_scorers.py` — run
them anytime with `pytest tests/unit/test_eval_scorers.py`.

An LLM-judge usefulness/precision dimension can be layered on later; the deterministic three
are what gate adoption.

## Candidates (the bake-off)

Registered in `models.py`. Claude is called via the official `anthropic` SDK (native
structured outputs); the OpenAI-compatible providers via the `openai` SDK + per-provider base
URLs.

| key | model | provider | API key env |
|---|---|---|---|
| `baseline` | current `openai_service` pipeline | — | `OPENAI_API_KEY` |
| `gemini-json` | `gemini-3-pro-preview` + JSON mode | Google AI Studio | `OPENAI_API_KEY` |
| `claude-sonnet` | `claude-sonnet-4-6` | Anthropic | `ANTHROPIC_API_KEY` |
| `claude-opus` | `claude-opus-4-8` | Anthropic | `ANTHROPIC_API_KEY` |
| `qwen` | `qwen-max` | DashScope | `QWEN_API_KEY` |
| `kimi` | `kimi-k2-0905-preview` | Moonshot | `KIMI_API_KEY` |
| `deepseek` | `deepseek-chat` | DeepSeek | `DEEPSEEK_API_KEY` |

To bake off Claude: `pip install anthropic` (kept out of core requirements). Base URLs default
to each provider's documented OpenAI-compatible endpoint and are overridable via `*_BASE_URL`.

> **Cost column:** Claude per-token prices are verified (claude-api skill). The other prices
> are **UNVERIFIED placeholders** — confirm against each provider's pricing page before relying
> on the `$cost` column. Cost is secondary to the quality verdict; edit prices in `models.py`.

## Running it

Requires SEC EDGAR network access (to fetch filings/XBRL) and the relevant provider keys.

```bash
cd backend

# 1. Build the golden set: resolve accessions/URLs + auto-populate XBRL ground truth.
python -m evals.build_golden_set            # writes golden_set.json, sets verified=true
python -m evals.build_golden_set --dry-run  # preview without writing

# 2. Baseline the current pipeline first.
python -m evals.runner --candidates baseline

# 3. Bake off candidates against it.
python -m evals.runner --candidates baseline,gemini-json,claude-sonnet,claude-opus,qwen,kimi,deepseek
```

Reports land in `evals/reports/eval_<timestamp>.{json,md}`, ranked by mean aggregate.

## Golden set

`golden_set.json` ships with well-known issuers (mega-cap, financial, 10-K/10-Q) but
`verified: false` and empty accession/ground_truth. `build_golden_set.py` fills them from live
EDGAR/XBRL. **Extend it toward 15–25 filings** with small-caps, non-financial issuers, and a
known problem case (e.g. a pre-2019 filing) to cover the roadmap's intended mix.

## Adoption rule

Promote a candidate to default **only if it beats `baseline` on schema-validity AND numeric
accuracy AND coverage with no regression**, at acceptable latency/cost. Otherwise keep the
flag off, report the numbers, and recommend next steps. The harness is also the regression
suite for every future prompt change.

> The baseline maps the current pipeline into the canonical shape but does **not** enforce the
> canonical schema, so it typically scores schema-invalid here. That gap is precisely what S1
> aims to close and is the honest baseline to beat.
