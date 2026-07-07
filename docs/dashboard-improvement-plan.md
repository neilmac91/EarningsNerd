# Dashboard Improvement Plan

**Date:** 2026-07-07 · **Status:** Recommendation (nothing here is built yet) · **Scope:** the signed-in dashboard (`/dashboard`), going into public beta next week.

This plan is grounded in the code as of `main` at `659cdde` (every file:line reference was read), in competitor research across 14 products (URL log in §4), and in open-source research with licences verified on the repos themselves (URL log in §5). Method notes and anything that could not be verified are in §7.

---

## 1. Executive summary

### What the dashboard is for

A returning user should get three answers in under 30 seconds:

1. **Did any of my companies file something new, and what changed in it?** One card per company, newest filing, with the metric-delta chips and a one-click path to the summary.
2. **What's coming up?** The next earnings dates for the companies I follow.
3. **Where do I pick up my own work?** Saved summaries and anything still generating.

That makes the dashboard a *filing-event hub*, not a market terminal. This matches how the strongest filing-centric comparables work: BamSEC's logged-in homepage is a documents feed for watched companies, Quartr's pitch is "your watchlist is your dashboard," and TIKR organizes its watchlist feed by "what is coming up versus what just happened." None of them lead with prices, and neither should EarningsNerd: the product's edge is grounded filing analysis, so the dashboard should surface filings and what changed in them, with prices as seasoning at most.

Everything else in this plan serves that job statement.

### The top moves, in priority order

| # | Move | Impact | Build effort | Infra cost |
|---|------|--------|-------------|------------|
| 1 | Fix "What's new" to one-newest-filing-per-company, plus its copy (§2) | High: this is the broken core loop | ~1 day incl. tests | $0 |
| 2 | Restructure the layout: merge the watchlist into a "Your companies" status section with inline add, remove the quick-action cards, demote plan/usage (§3) | High: the page currently buries what matters and pads what doesn't | 1–2 days | $0 |
| 3 | Turn on the earnings calendar that is already built (§3, §5). The flag comment claiming it needs an FMP key is stale; it now runs off the owned `earnings_events` table | High: fills the "coming up" half of the job | Hours, plus a production seed check | $0 |
| 4 | Empty-state onboarding: one-tap popular-ticker chips and the existing `WatchlistAddSearch` on the dashboard itself (§2, §3) | Medium-high: most beta users arrive with an empty watchlist | ~½ day | $0 |
| 5 | Post-beta value-adds, all $0-infra and MIT-clean: persisted Form 4 insider activity, XBRL trend sparklines, a weekly watchlist brief, redline filing diffs, 13F holdings (§5, §6) | Medium each, compounding | S–M each | $0 (AI brief: pennies) |

A recurring theme made this plan cheaper than expected: **most of the "new" value is already in the repo, dark.** The earnings calendar, Form 4 parsing, multi-period financial facts, a rich change-report component, a sparkline primitive, and recharts are all built and unshipped. The main cost of this plan is flipping things on carefully, not building things.

---

## 2. The "What's new" fix (build-ready spec)

### 2.1 Root cause

The section is `FilingFeed` (`frontend/features/dashboard/components/FilingFeed.tsx`), which calls `GET /api/dashboard/feed?limit=20` (`frontend/features/dashboard/api/dashboard-api.ts:39-42`) and renders every returned item as a `WhatChangedCard` in a two-column grid with no client-side dedupe or cap (`FilingFeed.tsx:52-56`).

The bug is server-side, in `compose_feed` (`backend/app/services/dashboard_feed_service.py:226-233`):

```python
filings = (
    db.query(Filing)
    .options(joinedload(Filing.company))
    .filter(Filing.company_id.in_(company_ids), Filing.filing_type.in_(form_types))
    .order_by(desc(Filing.filing_date))
    .limit(limit)
    .all()
)
```

This takes the newest 20 filings **across the whole watchlist**, not per company. A user following two companies gets up to 20 of their historical 10-Ks and 10-Qs, which is exactly the "entire filing history as padding" the dashboard shows today. The docstring says the query "clones the watchlist-insights query pattern," but it cloned the N+1-freeness, not the latest-per-company semantics.

### 2.2 The fix

Restructure `compose_feed` (`dashboard_feed_service.py:215-292`). The router (`backend/app/routers/dashboard.py:66-76`), the Pydantic response models, and the TypeScript `FeedItem` type all stay unchanged, so the frontend keeps working with no type changes.

