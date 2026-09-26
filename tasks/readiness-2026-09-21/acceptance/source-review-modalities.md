# E7 source modality inventory: every table, fact and image dispositioned

**Status:** internal engineering format (`schema_version` 1, kind `e7_offline_source_modality_inventory`),
draft for review. It is not an E7 evidence schema, has no readiness, protocol, executor, output or
decision call site, and cannot admit evidence.

`backend/evals/acceptance_source_modalities.py` is the third offline-custody piece of the
[hierarchy plan](source-review-hierarchy-implementation-plan.md#1-offline-source-custody), after the
[byte-custody review units](source-review-units.md) and the [member dispositions](source-review-members.md).
Both of those record that tables, inline-XBRL facts and images inside a source are not inventoried.
This format closes that gap for one HTML source packet. Every table, inline-XBRL fact (hidden facts
included) and image reference gets exactly one explicit, hash-bound disposition, so none can drop out
of review scope unnoticed. Unresolved items stay listed and hold completion.

## What a valid inventory proves

`validate_modality_inventory(inventory, accession_number=..., expected_packets=..., packet_bytes=..., unit_manifest=..., packet_role=...)`
proves the following for the caller's inputs, and nothing more:

1. The unit manifest is valid for the caller's accession, its frozen expected packets and its bytes;
   the validator calls `validate_unit_manifest` itself. The inventory is bound to that manifest's
   `manifest_sha256`, to the named packet's role, SHA-256 and length, and to the accession.
2. The items are exactly those enumerated from the packet's own bytes by the existing deterministic
   source-view parser (`acceptance_source_view.project_html`), in view order. Tables come first, then
   inline-XBRL facts (`ix:nonFraction`, `ix:nonNumeric`, `ix:fraction`), then `img` references. An
   omitted, added, reordered or relabelled item is rejected.
3. Each item records its byte span `[start, end)` from its start tag to its end tag (the start tag alone
   for an image), the span's SHA-256, and its hidden reasons. Hidden reasons collect the
   `hidden_reasons` of every element whose span contains the item, including the item itself:
   `hidden_attribute`, `aria_hidden_true`, `inline_style_hidden` and `inline_xbrl_hidden`. They are
   listed outermost element first, then in each element's own order, keeping only the first occurrence
   of a repeated reason; the list is not sorted, and `item_id` hashes it in that order. Hidden items are
   counted separately and never dropped.
4. Every item has exactly one disposition:
   - `assigned_to_review_units` names one or more `unit_id`s of this packet in manifest order. Every
     named unit must cover at least one of the item's bytes, and together they must cover all of them.
     A table that straddles a unit boundary therefore names every unit it spans.
   - `unresolved` carries a declared `reason` label. The item is listed in `unresolved_item_ids` and
     holds completion.

It does **not** prove that any item was reviewed, that a table's caption, headers, continuations and
footnotes were supplied together, that a fact's concept, value, context, unit, scale or sign is right,
or that a referenced image was viewed or linked to its graphic member. Every attestation flag is
`false`, and the inventory never carries `coverage_status`.

Only one HTML packet is inventoried per call. Other HTML packets need their own inventories. A packet
must be strict UTF-8 that the source view can project and must contain an `html` or `body` element, so
a graphic, plain-text, XML or other non-HTML packet is rejected rather than inventoried as empty; its
custody lives in the unit manifest and the member ledger.

## API

```python
from evals.acceptance_source_modalities import (
    build_modality_inventory, load_modality_inventory, validate_modality_inventory,
)

inventory = build_modality_inventory(
    accession_number=accession, expected_packets=contract, packet_bytes=packet_bytes,
    unit_manifest=manifest, packet_role="primary",
    dispositions={
        "T00001": {"kind": "assigned_to_review_units", "unit_ids": [first_unit_id, second_unit_id]},
        "F00001": {"kind": "assigned_to_review_units", "unit_ids": [first_unit_id]},
        "I00001": {"kind": "unresolved", "reason": "graphic_not_viewed"},
    },
)
summary = validate_modality_inventory(load_modality_inventory(stored_bytes), accession_number=accession,
                                      expected_packets=contract, packet_bytes=packet_bytes,
                                      unit_manifest=manifest, packet_role="primary")
```

`dispositions` maps each item's `view_id` to one disposition. The builder rejects a missing view ID
(`no disposition for items: …`) and one the packet does not contain, so it cannot leave an item
implicit. `expected_packets` must come from the frozen source contract, never from the manifest.
Stored inventories must be exactly `canonical_json(inventory)`, as for the other custody formats, and
must be loaded through `load_modality_inventory`.

Both functions are pure: no file, network or clock access, and they never mutate their arguments.
Invalid input raises `ValueError`; nothing is repaired, coerced or reordered. Type identity is exact at
every depth.

## Format

An inventory has `schema_version`, `kind`, `accession_number`, `packet` (`{role, sha256, byte_length}`),
`unit_manifest_sha256`, `items`, the five attestation flags (`semantic_review_attested`,
`visual_review_attested`, `fact_values_verified`, `modality_completeness_attested`,
`admission_approved`) and the fixed `limitations` list.

Each item carries `item_id`, `modality` (`table`, `inline_xbrl_fact` or `image`), `view_id` (`T00001`,
`F00001` or `I00001`, numbered in view order within its modality), `start`, `end`, `sha256`,
`hidden_reasons` and `disposition`.

`item_id` = `SHA-256("e7-source-modality-item-id-v1" || 0x00 || canonical_json({"accession_number",
"packet_sha256", "modality", "view_id", "start", "end", "sha256", "hidden_reasons"}))`, with the same
`canonical_json` as the unit manifest. The regression test recomputes it independently.

The validation summary reports `item_counts` and `hidden_item_counts` per modality,
`assigned_item_count`, `unresolved_item_ids`, the flags and the limitations. It binds the inventory
through `inventory_sha256` and the manifest through `unit_manifest_sha256`.

**Fail-closed parsing.** Anything that would let an item leave scope silently is rejected instead of
counting zero:

- The inventory inherits the source view's refusals: a packet that is not strict UTF-8, or whose markup
  the parser cannot project safely, is rejected. A packet without an `html` or `body` element is
  rejected.
- Inline XBRL binds a namespace, not a prefix. Facts and `hidden` or `header` sections are recognised
  only under the conventional `ix:` prefix, so `nonFraction`, `nonNumeric`, `fraction`, `hidden` or
  `header` under any other prefix is rejected.
- Image-bearing markup other than `img` (`image`, `svg`, `object`, `embed`, `picture`, `iframe`,
  `canvas`) is rejected rather than left uncounted. CSS background images are not evaluated.
- A hidden non-void element without an explicit end tag is rejected, because its hidden scope would be
  ambiguous. The parser already rejects every open element except `html` and `body` at end of file, so
  this fires for an unclosed hidden `html` or `body`. A guard for an inline-XBRL fact without an end tag
  is kept as defence in depth; the parser rejects that case first.

## Limitations

The inventory and summary carry exactly these strings, together with every flag `false`:

1. Items are enumerated by the deterministic source-view parser; hidden status covers HTML attributes, inline style and ix:hidden only, and external CSS, scripts and browser rendering are not evaluated.
2. An assignment proves only that the item's bytes lie inside the named review units' coverage; it does not prove the item was reviewed or that a table's caption, headers and footnotes were supplied together.
3. Inline-XBRL facts are identified by their element spans; concepts, values, contexts, units, scale and sign are not validated.
4. Image references are counted from img tags; the referenced graphic bytes, their member linkage and any visual inspection are not proven.
5. No source review, E7 coverage_status or E7 admission is attested; unresolved items hold completion.

Any change to these strings, the flags, the modalities, the dispositions or a key set needs a new
`schema_version`. Table grouping (caption, header and footnote bundles), image-to-member linkage, visual
dispositions, the review graph, issue ledgers and admission remain later reviewed slices. Real-source
validation over H01/H02/H25 is not performed here, because their raw bytes are not in this environment.
