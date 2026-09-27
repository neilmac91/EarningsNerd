# H30 cross-role history binding

## Independent retained-history authority correction

The earlier measurements below are historical. Review of head `68e8ff1f` found that removing a
whole technical attempt and recomputing the wrapper's closure could pass: the same declaration
supplied both the history and its completeness seal. PR #970 stayed draft for this valid finding.

The correction binds the retained set independently of that wrapper. The operator created
[one canonical legacy authority](legacy-source-review-history.json) with exclusive-create
semantics, SHA-256 `836403b0b85d0a6169d6ab49aedfe99442ceccb159f9084aaa5d6b29219678c6`.
It binds all four historical origin identities and their artifact hashes, together with the two
original A2/B2 reservation, dispatch, settlement and all six child hashes;
the original A3/B3 successor reservations independently repeat each child map. The
[freeze receipt](legacy-history-freeze-receipt.json) records this retrospective migration.
The earlier [technical-only draft](legacy-source-review-history-technical-only.json) is retained
for provenance and was superseded before release after review found the analogous whole-origin
omission. No original source bytes were changed and no pre-dispatch journal history was invented.

The authority's expected digest is pinned in reviewed code outside the prerequisites and
wrapper, following the fixed E7 source-contract pattern. Locations are untrusted relative
paths under one evidence root. The same resolver must run before optional wrapper handling
in readiness, inventory and downstream source-context exclusion. Exact equality with the
retained authority is required; deleting an attempt, the whole wrapper, or its authority
location cannot select the compatibility route. The ordinary no-history route remains for
programmes and accessions with neither a registered authority nor a history wrapper.

This is completeness relative to the operator's retained legacy declaration at migration.
It does not prove provider-global history, unretained attempts, model attention, financial
correctness or programme admission. Fresh validation and review of this correction are
recorded separately below before release.

## Historical implementation and measurements

Historical implementation commit `3755d1139abbd94de79c4314849d5772ebbeb351` on main parent
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

The next exact-head review found two more mechanical omissions inside those same invariants:
adverse-source contexts were absent from the shared accession ownership map, and a technical
settlement could omit its brief or read log. Commit
`cfdfa19751a22fe1d0d1f7d6a9d3bc799ae9ecb7` reuses the existing adverse evidence reader, binds its
contexts to their accessions, and requires exactly the `draft.json`, `brief.md`, and `read-log.json`
artifact leaves. It adds no schema field or semantic classifier.

[Final actual smoke](actual-smoke-final-mechanical.json) again retains the 52/51/1 split and eight
contexts. The [final full backend gate](full-backend-gate-final-mechanical.log) passed Ruff, Bandit,
and **3,732 tests with 40 warnings in 167.86 seconds** on the implementation commit, including all
four PostgreSQL lanes and performance. Removing only the exact technical child-set predicate makes
the coherently resealed omission case fail in
[the final fault proof](fault-proof-final-technical-closure-fail.log); exact restoration passes in
[the restored log](fault-proof-final-technical-closure-restored.log). The inherited closed-stream
diagnostic remained after the successful pytest summary and zero exit.

The final exact-head review found one remaining scalar contract omission: the retained reservation
and dispatch agreed on `actual_prompt_sha256`, but the shared value was only required to be
non-empty. Commit `3755d1139abbd94de79c4314849d5772ebbeb351` requires an exact lowercase
64-hex digest before dispatch equality can inherit it. The existing history invariant coherently
reseals both retained records with the same non-digest value; removing only the syntax predicate
makes that mutation pass and therefore fails [the fault proof](fault-proof-final-digest-fail.log).
Exact restoration passes [the same gate](fault-proof-final-digest-restored.log).

[Final actual H30 smoke](actual-smoke-final-digest.json) preserves the 52/51/1 split, four origins,
two technical attempts, eight-context closure, nine manifest children and six settlement children.
The [final backend gate](full-backend-gate-final-digest.log) passed Ruff, Bandit and **3,732 tests
with 40 warnings in 169.89 seconds**, including four isolated PostgreSQL 15.15 lanes and
performance. The digest syntax and retained custody do not prove the original provider runtime.

The subsequent exact-head review found that a same-accession current context could relabel its
current eligible bytes as a retired origin. The bounded alias audit also reproduced duplicate
origin bytes under two historical identities, a shared union artifact serving as both technical
dispatch and settlement, and current eligible bytes serving as an ineligible technical child.
Commit `cc8fa102af25ed01c5bba01e7004c2a6375808b6` rejects those aliases while continuing to allow a
same-accession context to own distinct current and historical artifacts. Adverse-source artifacts
remain retired custody and are not reclassified as current eligible evidence.

[Alias-corrected actual smoke](actual-smoke-final-alias.json) preserves the exact 52/51/1 split,
four origins, two technical attempts, eight-context closure, nine manifest children and six
settlement children. The [alias-corrected backend gate](full-backend-gate-final-alias.log) passed
Ruff, Bandit and **3,732 tests with 40 warnings in 178.02 seconds**, including four isolated
PostgreSQL 15.15 lanes and performance. Removing only the current-origin alias predicate makes the
coherently resealed current-brief mutation pass and therefore fails
[the origin-alias fault proof](fault-proof-final-origin-alias-fail.log); exact restoration passes
[the same gate](fault-proof-final-origin-alias-restored.log). A second removed-guard proof records
the independent [technical-child alias](fault-proof-final-technical-child-fail.log), which is
rejected again after [exact guard restoration](fault-proof-final-technical-child-restored.log). The
inherited closed-stream diagnostic remained after pytest's successful summary and zero exit.

## Independent-authority release verification

[Local gate receipt](authority-local-gate-receipt.json) records the corrected implementation
and synthetic-fixture isolation. [Full gate](authority-full-backend-gate.log) passes **3732 tests, 40 warnings in 169.48 seconds**
with performance and four isolated PostgreSQL 15.15 lanes; Ruff passes and Bandit reports zero
medium/high findings. The first full run found one synthetic-fixture conflict; its fixture-only
correction preserves the production wrong-manifest hold. Locked contract tests are unchanged.

[Actual retained-bundle smoke](authority-actual-smoke.json) preserves 52 IDs, eight contexts and
one unresolved custody hold, and rejects all six coherent omissions with zero provider calls.
The [origin omission mutation](authority-mutation-fail.log) fails exactly at the omission-rejection
assertion; [restoration](authority-mutation-restored.log) passes. The preliminary
[technical-equality probe](authority-mutation-technical-equality-redundant-guard.log) stayed green
because the separate authority-backed closure check also rejects that omission; it is retained
as a redundant-guard probe, not a successful mutation proof.

[Independent review](independent-authority-review.md) is clear across correctness, rules/brief
and tests/gates after the four accepted findings. Publication of these receipts does not admit
E7 or promote a production prompt. For a prerequisite rooted in the operator workspace, the
required authority location is `outputs/takeover-2026-09-26/h30-independent-history/legacy-source-review-history-complete.json`
for accession `0001104659-25-086034`; the reviewed code supplies its expected digest.
