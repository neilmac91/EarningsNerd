# DeepSeek V4.1 Flash migration — impact assessment and plan

Prepared 10 September 2026, 16:30 CEST. Repository state: `main` at `a811faf` (branch `claude/focused-cori-9g1kg1`, no changes made). Cutover: Monday 14 September 04:00 UTC / 06:00 CEST.

Verified against DeepSeek's current API docs today (api-docs.deepseek.com, fetched 10 Sept):

- `deepseek-flash`: 1M context, 384K max output, **thinking mode ON by default**, non-thinking supported, vision supported. `deepseek-v4-pro`: 1M / 384K, no vision. Unchanged from V4.
- Thinking is controlled by `thinking: {type: enabled|disabled}` (we pass it via `extra_body`) and `reasoning_effort` (`none`/`low`/`high`/`max`; the guide page also lists `low`/`high`/`max`, default `high`). Thinking mode rejects `temperature`; `top_p` floors at 0.95; `tool_choice: required` returns 400 in thinking mode; `reasoning_content` must be replayed on multi-turn tool calls.
- Usage object: `prompt_tokens`, `completion_tokens`, `prompt_tokens_details.prompt_cache_hit_tokens` / `.prompt_cache_miss_tokens`, `completion_tokens_details.reasoning_tokens`. Today's responses still carry the top-level `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` our code reads (confirmed by the hit/miss splits recorded in `tasks/review-evidence/*` on 9 Sept). Our parser does not read the nested names, so a shape change would silently drop the split (see W7).
- `max_tokens` default is 8K in non-thinking mode, 64K in thinking mode. JSON mode: "the API may occasionally return empty content" (known; our retry handles it as `MalformedCompletion`).
- Rate limits are account-level **concurrency**: `deepseek-flash` 2,500 concurrent, `deepseek-v4-pro` 500; 429 when exceeded; server drops a request that has not started inference after 10 minutes.
- Pricing per 1M (off-peak / peak): Flash $0.003/$0.006 hit, $0.15/$0.30 miss, $0.60/$1.20 output. V4 Pro $0.022/$0.044, $0.66/$1.32, $1.98/$3.96. Matches your table.

I could not find the two CSVs in the repository or the session filesystem, so the platform totals below are taken from your prompt as given.

---

## 1. Findings — what the codebase does today

### 1.1 Every LLM call path

There is exactly one wire client: `AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, max_retries=0)` built in `backend/app/services/openai_service.py:78-80`, plus an optional fallback client (`ai/provider_requests.py:116-138`) that is inert in production because `AI_FALLBACK_MODEL` is never set in any deploy command. Four call sites use it. Nothing else in `backend/app` or `backend/scripts` calls a model: no embeddings, no classifier, no data-quality LLM check, no change-report LLM (verified by grep across `change_report_service`, `data_quality_service`, `notable_filings_service`, `dashboard_feed_service`, `pulse_service`, `fallback_summary`, `earnings_alert_service`, `filing_scan_service`). Anthropic/Claude appears only in the eval harness (`backend/evals/judge.py`, `evals/models.py`), never at runtime.

| # | Path | Where | Model | Parameters | Streamed | Trigger |
|---|---|---|---|---|---|---|
| A | Filing summary (structured JSON extraction) | `openai_service.py:325-373` → `provider_requests.py:_request_content` | `AI_DEFAULT_MODEL` (`get_model_for_filing`, `openai_service.py:94-98`) | `temperature=0.2` (0.1 when `USE_STRUCTURED_OUTPUT`, off in prod), `max_tokens=8000` (`ai/extraction.py:30`), `response_format={"type":"json_object"}`, `extra_body={"thinking":{"type":"disabled"}}` (`provider_requests.py:181-182`), up to 3 attempts in a 75 s budget (`provider_requests.py:20-22`) | Yes on attempt 0 when `STREAM_SECTION_REVEAL` (prod: on) | User SSE request, background/cron path, pregenerate job, admin refresh |
| B | Section recovery (re-ask for empty sections) | `ai/section_recovery.py:122-128` | `AI_SECTION_RECOVERY_MODEL` → `AI_FAST_MODEL` → default (both empty in prod, `openai_service.py:85-87`) | `temperature=0.1`, `max_tokens=500`, non-thinking, 12 s timeout, ≤3 concurrent (`RECOVERY_MAX_CONCURRENCY`) | No | Automatic inside A, up to 9 calls per summary |
| C | Copilot "Ask this Filing" | `copilot_service.py:828-838` → `ai/copilot_chat.py:157` (`stream_chat_with_tools`) | `openai_service.model` = default | `temperature=0.2`, `max_tokens=COPILOT_MAX_TOKENS=2400`, `tools` + `tool_choice="auto"`, ≤4 rounds, thinking disabled (`copilot_chat.py:213`), 75 s deadline, 2 attempts before first chunk | Yes | User request (Pro) |
| D | Multi-Period Analysis narrative | `trend_analysis_service.py:1289-1293` → `copilot_chat.py:105` (`stream_chat`) | default | `temperature=0.2`, `max_tokens=ANALYSIS_MAX_TOKENS=3200`, thinking disabled (`copilot_chat.py:139`), one regenerate-on-citation-defect retry (`:1266`) | Yes | User request (Pro) |

