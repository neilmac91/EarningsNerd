# H30 cross-role history binding

Implementation commit `be913d718ee01c95fc7fb2a6a9e6239cae4fba57` on main parent
`e39b475e13a0599d037303aacc75a82d51b053b8` adds an optional, generic
`ai_assisted.reconciliation_history` wrapper. Omitting the wrapper leaves the existing evidence
inventory unchanged.

The wrapper binds the current reconciliation, retained raw draft, all manifest children, exact
origin artifacts and derived history identities, and incomplete technical-attempt custody. Every
declared source-exposed context enters the existing downstream context-exclusion gate. The ledger
cannot omit a byte-derived issue/disagreement identity, move an identity to another origin, or move
an unresolved hold to another row. A technical no-history attempt must bind an empty draft and exact
zero issue count.

## Actual H30 smoke

[Actual smoke](actual-smoke.json) validates the frozen H30 artifacts without rewriting them:

- 52 exact history identities: 51 filing-source rows and one unresolved row under the retained
  custodian classification;
- four historical origins, two incomplete technical attempts, all eight known source contexts,
  nine manifest children and six settlement children;
- zero provider calls and no programme admission.

Structural validation preserves the frozen unresolved identity and status. It does not prove the
financial-versus-runtime semantic classification; H30's classification came from the separate
retained reconciliation/custody review. Histories with unresolved financial disputes require a
separate supported reconciliation path.

The raw wrapper and all local receipts remain outside Git at
`outputs/takeover-2026-09-26/h30-history-binding/` in the operator workspace. The exact raw wrapper
SHA-256 is `5e228c7a7fb6ceffd235c1bb825daa418129ca2451daf4df76c1f6ec8672db20`.

## Verification

[Full backend gate](full-backend-gate.log) on the implementation commit passed Ruff, Bandit and
**3,732 tests with 40 warnings in 158.13 seconds**, including all four isolated PostgreSQL 15.15
lanes and the performance suite. The inherited closed-stream logging diagnostic appeared only after
pytest's successful summary and did not change the zero exit status.

[Fault proof](fault-proof-fail.log) removes only the identity-to-origin predicate. The existing
history invariant then fails on the coherent two-origin swap. Exact restoration passes the same
gate in [the restored log](fault-proof-restored.log). The final
[independent review](independent-review.md) records the refuted counterexamples and clears the
bounded implementation at the measured commit.

This change makes no provider call, financial finding, production flag, baseline, migration, or
admission decision. Release and production verification remain separate.

## Exact-head hosted-review corrections

The first hosted exact-head Codex review of PR #970 found two coherent declaration gaps. A history
origin could borrow a current context owned by another accession, and a manifest could omit one of
the three canonical count keys. Commit `2f3fbdee5128c3bf997541d6039062d869283e76` binds every current
source/reconciliation context to its accession before accepting historical origins or technical
attempts, and requires all three canonical counts before comparing their derived values. The
same-accession A3 historical/current context remains valid.

[Corrected actual smoke](actual-smoke-hosted-fixes.json) retains the exact 52/51/1 disposition split
and all eight source contexts. The [corrected full backend gate](full-backend-gate-hosted-fixes.log)
passed Ruff, Bandit and **3,732 tests with 40 warnings in 164.31 seconds** on that commit, including
all four PostgreSQL lanes and performance. The inherited closed-stream diagnostic again occurred
after the successful pytest summary. Removing only the origin ownership predicate makes the
coherent cross-accession mutation fail in
[the new fault proof](fault-proof-hosted-context-owner-fail.log); exact restoration passes in
[the restored log](fault-proof-hosted-context-owner-restored.log).
