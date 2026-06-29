# Task: Per-ADS EPS display (roadmap item 1.5)

## Context
The ADS-ratio correctness layer (item A / #461) computes a per-ADS EPS block
(`{value, ordinary_per_ads, currency, as_of, source, arithmetic}`) for the four
ratio≠1 ADRs (BABA 8 / TSM 5 / JD 2 / PDD 4) in `extract_standardized_metrics`.
A reconnaissance pass found it **never reached the frontend**: `attach_normalized_facts`
used the standardized metrics only to backfill prior periods, and the frontend
`MetricItem` had no per-ADS field. So the correct per-ADS figure — the most
credibility-sensitive number on an ADR report — was computed but invisible.

## Decision
- **Backend (additive):** in `attach_normalized_facts`, merge `xbrl_metrics[eps_key].per_ads`
  onto the EPS row of `financial_highlights.table` (the JSON the API serializes). New key only;
  never alters the as-filed per-ordinary-share `current_period`, so it can't regress the eval
  baseline (the golden set already accepts per-ADS as a valid alt-value).
- **Frontend:** add `PerAdsValue` + optional `per_ads` to `MetricItem`; one shared `PerAdsNote`
  component renders the per-ADS figure with its conversion **arithmetic inline** and the
  **sourced + dated** ratio in the tooltip — auditable, never an unexplained number (1.5's contract).
- Reuse the existing financial-highlights rendering (`FinancialMetricsTable`, `SummaryFinancials`);
  no new endpoint, no schema/migration.

## Plan
- [x] Backend: merge `per_ads` onto the EPS row in `attach_normalized_facts` (`app/schemas/summary.py`)
- [x] Frontend type: `PerAdsValue` + optional `per_ads` on `MetricItem` (`types/summary.ts`)
- [x] New `PerAdsNote` component (figure + inline arithmetic + sourced/dated tooltip)
- [x] Render it in `FinancialMetricsTable` (EPS current-period cell) + `SummaryFinancials` (EPS bullet)
- [x] Backend test: per_ads merged onto EPS row, value untouched, absent for domestic/non-dict/no-metrics
- [x] Frontend test: table renders per-ADS figure + arithmetic when present, omits otherwise
- [x] Verify frontend locally: vitest (48 files / 217 tests) + typecheck + lint (max-warnings 0) — green
- [ ] Commit + push + open draft PR

## Notes / follow-ups
- Backend test runs in CI (`backend-tests`) — `pytest`/`pydantic` aren't installed in this sandbox,
  so the backend change is verified by inspection + CI; the frontend is verified locally.
- Eval: the change is additive (a new key on the EPS row), so it should be eval-neutral; re-run the
  eval on the ADR golden-set members (BABA/TSM/JD/PDD) before relying on it in prod as belt-and-suspenders.
- Next (item 1.4): upgrade headline-figure source links from the external SEC `#:~:text=` deep-link to
  the in-app `requestHighlight` scroll-highlight (separate PR; needs grounding the SourceTrace wiring).

## Review
- 1.5's gap was a backend→frontend plumbing miss, not missing data: the per-ADS figure existed but
  `attach_normalized_facts` dropped it. Fix is a 4-line additive merge + a small presentation layer.
- Strictly additive end to end — no existing event/value/schema changed; the as-filed
  per-ordinary-share EPS is untouched (backend test asserts this), so the perfect eval baseline holds.
- Auditable by construction: the per-ADS figure is always shown WITH its ratio + arithmetic and a
  dated source, so the correction can be verified rather than trusted (the accountability moat, #2).
