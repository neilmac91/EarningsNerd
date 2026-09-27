# PR 969 independent strict-XHTML review

Reviewed the five-file working diff in `the isolated PR969 checkout` on base `7ff7762132286f22678c814ab42fa3440e56d545`. This was a read-only review; no branch files or tests were changed or run by the reviewer.

## Result

No remaining blocker after one bounded correction. The direction is coherent for the documented lexical XHTML subset:

- strict XML references use the five predefined named references and numeric XML code points, avoiding HTML C1 remapping;
- strict processing instructions are consumed through the first exact `?>` by the shared parser override;
- the source view and capacity preflight share strict-XHTML selection plus PI and BOM span handling;
- exact raw spellings are checked before using HTMLParser's lowercase indexes; unprefixed uppercase XHTML elements, case-distinct names, and case-changed projection-semantic attributes fail closed;
- CDATA and raw `script`/`style` constructs that HTMLParser cannot project with XML semantics fail closed;
- namespaced camel-case XBRL names remain supported when spelling is consistent.

## Finding, refutations, and correction

The initial snapshot preserved literal TAB/LF/CR inside strict XML attribute values. XML 1.0 instead performs end-of-line normalization and then replaces literal TAB/LF with spaces, while a character reference such as `&#x9;` remains a tab. A concrete probe projected `<p title="a\tb"/>` as `a<TAB>b`; ElementTree produced `a b`.

Two attempted refutations did not hold:

1. Calling the output lexical did not resolve the mismatch: `value_span` already preserves the lexical bytes, while `value` is decoded and is consumed for style, visibility, table, image, `src`, and `alt` semantics.
2. The absence of this pattern in the current H01 corpus would only avoid an observed corpus delta; it would not make the accepted valid-XHTML input correct.

The stable snapshot now shares `_decode_xml_attribute_value` between construction and verification. It normalizes CRLF and lone CR to LF, replaces literal TAB/LF with spaces, then decodes references once. Its focused proof compares the projected values with ElementTree and distinguishes literal CRLF from `&#x9;`. The owner reported two focused tests, Ruff, and `git diff --check` passing after this correction.

## Limits retained

This review does not convert the source aid into a generic XML/XHTML renderer and does not grant source admission. The capacity preflight validates strict XML well-formedness and the XHTML root for selection and measures callback spans; it still does not attest the projection's structural grammar. Exact raw spans remain authoritative for name spelling. Broader XML Infoset behavior outside the documented fail-closed subset remains out of scope.
