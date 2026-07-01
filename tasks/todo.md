# Task: Sharpen the AI reports via eval-gated prompt-prose waves (post-council activation)

## Task #18 — Two-tier judge wiring (measure Wave 4 cheaply) — DONE, shipping
- [x] `evals/judge.py`: dispatch `judge_summary` on the model id via `judge_backend()` →
      three backends, existing Opus path refactored (behaviour unchanged):
      - `claude-*` → **anthropic SDK** (`ANTHROPIC_API_KEY`, API credits) — DEFAULT, authoritative.
      - `cli:sonnet`/`cli:opus` → **subscription CLI** (`claude -p --output-format json`), with
        `ANTHROPIC_API_KEY` stripped from the child env so it uses the logged-in Claude
        subscription (OAuth), not API credits. Manual/local only (no OAuth in CI).
      - `glm-5.2`/`openai:<model>` → **OpenAI-compatible** (z.ai), `JUDGE_OPENAI_BASE_URL/API_KEY`
        (fall back to `OPENAI_*`). Cheap CI/fallback judge.
- [x] Shared `_judge_with_retry` (2 attempts, parse, never raises) factored out of the old loop.
- [x] `--judge` help + `evals/RUNBOOK.md` document the backends + the **agreement-check** gate
      (default stays Opus so a cheaper judge can't *silently* weaken the bar).
- [x] Tests: `judge_backend` routing (10 cases), dispatch, missing-cred graceful-fail for each
      backend, retry-then-parse, CLI subprocess mock asserting `ANTHROPIC_API_KEY` stripped + JSON
      parsed from the `result` wrapper. 24 judge tests; full suite **864 passed**; ruff + bandit green.
- [x] **Live wiring smoke** (synthetic G3-hallucination case): all three backends caught the
      fabricated outlook and returned FAIL — `cli:sonnet` matched Opus exactly `{2,2,4,3}`,
      `glm-5.2` within 1 pt. Wiring proven; fuller golden-set agreement check runs with Wave 4.


## Wave 3 — ADR go-live (in PR #484) — RESULTS
- [x] **20-F ADR prose** (3 groundable items: filing-stated risk-change, convenience-translation
      date/rate, restatement/basis flag). Judged before/after on 7 20-F golden filings (fixed judge):
      recall +0.012, no deterministic regression, judge dims flat-within-noise, G3 fabrication flags
      down on most ADRs. **Ship.**
- [x] **`--forms` eval filter** (cheap per-form judged runs; e.g. `--forms 20-F` = 7 vs 22 entries).
- [x] **`USE_STRUCTURED_OUTPUT` evaluation → DON'T FLIP.** Full-set analyst vs structured: structured
      **loses 5.6 pts recall** (0.796 vs 0.851), less consistent, no offsetting gain. Keep OFF; the
      `*-structured-agent.md` prompts stay dormant; no case to invest in structured-agent prose.
- [x] **Currency-consistency guard** (`score_currency_consistency`) — deterministic scorers are
      currency-AGNOSTIC (numeric_precision matched value not unit), so a foreign filer's figures
      rendered as bare `$` (e.g. DKK→`$`, a ~7x distortion) was invisible. New scorer flags bare-`$`
      on non-USD filers (US$/NT$/HK$ excluded via lookbehind; currency-alias native counting).
      WARN-gated (not hard — the slip is intermittent, would flake CI). Validated on real NVO/BABA/ASML.
- [~] **FPI adoption gate / `ENABLE_FPI_FILINGS` flip** — Step A (offline tests) green; B/C eyeball:
      currency correct on **6/7 ADRs all runs**; **NVO (DKK) has an intermittent ~1/3 `$`-slip**
      (the prompt already says "never render non-USD as `$`" yet the model occasionally ignores it).
      GO-LIVE DECISION for founder: (a) flip now, accept the rare DKK slip with the guard monitoring,
      or (b) hold until a runtime currency-enforcement (post-gen: regenerate/flag if reporting_currency
      != USD and bare-`$` present) reduces it. Recommend (b) if DKK-class quality matters at launch.

## Context
The report **is** the product. Highest-leverage, lowest-risk lever right now is improving the AI
prompt prose (content + presentation), each change gated on the eval (deterministic scorers always;
LLM judge for qualitative dims). Full plan: `~/.claude/plans/act-as-an-expert-adaptive-rivest.md`.

## Shipped (merged to main)
- [x] **Wave 0a** — re-verified ASML in the golden set after #478 (drift-free; 26/27 verified). (#479)
- [x] **Wave 1** — figure-citing directives (working capital, full operating/investing/financing
      cash flow, EPS nuance) in 10-K/10-Q/20-F analyst prompts. (#479)
- [x] **Wave V** — visual appeal: bold key figures (prompt prose + deterministic `_build_structured_markdown`);
      editorial-writer path is disabled (decision 3a), so the renderer is the real lever. (#479)
      Eval-gated: recall 0.778→0.816, precision/coverage/gate held, latency flat. Baseline re-pinned.
- [x] **Reset-all endpoint** — `POST /api/admin/summaries/reset-all` (FK-safe, dry-run, keeps
      XBRL/content, `include_saved` opt-in) to refresh summaries after a prompt change. (#480)
- [x] **Phase-2 readiness** — deterministic `score_specificity` scorer (anti-boilerplate + change-language,
      CI WARN-gated) + made the LLM judge reliable (no temperature, max_tokens 4096, json_repair, retry)
      + re-pinned baseline with `mean_specificity=0.9857`. (#481)

## Wave 2 (narrative quality), judge-gated — COMPLETE, shipping
- [x] Add to 10-K/10-Q/20-F analyst prompts: "What changed & why" driver directive, anti-boilerplate
      specificity, risk-factor materiality filter. Verified all forms load (6-K unchanged).
- [x] Judge before/after (DeepSeek, `--runs 3 --judge`) + GLM bake-off, all 78 runs each, 0 errors.
- [x] **Result:** regression gate GREEN — recall +0.009, precision/coverage/gate_fail held,
      specificity flat (−0.0012; deterministic scorer saturated ~0.99). Judge specificity +0.074,
      insight +0.058 (before/after delta valid; both old-cap). No regression anywhere; small positive.
- [x] Deterministic specificity target didn't move (scorer near-ceiling) → Wave 2 is a
      **no-regression prose refinement**, NOT re-pinning baseline (re-pin only on a locked gain).
- [x] Full pytest (818 unit) + ruff + bandit GREEN. Push + draft PR.
- [ ] (Optional, ~$50, founder call) Fixed-cap authoritative judged run on the Wave-2 config for
      trustworthy faithfulness/insight numbers now that the judge sees the full excerpt (528827a).

## MAJOR finding this session — judge truncation artifact (FIXED, 528827a)
- Judge saw `excerpt[:60000]` while the model grounds on the full ~124–165k excerpt → real
  deep-filing facts (buybacks/dividends/segment revenue, late in a 10-K) were false-flagged as G3
  hallucinations, driving faithfulness to 1.96 / judge_pass 0 across all 78 runs — despite
  deterministic numeric_precision 1.0. Proved on AAPL FY25 ($100B buyback at char 73,895, past 60k).
  Raised cap to 200k; verified faithfulness 2→4, insight 3→4 on the same summary. **The pipeline was
  never hallucinating; the judge was under-contexted.**

## GLM-5.2 vs DeepSeek bake-off — COMPLETE (see tasks/glm-5.2-bakeoff.md)
- [x] Full-pipeline env-swap, judge-on, identical Wave-2 prompts. **Quality dead-heat** (deltas within
      noise; both perfect on precision/coverage/gates; 0/78 errors). DeepSeek ~48% faster, ~3.5×
      cheaper. **Decision: stay on DeepSeek; keep GLM-5.2 as a validated env-swap failover.**
- [x] Generalized reasoning-model thinking-disable to GLM/z.ai (264eb65; DeepSeek/Gemini unchanged).

## Method / guardrails (CLAUDE.md)
- Eval-gate every wave (deterministic no-regression + judge hold-or-improve). Re-pin baseline on a locked gain.
- Run the FULL pytest AND `ruff check .` before pushing (lessons.md).
- Surgical edits; keep directives lean (over-prescription → formulaic prose risk).
