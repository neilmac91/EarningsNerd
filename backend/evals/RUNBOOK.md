# Adoption-Gate Runbook

How to run `backend/evals/` for adoption decisions and ongoing regression measurement.
Live runs need SEC EDGAR network access and provider API keys; CI uses its existing Actions
secret. Offline scorer/parity tests need neither: `pytest tests/unit/test_eval_*`.

The original adoption steps below remain a procedure for future comparisons. Current code
defaults and deployment overrides are documented in `docs/CONFIGURATION.md`: the quality gate
and native edgartools sections are already on, structured-output mode remains off, and CI's
service deployment enables FPI filings and progressive section reveal. Do not infer live state
from an old rollout example.

Verified checkpoint (2026-09-05): resilience #701 merged as `f4c6041f`; deployment
[33977786320](https://github.com/neilmac91/EarningsNerd/actions/runs/33977786320) applied 0
migrations and skipped 34, with revision `00266-q6k` serving all traffic and detailed health
healthy. The sole #698 baseline pin remains unchanged. Hygiene and Copilot work, the first
actual strong-judge readout, and readout-dependent evidence-snap activation remain unfinished.

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
export AI_DEFAULT_MODEL=deepseek-v4-pro
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
| `claude-opus-4-8` (default) | anthropic SDK | `ANTHROPIC_API_KEY` (API credits) | Authoritative audits, re-pinning baseline |
| `cli:sonnet` / `cli:opus` | subscription CLI (`claude -p`) | logged-in Claude subscription (OAuth); `ANTHROPIC_API_KEY` is stripped from the child env | Local/manual gates — **no OAuth in CI** |
| `glm-5.2` / `openai:<model>` | OpenAI-compatible chat | `JUDGE_OPENAI_BASE_URL` + `JUDGE_OPENAI_API_KEY` (falls back to `OPENAI_*`) | Cheap CI/fallback judge |

**Agreement check before trusting a cheaper backend as the gate.** The default stays Opus so a
cheaper judge can never *silently* weaken the bar — but before you rely on one, run the same
`--forms <form> --runs 3` set through both it and `claude-opus-4-8` and confirm the verdicts and
per-dimension means agree within noise. (Wiring smoke on a synthetic G3-hallucination case:
`cli:sonnet` matched Opus exactly `{faith2,insight2,clarity4,spec3}`; `glm-5.2` was within 1 pt —
both fired the same G3 gate.) For `cli:*`, unset `ANTHROPIC_API_KEY` in your shell first, or it
will still route through the subscription (the child env strips it) — but confirm you are logged in
(`claude -p --model sonnet -p "ok"`).

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

### Re-pinning the baseline

Routine `eval-baseline` PR runs evaluate the complete verified set twice. Manual CI dispatch
accepts only `eval_runs=2` or `3`; use **3 with blank limit** for the authoritative pin.
The workflow uses its existing `DEEPSEEK_API_KEY` secret; do not extract it to a local machine.
Inspect both the actual runner and regression-gate logs (the job is advisory), then download
the JSON/Markdown `eval-report-<run_id>` artifact. Keep the run ID, source SHA and report name
in the PR. Two repeats improve the granularity of mean/WARN measurements; they do **not**
excuse a hard veto (one failed filing-run out of 52 still exceeds the 0.005 hard tolerance).

Reports capture the actual model, provider URL, statement/stream/extraction and trust flags,
judge selection, GitHub source SHA and golden-set SHA256 where the model runs. The pin tool
uses that metadata, never the local machine's model environment. It refuses missing or
changed golden-set provenance, fewer than three runs, a subset, missing/duplicate runs,
errors, hard vetoes/missing gate evidence or inconsistent counts/pass rates. Older reports without this provenance must be measured anew.
An existing `note` survives re-pinning; `--note "..."` explicitly replaces it. Preserve
provenance and explain intentional bar changes rather than performing cosmetic re-pins.
A reported baseline `total_cost_usd=0` is currently unmetered, not proof of a free model run.

The wave-2 parity pin is complete in #698: `eval_20260905T111951Z.json`, 26 × 3,
source `f5b46ba9`, zero errors/vetoes, PASS/0 warnings. Measure later work against it.
Re-pin only for an explicitly justified model/prompt, structured-output, extraction-library or
armed-guard change with actual before/after evidence. Adding an advisory dimension or observing
changed scores alone does not authorize a cosmetic replacement. From `backend/`:
```bash
python -m evals.runner --candidates baseline --runs 3            # full verified set
python scripts/pin_baseline.py evals/reports/eval_<stamp>.json   # rewrite baseline_scores.json
```
Then commit the new `baseline_scores.json` in the same PR as the change it protects, so the diff
shows both the code change and the new bar. **BRK.B is `verified: false`** (no consolidated EPS
fact) and is auto-excluded by the runner — leave it out of the pinned set until its ground truth
is hand-filled.

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
| Figure coverage | — | `count_uncited_figures`: financial figures outside every citation's claim span (the misplacement guards convert wrong chips into *uncited* prose — this counts what shipped naked) | counted, never modified |
| Telemetry | — | `misplaced_fact_markers` / `figure_count` / `uncited_figures` on the complete event, both warning logs, and the same trio on the PostHog `copilot_inference_cost` event | — |

**Offline gates (CI, free, every PR):** `pytest tests/unit/test_copilot.py tests/unit/test_copilot_evals.py -q`
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
source and database SHA-256 hashes. Questions and expected values never enter extraction. Both
BABA accessions coexist, so a same-valued newer comparative cannot impersonate the viewed filing.
Only after successful source preparation does the runner receive the existing Actions generator
credential and run all six vetted numeric questions three times (18 attempts). Original unverified
qualitative/refusal questions remain unchanged under `pending_cases`; they are not silently certified.

The runner requires exactly one valid terminal completion per attempt, all planned identities,
zero execution errors and no trust/accuracy veto. Every declared XBRL citation is checked before
numeric filtering for viewed accession, finite value, unit and period; derived operands need their
own origin and known basis. A used expected-metric citation must match that QA's declared period.
Explicit wrong currency also vetoes a same-magnitude answer without a citation. Missing citation
coverage remains advisory. Runtime per-filing facts currently omit duration starts: direct lookups
remain available, but derived unknown-duration arithmetic returns `basis_unavailable` without
inventing dates. No production backfill is needed for this gate.

Artifacts always retain preparation evidence, complete emitted answers/citations, actual input
messages, elapsed times, and denominator counts, including failures. `requested_model` is configured;
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
readout remains credential-held and is still required before evidence-snap activation.


## Weekly strong-judge measurement (WS-6 step 2)

`data-quality-weekly.yml` measures the committed `weekly_cohort.json`: AAPL/JPM annual,
NVDA/KO/BYND quarterly, ASML/BABA 20-F and MELI annual, exact verified accessions, three repeats
and 24 required identities. It uses the configured `claude-opus-4-8` Anthropic judge; generator
identity in the handoff is the configured/requested model, not yet response-model telemetry.
Both credentials are checked before generation. The current founder credential is absent: no
first judged readout is claimed. Do not substitute a cheaper judge without its agreement study,
trigger the live email workflow during development, or arm evidence-snap from unavailable data.
The separate `requirements-eval.txt` pins the judge SDK and additional transport dependencies;
they are not production runtime dependencies.

Judge input includes full canonical JSON (100k-character bound), source excerpt (200k) and
XBRL serialization (40k). Bounds are checked before truncation; overflow is an explicit judge
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