Thinking is disabled by the substring gate `_thinking_disabled_model` (`ai/model_flags.py:11-27`): true when `"deepseek"` is in the model id or base URL. `deepseek-flash` matches, so the switch carries over with no code change. That matters more on V4.1 than on V4 because Flash defaults to thinking ON and thinking mode rejects `temperature`, which every path sends. If the gate were ever bypassed (a non-DeepSeek base URL such as OpenRouter fronting DeepSeek), every call would 400 on `temperature` or spend its output budget on reasoning.

Answering your specific questions: **Copilot does not use thinking mode**, sends no `reasoning_effort`, and **is streamed** (token-by-token with `stream_options.include_usage`). Neither does any other path. Because thinking is off everywhere, the 1.8K mean output tokens per request in the platform export contain **no reasoning tokens**; output cost is real answer/JSON text, and thinking effort is not a lever we are currently pulling.

**Gemini is not live.** It survives as: the base-URL allowlist entry `generativelanguage.googleapis.com` (`config.py:568`), a comment example for `AI_FAST_MODEL` (`config.py:306`), test fixtures (`scripts/verify_startup_config.py:73,86`, `tests/unit/test_ai_model_routing.py:13,46`), the `gemini-json` bake-off candidate in `evals/models.py:46-51`, a stale job command in `tasks/gcp-deploy-runbook.md:129`, and superseded docs (ADR-0002). The `AI_FALLBACK_*` seam that could route to it is unset in prod.

### 1.2 Where the model name lives (nine literal copies)

`AI_DEFAULT_MODEL` is a Settings field (`config.py:296`), so app code never hardcodes the id. But the value is duplicated as a literal in:

1. `backend/app/config.py:296` (default)
2. `.github/workflows/ci.yml:581` — Cloud Run **service** env (`--update-env-vars=…AI_DEFAULT_MODEL=deepseek-v4-pro`) on every backend deploy
3. `.github/workflows/ci.yml:593` — `earningsnerd-pregenerate` job env
4. `.github/workflows/ci.yml:344` — `eval-baseline` CI job
5. `.github/workflows/copilot-eval.yml:31`
6. `.github/workflows/data-quality-weekly.yml:57`
7. `backend/.env.example:17`
8. `docs/CONFIGURATION.md:118,183` — machine-gated: `tests/unit/test_configuration_reference.py:15` fails CI if the doc default disagrees with the code default
9. `tasks/gcp-deploy-runbook.md:93` (manual bootstrap)

`ops.yml:185` reads `AI_DEFAULT_MODEL` back from the live service for drift checks. The API key is Secret Manager `DEEPSEEK_API_KEY:latest` for the service and pregenerate job (`ci.yml:579,592`), and the **same secret is the GitHub Actions `DEEPSEEK_API_KEY`** used by the CI eval jobs. The seven other Cloud Run jobs receive no AI env and make no LLM calls.

Prices are also configuration (`config.py:511-513`) and are **stale**: `0.003625 / 0.435 / 0.87` per 1M, versus V4 Pro's actual `0.022 / 0.66 / 1.98`. The PostHog `copilot_inference_cost` / `analysis_inference_cost` events have been under-reporting by roughly 2.3× since the July repricing, and the peak surcharge is explicitly not modelled (`config.py:509-510`).

### 1.3 Prompt structure and the 38K-input / 98% cache-hit figures

Summary prompt (`openai_service.py:313-368`): system message (static, ~120 tokens) → user message beginning with the per-filing-type analyst preamble (`prompts/10k-analyst-agent.md`, ~9.5K chars ≈ 2.5K tokens, static) → `Company:` line (variable, `:317`) → extracted signals + XBRL block (variable) → `CRITICAL FILING EXCERPTS` up to 80K chars (`extraction.py:28`; variable, the bulk) → output reference + schema + rules (static, ~4K tokens, **after** the variable content). So a first summary of a new filing is a cache miss on ~35-40K tokens; only the ~2.6K-token preamble is a reusable prefix across filings. Re-runs of the same filing (retries, the eval harness, a regenerate) are near-total hits.

Copilot prompt (`copilot_service.py:298-320`): system prompt (static) → one user message with filing meta + excerpt capped at 120K chars ≈ 30K tokens + compact XBRL block (`:239-276`, static **per filing**) → last 6 history turns → question. **Yes, the whole filing excerpt is resent every turn and every tool round**; each turn is a ~30K-token request that is a cache hit on everything but the new turn. That is by design and is what the 98% hit rate is buying.

Both orderings are cache-correct (static before variable). No path puts variable content in front of static content except the `Company:` line inside the summary user message, which is unavoidable and harmless.

The 38K mean input per request and 98.1% hit rate are therefore explained by **repeated calls over the same filing text**, not by production users reading many distinct filings. Fresh, distinct-filing summaries generate cache-miss tokens at ~40K each; the export shows only 1.3M miss tokens/day, which bounds fresh summaries at roughly **30 per day**. The other ~1,760 daily requests are hits on already-cached filings. Section 3 shows where they come from.

### 1.4 Volume: the CI eval harness, not users, drives the bill

Two GitHub Actions workflows run the **real production pipeline against the production DeepSeek key** on pull requests:

