# E7 source review graph: context and receipt custody for one role

**Status:** internal engineering format (`schema_version` 1, kinds `e7_offline_source_review_graph` and
`e7_offline_source_role_contract`), draft for review. It is not an E7 evidence schema, has no readiness,
protocol, executor, output or decision call site, and cannot admit evidence.

`backend/evals/acceptance_source_review_graph.py` is the fourth offline-custody piece of the
[hierarchy plan](source-review-hierarchy-implementation-plan.md#1-offline-source-custody), after the
[byte-custody review units](source-review-units.md), the [member dispositions](source-review-members.md)
and the [modality inventory](source-review-modalities.md). It covers the context and receipt custody part
of the [hierarchy proposal](source-review-hierarchy-proposal.md): for one role, every review unit is bound
to exactly one leaf, the leaves, reducers and single role synthesis form a hash-linked tree, every node
ran in its own registered and eligible context, and every receipt matches a frozen role contract and the
exact bytes it names. Issue propagation, reducer dispositions and reconciliation are the next stage and
are not validated here.

## What a valid graph proves

`validate_review_graph(graph, accession_number=..., expected_packets=..., packet_bytes=..., unit_manifest=..., role_contract=..., artifacts=..., foreign_context_ids=...)`
proves the following for the caller's inputs, and nothing more:

1. **Bindings.** The unit manifest is valid for the caller's accession, frozen expected packets and bytes
   (the validator calls `validate_unit_manifest` itself). The graph is bound to that manifest's
   `manifest_sha256`, to the role contract's SHA-256 and role, and to the accession.
2. **Role contract.** The contract declares the role, the allowed node kinds (it must allow `leaf` and
   `role_synthesis`; `reducer` is optional), one `template_sha256` per allowed kind, and the provider, model
   and provider version. An unavailable immutable build is declared as `provider_version: null` with an
   explicit `exposure_limit` label, never inferred; a declared version requires `exposure_limit: null`.
3. **Complete, single-rooted tree.** Every unit in the manifest is bound to exactly one `leaf`. Reducers and
   the synthesis name ordered children as `(node_id, artifact_sha256)`, and each reference must equal that
   child's own `artifact_sha256`. Children precede their parent in `nodes`, which excludes cycles. Every
   node except the synthesis has exactly one parent, and exactly one `role_synthesis` node comes last.
   Unreachable nodes are rejected.
4. **Context custody.** The `context_registry` is the append-only attempt history: each entry is
   `{context_id, node_id, attempt, status}` with `status` one of `eligible`, `failed`, `compacted`,
   `truncated` or `retired`. Context IDs are unique, a node's attempts run 1, 2, … in registry order, and no
   registered context may appear in the caller's `foreign_context_ids` (the other roles' contexts for this
   accession). Every node runs in the context registered for it, which must be `eligible` and that node's
   latest attempt, and no context is used twice. Every eligible context is used by a node. Entries for
   nodes not in the graph, such as a retired earlier attempt, are allowed only if they are not eligible.
5. **Receipts.** Each node's receipt binds the role contract hash, the contract's template hash for the
   node's kind, the rendered prompt hash, the provider, model and version from the contract, and an
   `input_sha256`. For a leaf that is its unit's `unit_id`, which binds the accession, packet, coverage and
   context spans, labels and payload hash, so two units with identical bytes are not interchangeable. For a
   reducer or synthesis it is `children_sha256(children)` =
   `SHA-256("e7-source-review-children-v1" || 0x00 || canonical_json(children))`; the regression test
   recomputes it independently.
   The receipt must be `source_only: true`, `truncated: false` and `compaction_observed: false`, with an
   empty `candidate_inputs` list.
6. **Frozen bytes.** `artifacts` maps SHA-256 to bytes for exactly the templates, rendered prompts and node
   artifacts the graph references, and every entry must hash to its key. Extra or missing bytes are
   rejected. A node's `artifact_sha256` must be its own output: it cannot equal another node's artifact,
   any template or any rendered prompt.

Because a node must use an eligible context, a compacted, truncated or failed node and every node that
depends on it cannot validate until the node is retried in a fresh context and its dependents re-bind the
new artifact hash. The summary's `source_context_closure` lists every registered context, including the
ineligible ones, and `frozen_artifact_sha256s` lists every frozen template, prompt and artifact.

It does **not** prove that any provider ran a node, that a receipt's declarations are true, that the
review was correct, that issues were propagated, or anything about table grouping, modalities or members
(those have their own formats). Every attestation flag is `false`, and the graph never carries
`coverage_status`.

## Format

A graph has `schema_version`, `kind`, `accession_number`, `role`, `unit_manifest_sha256`,
`role_contract_sha256`, `context_registry`, `nodes`, the four attestation flags
(`semantic_review_attested`, `issue_propagation_verified`, `modality_completeness_attested`,
`admission_approved`) and the fixed `limitations` list.

Each node carries `node_id`, `kind` (`leaf`, `reducer` or `role_synthesis`), `unit_id` (a leaf's unit, else
`null`), `children`, `context_id`, `receipt` and `artifact_sha256`. A receipt carries
`role_contract_sha256`, `template_sha256`, `rendered_prompt_sha256`, `input_sha256`, `provider`, `model`,
`provider_version`, `source_only`, `truncated`, `compaction_observed` and `candidate_inputs`.

A role contract has `schema_version`, `kind`, `role`, `node_kinds` (`{kind: {"template_sha256"}}`),
`provider`, `model`, `provider_version` and `exposure_limit`. Its identity is the SHA-256 of its canonical
JSON.

Stored graphs must be exactly `canonical_json(graph)` and are loaded through `load_review_graph`. The
validator is pure and never mutates its arguments; invalid input raises `ValueError`, and nothing is
repaired, coerced or reordered. Type identity is exact.

## Limitations

The graph and summary carry exactly these strings, together with every flag `false`:

1. Receipts are recorded declarations; the validator checks them against the frozen role contract and the supplied bytes, not that a provider actually ran them.
2. Context freshness is proved only against this graph's registry and the caller-supplied context IDs of other roles, never provider-globally.
3. Leaves bind whole review units; table grouping, modality dispositions and member linkage are validated by their own formats, not here.
4. Issues, evidence fragments, reducer dispositions and reconciliation are not validated.
5. No source review, E7 coverage_status or E7 admission is attested.

Any change to these strings, the flags, the node kinds, the statuses or a key set needs a new
`schema_version`. Issue ledgers, evidence fragments, reducer dispositions, source-reconciliation leaves,
schema-3 briefs and admission remain later reviewed slices.
