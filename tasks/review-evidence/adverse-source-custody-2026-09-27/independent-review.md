# Independent adverse integration review

Scope: read-only review of the uncommitted `codex/wave3-adverse-source-custody` diff at `5554bc87`, the two modified unit-test files, and `/private/tmp/h29-adverse-schema2-integration/{h29_integration_harness.py,bundle/receipt.json}`. No provider/network calls or test runs were made. `git diff --check` was clean.

## Findings

### [P1 should-fix] Bind the reservation to the governing protocol prompt

`backend/evals/acceptance_ai_adverse.py:142-152` verifies the bespoke reconciliation prompt hash, requested context, eligible A/B hashes, and empty candidate inputs, but it never checks `operator_reservation.protocol_prompt_sha256` against the `source_reconciliation` prompt in the protocol. It also ignores `admission_approved`. The supplied schema smoke makes the missing relation concrete: the reservation declares protocol prompt `706655d7...`, while the bundled protocol role points to placeholder prompt `063e2baf...`; validation still returns `issues: []`. Consequently the same validator would accept a coherently rehashed reservation naming a different governing prompt, or one contradicting the no-admission boundary, in a full programme bundle.

Fix by passing the frozen `source_reconciliation` role prompt hash into `validate_rows`, requiring the reservation's protocol-prompt hash to match it, and validating the no-admission field. The smoke fixture should continue to be described as schema-only unless it carries the real prompt/contract bytes.

Refutation 1: freezing both artifacts in the eventual inventory does not establish that the pre-dispatch reservation selected that governing prompt; the supplied mismatch demonstrates the missing relational check. Refutation 2: the placeholder mismatch is intentional for this smoke bundle, but the validator has no fixture-only branch, so the same omission applies when the approved 30-filing manifest is used. Finding stands; it does not invalidate the supplied bundle's limited schema-smoke purpose.

### [P2 should-fix] Reject undeclared children in the status addendum's original-artifact set

`backend/evals/acceptance_ai_adverse.py:116-140` reduces `status_addendum.original_artifacts` to a hash set and only checks that the draft, narrative, and read-log hashes are members. `inventory_rows` at lines 37-52 seals the nine top-level row artifacts but does not traverse extra records embedded in the addendum. A coherently rehashed addendum can therefore declare a fourth original artifact whose bytes are missing or mutable, while validation and the advertised child-artifact closure still pass.

Require exactly the three expected original-artifact records (with valid record shapes and the exact hash set) or explicitly inventory every declared child. The actual H29 addendum has exactly those three, so this change should preserve the real bundle.

Refutation 1: the addendum's own bytes preserve the extra record's claimed path/hash, but they do not prove that referenced artifact exists or freeze its bytes. Refutation 2: the extra artifact could be treated as irrelevant narrative, but the validator already uses `original_artifacts` as the custody binding and the inventory function promises a complete child-artifact closure. Finding stands.

### [P2 test gap] Pin valid cross-packet reattribution in the repository suite

The implementation correctly permits an adverse disposition to cite a different frozen packet from the retired issue and records a limitation (`backend/evals/acceptance_ai_adverse.py:176-185`, `backend/evals/acceptance_ai_protocol.py:395-397`). The actual H29 bundle exercises this for `H29-B-011` (`complete_submission` to `earnings_exhibit`). The unit helper, however, always copies the retired issue's role/hash, and its `wrong_source` mutation uses an unknown hash. No collected unit test proves that a valid alternate packet remains accepted or that the limitation is retained.

Add one mutation using another role/hash from `expected_sources`, retain a nonempty reason/locator, and assert no adverse-invalid issue plus the reattribution limitation. Refutation 1: the external H29 harness exercises the branch, but it is under `/private/tmp` and is not a CI gate. Refutation 2: the existing wrong-source mutation only proves rejection of an unfrozen hash; it would not catch a future equality check that wrongly forces the retired source choice. Finding stands.

## Verified behavior

- The actual bundle retains 12 A issues, 13 eligible B2 issues, 25 unchanged current dispositions, all 15 retired B issues in a separate ledger, nine adverse artifacts, and zero unresolved rows.
- Source-context exclusion closes over four distinct contexts: eligible A, eligible B2, retired B, and reconciliation. Both quality and challenge contexts are checked against that closure.
- Owner-relative context receipts are path-contained, hash-verified, and ambiguity-rejected when base-relative and owner-relative candidates differ. For legacy base-relative records with no `adverse_source_evidence`, the inventory field set, resolved path, record, and byte hash remain unchanged; the existing equality assertion covers the optional-field removal path.
- Cross-packet adverse attribution does not force the retired issue's source choice; it requires a declared frozen role/hash, nonempty reason and locator, and a valid reconciled target for supported rows.
- The integration harness is a one-accession offline schema smoke. Its protocol prompts/contracts are placeholders, its manifest is not the approved 30-filing programme manifest, and its receipt correctly retains the remaining 29-source-unit, readiness, exposure, blind-review, and final-decision holds. It cannot support programme admission.

