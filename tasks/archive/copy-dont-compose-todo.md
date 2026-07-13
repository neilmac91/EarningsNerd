# Copy-don't-compose evidence — citation follow-up 2 (summary-2026-07-k)

**STATUS: SHIPPED to draft PR with a FLAT verdict, per the pre-committed decision rule (stop
iterating). Three measurements: -j 0.6766 → -k rule-only 0.6793 → -k rule+example 0.6753 —
composed-evidence behavior sits at the MODEL'S FLOOR for prompt-only intervention (the
arch-stop-tuning-prose-know-the-floor lesson, now measured for evidence). Zero regression
anywhere: gates PASS 0 warnings ×2, checked stable 6.38, forward_quote 0.9487 (RIVN boundary
1/3), watch dims in-floor; the contract text + fictional example + 2 new tripwire fragments ship
as correct-and-costless. ROUTE FORWARD (recommended next slice): deterministic evidence
auto-snap — at enrichment/post-processing, snap 61–92-scoring composed evidence to the nearest
REAL filing sentence via rapidfuzz, restoring provenance in code instead of prose. Skeptic:
classes 1-5 clean, one minor pin fix (2b77c57). Tripwire silent on the new example all runs.**

## Measurement log

- -k rule-only (eval_20260713T131255Z): citation 0.6793 (106nm/62nc), checked 6.49, forward
  0.9615, gates PASS — FLAT vs -j ⇒ iteration 2 per the rule.
- -k rule+example (eval_20260713T134612Z): citation 0.6753 (96nm/69nc), checked 6.38, forward
  0.9487 (RIVN 1/3, ASML ×3), gates PASS — FLAT ⇒ SHIP + STOP (floor measured).

**Goal (task #39; the #627 residual):** after evidence-as-prose, the citation scorer's remaining
no-counterpart population is COMPOSED PROSE — the model writes a fluent sentence restating
figures ("Diluted earnings per share increased 16%." at 73.2) instead of copying a sentence that
EXISTS in the filing. Form-compliant, provenance-non-compliant, 61–86 partial_ratio. Name
composition as the violation on the evidence surfaces; the contracted answer when no real
sentence exists stays `""`.

## Design decisions (lessons applied)

1. **Quote-mechanics text stays byte-identical** (the RIVN boundary lesson from -j): the new
   sentence extends the EVIDENCE IS PROSE rule and evidence-specific sites only.
2. **Scope discipline — the critical risk of this slice:** "never compose" must bind
   `supporting_evidence` ONLY. `commentary`/`impact`/driver prose are the model's own analysis BY
   DESIGN; wording must not read as banning composition there. Every added sentence names
   supporting_evidence or sits inside the already-scoped rule/field.
3. **No concrete example carrying figures** (example-bleed class, -j decision reaffirmed): shape
   description only ("a sentence you wrote yourself that restates figures"). If the -k eval shows
   rule-only is flat, escalate to a FICTIONAL no-number example in a follow-up (measurement
   ladder).
4. **Emission-collapse watch:** fabrication framing may push evidence to `""` wholesale. The
   citation_checked counter watches; decision rule below.
5. Prompt-content change ⇒ RUNBOOK: bump `summary-2026-07-k` + ledger, eval `--runs 3`, gate
   PASS, no re-pin (pin package stays sequenced after this slice, from its final behavior).

## Pre-committed decision rule (before the eval runs)

- SHIP if: citation_fidelity materially ↑ from 0.6766 (target ≥ ~0.75) AND mean_citation_checked
  ≥ ~4.5 (vs 6.51; some drop expected — composed evidence converting to `""` is the honest trade)
  AND forward_quote_fidelity inside the established 0.92–0.96 band AND hard gates PASS.
- If citation_fidelity flat → rule-only insufficient; consider ONE iteration adding a fictional
  no-number worked example, then stop.
- If checked collapses (< ~3) → the fabrication framing over-fired; soften and re-measure once.

## Plan

- [ ] EVIDENCE IS PROSE rule += COPY-DON'T-COMPOSE sentence (exists-in-the-filing; composed
      sentence = fabricated evidence, worse than "").
- [ ] Both schema evidence fields += "never a sentence you compose yourself to restate figures".
- [ ] Preambles ×4 evidence bullet += the copy-not-compose clause (identical sentence).
- [ ] RECOVERY_SYSTEM_MESSAGE += the clause (scoped to the two sections, as -j scoped prose).
- [ ] Version `summary-2026-07-k` + ledger line.
- [ ] Rule-12 pins (phrase family "compose") on: rule, fields ×2, preambles ×4, recovery message.
- [ ] Full backend gate from backend/.
- [ ] Skeptic subagent BEFORE eval — classes: commentary/impact scope leak (the big one),
      internal contradiction, risks carve-out intact, example-bleed (no figures added), recovery
      parity, test integrity.
- [ ] Eval `--runs 3` on -k → decision rule → draft PR + subscribe + check-ins.

## Not in scope (documented)
- Arming AI_FORWARD_QUOTE_GATE: founder ratified the recommendation — stays un-armed, counter
  watching.
- Pin package (fidelity floors + citation_checked companion WARN): next, from -k's final
  behavior once fleet refresh timing is set.
- Fleet refresh for -j/-k (prod ops; refresh-stale machinery exists).
- Table-aware scorer (permanently rejected — eval↔product parity).
- Carried ledger: M&A payments, effective tax rate, ROIC, segment axes, buyback-halt probe, IFRS
  equity-holders dividend variant.
