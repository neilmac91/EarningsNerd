# Pin serialized wire formats with tests — suites that only check values let format drift through

Date: 2026-07-06   Area: test

**Context**: The S5 timezone sweep flipped `datetime.utcnow()` (naive) to an aware
helper. Everything valuable was tested — except the exact serialized strings. Pre-existing
code appended `"Z"` to `isoformat()` output; aware datetimes serialize as `+00:00`, so
those sites briefly emitted malformed `…+00:00Z` timestamps, which broke the trending
cache's round-trip parser — and the 1,233-test suite stayed green, because nothing pinned
the wire format. There was even a second-order case: one service emitted `+00:00` and its
router appended the `Z`. The fix (`iso_z()`, offset→Z, byte-identical legacy format) came
with `test_datetimes.py` pinning the contract and a round-trip test through the real
parser.

**Rule**: Any value that crosses a process boundary as a string (JSON timestamps, cache
payloads, SSE frames, IDs with encoded structure) gets a test asserting the EXACT
serialized form and a round-trip through the real consumer/parser. When changing how a
value is produced, grep for every consumer of its serialized form — including
concatenations (`+ "Z"`) that assume the old shape.

**Evidence**: PR #563 delta-log entry (the `+00:00Z` regression and the hot_filings
service/router double-suffix case); `backend/app/utils/datetimes.py` `iso_z()`;
`backend/tests/unit/test_datetimes.py` round-trip via the trending parser.


**Progressive JSON completion (2026-09-09).** A current-schema final renderer does not prove
preview fidelity. The old preview used the legacy renderer and invented generic absence claims;
repairing an unfinished scalar can also promote a prefix into a figure. Decode complete original
section containers at the existing JSON owner before calling the shared current-schema projection.
Missing sections remain pending. Reject non-finite constants and float overflow: JSONDecoder's
`parse_constant` alone does not prevent `1e999` becoming the visible string `inf`. Previously
completed sections may remain visible when a later member is unfinished; this is not whole-prefix
JSON validation or source/final-provider identity certification. The ordinary
`test_stream_section_reveal.py::test_previews_render_only_originally_complete_current_sections`
checks character truncations and actual callback progress while preserving collected final bytes.


**Same-day actual-output correction.** A shared renderer alone does not apply final ownership.
The first #803 run emitted model segment figures that final processing intentionally discarded.
Run the existing numeric owner and bank sanitizer on the fresh parsed preview copy, then retain
only originally complete section keys; do not copy financial formulas or synthesize an unreceived
section. When an armed quote guard cannot verify at the preview seam, wait for final verification
rather than exposing an unverified attributed quotation. This is a distinct ownership invariant,
covered in the same unlocked home; retain the original completion proof without repeating it.
