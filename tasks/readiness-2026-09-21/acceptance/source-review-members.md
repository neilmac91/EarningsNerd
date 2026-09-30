# E7 source member ledger: explicit member dispositions

**Status:** internal engineering format (`schema_version` 1 or 2, kind `e7_offline_source_member_ledger`),
draft for review. It is not an E7 evidence schema, has no readiness, protocol, executor, output or
decision call site, and cannot admit evidence.

`backend/evals/acceptance_source_members.py` is the second offline-custody piece of the
[hierarchy plan](source-review-hierarchy-implementation-plan.md#1-offline-source-custody), after the
[byte-custody review units](source-review-units.md). It gives every member of one complete
submission exactly one explicit, hash-bound disposition. Every member stays visible. Members
that are unresolved or only declared as packaging are listed in the summary and hold completion,
so no exhibit, graphic, archive or structured file can drop out of review scope unnoticed.

## What a valid ledger proves

`validate_member_ledger(ledger, accession_number=..., submission=..., document_map=..., unit_manifests=[...], authoritative_attachment_bytes=None, filing_cik=None)`
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
     bytes. Schema 2 also permits `authoritative_attachment` as described below. No two members may
     claim the same manifest packet.
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
`acceptance_source_units.validate_unit_manifest`, whose required `expected_packets` must come
from the frozen source contract, never from the manifest.

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

## Schema 2: current authoritative attachment supplements

Schema 1 and all of its existing recorded bytes remain valid. Schema 2 adds the exact top-level
key `authoritative_supplements` and the two additional limitations below. It does not change the
frozen submission, member identities, strict uuencoding rules or the four false attestation flags.

To build schema 2, pass a nonempty `authoritative_supplements` list, an
`authoritative_attachment_bytes` dictionary mapping each member ID to immutable body bytes, and
`filing_cik` to `build_member_ledger`. To validate it, supply the same byte dictionary and expected
CIK to `validate_member_ledger`; the recorded supplement list comes from the ledger. Schema 1
rejects these additional inputs. The CIK must match the unambiguous SEC-HEADER before the first
DOCUMENT in the frozen submission; the accession's prefix is not used as the registrant CIK.

Each supplement has exactly these keys: `member_id`, `ordinal`, `declared_filename`,
`frozen_encoded_sha256`, `requested_url`, `final_url`, `status_code`, `representation`,
`byte_length`, `sha256`, and `transport_owner_sha256`. Records must follow frozen ordinal order.
The member identity, filename and encoded-content hash are rechecked against the frozen bytes;
only `invalid_uuencode` members with `decoded: null` can receive this representation. Both URLs
must equal the canonical same-filing SEC attachment URL, status must be 200, representation must
be `httpx_identity_entity_bytes`, and body length/hash must match the supplied bytes. The recorded
transport-owner SHA is provenance, not proof that a network request or review occurred.

Every supplement must correspond to exactly one `assigned_to_review_units` disposition using
`representation: authoritative_attachment`, and its body hash must equal that unit manifest's
packet hash. Missing, extra, duplicate or unused supplements are rejected. Validate the unit
manifest against those retained authoritative bytes separately; do not substitute them for the
frozen encoded member. A filename extension does not establish content type or review relevance.

The schema-2 validation summary reports `authoritative_supplement_count` and retains the extended
limitations. It can establish the linkage to current authoritative bytes, not that those bytes
were served unchanged when the original submission was frozen. Resolving six attachment bindings
does not resolve other members or establish whole-accession review or E7 admission.

## Limitations

1. Member enumeration follows the existing document map's SGML parse; only the mapped byte spans are re-verified here.
2. A member assigned to review units names a unit-manifest packet with its exact bytes; review of that packet is not attested.
3. Declared non-content packaging and every label are unverified declarations and hold completion; only exact duplicates are hash-proven.
4. Tables, inline-XBRL facts (including hidden facts) and images inside members are not inventoried or dispositioned.
5. No source review, E7 coverage_status or E7 admission is attested; unresolved members hold completion.

Schema 2 additionally records:

6. Current authoritative attachment bytes are a supplement, not a successful decode of the frozen encoded member or proof that SEC served identical bytes at freeze time.
7. The recorded transport-owner SHA-256 is provenance only; it does not establish source review, correctness, completeness or admission.

Modality inventories (expected table, fact and image IDs), the review graph, context registry,
issue ledgers and admission remain later reviewed slices.
