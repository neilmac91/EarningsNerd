# Task: Sharpen the AI reports via eval-gated prompt-prose waves (post-council activation)

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
