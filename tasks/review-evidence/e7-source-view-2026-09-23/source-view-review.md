# Independent review: E7 offline HTML source view

## Decision

No blocker or should-fix defect remains for the bounded H29 source-only draft reviews. The frozen implementation at commit `696bf214` and source SHA-256 `75ee1827581cec1b82d934e13888ab1ce2cb2fc37bf3ffa67e10484fd0cd6d9f` may be used as a review aid for the retained H29 dossier. It does not prove semantic attention, browser-rendering equivalence, visual review, or reference-brief completeness, and the code and manifests say so explicitly.

This decision is limited to the six H29 HTML views. It does not approve the module as a general 64 MiB HTML rendering substitute or as a validator for externally supplied projection JSON.

## What the implementation establishes

- `project_html` accepts only nonempty strict UTF-8 input within the configured byte cap. Its event stream must partition every source byte in order and each event carries its exact source span and hash.
- Each data/entity/character-reference event has exactly one text unit. `verify_projection` re-decodes that unit from its raw span, checks its inclusion state, rebuilds the normalized text, and checks the normalized-text hash. The dropped-unit and coherently rewritten-unit mutation proofs fail as intended.
- Whitespace folding is explicit. Tag boundaries do not silently invent spaces: structural markers preserve paragraph/break boundaries and row arrays preserve cell boundaries while `review_text` proves that all `@TEXT` and `@ROW` payloads concatenate exactly to `compact_text`.
- Tables retain table, row, cell, rowspan, colspan, and nested-table relationships. Reader row aggregation is disabled when a row contains a nested table, image, or exclusion, so those markers remain visible. The nested-table/image fixture exercises this fallback.
- Hidden text identified through `hidden`, `aria-hidden=true`, inline `display:none`/`visibility:hidden`, and `ix:hidden` stays in the text stream and is annotated. Scripts, styles, and comments are excluded with byte locators and hashes. Unknown declarations, including CDATA-like material, fail closed. External CSS and browser rendering remain disclosed limitations.
- Image `src` and `alt` values are retained and emitted as reader markers. Other element attributes remain in `source-view.json`; the exact raw bytes stay authoritative for unsupported display modalities.
- `build_source_view` checks the expected source byte count and hash before projection, rereads and compares the whole source immediately before creating the output directory, refuses overwrite, and hashes every published artifact in the manifest. An interrupted multi-file write can leave a partial directory, but cannot be mistaken for the retained complete dossier because the dossier manifest binds every expected file.
- The parser does not execute HTML or fetch local or remote resources. The only path writes are to a caller-selected new output directory, which is appropriate for this offline trusted CLI workflow.

## H29 evidence

I independently regenerated all six views from the frozen code into a temporary directory. For every view, `compact.txt`, `reader.txt`, `source-view.json`, and `manifest.json` were byte-identical to `pilot-inputs-final`, and every reader inverted to the stored compact text. The focused unit test passed (`1 passed`) and Ruff passed.

The retained pilot audit independently matches text and table/row/image/exclusion inventories for all six views. The H29 documents contain 2/30/62 tables and 0/13/1 image references across the three embedded members; the standalone counterparts match their selected embedded documents, with the separately recorded wrapper/script differences. All H29 `table`, `tr`, `td`, and `th` elements have explicit recorded closes. There are no hidden text units, nested tables, rowspans, processing instructions, or unsupported media elements in the H29 documents. The index has one empty hidden tracking iframe; its attributes are retained in the projection and it is separately identified in `representation-audit.json`. Both decoded graphics remain separate hash-bound visual inputs.

## Candidate issues tested and refuted as H29 blockers

### Omitted HTML end tags can over-extend hidden annotations

A synthetic `<p hidden>secret<p>visible` and a synthetic omitted-`</td>` row both mark the later text hidden because `HTMLParser` does not apply all browser implicit-close rules to the custom element stack.

1. I checked all six retained projections: every H29 table/row/cell has an explicit recorded end, and no H29 text unit has a hidden reason. The reproducer precondition is absent from these inputs.
2. The synthetic later text is still retained byte-for-byte in the text stream and remains source-located; the error is an over-broad hidden annotation rather than dropped source. The raw source and disclosed lack of rendering equivalence remain authoritative.

This is not an H29 stop condition. Before applying the tool to filings that combine omitted closes with hidden ancestors, either implement the relevant implicit-close rules or fail closed on that combination.

### `verify_projection` does not authenticate all derived structural metadata

A coherent mutation of an attribute's decoded `value` and the corresponding image `src` can pass `verify_projection` while all byte locators stay unchanged. The function's docstring accurately limits its promise to byte identity, event partitioning, unit locators, and text projection.

1. The production path does not accept projection JSON as input: it constructs attributes, tables, images, and exclusions from the checked raw bytes, verifies immediately, serializes once, and hashes the result. There is no mutation boundary between parse and publication in this workflow.
2. For H29, independent parsing already matched the text and table/row/cell/image inventories, the final reader marker audit matches the projection, and an independent regeneration reproduced every retained artifact byte-for-byte.

This is not an H29 stop condition. If `verify_projection` later becomes an acceptance API for persisted or externally supplied projections, extend it to re-decode attribute names/values and validate table, element, image, and exclusion records against their referenced events, or rename it to make the narrower invariant explicit.

### The configured 64 MiB ceiling is higher than the practical memory envelope

The parser builds a Python integer offset entry for every decoded character, so a worst-case 64 MiB ASCII input can require far more memory than its raw byte size.

1. The largest H29 HTML input is 302,272 bytes, over two orders of magnitude below the cap; all six deterministic regenerations completed together in about 2.2 seconds in this environment.
2. The current contract explicitly pilots H29 only and reserves larger filings for a separately reviewed hierarchy. No H29 source approaches the memory-risk regime.

This is not an H29 stop condition. Before treating 64 MiB as a supported operational limit, benchmark it and either lower the cap or replace the per-character Python integer table with a compact/incremental byte-position map.

## Scope conclusion

The implementation is a useful, truthful input-projection layer for the current H29 draft reviews. A reviewer still must read all listed readers, resolve material display or raw-source questions, inspect both decoded images, record actual delivery/truncation observations, and keep completeness partial if any required source disposition remains unresolved. No schema-3 hierarchy or readiness change follows from this code review.
