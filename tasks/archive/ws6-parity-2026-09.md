# Parity and the sole measured baseline — implementation archive

Archived 2026-09-05 after [PR #698](https://github.com/neilmac91/EarningsNerd/pull/698) merged and its deployment was verified.
Final local backend gate: `1961 passed`; Ruff and Bandit passed. Authoritative run 33962580838: 26 × 3 = 78 accepted, zero errors/vetoes, PASS/0 warnings. The initial two JPM G5 omissions were not pinned. The sole pin is unchanged by subsequent stages; pin validation rejects incomplete or vetoed evidence.

See the [current evidence ledger](../wave2-ledger-2026-09.md) for merge SHAs, actual CI and deployment links,
and [active handover](../handover-wave2-2026-09.md) for unmet programme conditions.
The original plan below is historical: unchecked implementation boxes record its pre-execution
state, not a request to repeat completed work. Explicit readout, broader-coverage and founder
residuals remain open in the active todo. No wave-completion claim is made.

---

## WS-6 step 1 — eval parity and one measured baseline (2026-09-05)

- [x] Audit production/eval configuration and streaming calls; explicitly pin statement-financials parity, restore JPM bank-component ground truth, and test streaming/non-streaming final-result equivalence without touching locked contracts.
- [x] Use two runs for routine CI evaluation, retain hard tolerances, and provide a bounded three-run CI measurement using the existing provider secret; preserve baseline notes and provenance.
- [x] Prove new tests by mutation and run the exact full backend gate — #698 final local 1961 passed; CI 33963437020 passed.
- [x] Observe the actual CI runner and regression logs/artifact on the complete parity candidate, investigate any regression, then make one honest full-set three-run baseline pin with preserved notes.
- [x] Record parity artifact provenance and independent review; #698 merged/deployed. Measurement #700 subsequently merged/deployed; resilience, hygiene, Copilot and judged-readout-dependent arming remain unfinished.

Authoritative evidence: [run 33962580838](https://github.com/neilmac91/EarningsNerd/actions/runs/33962580838)
measured source `f5b46ba96b3023f93554087e431937ed9daba3c4` after #697 deployed. Artifact
`9968531910`, `eval_20260905T111951Z.json`, contains 26 × 3 = 78 unique filing runs,
zero execution errors and hard vetoes; the old-baseline gate passed with zero warnings.
The sole pin records that report's actual harness (judge off), source/golden hashes and measured
statistics; citation fidelity is 0.7012. Transport diagnostics remain in retained private evidence; requested streaming alone is not proof of transport behavior.
The final pin-helper change only rejects vetoed/incomplete gate evidence before overwriting an
existing baseline. Its seven new CLI cases pass; removing result/summary checks causes four/three
real assertion failures. Generation/scorer source is unchanged from the measured commit.
Final full gate and independent review passed before #698 merged. Deployment 33964233483
reported `applied=0 skipped=34`, revision `00264-ctx` serving all traffic and healthy detailed
health. First strong-judge readout remains unavailable without its credential; this deterministic
measurement does not authorize evidence-snap.
