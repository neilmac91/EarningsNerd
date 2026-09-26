# Source review units: review advisories enforced, 24 September 2026

The independent review of the [byte-custody review units](../../readiness-2026-09-21/acceptance/source-review-units.md) (#954) carried two advisories forward. The founder asked for both to be implemented. Implementation commit `924c84b`, branched from main `964c85b`.

## What changed

- **Expected packet contract.** `validate_unit_manifest` now requires `expected_packets`: `{role, sha256, byte_length}` objects, ascending by role, which must come from the frozen source contract. The declared packets must equal it exactly. A manifest that omits a packet and all of its units is rejected as `manifest omits expected packets` even when the supplied bytes match it; before this change only the key set of `packet_bytes` could catch that. Extra packets and a changed SHA-256 or length are rejected by role.
- **Context-byte limits.** Declared context is capped per unit (64 KiB) and in total over the manifest, counting repetitions (64 MiB, the raw-source limit). Both caps are computed from span offsets before any context byte is hashed, so validation hashing is bounded. Callers may pass tighter integer limits once leaf sizes are chosen, never looser ones.

The stored manifest format is unchanged at `schema_version` 1, and the golden vectors, including `manifest_sha256` `ea73eff3…`, still hold. The validation summary is a return value with its own version. It moves to version 2 with `expected_packet_contract: "exact"` and the two limits in force. Nothing else in the repository consumes it; the version-1 summary in the [#954 evidence](../e7-source-units-2026-09-23/synthetic-example-summary.json) stays as a historical record.

## Verification

[Full gate](full-gate.log) on committed `924c84b`: ruff and bandit pass, and pytest reports 3697 passed, 2 deselected (the performance marker), with zero failures, errors or skips. That is main's 3695 plus the two new gates. The four PostgreSQL lanes ran against a scratch local `postgres:15`, never production. The documented API example runs verbatim and reproduces `ea73eff3…`.

## Mutation proofs

One per new gate, both on committed `924c84b` ([receipt](mutation-proof.json), [runner](mutation-proof-runner.py.txt)), each with a fresh bytecode-cache prefix and a byte-identical restore (`dd34af39…` before and after, clean tree):

| Gate | Mutation | Mutated | Restored |
| --- | --- | --- | --- |
| `test_declared_packets_must_equal_the_expected_source_contract` | remove the `_expected_contract` call | 1 failed | 1 passed |
| `test_declared_context_is_bounded_before_it_is_hashed` | disable the per-unit context check | 1 failed | 1 passed |

## Boundaries

No readiness, protocol, executor, output or decision wiring; no E7 generation, Fable or judge call, spend, flag or migration. The member ledger and every other existing file are unchanged apart from the three planning and interface docs. The two previously denied E7 guard proofs were not touched.
