# Review record: source review units

Two independent multi-agent reviews ran before publication. Neither is Agent B's independent verification, which remains separate. Neither made a model-provider, Fable or judge call against E7 material.

## 1. Design critique before implementation

Three independent lenses (requirements compliance, adversarial encoding, downstream compatibility) reviewed the draft specification before any code was committed. Results:

- Requirements lens: 7 should-fix, 2 nit.
- Adversarial lens: 1 blocker, 7 should-fix, 1 nit.
- Downstream lens: 3 should-fix, 2 nit.

Many findings overlapped. All of the following were accepted:

- exact type identity for every value;
- exact key sets at every depth;
- empty-packet and empty-set rejection;
- `fullmatch` with explicit ASCII classes;
- touching (not merged) context items;
- explicit missing/extra/duplicate/foreign definitions;
- a permitted, per-role policy for byte-identical packets;
- an expected-accession argument on the validator;
- `source_set_completeness_attested`;
- a summary that carries every flag, the limitations and `manifest_sha256`;
- verbatim limitation strings with a version-freeze rule;
- normative canonical storage via `load_unit_manifest`;
- a consumer-owned `packet_bytes` key set;
- documented field-name choices.

The adversarial lens proposed rejecting identical bytes under two roles. That was declined in favour of the downstream requirement that every approved packet appear; exact-duplicate dispositions belong to the member slice.

The adversarial lens recomputed the packet, unit-payload and unit-ID golden vectors from the specification alone, without reading the code. They matched the implementation byte for byte. The downstream lens did the same for the whole-manifest `manifest_sha256`, and it also matched.

## 2. Adversarial review of committed `6a96a1c`

Four lenses (bypass hunting with executed scripts, specification conformance, test strength, scope/rules) reviewed an extracted snapshot of the committed state. They did not use the checkout and ran no mutation experiments. Each blocker or should-fix finding then received two independent refutation attempts; a finding stands only if both fail.

| Finding | Refutations | Disposition in `f6a0fb9` |
| --- | --- | --- |
| `str`-subclass dict keys could pass the exact key-set check, so a hashed serialization could carry `coverage_status` | Both failed; stands | `_object` and `_packet_bytes` require exact `str` keys; masquerading-key regressions added |
| Partition edges at byte 0 and `byte_length` were never exercised | Both failed; stands | Both edge gaps added to the central gate |
| No validator-side rejection of a reordered `declared_packets` manifest | Both failed; stands | Reversed-packet tamper added |
| Schema-version freeze rule was not machine-enforced | One refuted, one did not; does not stand | Addressed anyway by the pinned whole-manifest vector |
| Nits: doc value types omitted `bool`; round-trip prose overstated; limitation 5 said "context custody"; context-overlap case covered only an exact match; evidence link not yet present | Not verified (nits) | All accepted |

The scope lens confirmed that `523b26fe..6a96a1c` added exactly three files and that every existing file is byte-identical to the base, including the protocol, readiness, executor, output and decision modules and the locked contract tests. It found no `os.getenv`, datetime, `app` import, file or network I/O, or `sec.gov` literal. Existing allowlist gates do not scan the new module.

Rewording limitation 5 to "model-context custody" changed the whole-manifest vector to `ea73eff3b57db48cd9f3c127e719ca389d60d5afd93f4861ea496464fc521e7b`. An independent script rebuilt the example from the documented rules and the doc's verbatim limitation strings. It obtained the same value before the vector was pinned.
