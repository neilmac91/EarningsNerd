# Markup nesting correction — author findings

- Source commit: `2f59c73be3568a69fb5454abf993b95d8c896dc1`
- Files changed: `backend/evals/acceptance_source_view.py` and its existing single invariant test.
- The pre-fix parser accepted both `<a hidden>A<a>B</a></a>` and `<a hidden>A<em>middle<a>B</a></em></a>` and marked the inner anchor text hidden. Explicitly balanced source tags therefore bypassed the non-top-close and EOF guards even though the HTML tree builder closes the first active anchor.
- The correction fails closed through the existing `_reject_unsupported_implicit_boundary` entrypoint. It rejects repeated open `a`, `button`, `form`, or `nobr` elements; headings under an open heading; all `select` sources; stray table parts; table-only nonstructural starts; direct nested tables; and non-ASCII-whitespace table text. Structural starts that would implicitly close an open cell, row, row group, caption, or colgroup are also rejected.
- Explicit content in cells and captions, nested tables inside cells, direct table `script`/`style` exclusions, comments, and the five HTML ASCII whitespace characters remain supported. The table check uses the existing top table state and private cell/caption flags, so ordinary starts and text retain an O(1) fast path.
- Focused invariant: `1 passed`, with the two existing dependency deprecation warnings. Ruff and `git diff --check` passed.
- Balanced ordinary `div` timings remained near-linear: 2,000 = 0.0330 s; 4,000 = 0.0640 s; 8,000 = 0.1304 s; 16,000 = 0.2769 s.
- All six H29 inputs contain zero newly rejected nested-special, heading, selection-mode, stray-table-part, foster-start, or foster-text cases. Regeneration at the committed source produced 24/24 byte-identical artifacts; see `pilot-equivalence.json`.
- Independent review found no blocker and separately compared all six projected objects byte-for-byte with the frozen `source-view.json` files.

This remains a source projection with a conservative supported grammar, not an HTML5 repair or rendering engine. The global nesting checks can reject malformed markup that a browser would recover differently across scope boundaries, and `select` is intentionally unsupported rather than partially modeled. The relevant primary tree-builder rules are in the [WHATWG parsing specification](https://html.spec.whatwg.org/multipage/parsing.html).
