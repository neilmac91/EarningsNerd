# Tier 4 — Citations everywhere (full-fidelity gen→web; exports = T4.3 follow-up)

**Goal (roadmap T4.1 + T4.2 + T4.4):** every model claim traces to the filing. Verbatim management
quotes + per-claim supporting excerpts (metric Investor-Takeaway, footnotes) are verified against the
filing text and rendered as Trace-to-Source chips on the web; a citation-fidelity eval scorer measures
the verification rate (advisory-first). Founder deferred to expert recommendation → full-fidelity
gen→web; PDF/CSV citations (T4.3) documented as a follow-up.

## Load-bearing facts from the understand-phase map (7 subagents)

1. **Evidence SHAPE is dead-plumbed end-to-end.** `Block.evidence: Optional[dict]` {excerpt,
   section_ref, verified, fragment_url} (summary_sections.py:132, serialized :157) + frontend
   `RenderedBlock.evidence: BlockEvidence` (summaries-api.ts:23). NO builder sets it; NO surface renders
   it. This is the T4 hook.
2. **Verification is EXACT, not fuzzy.** `verify_excerpt_in_text` (provenance_service.py:89) = normalized
   substring, 24-char floor. **rapidfuzz is in requirements.txt but UNUSED in app code** — the roadmap's
   "≥92" is net-new. `verify_excerpt_in_text` is SHARED with copilot_service + evals/copilot_scorers →
   MUST NOT be mutated; add a NEW anchoring helper.
3. **Enrichment is read-time + version-aware, enriches ONLY risks + metrics** (enrich_raw_summary:314,
   v2 keys risks/results_that_matter :338-339). build_risk_source (:189) is the generalization template.
   Runs over the ENRICHED raw_summary → rendered_sections inherits evidence (:387). Non-mutating,
   tolerant of historical rows.
4. **The model already emits source_section_ref per section** (schema_template) but it's STRIPPED for
   risks (normalize.py rebuild) and DROPPED at render for quotes/footnotes. Forward quotes are emitted
   VERBATIM (the quote IS the excerpt) → exact-verify is perfect, no new field.
5. **Frontend: ONE surface (SummaryBlocks).** Risks (SourceTrace, special-cased from raw_summary) +
   metrics (MetricSourceLink, XBRL-value provenance) already show provenance. Use **SourceTrace** (the
   "beside" chip), NOT CitationChip (inline [n]). Investor-Takeaway commentary is PER-ROW (metric table)
   → needs a per-row field, not Block.evidence.
6. **Eval: NO summary citation scorer exists** (T3.0's citation/verbatim scorers never landed; only
   redundancy + delta) AND runner._baseline_to_canonical DROPS evidence. T4.4 must add a scorer AND make
   the harness SEE evidence. Ship advisory (WARN) first — house pattern.

## Design decisions