Ratings: security good with the two binding/custody fixes above; performance clear; correctness should-fix; maintainability good; tests should-fix for the valid reattribution branch.

## Corrective-delta re-review — 2026-09-27

The three original implementation findings are closed in the reviewed bytes.

- `acceptance_ai_protocol.py:244-247,385-393` now obtains the frozen `source_reconciliation` role-prompt hash and passes it into adverse validation. `acceptance_ai_adverse.py:149-161` binds the reservation to that hash and requires `admission_approved is False`. The unit mutation loop covers a wrong actual-prompt hash, wrong protocol-prompt hash and admission set true.
- `acceptance_ai_adverse.py:117-127` now requires exactly three unique historical paths and the exact draft/narrative/read-log SHA multiset. The actual H29 status addendum satisfies that rule.
- `test_acceptance_ai_protocol.py:218-228` now reattributes one retired issue from `primary` to the other frozen `index` packet, retains a source locator, and asserts both acceptance and the reattribution limitation.

The refreshed integration bundle contains the actual retained bytes for all five source-review prompts. Its reconciliation prompt hash `706655d79...` equals the reservation's `protocol_prompt_sha256`. Contracts remain explicitly marked integration-only with dispatch disabled; the receipt and operator document accurately retain the one-accession/non-admission/full-programme holds.

### Remaining [P2 rules/tests should-fix] Add the mutation proof for the exact-three original-artifact gate

The new exact-three/multiset rejection at `backend/evals/acceptance_ai_adverse.py:117-127` has no corresponding negative mutation in either modified unit test. `test_acceptance_ai_protocol.py` constructs the valid three-item addendum at lines 128-132, but the mutation block at lines 250-279 changes only disposition and reservation records. This leaves the newly introduced custody gate without the mutation proof required by `AGENTS.md` sections 4 and 5.

Add one mutation that appends a fourth `{path, sha256}` record (or duplicates one historical record), rehashes the addendum reference, and asserts `ai_adverse_source_invalid`. Refutation 1: the real H29 bundle proves the positive three-item case only; it cannot prove rejection of an extra unsealed child. Refutation 2: the coherent inventory-rewrite test mutates the retired prompt, not `status_addendum.original_artifacts`, so it does not exercise this predicate. The test-proof finding stands; no code-correctness regression was found.

### Final evidence hashes

- Combined six-file diff SHA256: `b11ca6dc4252d06a61b29b764cbe798256549b0767847960218ef16a322acd42` (independently reproduced with the harness's tracked-plus-untracked binary-diff construction).
- Refreshed receipt SHA256: `9772a793f5562fa00ceaa9c3657525ec8230c300c2e11d66ecfb5917a121d188`.
- Refreshed inventory SHA256: `1c206a34754ea6c00e430b0363b9c41a315a963a2d7b13dff0ea64702d86c6a8`.
- `acceptance_ai_adverse.py`: `389d28b6b7473bddb403f3d4da960de88b219cd381916f861536d33d73e841d4`.
- `acceptance_ai_decision.py`: `b65a0851578a3862981c6043809d1e6ec6d1fff205aeee8a23e1acfbba3b78d5`.
- `acceptance_ai_protocol.py`: `a414ec92721776df55960367f2dc749309c0addbced94ade36f5b4585f9e4622`.
- `source-review-adverse-evidence.md`: `81159a1f10816754ffd562b05632ba9e82a8f95c4468bb75d8d5a0f6b3a75a5c`.
- `test_acceptance_ai_decision_integration.py`: `e947f2cfc21612fabcaf6b8de8dca6140c56d08bc0b332e2010fd5e30781ab55`.
- `test_acceptance_ai_protocol.py`: `0ef876221566c2b0f8f83b1d695993d355c73813f236b6586d92c39da9ce37cc`.

No tests, model/provider calls or network calls were run in this re-review. `git diff --check` remained clean.

## Root final closure — 2026-09-27

The exact-three negative case is now in the existing protocol gate; it coherently rehashes an addendum with a fourth original record. The owner-path case now also rejects conflicting sibling bytes when the root copy has the expected hash. Four deliberate predicate bypasses each fail their existing gate, with 14 tests passing after restoration. Final code1604f0ff97bbfa5af40b6fe63b9ee701fe823457 passed Ruff, Bandit and 3730 tests (40warnings) including four PostgreSQL lanes and performance. No remaining review finding.
