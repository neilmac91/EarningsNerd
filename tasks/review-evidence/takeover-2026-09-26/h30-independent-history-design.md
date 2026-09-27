# H30 independent history authority design check

**Disposition: keep PR #970 draft at `68e8ff1f29a3ec844d595cfce93b72225d46dba3`.** The final review finding is valid. Existing H30 bytes can support an exact legacy-custody migration, but no existing artifact independently asserts the complete set of retained technical attempts. A new externally pinned legacy authority is required before the wrapper can claim omission resistance. It must describe retrospective custody, never pretend that the attempts were reserved through the #964 journal.

## What exists and what it proves

PR #964 (`24d1ca5c`) has the right authority boundary for new work. `acceptance_source_review_execution.py` reserves before dispatch, stores every terminal row in an operator-owned SQLite journal, seals ordered `history.json`, and requires an **externally supplied** `expected_history_sha256` at validation. The journal database must carry the same committed seal. Its stated scope is only contexts dispatched through that journal, never provider-global history. This prevents a graph and its own digest from coherently omitting an attempt.

H30 predates that journal. There is no `execution.sqlite3`, `binding.json`, `history.json`, or settlement intent under the H30 source bundle. Importing H30 into #964's normal row path would falsely imply pre-dispatch reservation and journal chronology.

The retained legacy bytes are nevertheless strong enough to bind two exact chains:

| context | reservation | dispatch | settlement |
|---|---|---|---|
| `/root/h30_source_a_retry2` | `9ad6d898…503e` | `08b1f726…0b3b` | `13f11e5a…d2c` |
| `/root/h30_source_b_retry2` | `b33e22c1…b0c5` | `b5ec64d8…00d4` | `1a76e2ff…8992` |

Each dispatch names its reservation digest. Each settlement names the same context, status `partial_ineligible`, zero issues, and exact `draft.json`, `brief.md`, and `read-log.json` hashes. The immediately following A3 and B3 reservations independently repeat those respective three-child hash maps in `retained_previous_attempt`; both maps equal the corresponding settlement maps byte-for-byte. This supports exact custody and successor continuity.

It does **not** establish exhaustive history. `generated/external-history-manifest.json` was created before these attempts and names only the three older E7 contexts. `custody-final-audit.json` inventories current A3/B3 and old financial history but omits A2/B2. The A3/B3 successor records say one prior artifact set existed but do not name its context or reservation/dispatch/settlement digests, and they cannot rule out another unretained attempt. No existing sealed file names both A2 and B2 as the complete retained legacy technical set.

## Minimal truthful integration

Reuse #964's external-hash authority pattern, not its live journal semantics.

1. Create one canonical, immutable `legacy-source-review-history.json` at an operator-owned path. Its kind must explicitly say `legacy_custody_migration`, with accession, scope, limitations, all admission/semantic flags false, and exactly two entries. Each entry contains `context_id`, role, terminal status, reservation/dispatch/settlement path and SHA-256, the exact sorted child basename/hash map, and the matching A3/B3 successor-reservation path/SHA-256. Do not add synthetic reservation IDs, attempt numbers, provider receipts, or journal timestamps.
2. Freeze it with immutable-create behavior and retain its SHA-256 outside the schema-2 prerequisite and outside `reconciliation_history`. The readiness caller must supply both authority path and expected digest, as #964's `validate_execution_binding(..., expected_history_sha256=...)` does. A digest stored only beside or inside the wrapper is another editable seal and is insufficient.
3. Add a small validator beside `acceptance_source_review_execution.py`, for example `validate_legacy_history_binding(path, expected_sha256)`. It canonical-round-trips the authority, verifies the external digest, reads and hashes every named legacy and successor artifact, checks the two control chains and child-map equality, and returns a typed set of exact attempt identities. Its result should say `complete_retained_legacy_custody_verified`, never `complete_operator_history_verified`.
4. Bind the external authority registry and expected digest in the frozen programme before wrapper validation; omitting an optional caller argument must not disable it. Authority presence selects the history route: every authority accession requires exactly one `reconciliation_history` record, and every technical-history record requires exactly one authority. Only accessions present in neither may use no-history compatibility. Load the authority before any optional-wrapper branch, seed its contexts into the shared exclusion set, and thread its validated identities through `review_evidence_inventory` into `_reconciliation_history_inventory`. Compare the wrapper-derived technical identity set exactly to the authority set. Exclusion alone is insufficient: preserve every chain/child binding and the current alias, accession and zero-issue checks.

The identity compared across the boundary should be the tuple `(accession, context_id, role, status, reservation_sha256, dispatch_sha256, settlement_sha256, sorted child basename/hash pairs)`. The successor witness is validation evidence, not another attempt identity. The authority limitations must state that it attests the operator's retained H30 custody set as of migration, not provider-global history, private model attention, financial correctness, or programme admission.

## Required proof

The strongest counterexample must remove A2 or B2 from `technical_attempts`, recompute `source_context_closure_sha256`, and coherently reseal every wrapper-derived inventory hash. Validation must still fail solely because the derived identity set differs from the externally pinned authority set. A second mutation should remove the same entry from both wrapper and authority and recompute the authority digest; it must fail against the unchanged external expected digest. Substituting a new context while reusing the same three child hashes must fail the exact identity comparison. Deleting the entire `reconciliation_history` key must fail against the still-present external authority, with its contexts remaining excluded; deleting both wrapper and supplied authority must fail against the frozen programme registry/digest. Backward compatibility applies only when neither exists. These are controls within the same complete-history invariant, not separate acceptance programmes.

If no operator-owned external digest can be retained and supplied independently, there is no truthful closure with current evidence. Keep #970 on hold rather than treating `custody-final-audit.json`, the pre-attempt external-history manifest, or a newly co-edited wrapper seal as independent completeness authority.
