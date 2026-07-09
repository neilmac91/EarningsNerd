# Tier 5.2 — Segments fed deterministically (per-segment revenue / operating income from XBRL dimensions)

**Goal (roadmap T5.2 / plan §7):** the Segments section gets a GROUNDED, machine-authored per-segment
revenue + operating-income table from the filing's own XBRL `StatementBusinessSegmentsAxis` dimensions,
instead of model-authored figures. "Numbers from code, words from the model." $0 infra (no edgartools bump —
`by_dimension` is confirmed working on the pinned 5.40.1). Mirrors the proven T5.1 machine-authoring pattern.

## Load-bearing facts (understand-phase: 2 workflow maps + direct verification)

1. **`by_dimension` works on pinned 5.40.1** (verified live: AAPL→5 geographic segments, MSFT→3 product
   segments). API: `xb.facts.query().by_concept(concept, exact=True).by_dimension("StatementBusinessSegmentsAxis")
   .to_dataframe()` → one row per (concept×member×period); `dimension_member_label` = clean segment name,
   `numeric_value` = float. Empty DataFrame (never None) for single-segment / untagged filers.
2. **Rule-5-safe reuse point.** The pipeline already fetches `xb = filing.xbrl()` at `xbrl_service.py:258`
   inside `_extract_from_filing_instance_sync`. The segment helper MUST run there while `xb` is in scope
   (writing `result["segments"]`) → ZERO new SEC traffic, rides the existing L1/L2 cache + `Filing.xbrl_data`.
   `filing.xbrl()` bypasses the app rate-limiter, so a separate fetch would violate rule 5 — do NOT re-fetch.
3. **The code deliberately discards dimensional facts today** (`instance_extractor.py:351,398`:
   `if row.get("is_dimensioned"): continue`). T5.2 keeps them, filtered to the segment axis. All period /
   currency primitives already exist (`duration_in_window`, `_iso_date`, `_numeric`, `_currency`).
4. **Period-selection lesson (`sec-xbrl-period-selection.md`):** NEVER trust `fy`/`fp` or `period_end.max()`
   — select segment facts for the filing's OWN reporting period via `duration_in_window(..., period_of_report)`,
   the same discipline the consolidated path uses. Concept-list ORDERING is behavior (tag priority), not style.
5. **Reliability caveats (verified):** (a) co-present axes — filter on `StatementBusinessSegmentsAxis` alone
   (GH-607 makes `member`/label report that axis correctly); (b) drop Corporate / Elimination / Intersegment /
   Reconciliation / Total members or you double-count; (c) revenue tag varies
   (`RevenueFromContractWithCustomerExcludingAssessedTax` → `Revenues` → `SalesRevenueNet`) — ordered fallback,
   `exact=True`; (d) banks skip generic revenue tags (period-selection lesson) → segments degrade to empty for
   FIs, matching the roadmap's graceful-degradation intent; (e) sum(segments) ≈ consolidated is the sanity check.
6. **Render/schema (verified directly).** `SegmentRow{segment, revenue, operating_income, change, commentary,
   source_section_ref}` (all strings), rendered as a table by `summary_sections._v2_segments:687`. Today
   FULLY model-authored — the fabrication surface T5.2 removes.
7. **Eval plumbing.** `score_summary(payload, ground_truth)` is PAYLOAD-ONLY (no `xbrl_metrics`), so an
   XBRL-fidelity segment scorer needs harness threading (defer, like the T4 citation scorer). Deterministic
   segments are correct-by-construction (pinned by extraction unit tests + live verification); the existing
   coverage / financial_depth scorers reflect the added content. Run `--runs 3`, protect HARD gates.

## Design decision — DETERMINISTIC table (expert call; deviates from the roadmap's hybrid — for founder review)

The roadmap (§7, line 156/287) wanted "injected figure table **+ model commentary on mix and concentration**."
This PR ships the table **fully deterministic** — code owns segment name + revenue + YoY change + operating
income, and `commentary` = a deterministic **mix read** (revenue share %). The model no longer authors segments
(mechanism-A). **Why deviate:** aligning model-authored segment rows to XBRL segment labels by name is fragile
and is itself a fabrication surface — exactly what T5.2 exists to remove. The deterministic mix% delivers the
concentration signal without that risk. The model's qualitative segment "why" (a robust hybrid: code figures +
model commentary matched to code rows with a deterministic fallback) is a documented **T5.2b follow-up**.
Flagged prominently in the PR for the founder to weigh in (per the standing "document the request in a PR").

