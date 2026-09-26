# E7 source review units: byte custody only

**Status:** internal engineering format (`schema_version` 1, kind `e7_offline_source_unit_manifest`).
It is not an E7 evidence schema. It is not wired into readiness, protocol, executor, output or
decision code, and it cannot admit evidence.

`backend/evals/acceptance_source_units.py` builds and independently validates a deterministic
manifest of review units over explicitly declared source packets. This is the first part of the
[offline custody stage](source-review-hierarchy-implementation-plan.md#1-offline-source-custody). It covers
exact packet identity, half-open byte spans, exact disjoint coverage, separately hashed repeated
context, length-framed unit payload hashes and canonical unit identities. The review graph,
member/modality obligations, issue ledgers and admission belong to later reviewed slices.

## What a valid manifest proves

A manifest that passes `validate_unit_manifest` proves the following for the bytes and accession
the caller supplied, and nothing beyond them:

1. Each declared packet's actual bytes have exactly the declared length and SHA-256. The declared
   accession and role are bound into every packet and unit identity, and the manifest declares the
   accession the caller expected.
2. The declared packets are exactly the caller's expected packets (role, SHA-256 and length), so a
   manifest cannot omit, add or change a packet. The supplied bytes cover exactly that set, and
   every unit refers to one declared packet. The reference rules below define what counts as a
   missing, extra, duplicate or foreign reference.
3. For each declared packet, the union of all coverage spans is exactly `[0, byte_length)`, with no
   gap, overlap or duplicated byte. The validator walks the union; an equal total length is not enough.
4. Every span hash, unit payload hash, packet ID and unit ID recomputes from those bytes and the
   declared labels. Context spans are hashed separately and never count as coverage.
5. Declared context stays within the per-unit and total context-byte limits, which are checked on
   span offsets before any context byte is hashed.

It does **not** prove that the declared accession, role, `structural_kind` or `registrant_scope`
is true. It does not show that the declared packets are every source in the filing, that any
split is a safe text or table boundary, or that anything was reviewed. Nor does it show that
tables, hidden inline-XBRL facts, images, encoded archives or decoded members were accounted
for; byte coverage cannot certify those obligations. The format never sets E7
`coverage_status: complete` and leaves evidence schema 2, protocol schema 3 and every existing
validator unchanged.

## API

```python
import hashlib
import json

from evals.acceptance_source_units import build_unit_manifest, load_unit_manifest, validate_unit_manifest

raw = b"abXcde"
manifest = build_unit_manifest(
    accession_number="0000000000-26-000001",
    packets=[{"role": "primary", "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": 6}],
    packet_bytes={"primary": raw},
    units=[
        {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
         "coverage_spans": [{"start": 0, "end": 2}, {"start": 3, "end": 4}], "context_spans": []},
        {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
         "coverage_spans": [{"start": 2, "end": 3}, {"start": 4, "end": 6}],
         "context_spans": [{"start": 0, "end": 2}]},
    ],
)
contract = [{"role": "primary", "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": 6}]  # frozen source contract
summary = validate_unit_manifest(manifest, accession_number="0000000000-26-000001",
                                 expected_packets=contract, packet_bytes={"primary": raw})
stored = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii")  # canonical_json
assert validate_unit_manifest(load_unit_manifest(stored), accession_number="0000000000-26-000001",
                              expected_packets=contract, packet_bytes={"primary": raw}) == summary
```

Both functions are pure. They do no file, network or clock access and never mutate their
arguments. Invalid input raises `ValueError`; nothing is repaired, coerced, sorted or merged.

The builder records packets and units in the order declared, then runs the same validator over
its own output, with its own `packets` as the expected contract, so it cannot emit a manifest
that the validator rejects. That self-check is not trust: a consumer must call the validator
with its own expected accession, its own expected packets and its own bytes.

**Expected packets.** `expected_packets` is required. It is a list of `{"role", "sha256",
"byte_length"}` objects in ascending role order, validated by the same rules as builder packet
input, and it must come from the frozen source contract for that accession, never from
`manifest["declared_packets"]`. The declared packets must equal it exactly. A manifest that
silently omits a packet and all of its units is rejected as `manifest omits expected packets`,
even when the supplied bytes match the manifest. An extra packet is rejected as outside the
expected contract, and a packet whose SHA-256 or length differs is rejected by role. The
`packet_bytes` key set must then equal the same roles.

**Context-byte limits.** Declared context is hashed separately for every unit that repeats it, so
without a bound validation cost grows with total declared context bytes, not with source size. The
validator therefore enforces two ceilings, computed from span offsets before any context byte is
hashed:

| Limit | Default and ceiling |
| --- | --- |
| `max_unit_context_bytes`: summed context span lengths of one unit | 65,536 bytes (64 KiB) |
| `max_total_context_bytes`: summed context span lengths over the manifest, counting each repetition | 67,108,864 bytes (64 MiB, the raw-source limit) |

A caller may pass tighter integer limits, for example once leaf sizes are chosen. It may not pass
looser ones, and `bool` or non-integer values are rejected. The builder applies the default
ceilings. Together the ceilings bound validation hashing to a fixed number of passes over the declared
packet bytes plus at most 64 MiB of context. The limits are validation policy, not part of the stored manifest, so tightening
them can reject a manifest that an earlier limit accepted.

`load_unit_manifest(raw)` parses stored bytes and accepts them only if they are exactly
`canonical_json(manifest)` (see below). Stored manifests **must** be written in that form, which
deliberately differs from the indented `json.dumps(..., indent=2) + "\n"` used by the existing
acceptance writers. Consumers **must** load stored bytes through it before validating. The
round trip rejects duplicate JSON keys (a file that hashes one claim while parsing another),
indentation, key-order, exponent and `-0` spellings, so the file hash, the stored bytes and
`manifest_sha256` remain one identity. A decimal such as `6.0` survives the round trip and is then
rejected by the validator's exact-`int` rule. Loading proves nothing about the source bytes; it only
precedes `validate_unit_manifest`.

## Declarations

Type identity is exact, including every object key and `packet_bytes` key; subclasses are rejected.

| Value | Rule |
| --- | --- |
| Objects / lists | `type(v) is dict` / `type(v) is list`, with exactly the keys listed below. A missing or extra key at any depth is rejected. |
| Integers (`schema_version`, `byte_length`, `start`, `end`) | `type(v) is int`, so `True` and `1.0` are rejected. |
| Attestation flags | `v is False`. |
| Packet bytes | `type(v) is bytes`, immutable. `bytearray`, `memoryview` and `bytes` subclasses are rejected. |
| `accession_number` | `re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", v)` on a `str`. `fullmatch` rejects trailing newlines, and the explicit `[0-9]` (no `\d`) rejects non-ASCII digits. |
| `role`, `structural_kind`, `registrant_scope` | `re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,127}", v)`. These are supplied declarations: the library checks only their form and binds them into identities. |
| Hashes and IDs | `re.fullmatch(r"[0-9a-f]{64}", v)`. |

Builder input objects:

- packet: `{"role", "sha256", "byte_length"}`
- unit: `{"packet_role", "structural_kind", "registrant_scope", "coverage_spans", "context_spans"}`
- span: `{"start", "end"}`

Manifest objects:

- top level: `{"schema_version", "kind", "accession_number", "declared_packets", "units",
  "semantic_review_attested", "semantic_labels_verified", "source_set_completeness_attested",
  "member_modality_completeness_attested", "admission_approved", "limitations"}`
- packet: `{"packet_id", "role", "sha256", "byte_length"}`
- unit: `{"unit_id", "packet_id", "structural_kind", "registrant_scope", "coverage_spans",
  "context_spans", "unit_sha256"}`
- span: `{"start", "end", "sha256"}`

**Field names.** Spans carry `{start, end, sha256}` and deliberately omit the derived `bytes`
length used by `acceptance_source_view` and `acceptance_document_map` spans. Packets use
`byte_length`, following the hierarchy proposal, rather than the source contract's `bytes`.
Adapters from those owners must project `{start, end}` explicitly. Later fragment and ledger
spans should reuse `{start, end, sha256}`.

**Spans.** Offsets are zero-based byte offsets with exclusive ends, never character indexes, and
must satisfy `0 <= start < end <= byte_length`. A unit needs at least one coverage span.
`coverage_spans` must be strictly increasing with at least one byte between spans. Adjacent
coverage must be declared as one span, so each covered byte set has exactly one representation
within a unit. `context_spans` may be empty. Context spans must be ascending and non-overlapping,
and they may touch: a caption followed directly by a header row remains two separately hashed
items. They must not overlap the unit's own coverage and may refer only to the unit's packet.
Several units may repeat the same context span.

**Order.** `packets` / `declared_packets` are in strictly ascending byte-wise `role` order.
`units` are ordered by declared packet, then by first coverage start. The builder never sorts;
any other order raises. Because exactly one order is accepted for each declared set, the
manifest is deterministic without any reordering.

**References.**

- A *missing* reference is an expected packet the manifest does not declare, a declared role with
  no supplied bytes, or a declared packet with no coverage unit.
- An *extra* reference is a declared packet outside the expected contract, or a supplied-bytes key
  that is not a declared role.
- A *duplicate* reference is a repeated role (rejected by the ordering rule) or a repeated
  `unit_id`, which is checked explicitly.
- A *foreign* reference is a unit `packet_id` (or builder `packet_role`) that matches no packet
  the validator recomputed for this accession. A manifest that declares a different accession
  from the caller's expectation is also foreign.

Byte-identical content under two declared roles is permitted. Each role is its own packet
identity, is partitioned independently and is counted separately in the totals. Exact-duplicate
dispositions belong to the later member slice.

**Empty-packet policy.** Each declared packet needs `byte_length >= 1`, and at least one packet
must be declared. A zero-byte packet cannot be partitioned into non-empty reviewable units, and
accepting an empty partition would record an unreviewable unit as covered. Both cases are
rejected. Declare such a packet outside this format with its own explicit disposition.

## Canonical encoding

All hashes are lowercase hexadecimal SHA-256. `canonical_json(v)` is
`json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)`
encoded as ASCII, with no trailing newline. Validated values contain only restricted ASCII
strings, `int`, `bool` (the `false` flags), `list` and `dict`, so this encoding is deterministic. `u64(n)` is an unsigned
64-bit big-endian integer, and `||` is byte concatenation. Each domain tag is its ASCII bytes
followed by a single `0x00` byte.

- Span `sha256` = `SHA-256(packet[start:end])`.
- `packet_id` = `SHA-256("e7-source-unit-packet-id-v1" || 0x00 || canonical_json({"accession_number": accession_number, "byte_length": byte_length, "role": role, "sha256": sha256}))`.
- `unit_sha256` = `SHA-256("e7-source-unit-coverage-v1" || 0x00 || u64(n) || u64(len_1) || bytes_1 || … || u64(len_n) || bytes_n)`
  over the `n` ordered coverage fragments only. Offsets, context bytes and labels are excluded;
  the unit ID binds them. Each fragment carries its own length, so `("ab", "c")` and `("a", "bc")`
  hash differently, although both concatenate to `abc`.
- `unit_id` = `SHA-256("e7-source-unit-id-v1" || 0x00 || canonical_json({"accession_number": accession_number, "packet_id": packet_id, "structural_kind": structural_kind, "registrant_scope": registrant_scope, "coverage_spans": coverage_spans, "context_spans": context_spans, "unit_sha256": unit_sha256}))`.
  Both span lists keep their declared order, and each span is `{"start", "end", "sha256"}`.
- The manifest's serialized form is `canonical_json(manifest)`. The summary's `manifest_sha256`
  is the plain SHA-256 of those bytes, which is also the stored file's hash. It is the only
  manifest identity later slices may bind.

The identities exclude manifest position, other units, the attestation flags, the limitations
text and any semantic review. A caller who recomputes a consistent manifest for a different
accession or role creates a different, equally mechanical declaration. The validator rejects a
different accession only because the caller states which one it expects; it cannot tell which
declaration is true.

**Golden vectors** for the API example above, pinned in the regression test and independently
recomputed from this specification during design review:

| Value | SHA-256 |
| --- | --- |
| packet `sha256` | `535c9349dd5a5816c1d21c89aed279c46320a9693036e973ea547f0bd0f482c8` |
| `packet_id` | `8b5a7530cecb1e5ef0a5f9ab011e5238cb8a3987851d5fa568528db6a36d8a39` |
| unit 1 `unit_sha256` | `7ae7f33b1c1424603f480fa8ddd79064bb71a15e1aa2c3b1513623f3387f77a4` |
| unit 1 `unit_id` | `a4f6def0bfa75f139b4f145b01ad19b18ed202de5758fc19ed9b579bf721044a` |
| unit 2 `unit_sha256` | `b031a940ab59b3a68f207048db42605a357d1aafd08a06c1d5adc4be62502d83` |
| unit 2 `unit_id` | `e575eeaf1918dc720ecc75be88cb6a4d5fc7bffba553afbc59eb3fc2b55d2f4e` |
| `manifest_sha256` | `ea73eff3b57db48cd9f3c127e719ca389d60d5afd93f4861ea496464fc521e7b` |

The `manifest_sha256` vector covers the limitation text, the flags, every key set, the kind and
the encoding together. The regression test pins it, so changing any of them without a new
`schema_version` fails CI.

## Validation summary

```json
{
  "schema_version": 2,
  "kind": "e7_offline_source_unit_validation",
  "manifest_sha256": "<SHA-256 of canonical_json(manifest)>",
  "accession_number": "0000000000-26-000001",
  "packet_count": 1,
  "unit_count": 2,
  "declared_packet_bytes": 6,
  "coverage_bytes": 6,
  "context_span_count": 1,
  "context_span_bytes_not_counted_as_coverage": 2,
  "declared_packet_byte_partition": "exact",
  "expected_packet_contract": "exact",
  "max_unit_context_bytes": 65536,
  "max_total_context_bytes": 67108864,
  "semantic_review_attested": false,
  "semantic_labels_verified": false,
  "source_set_completeness_attested": false,
  "member_modality_completeness_attested": false,
  "admission_approved": false,
  "limitations": ["…the five strings below…"]
}
```

`context_span_bytes_not_counted_as_coverage` sums every context span's length once per unit that
declares it, so a header repeated in two units counts twice there and never in `coverage_bytes`.
`declared_packet_byte_partition: "exact"` is a mechanical statement about the declared packets
only. It is deliberately not named `coverage_status`. The summary is a return value with its own
kind; it repeats the flags and limitations so that a quoted summary keeps its disclaimers, and
it binds the validated manifest through `manifest_sha256`. It is not a stored evidence format:
changing a summary-only field changes its own `schema_version`, not the manifest's. Summary
version 2 added `expected_packet_contract` and the two context limits in force; the manifest
format and its golden vectors are unchanged at version 1. The summary in the
[#954 evidence](../../review-evidence/e7-source-units-2026-09-23/synthetic-example-summary.json)
is the version-1 summary and remains a historical record.

## Limitations

The manifest and summary carry exactly these strings. The validator requires them verbatim,
together with every flag `false`:

1. Byte custody only: the declared accession, packet roles, structural kinds and registrant scopes are unverified declarations.
2. The declared packets are not every source in the filing; other exhibits, submission members, supplements and graphics remain separate obligations.
3. A byte-valid span boundary is not a semantically safe text, table, footnote or UTF-8 character split.
4. Tables, hidden inline-XBRL facts, images, encoded archives and decoded members are neither inventoried nor dispositioned.
5. No source review, model-context custody, issue propagation, E7 coverage_status or E7 admission is attested.

Any change to these strings, the flags, a key set or the encoding needs a new `schema_version`.
Existing version-1 manifests stay valid only under the version-1 rules. This format adds no
parent/child graph, table ID, member disposition, context registry, prompt or model declaration,
issue ledger, reducer, reconciliation, blinded packet or readiness integration.

Evidence for this slice: [e7-source-units-2026-09-23](../../review-evidence/e7-source-units-2026-09-23/README.md).