- `eval-baseline` (`ci.yml:254-392`): on every PR push touching `backend/app/*`, `backend/evals/*`, or `backend/prompts/*` (`ci.yml:302-304`), runs the 26-filing golden set × 2 repeats = 52 summaries at concurrency 2 (`:344-370`). Measured per run on 9 Sept (`tasks/review-evidence/reported-metrics-final-2026-09-09/pr799-summary-round2-acceptance.md:11`): 52 calls, 2,166,784 prompt tokens (2,163,712 hit / 3,072 miss), 145,270 completion. The golden filings stay warm in DeepSeek's cache between PRs, so input is essentially free; output is 145K tokens per run.
- `copilot-eval` (`copilot-eval.yml`): on every non-draft PR touching backend, 6 golden questions × 3 repeats = 18 answers, ~30 `chat_stream` calls, ~935K prompt tokens (99.8% hit), ~4.3K completion (`tasks/review-evidence/explanations-first-2026-09-09/pr805-copilot-acceptance.md:15` and two sibling files).

Git history shows 2 merges to main on Mon 7 Sept, 24 on Tue 8, 24 on Wed 9. A full enumeration of GitHub Actions runs for 5-9 Sept (UTC) with a job-level sample (every 9th `ci.yml` run, every 2nd `copilot-eval.yml` run) gives:

| UTC day | `ci.yml` runs | `eval-baseline` actually executed (est.) | median job min | `copilot-eval.yml` runs | `copilot-eval` executed |
|---|---|---|---|---|---|
| Fri 5 | 143 | ~54 | 6.4 | 11 (API window truncated) | 5 |
| Sat 6 | 109 | ~34 | 6.3 | 88 | 44 |
| Sun 7 | 36 | ~9 | 12.2 | 34 | 11 |
| Mon 8 | 91 | ~36 | 13.1 | 50 | 22 |
| Tue 9 | 43 | ~9 | 14.8 | 17 | 10 |

