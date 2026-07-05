# Roadmap UX/UI Review — Plan A features vs Plan D directives (2026-06-21)

Scope: every product feature shipped since PR #316 (the competitive strategy roadmap),
graded against the Plan D UX directives (D1–D8) and the "third-wave coffee × precision
fintech" brand thesis. Five parallel review passes; findings synthesized below.

## Verdict

The *new* roadmap components are, individually, well-built and on-brand — FilingPulse,
the Copilot core, full-text Search, Fundamentals, and the CitationChip provenance pattern
are genuinely good. What drags the experience down — and why the redesign "doesn't feel
different" — is **cross-cutting inconsistency**, not the new features themselves:

1. The new on-brand components are surrounded by **legacy UI that is still light-mode and
   still casino-colored**, diluting the calm/dark-first redesign.
2. **Four roadmap features are built but flag-dark** in production (insider, calendar,
   charts, quality badge) — so a Pro user literally cannot see them.
3. The hero motif (**provenance**) is fully realized only in the Copilot; the summary
   surface uses a weaker, bolted-on version.

So the highest-leverage work is a **consistency + activation pass**, not new building.

## What's genuinely excellent (keep / propagate)

- `CitationChip.tsx` — calm mint chips, distinct XBRL [F#] vs text [n], portal hover-card
  with verbatim excerpt + "Verified/Cited" + EDGAR deep link, keyboard-accessible. **This
  is the gold-standard provenance pattern the whole app should adopt.**
- `FilingPulse.tsx` — the casino buzz UI is genuinely gone: a single muted gauge, no 1–100
  score, plain-language tiers, a labeled "what's driving this" source breakdown, `role=img`
  + aria-label, regression-tested. Exemplary D3.
- `features/search/components/FullTextSearch.tsx` — dark-first, debounced, `keepPreviousData`
  (no flashing), example queries, every row EDGAR-linked. Best-in-class against the standard.
- `FundamentalsTrendChart.tsx` — one curated metric at a time, single mint color, no grid
  noise, `UnverifiedBadge` on reconciled=false. Exemplary restraint + honesty.
- Copilot research-desk on desktop: filing stays visible in a CSS grid beside the rail,
  citations flip the pane to an in-app reader that scrolls + flash-highlights the source.

## Cross-cutting P0 themes (highest leverage)

### T1 — Casino red/green is pervasive (violates D3, and is an a11y fail: color-only signal)
Offenders (muted mint/slate + a non-color glyph instead):
- `components/StatCard.tsx:76,109-113` — **flashing `animate-radar-ping` on >10% gain** (the
  single most on-the-nose casino pattern; `globals.css:103`).
- `components/FinancialMetricsTable.tsx:124-125` `text-green-600`/`text-red-600`
- `components/StatCardSparkline.tsx:11-12` hard `#e11d48`/`#059669`
- `components/TrendingCompanies.tsx:75`, `components/TrendingTickers.tsx:66-67`
- `features/companies/.../InsiderActivityPanel.tsx:75-80,143,151,196-200` (sells = red)
- `features/filings/components/WhatChanged.tsx:8-9`, `dashboard/WhatChangedCard.tsx:10-11`,
  `app/compare/result/page.tsx:321-322,367`
- `app/filing/[id]/page-client.tsx:289` stock quote `text-green-600`/`text-red-600`

### T2 — Not dark-first (violates D1, the brand signature)
The roadmap components are dark-first; the **most-viewed legacy surfaces are light-only**:
- `components/SummarySections.tsx:277-318` — the canonical filing summary card, no `dark:`.
- `app/compare/result/page.tsx` — `bg-white`/`text-gray-*` throughout, breaks in dark mode.
- Summary section cards (`SummaryBlock.tsx`, `SummaryExecutiveSnapshot/Financials/Snapshot`),
  `SummaryProgress.tsx:107`, `FinancialCharts.tsx:94`, `FinancialMetricsTable.tsx:65-94`,
  `StatCard.tsx:82,131`, `WatchlistAddSearch.tsx:76,98,121`.
- Company/filing page chrome is composed light-primary with `dark:` as the variant —
  inverted from D1 (`page-client.tsx:245,247,313`).

### T3 — Provenance is two different UXs (violates D2 "provenance is the texture")
- Copilot: rich ambient hover-card (gold standard).
- Summary metrics/risks: `MetricSourceLink.tsx` + `SummaryRisks.tsx TraceToSource` are plain
  text links; metrics show **no excerpt at all**, risks only in a static "Evidence" box.
- No mobile tap-sheet for provenance anywhere (even CitationChip is hover/focus-only).
- **Fix:** extract one shared ambient Trace component (the CitationChip pattern) and use it
  for metrics, risks, and Copilot alike; add a mobile bottom-sheet variant.

### T4 — Honest-state pillar (D8) is switched OFF
`ENABLE_QUALITY_BADGE=false` → degraded/Partial summaries are still presented as complete.
This directly contradicts the "honest labeling" brand pillar. When on, also restyle from the
green/amber pill (`page-client.tsx:1234-1238`) to a quiet neutral/mint chip.

## Flag-dark roadmap features (activation — quick visible wins)
| Flag | Default | Gates | Recommendation |
|---|---|---|---|
| `ENABLE_QUALITY_BADGE` | OFF | Full/Partial honesty chip | **Turn on** (restyle to quiet chip) — it's a brand pillar |
| `ENABLE_INSIDER_ACTIVITY` | OFF | Form 4 panel (PR #342) | Turn on after T1 recolor (sells→neutral) |
| `ENABLE_CALENDAR` | OFF | Earnings calendar (PR #306) | Turn on if FMP key present; else leave dark |
| `ENABLE_FINANCIAL_CHARTS` | OFF | Charts + peer panel | Turn on after T2 dark-mode + T1 recolor |
| `ENABLE_SECTION_TABS` | OFF | Tabbed summary | Keep OFF (D4 prefers progressive disclosure) ✓ |
| `ENABLE_APPLE_SIGNIN` / `TURNSTILE` | OFF | — | Keep OFF (backend/keys not wired) ✓ |

## Per-feature notes
- **A5 "What Changed"** is under-sold: the narrated `key_changes` sentence — the unique
  filing-native hook — is buried as a grey footnote *below* metric chips
  (`WhatChanged.tsx:119-126` should lead, above `:52`). Dashboard card has no narration at all.
- **Compare** leads with a 12-row metrics table before the "Key Movements" signal block
  (`compare/result/page.tsx`) — invert to signal-first + collapse the table (D4).
- **Discoverability:** Search and Compare are not in the main nav (`Header.tsx:14-21`);
  `/search` is footer-only, `/compare` has no global entry point.
- **Copilot metering invisible:** no "N of M questions" for FREE, no "Unlimited/Pro"
  affordance — PRO never feels generous, FREE hits a raw 429 bubble.
- **Copilot FREE teaser** is informative but not try-able (blurred, no tappable starters).

## Mobile / D7 gaps
- Copilot mobile sheet: **no focus trap, no backdrop/scrim** (Tab escapes, tap-outside
  doesn't dismiss); it occludes the summary (no split/peek) — desk metaphor is desktop-only.
- **Notification bell is desktop-only** (`Header.tsx:84` md:flex block); mobile users can't
  see/clear alerts.
- No mobile tap-sheet for provenance (T3).

## Recommended sequence (each a focused PR, per the established cadence)
1. **P0-A "Calm palette" pass (T1)** — kill the flashing ping; replace all saturated red/green
   with muted mint/slate + a non-color glyph. Biggest brand-perception delta, low risk.
2. **P0-B "Dark-first" pass (T2)** — dark variants on SummarySections, compare, summary cards,
   charts/tables. Makes the whole app feel like the redesign.
3. **P0-C Unify provenance (T3)** — shared ambient Trace component + mobile sheet.
4. **P1 Activation** — quality badge on (restyled); insider recolor + on; What-Changed leads
   with narration; nav for Search/Compare; Copilot metering + mobile focus-trap/backdrop;
   notification bell on mobile.
5. **P2** — enable charts (post T1/T2); compare signal-first; dashboard card narration.
