# Dashboard Improvement Plan — launch-tier implementation summary

**Branch:** `claude/serene-mendel-8ju9kj` · **Date:** 2026-07-07 · **Spec:** `docs/dashboard-improvement-plan.md`

Implements the plan's launch tier — everything under §6 **"Quick wins (this week, before beta)"** and
**"Pre-beta polish"**, per the detailed specs in §2 and §3. The entire §6 **"Later (post-beta)"** tier is
out of scope and untouched. The dashboard feed API response shape is unchanged (frontend types did not move).

---

## What changed, mapped to the plan

### §2 — The "What's new" fix

- **Backend `compose_feed`** (`backend/app/services/dashboard_feed_service.py`) restructured to return
  **one item per watched company** (its newest eligible filing), companies ordered by that filing's date
  (newest first), tie-broken by `id` desc. A single metadata scan over every watched company's eligible
  history (xbrl deferred) both selects each company's newest filing (element `[0]`) and backs the
  prior-same-form comparison; the buggy "newest N across the whole watchlist" query is gone. Heads are
  rehydrated in one `id.in_(...)` query. `limit` now caps the **company** count. Query count stays at five;
  the Pydantic response models and the TS `FeedItem` type are untouched. Three docstrings updated
  (module, `compose_feed`, and the route in `backend/app/routers/dashboard.py`).
