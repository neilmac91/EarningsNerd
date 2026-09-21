# Verifier response safeguards — 21 September 2026

Strict, complete claim batches reject partial or ambiguous model replies before any early `not_stated` verdict can act. A supporting quote must occur within one supplied passage. Both production attribution flags remain false. This is deterministic boundary validation, not a prompt change or semantic acceptance.

Local code head: `61059536371e9beaeb0d740bea6b12fa540e3336`. Full committed gate: Ruff clean; Bandit no medium/high findings; **3,439 passed, 78 warnings in 136.10s**, including performance and all four isolated PostgreSQL 15 concurrency lanes. Focused discovery/verifier suite: **54 passed, 2 warnings in 6.72s**. No locked test, baseline, stamp, prompt, model, source window or deployment flag changed.

Exactly one original mutation per invariant:
- Restored permissive batch parsing (keeping passage-local quote checking): **10 failed, 8 passed, 13 deselected** in the existing parametrized batch gate. Early partial decisions, repaired JSON, invalid IDs and duplicate keys were rejected by the new gate.
- Restored concatenated-passage quote validation: **1 failed, 30 deselected** in the existing quote-provenance gate.
Both mutations were restored to committed bytes before the full green gate. An earlier mutation setup used an incorrect relative path and made no source change; its ordinary green test run is not a mutation proof.

Independent Sol review of the committed diff completed all three lenses with no blocker or should-fix. Refutation checks considered late invalid claims leaking earlier verdicts (the local map is returned only after full validation) and a quote spanning two passages being rescued (matching now tests each passage independently). The 700-token verifier cap can still produce an incomplete reply, now safely rejected; do not treat that as measured semantic accuracy.

Balance-only workflow [35657001885](https://github.com/neilmac91/EarningsNerd/actions/runs/35657001885) observed USD 73.43 at 2026-09-21T21:24:47.5669241Z before hosted measurement. Hosted checks, actual artifacts and production deployment are pending at this preparation checkpoint.
