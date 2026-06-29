# Task: Filing-scoped fundamentals chart (Design B) + event-driven facts backfill

Founder feedback: the filing page chart should represent **the specific (immutable) filing**, not
the company's accumulated trend. So:
- **B — make the filing-page chart filing-scoped:** show the multi-year figures *as reported in this
  filing's own XBRL* (its comparative years), not the company's latest `is_latest` series by ticker.
  Immutable + faithful to the document.
- **Event-driven backfill:** populate a filing's facts once, when it's summarized (xbrl_data stored),
  instead of a recurring cron. Filing-scoped data never goes stale, so no schedule is needed.

The company page chart stays company-scoped (correct there) — only the filing page changes.

## Design notes (verified)
- `financial_fact` rows carry `filing_id` + `accession`; a 10-K's XBRL has the current year + prior
  comparatives, so one filing → a multi-year FY series. Filing-scoped query = `WHERE filing_id = X
  AND fiscal_period = 'FY'` (NO `is_latest` filter — we want the figures *this* filing reported, even
  if a later filing restated them). One row per (concept, period_end) within a filing.
- Both summary paths persist `xbrl_data` at known chokepoints: `summary_pipeline.py:~295` (SSE, inside
  `update_xbrl_sync`, own session + threadpool) and `summary_generation_service.py:~603` (batch).
- `upsert_facts(reconcile=True, authoritative=None)` runs only the local gate — no network — so the
  post-summary hook is fast + SEC-call-free.

## Backend
- [ ] `facts_service.process_filing_facts(db, filing, *, extract=None, standardized=None, authoritative=None)`
      — per-filing extract→normalize→upsert→stamp (the per-filing core). Refactor `backfill_facts` to
      call it (DRY; behavior-preserving — keep the counters/cross-check/idempotency the tests assert).
- [ ] `facts_service.get_filing_fundamentals(db, filing_id)` — filing-scoped FY series (no is_latest).
- [ ] `GET /api/filings/{filing_id}/fundamentals` → `FundamentalsResponse` (404 if filing unknown).
- [ ] Hook `process_filing_facts` (best-effort, try/except) after both xbrl_data commits — pass the
      already-extracted `standardized` metrics on the SSE path to avoid re-extraction; `authoritative=None`
      (no SEC round-trip on the hot path). Never break the summary stream.

## Frontend
- [ ] `getFilingFundamentals(filingId)` in fundamentals-api.ts (`GET /api/filings/{id}/fundamentals`).
- [ ] `FundamentalsTrendChart`: accept `filingId?` (filing-scoped fetch, key `['filing-fundamentals', id]`)
      OR `ticker?` (company-scoped, as now); `enabled` on whichever is present. Company page unchanged.
- [ ] Filing page: render `<FundamentalsTrendChart filingId={filing.id} subtitle="…as reported in this
      {filingType}" />` (filing-scoped framing) instead of ticker-scoped.

## Tests
- [ ] backend: `get_filing_fundamentals` returns the filing's FY rows incl. restated (is_latest=False);
      `process_filing_facts` extracts+upserts+stamps one filing; backfill tests still green.
- [ ] frontend: chart spec — a `filingId`-mode render test (mock `getFilingFundamentals`); existing
      ticker-mode tests stay green.

## Verify
- [ ] `py_compile`; `npm run typecheck` + `lint`; full `vitest`. Backend DB tests run on CI.

## Review
- **B (filing-scoped):** new `get_filing_fundamentals` (query by `filing_id`, FY-only, no `is_latest`)
  + `GET /api/filings/{id}/fundamentals`; chart gained a `filingId` mode (company page unchanged);
  filing page now passes `filingId` + a "as reported in this {type}" subtitle. The shared row→series
  shaping was factored into `_fundamentals_payload` (DRY).
- **Event-driven backfill:** factored the per-filing core into `process_filing_facts` (used by both
  `backfill_facts` and the hooks). Hooked it best-effort + network-free after both xbrl_data commits
  (SSE reuses the metrics it already extracted; batch re-extracts). `backfill_facts` refactor is
  behavior-preserving — existing backfill tests use `cross_check=False`, and the cross-check test
  still passes `authoritative` through, so no new network calls.
- **Verified:** `py_compile` clean; `npm run typecheck` + `lint --max-warnings 0` clean; vitest 50
  files / 231 tests (+1 filing-scoped). New backend tests (filing-scoped read incl. restated rows;
  `process_filing_facts`) run on CI.
- **Outcome:** the filing chart is now an immutable, document-faithful snapshot; no recurring backfill
  needed (facts populate when a filing is summarized).