- **Anchoring helper `anchor_evidence(excerpt, section_ref, base_url, normalized_source)` → evidence
  dict** (new, provenance_service): (1) EXACT via `verify_excerpt_in_text` → verified + precise
  `#:~:text=` fragment from the excerpt; (2) else FUZZY `rapidfuzz.fuzz.partial_ratio_alignment`
  ≥92 over the normalized source → verified + fragment from the REAL matched source window (honest: the
  claim IS in the filing; link the actual text, not the model's paraphrase); (3) else verified=False +
  section-level link (base_url). 24-char floor preserved. Does NOT touch the shared exact verifier.
- **Prompt change (tightly scoped):** add a verbatim `supporting_evidence` excerpt field to
  **PLMetricRow** (Investor-Takeaway — founder's ask) and **FootnoteItem** only. Quotes already verbatim
  (no field). the_print/segments get SECTION-level refs (no per-claim excerpt — least-requested, most
  invasive to restructure key_takeaways). → SUMMARY_PROMPT_VERSION bump + eval --runs 3 + re-pin.
- **Risks stay on their existing web path** (SummaryBlocks special-case from raw_summary) — do NOT move
  to Block.evidence (would break the frontend risk branch). Generalize enrichment to quotes/footnotes/
  the_print/metric-takeaway only.
- **Honest labeling preserved** (rule 9 + trust-is-the-product): verified=True only when located
  (exact or ≥92); else "Cited" (section link). Filing-only (rule 2): fragment_url from this filing's
  document_url/sec_url only.
- **Citation scorer advisory-first (WARN):** `score_citation_fidelity` measures fraction of emitted
  excerpts that verify; report mean_citation_fidelity, do NOT gate yet (flip to HARD is T4.4-later).

## Plan

**STATUS: design locked; implementing backend core first.**

### T4.1 backend — evidence pipeline
- [ ] `provenance_service.py`: new `anchor_evidence(...)` (EXACT→fuzzy≥92→section-level); reuse
      build_text_fragment_url; import rapidfuzz.fuzz. Keep verify_excerpt_in_text untouched.
- [ ] `provenance_service.py::enrich_raw_summary` (v2): new passes for forward_signals.quotes (verify
      the quote), notable_footnotes (verify supporting_evidence), the_print (section-level ref),
      results_that_matter driver rows (verify PLMetricRow.supporting_evidence → per-row evidence).
      Attach evidence dicts to the section objects so render + web inherit.
- [ ] `summary_schema.py`: add `supporting_evidence: str = ""` to PLMetricRow + FootnoteItem.
- [ ] `openai_service.py` schema_template + `prompts/{10k,10q,20f,6k}-structured-agent.md`: instruct a
      VERBATIM supporting_evidence excerpt on metric takeaway rows + footnotes (quote the filing exactly
      so it verifies). `summary_versioning.py`: bump SUMMARY_PROMPT_VERSION.
- [ ] `normalize.py` / render: stop dropping source_section_ref for quotes/footnotes.
- [ ] `summary_sections.py` v2 builders: set `Block.evidence` from enriched section dicts
      (_v2_the_print, _v2_forward_signals quotes, _v2_notable_footnotes); thread per-row evidence onto
      metric_rows in _metrics_block. Do NOT render evidence into sections_to_markdown (keep GFM clean —
      the "(Evidence:" leak test).

### T4.2 frontend — Trace-to-Source everywhere
- [ ] `SummaryBlocks.tsx` BlockView: render `<SourceTrace>` from `block.evidence` on paragraph (Print),
      quote (forward quotes), table (footnotes) kinds.
- [ ] `FinancialMetricsTable.tsx`: Investor-Takeaway commentary chip (per-row commentary evidence beside
      MetricSourceLink). Add per-row fields to the metric-row types.
- [ ] `SummaryBlocks.spec.tsx`: assert evidence chips render on the block kinds + the commentary chip
      (rule 12 gate).

### T4.4 eval — citation-fidelity MEASUREMENT (readout, permanent scorer deferred)
- **Refinement:** the eval harness's `_baseline_to_canonical` (runner.py:110) drops all evidence and
  `score_summary` has no filing text — a permanent `score_citation_fidelity` needs a real harness
  refactor (thread raw sections + filing text). That's cleaner as its own follow-up. For THIS PR:
- [ ] Readout script (scratchpad): regenerate the golden filings, measure the fraction of emitted
      quote / metric-takeaway / footnote excerpts that verify against the filing text → PR body.
      (Same shape as the T3.2 FP readout; no permanent harness change.)
- [ ] Permanent `score_citation_fidelity` scorer → DEFERRED follow-up (documented in PR).

### Verify / ship
- [ ] Full backend gate (ruff+bandit+pytest, amend serializer/render pin tests) + frontend gate
      (eslint+tsc+vitest+build).
- [ ] Eval --runs 3 + verify HARD gates hold (recall/coverage/precision/gate_fail) + re-pin
      baseline_scores.json (records advisory mean_citation_fidelity + any prompt-change movement) +
      RUNBOOK sync (rule 12 / ops-repin-binds-advisory-dims lesson).
- [ ] Adversarial review workflow (correctness, contract-test compliance, honest-labeling, filing-only,
      eval-safety, DS-compliance) → fix → final gates.
- [ ] Commit + push + draft PR. Document deferred T4.3 (exports) + the per-claim-vs-section-ref fidelity
      note for the staff engineer.

## Not in scope (this PR)
- T4.3 exports (PDF footnote appendix + CSV source-ref) — follow-up (export path renders UNENRICHED;
  needs its own enrichment plumbing + appendix builder).
- Flipping the citation scorer advisory→gating (WARN-first; a later re-pin binds it).
- Moving risks off their existing special-cased web path.
- Per-claim excerpts on the_print key_takeaways (section-level ref only this PR).
