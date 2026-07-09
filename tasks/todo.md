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

- [ ] **xbrl_narrative.py**: `REPORTABLE SEGMENTS (XBRL)` block — label names in revenue order + "provide a
      one-line qualitative driver per listed segment in `segments`; no $ amounts; omit when none listed".
      (Labels contain no "$" → safe under the non-USD relabel.)
- [ ] **openai_service.py schema_template**: re-add `segments` as COMMENTARY-ONLY rows
      `[{"segment": "<copy a name EXACTLY as listed>", "commentary": "<one-line driver, qualitative>"}]`;
      update the eight-sections rule + ONE-HOME segment clause (figures stay deterministic).
- [ ] **markdown_render.py**: harvest `{casefold(label) → commentary}` from the popped model value
      (placeholder-filtered); per authored row, commentary = `"<det mix> — <model note>"` / either alone;
      unmatched labels dropped; model can never create rows or the section key.
- [ ] **figure_trace.py**: re-include `segments[].commentary` in `_prose_blob` (model prose again).
- [ ] **N/A badge**: snapshot gains `"not_applicable": ["segments"]` iff segments un-authored post-fallback;
      `_verdict_coverage` subtracts honored N/A (∈ tracked ∧ uncovered) from the TOTAL only. Raw snapshot
      counts stay raw (documented); the verdict applies the semantics. `fallback_summary`'s hardcoded 9 is
      the degraded path — out of scope, documented.
- [ ] **Version bump** → `summary-2026-07-g` (prompt-content change).
- [ ] **Tests (rule 12)**: commentary merged / unmatched-dropped / placeholder-ignored / deterministic-only
      fallback / no-rows-created; figure_trace flags a fabricated `$` in segment commentary + stays clean on
      the %-only machine half; verdict N/A math (authored→9, absent→8, covered-but-claimed-N/A→ignored,
      legacy snapshot→9); snapshot emits `not_applicable` correctly.
- [ ] **Gates + eval `--runs 3`** (prompt change) → HARD gates hold → no re-pin unless the bar moved.
- [ ] Adversarial review → fix → commit → push → draft PR (document: fallback-path 9, the P0-2 counter rider
      now measuring a SMALLER tail, deferred items unchanged).

## Not in scope (this PR)
- Geographic/IFRS-native axes, bank segment concepts, segment eval scorer (deferred list on #616).
- T5.3 value drivers (needs an XBRL-concept extraction slice first), T5.4 forward-quote gate, T4 follow-up.
