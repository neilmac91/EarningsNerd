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

## In progress — Wave 2 (narrative quality), judge-gated
- [x] Add to 10-K/10-Q/20-F analyst prompts: "What changed & why" driver directive (management's causal
      language), anti-boilerplate specificity (discourages exactly the phrases `score_specificity` flags),
      risk-factor materiality filter (company-specific/quantified only).
- [x] Verify all forms still load (prompt_loader); 6-K intentionally unchanged.
- [ ] Judge **before** baseline on current prompts (running, `--runs 3 --judge`).
- [ ] Judge **after** on the Wave 2 prompts; compare before/after (insight/specificity/clarity hold-or-improve).
- [ ] Deterministic gate: `mean_specificity` ↑, no recall/precision/coverage regression (`regression_gate`).
- [ ] Run full pytest + ruff; commit; push; open draft PR; founder review/merge.

## Method / guardrails (CLAUDE.md)
- Eval-gate every wave (deterministic no-regression + judge hold-or-improve). Re-pin baseline on a locked gain.
- Run the FULL pytest AND `ruff check .` before pushing (lessons.md).
- Surgical edits; keep directives lean (over-prescription → formulaic prose risk).
