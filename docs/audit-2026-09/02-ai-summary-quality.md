# EarningsNerd — AI Quality Audit (read-only)

> Appendix 02 of `docs/ENGINEERING_AUDIT_2026-09.md`. Workstream report reproduced as written; hypotheses are labelled by the author.

Repo state: `main` @ `e8ea339` (2026-07-16). Paths relative to `/home/user/EarningsNerd/`. Claims are code-verified unless marked **[hypothesis]**.

## (A) Pipeline map

**One orchestrator** (`backend/app/services/summary_pipeline.py::stream_filing_summary`; rule 1 holds): SSE route and cron drain (`summary_generation_service.py:493-590` → `precompute_service.py:56,185`) both consume it. `previous_filings=None` hard-coded (`summary_pipeline.py:632`).

| # | Stage | Where | Budgets / notes |
|---|---|---|---|
| 1 | Short-circuit, dedup, quota gate, semaphore(6) | `summary_pipeline.py:188-260` | `PIPELINE_TIMEOUT_SECONDS=120` (:137) |
| 2 | Concurrent fetch: document (15s), XBRL metrics (15s), edgartools sections (30/40s) | `:~360-430`; `edgar/xbrl_service.py:698-730` | 6-K → EX-99 exhibits (`sixk_extractor.py`), no XBRL |
| 3 | Excerpt build + 24h cache | `summary_generation_service.py:440-491`; `ai/extraction.py:454-527` (cap 320k chars) | Join budget 18s (:143); on timeout excerpt AND XBRL dropped → model sees `filing_text[:15000]` raw HTML (`openai_service.py:175`) |
| 4 | Grounding: regex "signals" (excerpt[:25000], `:178`) + XBRL whitelist block w/ prior period, ROE/ROA banded, FI addendum | `ai/xbrl_narrative.py:41-71,106+` | Filing-own XBRL comparatives — rule-2 compliant |
| 5 | Single extraction call → 9-section v2 JSON, `json_object`, temp 0.2, `max_tokens=8000`, thinking off | `openai_service.py:255-407, 455-534`; `extraction.py:24-53` | **Prod runs the streaming branch** (`STREAM_SECTION_REVEAL=true`, `.github/workflows/ci.yml:386`; branch `:413-433`) |
| 6 | json_repair → coerce → empty-section detection → LLM recovery (12s, 500 tok, ≤6000-char context) → machine-authored XBRL fields | `:560-620`; `ai/section_recovery.py:97,133-137`; `ai/markdown_render.py:232+` | Recovery regex runs on **raw HTML** (`extraction.py:554` no-op "clean") or `excerpt[:6000]` on cache hit |
| 7 | Guards on shared `sections_info`: taxonomy filter (:763), bank revenue-row sanitizer (:772), forward-quote gate (:796), evidence snap (:815) | `openai_service.py:757-822` | Excerpt-only grounding; no excerpt → measure nothing |
| 8 | Coverage → `render_sections` (one projection) → complete/partial/error | `:824-1096` | partial <0.5 / <0.7 (:1071,:1083) |
| 9 | 75s in-stage cutoff → deterministic `generate_xbrl_summary` (partial) | `summary_pipeline.py:673-704`; `fallback_summary.py:414` | `status="error"` not persisted (:708) |
| 10 | `assess_quality` (4/9 bar, XBRL literal grounding, figure-trace list) → counters → persist (keep-better) → quota | `summary_generation_service.py:148-357`; `summary_pipeline.py:771-856` | stamps schema 2 / `summary-2026-07-k` |
| 11 | Read-time exact-match provenance (Verified badge) | `provenance_service.py:247-300` | exact-only by design |

**Guard ledger (prod truth = `config.py` defaults + `ci.yml:386` overrides):**

| Guard | Flag / default | Prod | Mode |
|---|---|---|---|
| Taxonomy filter, bank sanitizer, machine-authored XBRL fields | — | — | **Acting** |
| S4 quality gate | `AI_QUALITY_GATE=True` (:341) | on | Acting on billing/badge only |
| XBRL literal grounding (rev/NI) | in `assess_quality` | — | Acting (tiers partial) |
| Figure-trace | `AI_FIGURE_TRACE_GATE=False` (:351) | off | **Measure-only** (`figure_trace_untraceable` log :782) |
| Forward-quote gate | `AI_FORWARD_QUOTE_GATE=False` (:362) | off | **Measure-only** (:822); "don't arm" ratified — 8/8 near-miss, 0 fabrications |
| Evidence auto-snap | `AI_EVIDENCE_SNAP=False`, min 72 (:379-380) | off | **Measure-only** (:840); armed ceiling 0.675→0.859 citation_fidelity |
| `machine_sections_only` | — | — | Measure-only (:807) |
| `USE_STRUCTURED_OUTPUT=False` (:320) | — | off | never adopted |
| `USE_STATEMENT_FINANCIALS=False` (:429) | — | **on out-of-band** (`docs/data-quality-remediation-log.md:55`) | acting in prod, **off in eval env** |
| `STREAM_SECTION_REVEAL=False` (:498) | — | **on** | eval never exercises it (`evals/runner.py:161` no `stream_cb`) |
| `ENABLE_FPI_FILINGS=False` (:390) | — | **on** | RUNBOOK:428 "Intentionally NOT added yet" — stale |

