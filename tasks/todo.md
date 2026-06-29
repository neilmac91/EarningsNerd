# Task: Multi-period trend in "what changed" (roadmap item 2.5)

## Context
2.5 wants the company's multi-period financial trajectory shown alongside the period-over-period
"what changed" diff on the filing page — display-only, off the already-stored `financial_fact`
series (so no summary-pipeline touch, no eval impact).

A recon found the data + the UI already exist:
- `financial_fact` holds the multi-period series, served by `GET /api/companies/{ticker}/fundamentals`
  (`getFundamentals(ticker)`), and rendered by `FundamentalsTrendChart` on the company page.
- `FundamentalsTrendChart` is fully self-contained: takes only `ticker`, self-fetches (React Query),
  self-gates (renders nothing on error / until facts exist), design-system compliant.

## Decision (simplest, lowest-risk — reuse over new)
Render the existing `FundamentalsTrendChart` on the filing page, in the "what changed" area, behind
the same `ENABLE_FINANCIAL_CHARTS` flag the company page uses. **Frontend-only, ~2 lines** — no
backend change, no API-contract change, no new chart code, no eval risk. (The recon's alternative —
extending the change-report response with a `metric_series` — was rejected as more surface for no
real gain, since the series is already served and the component already exists.)

## Plan
- [x] Dynamic-import `FundamentalsTrendChart` in `page-client.tsx` (ssr:false, like `FinancialCharts`;
      no loading fallback so it can self-gate to null without flashing an empty card)
- [x] Render `{ENABLE_FINANCIAL_CHARTS && filing.company?.ticker && <FundamentalsTrendChart .../>}`
      right after `<WhatChanged>` (trajectory next to the diff)
- [x] Verify: typecheck (narrowing) + lint + full vitest (50 files / 224 tests) — all green
- [ ] Commit + push + open draft PR

## Notes
- **Zero eval impact:** reads only `financial_fact` (static, already-stored), no LLM / pipeline.
- **Ships behind `ENABLE_FINANCIAL_CHARTS`** — same flag/state as the company-page chart, so it
  lights up together when the founder flips the flag (consistent rollout); dark until then.
- No new test: this is wiring of an existing, already-tested, self-contained component (identical
  pattern to the company page); covered by typecheck + lint + the unchanged suite.

## Review
- Maximally surgical: 2.5 turned out to be a reuse, not a build — the series, endpoint, client, and
  a polished design-compliant chart all already existed; the only gap was rendering it in the filing
  context. Frontend-only, flag-gated, no eval/backend exposure.