- **Eligible forms (§2.3):** 10-K / 10-Q, plus 20-F / 40-F only while `ENABLE_FPI_FILINGS` is on. Unchanged.
- **Tests (§2.8)** in `backend/tests/unit/test_dashboard_feed.py`: updated
  `test_compose_feed_orders_filters_and_annotates` (single company now yields one item) and added the 7
  specified tests (one-item-per-company, order-by-latest-desc, same-day tie-break by id desc, limit caps
  company count, skips companies without eligible filings, what-changed uses prior-same-form not feed,
  FPI form behind flag) via a new multi-company fixture. `test_compose_feed_empty_for_no_watchlist` kept.
  This is a deliberate feed contract change (recorded here per the repo's contract-change convention);
  `test_dashboard_feed.py` is a plain unit file, not a locked contract anchor.
- **Frontend `FilingFeed.tsx`:** 6-card cap; subline "The latest filing from each company you follow.";
  right-aligned **"See all {N} companies"** overflow → `/dashboard/watchlist`, where **N comes from the
  watchlist count** (passed in as `watchlistCount`), never `data.length` (which is capped at the fetch
  limit). Two distinct empty states: empty watchlist → onboarding; populated-but-no-eligible-filings →
  a quiet "Nothing new yet" line.
- **`WhatChangedCard.tsx`:** recency **"New"** badge (`Badge variant="new" icon={null}`) for filings ≤ 14
  days old (local-calendar-day comparison, null-safe); the §2.6 fallback copy ("No comparison figures for
  this one yet. The summary has the full picture."); and the **"Latest report"** label (paired with
  "Last filed" in Your companies, §3.2, to disambiguate the form-scope difference).
- **Empty-state onboarding (§2.5):** `FeedOnboarding.tsx` embeds the existing `WatchlistAddSearch` plus
  `PopularTickerChips.tsx` — 6 static mega-cap chips (AAPL, MSFT, NVDA, AMZN, GOOGL, TSLA) rendered with
  no network call, each wired to `addToWatchlist`. Deliberately not the trending endpoint (no quote fan-out).
- **Feed staleness (§2.7):** `queryKeys.dashboardFeed()` **and** `queryKeys.dashboardCalendar()` are now
  invalidated at every watchlist-mutation site — `WatchlistAddSearch` (add), `YourCompanies` (remove),
  the company-page toggle (`app/company/[ticker]/page-client.tsx`), and `PopularTickerChips` (add).
- **Copy (§2.6):** applied verbatim; passes the existing em-dash gate.

### §3 — Holistic restructure

- **`app/dashboard/page.tsx`** rebuilt as a two-column layout at `lg` (main ≈ 2/3, side ≈ 1/3):
  - Main: "Jump to any company" search · **What's new** (`FilingFeed`) · **Your companies** (`YourCompanies`).
  - Side: **Coming up** (`EarningsCalendar`, flag-gated) · **Saved summaries** (renders **only when > 0**) ·
    **Plan and usage** (a single compact strip).
  - **Quick-action cards removed.** Plan/usage demoted from two full cards to one strip; the ≥80% usage
    warning is surfaced as a slim banner at the **top** of the page (free plan only). Subscription/usage
    error+retry preserved in the strip; portal/logout/delete-summary mutations intact.
- **`YourCompanies.tsx`** (new): one compact row per company from `getWatchlistInsights` — logo · name ·
  ticker · **"Last filed {type} · {date}"** · summary-status badge · remove — plus the inline
  `WatchlistAddSearch` and a link to the full insights page. No new backend work.
- **Semantic divergence kept on purpose (§3.2):** the shared insights query keeps its any-form "latest
  filing" basis; the mismatch with the feed's periodic-report basis is resolved with the **labels**
  "Latest report" (feed) vs "Last filed" (Your companies). No form filter was added to the shared query.
- **`EarningsCalendar.tsx` polish (§3.2):** renders the already-fetched `eps_estimated`; replaces the
  self-hide-when-empty behaviour with a quiet "No earnings dates in the next two weeks." line (with a
  loading skeleton); the stale FMP flag comment is rewritten. **The production flag is not flipped** (see
  go-live steps).
- **`SummaryStatusBadge.tsx`** (new): the status→badge mapping extracted from the watchlist insights page
  into one shared component, now used by both that page and Your companies (identical labels/variants,
  including "Needs Attention"). This is the plan's "use the exact mapping" made a single source of truth.

### §6 — Pre-beta polish

- **Usage-warning banner** at the top when usage ≥ 80% (free plan) — see §3 above.
- **Same-day tie-break fix in `get_watchlist_insights`** (`backend/app/routers/watchlist.py`): the
  `func.max(filing_date)` join now orders by `id` desc and keeps the first (highest-id) row per company,
  so a same-day 10-K + 10-Q lands on a deterministic filing — matching the feed's `(filing_date, id)` desc
  tie-break, which the insights page and the Your-companies rows both rely on.
- **Save-summary discoverability** (`SummaryActionsBar.tsx`): the Save button is promoted from secondary to
  **primary** so the affordance reads as the main action a signed-in reader takes, rather than a low-key
  optional one.
- **Form-type filter-chip groundwork (design only):** see "Groundwork / deferred" below — this item is
  explicitly "design only, ships with 8-K rows," and 8-K event rows are in the out-of-scope Later tier,
  so no premature UI was built.

### Doc-drift fixes (§3.2 hygiene; code is truth)

- **`CLAUDE.md`:** the stale `/api/compare` reference → `GET /api/summaries/filing/{id}/what-changed`
  (verified: no `/api/compare` router exists; smoke test `test_compare_router_is_gone` locks it at 404).
- **`docs/adr/0003-edgartools-for-sec-data.md`:** noted the edgartools pin has advanced from the ADR's
  `>=5.12.0` floor to `>=5.40.1` (`requirements.in`), resolved to `==5.40.1` in `requirements.txt`.
- **`frontend/lib/featureFlags.ts`:** the `ENABLE_CALENDAR` comment rewritten — the FMP dependency is
  retired; the backend now reads the owned `earnings_events` table.

---

## Verification (all green)

- **Backend:** `ruff check .` clean · `bandit -r app -ll` clean (0 medium/high) · `pytest` **1389 passed,
  2 deselected** (fast lane; includes the 8 new/updated `test_dashboard_feed.py` tests).
- **Frontend:** `eslint . --max-warnings 0` clean · `tsc --noEmit -p tsconfig.ci.json` clean ·
  `vitest run` **331 passed (70 files)**, including the em-dash gate · `next build` OK.
- **Design system:** the DESIGN_SYSTEM.md §12 legacy-color grep returns nothing across `app components
  features`; no raw durations/beziers in the changed files. Both themes were built with theme-paired
  tokens throughout (no single-theme colors); a live both-theme preview check is a good final step on Vercel.

### Adversarial review pass (findings fixed)

Four independent reviewers checked the diff against §2/§3/§6. Confirmed findings, all resolved:

- **FilingFeed empty-state** treated an unknown watchlist count (`undefined` while the insights query is
  loading or errored) the same as a known-empty watchlist, so it could flash the onboarding panel for a
  returning user, or render "Follow your first company" alongside the Your-companies error card. Fixed:
  the onboarding shows only when the watchlist is **known-empty** (`watchlistCount === 0`); otherwise the
  quiet "Nothing new yet" state.
- **`isRecentFiling`** diffed two local midnights, so a filing exactly 14 days old across a fall-back DST
  week computed as 14.04 and dropped the "New" badge a day early. Fixed with DST-immune `Date.UTC`.
- **Test strength:** two of the new backend tests (`limit_caps_company_count`,
  `orders_companies_by_latest_filing_desc`) originally used one-filing-per-company fixtures, so they would
  also pass on the old buggy code. Fixtures strengthened to give a company multiple filings, so each test
  now fails on the pre-fix "newest N filings across the watchlist" behaviour.

---

## Manual go-live steps (for the founder — left deliberately, per the guardrails)

Nothing below was changed in this branch; these are the switches to flip in the target environment.

1. **Earnings calendar (§3, §7).** Before flipping the flag, confirm `earnings_events` is seeded and fresh
   in **production**:
   - Check that rows exist with `event_date >= today` (e.g. a one-off Cloud SQL query
     `SELECT count(*) FROM earnings_events WHERE event_date >= CURRENT_DATE;`, or inspect the
     `earnings-calendar-refresh` job's last run).
   - If empty/stale, run the refresh once — the Cloud Run job **`earningsnerd-earnings-calendar-refresh`**,
     or `POST /internal/jobs/earnings-calendar-refresh` (requires the internal token). It ingests Alpha
     Vantage bulk estimates + the EDGAR 8-K Item 2.02 sweep.
   - Then set **`NEXT_PUBLIC_ENABLE_CALENDAR=true`** on Vercel and redeploy the frontend. This also lights
     up the `/calendar` page and its nav entries (intended — the market-wide calendar endpoint is live).
     The render path degrades to the quiet "No earnings dates…" line if the table is empty, so the risk of
     flipping is low, but seeding first is what makes the widget useful on day one.
2. **Other production flags — leave as-is.** No production env vars or feature flags were changed. In
   particular `ENABLE_FPI_FILINGS`, `ENABLE_INSIDER_ACTIVITY`, `ENABLE_ANALYSIS`, and `NOTABLE_FILINGS_ENABLED`
   keep their current defaults.

---

## Groundwork / deferred

- **Form-type filter chips (§6, "design only").** Intentionally not built as UI. With the feed now
  one-card-per-company over 10-K/10-Q only, there is nothing to filter yet — form-type chips become
  meaningful when the labeled **8-K "event" rows** join the feed (a post-beta, out-of-scope item, §2.3).
  Recommended design when that lands: a chip row above the two-column grid, populated from the distinct
  `filing_type`s actually present in the feed response (mirroring the company page's
  `availableFilingTypes` pattern), hidden while only periodic reports exist, and driving a client-side
  filter of the feed items. It should ride the `eightk_coverage` Pro entitlement per §2.3.
- **Double add-search on a fully empty watchlist (by design):** for a brand-new user, both the feed
  onboarding and the Your-companies empty state mount a `WatchlistAddSearch`, so two identical add-search
  inputs appear. This is faithful to the plan (§2.5 mounts it in the feed empty state; §3.2 mounts it in
  Your companies) and each instance has isolated local state, so nothing breaks — flagged only so the
  founder can collapse it later if the redundancy bothers them.

## Out of scope (untouched, per the brief)

The entire §6 "Later (post-beta)" tier: Form 4 insider module, 8-K event rows, weekly brief, trend
sparklines, user-facing full-text search, redline section diffs, 13F holdings, and the dashboard
`AnalysisTeaser` hook. Also the incidental `datetime.now()` cleanup the plan parks in the trending route.