Observability: the five counters are INFO logs only; `scripts/setup_citation_alerts.sh` covers Copilot only; `docs/OPERATIONS.md` never mentions them. The "fleet readout" every arming decision depends on has no viewing surface.

## (B) Measured / not measured

Pinned bar (`backend/evals/baseline_scores.json`, 2026-07-13, 26×3, judge off): gate_fail **0.0** (HARD), precision **1.0** (HARD −0.05, labeled rev/NI/EPS only, `scorers.py:247`), coverage **1.0** (HARD), recall **1.0** (HARD −0.10), pass 1.0, stdev 0.0, depth 0.979, specificity 0.992, currency 1.0, redundancy 0.946, delta 0.942, forward_quote 0.949 (band 0.923–0.962), **citation_fidelity 0.689**, citation_checked 6.27 (all WARN). Aggregate 0.30/0.45/0.25 (`schema.py:185`).

Honest reading: every HARD dim is saturated with zero variance. Recall/precision test whether XBRL ground-truth values appear in output — the grounding block hands the model those values, and `_apply_structured_fallbacks` machine-writes cash/WC figures "to hold the numeric-recall floor" (`markdown_render.py:245-249`). HARD gates protect plumbing, not prose.

CI (`ci.yml:125-206`): PR/dispatch only (:126) — skipped on main by design; path-filtered (:147); needs `DEEPSEEK_API_KEY` secret (:157-163; lessons say armed); `continue-on-error` (:128), not in deploy `needs:` — advisory. `--runs 1` (:195) → one stochastic veto (1/26=0.038 > 0.005) fails the job (open follow-up in `tasks/archive/t3.1-v2-cutover-todo.md`). Env pins `USE_STRUCTURED_OUTPUT=false` but not `USE_STATEMENT_FINANCIALS`. Gate ignores `harness.model` (`regression_gate.py:130-146`); no `response.model`/`system_fingerprint` read anywhere.

**Not measured:** faithfulness/G2/G3 hallucination (judge-only, `judge.py:7-9,47-49`, off everywhere; July judged floor 3.78/5 with 4/9 runs flagged, `lessons/arch-edit-causal-directive-add-example.md`); untraceable-$ figures (app-only, not an eval dim); %/ppt/ratio prose figures; risks evidence fidelity (excluded, `scorers.py:849-856`); insight/usefulness; **6-K** (0 in golden set vs 11 10-K/9 10-Q/7 20-F; prod serves them); G5 bank gate dormant (RUNBOOK:61-72); no REIT/utility/insurer/micro-cap; Copilot golden set 2 entries, both `verified:false`; no trends golden set (RUNBOOK:537); **no per-summary tokens/cost/model telemetry** (grep `usage` in `openai_service.py`: none; only copilot/analysis emit `*_inference_cost`).

## (C) Unfinished quality work

| Item | Evidence | Status | Size | Impact |
|---|---|---|---|---|
| Evidence auto-snap arming | `config.py:364-380`; `tasks/archive/evidence-auto-snap-todo.md` | Shipped-unarmed; decision blocked on unviewable forensics | S–M | High (trust surface; known false-Verified class) |
| Forward-quote gate | `config.py:353-362` | Shipped-unarmed; "don't arm" ratified | S | Low |
| Figure-trace tier gate | `config.py:343-351` | Shipped-unarmed; FP readout never recorded | S–M | Medium |
| -j evidence-as-prose / -k copy-don't-compose | archive plans | -j shipped (+31%); -k measured flat → stopped (correct) | — | done |
| YoY% amplifier; GLM-5.2 swap | lessons; `glm-5.2-bakeoff.md` | measured harmful/tie → dropped (fine) | — | — |
| Red-flag callouts (A14) | `markdown_render.py:251` "lands later" | **Open** | M | High |
| G5 re-arm (JPM components) | RUNBOOK:61-72 | **Open**; prod already emits them | S | Medium |
| Eval↔prod parity (`USE_STATEMENT_FINANCIALS`, streaming) | `ci.yml:179-188`; `runner.py:161` | **Open** | S | Medium |
| Single-run gate_fail granularity | t3.1 plan follow-up | **Open** | S | gate credibility |
| Fleet refresh to `-k` | all -i/-j/-k plans "founder timing" | **Open (ops)**, unverifiable | S | High for existing rows |
| Stable prompt prefix (T6.1) | `openai_service.py:370-407` schema/Rules placed AFTER excerpt | **Open** | S | cost only |
| Off-peak scheduling (T6.2) | pregenerate cron 06:00 UTC = inside surcharge window **[hypothesis]** | **Open** | S | cost |
| `SUMMARY_SELF_VERIFY` (T6.3) | absent from config | Open, optional | M | potentially high |
| Recovery grounding (raw HTML, 6000 cap) | `extraction.py:554`; `section_recovery.py:97` | **Open** | S | Medium on degraded tail |
| Dead Gemini fallback / no retry | `openai_service.py:81-92,455,511,534` | **Open** | S | availability |
| Summary cost/model telemetry | none | **Open** | S | drift + cost |
| 6-K / sector / small-cap golden entries; Copilot & trends golden sets | `golden_set.json`, `copilot_golden_set.json` | **Open** | M | High |
| Multi-Period audit (P0/P1) | `tasks/analysis-review-findings.md` §8 | Shipped except counsel item | — | — |
| `previous_filings` latent path | `openai_service.py:242-253` | Open hygiene (rule 12) | XS | removes only cross-filing prompt path |
| Docs drift | RUNBOOK:428 vs `ci.yml:386`; report-quality plan header; Gemini comments `openai_service.py:77-100` | Stale | XS | — |

