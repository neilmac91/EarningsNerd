# H01/H02/H25 hierarchy-capacity reconnaissance

**Status:** bounded offline metadata reconnaissance only. It does not review source meaning, run an HTML projection, change admission or protocol, or approve a hierarchy. The measurements use only the three retained document maps, their declared packet paths, and streamed size/SHA-256 checks of the three primary files. No download, provider call, or source mutation occurred. Machine-readable detail is in [`capacity.json`](capacity.json).

## Measured packet and member sizes

All governing byte counts below are from the approved revised source contract bound by `source-map-final/index.json`. `Members >2 MiB` compares whole SGML document-content spans with 2 MiB; it is **not** a parser-event count.

| Filing | Revised primary / index / complete submission | SGML members (readable) | Largest member | Members >2 MiB (readable) | Member-preserving 2 MiB raw-span floor |
|---|---:|---:|---|---:|---:|
| H01 CAT 10-K | 6,100,579 / 14,404 / 33,197,476 B | 162 (8) | 7,469,968 B XML, structured-data route | 3 (1) | primary 3; all readable 10 |
| H02 DUK 10-K | 16,080,286 / 38,152 / 81,613,612 B | 268 (42) | 21,628,456 B XML, structured-data route | 7 (1) | primary 8; all readable 49 |
| H25 HSBC 20-F | 57,158,558 / 95,290 / 297,209,475 B | 550 (10) | 57,158,447 B 20-F, readable route | 15 (1) | primary 28; all readable 37 |

The three maps account for 980 members and 412,020,563 complete-submission bytes. The selected primary members are inline-XBRL HTML (`XBRL` wrapper) with 86, 90, and 87-byte SGML headers. Declared member types include the readable 10-K/20-F and exhibits, XML/XBRL data and rendering members, JSON, ZIP, and graphics; exact per-type counts, bytes, maximums, and routes are retained in the JSON. H25 is the limiting readable case: its 57,158,558-byte direct primary consumes about 85.2% of the 64 MiB ceiling.

## Current limits

`acceptance_source_view.py` limits a complete HTML input to 64 MiB and each emitted parser-event byte span to 2 MiB. All three revised direct primary packets, and every readable SGML member, are below 64 MiB. H02 and H25 complete-submission containers exceed 64 MiB, but those are `text/plain` SGML containers and are not direct `project_html` inputs; routing either container to that API would fail and would also be a format error.

The maps cannot establish the 2 MiB parser-unit condition. A 57 MiB document can consist entirely of small parser events, while one large text/comment/markup event can exceed 2 MiB. Whole-member sizes therefore neither prove a block nor prove safety. The raw-span floors in the table show only the minimum number of at-most-2-MiB leaf spans when member boundaries are preserved.

This reconnaissance also does not measure structural-JSON expansion or peak memory, actual model-context size, or table/image/other-modality capacity. Those remain separate implementation and protocol questions.

## Custody verification

The current primary files stream-hash exactly to the approved revised source manifest and final maps. The candidate-original columns are historical comparison only:

| Filing | Revised bytes / SHA-256 prefix | Candidate-original bytes / SHA-256 prefix | Result |
|---|---|---|---|
| H01 | 6,100,579 / `3c749d4d1d3a` | 6,100,583 / `fb9bdf42368d` | distinct identity |
| H02 | 16,080,286 / `25141df6945a` | 16,080,290 / `6c451cbcbd57` | distinct identity |
| H25 | 57,158,558 / `08f3a9c524be` | 57,158,562 / `4b60b424ae53` | distinct identity |

This is not filesystem drift against the revised contract and not an HTTP `Content-Length` versus stored-byte distinction. `source-manifest.json` explicitly records each as `diff_status: changed` from a `new_sec_service_fetch`, retaining both original and revised identities. The original primary bytes are unavailable, so this reconnaissance cannot determine the exact cause of the four-byte changes and does not infer normalization. The approved revised identities govern this capacity measurement. The original/revised distinction preserves the existing custody rule—bind one declared contract and never mix identities—and creates no new hold.

## Smallest useful next tranche

Add one identity-bound parser-event capacity preflight for these three declared **revised** primary HTML packets. It should stream the selected contract's size and SHA-256 verification, then use a bounded whole-input tokenizer without constructing the structural projection. It must preserve the current parser's logical event boundaries across input chunks (or explicitly coalesce split fragments); naively feeding fixed-size chunks can split one data event and falsely pass the 2 MiB limit. Report the maximum parser-event byte span and event kind, and fail on a source over 64 MiB, an event over 2 MiB, or any identity mismatch. Pilot H01, H02, then H25. This measures the still-unknown parser-event bound and supplies split-pressure evidence before implementing leaf manifests or a hierarchy validator. Structural-output memory, model-context sizing, and modality capacity remain unproven. This tranche does not alter either previously denied guard, admission, the approved quality bar, or the source-review protocol.
