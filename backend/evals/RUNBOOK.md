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
export ANTHROPIC_API_KEY=...    # claude-sonnet, claude-opus, judge
# optional: QWEN_API_KEY / KIMI_API_KEY / DEEPSEEK_API_KEY
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

## FPI adoption gate — flipping `ENABLE_FPI_FILINGS`

Separate, default-off gate (`app/config.py` → `ENABLE_FPI_FILINGS`). It controls whether the
company-filings endpoint lists + summarizes foreign-issuer forms (20-F/6-K/40-F) for ADRs like
Alibaba. **What you're deciding:** are 20-F summaries + native-currency financials good enough to
turn on for users. See `tasks/fpi-support-roadmap.md`.

The golden set ships three verified FPI 20-Fs covering the currency/taxonomy matrix:

| Ticker | Accounting | Reporting currency | Why |
|---|---|---|---|
| BABA | U.S. GAAP | CNY (+ USD convenience) | flagship; convenience-translation filter |
| TSM  | IFRS | TWD | ifrs-full namespace + non-USD |
| ASML | IFRS | EUR | EUR; revenue hand-filled (double-tagged — see below) |

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