About 36% of `ci.yml` runs pass the "AI-relevant paths changed" gate and hit DeepSeek; the per-day executed counts are ±9 for the thin days. Roughly 110-140 executed `eval-baseline` jobs and ~95 `copilot-eval` jobs over the five days. Two observations: the eval job's duration doubled from ~6 min to ~13-15 min from 7 Sept onward (same 52 summaries; either provider latency or added pipeline work — worth a look, not part of this plan), and the export's per-day split does not line up with UTC days (the quiet Monday 7 Sept at $4.61 fits ~9 runs; Wednesday 9 Sept at $13.55 does not fit ~9 runs unless the export's day boundary is Beijing time, which it probably is). The five-day totals are the robust figures.

Solving the three per-day observables (requests, output tokens, cache-miss tokens) for three unknowns using the measured per-run footprints above gives a mix that also reproduces the fourth observable (input tokens 68.1M implied vs 68.2M actual):

| Traffic component | Per day (5-9 Sept mean) | Requests | Output tokens | V4 Pro $/day (off-peak) | Flash $/day (off-peak) |
|---|---|---|---|---|---|
| `eval-baseline` CI runs | ~22 runs | ~1,120 | ~3.1M | $7.27 | $2.03 |
| `copilot-eval` CI runs | ~22 runs | ~650 | ~0.09M | $0.65 | $0.12 |
| Fresh product summaries (users, pregenerate) | ~29 filings | ~29 + recovery | ~0.08M | $0.93 | $0.22 |
| **Total** | | ~1,800 | ~3.3M | **$8.85** (+10% peak = $9.76 actual) | **$2.37** (+10% = $2.62) |

This is a model fit, not a log query, and it lumps real Copilot/Analysis usage into the "fresh summaries" residual (they are cache-hit-dominated and cheap, so the error is small). It is consistent with the repo's own record that prod had "zero users" during the S1 soak (`lessons/ops-eval-gate-for-ai-changes.md:9`) and with the beta-stage funnel. **The conclusion I am confident in: on 5-9 Sept, roughly 85-90% of DeepSeek spend was CI eval traffic; product traffic cost about $1/day on V4 Pro.** The Actions sample above (110-140 executed `eval-baseline` jobs over five days) agrees with the token-mix fit (~108) within its sampling error, and 110-140 runs at $0.34-0.68 each accounts for $37-48 of the $48.82 by itself.

### 1.5 Observability today

- Every provider attempt logs one JSON line `ai_call {operation, provider, actual_model, outcome, usage:{prompt, completion, total, cache_hit, cache_miss}}` (`ai_metrics.py:98`) and each summary logs an `ai_summary` aggregate (`:105`). Operation labels: `summary_primary`, `summary_fallback`, `section_recovery`, `chat_stream` (`:22`). Analysis and Copilot share `chat_stream`, so they are not separable in logs today.
- Not recorded: latency per call, `reasoning_tokens`, requested-vs-actual model, `system_fingerprint`, estimated cost, peak/off-peak, trigger (user / job / CI eval), user or filing id (deliberately).
- Per-process counters only, exposed via admin `GET /metrics` (`docs/OPERATIONS.md:81-97`); reset on instance restart. No log-based metric, alert, or dashboard exists in the repo (`ops.yml` reads logs for other events only).
- Cost reaches PostHog only for Copilot and Analysis (`routers/summaries.py:320-360`, `routers/analysis.py:263-290`), priced with the stale constants. **Summary-path usage never reaches PostHog or the DB.** No table stores tokens or cost; `trend_analyses.model` (`models/trend_analysis.py:37`) is the only persisted model name.
- Consequence for Monday: after the alias routing starts, if DeepSeek echoes `deepseek-v4-pro` in `response.model` (unknown; today it echoes the requested id), **nothing in our logs would show the swap**. Detection would have to come from output-length and latency shifts, which we do not record per call.

### 1.6 Regression harness

- `evals/runner.py` `baseline` candidate runs the production pipeline (`summarize_filing`, `:275-298`) with model/base URL taken from env; no CLI flag, so a Flash arm is `AI_DEFAULT_MODEL=deepseek-flash` (RUNBOOK step 1). Golden set: 26 verified filings (11 10-K, 9 10-Q, 7 20-F). Per-filing artefacts (`payload`, `raw_sections`, `grounding_excerpt`, `figure_trace`) are written to `evals/reports/eval_<ts>.json` (`:327-332, :444-452`) — but `evals/reports/.gitignore` ignores everything, so **no V4 Pro per-filing outputs are stored in the repo**.
- The baseline path hardcodes `cost_usd: 0.0` and records **no token counts** (`runner.py:323`); only non-baseline raw-call candidates record `input_tokens/output_tokens` (`:350-351`). The GLM bake-off flagged the same gap.
- `baseline_scores.json` is aggregate-only: pinned 2026-09-05 from `eval_20260905T111951Z.json`, `model: deepseek-v4-pro`, 3 runs × 26, `judge: false`, `source_sha f5b46ba9`. The source report exists only as a GitHub Actions artifact with **14-day retention (expires ~19 Sept)**.
- Judge: `claude-opus-4-8` via the Anthropic SDK (`judge.py:47`, $5/$25 per 1M), off by default, not part of the CI gate; scores hard gates G2/G3 (fabricated comparatives, hallucinated facts) plus faithfulness/insight/clarity/specificity 1-5. Deterministic scorers (schema, numeric precision/recall, coverage, citation and forward-quote fidelity, redundancy, delta consistency) are the gate (`regression_gate.py:42-72`), compared **aggregate vs pinned aggregate**, not paired per filing.
- Copilot eval: 6 questions × 3 runs, deterministic scorers only, stores per-answer text and citations. CI cannot run a Flash arm (model hardcoded in all three workflows).
- Precedent: the GLM-5.2 bake-off (`tasks/archive/glm-5.2-bakeoff.md`) used exactly this env-swap, 78 attempts per arm, judge on, and its lessons (`lessons/test-bakeoff-hold-knobs-constant.md`, `lessons/test-judge-context-parity.md`) apply directly: smoke one raw call and inspect `content` and `reasoning_content` before the arm; hold every knob constant.

### 1.7 Format dependencies a new model could break

- Summary: `response_format=json_object` plus `_JsonRepairMixin` (`ai/json_repair.py`), deterministic taxonomy guard (`openai_service.py:573-590`), section recovery for empty sections, verbatim-evidence contracts (`supporting_evidence`, `quotes[].quote` must be exact substrings; unverifiable spans become `""` or are dropped by the forward-quote audit), and list fields collapsed with `"; ".join` in `ai/markdown_render.py:459,538` and `summary_sections.py:100,102` (the P0-2 semicolon-join issue noted at `markdown_render.py:24`; a model that returns multi-sentence array items re-creates the collapsed look). Field-name scaffolds (`Guidance:`, `Evidence:`) are stripped by the renderer (`markdown_render.py:151,196`; `summary_sections.py:472`), which handles known shapes only.
- Copilot: prose → literal `===CITATIONS===` line → JSON array → `===FOLLOWUPS===` → JSON array, or `===NOT_DISCLOSED===` (`copilot_service.py:55-60, 63-122`); inline `[n]`/`[Fn]` markers with adjacency guards; tool-call assembly across chunks; a 240-char hold-back heuristic (`copilot_chat.py:43`) to hide inter-tool narration. A chattier or differently-formatted model shows up as leaked narration, missing followups, misplaced markers (already counted: `copilot_service.py:980-990`).
- Analysis: `[F#]` markers resolved against a server-side index, illegal-reference detection and one regenerate retry (`trend_analysis_service.py:854-930, 1266`).

### 1.8 Concurrency and rate limits

Fleet ceiling toward DeepSeek is process-local semaphores summed over instances: service `max-instances=2` × (6 generations + 3 recovery + 8 chat) + jobs ≈ 43 concurrent streams (`config.py:464,467,476`; `provider_admission.py`), plus CI eval concurrency 2. Against Flash's 2,500 (Pro's 500) concurrency cap this is not a constraint. 429s are retried with `Retry-After` capped at 5 s inside the 75 s budget (`provider_requests.py:80-110`). No token-bucket limiter exists and none is needed at this scale.

### 1.9 Other references

