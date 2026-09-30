# Independent review — E7 source capacity preflight

**Status:** superseded historical review; do not treat as a clean review of the corrected implementation.  
**Reviewed commit:** `b73492dddf4224bafa96e174e66ff72f59e5f1e9`  
**Scope:** `backend/evals/acceptance_source_capacity.py` and `backend/tests/unit/test_acceptance_source_capacity.py` only  
**Original disposition:** no actionable finding. A later root refutation invalidated that disposition: for `</><!--x-->`, `HTMLParser` consumes the leading malformed `</>` without a callback. The b734 cursor remains at byte 0 and records the comment as `0:11`, while the source-view parser locates it at byte 3 and rejects the uncovered prefix. Independent finite probes subsequently found other accepted mismatches. The corrective implementation must compare each callback's `getpos()` with an incrementally maintained expected line/column before recording its raw span.

## Correctness review

The implementation measures the same raw parser-event unit governed by `acceptance_source_view.py` without building its projection or allocating a byte offset for every decoded character.

- `_read_verified_source` reads in bounded chunks, enforces the 64 MiB ceiling while reading, and compares both expected bytes and SHA-256 before UTF-8 decoding or constructing the parser. The returned `bytearray` is the same verified buffer parsed afterward, avoiding a reopen race between identity verification and measurement.
- `_CapacityParser` calls `HTMLParser(convert_charrefs=False)` with one full decoded input followed by `close()`. This preserves the current source-view callback boundaries; fixed-size `feed()` calls would split ordinary data callbacks and could understate the maximum.
- The monotonic byte cursor is sound for this purpose. Start tags, data, and named/numeric references must exactly match the next raw bytes. End tags, comments, declarations/DOCTYPE, and processing instructions use the same raw delimiter rules as the source-view parser. Self-closing tags delegate to the same start-tag behavior. Unknown declarations fail closed. Every accepted callback advances exactly once, and final `cursor == len(raw)` rejects gaps or trailing bytes.
- Event size uses raw UTF-8 bytes. The strict `>` comparison accepts exactly 2 MiB and rejects larger events. The maximum retains the first event on equal size, matching Python's `max(events, key=...)` behavior used by the invariant.
- The audit retains only counts and one maximum event record. It explicitly declines structural-grammar, semantic, admission, projection-memory, model-context, hierarchy, and modality claims.
- Output creation uses exclusive mode after preflight. A concurrent creator is preserved and converted to the documented fail-closed error rather than overwritten.

## Invariant adequacy

The single invariant is compact but meaningful. Its representative input includes UTF-8 data, start/end and self-closing tags, ordinary data, script/style data, a comment, DOCTYPE, a named entity, numeric character reference, quoted `>` in an attribute, and a processing instruction. It compares event count, kind counts, and the exact winning event identity/span/hash with a real `project_html` projection. It also proves identity failure occurs before tokenization, exclusive-output race preservation, exact-limit acceptance, ASCII and multibyte overflow rejection, and source-limit failure.

The fixture does not separately assert semicolonless-reference or unknown-declaration failure, nor force every callback kind to become the maximum. Those are test-coverage limits rather than correctness findings: the implementation directly mirrors the existing fail-closed reference reconstruction and routes every callback through the same size helper. The artifact does not establish behavior under a different Python `HTMLParser` implementation; that remains a comparability limit rather than a defect in this bounded preflight.

## Validation provenance

I performed a read-only review of the committed objects and did not run tests or modify the worktree. The author reported the focused invariant passing with Ruff clean. The root coordinator separately reported an event-limit mutation failing the invariant and exact restoration passing. Full-gate and real-source pilot results were outside this review and remain separate evidence.
