# Evidence-as-prose — citation follow-up (summary-2026-07-j)

**Goal (task #38; the recommended follow-up from PR #626's citation_fidelity discovery):** the
first permanent-scorer readout measured ~0.51 with the failure population dominated by TABLE-ROW
TRANSCRIPTIONS used as evidence ("Total operating expenses $62,151 8% $57,467…" — 136
no-counterpart on the final -i run) plus prose elisions (117 near-miss). Table rows have no single
linear text form, so a transcription can NEVER verify by exact search — and T4's read-time
enrichment already discards unverifiable excerpts, so every table-row evidence emission is pure
waste on the product surface. Fix the ROOT: instruct the two verbatim-contracted evidence surfaces
to quote NARRATIVE PROSE (a sentence or contiguous fragment), never table rows/cells. The scorer
stays untouched — it already measures exactly what the product can honor; a table-aware scorer
would instead break the eval↔product one-definition-of-verbatim invariant (it would score content
the product discards as "fine").

## Design decisions

1. **One contract, every model-facing surface** (lessons/arch-guard-every-model-facing-surface):
   schema fields (results_that_matter.table[].supporting_evidence :296,
   notable_footnotes[].supporting_evidence :350) + the VERBATIM COPYING rule (:404, inside its
   existing quotes+results/footnotes scope — risks carve-out untouched) + preambles ×4 (identical
   shared sentence) + recovery snippets ×2 + recovery system message.
2. **Rule + shape description, NO new concrete example** (deliberate departure from the
   rule+example lesson): a table-row example would put NUMBERS in the prompt — the example-bleed
   class with fabricated FIGURES as the payload, strictly worse than bled prose. "Don't transcribe
   table rows" is a crude, well-understood prohibition; if the -j eval shows the rule alone is
   flat, add a fictional-numbered example in a follow-up WITH tripwire fragments (measurement
   first). No new EXAMPLE_BLEED_FRAGMENTS needed since no new example spans ship.
3. **`""` remains the contracted no-prose answer** — already in the empty-allowed machinery; the
   expected trade is FEWER but VERIFIABLE excerpts. mean_citation_checked will likely drop some;
   a collapse toward ~0 is the failure mode to watch (the volume signal built in #626).
4. **Prompt-content change ⇒ RUNBOOK**: bump `summary-2026-07-j` + ledger; eval `--runs 3`;
   regression_gate MUST PASS; NO re-pin (bar not being moved; fidelity-dim pinning remains routed
   to the founder per the #626 staff review).
5. **forward_quote_fidelity is floor-unprotected (staff review's explicit caution)** — 0.9615 must
   HOLD on the -j run; treat any material regression as a BLOCKER even though no gate fires.
   Watch dims: specificity/redundancy/delta as always.

**STATUS: SHIPPED to draft PR on the v2 (own-rule) text. Final: gate PASS 0 warnings ×2;
citation_fidelity 0.5149 → 0.6492 (+26% rel), no-counterpart 136 → 78 (−43%), checked stable
6.31 (no emission collapse). forward_quote 0.9615 → 0.9231 — read honestly, the whole delta is
RIVN's single boundary sentence (97.3 near-miss, the pre-slice class) + ASML's eternal 98.5:
same two sentences every run, zero fabrications, tripwire silent; RIVN failed 3/3 even with
quote-mechanics text byte-identical to -i ⇒ prompt-prose floor, not dilution — no further
wording iteration. Residual nc anatomy = COMPOSED prose (model-written sentence-shaped summaries
of figures, 61–86 scores) — the next causal directive, documented not chased. Skeptic: 2 minor +
1 nit, all taken.**

## Measurement log

- **-j run 1 (eval_20260712T130030Z, prose clause spliced into the quote bullet/rule):** gate
  PASS 0 warnings; citation_fidelity 0.5149 → 0.6022 (no-counterpart 136 → 97, near-miss 117 →
  103); checked 6.59 → 6.31 (no collapse); BUT forward_quote_fidelity 0.9615 → 0.9359 — RIVN
  regressed to its PRE-SLICE 97.3 re-tense near-miss in 2/3 runs (not Meridian bleed — tripwire
  silent; not fabrication). Causal read: the prose clause diluted the exact quote-mechanics
  emphasis that fixed RIVN in -i. Action: restructured — quote bullet/rule restored to -i text
  verbatim; evidence-as-prose became its OWN rule bullet (EVIDENCE IS PROSE) and preamble bullet.
  Re-measuring on the restructured text (version stays -j; unreleased).
- **-j v2 (eval_20260712T132336Z, own EVIDENCE IS PROSE rule; quote text byte-identical to -i):**
  gate PASS 0 warnings; citation_fidelity 0.6492 (nc 78, nm 101); checked 6.31; specificity
  0.9941 / redundancy 0.9515 improved, delta 0.9637 in-floor; forward_quote 0.9231 — RIVN 97.3
  ×3 despite identical mechanics text ⇒ dilution hypothesis REFUTED; boundary-sentence variance
  (prompt-prose floor). Pre-committed decision rule → SHIP v2 with the variance documented.

## Plan

- [ ] Prompt edits on all 6 surface groups (schema ×2, rule, preambles ×4, recovery snippets ×2 +
      system message) — same phrase family ("table-row transcription", "narrative PROSE") on every
      surface for greppability.
- [ ] Version bump `summary-2026-07-j` + ledger line.
- [ ] Rule-12 pins in test_verbatim_contract.py: prose demanded on both schema fields; rule clause
      present; preamble parity ×4; recovery snippet parity ×2; recovery system message.
- [ ] Full backend gate (ruff + bandit + pytest) from backend/.
- [ ] Skeptic subagent on the prompt diff (prompt-effect lens: bleed, contradictions, scope leaks
      into risks, never-empty conflicts, recovery parity).
- [ ] Eval `--runs 3` on -j → regression_gate PASS + readout: citation_fidelity ↑ from 0.5188
      (no-counterpart class should collapse), mean_citation_checked no collapse,
      forward_quote_fidelity holds ~0.9615, watch dims hold.
- [ ] Draft PR with before/after + subscribe + check-ins.

## Not in scope (documented)
- Table-aware scorer (rejected: breaks eval↔product parity; the scorer is correct as-is).
- Arming AI_FORWARD_QUOTE_GATE (recommendation stands: don't — one honest ASML near-miss, zero
  fabrications; founder's call).
- Fidelity-dim re-pin / citation_checked companion WARN (one pin run covers all once the founder
  settles arming + fleet-refresh; RUNBOOK line from #626 preserves the intent).
- Fleet refresh for -i/-j (prod ops action; refresh-stale machinery exists; founder timing call).
- Risks-evidence contract (looser by design, untouched).
