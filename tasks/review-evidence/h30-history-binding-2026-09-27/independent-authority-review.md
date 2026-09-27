# Independent retained-history authority review

The operator accepted the whole-attempt omission finding on head `68e8ff1f` and kept PR #970
draft. The correction uses a reviewed-code authority digest outside the mutable wrapper;
its scope is the retrospective operator-retained legacy set, not provider-global history.

## Findings and fresh refutations

1. **Coherently omitted technical attempt.** A wrapper and its own recomputed closure cannot
   prove the declaration is complete. The first refutation failed because both come from the
   same editable input. The second failed because omitted children never enter validation.
   The externally pinned authority fixes the exact technical identity set, including every
   control and child digest, before optional-wrapper handling.
2. **Coherently omitted same-context partial A3 origin.** Removing the fourth origin and its
   six rows leaves the current A3 context and the three older manifest origins unchanged.
   The current brief cannot witness the distinct partial artifact; the older manifest cannot
   witness an artifact created later. Both refutations failed. The final authority therefore
   also fixes all four origin context/role/status/prefix/artifact identities. Existing byte-derived
   ledger validation then requires all 52 IDs. The earlier technical-only authority is retained
   as a superseded design artifact and is not the pinned release authority.
3. **Unreviewed executing authority module.** A clean candidate checkout does not protect the
   separate executing controller. The SQLite inventory is created too late to protect first
   admission against modified controller code. Both refutations failed. The new module is now
   in `MEASUREMENT_FILES`; the existing two-tree gate covers controller and frozen-checkout drift.
4. **Successor contexts lost after current-reference replacement.** Current references happen
   to exclude A3/B3 today, but can later be superseded. A reserved successor is still retained
   source-role custody and cannot be silently offered as a blind context. Both refutations
   failed. Validated successor contexts now remain in the authority's exclusion set and wrapper
   closure, with cross-accession current-context ownership checked. Actual H30 still has eight
   distinct excluded contexts.

## Authority audit

Independent review verified the canonical external authority and public copy are byte-identical:
5,185 bytes, SHA-256 `836403b0b85d0a6169d6ab49aedfe99442ceccb159f9084aaa5d6b29219678c6`.
All four origin files, six technical controls, six children and two successor witnesses were
hashed independently. Both child maps agree with their settlement and successor reservation.
The four original artifact bodies yield 52 unique history IDs with canonical set SHA-256
`79f7ba4468d0ab2f2c8e90127a73b7e1118cd17c14ab4c75d3c83bedaf9364e1`.
No source artifact was rewritten and no provider was called for these checks.

The final correctness, rules/brief and tests/gates review and committed-state verification are
recorded with the release evidence. Structural custody validation does not establish financial
truth, resolve the retained runtime dispute, prove unseen provider activity or admit E7.

## Final fixture review

The full backend run found that the synthetic decision integration graph reused H30's accession
with invented evidence and an unrelated synthetic manifest. The production guard correctly
rejected it. Independent review accepted a test-local registry override: it neither changes the
production wrong-manifest hold nor leaks beyond pytest's restored monkeypatch scope. Rewriting
all synthetic accession labels would not add coverage. The complete repeated gate passes 3,732
tests; the real pinned-bundle smoke and protocol invariant retain production authority coverage.
