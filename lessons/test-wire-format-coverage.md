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
