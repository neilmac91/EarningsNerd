# E7 source preparation — 23 September 2026

This is engineering preparation for the approved AI-assisted E7 protocol, not source-review
completion or quality acceptance. No generation or judging call ran during this work.

The tested mapper binds the existing frozen source contract and records every byte of the
30 complete submissions: **973,729,710 bytes across 4,330 documents**. It separately validates
all **92 filing packets, 60 SEC JSON supplements and 30 embedding contracts**. The revised
source, supplement, embedding and selection hashes remain unchanged.

The real-archive repeat completed in **19.06 and 18.44 seconds**, with a measured maximum resident set of
**334,004,224 bytes** on macOS/Python 3.11.16 (memory mapping includes resident source pages).
Both runs produced **31 byte-identical JSON files**, including the index. The [receipt](receipt.json)
binds that index to `d7f2556fd48c05a20327c8ed48b53b23f6f7ef1c66d9c19d32c0e0a4036b7d48`.
Full maps and the underlying private archive remain outside Git.

Independent review verified the exact source/document/content partitions and identified three
issues in the initial prototype: unbound embedding metadata, exclusive readable routing for
inline-XBRL primaries, and overly broad archive-scope wording. The repository implementation
uses the fixed shared resolver before and after mapping, adds non-exclusive inline-XBRL review,
and explicitly limits byte accounting to complete submissions while inventorying other packets.
A final review found a missing orchestration gate. The added test proves successful map creation and that final inventory verification happens before index publication; failure leaves partial maps without a complete index. Full-suite results are recorded in the pull request.

The behavioral test covers UTF-8 byte offsets, CRLF boundaries, wrapper preservation, exact
duplicates, graphics, inline-XBRL routing, deterministic results, malformed/duplicate identities,
source drift and refusal to write from an unapproved archive. One mutation proof removed only
the new selected-document SHA equality: the test failed with `DID NOT RAISE ValueError`;
exact-byte restoration passed (`1 passed, 2 warnings`). A second proof removed only the final inventory recheck; the orchestration test failed and exact restoration passed. Both tests then passed together (`2 passed, 2 warnings`). No pre-existing budget or source-brief
admission safeguard was mutated.

The original 232-million-character flattened queue is retained as an incomplete prototype.
Neither it nor this document map establishes semantic coverage. The [mapper instructions](../../readiness-2026-09-21/acceptance/source-document-map.md)
state the remaining structured/image/unknown-format review requirements.
