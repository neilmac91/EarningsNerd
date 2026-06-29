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

---

# 2.6 Phase A — richer cited financials (flagged, narrative-neutral)

## Goal
Make the *verifiable* surfaces (filing-scoped trend chart + Copilot numeric citations) richer by
extracting the genuinely-missing statement lines — the **full cash-flow statement** (investing +
financing flows) and **working-capital** lines (current assets/liabilities → derived working_capital
+ current_ratio) — **without touching the AI narrative** (that's Phase B, eval-gated, later). Behind
`RICHER_FINANCIALS_ENABLED` (default OFF) so flag-off behaviour — and the eval baseline — is
byte-for-byte unchanged.

## Done
- [x] `config.RICHER_FINANCIALS_ENABLED: bool = False` (flag).
- [x] `instance_extractor.py`: `RICHER_DURATION_CONCEPTS` (investing/financing CF, US-GAAP + IFRS) +
      `RICHER_INSTANT_CONCEPTS` (current assets/liabilities). Kept in separate dicts, merged only when
      the flag is on.
- [x] `xbrl_service._extract_from_filing_instance_sync`: flag-gated merge of the richer dicts into the
      generic DURATION/INSTANT loops (off ⇒ original dicts, byte-for-byte).
- [x] `xbrl_service.extract_standardized_metrics`: surface the 4 new base lines + derive
      `working_capital` (CA−CL) and `current_ratio` (CA÷CL) per period (self-gating; divide-by-zero
      guarded). Inert when the flag never populated the series.
- [x] `facts_service`: `_CONCEPT_UNITS` (USD for the 4 lines + working_capital; `pure` for
      current_ratio); `NON_NEGATIVE_CONCEPTS` += current_assets/current_liabilities (the CF flows and
      working_capital can legitimately be negative → left out).
- [x] `FundamentalsTrendChart.FEATURED` += investing/financing CF, current assets/liabilities,
      working capital (self-gate: render only when present).
- [x] `copilot_tools.py`: **no change needed** — reads `financial_fact` generically; `_concept_label`
      title-cases unknown keys ("Working Capital", "Current Ratio", "Investing Cash Flow").

## Deliberate scoping
- The `get_financials()` **fallback** path (`_extract_from_dataframe`) is left unenriched. It is a
  company-scoped/last-resort path (wrong for filing-scoped B anyway); enriching it adds complexity to a
  degraded-mode branch for no user-visible gain. Flag-off stays byte-for-byte; flag-on uses the
  accession-aware instance path (the correct one) for the new concepts.
- **Narrative untouched:** `_xbrl_spec` (prompt whitelist) is NOT modified → eval baseline unchanged.
  Phase B (add keys to `_xbrl_spec`) is a separate, eval-gated PR.

## Tests
- [x] backend `test_accession_xbrl_extraction.py::test_richer_financials_extracted_only_behind_the_flag`
      — flag off ⇒ concepts absent; flag on ⇒ extracted from the filing's own instance.
- [x] backend `test_richer_financials.py` (new) — standardize surfaces the new lines + derives
      working_capital/current_ratio per period; liquidity self-gates without CL; zero-CL skips the
      ratio; absent when no richer data; normalizer units (USD / `pure`); reconcile hard-rejects
      negative current assets/liabilities but keeps negative financing CF.
- [x] frontend chart spec — the richer 2.6 metrics render as buttons when present (+1 test).

## Verify (done locally)
- [x] `python3 -m py_compile` + `ruff check .` clean on all changed backend files.
- [x] backend: `test_richer_financials.py` + `test_accession_xbrl_extraction.py` = 30 passed;
      `test_facts_service.py` + `test_ads_ratios.py` = 58 passed (no regression).
- [x] frontend: `npm run typecheck` + `lint --max-warnings 0` clean; chart spec 7 passed (+1 new).
- [ ] CI: `backend-tests` + `eval-baseline` green (eval-baseline proves the narrative is untouched).

## Review
- **Shape:** 2.6 is purely *additive* (new concepts), not a refactor. The audit confirmed our
  accession-aware `filing.xbrl()` instance path is the correct one for filing-scoped (B); the docs'
  "just use `company.get_financials()`" advice is company-scoped/latest and would regress B.
- **Backfill:** historical filings pick up the new concepts on the next `process_filing_facts` (the
  event-driven hook from #473) or a one-off `backfill_facts` run once the flag is on. No schema change.
- **Rollout:** default OFF; flip `RICHER_FINANCIALS_ENABLED=true` + run a one-off backfill to populate
  existing summarized filings, then the chart shows the new metric buttons and Copilot can cite them.
