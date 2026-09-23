# Independent review: unsupported HTML tree-recovery guards

Reviewed read-only at commit `2f59c73be3568a69fb5454abf993b95d8c896dc1`.

- Parser SHA-256: `b78931856eb448ef8a2f2d21f3c2d9c30ead0e4db1265a3966bb66a3c282f6a6`
- Focused test SHA-256: `af241bc7d892506d9365576066915f7236e1399849f80dee12fac6e608c2c0c5`
- Diff scope: 47 parser lines and 20 test lines added or changed across the existing two source-view files.

## Conclusion

No actionable blocker remains in this commit. It closes the exact balanced-markup classes that the prior explicit-end/EOF guards could not see: adoption-agency and non-nestable starts, heading autoclose, selection-mode parsing, stray table parts, and table foster parenting. The implementation rejects unsupported syntax rather than approximating a browser tree, which preserves the source aid's byte and ancestry claims within its declared subset.

I did not run pytest or any model/provider call. The author reported one focused invariant test passing, Ruff passing, and a 16,000-deep ordinary-div projection completing in 0.277 seconds. The root-owned full gate was still running while this review was written.

## Review lenses

### Correctness: pass

- Repeated open `a`, `button`, `form`, and `nobr` tags are rejected before an event or element is recorded. A heading start is rejected whenever another heading remains open. These checks close the false-hidden-ancestry cases confirmed against an independent HTML5 parser.
- Every `select` start is rejected. This is intentionally conservative: select insertion modes can ignore or implicitly close tags in ways the lexical parser does not implement. None of the six H29 sources contains a select tag.
- Table flow state is kept on the innermost table stack entry. Outside an explicit `td`, `th`, or `caption`, the parser accepts only table structural starts plus direct `script`/`style`, and rejects substantive text, entities, character references, nonstructural starts, direct nested tables, and cells that would require an implicit row.
- The broadened table scope rules reject a table-part start that would implicitly close an open cell, row, row group, caption, or colgroup. The nearest-table boundary prevents an outer cell or row from being mistaken for the current nested table's state.
- `HTML_ASCII_WHITESPACE` is the exact five-character HTML set. Non-breaking space and other substantive decoded entities are rejected in foster-parenting positions.

### Security and performance: pass

- The change only converts ambiguous inputs into deterministic `ValueError` failures; it adds no I/O, network, serialization, or authorization path.
- Ordinary starts and text consult the current table state in O(1). Stack scans occur only for the four non-nestable tags and headings, and those inputs either pass once or reject at the conflicting start. The prior unconditional deep-stack scan is not reintroduced.
- Table state mutates with the existing push/pop lifecycle, so nested tables have independent cell/caption state and outer cell association resumes after the nested table closes.

### Maintainability and evidence: pass

- The constants name the supported subset directly. Existing validation remains the final byte-partition and source-hash authority.
- The single invariant test now contains both rejecting adversarial cases and accepting controls for nested lists/tables, direct table `script`/`style`, explicit ruby markup, and void self-closing syntax.
- My independent direct execution against the committed module rejected all targeted synthetic classes and accepted explicit nested-table, caption-flow, direct-script/style, and ASCII-whitespace controls.

## Refutation attempts

1. **Could balanced closing tags allow the original false ancestry through?** No. On the prior head, balanced nested anchor, button, form, nobr, heading, select, and table-foster cases all projected successfully. At `2f59c73b`, each rejects at the conflicting start or substantive table text before a misleading unit is recorded.
2. **Could the new table rule reject valid nested tables?** An explicit table inside a `td` projected successfully, including text before and inside the nested table. The innermost table state becomes authoritative while nested, then the outer cell remains active after the nested table closes.
3. **Could an outer open cell incorrectly license bad content in a nested table?** No. `_in_table_flow_context` reads only `table_stack[-1]`; a newly pushed nested table begins with no cell/caption, so direct substantive content is rejected even while the outer table still has an open cell.
4. **Could cell/caption state leak after an explicit close?** Direct controls accepted content while the state was open, then rejected fostered text immediately after `</caption>` or outside a cell. The close handlers clear only the current table entry.
5. **Could entity decoding bypass the text guard?** `&nbsp;` was independently rejected while plain tab, line feed, form feed, carriage return, and space were accepted. Entity and character-reference handlers both pass their decoded value through `_text`.
6. **Could the broadened cell/row/group rules confuse an outer table with an inner table?** Their boundary scans stop at the nearest open `table`. A valid explicitly nested table control passed, while caption-under-cell and table parts that would close a current row/group rejected.
7. **Could the conservative subset invalidate the retained H29 evidence?** All six frozen H29 HTML inputs projected successfully. Each new `project_html` result compared equal as a Python object to its frozen `pilot-inputs-final/*/source-view.json`; the sources contain no select tags and the event audit found no new rejected nesting or foster-parenting condition.
8. **Could this object comparison overstate full artifact equivalence?** Yes if described as a 24-file byte comparison, so this review does not do that. It establishes equality of the six structured projection objects. The author/root's separately retained artifact regeneration is the authority for byte equality of manifests, readers, compact text, and JSON files.

## Scope

The parser remains a conservative lexical source aid rather than a full HTML/CSS renderer. The finding is closed because known accepted inputs that would require tree repair now fail closed, while the retained H29 inputs remain inside the supported subset. This review makes no E7 acceptance or production-admission claim.
