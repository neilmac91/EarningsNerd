# Independent review — inline `!important` hidden-style fix

**Disposition: no actionable finding.** Commit `a0fea57bb981ae55f21bb3aa72146fbc19eacb20` is a narrow correction for the reproduced P2. The diff from `32c8c65ed536d1c9ca070dd241ac91495d9fd165` changes only the source-view matcher and its existing invariant test. This review did not edit the repository or assess financial content.

## Lens 1: matching semantics and declaration boundaries

The revised expression recognizes `display:none` and `visibility:hidden` followed by optional `!important`, including whitespace between `!` and `important`, surrounding declaration whitespace, mixed case, a final declaration without a semicolon, and a declaration followed by another property. Its `(?:^|;)` and `(?:;|$)` boundaries continue to reject property prefixes, value suffixes, and embedded text.

Two independent refutations found no under-match or new boundary defect in the intended lexical scope:

1. Fresh projections correctly marked descendants hidden for `display : none ! important`, tab-separated `visibility : hidden ! IMPORTANT ;`, mixed-case declarations after another property, and entity-decoded `display:none&#33;important`.
2. Fresh projections kept visible controls unmarked for `display:block!important`, `xdisplay:none!important`, `display:none!importantx`, `color:red display:none!important`, `visibility:hiddenly !important`, and `display:none important`. The committed combined near-miss fixture independently covers the same boundary classes.

This remains a lexical inline-style annotation rather than a CSS renderer. It does not claim cascade resolution, stylesheet evaluation, escaped-token interpretation, or complete CSS grammar. The module still states `css_rendering_evaluated: false` and retains raw style attributes for review.

## Lens 2: source custody and projection integrity

The fix changes only the boolean annotation derived from a decoded style value. It does not alter parsing, source events, unit inclusion, normalization, attributes, byte spans, table structure, or image/exclusion handling.

Two independent refutations found no source loss or locator drift:

1. The committed fixture asserts the exact compact-text concatenation and the exact four decoded style values, then passes `verify_projection`; both hidden and visible source text remain present.
2. A fresh table fixture rechecked every text-unit span hash against the original bytes, every style/data attribute value span against its raw bytes, the compact-text hash, and equality recovered from both reader renderings. Entity-decoded `!` was classified while its raw `&#33;` bytes remained recoverable from `value_span`.

The restored implementation SHA-256 is `dccd0cf36702b5f81a94f55ade21c2583a8eab3367d6bcd6380ddd78f08ab1ef`, matching the mutation receipt.

## Lens 3: propagation, rendering, tests, and bounded runtime

Hidden reasons are stored on the matched element and collected through `element_stack`, so descendants inherit the marker. Reader rendering carries the marker through ordinary text aggregation and table-row aggregation.

Two independent refutations found no propagation or control regression:

1. The committed test checks nested `span`/`strong` descendants for both important forms, preserves the existing plain-hidden form, and verifies `hidden=inline_style_hidden` versus `hidden=-` in the compact reader.
2. A fresh two-row table fixture produced `inline_style_hidden` on both cells beneath a hidden `tr`, while the `display:block!important` row and its child remained unmarked. Both reader text and detailed-review text reconstructed the unchanged compact stream.

The mutation evidence is valid: restoring only the pre-fix matcher caused the existing unit-annotation assertion to fail (`inline_style_hidden in []`), and restoring committed bytes passed. Failure at that earlier assertion proves the guard; a second mutation aimed at the later reader assertion was unnecessary. The retained log hashes match the mutation receipt. Direct adversarial searches over one-million-character plain/whitespace values and 750,000 characters of repeated near misses completed in 0.03 seconds or less, with no match, providing a separate check against obvious regex backtracking risk.

The change does not modify readiness, budget, schema, or admission logic and makes no broader CSS or semantic-coverage claim.