- `backend/scripts/deploy_check.py:41` validates `OPENAI_BASE_URL` against Google/OpenRouter only — **it already reports production's DeepSeek URL as invalid** and checks nothing about the model. `main.py:175` logs "Google AI Studio configured" regardless of provider.
- Frontend: `frontend/app/security/page.tsx:258` names DeepSeek as provider (no model id; unaffected). No pricing or per-summary-cost copy anywhere user-facing. Separate finding, out of scope but flagged: `frontend/app/privacy/page.tsx` lists Stripe/Resend/PostHog/Sentry as sub-processors "located in the United States" and omits DeepSeek, while `docs/legal/PRIVACY_POLICY.md:84` lists DeepSeek (PRC).
- Entitlements and Stripe: caps (`PRO_SUMMARY_MONTHLY_CAP=300`, `COPILOT_MONTHLY_QUESTION_CAP=1000`, `ANALYSIS_MONTHLY_CAP=100`) are anti-abuse guardrails, not cost-derived; no margin model exists. Nothing Stripe-facing changes.
- Docs pinning the model or prices: `CLAUDE.md:9-10`, `README.md:40-43`, `docs/ARCHITECTURE.md:20-32`, `docs/DEPLOYMENT.md:190,674`, `docs/adr/0006-gemini-to-deepseek.md` (its stated rationale is "chose pro over flash on the quality preference"; needs a superseding ADR, not an edit), `docs/summary-quality-improvement-plan.md:213-231` (largest stale section), SEO/launch/perf docs with "$0.02-0.05/summary" figures. Tests pinning literals: `test_provider_resilience.py`, `test_copilot_cost.py:65,73,96`, `test_ai_metrics.py:27,100`, `test_weekly_readout_receiver.py:63` — fixtures, none break on a default change.
- Multimodal: no image/vision code anywhere in product code.

---

## 2. Quality risk assessment per call path

| Path | Risk from a new-pretraining model | Likelihood | Detection |
|---|---|---|---|
| A. Summary JSON | (1) Verbatim-copy discipline drops: more paraphrased `supporting_evidence`/`quotes` → more `""` evidence, more forward-quote drops, lower `citation_fidelity` / `forward_quote_fidelity`. (2) Verbosity: longer `key_takeaways`, multi-sentence array items → semicolon-collapse look, redundancy dimension falls, output tokens rise (the cost-invalidating case). (3) Hedging/objectivity: promotional adjectives the OBJECTIVITY rule bans. (4) JSON adherence: DeepSeek's own "occasionally empty content" note; extra keys the taxonomy guard strips; truncation if output grows toward 8000. (5) Numbers: fabricated comparatives / restated XBRL figures → `gate_fail_rate`, `numeric_precision`. | Medium. Flash is claimed ≥ Pro on benchmarks; adherence to a 6K-token rule set is what usually shifts. | Deterministic gate on the 26-filing set, both arms, paired per filing; judge G2/G3 on both arms; per-filing output-token delta; production counters `forward_quote_unverified`, `evidence_snap`, quality tier rate (partial vs full) week-over-week. |
| B. Section recovery | Same as A at 500 tokens; empty/over-long answers. | Low-medium | Recovery call count per summary and empty-section rate from `ai_call` logs (`section_recovery` operation). |
| C. Copilot | (1) Tool-calling format: argument fragment assembly, `cite` marker reuse, more or fewer tool rounds (cost + latency). (2) Sentinel discipline: missing `===FOLLOWUPS===`, JSON fences, prose after the citations block. (3) Inter-tool narration longer than 240 chars leaking as answer text. (4) Refusal calibration: over-use of `===NOT_DISCLOSED===` or answering from outside the filing. (5) Marker misplacement. | Medium-high: this is the surface with the most format contracts and the least deterministic post-processing. | Copilot golden set (6 × 3) both arms: citation faithfulness, refusal calibration, numeric accuracy; production counters `misplaced fact markers`, `uncited figures`, stream-error rate, tool-round distribution, followups-missing rate (add). |
| D. Analysis narrative | `[F#]` discipline; regenerate-retry rate doubles cost if it worsens. | Medium | No golden set exists. Detection: retry rate and illegal-ref counts from logs; add 3-5 fixed tickers to a smoke run. |

Structural point: Neil's prior lesson holds. The deterministic gates catch fabricated numbers and broken formats; they do not catch a quieter, blander, or more hedged summary. That is what the judge arm (Claude Opus 4.8, ~$25 per 78-attempt arm) is for, and why it should run on both arms this week even though it is not in the CI gate.

---

## 3. Cost model

Inputs (your export, 5-9 Sept, 8,980 requests): 334.6M cache-hit input, 6.4M cache-miss input, 16.5M output, $48.82 actual.

| | Hit $ | Miss $ | Output $ | 5-day off-peak | Per day | Actual incl. peak | Per month |
|---|---|---|---|---|---|---|---|
| V4 Pro (0.022 / 0.66 / 1.98) | 7.36 | 4.22 | 32.67 | $44.26 | $8.85 | $9.76 (×1.103) | ~$293 |
| V4.1 Flash (0.003 / 0.15 / 0.60) | 1.00 | 0.96 | 9.90 | $11.86 | $2.37 | $2.62 (same peak share) | ~$78 |

Your projection is confirmed: −73%; output becomes 83% of spend; peak-shifting is worth ~$0.25/day and is not a priority (though the pregenerate cron at 06:00 UTC Monday sits inside the peak window and is a one-line move; it is idempotent and usually makes zero calls, so it barely matters).

Per-path unit costs (off-peak, derived from measured footprints in §1.4):

| Unit | V4 Pro | Flash |
|---|---|---|
| One `eval-baseline` CI run (52 summaries, warm cache) | $0.34 | $0.09 |
| One `copilot-eval` CI run | $0.03 | $0.006 |
| One fresh product summary (~40K miss, 2.6K out) | $0.032 | $0.008 |
| One Copilot answer (2 rounds, ~62K hit, 600 out) | $0.004 | $0.0008 |

Two corrections to the framing:

