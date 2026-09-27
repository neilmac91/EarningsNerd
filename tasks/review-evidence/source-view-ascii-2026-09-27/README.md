# Bounded source-view capacity correction — 27 September 2026

The ASCII offset optimization lets the two named frozen direct primary documents complete
projection and verification under the existing 3 GiB Linux address-space limit and 180-second
per-worker timeout. The [unchanged released parser previously failed on H25](../source-capacity-2026-09-27/README.md#bounded-linux-result).
The original failure remains retained; the candidate changes code, not the source or execution limits.

## What changed

For ASCII text, character positions are already UTF-8 byte positions. The parser now uses an
identity `range` instead of retaining one Python integer per character. H25 is entirely ASCII;
its 57,158,559-entry offset list alone was estimated at roughly 2.06 GB on the measured CPython
layout. Non-ASCII inputs retain the existing cumulative UTF-8 offset algorithm. After `finish`,
the returned records own their lists, so parser-only state and the redundant decoded-text reference
are released before normalization and verification. Every existing verifier and renderer still runs.

This is not a claim that final peak RSS fell by 2.06 GB: the old run failed before completing,
whereas the new run reached later allocations. The original failure's exact phase was unrecorded.

## Measured result

The [single candidate run](https://github.com/neilmac91/EarningsNerd/actions/runs/36308012474)
at diagnostic commit `9ffef5aefd592a4df2af9e762fc1a4e2c1e3067f` verified the frozen ZIP and source
hashes, then ran without network or provider credentials. Python was 3.11.16. The
[unmodified worker receipt](capacity-receipt.json) records:

| Direct primary | Worker time | Peak RSS | Events | Compact text bytes | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| H25 | 63.118840 s | 3,173,560,320 B | 1,278,811 | 3,108,506 | Projection and outer verification completed |
| H02 | 22.691184 s | 1,245,945,856 B | 355,227 | 1,299,810 | Projection and outer verification completed |

Both children observed exact soft/hard `RLIMIT_AS=3,221,225,472`; neither exceeded its 180-second
wall limit. H02 started only after H25 passed. H25 still uses substantial memory, so this one
bounded success does not establish general operating headroom or capacity for other sources.
The worker retains counts and compact-text hashes, not complete serialized projection artifacts.

The module in this change is byte-identical to the measured candidate:
`be3142802e443b92e38bf4723e8c98d7067732d80cc2249ae4d9d14f276520c7` (58,613 bytes).
The retained diagnostic ZIP is 3,223,616 bytes with SHA-256
`4877af596173961fcd141db35235a22b75b18b8ec622e8f99d1eeaa87a8eb743`.
The separate diagnostic branch and ZIP are not part of this application change.

Small ASCII, UTF-8, BOM and attribute fixtures produced identical complete projections, locators,
review text and reader text against the released parser under Python 3.11.16. Independent review
also compared strict-XHTML and malformed-input rejection cases. A separate Python 3.14 comparison
is retained as additional evidence, not a substitute for the runner's version. Local parity,
workflow checks, raw hosted logs, the ZIP and hashes remain under the operator workspace's
`outputs/takeover-2026-09-26/h25-ascii-capacity/`.

## Remaining limits

H25 is the 57,158,558-byte direct primary, not the SGML member that differs by 111 wrapper bytes.
This result does not establish all-member coverage, image decoding or financial interpretation.
The 264 strict encoded-member failures and all 980 unresolved member dispositions remain as
recorded in the prior census. Complete source-role payloads, provider context fit, 60 independent
briefs, 30 reconciliations and E7 admission remain unproved. No E7/E8 judging, source recapture,
decoder relaxation, baseline re-pin or production-flag change is part of this correction.
