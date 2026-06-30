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

## Review fixes (Gemini, PR #475 — all applied)
- **Guard derived liquidity on non-negative components (HIGH):** `working_capital`/`current_ratio` are
  derived BEFORE reconciliation and aren't all non-negative, so a corrupt negative current-assets/
  liabilities would persist garbage. Now only derived when `ca_v >= 0 and cl_v >= 0` (ratio: `cl_v > 0`).
- **Surface `current_ratio` on the chart (HIGH):** it was persisted but omitted from `FEATURED`. Added
  with a new `'ratio'` `FmtKind` (renders as a `2.50×` multiple — never "$"/"%"); no `as any` cast.
- **`current_ratio` → `NON_NEGATIVE_CONCEPTS` (MEDIUM):** defense-in-depth hard-reject (a ratio of two
  non-negative numbers can't be negative).
- Tests added: negative component ⇒ no derived liquidity; negative `current_ratio` hard-rejected;
  chart renders the Current Ratio button. 90 backend + 7 chart tests green; typecheck/lint clean.

---

# 2.6 Phase B — ground the AI narrative on the richer financials (branch claude/richer-narrative)

## Goal
Let the summary *narrative* cite the Phase A cash-flow/liquidity figures (they already reach the
chart + Copilot). Data-only, no new flag — gated transparently by `RICHER_FINANCIALS_ENABLED` (now on
in prod). Investor sources (SEC "How to Read a 10-K"; Investopedia) prioritise the cash-flow statement
+ liquidity, which is exactly the gap.

## Done (code)
- `openai_service.py`: extracted the grounding-block builder to module-level `build_xbrl_narrative_section`
  + `_format_xbrl_metric_value` + `_XBRL_NARRATIVE_SPEC` (behavior-preserving refactor → unit-testable).
  Added the 6 keys (investing/financing CF, current assets/liabilities, working capital, current ratio)
  in statement order, + a new `ratio` format ("2.50x"). The method now calls the helper.
- The 6 new keys are inert unless extraction populated them (flag on) → flag-off block is byte-for-byte
  identical → eval baseline unchanged. ROE/ROA/margins/FCF already grounded (verified — not re-added).
- New test `tests/unit/test_xbrl_narrative_section.py` (9 tests incl. a byte-for-byte legacy-block
  assertion). `py_compile` + `ruff` clean; 22 openai-related unit tests green (incl. structured-output).

## Eval gate (in progress)
- Golden set carries only revenue/net_income/eps facts → the eval measures **no-regression** (not a
  recall lift). Running the full set `--runs 3` against DeepSeek (`RICHER_FINANCIALS_ENABLED=true`) →
  `regression_gate --latest` vs pinned `baseline_scores.json` (deepseek-v4-pro). Smoke (AAPL/MSFT)
  scored aggregate 1.0, gate_fail 0.0.

## Next
- On gate pass: commit, push `claude/richer-narrative`, open draft PR (trailers + footer), watch CI.
- Follow-up idea (not this PR): extend the golden set with cash-flow/working-capital ground-truth facts
  so the eval can actually score the richer grounding (today it can't move recall).

---

# Eval golden-set extension — score the richer grounding (branch claude/eval-golden-set-richer)

## Goal
Add cash-flow + liquidity ground-truth facts so numeric recall MEASURES the Phase B grounding (not
just no-regression). Decisions: flip `RICHER_FINANCIALS_ENABLED` default → True (graduate the flag;
eval+CI+prod coherent); add the robust 5 (operating/investing/financing CF + current assets/liabilities).

## Done (code)
- `app/config.py`: `RICHER_FINANCIALS_ENABLED` default → True (+ comment).
- `evals/build_golden_set.py`: `EXTENDED_METRIC_CONCEPTS` (5 metrics, mirror product dicts);
  `_fact_for_metric` gained a `kind` param + INSTANT branch (`instant_series_with_currency`); core loop
  passes concepts+kind; ADDITIVE extended loop (a miss is NOT a `problem`); `verified` now counts only
  CORE metrics (banks/retailers missing a line stay verified).
- `tests/unit/test_accession_xbrl_extraction.py`: new sync test for the extended concepts + kind tags.
- py_compile + ruff clean; 74 unit tests green (sync + flag-sensitive + facts_service).

## Golden set rebuilt (canonical `build_golden_set`)
- +127 facts (80→207): operating/investing/financing CF ×26, current assets/liabilities ×25 (banks
  omit them — additive, no penalty). verified 26→25.
- **ASML collateral (documented, not a regression I caused):** with the pinned `edgartools==5.39.0`
  (CI/prod toolchain), ASML's FY2025 20-F tags revenue ONLY dimensionally (segment breakouts, no
  undimensioned consolidated total), so `duration_series_with_currency` correctly can't derive it →
  ASML unverified → auto-excluded. Phase A (#475) only added dicts (verified via `git show`), so this
  is a pre-existing edgartools/IFRS extraction limitation surfaced by rebuilding, not a code change.
  FLAG to founder: ASML prod summaries likely lack XBRL revenue grounding under 5.39.0 — separate follow-up.

## Eval gate (DONE)
- Flag-on bake-off (`--runs 3`, DeepSeek, n=75): gate_fail 0.0, precision 1.0, coverage 1.0,
  pass_rate 1.0, **recall 0.794** (now a live, non-saturated signal — was 1.0 over only rev/NI/eps).
- Re-pinned `baseline_scores.json` (recall 0.794, 25×3); `regression_gate --latest` PASS.
- Per-metric recall: revenue/net_income/eps 100%, operating_cash_flow 100%, financing_cash_flow 86%,
  investing_cash_flow 81%, **current_assets 36%, current_liabilities 31%**. Core never missed (no
  regression). The balance-sheet liquidity lines are the underused ones → headroom for a future
  prompt-prose tweak (the analyst prompt asks for "working capital adequacy" only qualitatively).

## Next
- Push babfd58 + baseline commit; open draft PR (trailers + footer); watch CI (`eval-baseline` now
  flag-on → reproduces recall 0.794 against the freshly pinned bar).
