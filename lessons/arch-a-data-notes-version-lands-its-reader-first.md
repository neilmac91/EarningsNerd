# A data notes version move lands its reader first, in a pull request of its own

Date: 2026-10-28   Area: arch

**Context**: A saved analysis keeps its notes under `DATA_NOTES_VERSION`, and a change to their words, record-only
list or letter order takes a new version (`NOTES_DIGESTS` in `backend/tests/unit/test_analysis_data_notes.py`). The
page decodes each report and narrative only at a version it knows: `decodeEnvelope` in `dataNotesContract.ts` and
`decodeNarrativePresentation` in `narrativePresentation.ts`. E211 (#1667) gave its two proxy reasons words, so the
server had to write version 3. Its first version 3 commit (`a049d34f`) shipped the page's reader beside the writer.
The verification of that commit found the gap:
- Vercel deploys a merge minutes after it lands, but `deploy-backend` waits on the test jobs.
- A tab opened before the Vercel deploy keeps the old bundle, which reads only versions 1 and 2.
- Once Cloud Run moves, that tab refuses every completion (EVIDENCE_RECOVERY). Run analysis then fails the report's
  decode as well, until the tab is reloaded.

Version 2 had avoided it by hand: #1641 taught the page version 2 before #1659 moved the server.

**Rule**: Teach the page a new data notes version in a pull request of its own, and move `DATA_NOTES_VERSION` in a
later one, only once the reader has deployed. The reader admits the new version with the old shape; it does not write
it (the local grouper keeps the server's current version). Record the reader's pull request in `READERS` in
`frontend/tests/unit/analysis-presentation-api.spec.ts`.

**Evidence**: #1769 taught the page version 3 ahead of #1667. Partly gated by
`frontend/tests/unit/analysis-presentation-api.spec.ts`:
- both decoders must read exactly version 1 and the versions in `READERS`;
- the server's `DATA_NOTES_VERSION`, read from `backend/app/services/trend_analysis/data_notes.py`, must be one of them.

A version the page reads without a recorded reader, or a server version no recorded reader covers, fails the spec, and
its message names this rule. One tree cannot show deploy order, so whether the recorded pull request merged and deployed
before the server moved is review-checked.
