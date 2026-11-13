# Summary-Quality Eval Harness (roadmap S3)

A golden-set + deterministic-scorer harness so changes to AI summarization (prompts, models,
pipeline) are **measured against a baseline**, not assumed. This is the proof mechanism that
must exist *before* the prompt/schema rewrite (S1) and model bake-off — changing prompts
without a measurement loop is how the current "hit and miss" state arose.

## What it measures

Every candidate produces the same canonical summary shape (`schema.EVAL_SUMMARY_JSON_SCHEMA`)
and is scored by **deterministic** metrics (no LLM-judge needed for the verdict):

| Metric | What it catches | Source |
|---|---|---|
| **schema validity** (+ `repaired` flag) | "enforced, not requested" structured output — the S1 thesis | `scorers.validate_schema` / `parse_model_json` |
| **numeric accuracy** (recall) | *missing* financials vs XBRL ground truth | `scorers.score_numeric_accuracy` |
| **numeric precision** | a *wrong* number in a labeled financial field — recall is fooled when the correct value also appears, precision is not | `scorers.score_numeric_precision` |
| **coverage** | sections that are present *and substantive* (not "Not disclosed") | `scorers.score_coverage` |

`RubricScore.aggregate()` combines schema/recall/coverage (0.30 · 0.45 · 0.25). These scorers are
pure functions, unit-tested offline in `tests/unit/test_eval_scorers.py` — run them anytime with
`pytest tests/unit/test_eval_scorers.py`.

### Hard gates (a promotion veto — Artifact 1)

Some failures are unacceptable at any aggregate. `RubricScore.gate_failures` lists them and
`RubricScore.passed_gates` is the veto — a gate-failing run **cannot count as a PASS** regardless
of its score:

- **G1 numeric fidelity** — a labeled financial field contradicts ground truth (deterministic).
- **G4 output hygiene** — leaked AI/internal notices or placeholder filler (deterministic).
- **G2 fabricated comparatives / G3 hallucinated facts** — need the source, so they are assessed
  by the optional **LLM judge** (`judge.py`), a *secondary, evidence-citing* signal — never a
  replacement for the deterministic gates. Off by default (`--judge`); see below.

### Consistency (Artifact 3)

"Hit and miss" is a *variance* problem a single run can't see. `--runs N` scores each
(candidate, filing) N times and reports **`pass_rate`** (gate-passing runs clearing the aggregate
threshold) and **`aggregate_stdev`**. Two candidates with the same mean can differ wildly in
consistency — that's what to optimize for.

## Candidates (the bake-off)

Registered in `models.py`, except `baseline`, which runs the current `openai_service` pipeline. Claude is
called via the official `anthropic` SDK (native
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
> The `baseline` row is priced differently: the pipeline's own `ai_call` estimates
> (`app/services/llm_pricing.py`, peak-aware), for every generation including retries, so it is
> not like-for-like with the candidates' rows (see RUNBOOK Step 7).

## Running it

Requires SEC EDGAR network access (to fetch filings/XBRL) and the relevant provider keys.

```bash
cd backend

# 1. Build the golden set: resolve accessions/URLs + auto-populate XBRL ground truth.
python -m evals.build_golden_set            # writes golden_set.json, sets verified=true
python -m evals.build_golden_set --dry-run  # preview without writing

# 2. Baseline the current pipeline first.
python -m evals.runner --candidates baseline

# 3. Bake off candidates against it. --runs measures consistency; --judge adds the
#    secondary LLM-judge signal (needs `pip install anthropic` + ANTHROPIC_API_KEY).
python -m evals.runner --candidates baseline,gemini-json,claude-sonnet,claude-opus \
    --runs 3 --pass-threshold 0.7 --judge claude-opus-4-8
```

Reports land in `evals/reports/eval_<timestamp>.{json,md}`, ranked by `pass_rate` then mean
aggregate. Flags: `--runs N` (consistency), `--pass-threshold` (aggregate a gate-passing run must
clear to PASS, default 0.7), `--judge <model>` (secondary signal, off by default).

## Golden set

`golden_set.json` holds 35 verified filings (14 10-K, 11 10-Q, 7 20-F, 3 6-K), each with its
accession and `ground_truth`. `build_golden_set.py` resolves a new entry from live EDGAR/XBRL and
sets `verified` once its invariants pass. **To extend it**, add entries for small-caps,
non-financial issuers, and a known problem case (e.g. a pre-2019 filing) to cover adversarial
cases; `RUNBOOK.md` Step 2 gives the entry shape.

## Adoption rule

Promote a candidate to default (flip `USE_STRUCTURED_OUTPUT` / `AI_QUALITY_GATE`, or switch
`AI_DEFAULT_MODEL`) **only if it beats `baseline` on schema-validity AND numeric accuracy AND
coverage, with no hard-gate regression** (`gate_fail_rate` no worse than baseline), **AND meets
the consistency target** (high `pass_rate`, low `aggregate_stdev`) — at acceptable latency/cost.
The optional `judge_pass_rate` is corroborating evidence, not the gate. Otherwise keep the flag
off, report the numbers, and recommend next steps. The harness is also the regression suite for
every future prompt change.

> `schema_valid` accepts both `financial_highlights` shapes (the flat canonical one and the
> production pipeline's richer one), so the baseline earns it (about 1.0). `USE_STRUCTURED_OUTPUT`
> changes the prompt and temperature, not the output shape; see the RUNBOOK's "`schema_valid`
> recognizes both financial_highlights shapes" paragraph.

---

## Copilot eval ("Ask this Filing", P8)

The summary harness above grades one structured summary per filing. The Copilot is a per-question
grounded Q&A loop, so it has a sibling eval with its own deterministic gates:

- **Golden set:** `copilot_golden_set.json` — per-filing question cases, each marked `disclosed`
  (answerable) or not. Deliberately-undisclosed questions calibrate **refusal** (the model must say
  "not disclosed", not fabricate).
- **Scorers (`copilot_scorers.py`, deterministic, no network):**
  - *Citation faithfulness* — every text citation's excerpt must verify **verbatim** in the filing
    (re-run independently of the answer's own `verified` flag; XBRL/tool citations exempt), and its
    section label must carry none of decision F's double quote marks (Copilot's own publication
    rule). Hard gate.
  - *Refusal calibration* — refuse iff the filing does not disclose the answer. Hard gate.
  - *Numeric accuracy* — for targeted numeric questions, the expected figure must appear (reuses the
    summary harness's value-rendering matcher). Hard gate.
- **CI rigor:** `tests/unit/test_copilot_evals.py` exercises the scorers on synthetic answers — runs
  on every change, no model/network.
- **Live run:** `python -m evals.copilot_runner --preparation <preparation.json> --runs 3` runs the
  live Copilot over the golden set and writes `copilot-eval.{json,md}` under `--output`. It needs
  the model API, `GITHUB_SHA` set to a 40-hex commit, and the preparation that
  `evals.copilot_bootstrap` writes; `.github/workflows/copilot-eval.yml` runs that sequence on
  qualifying pull requests.
