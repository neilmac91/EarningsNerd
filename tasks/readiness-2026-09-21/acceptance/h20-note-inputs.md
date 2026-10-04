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
smaller set from the notes. The other inputs are the owner's exact note-v1/U001-v1 projections.
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
and pass the separately approved full graph, source-role and capacity gates. No held PR1035
or existing runtime/schema is changed here.

The synthetic test file has one guard each for externally pinned supported contracts, exact
native byte/representation custody, and non-admission/runtime isolation. Mutation evidence
belongs in the implementation handback and PR body; actual-source verification stays private
and must use opaque byte hashing/slicing without displaying payloads.
