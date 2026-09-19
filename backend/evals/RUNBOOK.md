# Adoption-Gate Runbook

How to run `backend/evals/` for adoption decisions and ongoing regression measurement.
Live runs need SEC EDGAR network access and provider API keys; CI uses its existing Actions
secret. Offline scorer/parity tests need neither: `pytest tests/unit/test_eval_*`.

The original adoption steps below remain a procedure for future comparisons. Current code
defaults and deployment overrides are documented in `docs/CONFIGURATION.md`: the quality gate
and native edgartools sections are already on, structured-output mode remains off, and CI's
service deployment enables FPI filings and progressive section reveal. Do not infer live state
from an old rollout example.

Verified AI checkpoint (2026-09-05): hygiene #702 and Copilot #703 are merged. Copilot merge
`d7a2a269` passed [production deployment](https://github.com/neilmac91/EarningsNerd/actions/runs/33986181022)
with the evidence below. The sole #698 baseline pin remains unchanged. (Historical: the first
strong-judge readout was produced on 2026-09-15 and `AI_EVIDENCE_SNAP` armed the same day; see
"Weekly strong-judge measurement" and the re-pin paragraphs.)

| Verified checkpoint | Actual result |
| --- | --- |
| Migration tail | `apply_migrations: applied=0 skipped=34` |
| Backend revision / traffic | `00268-jn7` / 100% |
| Detailed health | Healthy in deployment and independent post-deploy checks |
| [Summary evaluation](https://github.com/neilmac91/EarningsNerd/actions/runs/33985211897) | 52 planned/scored, errors 0, hard vetoes 0; PASS with 1 advisory warning |
| [Copilot evaluation](https://github.com/neilmac91/EarningsNerd/actions/runs/33985648605) | 18 planned/completed/scored/passed, errors 0 |

## What you're deciding

Three separate decisions are represented in `app/config.py`; measure each explicitly:

| Change | Flag (field) | Truest way to test it |
|---|---|---|
| S1 structured extraction | `USE_STRUCTURED_OUTPUT` | run `baseline` with the flag **off vs on** |
| Switch the model | `AI_DEFAULT_MODEL` | bake-off candidates vs baseline |
| S4 honest quality gate | `AI_QUALITY_GATE` | product behavior — validate separately (Step 8) |

---

## Step 1 — Environment
Run where EDGAR is reachable (EDGAR rejects requests without a valid User-Agent), with the app's
normal env loaded.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install anthropic          # only for Claude candidates + the LLM judge

# Load your normal backend .env, then add provider keys:
export OPENAI_API_KEY=...       # baseline uses the OpenAI-compatible DeepSeek provider
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export AI_DEFAULT_MODEL=deepseek-flash
export AI_FALLBACK_MODEL=       # leave empty for every eval and pin
export AI_FALLBACK_BASE_URL=    # leave empty for every eval and pin
export AI_EVIDENCE_SNAP=true   # armed in production since 2026-09-15; pins must match the deploy env
export AI_FIGURE_TRACE_GATE=false
export AI_FORWARD_QUOTE_GATE=false
export USE_STRUCTURED_OUTPUT=false
export USE_STATEMENT_FINANCIALS=true
export STREAM_SECTION_REVEAL=true  # exercise the same callback-selected extraction path as prod
export ANTHROPIC_API_KEY=...    # claude-sonnet, claude-opus, and the Opus judge (API credits)
# optional: QWEN_API_KEY / KIMI_API_KEY / DEEPSEEK_API_KEY
# optional judge backends (see "Judge backends" in Step 6):
#   JUDGE_OPENAI_BASE_URL / JUDGE_OPENAI_API_KEY   # for --judge glm-5.2 / openai:<model>
#   (for --judge cli:sonnet, no key: uses the logged-in `claude` subscription via OAuth)
```

Sanity check (no API spend):
```bash
SKIP_REDIS_INIT=true python -c "import evals.runner, evals.judge; print('harness OK')"
```

---

## Step 2 — Expand the golden set to 15–25 filings
`golden_set.json` ships with a diverse seed. To add more, fill only 5 fields per entry; the
builder resolves the rest:

```json
{"ticker": "XXXX", "cik": "0000000", "company_name": "...", "filing_type": "10-Q",
 "accession_number": "", "document_url": "", "ground_truth": [], "verified": false,
 "notes": "why this one"}
```

Cover the adversarial cases — that's where quality breaks: small-caps / non-financial issuers
(thin XBRL), a **no-prior-period** case (recent IPO), a known prior problem filing, and a roughly
even 10-K / 10-Q split. Find a CIK at
`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&ticker=XXXX`.

### G5 bank-component facts (JPM) — restored after statement-financials graduation

JPM's FY2025 ground truth includes net interest income **$95,443 million** and noninterest
revenue **$87,004 million**, verified against the accession's
[Consolidated Statements of Income](https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/R3.htm).
These facts were temporarily removed in #611 while extraction could not emit the components
reliably. WS-7 #690 graduated `USE_STATEMENT_FINANCIALS=true`; WS-6 restores both facts so
G5 again requires them to surface separately. A total-revenue figure alone does not satisfy
G5. Do not remove these facts to make a failing measurement green: inspect the extraction,
streamed output and per-run failure first. SIC backfill and persisted-fact remediation remain
separate founder-run production operations.

---

## Step 3 — Build & verify
```bash
python -m evals.build_golden_set --dry-run   # preview resolution + XBRL facts
python -m evals.build_golden_set             # writes, flips verified=true on success
```
Then inspect:
- Most entries should be `verified: true`. Small-caps may come back `incomplete` — fill
  `ground_truth` by hand (`[{"metric":"revenue","value":1234000000,"unit":"USD"}]`) and set
  `verified: true`.
- **Spot-check 2–3**: open the `document_url`, confirm `ground_truth` matches the filing. Wrong
  ground truth silently corrupts every score.

---

## Step 4 — Cheap wiring smoke test
```bash
python -m evals.runner --candidates baseline,gemini-json --limit 2 --runs 1
```
Confirm it fetches, scores, and writes `evals/reports/eval_*.md` with no errors.

---

## Step 5 — Baseline (the bar to beat)
```bash
python -m evals.runner --candidates baseline --runs 3
```
Record `pass_rate`, `mean_aggregate`, `gate_fail_rate`, recall/precision/coverage. Baseline is
expected to score schema-invalid (it doesn't enforce the canonical schema — the gap S1 closes).

Test the S1 flag directly (this is exactly what flipping it does in prod):
```bash
USE_STRUCTURED_OUTPUT=false python -m evals.runner --candidates baseline --runs 3
USE_STRUCTURED_OUTPUT=true  python -m evals.runner --candidates baseline --runs 3
```

### A11 — cheaper section-recovery model

`AI_SECTION_RECOVERY_MODEL` routes only the section-recovery sub-task to a cheaper model
(defaults to the Pro model — unchanged until set). `baseline` exercises recovery end-to-end,
so test the flip the same way as the S1 flag:
```bash
# unset (Pro recovery) vs flash recovery
python -m evals.runner --candidates baseline --runs 3
AI_SECTION_RECOVERY_MODEL=gemini-2.5-flash python -m evals.runner --candidates baseline --runs 3
```
Promote (set the env in prod) only if the flash run shows **no regression** in `coverage` /
`num_recall` and **no increase** in `gate_fail`, with comparable `pass_rate` / `agg_stdev`
(the same adoption rule as Step 8). Recovery failures degrade gracefully (an unfilled section
stays empty, never corrupted), so this is the lowest-risk place to start cheaper-model routing.

---

## Step 6 — The bake-off
```bash
python -m evals.runner \
  --candidates baseline,gemini-json,claude-sonnet,claude-opus \
  --runs 3 --pass-threshold 0.7 --judge claude-opus-4-8
```
Cost: ~`24×N` API calls for N filings (4 candidates × 3 runs + a judge call each). Start with
`--limit 5`, then run the full set. If cost matters, fix the **unverified price placeholders** in
`models.py` first (Claude prices are verified; others are guesses).

### Judge backends (cost vs authority)
`--judge <model_id>` dispatches by prefix (see `judge_backend` in `judge.py`), so you can trade
cost for authority without touching code:

| `--judge` value | Backend | Auth / env | When |
|---|---|---|---|
| `claude-opus-4-8` (bake-off default) | anthropic SDK | `ANTHROPIC_API_KEY` (API credits; `requirements-eval.txt`) | Bake-off audits on credits; the Opus agreement reference |
| `cli:claude-fable-5-1` | subscription CLI (`claude -p`) | logged-in Claude subscription (OAuth); `ANTHROPIC_API_KEY` is stripped from the child env | **The weekly readout's contract judge** (`ai_readout.JUDGE_MODEL`, W3-7); local only — **no OAuth in CI** |
| `cli:sonnet` / `cli:opus` | subscription CLI (`claude -p`) | as above | Local/manual gates |
| `glm-5.2` / `openai:<model>` | OpenAI-compatible chat | `JUDGE_OPENAI_BASE_URL` + `JUDGE_OPENAI_API_KEY` (falls back to `OPENAI_*`) | Cheap fallback judge |

**Agreement check before trusting a cheaper backend as the gate.** The bake-off default stays Opus so a
cheaper judge can never *silently* weaken the bar — but before you rely on one, run the same
`--forms <form> --runs 3` set through both it and `claude-opus-4-8` and confirm the verdicts and
per-dimension means agree within noise. (Wiring smoke on a synthetic G3-hallucination case:
`cli:sonnet` matched Opus exactly `{faith2,insight2,clarity4,spec3}`; `glm-5.2` was within 1 pt —
both fired the same G3 gate.) For `cli:*`, the child env strips `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN` and the Bedrock/Vertex/Foundry routing variables, so the judge always runs
on the subscription; unset the same variables in your shell *before* probing that you are logged
in (`claude -p --model claude-fable-5-1 --output-format json --tools "" "Reply with exactly: OK"`
must answer with `"is_error":false`; the standalone CLI needs its own one-time `/login`, and
`--bare` disables subscription auth). The weekly readout contract moved to `cli:claude-fable-5-1` on
2026-09-15 at the founder's direction (subscription, not API credits). Fable 5.1 is not a cheaper
judge than Opus 4.8, and an Opus agreement check for it would itself spend API credits, so that
check is recorded as deferred pending the founder's decision, not performed; a local
`python -m evals.judge_readout <report.json> --judge claude-opus-4-8` on an already generated
weekly report is the cheapest way to run it later (its verdicts are retained; the readout stays
unavailable for any non-contract judge).

---

## Step 7 — Read the report
`evals/reports/eval_<timestamp>.md`, ranked by `pass_rate`. Read in priority order:

1. **`pass_rate`** — gate-passing runs that clear the threshold. The headline.
2. **`agg_stdev`** — consistency. Low = reliable; high = "hit and miss." The whole point.
3. **`gate_fail`** — hard-gate vetoes (fabricated number / hygiene). Must not regress vs baseline.
4. `schema_valid`, `num_recall`, `num_precision`, `coverage` — deterministic components.
5. **`judge_pass`** — secondary corroboration (faithfulness/insight); never the deciding number.
6. `$cost`, `latency(s)` — tie-breakers / feasibility.

The `.json` has per-filing detail — use it to see which filings dragged a candidate down.

---

## Step 8 — Apply the adoption rule → action
Promote a candidate **only if** it beats baseline on schema/recall/coverage, with **no gate-fail
regression**, **and** hits the consistency target (high `pass_rate`, low `agg_stdev`) at
acceptable cost/latency. Then:

- **Structured output (`USE_STRUCTURED_OUTPUT=true` / `gemini-json`) wins** → flip
  `USE_STRUCTURED_OUTPUT=true` in your env. True one-flag change. ✅
- **A Claude/other model wins decisively** → NOT a one-line `AI_DEFAULT_MODEL` change. Production
  summarization uses the OpenAI-compatible client pointed at DeepSeek; routing to Anthropic needs an
  engineering follow-up in `openai_service.py`. The bake-off *justifies* that ticket.
- **Nothing beats baseline** → keep flags off, file the report; it tells you which dimension to
  fix next (usually precision or coverage on the adversarial filings).
- **`AI_QUALITY_GATE` (S4)** is a product-behavior decision (does a "partial" consume quota / show
  a badge), validated in staging — independent of the bake-off scores.

---

## Step 9 — Roll out + keep the gate
1. Flip the chosen flag in **staging/canary first**; watch real summaries + activation, then prod.
2. **Re-run the eval after** to confirm prod-config matches the winning numbers.
3. Keep the harness as a regression gate: offline scorer tests on every PR; full bake-off before
   any future AI/prompt/model change.

---

## Regression gate (B1) — pinned baseline + machine-checkable diff

Steps 1–9 describe the **adoption procedure**. B1 makes its evidence durable: it pins the current
production-pipeline quality and gives a deterministic, CI-runnable check that a change hasn't
eroded it — the safety net under any future output-quality work (and before a large precompute run).

Three pieces:

| Piece | What it is |
|---|---|
| `baseline_scores.json` | The pinned bar to protect — the `baseline` candidate's summary stats from a full verified-set run, committed to git. |
| `regression_gate.py` | Deterministic per-dimension diff of a fresh `reports/eval_*.json` against the pinned baseline. Exits non-zero on a HARD regression. |
| `eval-baseline` CI job | Advisory workflow job in `.github/workflows/ci.yml` that runs the live pipeline over the full verified golden set twice per AI-relevant PR, then checks completeness and quality against the pin. |

### Running the gate locally
```bash
cd backend
python -m evals.runner --candidates baseline --runs 2   # routine repeat measurement
python -m evals.regression_gate --latest                # diff it against baseline_scores.json
# or gate a specific report:
python -m evals.regression_gate evals/reports/eval_<stamp>.json
```
Exit 0 = complete operational evidence with no hard regression (warnings may print); exit 1 =
incomplete operational evidence or at least one HARD regression. Full reports must retain the
pre-execution requested candidates, selected filing cohort and repeats in `harness`, with exactly
one result per requested identity and matching `n`, `scored` and `errors` counts. Execution
errors, missing scores, missing/duplicate/unrequested attempts and malformed counts block the
gate even when the scored subset has perfect means. Quality means and their thresholds remain
scored-output measurements; errors are not fabricated zero-quality scores. Historical reports
without a declared plan cannot establish completeness through this CLI; the statistics-only
`compare_candidate` API remains available for historical metric comparisons.

**Transient provider faults get one retry (2026-09-08).** An attempt whose failure the production
client itself classifies as transient (`_is_transient` in `runner.py`: a timeout, connection
loss, HTTP 408/409/429/5xx, a malformed completion) is re-generated once after 5 s
(`--transient-retries`, default 1; 0 restores first-failure reporting). What that means per path:
the `baseline` candidate runs the production summary path, which raises only its own
`TimeoutError` (the 75 s request budget exhausted after up to three internal provider attempts)
and turns other provider faults into application `status: error` fallbacks. The runner retains
these as unscored, non-transient failed attempts with bounded application-error details, source
provenance, excerpt coverage and observed preview counts; it does not infer retryability from
the fallback text. Thus for
`baseline` the retry fires on that timeout alone and stacks one more generation on top of the
app's internal attempts; the other transient classes are reachable only for REGISTRY candidates,
and the Claude candidates' Anthropic SDK faults (timeout, connection, 429, 5xx) are classified
by class identity so the optional SDK need not be installed.
Scorer, schema, grounding and programming errors are never retried. The retry cannot select on
quality: a timeout yields no output, so the retried generation is the only one scored. Nothing is
hidden: the row keeps `retried`, `first_error` and `first_latency_seconds`, the summary carries a
`retried` count, both the PR harness and the weekly readout's harness record `transient_retries`
and `retry_delay_seconds`, and the gate's completeness note says `transient provider faults
retried=N` when any happened. A second transient failure is the attempt's error and blocks the
gate exactly as before. Rationale: on 2026-09-08 two consecutive advisory runs on PRs touching no
AI code went red on one such timeout out of 52 attempts each (the other 51 scored at pass rate
1.0); the retry turns that into scored evidence with the fault on record instead of an execution
error nobody can re-run.

The runner retains elapsed time, requested streaming and observed preview counts on generation
errors, and its CLI emits only sanitized `ai_call`/`ai_summary` telemetry. Preview observations do
not prove a stream completed, and missing usage remains unavailable. Weekly reports also retain
their fixed eight-filing × three-run manifest; their separate strong-judge readout validation still
determines judged completeness. A regression PASS does not establish a first judged readout or
arm any feature. The gate
**logic** is unit-tested offline (`tests/unit/test_eval_regression_gate.py`) — no network/AI — so it
runs for free in `backend-tests` on every PR.

### Thresholds (absolute deltas, in `regression_gate.py`)
Hard tolerances sit comfortably above the baseline's measured run-to-run `aggregate_stdev` so
ordinary model jitter never trips the gate, while a real drop does. Tuned deliberately
non-configurable from the report (a candidate must not relax its own gate).

| Dimension | Severity | Trips when |
|---|---|---|
| `gate_fail_rate` (fabricated number / hygiene veto) | **HARD** | increases > 0.005 (must never regress) |
| `mean_numeric_precision` (labeled-field fidelity) | **HARD** | drops > 0.05 |
| `mean_coverage` | **HARD** | drops > 0.05 |
| `mean_numeric_accuracy` (recall) | **HARD** | drops > 0.10 (looser — noisiest on small subsets) |
| `pass_rate` | warn | drops > 0.05 |
| `aggregate_stdev` (consistency) | warn | increases > 0.05 |
| `schema_valid_rate` | warn | drops > 0.05 |
| `mean_financial_depth` | warn | drops > 0.10 |

**`schema_valid` recognizes both financial_highlights shapes** — the flat canonical
`[revenue, net_income, eps, key_metrics]` (a bake-off candidate prompted to emit it) **or** the
production pipeline's richer `[table, profitability, cash_flow, balance_sheet]`. Both are
well-formed, so production output earns `schema_valid` (≈1.0). Earlier this required only the flat
shape, which made real output structurally schema-invalid and silently capped the aggregate at
~0.70 (the 0.30 schema weight was unearnable). It was NOT the `USE_STRUCTURED_OUTPUT` lever —
that flag changes the prompt/temperature, not the output shape, so it can't move `schema_valid`.
A malformed/empty object still fails.

### The advisory CI job (`eval-baseline`)

- **Existing generator credential.** The `DEEPSEEK_API_KEY` GitHub Actions secret has powered
  the actual #698, #700 and #701 evaluations. The key-check step still self-skips with a notice
  if that secret is absent; a skipped job is not evaluation evidence. This is separate from
  production GCP Secret Manager and from the still-unavailable strong-judge credential. Do not
  extract the Actions secret to a local machine.
- **Advisory workflow, required evidence review.** The job retains `continue-on-error: true`
  and is absent from `deploy-backend`'s `needs:`. A green overall workflow therefore cannot prove
  that the evaluation passed. Inspect the actual report and gate result before merging an
  AI-relevant change; execution errors and incomplete attempts block that clearance even if
  scored-only quality means are perfect.
- **Path-filtered.** Runs when `backend/app/**`, `backend/evals/**`, or `backend/prompts/**`
  change, or on manual `workflow_dispatch`. Each measurement makes real provider calls;
  dispatching a limited run does not establish full-set evidence.
- **PR vs dispatch.** PRs run the **full verified set twice** (`--runs 2`). Manual dispatch
  defaults to two repeats and accepts only `eval_runs=2` or `3`, with an optional positive
  `limit`. The sole authoritative #698 pin used three repeats with no limit; retain that pin
  and the documented replacement conditions below. The runner records its requested cohort
  and repeat count before execution, so missing attempts cannot shrink the measured population.
- **CI scheduling evidence.** Summary CI explicitly passes `--concurrency 2`; the runner's
  default remains five. Two is an unmeasured starting assumption to reduce simultaneous filing
  work, with a possible increase in CI duration. Recovery still fans out and other PRs/Copilot
  can overlap, so this is not a provider-request cap or a demonstrated timeout fix. E09's failed
  summary run `34042620267` overlapped Copilot from 15:34:29–15:36:00 UTC within its
  15:32:53–15:39:42 generation interval; accepted summary run `34044216078` also overlapped
  Copilot from 16:04:41–16:06:28 within 16:03:51–16:09:37 (2026-09-06). Both outcomes retain
  separate evidence; these intervals establish neither timeout causality nor a production
  failure rate. The 75-second runtime deadline and existing per-PR cancellation groups stay
  unchanged. The artifact retains `ci-execution.txt` with source SHA, filing concurrency and
  the exact shell-escaped invocation, written before generation so failure still leaves evidence.
  Concurrency is absent from the report's `harness`: keep this execution record separate,
  disclose scheduling differences when reviewing reports, and preserve all baseline/harness
  identities and historical artifacts. This scheduling change does not authorize a re-pin.
  The existing `test_ci_parity_and_bounded_repeat_measurement` gate executes the workflow shell
  against a harmless stub, including dispatch arguments and failure-exit/evidence retention.
  Changes to this RUNBOOK match the `backend/evals/` PR filter and therefore trigger the normal
  summary measurement; offline tests and skipped runs cannot establish live acceptance.
- **Unchanged hard tolerances.** A `gate_fail_rate` increase greater than **0.005** fails;
  precision/coverage drops greater than **0.05** and recall drops greater than **0.10** fail.
  Two repeats improve measurement granularity, but one hard veto in 52 outputs still exceeds
  the veto tolerance. WARN-level pass rate and variance remain distinct from hard vetoes.
- **Judge is off in routine regression CI.** These runs use deterministic scorers. The weekly
  strong-judge workflow and any required authoritative judged comparison have separate evidence
  requirements; their credential/readout prerequisite remains held. A judge-off pass, unavailable
  readout or cheaper substitute cannot satisfy the first strong-judge readout or arm a guard.

Historical context: before #698, this section described a one-run CI recipe and initial secret
setup. Its old 0.05 veto tolerance and single-run jitter rationale are superseded by the current
two-repeat workflow and 0.005 veto threshold above. The measured pin provenance and historical
quality evidence below are retained.

### Golden-set figure semantics (legitimate alternate bases)

A single XBRL-tagged value can't capture that a figure is correctly reported on more than one
basis. Ground truth therefore carries the primary in `value` and the other legitimate renderings in
`alt_values`; the scorer matches a fact when the output renders `value` OR any `alt_values` entry
(recall and precision both). `build_golden_set` derives them systematically:

- **EPS basic vs diluted** — diluted added when it differs from the basic `value` (the headline
  figure investors use). Single-class filers / loss-makers have basic == diluted → no alt.
- **EPS per-ADS (ADR filers)** — a 20-F headlines "earnings per ADS" while XBRL tags
  per-ordinary-share. When an entry sets `ads_ratio` (ordinary shares per ADS; e.g. BABA 8, TSM 5),
  per-ADS renderings (`per-share × ratio`, basic and diluted) are added — so Alibaba's
  "RMB44.00 per ADS" (= RMB5.50 × 8) matches.
- **Net income multi-basis** — a multi-entity filer tags several legitimate figures: consolidated
  (incl. NCI / `ProfitLoss`), attributable to the parent (`NetIncomeLoss` /
  `ProfitLossAttributableToOwnersOfParent`), and available-to-common (after preferred / mezzanine).
  The non-primary ones are added as alts, so a summary quoting any of them is correct. Single-concept
  (most domestic) filers get none.

These are eval-honesty fixes, not model changes: the summaries were already reporting correct,
ADR-appropriate figures. A *fabricated* number still won't match any legitimate basis.

### Financial-depth applicability and delta association (E6)

The default financial-depth rubric remains cash flow, balance sheet and margins (three equally
weighted categories), including the known incomplete-statement 6-K cohort. An explicit `insurer`
profile in a frozen golden entry also recognizes insurance float for balance-sheet depth and
underwriting earnings/profit/loss/income or combined ratio for operating profitability. Premiums
alone do not earn profitability depth, and the cash-flow requirement is unchanged. BRK.B and PGR
carry filing evidence and its accession in `financial_depth_profile_source`; loading a non-default
profile without evidence for the selected accession fails. Re-resolving a filing through the golden
builder therefore requires reviewing and refreshing this evidence. Candidate output never selects
its own rubric. Both runner paths pass the golden profile, the score records the profile actually
used, and each result retains its source. The golden-set hash binds this applicability; the pin
script rejects a missing or mismatched measured profile.

Delta consistency now attaches a direction-cued percentage directly to its named metric, allowing
only a short set of auxiliary words and explicit currency amounts (including parenthetical
changes and "decreased $2B, or 3%"). It does not borrow the percentage of another nearby metric.
This intentionally favors precision over recall: intervening descriptors, pronoun references and
percentage-before-metric phrasing can remain unmeasured. It still compares absolute magnitudes,
not signed direction or loss-narrowing semantics. The retained GPRO failure was revenue's 18.7%
decline borrowed by an unquantified net-loss sentence, not evidence of a negative-base sign bug.

These are measurement corrections, not improved generated summaries. The existing pin remains
historical until a fresh complete three-repeat run on this scorer/golden version is inspected and
pinned under the process below; retained reports can support an offline comparison but cannot be
re-pinned with the new golden identity or substituted for that measurement.

### Re-pinning the baseline

Routine `eval-baseline` PR runs evaluate the complete verified set twice. Manual CI dispatch
accepts only `eval_runs=2` or `3`; use **3 with blank limit** for the authoritative pin.
The workflow uses its existing `DEEPSEEK_API_KEY` secret; do not extract it to a local machine.
Inspect both the actual runner and regression-gate logs (the job is advisory), then download
the JSON/Markdown `eval-report-<run_id>` artifact. Keep the run ID, source SHA and report name
in the PR. Two repeats improve the granularity of mean/WARN measurements; they do **not**
excuse a hard veto (one failed filing-run out of 52 still exceeds the 0.005 hard tolerance).

Reports capture the requested model, provider URL, fallback model/base URL,
statement/stream/extraction and trust flags, judge selection, GitHub source SHA and golden-set SHA256 where the model runs. The pin tool
uses that metadata, never the local machine's model environment. It refuses missing or
changed golden-set provenance, fewer than three runs, a subset, missing/duplicate runs,
errors, hard vetoes/missing gate evidence or inconsistent counts/pass rates. Older reports without this provenance must be measured anew.
Both measured fallback fields must be present and explicitly empty. The pin tool also refuses
missing, non-boolean or mismatched values for `AI_EVIDENCE_SNAP`, `AI_FIGURE_TRACE_GATE`,
`AI_FORWARD_QUOTE_GATE`, `USE_STRUCTURED_OUTPUT` and `USE_STATEMENT_FINANCIALS` against the
committed service deploy env in `.github/workflows/ci.yml`. Missing or ambiguous deploy pins
cannot authorize a pin. These are repository configuration checks; post-deploy observation
still establishes the effective serving state. Older reports lacking the new fallback fields
remain valid historical regression references, but cannot be used for a new pin. The sole #698
baseline is unchanged; this validation change does not itself authorize another measurement or pin.

An existing `note` survives re-pinning; `--note "..."` explicitly replaces it. Preserve
provenance and explain intentional bar changes rather than performing cosmetic re-pins.
A reported baseline `total_cost_usd=0` is currently unmetered, not proof of a free model run.

The wave-2 parity pin is complete in #698: `eval_20260905T111951Z.json`, 26 × 3,
source `f5b46ba9`, zero errors/vetoes, PASS/0 warnings. Measure later work against it.
**September 15, 2026 re-pin (armed guard: `AI_EVIDENCE_SNAP=true`).** `baseline_scores.json` now binds
`eval_20260915T204745Z.json`: 35 verified filings × 3 runs (105/105 scored, 0 errors, PASS with the standing
untraceable-dollar advisory), run 35020462848 on source `e44f8046`, EdgarTools 5.58.0, DeepSeek V4.1 Flash with
thinking off and an empty fallback, measured with evidence auto-snap armed exactly as the service and pregenerate
deploy env now pin it (founder decision after the first complete strong-judge readout, W3-7/D5). Listed trigger:
armed-guard change. Against the W3-8b pin below: citation fidelity 0.9272 → 0.9706 (the armed snap replacing
non-verifying P&L-takeaway/footnote evidence with matched filing sentences), citation checked 7.28 → 7.09,
financial depth 0.771 → 0.794, redundancy 0.902 → 0.912, delta consistency 0.830 → 0.844, forward-quote fidelity
1.0 → 0.995 and coverage 1.0 → 0.998 (one filing-run each, within the known bands), aggregate 1.0 → 0.9995 with
stdev 0.0049. Measure later work against this pin.

**September 15, 2026 re-pin (W3-8b 6-K classifier and 6-K goldens).** `baseline_scores.json` previously bound
`eval_20260915T060846Z.json`: 35 verified filings × 3 runs (105/105 scored, 0 errors, PASS with the standing
untraceable-dollar advisory), run 34934705614 on source `30e1e193`, EdgarTools 5.58.0, DeepSeek V4.1 Flash
with thinking off and an empty fallback. Listed triggers: a prompt change (the three class-specific 6-K
variants) and a golden-set change (three earnings-class 6-K entries, ASML/SE/PDD Q2 2026, hand-filled from
their exhibit tables and grounded on exhibit text through the same pre-classification production uses).
The 6-K entries score 1.0 on numeric accuracy, precision, coverage and currency on every run; their
financial depth is 0.22 because a results release carries no cash-flow or balance-sheet figures, which
pulls the pinned mean to 0.771 (the 32 non-6-K entries alone read 0.823, within their run-to-run band of
the previous pin). Governance and press-release 6-Ks have no numeric truth and are covered by unit
fixtures, not goldens. Measure later work against this pin.

**September 15, 2026 re-pin (W3-8a golden breadth).** `baseline_scores.json` now binds
`eval_20260915T003946Z.json`: 32 verified filings × 3 runs (96/96 scored, 0 errors, PASS with the
standing untraceable-dollar advisory), run 34913316907 on source `c1a926a8`, EdgarTools 5.58.0,
DeepSeek V4.1 Flash with thinking off and an empty fallback. The set adds PLD (REIT 10-K), NEE
(regulated utility 10-Q), PGR (insurer 10-K), FIGS (small-cap 10-Q) and GPRO (small-cap 10-K), and
BRK.B is now verified with its EPS hand-filled from the filing's Consolidated Statements of Earnings
($31.04 per average equivalent Class B share, $46,563 per Class A share as the alternate); the 26
previously verified entries are byte-identical. WARN floors moved with the set's composition, not
with code: on this run the previous 26 entries alone read financial depth 0.876 / delta
consistency 0.854 / citation fidelity 0.932, while the six added profiles read 0.741 /
0.815 / 0.909, so the pinned means are lower than the September 10 pin. Per-profile
findings on the added cases are recorded in #873, not treated as measurement errors. Measure
later work against this pin.

Re-pin only for an explicitly justified model/prompt, structured-output, extraction-library or
armed-guard change with actual before/after evidence. Adding an advisory dimension or observing
changed scores alone does not authorize a cosmetic replacement. From `backend/`:
```bash
python -m evals.runner --candidates baseline --runs 3            # full verified set
python scripts/pin_baseline.py evals/reports/eval_<stamp>.json   # rewrite baseline_scores.json
```
Then commit the new `baseline_scores.json` in the same PR as the change it protects, so the diff
shows both the code change and the new bar. BRK.B has no consolidated EPS fact in its XBRL, so the
builder leaves it `verified: false`; since the September 15 re-pin its EPS is hand-filled from the
filing's statement of earnings and it is verified and pinned. If the builder is re-run in place, it
will re-resolve every entry and drop that hand-filled fact; restore the committed entry rather than
accepting the rewrite.

The dimension history below records the July 2026 pins and their measured variance. The
current committed bar and source report are always `baseline_scores.json`; a later honest
re-pin supersedes those historical numeric floors without discarding their provenance.

**Content-quality WARN dimensions (T3.0 scorers) — historical pin rationale.** `mean_redundancy` (one-home rule,
defect c) and `mean_delta_consistency` (prose vs. code-computed table deltas, defect g) are computed
on every scored run and reported alongside the aggregate (never folded into it). They ship as WARN
gates — a breach prints but never fails the build. **As of `summary-2026-07-b` (pinned from
`eval_20260708T225435Z`) both are recorded in `baseline_scores.json` and now bind;** re-pinned
from `eval_20260713T201101Z` (the post-T5/citation-track behavior), the floors sit at ≈ 0.896
redundancy / ≈ 0.892 delta-consistency (delta drew the LOW end of its observed 0.94–0.98
run-to-run band on the pin run — a single-report pin is kept for provenance, never hand-mixed
values across runs). Because a WARN floor is one-directional — it only trips on a *drop* — pinning
these here protects today's measured improvement and cannot cap a future rewrite: when the Tier-3 v2
content rewrite lands with higher redundancy, you simply re-pin the floors upward in that PR (as with
any bar move). (Earlier guidance to defer pinning until v2 was mistaken on this point — a floor
sitting below v1 redundancy can't "lock it in"; v2 is free to exceed it.)

**`mean_forward_quote_fidelity` (T5.4) — now pinned.** Fraction of §5 Forward Signals
blockquotes in the rendered markdown that verify verbatim in the filing text, under the SAME
`normalize_for_match` definition the production `forward_quote_gate` (drop when
`AI_FORWARD_QUOTE_GATE` is armed), the T4 evidence badge, and the copilot citation gate all use —
one definition of "verbatim", so the eval can never disagree with the product. Shipped advisory
in the T5.4 PR (a first readout is a measurement, not a bar); **pinned from
`eval_20260713T201101Z` at 0.9487, so the −0.05 WARN now binds (floor ≈ 0.899).** Read any WARN
against the KNOWN VARIANCE BAND before reacting: across six `--runs 3` measurements on unchanged
quote text this dim ranged **0.9231–0.9615** — ASML's one 98.5 near-miss sentence fails every
run, and one-to-two boundary filers (RIVN 97.3, COST) flip run to run; the floor sits below the
whole band, but a single-run CI readout has coarser granularity (each failing filing-run is
1/26 ≈ 0.038), so one noisy CI WARN is boundary noise — a SUSTAINED drop is the signal. Never add
it to `compute_gate_failures` — `gate_fail_rate` is pinned at 0.0 with epsilon tolerance, and the
G5 lesson (PR #611) is that a stochastic hard gate fires as pure noise.

**`mean_citation_fidelity` (T4 follow-up) — now pinned.** The permanent citation
scorer: fraction of the two VERBATIM-CONTRACTED `supporting_evidence` surfaces (P&L-takeaway rows
+ notable footnotes; footnotes threaded into the canonical payload by the runner) locatable
verbatim in the filing text, same shared normalization and excerpt-first referent as
`mean_forward_quote_fidelity`. `""` is the contracted no-verbatim-line answer and never counts.
`risks[].supporting_evidence` is deliberately excluded — its contract is looser by design
("excerpt or citation"; an XBRL tag or section reference is legal), so a verbatim demand would
mis-score legitimate evidence. Same never-in-`compute_gate_failures` posture as the forward-quote
dim; **pinned from `eval_20260713T201101Z` at 0.6887 (the UNARMED evidence-snap default — the
model's measured prompt floor), so the −0.05 WARN binds (floor ≈ 0.639). Arming
`AI_EVIDENCE_SNAP` raises this dim to the measured ~0.86 ceiling — re-pin upward in that PR.**
(Done 2026-09-15: armed and re-pinned at 0.9706 on the 35-filing set; see the re-pin paragraphs.)
The promised companion landed with the same re-pin: `mean_citation_checked` is recorded (6.27)
and WARN-gated at an absolute 2.0 drop (~30% — decrease direction; a volume signal, not a
quality bar), so an evidence-emission collapse (model stops emitting evidence → hollow-perfect
fidelity) is *self-announcing* rather than depending on a human noticing the count shrink in a
report. (Distinct from these stochastic dims, the
deterministic example-bleed tripwire — `EXAMPLE_BLEED_FRAGMENTS` in `scorers.py`, the prompt's
fictional worked-example spans — DOES live in the G4 `compute_gate_failures` family: a
fictional-by-construction substring cannot fire as noise, which is the property the G5 lesson
protects.)

---

## FPI adoption gate — flipping `ENABLE_FPI_FILINGS`

`ENABLE_FPI_FILINGS` has a false code default, while the CI service deployment explicitly
sets it true. The original FPI adoption phases are archived in
`tasks/archive/fpi-support-roadmap.md`; the steps below document their validation procedure
for future changes. This page-scoped flag controls foreign-issuer form discovery/listing
(20-F/6-K/40-F); job form sets have separate scope. The remaining 6-K classifier and backfill
work are not implied complete by the service flag.

The golden set ships verified FPI 20-Fs covering the currency/taxonomy + ADS-ratio matrix:

| Ticker | Accounting | Reporting currency | `ads_ratio` | Why |
|---|---|---|---|---|
| BABA | U.S. GAAP | CNY (+ USD convenience) | 8 | flagship; convenience-translation filter; per-ADS EPS |
| TSM  | IFRS | TWD | 5 | ifrs-full namespace + non-USD; multi-basis net income |
| ASML | IFRS | EUR | — | EUR; revenue hand-filled (double-tagged — see below) |
| JD   | U.S. GAAP | CNY | 2 | Chinese ADR; per-ADS EPS (×2) |
| SE   | U.S. GAAP | USD | — | Singapore ADR (1:1); multi-basis net income |
| NVO  | IFRS | DKK | — | Danish (1 ADR = 1 B share); DKK |
| PDD  | U.S. GAAP | CNY | 4 | Chinese ADR; per-ADS EPS (×4) |

(MercadoLibre, `MELI`, is also in the set as a Delaware-incorporated LatAm **10-K** in USD — domestic
form, not an FPI 20-F.) An entry's `ads_ratio` (ordinary shares per ADS) drives the per-ADS EPS alts.

### Step A — offline (no API spend, no network)
```bash
cd backend
pytest tests/unit/test_fpi_currency.py tests/unit/test_fpi_summary.py tests/unit/test_edgar_services.py -q
```
Covers reporting-currency capture (native vs USD-convenience), the `*_per_share` scorer, 20-F
prompt selection, and the `FilingType` enum.

### Step B — live extraction spot-check (SEC only, no provider keys)
```bash
python scripts/verify_fpi_extraction.py BABA TSM ASML
```
Each must show its 20-F + 6-K, a non-None `Financials`, and `TwentyF` sections. Then confirm the
currency-aware path returns the **native** figure (not the USD convenience):
```bash
SKIP_REDIS_INIT=true python -c "import asyncio; from app.services.edgar.xbrl_service import edgar_xbrl_service as s; \
d=asyncio.run(s.get_xbrl_data('0001193125-26-231755','1577552')); print(s.extract_standardized_metrics(d)['reporting_currency'])"
# expect: CNY
```

### Step C — summary quality on the FPI entries (provider keys; reuses Steps 5–7 above)
```bash
python -m evals.runner --candidates baseline --runs 3   # scores all golden entries incl. BABA/TSM/ASML
```
In `evals/reports/eval_*.json`, check the three FPI rows: `num_recall`/`num_precision` (the
scorer is currency-agnostic, so a "RMB 1,023.67B" rendering matches), and **no `gate_fail`**
(no fabricated numbers). Then **read one FPI summary by eye** — non-negotiables:
- figures in the issuer's currency (RMB/TWD/EUR), **never `$`**;
- 20-F item structure (Item 3.D risk, Item 5 MD&A), not 10-K item numbers;
- VIE / PRC-control framing for BABA; no "dual-class" claim.

### Step D — adoption rule → flip
Enable **only if** the FPI rows clear the same bar as domestic (recall/coverage, no gate-fail) **and**
the eyeball check passes. Rollout (mirrors Step 9):

1. **Canary first** — a no-traffic revision with the flag, tested via its tag URL:
   ```bash
   gcloud run deploy earningsnerd-backend --region=us-west1 --image=<current-image> \
     --no-traffic --tag=fpi --update-env-vars=ENABLE_FPI_FILINGS=true
   # hit https://fpi---earningsnerd-backend-...run.app via the Vercel preview / curl, verify /company/BABA
   gcloud run services update-traffic earningsnerd-backend --region=us-west1 --to-tags fpi=100  # promote
   ```
   Or flip the live service directly (all traffic): `gcloud run services update earningsnerd-backend
   --region=us-west1 --update-env-vars=ENABLE_FPI_FILINGS=true`. **Merge semantics** — it survives
   later CI deploys (CI uses `--update-env-vars`, never `--set-env-vars`).
2. **Make it durable** — once validated, add `ENABLE_FPI_FILINGS=true` to the `--update-env-vars`
   list in `.github/workflows/ci.yml` (the `gcloud run deploy` step) so it's declarative, not an
   out-of-band setting. This declaration is already present in CI; do not repeat the rollout
   simply because this historical procedure lists it.
3. **Backfill FPI facts** so the fundamentals chart populates in the issuer's currency:
   `python scripts/backfill_facts.py` (or the `/internal/jobs/backfill-facts` job).
4. **Re-run Step B/C** against prod config to confirm it matches.

### Regenerating / extending the FPI golden entries
The three entries were resolved live (currency captured automatically). To refresh or add more,
resolve only the new ones (re-running the full `build_golden_set` re-resolves all 22 to their latest
filings). Hand-fill is fine for double-tagged filers (ASML tags revenue twice — €32.6673B statement
+ €32.7B rounded — which the extractor correctly drops as ambiguous; the AI still reads it from the
filing text).

## Copilot first live corrective evidence (2026-09-05, PR #703)

The first full 18-attempt run, `33984283703`, completed without execution errors but
returned `accepted=false` (14 passed). Its artifact `9974711370` remains unchanged.
The workflow initially masked the runner's nonzero exit through `tee`; both pipelines
now use explicit Bash fail-fast/pipefail semantics. Three correct MSFT `$13.64` answers
exposed a canonical `USD/shares` versus legacy `_per_share` scorer-unit mismatch; a
Copilot-only adapter preserves native golden/source units and the shared summary bar.
An AAPL text citation joined separated data with an invented ellipsis: that is a valid
hard citation veto, retained as a regression. The prompt now explicitly requires contiguous
text spans and reuse of existing fact markers. Neither invalid citations nor missing source
coverage are relabeled as verified. Several MSFT/historical-BABA outputs used no tools or
citations; their coverage remains an advisory measurement, not sourced-answer evidence.

The concurrent summary run `33984195172` also failed its actual completeness gate:
52 attempts, 51 scored, one BABA timeout. A workflow-level success badge does not override
that failed evaluation. Corrective full gates and fresh actual reports subsequently passed;
no tolerance, expected fact, model, pinned baseline or evidence-snap setting changes.

The accepted runs are linked in the checkpoint above; they do not replace the retained failed
reports. Citation coverage remains advisory: the accepted Copilot run includes five answers
without citations, so acceptance is not a claim that every answer is sourced. Derived arithmetic
still returns unavailable when the stored facts do not supply a compatible duration start.

## Copilot citation-fidelity audit — can users trust the chips?

The Copilot's promise is that every inline citation chip opens provenance for **exactly the claim
it decorates**. The layers below protect that promise; audit them together whenever a prompt, model, or
`copilot_service` resolver change touches the Q&A path (field precedent: legit revenue fact chips
reused as year labels on gross-profit/net-income figures).

**What's enforced automatically, per answer, in production** (`copilot_service._resolve_citations`):

| Layer | Citation kind | Check | On failure |
|---|---|---|---|
| Excerpt verification | text `[n]` | excerpt found verbatim in the filing (`verify_excerpt_in_text`) | chip renders unverified ("Cited", no badge) |
| Marker resolution | both | every inline marker resolves to a declared source | unresolvable F-marker stripped from prose |
| Value adjacency | fact `[Fn]` | a figure matching the fact's value (display-rounding tolerance) must sit in the claim span before the marker — bounded by the previous marker | occurrence stripped, counted as misplaced |
| Concept adjacency | fact `[Fn]` | the claim span must not name a *different* curated metric while never naming the fact's own (right value, wrong label — `_CONCEPT_SYNONYMS`) | occurrence stripped, counted as misplaced |
| Filing origin | fact `[Fn]` | trusted viewed accession and native reporting currency bind every tool query; each returned fact and derived operand retains origin | unavailable tool result, no verified marker |
| Currency adjacency | fact `[Fn]` | explicit ISO/symbol and supported textual currency labels, including inline emphasis/code formatting, must match the adjacent fact | occurrence stripped, counted as misplaced |
| Computed scope consistency | fact `[Fn]` | `copilot_tools._scope_matches_duration`: a derived metric's operands must not carry a fiscal label that contradicts their own reported duration (an `FY`-labelled three-month figure, say) | `basis_unavailable` — no derived value is returned |
| Uncited-claim repair | fact `[Fn]` | `_repair_uncited_fact_claim`: an answer that cites NOTHING and states one complete reported annual figure (subject, full fiscal end date, native currency, amount) gets a server-initiated DB lookup on the viewed accession; the marker is attached only when the filing's own fact matches concept, `period_end`, the filing's period of report, currency, value at the stated display precision, and carries its OWN reported duration inside the annual window (320–390 days) | abstains — the answer ships unchanged and still uncited |
| Figure coverage | — | `count_uncited_figures`: financial figures outside every citation's claim span (the misplacement guards convert wrong chips into *uncited* prose — this counts what shipped naked) | counted, never modified |
| Telemetry | — | `misplaced_fact_markers` / `figure_count` / `uncited_figures` on the complete event, both warning logs, and the same trio on the PostHog `copilot_inference_cost` event | — |

The repair row is the only layer that ADDS a citation, so it is positive certification rather than
falsification: a missing, ambiguous or partly matching fact abstains and the answer stays uncited.
It reads no SEC endpoint, makes no second model call and rewrites no prose — the marker is the only
byte inserted, and the resolver above still owns numbering and provenance. The lookup is
server-initiated and carries `_origin = "server_citation_lookup"`, so it never enters model
tool-call history. `count_uncited_figures` stays advisory and is never consulted.

**Duration is the binding proof. Newly ingested facts now carry it; rows written earlier do not,
and still abstain.** The annual form and the `FY` label are one signal, not two: `facts_service.
_fiscal_period` derives `FY` from the form. The companyfacts fallback in `edgar/xbrl_service.py`
only *ranks* the durations sharing a period end, so a lone three-month point ending on the fiscal
year end is kept and still reaches the fact table labelled `FY`, passing `_valid_fact_provenance`.
Certifying on the label would put a verified chip on a possibly-quarterly figure, so a fact whose
own duration does not span the claimed year abstains — as does one with no `period_start` at all,
including the retained BABA row that motivated this layer.

Extraction preserves the source duration forward-only through the per-filing instance and
companyfacts fallback paths. `duration_series_with_starts` retains the instance fact's start;
`append_items` retains the selected fallback fact's start; `normalise_series` passes it through;
`normalize_standardized_to_facts` stores it in the existing nullable column. The founder approved
the T9 expected-dictionary additions on 2026-09-12. Selection, precedence and upsert skip semantics
are unchanged. Newly inserted facts with proven annual duration can certify; existing undated
rows still abstain, and there is no backfill.

Preserving those dates also unblocked `compute_metric`, which had been inert on mislabelled rows
only because they carried no duration. Two three-month figures labelled `FY` from the form computed
a 25% growth rate carrying `fiscal_period: "FY"`, accepted by `_valid_fact_provenance` — a
quarter-over-quarter change presented as annual. The annual certifier guards only the
uncited-repair path and `_prior_comparable` is satisfied by Q4-versus-Q4, so neither caught it.
`copilot_tools._scope_matches_duration` now refuses a computed claim whose fiscal label contradicts
its own reported duration, on every operand backing the result (current, yoy prior, margin
denominator). Stored rows, selection, numeric precedence and direct `get_financial_fact` lookups
are unchanged: legitimately quarterly facts still compute, labelled as the quarters they are.

Durations are deliberately excluded from the model-facing compact block
(`_without_source_durations`), so prompt bytes are unchanged — widening what the model sees is a
prompt change with its own evidence requirements.
`tests/unit/test_copilot_citation_repair.py::test_quarterly_point_in_an_annual_filing_never_certifies`
drives that whole transformation through production code.

**Offline gates (CI, free, every PR):** `pytest tests/unit/test_copilot.py tests/unit/test_copilot_evals.py tests/unit/test_copilot_citation_repair.py tests/unit/test_copilot_paired_claims.py -q`
— covers the resolver's strip/keep behavior and the eval scorers (including `score_fact_marker_adjacency`,
which re-runs the SAME production matcher + window rule over the final answer, so a resolver
regression can't hide from the harness).

**Complete live acceptance (same-repository PR, explicit Ready for review opt-in):**
`copilot-eval.yml` stays skipped while the PR is draft. After the full offline gate and three
independent review lenses, the orchestrator marks it ready. The dedicated workflow responds to
`ready_for_review` and subsequent non-draft pushes; existing summary CI does not claim an automatic
restart on that event. Acceptance still requires its separate full summary artifact against the
sole unchanged baseline.

The workflow prepares six verified accessions/five issuers in a new file-backed SQLite database
using only `copilot_sources.json` identities and the production SEC/excerpt/fact paths. It records
source and database SHA-256 hashes, plus the source-only SQLite artifact. Questions and expected values never enter extraction. Both
BABA accessions coexist, so a same-valued newer comparative cannot impersonate the viewed filing.
Only after successful source preparation does the runner receive the existing Actions generator
credential and run all six vetted numeric questions three times (18 attempts). Original unverified
qualitative/refusal questions remain unchanged under `pending_cases`; they are not silently certified.

The runner requires exactly one valid terminal completion per attempt, all planned identities,
zero execution errors and no trust/accuracy veto. Valid refusal completions preserve the production
contract, which omits the strip counter. Every declared XBRL citation is checked before
numeric filtering for viewed accession, finite value, unit and period; derived operands need their
own origin and known basis. Normalized facts may have a null raw XBRL tag; absence is preserved
without inventing a tag or discarding otherwise valid source provenance. A used expected-metric citation must match that QA's declared period.
Explicit wrong currency also vetoes a same-magnitude answer without a citation. Missing citation
coverage remains advisory. Runtime per-filing facts currently omit duration starts: direct lookups
remain available, but derived unknown-duration arithmetic returns `basis_unavailable` without
inventing dates. No production backfill is needed for this gate.

Artifacts always retain preparation evidence, complete emitted answers/citations, initial input
messages, every actual tool name/arguments/result (including unused or rejected results), elapsed
times, and denominator counts, including failures. This semantic tool trace is not claimed to be
a full native HTTP conversation transcript. `requested_model` is configured;
`actual_model` remains unavailable in the report and per-call actual model/usage is recorded only by
sanitized provider telemetry. Unknown cost is not free. Source-preparation failure means zero
provider calls and requires diagnosis. No live acceptance result is claimed by implementation or
offline tests. The first weekly strong-judge readout and evidence-snap activation remain held.

**Gating rule — two different standards (July 2026, learned the hard way):**
- **Resolver/guard changes** gate DETERMINISTICALLY: the offline suites replay real failure shapes
  through `_resolve_citations` with no model in the loop (`pytest tests/unit/test_copilot.py
  tests/unit/test_copilot_evals.py`). Never gate a resolver change on a live run alone.
- **Prompt/model changes** gate on `--runs 3` (or more) AGGREGATES, never a single draw. Measured
  spread on IDENTICAL prompts reached 62%↔81% pass rate run-to-run — a single before/after is
  noise. The aggregate's TRUST line (rows with `Fact adj` < 1.0 across any run) is the hard veto.
- **Negative result on record:** pushing citation-density via prompt ("EVERY figure must carry a
  marker", "call compute_metric for derived numbers") made placement *worse* — the model fetched
  growth metrics it then reused across other metrics' growth figures, and dense marker runs
  produced the window-shielding bypass (since fixed in the resolver: stripped markers no longer
  bound adjacency windows). Coverage stays a WARN-level telemetry signal; do not re-attempt
  density-forcing prompts without a `--runs 5` aggregate showing the TRUST line clean.

**Production watch — alerting (one-time setup):** don't rely on reading logs; make drift find you:
```bash
bash backend/scripts/setup_citation_alerts.sh you@example.com
```
Idempotent (re-runs reuse existing resources). Prerequisites: authenticated `gcloud` for project
`earnings-nerd` with the `alpha` + `beta` components, and a deployed backend that includes the JSON
formatter's `severity` field (shipped with the script). Creates log-based metrics
`copilot_misplaced_fact_markers` + `copilot_uncited_figures` (matching the resolver's WARNING lines
in `jsonPayload.message` or `textPayload`), an "EarningsNerd Alerts" email channel, and two policies:
misplaced markers fire on ANY occurrence per hour; uncited figures on > 5/hour (occasional uncited
numbers are normal — the alert is for elevation). The same counters ride the PostHog
`copilot_inference_cost` event for dashboard trends. Baseline both after each deploy; a step-change
tracks model/prompt drift even with zero user reports.

**Manual spot-check protocol (quarterly, or after any model swap):** take 3 recent real answers
with fact chips; for each chip, open the popover and confirm (a) the excerpt's metric+period matches
the sentence the chip sits on, and (b) the figure matches the filing's XBRL (`financial_fact` row).
Ten minutes, catches what the automated checks still can't: a mislabel phrased outside
`_CONCEPT_SYNONYMS`, a wrong *period* with the right value, or a concept outside the curated map.

---

## Multi-Period Analysis narrative gate — bumping `trends-v1`

The Multi-Period Analysis narrative (`trend_analysis_service.stream_trend_narrative`, prompt
`prompts/trends-analyst-agent.md`) shares the Copilot grounding philosophy with a stricter input:
the model receives ONLY the pre-computed dataset (every value pre-marked `[F#]`), so any number
outside the dataset is a fabrication by construction.

**What's enforced automatically, per generation, in production** (`resolve_narrative_citations`):
every inline `[F#]` must resolve to a dataset marker (unresolvable markers are stripped from the
prose); resolved markers renumber into one continuous `[1]..[n]` sequence that always agrees with
the citations list; `grounded` (resolved-citation count) rides the complete event and the PostHog
`analysis_inference_cost` event.

**Offline gate (CI, free, every PR):** `pytest tests/unit/test_analysis_stream.py tests/unit/test_trend_analysis_service.py -q`
— pins the event contract, marker resolution, and the D4 cache semantics.

**Before bumping `PROMPT_VERSION`** (which invalidates every cached narrative fleet-wide and
regenerates on demand):
1. Run the offline gate above.
2. Manual spot-check protocol: generate fresh analyses for 3 diverse real companies (a calendar-FY
   tech, a Jan-FYE retailer like WMT, a bank like JPM) in both modes. For each: (a) every figure in
   the prose carries a chip and the chip's metric+period matches the sentence; (b) the Red flags
   section addresses each deterministic signal in the dataset (or reasonably dismisses it); (c) no
   number appears that isn't in the dataset (spot-check 5 per narrative against the metrics table).
3. Watch `analysis_inference_cost.grounded` for a step-change after rollout — a drop means the new
   prompt is citing less; treat like the Copilot marker alerts.

A future `trends_golden_set.json` + scorer (re-verifying every `[F#]`-adjacent number against the
dataset, the `copilot_scorers` pattern) is the intended automation of step 2.

## Gotchas
| Issue | Mitigation |
|---|---|
| EDGAR 403 / empty filings | Valid SEC User-Agent in env; respect ~10 req/s |
| Small-cap `verified:false` after build | Fill `ground_truth` manually from the filing |
| Cost surprise | `--limit` + fewer `--runs`; fix `models.py` price placeholders |
| `anthropic` ImportError / no key | `pip install anthropic`; judge/Claude degrade to a FAIL-with-error row, not a crash |
| Wrong ground truth | Spot-check against the filing — it silently corrupts every score |
| FPI figure renders as `$` | Reporting currency not captured — re-check `reporting_currency` (Step B); the value must be native (RMB/EUR/TWD) |
| FPI metric missing (double-tagged) | Filer tags the same line twice (statement + rounded) → dropped as ambiguous; hand-fill ground truth from the statement value |
| Huge 20-F section parse very slow (e.g. ASML >120s) | `get_filing_sections` caps at 40s and returns None → pipeline falls back to the fast dense-window extractor (lower precision, still usable). Expected, not a failure; don't raise the cap (it would block generation for minutes). |

### September parity measurement: component omission

The first parity run (CI `33960565273`, 26 verified filings × 2 repeats) completed
with zero execution errors but failed the unchanged hard regression gate: both JPM
results omitted noninterest income (G5; 2/52 vetoes). The component facts remain in
the golden set. An independent live SEC extraction returned both components and
JPM's legitimate reported total. The financial-institution directive now distinguishes
reported totals from no-total banks, and existing deterministic summary assembly owns
available component rows using aligned XBRL periods/currencies. It replaces model
component rows, including their incompatible commentary/evidence, without inventing
verbatim quotes. Reports retain the actual `xbrl_grounding` used for each result so
future failures can distinguish extraction absence from generation omissions.

This failed measurement was not pinned. The sole authoritative three-run measurement
subsequently ran on source `f5b46ba96b3023f93554087e431937ed9daba3c4`, including deployed
WS-7 #697, in run `33962580838` (artifact `9968531910`). All 78 results had no execution
errors or hard vetoes. #698 committed the exact measured baseline and deployed; #700 later
added measurement dimensions without changing that pin. The first actual weekly strong-judge
readout is still required before evidence-snap activation; since 2026-09-15 it waits on a
generation artifact and the founder's local `/judge-readout` run (next section), no longer on a
credential.


## Weekly strong-judge measurement (WS-6 step 2; two-phase since W3-7, 2026-09-15)

`data-quality-weekly.yml` measures the committed `weekly_cohort.json`: AAPL/JPM annual,
NVDA/KO/BYND quarterly, ASML/BABA 20-F and MELI annual, exact verified accessions, three repeats
and 24 required identities. The strong judge is `cli:claude-fable-5-1` (`app/services/ai_readout.py`
`JUDGE_MODEL` / `JUDGE_BACKEND`): Fable 5.1 through the founder's Claude subscription CLI, not an
API-credit model. CI has no subscription session, so the measurement runs in two phases:

1. **Generate (CI, Mondays 13:00 UTC).** `python -m evals.weekly_readout --generate-only` produces
   the 24 attempts with the CI-only generator credential and retains every attempt's judge inputs
   (canonical payload, grounding excerpt, XBRL grounding, application-owned statement evidence) in the
   `weekly-judged-readout-<run_id>` artifact. Its handoff is an explicit `unavailable … pending`
   readout, so that Monday's email says exactly that. `ANTHROPIC_API_KEY` appears nowhere in the workflow.
2. **Judge (founder's Mac, a fresh chat, `/judge-readout`).** `python -m evals.judge_readout
   <artifact>/report.json` replays exactly the retained inputs through `runner._maybe_judge` (same
   excerpt, statement evidence, XBRL serialization and full-coverage bounds; nothing is re-fetched or
   regenerated) with `claude -p` on the subscription, then builds the readout through the same
   cohort/golden/identity validation. Outputs land under `evals/reports/weekly-judged/<stamp>/`.
   A report whose golden set, cohort or attempt identities differ from this checkout is refused
   before the first judge call. `--judge` accepts another id only for an agreement check: its
   verdicts are retained in the judged report and the readout stays unavailable. The per-attempt
   verdicts are durable only where the skill records them (`tasks/review-evidence/w3-7/…`): the
   readout links the generation run, whose artifact holds unjudged attempts.
3. **Deliver (live email; ask the founder first).** `gh workflow run data-quality-weekly.yml -f
   readout_b64="$(cat …/readout.b64)"` re-sends the data-quality email with the judged readout and
   retains the bounded readout as that run's artifact; the dispatch installs nothing and generates
   nothing, and a readout that fails validation turns the run red instead of emailing silently.

Generator identity in the handoff is the configured/requested model, not yet response-model
telemetry. Do not trigger the live email workflow during development, arm evidence-snap from
unavailable or partial data, or raise the judge input bounds or edit the golden set to make a
verdict fit. Bound history: the first readout (2026-09-15, run 35012740718) judged 15 of 24 because
ASML (260k), MELI (250k with its statement descriptor) and BABA (231k) exceeded the 200,000-character
excerpt bound inherited from the Opus judge; with the founder's approval the bound is 400,000
characters for the 1M-context contract judge (`judge.py::_JUDGE_EXCERPT_CHAR_CAP`), and an attempt
over it is still an explicit judge error, never a truncation. A partial readout is reported as
partial. The judge subprocess replaces Claude Code's default system prompt with the judge framing,
disables tools and settings-defined MCP servers, persists no session and runs outside the
repository so no `CLAUDE.md` enters its context (`judge.py::_judge_via_cli`). The separate
`requirements-eval.txt` pins the optional API-credit judge SDK for a local Opus agreement check;
CI no longer installs it, and it is not a production runtime dependency.

Judge input includes full canonical JSON (100k-character bound), source excerpt (400k since
2026-09-15; 200k before) and XBRL serialization (40k). Bounds are checked before truncation; overflow is an explicit judge
error, and per-result input lengths/completeness are recorded. This fixes the observed BABA
22,020-character payload whose footnote evidence was previously silently cut at 20k. No model
prompt or deterministic score/weight changes accompany this measurement correction.

The artifact retains full result evidence, requested harness flags, source/golden/cohort hashes,
and raw v2 sections/excerpt for figure-trace replay. The compact base64 handoff is size/schema/
provenance/link validated once by `app.services.ai_readout`; invalid or absent handoffs show
unavailable in the ordinary report. The scheduled report runs even when measurement fails.
`complete` means all 24 attempts have valid full-input judgments, including honest negative
verdicts; missing/error judgments produce partial/unavailable status. No status auto-arms a flag.

`mean_untraceable_dollar_figures` reuses the production tracer on raw model prose, excluding its
machine tables and quote fields. It counts unique dollar-scale figures per measured output;
metadata-only XBRL, missing raw sections or absent numeric grounding are unavailable, not zero.
The JSON/Markdown report exposes measured/unavailable/error denominators. Any nonzero measured
mean emits an absolute WARN, never a hard veto or aggregate change. The parity pin lacks this new
metric; the gate explicitly says no reference measurement and does not invent a zero baseline or
silently skip the advisory. No retrospective metric is fabricated from the older artifact, which
lacks raw sections/excerpt. Persisted audit snapshots and these 24 weekly attempts have separate
denominators; an empty historical audit does not prove grounding existed.


### Current-schema preview completion (2026-09-09)

Progressive previews render only complete original JSON section dicts/lists through the current
shared section projection. The root object may still be open; unfinished sections remain pending,
without repaired scalars or legacy disclosure-absence fallbacks. Inputs above 256,000 characters
produce no new preview. Final generation, repair, normalization and rendering remain unchanged.
Observed callbacks are still optional and may be coalesced before browser delivery. Their retained
scope includes internal provider retries and does not certify association with the final provider
attempt; complete section syntax does not establish factual/source correctness.


**Preview ownership correction (September 9, first #803 actual readout).** Complete section
syntax alone did not prevent model-authored segment figures from appearing before final processing
removed them. Previews now reuse `_apply_structured_fallbacks` and the bank-row sanitizer on the
freshly parsed copy, then retain only section keys already complete in the stream. An originally
empty lead remains pending rather than acquiring the final degraded-detail notice. Thus code-owned
fields are derived or suppressed by their existing final owner; missing sections remain pending.
Working-capital/cash-flow fields still follow that owner's conditional overwrite behavior when
facts are available, rather than a new unconditional removal policy. If `AI_FORWARD_QUOTE_GATE`
is armed, attributed quotes wait for final verification because the preview callback has no source
excerpt. This conservatively delays even valid, short or no-excerpt quotes; final quote policy and
all flag defaults remain unchanged. The initial #803 artifact remains retained as a failed preview
ownership readout; corrected actual acceptance is a separate requirement.

### Provider usage conservation (September 12 migration audit correction)

Baseline result `provider_usage` and `latency_seconds` describe the final generation, including
when it fails. `retry_provider_attempts` retains every earlier generation's error, elapsed time
and observed usage; the existing bounded retry-preview evidence is unchanged.
`incurred_provider_usage` sums those disjoint generations once, and `incurred_latency_seconds`
measures total wall time including retries, backoff and scoring. Neither includes separate judge
provider usage. Candidate summaries retain their existing final-generation token means/totals and
add `incurred_provider_usage` with `incurred_usage_attempts` as its result-row denominator.

Token totals are sums of known provider counters, not full billed spend. `unknown_calls` counts
calls with no known usage fields; partially reported fields can also leave token totals incomplete.
Missing counters remain null. Older reports without incurred evidence remain unavailable in the
new summary fields; their final-attempt totals cannot reconstruct failed-generation costs. No
baseline or historical report is rewritten by this correction.


## September 13 financing-comparison acceptance

New capital-allocation output is a code-owned financing comparison plus exact primary/recovery filing passages, authorized by an explicit outer envelope. Existing unrestricted capital-allocation/highlight prose is not a fallback inside that new representation; old summaries remain legacy. Source descriptors require original cached XML context/unit evidence, not only empty SDK dimensions. Copilot compact context excludes these internal descriptors.

Before accepting this slice, inspect actual MELI source/current/prior descriptors and visible final/preview direction, plus retained AAPL program/per-share disclosures. Green aggregate scores do not establish those semantics. Unknown sources, broader financial explanations and issuer-adjusted FCF remain open. See [implementation evidence](../../tasks/financing-comparison-2026-09-13.md). No baseline floor is changed by this record.

Second-assessment correction: inspect explanation preservation in every draw, including when the model supplies nonempty table labels or program quotations. The source-owned internal passage is selected independently; table labels followed by numeric cells are rejected. Exact source matching and aggregate PASS alone do not prove useful explanation. Prior-period passages retain their dates and generic filing attribution.


## Selected Outlook source acceptance

A fresh selected MD&A can append one complete heading-delimited Outlook supplement, with a separate wrapper-inclusive 6,000-character allowance. The existing primary excerpt remains byte-identical before the addition; only forward recovery receives the complete supplement beyond its existing 30,000-character allocation. Cached excerpts are not invalidated. The content stamp advances to `summary-2026-09-j`, without scheduling regeneration.

Actual acceptance must verify Ford's complete source block reaches both primary and any forward recovery, inspect adjusted EBIT/FCF ranges with their labels and assumptions, and check all other source and financing/debt outputs for unintended displacement. Existing nonqualifying forms and incorporated exhibits remain outside this narrow boundary grammar. No baseline change or quality clearance follows from source availability alone.

## Paired annual Copilot claim acceptance

The finite annual revenue/net-sales plus net-income sentence may receive two server-owned chips only after both facts independently certify and share actual annual dates, currency and accession. The original one-claim grammar is unchanged. Unsupported, surviving partly cited or differently qualified text abstains. When the resolver removes invalid markers and leaves wholly uncited visible prose, the same positive certification may repair that visible claim. Rejected markers never supply evidence; original strip telemetry is retained. No model retry or historical backfill is added.

Actual acceptance checks the retained ASML wording, separate concept-correct chips and unchanged prose, alongside all other requested answers. Net-income raw-tag/accounting-basis provenance remains incomplete and must not be advertised as US-GAAP certification. Generic table-overclaim and quote-fidelity defects remain separate.


## Conventional cash claims in lead text

Supported whole OCF/FCF current/prior sentences and the two retained mixed cash/assets forms receive source-owned dated cash values and the existing conventional selected-capex basis. Both selected components must supply matching dates/currencies and reproduce the derived FCF amount. An explicit OCF YoY percentage additionally needs comparable actual annual durations and matching signed growth. The assets suffix is preserved as model prose, not newly certified. Financial-institution suppression remains controlling.

Acceptance must inspect actual lead wording, not just the already-qualified cash-conversion field. Preserve unrelated headline/takeaway text and assets suffixes, and verify both final and preview output. Unsupported paraphrases remain uncorrected; this is not a universal cash-claim or issuer-adjusted FCF gate. The content stamp advances to `summary-2026-09-k`; schema remains 2, with no automatic regeneration or historical replay.

September 13 applicability correction: the new lead qualifier additionally requires affirmative
nonfinancial classification from the selected instance's existing company metadata. Positive
financial profile/category/SIC evidence dominates; absent bank components do not qualify an
issuer. Missing, malformed, unclassified or uncached classification remains unknown and abstains.
This internal sidecar is excluded before model/eval/Copilot context caps and is not a financial
fact. No extra fetch or classifier call is added. The older bank-only cash-conversion behavior is
unchanged; its broader financial-profile applicability gap remains separately open.

Historical persisted/cache metrics and companyfacts fallback lack this evidence and remain
unqualified. Earlier retained-input proofs predate this added prerequisite: forward-classified
controls must be labelled as such, while exact historical rows remain unchanged. Actual
assessment must inspect fresh classification and confirm all other source/metric bytes remain
identical after removing only the new metadata. Do not retrofit classification into retained
evidence or treat aggregate PASS as universal lead coverage. The optional explicit prior-year
suffix additionally requires actual January 1–December 31 coverage of that year.

```bash
python -m pytest tests/unit/test_cash_claims.py tests/unit/test_cash_financial_applicability.py
```

## Reported operating-to-pretax relationships

Eligible fresh primary HTML supplies a separate application-owned statement context. A unique
complete statement, explicit dates/units, individual numeric cells and signed reconciliation
qualify the reported operating-to-pretax rows. The shared preview/final owner replaces only the
operating-versus-one-time slot and preserves supported complete expense, comparative, tax and
presentation disclosures. Statement position does not establish recurring or one-time status.
The content stamp is `summary-2026-09-l`; schema remains 2, and no regeneration is scheduled.

The ordinary pipeline and eval reuse their already-fetched selected primary document. The
context never enters generator/recovery messages or standardized XBRL and creates no additional
SEC/model call. Cached-only and unsupported sources remain legacy. A fresh document can coexist
with an older cached excerpt: its independent source evidence must not be described as text the
generator saw. Unsupported disclosure status is not evidence that no disclosure exists.

Before acceptance, inspect eligibility across every actual cohort source, signed MELI/SE rows,
complete preserved explanations and preview/final/export agreement. The 26 retained-source
offline inventory qualifies only MELI and SE; that does not predict every production request.
Optional judges receive the full separate descriptor before cap checks. MELI's retained excerpt
already exceeds the 200,000-character cap without the descriptor, so that review is explicitly
incomplete; do not truncate or infer a pass. No judge cap or baseline is changed.

Offline controls (no provider call), from `backend/`:

```bash
python -m pytest tests/unit/test_statement_relationship_source.py tests/unit/test_statement_disclosures.py tests/unit/test_statement_relationship_integration.py tests/unit/test_eval_measurement.py
```

See [implementation and proof evidence](../../tasks/operating-pretax-source-local.md). Full
committed gates, actual source/output acceptance and serial production verification remain
required; local source eligibility does not establish world-class analysis quality.

## Derived cash-card applicability correction — September 13, 2026

The earlier cash-lead record's open financial-profile gap is addressed for new generation.
Both conventional cash owners now require affirmative nonfinancial classification and retain
the bank-components veto. Financial and unknown inputs withhold the derived cash-conversion
card, after stripping any model-authored replacement. Basic reported cash flows and source-owned
financing/statement explanations remain. Content stamp is `summary-2026-09-m`; schema remains 2.
No replay or regeneration is scheduled.

Actual assessment must confirm COIN's previously admitted card is absent, JPM remains absent,
and other eligible cohort cards and all source-owned fields are preserved. Classification is
not certification of economic meaning: MELI customer funds, adjusted FCF and the usefulness of
its ratio remain separate unresolved work. Unknown historical inputs are not retroactively
classified. See [implementation and mutation evidence](../../tasks/cash-card-applicability-local.md).

## Judging a pull request's eval artifact (prompt-candidate acceptance, 2026-09-16)

The weekly readout judges only the fixed cohort. A prompt candidate needs its own semantic acceptance,
and the September 9 #805 assessment showed why a deterministic-only gate is not enough: correct tables
with false explanations pass every scorer. `evals.judge_report` judges **any** retained eval report —
a pull request's `eval-baseline` artifact (`backend/evals/reports/eval_<stamp>.json`, 35 × 2 attempts
with the payload, grounding excerpt, XBRL grounding and statement evidence retained) or a local run —
through the same harness judge path as the weekly readout, on the founder's subscription
(`cli:claude-fable-5-1`), with no generator credential and no re-fetch.

```bash
gh run download <run_id> --repo neilmac91/EarningsNerd -n eval-report-<run_id> -D /tmp/eval-<pr>
cd backend && python -m evals.judge_report /tmp/eval-<pr>/eval_*.json --output-dir evals/reports/judged/pr<pr>
```

Outputs: `judged.json` (every attempt with a fresh verdict; any verdict the report carried is
discarded) and `judged.md` (gate counts, the per-attempt verdict table, and a **#805 negative
controls** section: AAPL, AMZN, BA, JPM, MELI, NVDA, PFE, PLTR, RIVN). Exit 0 only when every
judgeable attempt has a complete verdict; 2 when provenance is refused before any call (golden set
differs from the checkout, duplicate or foreign attempt identity, no attempts).

**Before a long judge run, probe the subscription.** The judge is the founder's Claude subscription
and it has a usage limit. When it is reached every call returns exit 1 with an empty stderr and the
reason only in the JSON body (`result`: "You've reached your Fable limit"), so a whole 70-attempt run
can come back with zero usable verdicts. Probe first and check `is_error` is false:

```bash
claude -p --model claude-fable-5-1 --output-format json --tools "" --strict-mcp-config --no-session-persistence --system-prompt "Answer in one word." "Reply with exactly: OK"
```

The retained artifact survives an exhausted subscription: judge it again once the limit resets, and
never swap in a different judge model to get past it (verdicts from two judges are not comparable).
Quote denominators from `judged_summary.judged`, not the attempt count.

**Two runs, not one.** Quote a prompt change's effect from at least two independent generated runs per
configuration and report the range. The `o`-versus-`n` comparison of 2026-09-16/17 showed a candidate
run-to-run spread (54% and 66% of attempts judged negative) almost as wide as its gap to the control,
so a single run sets a direction but does not size an effect
(`lessons/evals-accept-a-prompt-change-on-two-runs-not-one.md`).

**Judge contract version 2** (`evals.judge.JUDGE_CONTRACT_VERSION`, `JUDGE_GATES`) adds two gates to
G2/G3: **G4 unsupported_cause** (a driver or attribution the source does not state; co-movement is not
cause) and **G5 basis_mismatch** (measure, scope, period, accounting or tax basis, unit or the number's
role changed; an ex-item total the filing does not define; "accelerated" without a prior rate; a
reversed sign). Every verdict and judged harness records the contract version; the September 15
weekly readout was judged under version 1 (G2/G3 only), so its negative count is not comparable to a
version-2 count without re-judging its retained `report.json`.

Acceptance bar for a grounding candidate (from the assessment): the negative controls move from a
false explanation to abstention (no G4/G5 failure), no new G2/G3 failure, and the deterministic
regression gate unchanged. A better mean dimension score is not the bar. Before the first use as a
gate, hand-check about five verdicts: the judge's own accuracy on causal claims is unmeasured.