1. **The bill is not a product cost curve.** ~$8/day of the $9.76 is CI evals. At current PR cadence the product itself costs ~$1/day on Pro and ~$0.25/day on Flash. The migration saves real money mostly on evals; the more important effect is that eval runs become cheap enough to run more often, with 3 repeats and the judge on.
2. **What invalidates the projection** is output length on path A. Per-filing output tokens are exactly what the harness does not record on the baseline path (`runner.py:323`). W2 below fixes that before the regression run so the Pro-vs-Flash output ratio is a measured number, not a guess. If Flash writes 30% more per summary, Flash cost is ~$3.3/day instead of $2.6; still −66%.

Peak-hour note: your development hours (08:00-12:00 CEST) are the 06:00-10:00 UTC peak window, so CI eval runs pay 2× more often than product traffic does. Not worth scheduling around; worth knowing.

---

## 4. Plan

Effort is my estimate for one engineer. "Risk" is risk of the change itself.

### 4A. Must do before Monday 06:00 CEST

**W1 — Secure the V4 Pro reference (revised per Neil, 10 Sept).** The reference is the 5 Sept pin: download the `eval-report-<run_id>` artifact for `eval_20260905T111951Z.json` (source SHA `f5b46ba9`, 3 × 26, judge off) from GitHub Actions before its 14-day retention expires (~19 Sept) and commit it under `backend/evals/baselines/` (a new tracked directory; `evals/reports/` stays ignored). No judge spend. Two limits to accept: that report carries no per-filing token counts (`runner.py:323`) and predates #792's runner changes, so `compare_reports.py` must tolerate missing fields. Optional and cheap (~$1.5, no judge): one 26 × 1 Pro run on today's `main` after W2, purely to get per-filing output tokens and outputs at the same SHA as the Flash arm; strike it if you would rather not. Effort: 30 min. Risk: none. **Time-critical only in the sense that after Monday 06:00 CEST the optional Pro run is impossible.**

**W2 — Record per-attempt usage on the baseline eval path.** Thread the pipeline's `ai_call` records (prompt/completion/hit/miss, `actual_model`, latency, and `reasoning_tokens` once W7 adds it) into each result row in `evals/runner.py` (~10 lines around `:275-323`), sum into the report summary, and add a small paired-comparison script (`evals/compare_reports.py`: per filing × run, delta in aggregate, gate dims, output tokens, latency between two reports). Do this **before** W1's Pro run so the baseline carries tokens. Effort: 0.5 day. Risk: low (harness only; unit test on the row shape). Gate: `tests/unit/test_eval_*.py` additions.

**W3 — Smoke and regression run on `deepseek-flash`.** Per `lessons/test-bakeoff-hold-knobs-constant.md`: one raw call to `deepseek-flash` with our exact kwargs (thinking disabled, `temperature`, `response_format`, `max_tokens=8000`) inspecting `content`, `reasoning_content`, `usage` (including whether `prompt_cache_hit_tokens` still arrives top-level) and `response.model`. Then the same 26 × 3 + judge run as W1 with `AI_DEFAULT_MODEL=deepseek-flash`, and the Copilot golden set. Compare with `compare_reports.py` and `regression_gate.py`. Decision rule: hard gates must hold (`gate_fail_rate` ≤ +0.005, numeric precision/coverage within thresholds), judge G2/G3 no worse, judge mean ≥ 4.0, output tokens per summary reported. Effort: 0.5 day. Cost: ~$0.5 Flash + ~$25 judge. Risk: none to prod.

**W4 — Move the model id to `deepseek-flash` explicitly, everywhere, in one PR.** Change `config.py:296`, `ci.yml:344,581,593`, `copilot-eval.yml:31`, `data-quality-weekly.yml:57`, `.env.example:17`, `docs/CONFIGURATION.md:118,183`, `tasks/gcp-deploy-runbook.md:93`; update the price constants `config.py:511-513` to Flash off-peak (`0.003 / 0.15 / 0.60`) and `docs/CONFIGURATION.md:159-161`; re-pin `baseline_scores.json` from the W3 Flash report via `scripts/pin_baseline.py`; write ADR-0008 superseding ADR-0006 (decision: Flash, rationale: forced retirement + measured parity, Pro re-evaluated when V4.1 Pro ships). Add the gate for rule 12: a unit test that greps the three workflows and `config.py` for `deepseek-v4-` literals (fails on any reappearance) — or better, W9's single-source. Deploy is the normal backend-touching merge; verify the deploy job's conclusion and `ops.yml`'s drift read-back shows `deepseek-flash`. Effort: 0.5 day plus review. Risk: low if W3 passes; the alias would carry us anyway, so the real risk is only in doing it late. **Do not merge W4 before W3 passes; if W3 fails, see Open Question 2.**

**W5 — No merge freeze (per Neil); instead, one re-pin owner.** Until W4 merges, `baseline_scores.json` encodes V4 Pro. From Monday 06:00 CEST every `eval-baseline` run on any PR scores Flash output against that Pro pin and can go red for reasons unrelated to the PR, and the runner's known defect (green CI can hide a red gate; handover §2a.1) makes that worse. Rule for the weekend: exactly one PR re-pins the baseline, the cutover PR (W4), and no prompt-changing PR (#805 and the prepared `d`/`e` candidates) is measured or merged between Monday 06:00 and the W4 merge. Effort: nil.

