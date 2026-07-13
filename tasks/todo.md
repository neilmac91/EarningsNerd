# Pin package — fidelity floors + citation_checked companion WARN (task #41)

**Goal (the staff-review ask on #626, deferred through three content PRs):** the citation-quality
gains ride floor-unprotected — the pinned baseline (eval_20260709T063234Z, -h era) records
neither fidelity dim nor the checked count, so their −0.05 WARN entries are inert, and the older
floors (redundancy ≈0.9115, delta ≈0.9701 at pin; specificity 0.9943) sit far below current
behavior. Re-pin the baseline from an authoritative run of the SHIPPED configuration (-k prompt,
snap unarmed) so every WARN binds at today's bar, and add the `mean_citation_checked` companion
WARN (the #626 RUNBOOK line's promised two-line change).

## Why now (and why it doesn't preempt the founder)

- Floors are ONE-DIRECTIONAL (RUNBOOK doctrine): they trip only on drops; arming the snap later
  RAISES citation_fidelity to ~0.86 and simply re-pins upward in that PR. Waiting protects
  nothing and leaves five merged slices' gains exposed.
- WARNs print but never fail CI (regression_gate exits 0 with warnings) — the pin adds signal,
  not blockage. Hard-gate tolerances are untouched.
- Arming + fleet refresh remain founder calls, unchanged.

## Plan

- [x] `mean_citation_checked` WARN entry in `_WARN_GATES` (decrease, 2.0 absolute ≈30% — volume
      signal, generous) + 3 rule-12 tests (collapse=WARN-not-HARD, mix-shift clean,
      unpinned-inert).
- [ ] Authoritative pin eval `--runs 3` on shipped config (running: b1ds7m1rw) — hard gates must
      PASS vs the OLD pin first.
- [ ] Re-pin `baseline_scores.json` from that report (full summary.baseline + metadata header;
      records the fidelity dims + checked count → all WARN entries bind).
- [ ] Self-check: `regression_gate --latest` vs the NEW pin = PASS, 0 warnings (tautology check).
- [ ] RUNBOOK: unpinned→pinned language on the forward-quote and citation paragraphs; document
      the forward_quote VARIANCE BAND (0.9231–0.9615 across six --runs 3 measurements; ASML
      eternal + RIVN/COST boundary flips) so a future WARN is read against it; note the checked
      companion gate now exists (fulfilling the #626 line).
- [ ] Full backend gate; commit; push; draft PR + subscribe + check-ins.

## Not in scope
- Arming AI_EVIDENCE_SNAP (founder; fleet forensics accrue via refresh regardless).
- Fleet refresh timing (founder ops).
- Quote-snap for §5; carried ledger (unchanged).