1. **Unchanged:** fetch watchlist `company_ids`; return `[]` if empty; `_feed_form_types()` keeps the `ENABLE_FPI_FILINGS` gate (`:38-44`).
2. **Move the metadata scan first.** The function already runs a second query (`:240-249`) loading each feed company's full 10-K/10-Q history with `defer(Filing.xbrl_data)`, to find each filing's prior same-form filing. Run that scan first, over **all** `company_ids`, and extend its ordering to `(Filing.company_id, desc(Filing.filing_date), desc(Filing.id))` so ties are deterministic. Build the `by_company` dict exactly as today.
3. **Pick heads in Python.** Each company's newest eligible filing is now simply `by_company[cid][0]`:
   ```python
   heads = [rows[0] for rows in by_company.values()]
   heads.sort(key=lambda f: (f.filing_date, f.id), reverse=True)
   heads = heads[:limit]
   ```
   `limit` semantically becomes "max companies shown"; note that in the docstring.
4. **Delete the buggy query** (`:226-233`) and rehydrate the heads with one `Filing.id.in_(...)` query using `joinedload(Filing.company)` (loads `xbrl_data` and company for at most `limit` rows), reordered to `heads` order via an id-to-position map.
5. **Unchanged:** `_prior_same_form` lookups against `by_company`, the prior-XBRL batch load, the summary-status batch, and item assembly (`:251-292`).

Also update the three docstrings that describe the old behavior: the module docstring (`dashboard_feed_service.py:3-6`), `compose_feed`'s (`:216-217`), and the route's (`dashboard.py:72-75`).

**Why this shape and not the alternatives.** The per-company scan must exist anyway for the prior-filing comparison, so the newest-per-company is element `[0]` for free; re-deriving it in SQL is redundant work. The obvious SQL alternative, mirroring the `func.max(Filing.filing_date)` group-by in `get_watchlist_insights` (`backend/app/routers/watchlist.py:246-265`), has a latent bug this feed would inherit: when a company files a 10-K and a 10-Q on the same date, the join on `(company_id, max_date)` returns both rows and the duplicate-company symptom reappears (the insights endpoint currently hides this by nondeterministic dict overwrite). A `row_number()` window function would work but has zero precedent in `backend/app` and complicates `joinedload`. The chosen shape keeps the query count at five, rides the existing `ix_filings_company_type_date` index, and is the smallest diff.

**Blast radius.** `compose_feed` has exactly one caller (`dashboard.py:76`). `change_report_service` imports only the pure `compute_what_changed` and does its own prior-filing lookup. The digest and alert paths don't touch the feed. Frontend consumption is only `getDashboardFeed` → `FilingFeed`.

**Scan width note.** The scan now covers every watched company's 10-K/10-Q metadata rather than one page's worth. Rows are metadata-only on a covering index; fine at beta watchlist sizes. If a pathological watchlist ever makes it slow, the escape hatch is a `func.max` pre-pass to shortlist the top-`limit` companies before the scan. Document it, don't build it.

### 2.3 Which filing types count as "new"

**Keep the current set: 10-K and 10-Q, plus 20-F/40-F only while `ENABLE_FPI_FILINGS` is on** (default off, `backend/app/config.py:314`). "Newest per company" means newest among these eligible forms.

Rationale, so this doesn't get relitigated later:

- These are the periodic reports the product actually summarizes and the only forms that carry the XBRL that powers the "what changed" chips (`dashboard_feed_service.py:30-33` documents this deliberately).
- **Form 3/4/5 stay out.** They aren't even ingested into the `filings` table (`SCAN_FORM_TYPES = ["10-K", "10-Q", "8-K"]`, `backend/app/services/filing_scan_service.py:34`), and a Form 4 drop is not the same class of event as a quarterly report. Insider activity deserves its own labeled surface (§5.2), not feed slots.
- **8-K is a deliberate fast-follow, not v1.** 8-Ks are already ingested, but they have no XBRL, so today they'd render as neutral filler cards. When added, they should be visually distinct "event" rows (form badge, headline item type, no metric chips) and can align with the `eightk_coverage` entitlement that already exists as a forward-looking Pro flag (`backend/app/services/entitlements.py:106-108` area). That gives 8-K coverage a monetization story instead of noise.

### 2.4 Ordering, cap, and overflow

- **Ordering:** companies sorted by their newest filing's `filing_date` descending; tie-break `Filing.id` descending (covers the same-day 10-K + 10-Q case deterministically).
- **Backend cap:** keep `limit=20` (router clamps 1–50). Post-fix this means "up to 20 companies," which is plenty of headroom.
- **Frontend cap:** show the first **6** cards (three rows of the existing 2-column grid): `data.slice(0, 6)` in `FilingFeed.tsx:53`. When `data.length > 6`, render a right-aligned link under the grid: **"See all {N} companies"** → `/dashboard/watchlist`. That page (Watchlist insights) already is the all-companies, latest-filing-each view, so overflow needs no new page.
- **Recency badge:** filings aged ≤ 14 days get a "New" chip (`Badge variant="new" icon={null}`, the tonal recipe the watchlist page already uses at `frontend/app/dashboard/watchlist/page.tsx:37-53`). Because the feed now always shows each company's latest filing regardless of age, the badge is what distinguishes "fresh this week" from "their last report, months ago." Both states are useful; only one should shout.