**W6 — Separate API key for CI.** `EarningsNerd` is the only key today (confirmed). Create a second DeepSeek key (`EarningsNerd-CI`) in the DeepSeek console (Neil; I cannot), put it in the GitHub Actions `DEEPSEEK_API_KEY` secret, keep the production key in Secret Manager only. This makes the platform dashboard split product vs CI by key from day one, which no amount of our own logging replaces for reconciling the invoice. Effort: 15 min. Risk: nil. (Confirm the DeepSeek usage page filters by key; I believe it does but did not verify.)

### 4B. Should do this month

**W7 — Per-request observability.** Extend `ai_metrics.record_ai_call` (`ai_metrics.py:22-50, 98`) with `latency_ms`, `requested_model` alongside `actual_model`, `system_fingerprint` if present, `reasoning_tokens` (from `completion_tokens_details`), the nested `prompt_tokens_details.prompt_cache_hit_tokens/miss` fallback, `estimated_cost_usd` (per-model price table with peak/off-peak by UTC hour, replacing the three flat constants), and a `trigger` label (`user`/`job`/`eval`) set from the entry point. Split `chat_stream` into `copilot_chat` and `analysis_chat`. Emit the summary path's usage to PostHog like Copilot/Analysis do (or, simpler, a Cloud Logging log-based metric on `ai_call` with sum of cost and a daily alert at, say, $5). Add a unit test that a fixture usage with only nested cache fields still yields a split. Effort: 1.5 days. Risk: low. This is what makes the *next* silent routing change visible: an `actual_model`/`system_fingerprint` change, or an output-token or latency shift per operation, shows on a chart the same day.

**W8 — Fix `deploy_check.py`** (`:36-42`) to accept `api.deepseek.com` and to print the configured model; fix the misleading "Google AI Studio configured" log line in `main.py:175`. Effort: 1 h.

**W9 — One source of truth for model config.** Replace the nine literals with one: a repository-level GitHub Actions variable (`vars.AI_DEFAULT_MODEL`) referenced by all three workflows and the two `gcloud … --update-env-vars` lines, with `config.py`'s default matching and the existing `test_configuration_reference` gating the doc. Add a test that `.github/workflows/*.yml` contain no `deepseek-` literals. Effort: 0.5 day. Risk: low; do it after W4 so Monday's change is a plain literal edit.

