# WS-7 implementation — steps 3–6 (archived)

Steps 1–2 shipped in PR #690. PR #697 merged `c925cfa83647f521583b6fa4dd257ac9027461db`, implementing the remaining code prerequisites;
founder backfill, job setup and off-peak universe generation remain separate execution gates.

- [x] Preserve filing-instance period metadata through normalization; derive trustworthy fiscal quarters without calendar-quarter guesses, and pin units/decimals behavior.
- [x] Audit every financial fact surface and display reconciliation warnings wherever flagged values appear.
- [x] List and ingest annual/quarterly amendments, identify superseded originals, and prefer amended prior periods in the Change Report without comparing a period to itself.
- [x] Read persisted accession-specific XBRL before external/cache fallback; complete the companyfacts liabilities/cash fallback.
- [x] Extend weekly examples to annual and quarterly forms and enable FPI on that job; provide an idempotent universe Company seed command without triggering AI generation.
- [x] Add mutation-proven regression tests, safe additive migration if required, accurate operational documentation, full backend/frontend gates for touched code, and independent review before merge.

## Evidence and remaining execution

Final source `6076fe7f` passed local backend 1935 tests and frontend 487 tests/build; CI
33961912275 passed backend 1935, performance 2, frontend 487, Playwright 21 (3 existing skips),
and PostgreSQL 34-file seed/replay plus ledger skip. All 32 backend / 10 Analysis / 5 supersession
mutations failed and were restored. [Exact checkpoint evidence](../wave2-ledger-2026-09.md).

- [x] Chief engineer verified production run 33962267301: `applied=1 skipped=33`, revision
  `earningsnerd-backend-00263-kzt` at 100% traffic, detailed health healthy (database 5.74 ms);
  pregenerate FPI env updated and Vercel production succeeded.
- [ ] Founder: SIC backfill, universe identity seed and follow-up SIC enrichment; observe live reports.
- [ ] Founder: off-peak universe generation after prerequisites; other console/job tasks remain open.

This archive closes implementation only. It does not assert existing data was backfilled,
unknown persisted fiscal metadata was re-extracted, or all product surfaces were activated.