### 2.5 Empty states

Two distinct states, currently conflated:

1. **Empty watchlist** (the common beta case): keep a `GuidanceCard`, but make it actionable. Embed the existing `WatchlistAddSearch` (`frontend/features/watchlist/components/WatchlistAddSearch.tsx`, today only on the insights page) plus a row of ~6 one-tap ticker chips wired to the existing `addToWatchlist(ticker)`. Source the chips from `GET /api/companies/trending` (most filings in 30 days, `backend/app/routers/companies.py:262`) so a new user's first follow pays off immediately with a fresh filing; fall back to a static mega-cap list (AAPL, MSFT, NVDA, AMZN, GOOGL, TSLA) if the endpoint returns nothing. This is the strongest onboarding pattern observed in the wild (§4: Last10K's ticker chips, stockanalysis.com's try-before-save watchlist, Yahoo's followable lists).
2. **Watchlist populated but no eligible filings yet** (companies just added, sync pending): a quieter one-liner, no CTA needed. Distinguishing the two takes one condition: the page already has the `watchlist` query in scope (`frontend/app/dashboard/page.tsx:54-59`).

### 2.6 Copy

Context first: a voice pass over dashboard/watchlist/calendar copy plus an AST-walking em-dash gate (`frontend/tests/unit/no-em-dash-copy.spec.ts`, which fails on any em-dash in user-visible strings) merged to `main` today in PR #576. The em-dash-laden copy the founder sees is production running a pre-#576 build; the tree is already clean and gated. What remains is the What's-new-specific copy below, which must also pass that gate.