## (D) Risks

| Risk | Evidence | Sev | Mitigation |
|---|---|---|---|
| Prose-faithfulness regressions invisible to gate (saturated HARD dims, judge off, figure_trace not an eval dim) | `baseline_scores.json`; `scorers.py`; `judge.py` | **P0** | Pin `mean_untraceable_dollar_figures` (WARN); scheduled judged run (`cli:sonnet`/`glm-5.2`, 8 filings, `--runs 3`) |
| No real retry/fallback: `[deepseek-v4-pro, gemini-2.5-pro, gemini-2.5-flash]` sent to DeepSeek; `max_retries=1`; 429 → two 404s → surfaces Gemini 404 → `status=error`; streaming uses primary only; retry test injects fake names | `openai_service.py:81-92,410,418,455,511,534`; `section_recovery.py:143`; `tests/unit/test_openai_service_retry.py:23` | **P1** | Backoff retry on primary + env `AI_FALLBACK_BASE_URL/MODEL` (GLM validated); delete Gemini chain; pin |
| Copilot tools company-scoped: `_query_fact` = `company_id`+`is_latest`, default most-recent → older filing's page can cite a newer filing's `[F1]` | `copilot_tools.py:210-231,264-277` vs `copilot_service.py:60-63` | **P1** | Default period from the filing; or bound to accession; resolver test **[user impact hypothesis]** |
| Measure-only gates have no readout | `summary_pipeline.py:782-848`; alert script Copilot-only | **P1** | Log-based metrics + weekly rollup from persisted `raw_summary` audits in `data_quality_service` |
| Eval scores non-prod bank path and non-prod call path | `ci.yml:179-188,386`; remediation log :399-404 | **P1** | Set flag in eval env/default; restore JPM facts; re-pin; pin streaming≡non-streaming |
| Weak recovery grounding | `extraction.py:554`; `section_recovery.py:81-106` | P2 | Build context from labeled excerpt sections, ~30k cap |
| Silent provider model drift undetectable | no `response.model` logging; gate ignores `harness.model` | P2 | Log model+usage per summary; judged drift run |
| Unguarded context-limit / empty-context paths: enrichment timeout → 15k raw HTML, no grounding, gates measure nothing, badge can read "full"; no token counting; context-length 400 cascades into dead chain | `openai_service.py:175`; `summary_pipeline.py:143`; `figure_trace.py:262-270` | P2 | Hard partial reason when no excerpt AND no XBRL; log prompt size; add test (none covers `[:15000]`) |
| Advisory gate noisy at `--runs 1` | `ci.yml:195` | P2 | granularity-aware tolerance or `--runs 2` |
| Latent cross-filing prompt path | `openai_service.py:242-253` | P2 | delete param + AST pin |
| Fleet staleness vs verbatim contract | version ledger; plans | P2 (ops) | record refresh; `is_stale` counts on `/metrics` |

## (E) Top-5 investments

1. **Prose-fidelity signal for the gate (P0)** — figure_trace as pinned eval dim + scheduled judged run. The only thing that would catch the causal-fabrication class the founder cares most about. S+S.
2. **Make measure-only channels observable, then arm** — metrics/rollup from persisted audits; decide `AI_EVIDENCE_SNAP` (biggest ready trust win, +0.17) and `AI_FIGURE_TRACE_GATE`. S–M.
3. **Real retry + fallback + telemetry** — kill the dead Gemini chain, add backoff + env failover, log `usage`/`response.model`. S–M.
4. **Eval↔prod parity + G5 re-arm** — `USE_STATEMENT_FINANCIALS` in eval/default, restore JPM facts, re-pin, pin streaming path. S.
5. **Golden-set breadth where prod already serves uncovered forms** — 6-Ks, REIT/utility/insurer, small caps; verify Copilot set. M.

Honorable mentions: recovery-context fix; delete `previous_filings`; prompt-prefix caching; fix three stale docs.
