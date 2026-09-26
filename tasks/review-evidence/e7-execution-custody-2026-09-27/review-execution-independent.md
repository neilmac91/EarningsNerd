# Independent review: source-review prompt and execution custody

## Snapshot and scope

Reviewed the finished combined filesystem snapshot in `/private/tmp/earningsnerd-takeover-20260926`: branch `codex/wave3-e7-review-execution`, HEAD `9f4713db353bac875ae22758382145d788e75153`, plus the uncommitted tranche.

| File | SHA-256 |
|---|---|
| `backend/evals/acceptance_source_review_graph.py` | `298fcd8b14e1ab08eb336ac0c004823017b45ff1c1dc5599a1d517d0c97e678e` |
| `backend/evals/acceptance_source_review_prompts.py` | `5c0ab0382d2caad8c2eeeb9f3a71d886edb240e576d95e9459b50ec717741720` |
| `backend/evals/acceptance_source_review_execution.py` | `9ceb5fc50ccd8a34b3ca3aeba46efca80c3f8c386f8dbc58cfb7694c9d8cf70f` |
| `backend/tests/unit/test_acceptance_source_review_graph.py` | `f4d96b649440a23062e3a922170315314700dbc212e20ddd54293be1f4284e9c` |
| `backend/tests/unit/test_acceptance_source_review_prompts.py` | `be8152b784b0bc5c67fbda24e6615e3fbe1d294f7ab6209faefb8834e7d9b148` |
| `backend/tests/unit/test_acceptance_source_review_execution.py` | `d5d5abc63e0ffceceefc1300504fc8fefd6c917b507427b226a97f20ee2024bc` |

I did not run tests. The execution owner reported its final focused test as `5 passed` with two inherited deprecation warnings, plus Ruff and `py_compile` green on its files. At root's direction, I made the narrow context-ID compatibility edit only in `acceptance_source_review_graph.py` and its existing test; the execution owner made the matching journal changes. Root owns review of that edit.

## Verdict

The reviewed custody tranche is clear for its stated offline, non-admitting scope after the context-identity and settlement-intent corrections. One explicit blocker remains before real source-review dispatch: measured input limits have not been chosen or enforced. No caller should dispatch through this API until that separate capacity prerequisite closes.

### 1. [P1 before dispatch] The reservation path has no model-input ceiling

`render_leaf_prompt` includes every coverage and context span in the prompt (`acceptance_source_review_prompts.py:239-280`). The source-unit validator caps context bytes but not a unit's coverage bytes. `render_parent_prompt` accepts an unbounded child list and unbounded child artifact bytes (`acceptance_source_review_prompts.py:300-345`). `_render` concatenates the template, manifest, and all parts without a byte or token ceiling (`acceptance_source_review_prompts.py:134-157`), and `reserve_attempt` returns that result as the prompt the caller may dispatch (`acceptance_source_review_execution.py:533-541`, `:633-643`). Templates are only type/hash checked (`acceptance_source_review_execution.py:349-370`, `:563-585`).

A valid manifest can therefore produce a leaf prompt as large as a whole packet, and a parent can concatenate arbitrarily large child outputs. The role/programme binding contains no maximum. Reservation can consume a fresh context for input known only after provider handling to be too large, compacted, or truncated. The journal safely preserves an adverse result, but that is not a bounded pre-dispatch check.

Recommended correction: after the H01/H02/H25 capacity work chooses values, freeze explicit byte ceilings per template, leaf prompt, parent prompt, child count, and child artifact (or a provider/model token ceiling with a deterministic tokenizer) in the role/programme contract. Compute sizes before creating the attempt directory/row and reject oversize input before reserving a context.

Refutation attempt 1: `validate_unit_manifest` caps context to 64 KiB per unit and 64 MiB total, but coverage partitions packets without a per-unit coverage maximum; those bytes are copied into the leaf prompt. This does not refute the finding.

