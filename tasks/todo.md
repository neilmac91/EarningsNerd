# T4 follow-up — verbatim-compliance tuning + recovery parity + citation-fidelity scorer

**Goal (task #36; sequenced after the T5.4 fleet readout made it targeted):** drive the measured
§5 near-miss population (8/8 failures at rapidfuzz 97.3–99.6, zero fabrications — RIVN "to be"→
"will be", ASML one-word guidance drift, SE Item-303 boilerplate elision) toward zero with
mechanical verbatim instructions + ONE worked example (lessons/arch-edit-causal-directive-add-
example.md: rule+example moved judge 3.11→3.78 where rule-only was flat); close the recovery
re-ask parity gaps; land the permanent `citation_fidelity` eval dim for the verbatim-contracted
supporting_evidence surfaces. Prompt-content change ⇒ RUNBOOK: eval `--runs 3`, bump
`summary-2026-07-i`, hard gates hold, no re-pin unless the bar moves intentionally.

## Load-bearing facts (2-reader understand sweep)

1. **The causal directives (all live in BOTH prompt modes — schema_template/Rules are
   unconditional; preambles only when USE_STRUCTURED_OUTPUT=true, default False):**
   (a) §5 `quotes[].quote` (:318) carries the WEAKEST verbatim instruction in the prompt — bare
   "<verbatim; forward-looking or unusual statements only>", no word-for-word mechanics, no
   escape hatch — on exactly the field the gate measures; (b) "SHORT VERBATIM" (:296/:350) caps
   length with no how-to-shorten rule → invites eliding inside the span (the SE class);
   (c) "as management states it" (:295/:336) / "exactly as the filing states it" (:312) frame
   voice-preserving paraphrase as compliance (the RIVN re-tense class); (d) "Arrays must never be
   empty" has no `quotes` exception → when no copyable forward quote exists the model MUST invent
   one; (e) the recovery re-ask emits fully unconstrained `<string>` quotes under "Stay concise"
   + max_tokens=350, carries NO verbatim rule, and its snippets DROP supporting_evidence entirely
   for results_that_matter and notable_footnotes.
2. **Risks evidence is contractually looser BY DESIGN** (":328 non-empty excerpt or citation";
   Rules :404 licenses "direct quote or XBRL tag reference") — do NOT fold risks into the strict
   verbatim scorer or silently tighten its contract; T4's read-time verified/cited badge already
   handles risks honestly.
3. **Scorer feasibility:** the canonical eval payload ALREADY carries results_that_matter (as the
   raw section dict under financial_highlights, evidence intact — the strip at
   summary_sections:273-280 is web-render-only) and risk_factors; notable_footnotes is dropped by
   `_baseline_to_canonical` (runner:110-121) → thread it (eval-harness-internal, no pipeline
   contract touched). Referent MUST be excerpt-first (the T5.4 blocking-finding rule).
4. **Length-sensitivity watch (no scorer exemptions in this slice):** longer quotes could feed
   specificity (boilerplate inside quotes counts) and redundancy (quote figures count) — but the
   edits demand exact COPYING and define shortening as span-selection, not longer quotes; watch
   the dims on the -i run, don't pre-neutralize (a scorer change would muddy the before/after).
5. Version machinery: bump → every stored row version-stale → refresh-stale drain; the arming
   readout must be RE-MEASURED after the prompt change before any AI_FORWARD_QUOTE_GATE decision.

## Plan

**STATUS: shipped to draft PR. Final eval on the review-fixed prompt: gate PASS, 0 warnings —
forward_quote_fidelity 0.9038 → 0.9615, 25/26 filings perfect ×3 (RIVN recovered after the
example-bleed fix; only ASML's single 98.5 near-miss sentence remains). First citation_fidelity
readout ~0.51 / ~6.6 checked per run — the table-row-evidence discovery, follow-up documented.
Adversarial review: 5 confirmed (all actioned, incl. the REPRODUCED example-bleed), 4 refuted.
Full gate 1742 passed.**

- [ ] **schema_template**: (a) :318 quote instruction → mechanical form (character-for-character;
      never substitute/add/drop/re-tense; shorten only by choosing a shorter contiguous span;
      include a quote ONLY if copyable exactly); (b) new blanket VERBATIM COPYING rule in the
      Rules block (mode-independent home) with the ONE worked example (RIGHT: shorter contiguous
      span / WRONG: re-tensed / WRONG: elided inside the span — the two measured failure modes);
      (c) :296/:350 gain the how-to-shorten reference; (d) "Arrays must never be empty"
      exceptions += `quotes` (both rule sites + the empty-sections sentence if applicable).
- [ ] **Preambles ×4**: extend the verbatim-evidence sentence to name `forward_signals.quotes`;
      add the missing risk-evidence line to 6-K (parity nit).
- [ ] **section_recovery**: quotes/evidence qualifiers restored in snippets (forward_signals
      quote+guidance qualifiers; risks evidence qualifier; supporting_evidence [+source ref]
      restored to results_that_matter and notable_footnotes snippets); one verbatim sentence in
      the recovery system message; max_tokens 350→500 (evidence fields lengthen output; truncated
      JSON would turn recoverable sections into hard misses). Full descriptive parity for
      non-evidence qualifiers stays OUT of scope (snippet bloat vs the token cap).
- [ ] **Version**: `summary-2026-07-i` + ledger line.
- [ ] **Eval**: `score_citation_fidelity` — payload-reading over the two verbatim-contracted
      surfaces (results_that_matter.table[].supporting_evidence via financial_highlights;
      notable_footnotes[].supporting_evidence via the new canonical threading), excerpt-first
      referent, exact-normalized substring, ''-skip (contracted legal answer), <24-char skip,
      near-miss/fabrication split in `citation_violations` (ride the score, the T5.4 pattern).
      RubricScore fields; runner mean + threading; `_WARN_GATES` entry (inert until re-pin);
      RUNBOOK paragraph. Risks evidence explicitly excluded (fact 2) — documented.
- [ ] **Tests (rule 12)**: scorer suite (verbatim/typography pass, elided fails as near-miss,
      fabricated fails, '' skipped, footnote+takeaway both read, neutral paths, threading);
      recovery-snippet parity pins (evidence/quote qualifiers present; fields present);
      prompt-content pins where cheap (the VERBATIM COPYING rule exists; quotes in the
      empty-allowed exceptions).
- [ ] **Gates + measurement**: full backend gate; eval `--runs 3` on -i → hard gates hold +
      before/after: forward_quote_fidelity 0.9038 → target ↑ (the slice's success metric),
      citation_fidelity first readout; specificity/redundancy watch (fact 4). Live probes on the
      three named near-miss filers (ASML/SE/RIVN): §5 audit before vs after.
- [ ] **Adversarial review** (prompt-effect lens + eval-contract lens, skeptic-verified) → fix →
      commit → draft PR (subscribe + check-ins).

## Not in scope (documented)
- Risks-evidence contract tightening (deliberately looser; read-time badge covers it).
- Scorer-side quote exemptions for redundancy/specificity (watch first; separate decision).
- Arming AI_FORWARD_QUOTE_GATE (re-measure the near-miss population on -i first).
- Fleet refresh timing after the version bump (founder call; refresh-stale machinery exists).
- Carried ledger: M&A payments, effective tax rate, ROIC, segment axes, buyback-halt probe, IFRS
  equity-holders dividend variant.
