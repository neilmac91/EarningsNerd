# Offline source-review execution custody

This slice makes source prompts reproducible and retains the attempts dispatched through an
operator-owned journal. It is **non-admitting**: it has no provider transport, source-evidence
inventory, acceptance executor or decision call site. It cannot close E7.

`backend/evals/acceptance_source_review_prompts.py` validates frozen source bytes through the existing
unit validator, then constructs a leaf prompt from the exact template, unit identity, coverage bytes
and declared context bytes. Parent prompts contain the ordered child identities and exact retained
child artifacts. Length framing and hashes bind every part; UTF-8 bytes are preserved. Binary/image
units and invalid UTF-8 are rejected, including binary units whose particular payload happens to
decode. Source validation is reusable across leaves without copying or rehashing the entire corpus
for every leaf.

`backend/evals/acceptance_source_review_execution.py` provides these operator steps:

1. `initialize_journal`: freeze the role contract, validated unit manifest, expected packets and
   source bytes in a new directory before opening review contexts.
2. `reserve_attempt`: retain the exact rendered prompt and input manifest before dispatch. Only one
   attempt may be pending. Context IDs are unique; retries retain the same node/input/template scope
   and use a fresh context. An eligible node cannot be redrawn. Parents may use only already eligible
   children from this journal, with matching retained artifact bytes.
3. Dispatch the returned prompt through a separately reviewed provider adapter. **No adapter is
   implemented here.** The caller must not dispatch before reservation returns successfully.
4. `settle_attempt`: retain the raw artifact, receipt and terminal status, including failures,
   compaction, truncation and retirement. Eligible receipts must match the frozen contract and prompt
   and declare source-only input, no truncation/compaction and no candidate inputs. A durable
   settlement intent binds status and payload hashes before files or the database are updated;
   crash recovery accepts identical bytes only.
5. `seal_history`: seal the ordered attempt history after every reservation is terminal. The returned
   history hash must be retained independently of the graph and journal. No further attempts may be
   added. A seal written before a database commit can be recovered without changing its bytes.
6. `validate_execution_binding`: supply that independently retained expected hash, the journal, graph
   and graph inputs. Validation checks the sealed history, frozen source/contract, every retained
   attempt and settlement intent, chronological child eligibility, deterministic prompt construction,
   graph registry equality and the existing schema-1 graph validator. Omission or renumbering of an
   adverse journal attempt cannot produce a valid binding.

The source-context closure includes **all attempts in this journal**. It does not prove that a
provider had no other sessions, that recorded declarations are true, or what a model privately
attended to. Preserving an external expected history hash is an integration requirement; replacing
both a history and its alleged expected hash is not verification. A future executor must freeze the
transitive inventory before output generation and compare it again at collection and decision time.

The [graph format](source-review-graph.md) retains schema 1, its field names and limitations.
Context identity accepts the existing bare tokens and bounded absolute provider IDs such as
`/root/h29_reference_a`, without normalization. Empty/path-traversal segments, whitespace and IDs
over 128 characters are rejected. This does not retroactively certify the historical H29 attempts.
Provider-version grammar is unchanged. All semantic, issue-propagation, modality and admission
attestation flags remain false; schema-2 acceptance behavior is unchanged.

Before any real dispatch, define and measure provider input/output capacity limits, retain all
unsupported modality routes, and complete the provider delivery/receipt contract. Before admission,
also complete issue propagation, reconciliation and the
[inventory, context-exclusion and blinded-projection integration](source-review-hierarchy-integration.md).
The six-view H29 byte-render rehearsal is a delivery-size fixture, not a source brief, full submission
review, successful provider run or acceptance result.