Refutation attempt 2: non-admitting status and terminal `compacted`/`truncated` handling prevent false admission after a call, but the API explicitly returns dispatchable bytes and consumes a context before any provider limit is checked. The hierarchy plan says model-input capacity remains open. This does not refute the finding.

## Corrected during review: exact actual context identity

The initial snapshot rejected the retained `/root/h29_reference_a` and `/root/h29_reference_b` IDs because both context regexes required an alphanumeric first byte. The approved compatibility correction adds public `validate_source_context_id` (`acceptance_source_review_graph.py:93-106`) and accepts either the existing token form or an absolute slash-qualified opaque ID, with the existing 128-character overall cap. It rejects empty segments, trailing slash, `.`/`..` segments, and whitespace/newlines. Provider versions remain on the old token grammar (`acceptance_source_review_graph.py:129-135`).

The graph test now preserves exact `/root/h29_reference_a` in the registry and closure and adds malformed-path cases (`test_acceptance_source_review_graph.py:53-62`, `:173-181`). The execution path uses the shared validator at reservation and sealed-history validation (`acceptance_source_review_execution.py:546`, `:920`); its end-to-end adverse attempt preserves the exact ID through reserve, seal, graph, and binder (`test_acceptance_source_review_execution.py:105-116`, `:155-209`). No legacy evidence is rewritten or retrofitted.

## Corrected during review: crash-safe settlement and sealing

The final execution module durable-exacts a canonical settlement intent before payload files, binding the reservation, terminal status, artifact hash or null, and receipt hash (`acceptance_source_review_execution.py:332-346`, `:681-715`). Binding validation independently requires that intent to equal the sealed attempt (`:845-860`). Changed status or receipt after a simulated post-intent crash is rejected, the original settlement remains resumable, and even a coherently rewritten history, graph, database marker, and newly supplied external hash cannot reinterpret the retained adverse status (`test_acceptance_source_review_execution.py:226-245`, `:346-411`). Reservation fsyncs the attempt-directory parent, and seal retries adopt only byte-identical `history.json` bytes.

## Checks that held

- Initialization canonical-round-trips the contract, manifest, and packet declarations; copies immutable packet bytes; validates them; freezes the bytes; and later re-hashes persisted source at the final binding boundary. The active owner holds frozen records and immutable `bytes`, detached from caller mutation.
- Leaf prompts bind exact validated coverage/context slices with ordered length/hash frames. Parent prompts bind exact ordered child IDs, artifact hashes, and bytes. Both reject non-UTF-8 input and unsupported non-text leaf modalities.
- A parent reservation requires each child to be a prior terminal eligible journal node whose retained artifact bytes match exactly (`acceptance_source_review_execution.py:286-325`, `:547-554`). Eligible receipts are validated against the frozen reservation before settlement (`:260-283`, `:655-656`).
- Retry scope is stable: an eligible node cannot be redrawn; retries require the same kind, template, input hash, and render identity with a fresh context. History sequence and per-node attempt numbers must start at one without gaps.
- The graph registry must equal the ordered sealed-journal projection, so deleting or renumbering an adverse attempt fails. Parent chronology is independently reconstructed from earlier eligible attempts (`acceptance_source_review_execution.py:857-971`). Every graph node binds its terminal eligible journal attempt and exact retained receipt, prompt, and artifact.
- `validate_execution_binding` requires an externally supplied expected history SHA-256, matches it to canonical history bytes and the journal's sealed marker, and binds the graph to the frozen source and role contract.
- All semantic/admission flags remain exactly `false`. Fixed limitations say completeness covers only this journal, prompt construction does not prove model attention, issue/modality completeness is not validated, and no E7 status or admission is attested.

## Release implication

This tranche is clear to continue offline and non-admitting. Keep real dispatch held until explicit input limits are measured, frozen, and enforced. Issue propagation, prior-finding disposition, modality completion, cross-role/downstream integration, actual H29 execution, and admission remain later work.
