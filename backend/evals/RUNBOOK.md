# Adoption-Gate Runbook

How to run `backend/evals/` as the **one-time adoption gate** that decides whether to enable the
default-off summary re-architecture. Operator task — needs SEC EDGAR network access + provider
API keys. (Offline scorer tests need neither: `pytest tests/unit/test_eval_*`.)

## What you're deciding

Three independent, default-off changes live in `app/config.py`. The eval tells you which to enable:

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
export OPENAI_API_KEY=...       # baseline + gemini-json (Google AI Studio)
export OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
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
  summarization uses the OpenAI-compatible client pointed at Google; routing to Anthropic needs an
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

Steps 1–9 are the **one-time adoption gate**. B1 makes that durable: it pins the current
production-pipeline quality and gives a deterministic, CI-runnable check that a change hasn't
eroded it — the safety net under any future output-quality work (and before a large precompute run).

Three pieces:

| Piece | What it is |
|---|---|
| `baseline_scores.json` | The pinned bar to protect — the `baseline` candidate's summary stats from a full verified-set run, committed to git. |
| `regression_gate.py` | Deterministic per-dimension diff of a fresh `reports/eval_*.json` against the pinned baseline. Exits non-zero on a HARD regression. |
| `eval-baseline` CI job | Advisory (non-blocking) job in `.github/workflows/ci.yml` that runs the live pipeline on a few golden filings per AI-relevant PR and runs the gate. |

### Running the gate locally
```bash
cd backend
python -m evals.runner --candidates baseline --runs 1   # produce a fresh report
python -m evals.regression_gate --latest                # diff it against baseline_scores.json
# or gate a specific report:
python -m evals.regression_gate evals/reports/eval_<stamp>.json
```
Exit 0 = no hard regression (warnings may print); exit 1 = at least one HARD regression. The gate
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
- **Inert until armed.** It self-skips with a notice unless a `DEEPSEEK_API_KEY` **GitHub Actions
  secret** exists. The prod key lives in GCP Secret Manager (used by `deploy-backend` via
  `--update-secrets`), which CI cannot read — so arming the gate is a one-time owner action:
  **Settings → Secrets and variables → Actions → New repository secret → `DEEPSEEK_API_KEY`.**
- **Non-blocking.** `continue-on-error: true` and deliberately NOT in `deploy-backend`'s `needs:` —
  a red gate is a signal to a reviewer, never a deploy block. (Same posture as `lighthouse`.)
- **Path-filtered.** Runs only when `backend/app/**`, `backend/evals/**`, or `backend/prompts/**`
  change (or on manual `workflow_dispatch`), so it spends tokens only on AI-relevant changes
  (~$0.15–0.30 + a few minutes per qualifying PR once armed).
- **PR vs dispatch.** A PR runs a cheap **6-filing smoke** (catches catastrophic regressions —
  parse breakage, hygiene leaks, sign flips). Manual `workflow_dispatch` runs the **full verified
  set** (authoritative, apples-to-apples with the pinned baseline); pass a `limit` input to scope it.
  > Caveat: the 6-filing PR smoke is diffed against the full-set baseline, so its `pass_rate` /
  > `aggregate_stdev` are not directly comparable (warn-only). The HARD dimensions
  > (precision/coverage/gate_fail/recall) hold on any reasonable subset. For an authoritative
  > verdict, run the full set via dispatch.
- **Judge is OFF in the gate** — deterministic scorers only. The LLM judge is flaky and costly
  (~$0.20/filing on Opus, 30–60s latency); keep it for manual pre-deploy spot-checks. For cheap
  iteration use `--judge cli:sonnet` (subscription, no API credits) or `--judge glm-5.2`; reserve
  `--judge claude-opus-4-8` for the authoritative before/after that gates a prompt change.

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
Re-pin whenever you intentionally move the bar — flip `USE_STRUCTURED_OUTPUT`, change the default
model/prompt, or adopt a quality improvement. From `backend/`:
```bash
python -m evals.runner --candidates baseline --runs 3            # full verified set
python scripts/pin_baseline.py evals/reports/eval_<stamp>.json   # rewrite baseline_scores.json
```
Then commit the new `baseline_scores.json` in the same PR as the change it protects, so the diff
shows both the code change and the new bar. **BRK.B is `verified: false`** (no consolidated EPS
fact) and is auto-excluded by the runner — leave it out of the pinned set until its ground truth
is hand-filled.

---

## FPI adoption gate — flipping `ENABLE_FPI_FILINGS`

Separate, default-off gate (`app/config.py` → `ENABLE_FPI_FILINGS`). It controls whether the
company-filings endpoint lists + summarizes foreign-issuer forms (20-F/6-K/40-F) for ADRs like
Alibaba. **What you're deciding:** are 20-F summaries + native-currency financials good enough to
turn on for users. See `tasks/fpi-support-roadmap.md`.

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
pytest tests/unit/test_fpi_currency.py tests/unit/test_fpi_summary.py tests/test_edgar_services.py -q
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
   out-of-band setting. (Intentionally NOT added yet — that would flip prod on the next backend deploy.)
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
it decorates**. Six layers protect that promise; audit them together whenever a prompt, model, or
`copilot_service` resolver change touches the Q&A path (field precedent: legit revenue fact chips
reused as year labels on gross-profit/net-income figures).

**What's enforced automatically, per answer, in production** (`copilot_service._resolve_citations`):

| Layer | Citation kind | Check | On failure |
|---|---|---|---|
| Excerpt verification | text `[n]` | excerpt found verbatim in the filing (`verify_excerpt_in_text`) | chip renders unverified ("Cited", no badge) |
| Marker resolution | both | every inline marker resolves to a declared source | unresolvable F-marker stripped from prose |
| Value adjacency | fact `[Fn]` | a figure matching the fact's value (display-rounding tolerance) must sit in the claim span before the marker — bounded by the previous marker | occurrence stripped, counted as misplaced |
| Concept adjacency | fact `[Fn]` | the claim span must not name a *different* curated metric while never naming the fact's own (right value, wrong label — `_CONCEPT_SYNONYMS`) | occurrence stripped, counted as misplaced |
| Figure coverage | — | `count_uncited_figures`: financial figures outside every citation's claim span (the misplacement guards convert wrong chips into *uncited* prose — this counts what shipped naked) | counted, never modified |
| Telemetry | — | `misplaced_fact_markers` / `figure_count` / `uncited_figures` on the complete event, both warning logs, and the same trio on the PostHog `copilot_inference_cost` event | — |

**Offline gates (CI, free, every PR):** `pytest tests/unit/test_copilot.py tests/unit/test_copilot_evals.py -q`
— covers the resolver's strip/keep behavior and the eval scorers (including `score_fact_marker_adjacency`,
which re-runs the SAME production matcher + window rule over the final answer, so a resolver
regression can't hide from the harness).

**Live eval (operator, needs model API + ingested filings):**
```bash
cd backend && python -m evals.copilot_runner --runs 3
```
Read `evals/reports/copilot_eval_*.md` (one per run) + the printed cross-run aggregate:
- `Cite faithful` < 1.00 → a text excerpt shipped that isn't verbatim filing text. Hard stop.
- `Fact adj` < 1.00 → a fact chip shipped on the wrong figure — the adjacency guard regressed. Hard stop.
- `Fact adj … (−N stripped)` → the guard caught N misplacements. Answers are safe, but a rising N
  means the model's placement discipline is degrading — tighten the prompt's one-marker-one-figure
  rule before it finds a shape the guard can't falsify.

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
