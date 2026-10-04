# Correction 02 — CTO operating-envelope handback, revision 2 → revision 3 (2026-10-04T15:21:41Z)

**Source of the findings:** the independent read-only PR reviewer for PR #1086 head `0cf48204` (no blocker;
82 anchors and 24 hashes checked; eight nits). The handback-related nits and their dispositions:

| Reviewer id | Finding | Disposition in revision 3 |
|---|---|---|
| R2 | B07 cited `fleet-coordination-proposal-2026-09-19.md:25` for "no container command override"; the supporting sentence is on line 26 | anchor corrected to `:26` with the exact wording ("no container command/argument override returned") |
| R3 | B09/B13 cited `database.py:29` (SQLite branch) for the production engine and `pool_pre_ping` | anchors corrected to the PostgreSQL branch `database.py:32–39` |
| R4 | B23 marked the notable-filings schedule unknown although it is in the repository | recorded as "08:30 and 18:30 America/New_York per `docs/DEPLOYMENT.md:623–624` **as reported by the independent reviewer**"; the chief did not read those lines (the earlier read of that section was denied by the auto-mode classifier and was not re-attempted); classification stays `configured-deploy` for the row with that attribution in the uncertainty column |
| R5 | B48 range stopped before the `await`; B57 cited the rollback guard rather than the rollback step | B48 `pregenerate_examples.py:86–91`; B57 `ops.yml:641` (the `rollback-traffic` step condition) |
| R6 | "93 anchors" in CORRECTION-01 is not verifiable from the committed outputs | the figure is the size of the generator's anchor table (one key per resolved `file:line` lookup; several bounds share a key and several keys feed only prose). Revision 3's table has 94 keys (one added for the engine-branch end line). The generator is not committed (tasks-only PR; nothing executable at the repository root) |

Field-by-field diff of the JSON, revision 2 → revision 3: exactly seven changed bound fields (B07, B09,
B13, B48, B57 `evidence`; B23 `value` and `uncertainty`), `revision: 3`, a new `observed_at`; the
`determination` block is byte-identical. No bound value or classification changed other than the B23
notable-filings entry, which moved from unknown to attributed-reported.

| File | Revision 2 SHA-256 | Revision 3 SHA-256 |
|---|---|---|
| `CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` | `ef22d1f5986c0b6f7165fc3e0f7b932f12a954ed74444a63bd3f09e6a4687a32` | `58ef902d0339ba812e859a764575f53828f60588b8104bf9318d79c69b0a967e` |
| `CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` | `9acb42fa5507a97cdb44d2195869c0bdb2c5897f289eb64d0bebdac86241c2ee` | `5ee84009c08f8ecf107174376f67c34084f9461b162fdbc5864e718f4ce3c8fd` |

Revision 1 hashes remain in `CORRECTION-01.md`; the COO disposition evaluated revision 1 and its HOLD is
unaffected by revisions 2 and 3 (no load-bearing `unknown` row changed). Other reviewer nits (R1 README
wording, R7 todo wording, R8 provenance slips) are fixed in the same commit outside the handback files and
are listed in `CHECKPOINT.md`.
