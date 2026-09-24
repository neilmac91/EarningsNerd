# E7 source member ledger: explicit member dispositions

**Status:** internal engineering format (`schema_version` 1, kind `e7_offline_source_member_ledger`),
draft for review. It is not an E7 evidence schema, has no readiness, protocol, executor, output or
decision call site, and cannot admit evidence.

`backend/evals/acceptance_source_members.py` is the second offline-custody piece of the
[hierarchy plan](source-review-hierarchy-implementation-plan.md#1-offline-source-custody), after the
[byte-custody review units](source-review-units.md). It gives every member of one complete
submission exactly one explicit, hash-bound disposition. Every member stays visible. Members
that are unresolved or only declared as packaging are listed in the summary and hold completion,
so no exhibit, graphic, archive or structured file can drop out of review scope unnoticed.

## What a valid ledger proves

`validate_member_ledger(ledger, accession_number=..., submission=..., document_map=..., unit_manifests=[...])`
proves, for the caller's expected accession, complete-submission bytes, document map and unit
manifests, and nothing more:

1. The document map describes exactly these submission bytes (SHA-256 and length). Every mapped
   member's payload, whitespace-trimmed payload and content spans re-hash from those bytes. Members
   are the contiguous ordinals `1..n` with unique filenames.
2. Every member has exactly one entry, in ordinal order, whose identity fields recompute exactly.
3. A uuencoded member (`begin <mode> <name>` … `end`, optionally inside EDGAR's `<PDF>…</PDF>`
   wrapper) decodes only when every data line's length character matches its exact encoded width
   and decoded byte count. Its decoded SHA-256 and length are then recorded. Anything else that
   starts a uuencode block is recorded as `invalid_uuencode` with no decoded hash. Nothing is
   padded, trimmed or repaired, and such a member cannot be assigned through a decoded hash.
4. Each disposition is well formed and its checkable linkage holds:
   - `assigned_to_review_units` names a unit manifest by `unit_manifest_sha256` (the
     `manifest_sha256` that `validate_unit_manifest` reports for it) and a packet role
     whose SHA-256 equals the member's exact `payload`, `trimmed_payload`, `content` or `decoded`
     bytes. No two members may claim the same manifest packet.
   - `exact_duplicate` names another member with byte-identical payload that is itself assigned to
     review units. This is the only hash-proven non-review disposition, and chains are rejected.
   - `declared_non_content_packaging` carries a declared `basis` label. The proposal requires
     source-proven packaging, which this slice cannot establish, so these members are listed as
     `unproven_packaging_member_ids` and hold completion like unresolved members.
   - `unresolved` carries a declared `reason` label. Unresolved members are listed in the summary
     and hold completion.

It does **not** prove that a packet was reviewed, that a packaging declaration is true, that the
document map's SGML parse is correct (only its mapped spans are re-verified), or anything about
tables, inline-XBRL facts (including hidden facts) or images inside members. Every attestation
flag is `false`, and the ledger never carries `coverage_status`.

The caller must have validated each unit manifest with its own packet bytes through
`acceptance_source_units.validate_unit_manifest`. The expected packet set must come from the
frozen source contract, never from the manifest.

## Member identity

`member_id` = `SHA-256("e7-source-member-id-v1" || 0x00 || canonical_json({"accession_number",
"submission_sha256", "ordinal", "declared_type", "declared_filename", "declared_sequence",
"payload": {"start", "end", "sha256"}}))`. It uses the same `canonical_json` as the unit manifest.
Declared type, filename and sequence are the SGML header values, required to be exact, printable
and stripped. They are declarations, not verified facts.

## Format

A ledger has `schema_version`, `kind`, `accession_number`, `submission`
(`{sha256, byte_length, member_count}`), `members`, the four attestation flags and the fixed
`limitations` list.

Each member carries `member_id`, `ordinal`, `declared_type`, `declared_filename`,
`declared_sequence`, the three `{start, end, sha256}` spans, `encoding` (`none`, `uuencode` or
`invalid_uuencode`),
`decoded` (`null` or `{sha256, byte_length}`) and `disposition`. Exact key sets apply at every
depth, and type identity is exact at every level (subclasses of `str`, `int`, `dict` or `list`
are rejected). Any change to the limitations, flags, dispositions or key sets
requires a new `schema_version`.

## Limitations

1. Member enumeration follows the existing document map's SGML parse; only the mapped byte spans are re-verified here.
2. A member assigned to review units names a unit-manifest packet with its exact bytes; review of that packet is not attested.
3. Declared non-content packaging and every label are unverified declarations and hold completion; only exact duplicates are hash-proven.
4. Tables, inline-XBRL facts (including hidden facts) and images inside members are not inventoried or dispositioned.
5. No source review, E7 coverage_status or E7 admission is attested; unresolved members hold completion.

Modality inventories (expected table, fact and image IDs), the review graph, context registry,
issue ledgers and admission remain later reviewed slices.
