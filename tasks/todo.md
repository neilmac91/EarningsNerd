# Task: PR #470 post-review amendments (multi-period fundamentals trend)

A 6-agent quality review of PR #470 surfaced two issues to fix before the chart goes live
(flag is dark today). Founder approved fixing both, with the recommended duplication approach.

## Fix 1 — Period-mixing under an "Annual figures" label (HIGH, data-defensibility)
**Root cause (verified):** `get_fundamentals` filters only `is_latest=True` with **no fiscal_period
filter** (`facts_service.py:617-622`). `backfill_facts` ingests *all* XBRL-bearing filings incl.
10-Qs (`:547`); 10-Q facts get `fiscal_period=None`, not `"FY"` (`_fiscal_period`, `:75`); the chart
buckets bars purely by `fiscal_year` (`FundamentalsTrendChart.tsx:95`). So a quarterly (3-month) bar
can sit beside an annual bar under a footnote that says "Annual figures." Pre-exists on the live
company page too (same read path) — the read-path fix heals both surfaces.

- [ ] Add `.filter(FinancialFact.fiscal_period == "FY")` to `get_fundamentals` (annual-only series),
      update the docstring to state the FY contract.
- [ ] Test: a company with a FY fact + a quarterly (fiscal_period=None) fact for the same concept →
      only the FY point is returned. (TestGetFundamentals, `@pytest.mark.requires_db`.)

## Fix 2 — Filing-page duplication (HIGH, design) — approach (b) replace
**Root cause (verified):** filing page renders BOTH `FundamentalsTrendChart` (new) and
`FinancialCharts` (`#3E8E84` current-vs-prior bars of overlapping metrics) under the *same*
`ENABLE_FINANCIAL_CHARTS` flag → two stacked bar charts + the metrics table. The **company page uses
only `FundamentalsTrendChart`** — so replacing on the filing page makes it consistent.
`FinancialCharts`' unique StatCards grid is acceptable to drop: `FinancialMetricsTable` (current/prior
numbers) + `WhatChanged` (delta pills) already cover current-vs-prior, and the company page has no
StatCards either.

- [ ] Remove the `FinancialCharts` dynamic import + render block from the filing page
      (`page-client.tsx`), and the now-orphaned `ChartsSkeleton` (only used by that import; else
      ESLint `--max-warnings 0` fails). Leave `FinancialCharts.tsx` and the company page untouched.
- [ ] Heading context (the design [medium]): add an optional `subtitle?: string` prop to
      `FundamentalsTrendChart` (default off → company page unchanged) and pass a filing-context line
      on the filing page (the chart spans the company's multi-year history, not just this filing).
- [ ] Test: the new `subtitle` renders when passed (and is absent by default).

## Verify
- [ ] Backend: `python3 -m py_compile` the changed files (pytest/pydantic unavailable locally; the FY
      test runs on CI `backend-tests` where a DB is present).
- [ ] Frontend: `tsc --noEmit` (subtitle prop narrowing), `eslint --max-warnings 0` (no orphaned
      ChartsSkeleton), full `vitest` (incl. the new subtitle assertion + unchanged FinancialCharts
      spec, which still tests the component directly).
- [ ] Confirm CI green on the pushed branch; PR #470 already open (draft).

## Notes
- Minimal-impact: shared `FinancialCharts.tsx` is NOT modified, so its other consumer (company page)
  and its existing spec are unaffected. The FY fix is a single read-path filter → fixes both pages.
- No new theme tokens (subtitle reuses the WCAG-safe muted pair) → no both-themes design risk.

## Review
- **Fix 1 (FY filter):** one-line read-path filter in `get_fundamentals` + a `requires_db` test
  asserting a quarterly point is dropped beside the FY value. Centralized at the read path, so it
  heals both the filing and company charts; the "Annual figures" footnote is now true.
- **Fix 2 (dedup):** filing page now renders only `FundamentalsTrendChart` (matching the company
  page) — removed the `FinancialCharts` import + render block + orphaned `ChartsSkeleton`.
  `FinancialCharts.tsx` itself and the company page are untouched (its existing spec still passes).
  Added an optional `subtitle` prop (default off → company page unchanged) and pass a filing-context
  line; covered by a new spec.
- **Verified:** `py_compile` OK; `npm run typecheck` (tsconfig.ci.json) clean; `npm run lint` clean;
  `vitest` 50 files / 225 tests green (was 224 — +1 subtitle test). Backend FY test runs on CI.
- **Scope honored:** surgical, reuse-over-new, minimal blast radius; the one shared-component change
  is additive and default-inert.