## Plan

**STATUS: design locked; implementing. Single PR (split to T5.2a extraction / T5.2b surfacing only if it balloons).**

- [ ] **`edgar/instance_extractor.py`**: new `segment_series(xb, concepts, form, period_of_report, axis=…)`
      helper — sibling of `duration_series_currency_concept`. Query `by_concept(exact).by_dimension(axis)`, KEEP
      dimensional rows, constrain to the filing's own period via `duration_in_window` (NOT `period_end.max()`),
      drop Corporate/Elimination/Intersegment/Reconciliation/Total members, ordered revenue-concept fallback,
      currency-aware. Returns per-member `{label, revenue{current,prior}, operating_income{current}, period,
      currency}`.
- [ ] **`edgar/xbrl_service.py`**: call it inside `_extract_from_filing_instance_sync` after `xb = filing.xbrl()`
      (:258); write `result["segments"]` (rides existing cache + `Filing.xbrl_data`). Standardize into a clean
      list `[{name, revenue, revenue_prior, operating_income, period}]` (sibling of `extract_standardized_metrics`
      or inline). Boundary validation (rule 9): compute sum(segment revenue) vs consolidated revenue; surface a
      coherence flag; keep the section only when ≥2 coherent segments.
- [ ] **`ai/markdown_render.py` `_apply_structured_fallbacks`**: machine-author `segments` from
      `xbrl_metrics["segments"]` — pop-first ownership (strip any model `segments`), inject deterministic rows:
      `segment`=label, `revenue`=format_currency, `operating_income`=format_currency|"", `change`=YoY% (revenue
      vs revenue_prior), `commentary`=mix read ("N% of revenue"). Currency-aware. Degrade gracefully: no rows →
      section empty. Overwrite unconditionally (model no longer authors it).
- [ ] **`openai_service.py` schema_template**: REMOVE the `segments` object (mechanism-A). Update the ONE-HOME
      note (segments injected). Bump `SUMMARY_PROMPT_VERSION → summary-2026-07-f`.
- [ ] **`ai/section_recovery.py`**: drop `segments` from the re-ask snippet (it's injected).
- [ ] **`ai/figure_trace.py`**: exclude `segments[].commentary` from `_prose_blob` (machine-authored — mirror the
      cash_conversion exclusion; the mix% is a `%` the dollar-gate ignores anyway, but keep the category correct).
- [ ] **`summary_schema.py`**: annotate `SegmentRow` figure fields as machine-authored.
- [ ] **Tests (rule 12):** extraction unit tests with a mocked `xb.facts.query()` chain — multi-segment happy
      path; Corporate/Elimination/Total filtered; concept fallback ordering; single-segment / no-dimension →
      empty; period constrained to reporting window (NOT max); currency. markdown_render tests — segments injected
      from xbrl_metrics; stray model segments stripped; graceful empty; currency; mix% + YoY. Live scratchpad
      verification vs AAPL / MSFT (dev-only, like the T4 readout).
- [ ] **Full backend gate + eval `--runs 3`** → HARD gates hold → no re-pin unless the bar intentionally moves.
- [ ] **Adversarial review workflow → fix → commit → push → draft PR** (document: the deterministic-vs-hybrid
      deviation + T5.2b model-commentary follow-up; the deferred XBRL-fidelity eval scorer; geographic-segment
      axis as a follow-up; graceful degradation for banks/untagged filers).

## Not in scope (this PR / documented follow-ups)
- **T5.2b — model mix/concentration commentary** (robust hybrid: code figures + model commentary matched to
  code rows, deterministic fallback) — the roadmap's "+ model commentary" half.
- **Geographic segments** (`StatementGeographicalAxis`) — keep to ASC-280 operating segments here to avoid
  conflating the two breakdowns; geographic is a clean follow-up.
- **XBRL-fidelity segment eval scorer** (needs `score_summary` to receive `xbrl_metrics` — a harness refactor).
- **T5.3 value drivers** (dividends/buybacks/ROIC concepts not extracted). **T5.4 forward-quote hard gate.**