**W10 — Thinking/effort experiment on Flash (measure, don't assume).** Keep non-thinking as the default for all paths: it keeps `temperature`, keeps streaming first-token latency for Copilot/Analysis, and avoids the `reasoning_content` replay requirement in tool loops. Then run one harness arm with `thinking: enabled, reasoning_effort: low` (drop `temperature` for that arm) on path A only, and compare judge insight/faithfulness and cost. Adopt only if it clears the gate with a measurable judge gain at an acceptable output-token multiple. Effort: 0.5 day. Cost: ~$1 + judge.

**W11 — Format-contract hardening where W3 shows cracks.** Candidates: Copilot followups-missing counter and a deterministic fallback, hold-back cap tuning, semicolon-join sites (`markdown_render.py:459,538`, `summary_sections.py:100,102`) rendering list items as bullets when any item exceeds one sentence. Only what W3 evidence justifies. Effort: 0.5-1 day.

**W12 — Docs sweep.** `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `docs/summary-quality-improvement-plan.md §4.2`, launch/SEO/perf cost figures. Effort: 2 h. Also raise the privacy-page sub-processor gap with counsel; not part of this migration.

### 4C. Strategic / later

**W13 — Provider profiles (the abstraction that makes the next migration a config change).** Today the coupling to DeepSeek is thin but scattered: one client + one fallback client; the substring thinking gate (`model_flags.py`); the `extra_body` thinking switch in two places (`provider_requests.py:181`, `copilot_chat.py:139,213`); the 8192 Gemini clamp (`provider_requests.py:184`); DeepSeek's cache-token field names (`ai_metrics.py:43-46`); single-model price constants; the base-URL allowlist (`config.py:568`); the role-alternation merge (`copilot_service.py:278`). Proposal: a `ProviderProfile` dataclass (name, base_url, api_key setting, model, thinking switch style: `deepseek-extra-body` / `none`, max-output clamp, price table, cache-usage field mapping) in `services/ai/providers.py`, a registry keyed by name, and per-task routing in Settings (`AI_ROUTE_SUMMARY`, `AI_ROUTE_RECOVERY`, `AI_ROUTE_COPILOT`, `AI_ROUTE_ANALYSIS`, each `profile:model`, defaulting to the DeepSeek profile). `OpenAIService` holds one client per profile. Gemini stays reachable through its OpenAI-compatible endpoint (`generativelanguage.googleapis.com/v1beta/openai/`), so no second SDK is needed; Anthropic would need a thin adapter if ever wanted. Routing any path to another provider then becomes: set the env var, run the harness, re-pin. Effort: 2-3 days plus a bake-off per new provider. Not before Monday; not this week.

**W14 — Multimodal: park.** Filings are text/iXBRL; charts are rare in 10-K/10-Q bodies and live in exhibits (Item 5 performance graph) or scanned 6-K/20-F PDFs. The only plausible near-term use is FPI PDF exhibits. Note it in the ADR as a later opportunity; no work now.

**W15 — Eval spend hygiene.** With Flash at $0.09 per eval run the CI gate is cheap, but path-filter it tighter (skip when only tests/docs under `backend/app` change), and consider `EVAL_RUNS=1` on pushes with 3 only on the pre-merge run. Effort: 1 h. Optional.

---

## 4D. Coordination with the Astra (GPT-6) hand-over work

What Astra's in-flight work touches (from `tasks/handover-astra-2026-09-09.md` §3 and the open PRs):

| Astra item | Files | Overlap with this plan |
|---|---|---|
| #805 draft, held (`codex/wave3-supported-financial-explanations`) | `openai_service.py` (prompt text in `generate_structured_summary`), `ai/section_recovery.py`, `summary_schema.py`, `summary_versioning.py` (bumps to `summary-2026-09-e`) | No file overlap with W2/W4. **Measurement overlap:** a prompt change needs an eval re-pin; so does the model swap. Two re-pins cannot be reasoned about independently. |
| #808 draft (`codex/wave3-instance-cash-debt-provenance`) | `edgar/instance_extractor.py`, `edgar/xbrl_service.py`, tests | None. |
| Prepared local `work/eval-error-outcome` (not pushed) | `evals/runner.py` | **Direct overlap with W2** (both add fields to the result row around `:275-323`). |
| Prepared local `work/measurement-only-dispatch` | `.github/workflows/data-quality-weekly.yml` | Trivial textual overlap with W4's one-line model edit at `:57`. |
| Prepared local `work/reported-metric-labels` (`d`), `work/metric-prior-identity` (`c`) | prompt/schema/facts code | Same measurement overlap as #805. |
| #792 (merged as `f212949`) | `evals/runner.py` | Already on `main`; W2 builds on it. The 5 Sept pin predates it. |

The important point is not file conflicts, which are small and mechanical. It is that **Astra's quality slices are measured against V4 Pro, and that measurement expires on Monday whatever we do.** A `d`/`e` candidate assessed on Pro this week and merged next week would carry evidence about a model that no longer serves production; assessed after Monday against the Pro pin it fails for the wrong reason. The migration therefore has to be sequenced ahead of Astra's next paid assessment, not around it.

Rules that keep the two streams from colliding:

1. **One re-pin owner.** The cutover PR (W4) is the only PR that touches `baseline_scores.json` until it merges. Astra's `d`/`e` are re-measured on `deepseek-flash` against the Flash pin afterwards, once each.
2. **W2 goes to whoever owns `runner.py` this week.** Either Astra folds the per-attempt usage fields into `work/eval-error-outcome` (it is already in that file), or I land W2 first as a 10-line additive change and Astra rebases. Not both.
3. **Pre-Monday scope is W1-W4 and W6 only**, in two small PRs (W2; then W4). W7, W9, W11, W13 wait until the wave-3 prompt slices (#805, `d`) are merged or explicitly parked, because W11 would edit the same prompt block #805 edits and W9 rewrites the workflows Astra's `measurement-only-dispatch` touches.
4. **A dated note in `tasks/handover-astra-2026-09-09.md`** (or the next handover) stating: model cutover date, the re-pin rule, "measure `d`/`e` on Flash, not Pro", and the W2 ownership decision. That file is Astra's coordination channel; nothing else reaches it.
5. **Balance check before any paid run** by either agent; the 9 Sept 402 shows the account can run dry mid-cohort and the runner then records fallback output as scored.

---

## 5. Decisions taken (Neil, 10 Sept) and what remains open

Answered: (1) the 5 Sept pin is the Pro reference, no judge spend; (2) if Flash fails the gate, ship Flash with prompt fixes and re-run, then route the failing path via `AI_FALLBACK_*` if needed; (3) eval reports tracked in git under `backend/evals/baselines/`; (4) `EarningsNerd` is the only DeepSeek key, so W6 needs a new one created in the console; (5) no merge freeze, replaced by the one-re-pin-owner rule in W5 and §4D.

Still open: (a) who owns `runner.py` this week (W2: me or Astra); (b) whether the optional ~$1.5 Pro token-count run in W1 is acceptable; (c) whether a GCP log-based metric or dashboard for `ai_call` exists outside the repo; (d) whether the DeepSeek notice says anything about `response.model` during the alias period.

---

## 6. Recommendation

Do W1 today (download and commit the 5 Sept pin artefact) and decide W2's owner, W3 tomorrow (Flash smoke + full run + Copilot set + paired comparison against the 5 Sept pin), and if it clears the gate, land W4 (explicit `deepseek-flash` in all nine places, Flash prices, re-pinned baseline, ADR-0008) on Friday with W6 (CI key) alongside and the re-pin-owner rule in force, so production is on the canonical id before the alias routing starts rather than riding a routing that can be withdrawn without notice. Keep thinking mode off on every path for the cutover and treat W10 as a measured experiment afterwards. Next week ship W7 (per-request cost, latency, reasoning tokens, requested-vs-served model, trigger label, log-based cost alert) and W9 (single source for the model id), because the real lesson of this episode is that we found out about a 3-day cutover from an email, and our own logs would not have shown the swap. Park the provider abstraction (W13) as the next architectural item after observability; the code is already thin enough that it is a two-day job, and it should be done when there is a second provider worth routing to, not speculatively. The cost side needs no heroics: product traffic is ~$1/day, the bill is CI evals, and Flash cuts both by ~73% while making it affordable to run the judge every time.
