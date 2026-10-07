# H20 partial note-input preflight

`backend/evals/acceptance_h20_note_inputs.py::preflight_h20_note_inputs` implements only the
approved structural boundary and U001 input-binding work for H20 accession
`0000014846-26-000037`. It is an offline function with no I/O, prompt rendering, journal
reservation, provider call or graph construction. Source-owner approval of boundaries is not
financial review, source acceptance, delivery evidence or capacity proof.

The keyword-only inputs are `original_contract_bytes`, `note_contract_bytes`,
`closure_contract_bytes`, their respective `expected_*_contract_sha256` values, and
`packet_bytes` (an exact role-to-immutable-bytes mapping). Each expected SHA must come from
independent retained approval/custody evidence; deriving it from the file being checked defeats
that boundary. The original JSON contract has `accession_number` and ascending `packets`, each
with exactly `role`, `sha256`, `byte_length`. Preserve the full original set; do not derive a
smaller set from the notes. The other inputs are the owner's exact note-v1 or approved note-v2
successor and U001-v1 projections. Only those two explicit implementation-status values are supported.
Those private inputs and native payloads are not repository fixtures.

The result binds both ordered sets of 15 complete notes, their exact original coverage and
native context, and the U001 origin's full 251 bytes as repeated context for every note. The
origin remains attached to its complete-submission packet even for standalone-primary notes.
Equal note hashes do not collapse the two original identities. Source structural labels and
all closure obligations remain intact. Per-note and whole-result tagged hashes cover those
records and all three external contract hashes. The result returns metadata only; original
bytes are neither returned nor logged. Existing context-byte custody ceilings include the
repeated origin and do not establish model capacity.

All review, global-partition, extraction/member-mapping, graph, runtime, capacity, dependency
closure and admission flags remain false. In particular, the note subset is not passed to the
whole-packet unit validator, remainder units are not invented, and this format cannot serve
as a schema1 graph manifest. Member34/member75's further obligations and complete child-output
dispositions remain outstanding. A future runtime binding must explicitly render and replay
the cross-packet origin, support the approved structural kind, retain original/review mapping,
and pass the separately approved full graph, source-role and capacity gates. This preflight
does not change held PR1035 or existing runtime/schema.

The synthetic test file has one guard each for externally pinned supported contracts, exact
native byte/representation custody, and non-admission/runtime isolation. Mutation evidence
belongs in the implementation handback and PR body; actual-source verification stays private
and must use opaque byte hashing/slicing without displaying payloads.

## H20 joint native input custody, version 2 hooks

`backend/evals/acceptance_h20_joint_inputs.py::validate_h20_joint_inputs` adds a separately
validated owner for exact whole-packet identity mapping and joint native context. Its keyword
inputs are the independently pinned original, review and joint contract bytes and their
`expected_*_contract_sha256` values; `original_packet_bytes`; and the existing `unit_manifest`,
`expected_packets`, `packet_bytes`. Do not derive an expected review set from a desired subset
or pass a boolean/mapping hash as proof. Both packet contracts are fully checked and the existing
whole-review-manifest validator still runs. All transforms other than exact whole-packet byte
identity are refused. Unmapped originals remain retained and visibly uncredited.

The joint contract is schema1, kind `h20_joint_native_inputs`, with the H20 accession, all three
input identities (`original_contract_sha256`, `review_contract_sha256`, `unit_manifest_sha256`),
`source_controls`, `packet_mapping` and `units`. `source_controls` binds independently retained
`handback_sha256`, `note_contract_sha256`, `u001_contract_sha256`; it asserts provenance only.
Each ordered packet mapping names `review_role`, `original_role`. Each ordered unit preserves
the manifest's `unit_id`, `structural_kind`, plus `dependency_context`: ordered exact original
spans containing `packet_role`, `start`, `end`, `sha256`, `dependency_id`. Same-packet and foreign
context receive the same overlap, own-coverage and byte-limit checks. The 64KiB per-unit and
64MiB total context ceilings include existing native context and these added spans together.

The immutable validated owner is optional `joint_inputs` to `render_leaf_prompt`,
`initialize_journal` and `validate_review_graph`. Supplying it selects prompt, graph, journal,
history and execution-validation schema2. Leaf receipts bind the tagged joint input hash;
source-unit schema1 and node kinds stay unchanged. Parent child hashing is unchanged and all
complete child bytes remain required. `render_parent_prompt` accepts the corresponding
`joint_contract_sha256`; journal rendering supplies it from the frozen owner. Journal replay
revalidates the frozen mapping, original bytes and whole review inputs. Unsupported modality
kinds are refused even when particular bytes happen to decode as UTF-8; source labels are never
converted into generic text.

This is offline custody and synthetic execution bookkeeping, not a source delivery route.
`deliver_reserved_attempt` explicitly rejects schema2 journals before a CLI/version or provider
process starts. A separately versioned span-delivery contract, exact-input/complete-output
capacity evidence and native finish proof remain prerequisites. All existing review/admission
flags stay false. Partial original3/note/U001 verification does not cover the full H20 mapping;
the larger projection/native-owner closures can exceed the retained context limit and must
fail closed. This increment neither changes the limit nor approves those larger closures.

Three synthetic guards cover independent mapping/whole-manifest validation, exact native
rendering/context limits, and versioned journal/graph replay plus refusal by the existing
delivery adapter. Their one-per-guard mutations run against committed bytes; real payloads and
their opaque verification receipts remain outside the repository.