| Where | Current (tree) | Recommended |
|---|---|---|
| Section heading (`FilingFeed.tsx:22-24`) | "What's new" (no subline) | Keep "What's new"; add subline: "The latest filing from each company you follow." |
| Card fallback line, when no XBRL deltas (`WhatChangedCard.tsx:73-75`) | "New 10-Q filed. Open it for the full breakdown." | "No comparison figures for this one yet. The summary has the full picture." (Honest about *why* there are no chips, and stops implying every filing is new.) |
| Empty, no watchlist (`FilingFeed.tsx:46-50`) | "No new filings yet" / "Add companies to your watchlist. When they file a 10-K or 10-Q, you'll see what changed here first." | "Follow your first company" / "Search above or tap a ticker below. New filings land here the day they hit EDGAR." (+ chips + inline add, §2.5) |
| Empty, watchlist quiet (new state) | (doesn't exist) | "Nothing new yet" / "We're syncing filings for your companies. Check back in a few minutes." |
| Error state (`FilingFeed.tsx:35-44`) | "Couldn't load your feed" / "Please retry in a moment." | Keep as is. |
| CTA labels (`WhatChangedCard.tsx:20-25`) | "Read summary" / "Generating…" / "Regenerate summary" / "Generate summary" | Keep as is. |
| Dashboard watchlist empty state (`dashboard/page.tsx:473-477`) | "Add companies to your watchlist from company pages." | "Track a company with the search above, or from any company page." (The "company pages only" claim went stale when `WatchlistAddSearch` shipped.) |

Voice rules for any new dashboard string: plain sentences, no em-dashes (the gate enforces this), say what the user gets rather than describing the feature, and never label old content as new.

### 2.7 Feed staleness (fix in the same PR)

Nothing invalidates the feed when the watchlist changes, so a user who adds a company sees no feed update for the rest of the session (global `staleTime` 60s, no focus refetch, `frontend/app/providers.tsx:27-34`). Add `queryKeys.dashboardFeed()` invalidation at all three watchlist mutation sites:

- `frontend/features/watchlist/components/WatchlistAddSearch.tsx:50-58` (currently invalidates `watchlist` + `watchlistInsights` only)
- `frontend/app/dashboard/page.tsx:74-84` (currently `watchlist` only; also missing `watchlistInsights`, same one-line fix)
- `frontend/app/company/[ticker]/page-client.tsx:126-128` (currently `watchlist` only; same)

Include `queryKeys.dashboardCalendar()` at the same sites; it's watchlist-derived too, and invalidating an unmounted query is harmless while the flag is off.

### 2.8 Tests

All in `backend/tests/unit/test_dashboard_feed.py`, which is a plain unit file, **not** one of the locked contract anchors (the lock set is T1–T10, auth flow, and Stripe webhooks). Because this is a deliberate contract change for the feed ("newest N filings" → "newest filing per company"), record it explicitly in the PR body per the repo's contract-change convention.

- **Update** `test_compose_feed_orders_filters_and_annotates` (`:177-196`): the single-company scenario now yields one item, so line 187 expects `["10-Q"]` and the `items[1]` assertions (lines 195-196) go away. Keep lines 188-193; the surviving "Revenue up" assertion proves the prior-filing comparison still reaches history the feed no longer returns.
- **Add** (needs a multi-company variant of the `_feed_scenario` fixture):
  1. `test_compose_feed_one_item_per_company` — 2 companies, ≥2 eligible filings each → exactly 2 items, each company once, each item that company's newest. This is the regression test that fails on today's code.
  2. `test_compose_feed_orders_companies_by_latest_filing_desc`
  3. `test_compose_feed_same_day_tie_breaks_by_id_desc` — same-day 10-K + 10-Q → one item, higher id wins.
  4. `test_compose_feed_limit_caps_company_count` — 3 companies, `limit=2` → the stalest company drops.
  5. `test_compose_feed_skips_companies_without_eligible_filings` — 8-K-only company absent; fully ineligible watchlist → `[]`.
  6. `test_compose_feed_what_changed_uses_prior_same_form_not_feed` — history [10-Q, 10-K, 10-Q] → the feed's one 10-Q compares against the older 10-Q, skipping the 10-K.
  7. `test_compose_feed_fpi_form_behind_flag` — 20-F surfaces only when `ENABLE_FPI_FILINGS` is on (patch `settings`, not env, per the conftest convention).
- **Keep** `test_compose_feed_empty_for_no_watchlist` as is.

Estimated effort for all of §2: **~1 day** (backend restructure + 8 tests ≈ half day; frontend cap/badge/empty-states/invalidations/copy ≈ half day). Infra cost: **$0**.

---

## 3. Holistic restructure

### 3.1 What's off today

Current order (`frontend/app/dashboard/page.tsx:186-479`): trial banner → search card → What's new → (flag-dark calendar) → Subscription + Usage cards → three quick-action cards → Saved summaries → Watchlist.

1. **The watchlist is at the bottom of the page it powers.** What's new derives entirely from it, yet managing it means scrolling past billing widgets. And its cards carry nothing but name + ticker + remove, while a much richer per-company view (latest filing, summary status) already exists behind `GET /api/watchlist/insights`.
2. **Prime real estate goes to Subscription and Usage.** Two full-width cards for information that changes monthly. The one part with daily urgency (approaching the free summary limit) is buried inside one of them.
3. **The quick-action cards duplicate chrome.** "View plans" duplicates the Pricing nav link; "Watchlist insights" duplicates the user menu; "Search companies" duplicates both the nav Search link and the search box directly above it, and it links to `/` (the marketing homepage) rather than `/search` (`dashboard/page.tsx:328`). All three can go.
4. **Saved summaries renders a large empty block** for the majority of users who have saved nothing, while the save action itself is a low-key secondary button that only appears post-generation on filing pages (`SummaryActionsBar.tsx:47-54`).
5. **The calendar is dark behind a stale comment.** `featureFlags.ts:104-109` says the widget waits on an FMP key, but the backend retired the FMP path: `calendar_service.py` now reads the owned `earnings_events` table, seeded by the Alpha Vantage + EDGAR 8-K engine (`earnings_calendar_service.py:413-476`) via the deployed `earnings-calendar-refresh` job (table migration `backend/migrations/20260703_create_earnings_events.sql`).
6. **The feed goes stale on watchlist edits** (§2.7), and the dashboard offers no way to add a company at all; its empty-state copy points users away to company pages.

### 3.2 Recommended layout

Two columns at `lg` (main ≈ 2/3, side ≈ 1/3); mobile stacks in this order. All composition from the existing `components/ui` kit (Card, Badge, GuidanceCard, DataTable, Skeleton) per `frontend/DESIGN_SYSTEM.md`.

```
┌──────────────────────────────────────────┬────────────────────┐
│ [trial banner, when active]              │                    │
│ Jump to any company  [search]            │  Coming up         │
│                                          │  (earnings dates   │
│ What's new                               │   for watchlist)   │
│  one card per company, newest filing,    │                    │
│  metric chips, New badge, cap 6,         │  Saved summaries   │
│  "See all N companies" overflow          │  (only when > 0)   │
│                                          │                    │
│ Your companies                           │  Plan and usage    │
│  one compact row per company:            │  (single compact   │
│  logo · name · ticker · latest-filing    │   strip)           │
│  chip · summary-status badge · remove    │                    │
│  + inline WatchlistAddSearch             │                    │
│  → "Open watchlist insights"             │                    │
└──────────────────────────────────────────┴────────────────────┘
```

- **What's new** stays the lead module (the fixed feed is the product loop). The feed answers "what just happened."
- **Coming up** answers "what's next," pairing with the feed exactly the way TIKR frames its watchlist feed ("what is coming up versus what just happened"). Ship it by flipping `NEXT_PUBLIC_ENABLE_CALENDAR` **after** verifying `earnings_events` is actually seeded in production (§7). Three small polish items while touching it: render the already-fetched `eps_estimated` (fetched but unrendered, `dashboard-api.ts:36`), replace the self-hide-when-empty behavior (`EarningsCalendar.tsx:21`) with a quiet "No earnings dates in the next two weeks." line so the section doesn't appear and vanish confusingly, and rewrite the stale flag comment. Note the flag also lights up the `/calendar` page and its nav entries (`Header.tsx:22,30`, `UserMenu.tsx:31`), which is a feature, not a problem: the market-wide calendar endpoint behind it is also live.
- **Your companies** merges the bottom watchlist strip with management affordances: one compact row per company built from the existing `getWatchlistInsights` response (latest filing type + date, summary-status badge using the exact mapping at `watchlist/page.tsx:37-53`), a remove action, the inline `WatchlistAddSearch`, and a link to the full insights page. Zero new backend work. This is the "one row per company reassurance table" pattern from Koyfin/stockanalysis/Zacks, with filing-status columns instead of price columns.
- **Saved summaries** renders only when the user has any; the empty block disappears. (Improving save discoverability on the filing page is a separate later item.)
- **Plan and usage** collapses to a single compact strip at the bottom of the side column: plan badge, usage meter, one link (manage or upgrade). Keep the existing ≥80% warning logic, but when it triggers, surface a slim banner near the top of the page where it will actually be seen (`dashboard/page.tsx:302-316` has the logic already).
- **Quick-action cards: removed.** Nothing replaces them; the nav and the on-page modules now cover all three destinations.

Same-PR hygiene (docs-vs-code rule: code is truth): fix the stale `ENABLE_CALENDAR` comment; fix CLAUDE.md's reference to `/api/compare` (no such route exists; the cross-filing surface is `GET /api/summaries/filing/{id}/what-changed`); optionally note in ADR-0003 that the pin is now `edgartools==5.40.1` rather than the `>=5.12.0` floor the ADR text mentions.

Estimated effort for §3: **1–2 days** (layout + Your companies ≈ 1 day; calendar flip + polish ≈ 2–4 hours after the seed check; copy and doc fixes ≈ 1 hour). Infra cost: **$0**. Verification per the design-system done-gate: legacy-color grep clean, both themes checked on preview.

---

## 4. Competitor patterns

Fourteen comparables were researched: BamSEC, Quartr, TIKR, Last10K, stockanalysis.com, Fintel (Group A: filing-centric); Earnings Whispers, Zacks, Yahoo Finance (Group B: earnings/calendar); Koyfin, Simply Wall St, Seeking Alpha, Fiscal.ai, Stocktwits (Group C: watchlist/portfolio). Signed-in dashboards sit behind auth walls, so findings mix direct observation of public pages with inference from help docs and reviews; each claim below held up across at least one directly fetched page unless marked inferred. Full URL list at the end of this section.

**The structural insight:** filing-centric tools are feed-led (BamSEC's homepage documents feed, Koyfin's Watchlist News, TIKR's Filings tab, Fintel's per-watchlist tabs); price-centric tools are table-led (stockanalysis, Zacks, Yahoo, Seeking Alpha). The best products do both: a chronological feed as the reason to return, and a per-company table as the reassurance nothing was missed. §3's layout is exactly that hybrid.

Patterns worth adopting, ranked by fit:

| # | Pattern | Seen at | Adoption here |
|---|---------|---------|---------------|
| 1 | Watchlist-scoped new-documents feed, form-type aware, each item deep-linking to the artifact | BamSEC (homepage Documents Feed), Koyfin (Watchlist News with "10-Qs or 8-Ks" filters and topic muting), TIKR, Fintel | This *is* the fixed What's new (§2). Form-type filter chips are a later nice-to-have once 8-Ks join the feed. |
| 2 | Split the page by time direction: "coming up" vs "just released" | TIKR (verbatim framing), Koyfin (portfolio-linked earnings calendar), Quartr (tailored calendar), Earnings Whispers (confirmed-date toggle) | Feed + calendar pairing in §3.2. The calendar keeps the dashboard alive on quiet days, which matters for an episodic product. |
| 3 | One compact status row per company | stockanalysis (watchlist table + averages), Koyfin (column views), Zacks (rank per row), Seeking Alpha (ratings columns) | "Your companies" (§3.2), with filing-status columns rather than price columns; that's the differentiated version. |
| 4 | Email digest as the retention engine, alerts scoped to the list | Zacks (free daily portfolio email), Seeking Alpha (per-portfolio digest with Subscribe), Simply Wall St (weekly email), BamSEC (watched-company alerts, Pro) | Already shipped (`run_daily_digest`, prefs, Pro realtime). Just keep feed and digest presenting the same "new" set, which the §2 fix guarantees since both derive from the watchlist + latest filings. |
| 5 | "What changed vs prior filing" as a visible affordance | Last10K (redline/blackline "track changes", $99/yr), BamSEC (Document Comparison, $69/mo Pro), Quartr ("spot inflection points") | Competitors paywall this; EarningsNerd's delta chips and change report are free. Keep the chips on every card (already the design) and treat the free change report as a marketing wedge, not a cost. |
| 6 | Empty-state onboarding: popular-ticker chips, try-before-commit, curated lists | Last10K (FAANG chips), stockanalysis (anonymous watchlist that works before signup), Yahoo (followable curated lists), Stocktwits ("Most New Watchers") | §2.5's chips + inline add. The anonymous-watchlist pattern is worth considering post-beta. |
| 7 | A daily/weekly AI brief ("Wake up informed") | Quartr (daily recaps), Zacks (daily brief) | Later (§6). Must respect the filing-only rule: a labeled cross-filing surface where each line derives from a single filing. |
| 8 | Freemium gates depth, not surface | TIKR (full UI free, history-gated), stockanalysis (alert counts 10/100/unlimited), Fiscal.ai (auto Pro trial) | Already the shape of `entitlements.py` (free: 5 summaries/mo, 3 earnings alerts, digest-only; Pro: unlimited, realtime, exports, analysis) and the reverse trial already exists. No change needed; keep resisting the urge to gate the dashboard itself. |

Not adopted, deliberately: filing-language sentiment scores (Last10K) invite ungrounded claims; per-company health glyphs (Simply Wall St snowflake, Seeking Alpha health score) imply ratings the product doesn't produce; Earnings Whispers' anticipated-earnings logo grid is a marketing asset more than a dashboard widget; keyword alerts across all filings (BamSEC/Quartr) are a strong power feature but M–L effort, post-beta at best.

<details>
<summary>Sources fetched (competitor research)</summary>

bamsec.com (+ /pricing, /features/other) · quartr.com (+ /products/quartr-pro, /pricing, /products/mobile-app) · tikr.com (+ /pricing, /stock-portfolio-tracking) · stockanalysis.com (+ /pro/, /changelog/, /watchlist/) · last10k.com (+ /features/pricing) · earningswhispers.com (+ /calendar) · koyfin.com (+ /features/watchlists/, /help/watchlist-news-feature/, /help/mastering-portfolio-tracking-with-koyfin/) · simplywall.st (+ /features/stock-watchlist) · stocktwits.com · finance.yahoo.com/portfolios/, /watchlists/, help.yahoo.com portfolio overview · apps.apple.com Seeking Alpha listing · bullishbears.com/fintel-review/ · findmymoat.com/tools/fiscal-ai. Blocked (claims marked inferred, sourced from search snippets/help-doc excerpts): fintel.io, zacks.com, seekingalpha.com, help.bamsec.com, support.tikr.com, help.stocktwits.com, fiscal.ai.
</details>

---

## 5. Open-source value-adds

Licences below were verified on the repos' LICENSE files or licence indicators, not assumed. Two headline facts reframe this whole section:

- **edgartools is already the product's SEC layer** (ADR-0003), pinned at the current release (`edgartools==5.40.1`, MIT, actively maintained: 2.4k stars, 162 releases, latest 2026-06-29). So the question is not "adopt EdgarTools?" but "which of its capabilities that we already pay the dependency cost for are unused?"
- **The charting stack already exists too:** recharts 3.9.2 is in `package.json` (used by the flag-dark analysis feature), and a dependency-free `TrendSparkline` primitive sits unused in `frontend/components/ui/Chart.tsx:317`. No new frontend libraries are needed for anything below.

### 5.1 Ranked recommendations

| Rank | Capability | User value | Infra $/mo | Build effort | Licence |
|------|-----------|-----------|-----------|--------------|---------|
| 1 | **Earnings calendar: flip it on.** Alpha Vantage bulk estimates (free key) + EDGAR 8-K sweep into the owned `earnings_events` table; widget + endpoints + jobs all built | High: fills "coming up" | $0 | S (config + seed check + §3.2 polish) | n/a (already shipped code) |
| 2 | **Form 4 insider activity, persisted.** Parsing exists (`ownership_extractor.py` via edgartools `Form4`, endpoint `GET /api/companies/{ticker}/insiders`); it is flag-dark because it fans out to EDGAR live, up to ~75s per view. Fix by persisting: a table of per-company insider aggregates refreshed by a job on the filing-scan pattern, then render from the DB. Company-page panel first; a dashboard "insider activity for your companies" module after | High: "insiders bought/sold" is the most-requested pattern the comparables monetize (Fintel, BamSEC ownership alerts) | $0 (SEC data, existing job infra; respects the 10 req/s layer) | M (2–3 days: table + migration + job + flag flip) | MIT (edgartools) |
| 3 | **Metric trend sparklines from data already in Postgres.** `financial_fact` holds multi-period revenue/net income/EPS/cash flows (`facts_service.py`), with free endpoints already serving history (`GET /api/filings/{id}/fundamentals`). Render small trend lines with the in-house `TrendSparkline` or recharts: on company pages first, optionally in "Your companies" rows later | High: turns static rows into "how is this company trending" at a glance; zero new SEC calls | $0 | S–M (1–2 days) | MIT (recharts) / in-house |
| 4 | **EDGAR full-text search for users.** The backend already wraps SEC EFTS keyless (`app/integrations/sec_api.py`, used for company search, notable filings, the 8-K sweep). A user-facing "search filings for a phrase" box (edgartools also wraps this as `search_filings()`) is a genuine differentiator vs summary-only tools | Med-high | $0 | M (UI + result page) | n/a (SEC public API) |
| 5 | **13F institutional holdings.** edgartools `ThirteenF` parses holdings and ships `compare_holdings()` (new/closed/increased/decreased vs prior quarter). Quarterly cadence limits its dashboard punch; better as a company-page module | Med | $0 | M | MIT |
| 6 | **redlines for real filing diffs.** MIT, maintained (v0.6.1). Track-changes output in Markdown/HTML/JSON; would upgrade the change report's current Jaccard-overlap risk-factor diff (`change_report_service.py:82-118`) into marked-up section diffs, feeding the existing filing-page `WhatChanged` component. The paywalled headline feature of Last10K/BamSEC, for free | Med (deepens an existing wedge) | $0 | M | MIT |
| 7 | **FinanceDatabase** (static MIT CSV of 300k symbols with sector/industry classifications) for richer peer grouping | Low-med: `peers_service` already ranks same-SIC peers from owned data, so this is enrichment, not enablement | $0 | S | MIT |

Also free and unused, for whenever peer metrics matter: SEC's Frames API (`data.sec.gov/api/xbrl/frames/...`) returns one fact per company per period, i.e. cross-company comparison for any GAAP concept at $0, reachable through the existing edgar layer.

### 5.2 Evaluated and excluded

| Project | Why not |
|---|---|
| **OpenBB Platform** | AGPL-3.0 (verified in the repo LICENSE). The network-use clause would obligate open-sourcing the backend. Hard exclude for a closed-source SaaS, regardless of features. |
| **yfinance** | Code is Apache-2.0, but the data comes from Yahoo endpoints whose terms the project itself describes as personal-use; breakage and ToS risk for a paid product. Honest footnote: the backend already has its own keyless Yahoo quote path for company-page quotes (`companies.py:311-391`); that is an existing, accepted risk, but don't deepen the dependency by building new features on it. |
| **sec-parser (alphanome-ai)** | README states it is no longer maintained. |
| **FinanceToolkit** | MIT itself, but pulls data from Financial Modeling Prep (API key, free tier 250 req/day) with yfinance fallback; the repo just finished retiring its FMP dependency, and every ratio it computes is derivable from `financial_fact` in-house. |
| **sec-edgar-downloader / secedgar / datamule** | Maintained but strict subsets of, or redundant with, edgartools at this scale. |
| **lightweight-charts (TradingView)** | Apache-2.0 with a mandatory attribution notice; fine, but only relevant if price time-series ever become a feature, and they need a data source the product deliberately doesn't have. Parked. |

<details>
<summary>Sources fetched (OSS research)</summary>

github.com/dgunning/edgartools + edgartools.readthedocs.io (insider-filings, 13f-filings, xbrl-querying, full-text-search, configuration, data-objects, performance pages) · pypi.org/project/edgartools · github.com/OpenBB-finance/OpenBB (+ LICENSE) · pypi.org/project/openbb · github.com/ranaroussi/yfinance · github.com/tradingview/lightweight-charts · github.com/recharts/recharts · github.com/airbnb/visx · github.com/jadchaar/sec-edgar-downloader · github.com/sec-edgar/sec-edgar · github.com/houfu/redlines · github.com/JerBouma/FinanceToolkit · github.com/JerBouma/FinanceDatabase · github.com/alphanome-ai/sec-parser · github.com/john-friedman/datamule-python · sec.gov EDGAR API + access pages (data.sec.gov submissions/companyfacts/frames, EFTS, 10 req/s policy).
</details>

---

## 6. Prioritised roadmap

Tags: impact / build effort (S ≤ 1 day, M 1–3 days, L > 3 days) / infra $ per month / risk.

### Quick wins (this week, before beta)

| Item | Impact | Effort | Infra | Risk |
|---|---|---|---|---|
| What's new fix: one-per-company query restructure + 8 tests + the 3 invalidation sites + cap/overflow + New badge + empty states + copy (§2) | High | M (~1 day) | $0 | Low; single-caller service, plain unit tests, response shape unchanged |
| Layout restructure: Your companies merge (reusing `getWatchlistInsights`), remove quick actions, demote plan/usage, saved-summaries conditional render (§3) | High | M (1–2 days) | $0 | Low-med; UI-only, design-system gates apply |
| Calendar flag flip, after verifying `earnings_events` is seeded in prod; render `eps_estimated`; quiet empty line; fix stale flag comment (§3.2) | High | S | $0 (Alpha Vantage free tier) | Low-med; verify seeding first, degrade path already returns `[]` |
| Empty-state onboarding chips + inline `WatchlistAddSearch` on the dashboard (§2.5) | Med-high | S | $0 | Low |
| Doc drift fixes: CLAUDE.md `/api/compare`, ADR-0003 version note (§3.2) | Low (hygiene) | S (minutes) | $0 | None |

### Pre-beta polish (if the week allows)

| Item | Impact | Effort | Infra | Risk |
|---|---|---|---|---|
| Usage-warning banner surfaced at top when ≥80% (§3.2) | Med | S | $0 | Low |
| Save-summary discoverability on the filing page (make the save affordance visible pre-scroll) | Med | S | $0 | Low |
| Feed form-type filter chips groundwork (design only, ships with 8-K rows) | Low now | S | $0 | None |

### Later (post-beta)

| Item | Impact | Effort | Infra | Risk |
|---|---|---|---|---|
| Persisted Form 4 insider module: table + refresh job + flip `ENABLE_INSIDER_ACTIVITY`; dashboard module after the company panel proves out (§5.1) | High | M | $0 | Med: new table + job; SEC rate budget shared with scan jobs |
| 8-K "event" rows in the feed, aligned with the `eightk_coverage` Pro entitlement (§2.3) | Med-high | M | $0 | Med: needs corroborated event typing, not raw form dumps |
| Weekly watchlist brief (email + dashboard card): per-filing one-liners on a labeled cross-filing surface, honoring the filing-only rule | Med-high | M | ~$1 (DeepSeek tokens) | Med: prompt work gated by the eval baseline |
| Trend sparklines in Your companies rows / company page (§5.1) | Med | S–M | $0 | Low |
| User-facing EDGAR full-text search (§5.1) | Med | M | $0 | Low |
| redlines-powered section diffs in the change report (§5.1) | Med | M | $0 | Low-med |
| 13F holdings on company pages (§5.1) | Med | M | $0 | Low |
| Multi-Period Analysis launch (`ENABLE_ANALYSIS`): its own track with its own checklist; the dashboard's role is just the existing `AnalysisTeaser` once live | High (Pro revenue) | Own track | $0 | Own track |

**Total incremental infrastructure across everything recommended: ~$0/month** (existing Cloud Run, Postgres, and cron jobs; Alpha Vantage free tier; SEC APIs are free; the weekly brief would add roughly pennies of DeepSeek tokens at beta scale). The budget being spent is founder days, which is why the quick-wins column is dominated by flag flips and reuse of dark-shipped code.

---

## 7. Assumptions, and what could not be verified

1. **Production flag and env state.** This plan assumes prod runs with `NEXT_PUBLIC_ENABLE_CALENDAR` off, `ENABLE_FPI_FILINGS` off (the code default, `config.py:314`), and `NOTABLE_FILINGS_ENABLED` off (default, `config.py:334`). Actual Vercel/Cloud Run env values were not inspectable from this environment.
2. **`earnings_events` seeding in production.** The table migration landed 2026-07-03 and the refresh job is in the deploy pipeline, but whether prod rows exist was not verifiable here. Before flipping the calendar flag, check row count and freshness (e.g. the admin/ops route or a one-off query: events with `event_date >= today`). If unseeded, one manual `POST /internal/jobs/earnings-calendar-refresh` should populate it.
3. **Production copy vs the tree.** The founder's report of em-dash-heavy card copy does not reproduce in the current tree; PR #576 (merged 2026-07-07) did a voice pass and added the em-dash gate. The likely explanation is prod running a pre-#576 build. If em-dashes persist after the next deploy, they are coming from somewhere the gate doesn't scan, and that is worth a fresh look.
4. **Competitor signed-in dashboards** are partially inferred (auth walls); every such claim in §4 is either from a fetched public page or marked as inferred from help docs/reviews in the underlying research. Fintel, Zacks, and Seeking Alpha are the most inference-heavy.
5. **Watchlist sizes at beta scale** are assumed modest (tens of companies, not thousands). The §2.2 scan-width escape hatch covers the pathological case; it is documented, not built.
6. **The change-report naming drift**: CLAUDE.md refers to a `/api/compare` surface that does not exist in the backend; the actual cross-filing endpoint is `GET /api/summaries/filing/{id}/what-changed`. Treated here as doc drift (code is truth), flagged for the same-PR doc fix.
7. **Alpha Vantage free-tier limits** were taken from the earnings-calendar service's own design (bulk CSV pulls within free limits, keyless EDGAR-only degradation). If the key is absent in prod, the calendar still works from the EDGAR sweep, with estimates missing.
