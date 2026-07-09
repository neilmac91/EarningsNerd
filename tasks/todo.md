# Tier 5.2b — segment commentary hybrid + N/A-denominator badge semantics

**Goal (both halves founder-prescribed in the #616 staff review):**
(A) the model's qualitative mix/concentration read returns to §7 — **attached to the code rows, keyed by the
code's own labels, never emitting rows** — so the model can never desync from or fabricate a segment;
(B) the quality badge stops penalizing by-design-absent segments: a genuinely single-segment filer reads a
clean `8/8`, not a misleading `8/9` (**N/A-denominator semantics**, not a de-count).

## Load-bearing facts (verified on post-#616 main)

1. **Filler pops first** (`markdown_render.py:442`) — harvest the model's commentary from the popped value
   BEFORE discarding; ownership invariant intact (only label-matched commentary survives, figures never).
2. **Snapshot is post-fallback** (`openai_service.py:752-768`) — `per_section["segments"]` already reflects
   the AUTHORED state, so `not coverage_map["segments"]` IS the by-design-absent signal (code is sole author).
3. **Verdict math** (`summary_generation_service._verdict_coverage:167-184`) — per_section ∩ tracked; the
   4/9 bar is an absolute literal (total dropping to 8 can't graze it). Legacy snapshots lack the new key →
   behavior identical (backward-compatible by construction). Frontend declares `covered_count/total_count`
   but no component renders them — blast radius is the verdict payload + the "only X/Y" reason string.
4. **figure_trace** currently excludes segments commentary (machine-authored in T5.2). Model prose returns →
   RE-INCLUDE `segments[].commentary` in `_prose_blob`; the deterministic mix/margin is %-only so the
   dollar-gate ignores it — no false positives from the machine half.
5. **Grounding**: `xbrl_narrative` says nothing about segments today. The model needs the code's labels →
   append a labels-ONLY block (no figures, no derived % — the `arch-no-precomputed-deltas-in-grounding`
   lesson) when ≥2 reportable segments exist.

## Plan

**STATUS: shipped to PR #617 — implemented, reviewed, eval PASS ×2, awaiting founder review/merge.**

- [x] **xbrl_narrative.py**: `REPORTABLE SEGMENTS (XBRL)` labels-only block (revenue order); instruction
      refined post-live-probe: "never restate the segment's OWN revenue/op-income/YoY (the table carries
      them); finer-grained product/sub-segment facts welcome" — the model was contributing valuable
      sub-segment facts ("Azure grew 34%") that honor ONE-HOME's intent.
- [x] **openai_service.py schema_template**: `segments` re-added COMMENTARY-ONLY; nine-sections rule +
      ONE-HOME clause reworded; blanket "arrays never empty / no empty sections" rules carve out segments
      (review finding: self-contradiction → placeholder-row waste).
- [x] **markdown_render.py**: harvest-before-pop merge; strings-only guard (dict commentary would repr into
      the cell — review finding); placeholder filter extended (not applicable / n/a / leading dashes).
- [x] **figure_trace.py**: `segments[].commentary` policed again; module docstring updated.
- [x] **N/A badge**: snapshot `not_applicable` + verdict denominator math (deduped, per_section-is-truth,
      legacy-compatible, absolute 4-bar untouched). fallback_summary comment updated (degraded path keeps 9).
- [x] **Version bump** → `summary-2026-07-g`.
- [x] **Tests**: 9 new/updated (merge, phantom-drop, placeholder, non-string, case-insensitive,
      cannot-create-section, figure_trace flip, verdict N/A ×3). Full gate **1639 passed**, ruff+bandit clean.
- [x] **Eval `--runs 3` ×2** (pre- and post-review-fix prompts): regression gate **PASS, 0 warnings** both;
      financial_depth 0.9445→0.9744, redundancy 0.9115→0.9303; no re-pin.
- [x] **Adversarial review** (2 agents + Gemini clean): no blocking defects; all touch-ups landed same PR.
      Live probe: AAPL 5/5 + MSFT 3/3 rows merged ("43% of segment revenue, 41% operating margin — Higher
      net sales of iPhone and Services…"), `not_applicable` emitted correctly.

**Acknowledged tradeoff (documented in PR):** extraction *failure* on a truly multi-segment filer is
indistinguishable from by-design absence → badge reads 8/8; the snapshot's `missing` list + ops log still
record it. Matches the locked "code is the only author ⇒ absence is by design" semantics.

## Not in scope (this PR)
- Geographic/IFRS-native axes, bank segment concepts, segment eval scorer (deferred list on #616).
- T5.3 value drivers (needs an XBRL-concept extraction slice first), T5.4 forward-quote gate, T4 follow-up.
