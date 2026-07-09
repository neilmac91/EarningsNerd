# Tier 5.1 — Earnings quality fed deterministically (NI-vs-CFO cash conversion + FCF)

**Goal (roadmap T5.1 / plan §3):** the earnings-quality section — "the differentiator sophisticated
readers pay for" — gets a GROUNDED, machine-authored cash-conversion read (operating cash flow vs net
income + free cash flow) instead of model prose. "Numbers from code, words from the model": code owns the
cash-conversion figures; the model keeps the one-time bridge (operating_vs_one_time) + red_flags. $0 infra.

## Load-bearing facts from the understand-phase map (6 subagents)

1. **Injection point exists + proven.** `markdown_render._apply_structured_fallbacks` (229-379) runs once
   at `openai_service.py:586` (inside summarize_filing, AFTER model+recovery, before storage), mutating
   `sections_info` in place. It already machine-authors `balance_sheet_liquidity.cash_flow` (omitted from
   schema → filler sole author) and `working_capital` (in schema, overwritten unconditionally). T5.1
   reuses this exact filler + its helpers (raw_current/raw_prior/metric_entry, format_currency/money_prefix
   — currency-aware, markdown_render.py:253-299).
2. **Inputs all present, no new extraction.** net_income (xbrl_service.py:1055), operating_cash_flow
   (1082, ALWAYS extracted), free_cash_flow (1121-1136, = OCF−|capex|), each {current,prior,series}.
   Cash-conversion ratio = OCF/NI (reuse the ROE/ROA denom!=0 guard, 1159-1172).
3. **figure_trace allowlist edit is FORCED.** `cash_conversion` is in `_PROSE_STRING_FIELDS['earnings_quality']`
   (figure_trace.py:81). Once code authors it, the NI-vs-CFO *relationship* (a derived value present in no
   single XBRL magnitude) would false-flag as an untraceable model-derived aggregate → once
   AI_FIGURE_TRACE_GATE is armed, that tiers a good summary "partial". MUST remove it, mirroring the
   cash_flow/working_capital exclusion (figure_trace.py:76-92).
4. **Bank correctness.** NI-vs-CFO/FCF are meaningless for banks (lending/deposit cash flows, no capex).
   `xbrl_narrative.py:138-147` already suppresses FCF/working-capital for FIs. Gate the filler on NOT
   `fi_components_present(xbrl_metrics)` (app/services/ai/fi_signals).
5. **One-home.** OCF's $ home is §8 cash_flow (the 3 legs); NI's is §2 results. §3 references them via the
   RATIO (cash conversion Nx) + FCF (FCF's own home is §3), NOT by re-quoting levels — mirroring the
   existing ONE-HOME rule (openai_service.py:388) that already tells the model to keep §3 qualitative.
6. **Eval.** financial_depth's cash-flow bucket is already saturated by the cash_flow bridge, so this is
   largely ORTHOGONAL to the scored dims (WARN, not in aggregate). Still a content+prompt change → run
   --runs 3, protect HARD gates (gate_fail/precision/coverage/recall), re-pin only if the bar intentionally
   moves (RUNBOOK).

## Plan

**STATUS: implemented; gates green; adversarial review clean; eval PASS (see below).**

- [x] **markdown_render.py `_apply_structured_fallbacks`**: cash_conversion block after the cash_flow block.
      Composes (currency-aware) "Operating cash flow was {ratio}x net income (cash conversion); free cash flow
      of {FCF}." from raw_current(net_income/operating_cash_flow/free_cash_flow). Ratio requires NI>0; missing
      FCF → ratio-only; missing ratio → FCF-only; authors nothing when neither is computable. Bank-gated on
      NOT fi_components_present. Overwrites unconditionally. **Loss-branch enhancement (adversarial-review
      driven):** a net LOSS with POSITIVE operating cash flow now authors "operating cash flow was positive
      despite a net loss" — §3's highest-value accrual signal (cash generated despite a GAAP loss), which the
      minimal FCF-only design silently dropped. Deterministic + threshold-free (NI<0 ∧ OCF>0); ONE-HOME-safe
      (no dollar level re-quoted). Expert extension of the locked plan, documented here + in the PR.
- [x] **openai_service.py schema_template**: cash_conversion REMOVED from the earnings_quality object
      (mechanism A). ONE-HOME rule note reworded. SUMMARY_PROMPT_VERSION → summary-2026-07-e.
- [x] **figure_trace.py**: 'cash_conversion' removed from `_PROSE_STRING_FIELDS['earnings_quality']`.
- [x] **summary_schema.py**: EarningsQuality.cash_conversion annotated machine-authored.
- [x] **section_recovery.py**: cash_conversion dropped from the earnings_quality re-ask snippet.
- [x] **Tests (rule 12):** ratio+FCF (currency-aware); ratio-only; loss+posOCF → qualitative read (+FCF);
      loss+posOCF, no FCF → qualitative only; loss+cash-burn, no FCF → authors nothing; negOCF+posNI →
      negative multiple; bank → suppressed; metrics absent → graceful; partial XBRL (NI-missing / OCF-missing)
      → FCF-only, no crash; overwrite; figure_trace no longer polices cash_conversion.
- [x] **Full backend gate:** ruff + bandit clean; **1609 passed**. (Frontend untouched — cash_conversion
      renders through the existing generic paragraph-block path in summary_sections.py; no frontend change.)
- [x] **Eval --runs 3:** HARD gates hold at ceiling (gate_fail 0.0; numeric_accuracy/precision/coverage/
      currency 1.0). Regression gate **PASS (0 warnings)**. No re-pin (bar did not intentionally move).
- [x] **Adversarial review workflow** (4 dims → adversarial verify): confirmed_count 0. The two worthwhile
      nits actioned: figure_trace comment accuracy + the loss-branch signal above.

## Eval-process follow-up (staff review, non-blocking)
- Tag `generation_collapse` rows in the eval report (crisp signature: `schema_valid=false` + zero facts +
  every section empty — the 40s EdgarTools cap on the largest 20-Fs keeps producing these) and print BOTH
  raw and collapse-excluded means, so "flake-adjusted" is a first-class reproducible readout instead of
  reviewer-trust hand-analysis in a PR body. **Tag, don't retry-and-hide** — silent retries would bias the
  consistency dimension the eval exists to measure. → T5 follow-up list.

## Not in scope (this PR)
- red_flags code-authoring (negative-FCF/accrual callouts) — the cash_conversion line already surfaces the
  accrual read; the callout adds threshold-judgment + list-merge nuance → follow-up.
- operating_vs_one_time (no standardized XBRL for one-time items → stays model-extracted).
- T5.2 segments (by_dimension is in edgartools 5.40.1 — NO bump — but needs an extraction helper + eval
  scorer). T5.3 value drivers (dividends/buybacks/ROIC concepts NOT extracted). T5.4 forward-quote hard gate.
