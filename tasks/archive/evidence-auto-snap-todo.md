# Evidence auto-snap — deterministic provenance repair (task #40)

**STATUS: SHIPPED to draft PR. The naive draft (default-ON, mutate-always) was REFUTED by the
skeptic with executed evidence (false-Verified wrong-fact snaps ×4; fragment replacement at 97.2;
recovery rewrite path; forensics-destroying audit; 0.5–1.1s event-loop block) → re-postured to
measure-always/act-when-armed with the full guard bundle (length-ratio, digit-density,
recovery-skip, threadpool, original+candidate forensics, F1 pinned as characterization).
AI_EVIDENCE_SNAP ships DEFAULT OFF. Armed-ceiling eval (env-armed --runs 3,
eval_20260713T180306Z): gate PASS 0 warnings; **citation_fidelity 0.6753 → 0.8594 (violations
−56%, 165 → 73)**; checked stable 6.49; hard dims at ceiling; watch dims held; forward_quote
0.9359 = untouched-surface boundary variance (ASML eternal + RIVN/COST 1/3 flips). Arming =
founder decision: the eval evidence + the always-on fleet would_snap forensics (original +
candidate per decision) are the inputs. Gate 1774 passed.**

**Goal (the measured route past the prompt floor, #631's recommendation):** -j/-k pinned composed
`supporting_evidence` at the model's prompt-tuning floor (citation_fidelity flat ~0.68 across the
rule → rule+example ladder; residual violations score 61–92 = light distortions of a REAL nearby
sentence). Close the gap in code: at generation time, evidence on the two verbatim-contracted
surfaces that does not verify exactly is SNAPPED to the best-matching real sentence from the same
excerpt the model generated from. Output is guaranteed-authentic filing text → read-time exact
verification (T4 Verified badge + `#:~:text=` deep link), exports, and the eval's
citation_fidelity all improve with zero read latency and zero prompt change.

## Load-bearing facts (code-read)

1. **Read-time enrichment is exact-only BY DESIGN** (provenance_service.build_evidence docstring:
   per-GET fuzzy would add seconds over multi-MB text; "a scale-tolerant (rapidfuzz) upgrade
   belongs on a per-section-scoped follow-up" — this slice is that follow-up, moved to WRITE
   time). Unverified evidence at read: excerpt nulled, no badge, section-level link.
2. **The wiring site exists**: `gate_forward_quotes(sections_info, filing_excerpt or "", …)` at
   openai_service.py:790 — after risks normalization, BEFORE coverage snapshot + render; audit
   attached to raw_summary_payload (:879); pipeline counter reads it (summary_pipeline.py:814).
   The snap runs immediately after, same object, same EXCERPT-ONLY grounding (the T5.4
   blocking-finding rule — never raw filing_text).
3. rapidfuzz already a direct dependency (gate imports it); `normalize_for_match` +
   `extract_quoted_span` + `_MIN_VERIFIABLE_LEN` are the shared verbatim vocabulary.
4. Fleet: every stored row is ALREADY version-stale vs -k → the pending fleet refresh regenerates
   through the snap; NO version bump needed (no prompt text changes; the stamp's operational role
   is regenerate-needed marking, already pending).

## Design decisions

1. **Repair-only, never destructive**: below the relevance floor the original text stays (read
   suppression already covers honesty; forensics preserved). No drop path → no arming decision;
   `AI_EVIDENCE_SNAP` ships DEFAULT ON as a kill switch (unlike the quote gate, whose armed mode
   DROPS content — different risk class: snap output is always a real span, relevance-gated).
2. **Relevance floor**: `token_set_ratio ≥ EVIDENCE_SNAP_MIN_SCORE` (default 85.0) on normalized
   text — subset-scoring is the DESIRED behavior for the composed class (model summarizes a real
   sentence) — PLUS the **figure guard**: evidence containing digit groups only snaps to a
   sentence sharing ≥1 digit group (pins the candidate to the same fact; blocks
   function-word-driven cross-metric matches).
3. **Scope**: results_that_matter.table[].supporting_evidence + notable_footnotes[].
   supporting_evidence ONLY. Risks excluded (citation-legal contract — citations are not spans).
   §5 quotes excluded (programmatically altering an ATTRIBUTED management statement is a separate
   founder decision — documented follow-up; quote near-misses RIVN 97.3 / ASML 98.5 would be
   snappable by the same mechanism).
4. **Snapped span returned in ORIGINAL source casing/typography** — must verify by exact search
   downstream; the round-trip property (snapped ⇒ verify_excerpt_in_text passes) is the core
   invariant, pinned by test.
5. Audit `raw_summary["evidence_snap_audit"] = {checked, exact, snapped:[{surface,label,score}],
   left:[{surface,score}], min_score}` + greppable `evidence_snap` pipeline counter (T5.4
   conventions).
6. RUNBOOK applies (new default-on AI flag): eval `--runs 3` + regression gate MUST PASS; NO
   re-pin. Success: citation_fidelity 0.6753 → target ≥0.80; near-miss class should mostly
   convert; checked unchanged (snap never empties); forward_quote unchanged (surface untouched);
   watch dims hold.

## Plan

- [ ] `app/services/ai/evidence_snap.py` — pure leaf (settings-free): `_sentences`,
      `_digit_groups`, `snap_value`, `snap_evidence` (audit).
- [ ] Config: `AI_EVIDENCE_SNAP=True`, `EVIDENCE_SNAP_MIN_SCORE=85.0` + docs/CONFIGURATION.md.
- [ ] Wire in openai_service after the quote gate (same excerpt grounding, flag-gated) + attach
      audit; pipeline counter next to forward_quote_unverified.
- [ ] Rule-12 tests: `test_evidence_snap.py` (~14: exact/near-miss/composed/figure-guard/floor/
      short/empty/no-source/scope/casing/round-trip-verify/audit/tolerance) + wiring pin.
- [ ] Full backend gate; skeptic (classes: round-trip invariant, wrong-sentence relevance risk,
      scope leak, excerpt-grounding, non-destruction, perf on 320k excerpts, flag posture).
- [ ] Eval `--runs 3` → gate PASS + readout vs -k final (0.6753/checked 6.38/forward 0.9487).
- [ ] Draft PR + subscribe + check-ins.

## Not in scope (documented)
- Quote-snap for §5 (attributed-statement alteration — founder decision; would fix RIVN/ASML).
- Read-time snap for already-stored rows (fleet refresh covers them; read stays exact-only).
- Pin package + fleet refresh timing (unchanged, founder).
- Carried ledger (unchanged).
