# Filing index & Change Report: design review + remediation

> Design source: the EarningsNerd design project (`Filings Index Review.dc.html`). Paths written as `code/…` there map to `frontend/…` here.

> Reviewed 2026-10-08 against `neilmac91/EarningsNerd@main` (tree `2129a80`), `frontend/`.
> Visual companion (live target, both themes, states, redline): `Filings Index Review.dc.html`.

## Verdict

Both components use the system's tokens, but neither follows its rules. The filings list breaks
**9 of 14** checked rules and the Change Report breaks **6**. The list states the form type four
times per row (stripe, tint, icon colour, chip), puts a primary button on every row (5 in one
viewport), nests four bordered containers deep and fails AA on its own tints. Fixing this doesn't
need a new colour. It needs things taken away.

**System gap:** DESIGN_SYSTEM.md §4 sanctions `<Badge variant="info">` as the "interim-filing
tint (10-Q/6-K)". That contradicts DESIGN.md §2.3 rule 2 (status colours never used for
anything else). Amend the doc, not just the call site.

## Findings: filings list (`app/company/[ticker]/page-client.tsx`)

| # | Sev | Finding | Evidence | Rule |
|---|---|---|---|---|
| 1 | P1 | `border-l-4` stripe on `rounded-xl` rows (curved-hook ends) | L612 | §6 cards lift, never tint |
| 2 | P1 | Rows tinted (`info-light/10`, `brand-weak`); 10-Q hover darkens, 10-K hover is a no-op | L358–390 | §6 hover brightens |
| 3 | P2 | Same `FileTextIcon` on every row, colour-matched (3rd signal) | L617 | no decorative icons |
| 4 | P1 | Info blue (status) + sage (action) used as form categories | L358 · Badge `info` | three vocabularies |
| 5 | P1 | "Recommended" twice (banner + row), sparkle on both; it's just the newest filing | L534, L625 · recommendedFiling.ts | §4 icon split |
| 6 | **P0** | Filed date tertiary on tints: **4.0:1** (10-Q), 3.7:1 hover, **4.3:1** (10-K) | L630 | §1 AA on mixed tint |
| 7 | P1 | Secondary + primary per row; "Generate Filing Summary" Title Case and wrong verb; ~170px per filing on phones | L646, L650 | one primary · sentence case |
| 8 | P2 | `sm:items-start`: text rides ~8px above the button centreline | L614 | alignment |
| 9 | **P0** | Year toggles: no `aria-expanded`/`aria-controls`, no focus ring, hover darkens; "(3 filings)" 4.35:1 on cream | L589–600 | ring · AA |
| 10 | **P0** | Toolbar: ink-fill "All" vs sage-fill types, chips r12 (should be full), raw `focus:ring-brand` select, no `aria-pressed`, no ring | L480–520 | §4 compose |
| 11 | P2 | Card › banner › year box › row card (4 deep) | L531, 590, 606, 612 | hairlines, not boxes |
| 12 | P1 | Hand-rolled `<Button loading>` Retry, not RetryButton | L575 | §4 every Retry |
| 13 | P2 | Filtering to a year outside the newest three shows only a collapsed bar | filterYear vs expandedYears | filters show results |
| 14 | P2 | Skeleton = 3 generic bars, not the list's shape | L560–562 | §4 layout-preserving |

## Findings: Change Report (`features/filings/components/WhatChanged.tsx`)

| # | Sev | Finding | Evidence |
|---|---|---|---|
| 1 | P2 | Hand-rolled card at r12 / e1 (cards are 16 / e2) | L28 |
| 2 | P1 | Comparison basis set as an uppercase eyebrow beside the title | L37 |
| 3 | P2 | Decorative sage GitDiff glyph before the heading | L32 |
| 4 | P1 | `justify-center` chips leave the third metric stranded on a centred line | L62 |
| 5 | P1 | Deltas in body semibold (not Geist Mono); prior/current figures omitted though in payload | L72 |
| 6 | **P0** | Colour from `direction`, ignoring the server's `tone` (debt down would render red) | L68 |
| 7 | P2 | Direction triple-encoded (tint + trend icon + sign) | L71 |
| 8 | P1 | "No longer cited" in sage, so brand signals a state; asymmetric +/− glyph colours | L104 |
| 9 | **P0** | Landing demo ships permanent skeleton bones announced as `role="status"` loading | ChangeReportDemo.tsx:24–50 |
| 10 | P2 | Prior link: raw ISO date + ↗ on an internal link | L43–49 |

## Target (summary; full redline in the DC §06)

- **One surface:** `<Card as="section">`; years and rows separated by hairlines (DataTable manners).
- **Toolbar:** `<SegmentedControl>` (All · 10-K · 10-Q, codes in Geist Mono) + `<Select size="sm">`.
- **Latest lead:** inset well `rounded-lg bg-background p-5` with the page's single primary.
  No tint, no sparkle, no chip.
- **Column header:** DataTable header recipe (Form · Period · Filed).
- **Year header:** `<h3><button aria-expanded aria-controls>`, year + count in `font-data`; collapsed
  lists stay in the DOM with `hidden`.
- **Row:** one `<Link>`, grid `72px minmax(0,1fr) 136px 112px`, min-h 48 (64 on phones),
  `-mx-3 px-3 rounded-lg`, hover `bg-white` / `dark:bg-white/[0.03]`, `ring-brand`.
  Form `font-data text-sm font-semibold`; period `text-sm font-medium` via `periodLabel()`;
  filed `font-data text-sm tabular-nums` secondary.
- **EDGAR:** sibling `<a>` absolutely placed in track 4. Never nested in the row link.
  32px target (44px on phones).
- **Markers:** `<Badge variant="brand">Latest</Badge>`; `<Badge variant="warning">Superseded</Badge>`
  + one line ("Superseded by the 10-K/A filed …").
- **Footer:** CardFooter recipe: FilingsHistoryNote + "Show full history" (secondary sm).
- **States:** ledger-shaped skeleton, Notice + RetryButton, filter-empty copy naming the filters,
  year filter forces its group open.

## Plan

**Phase 0 (S, ½ day): fixes that survive the rebuild**
RetryButton on the filings error (L575) · WhatChanged colours by `tone` · remove ChangeReportDemo
bones + `role="status"` (no risk block until verbatim lines) · drop sparkle from banner + row ·
sentence case. *Done when:* busyControlsStayFocusable passes; no SparkleIcon in app/company;
inverted-tone fixture renders gain ink.

**PR 1 (M, 1 day): primitives**
`ui/SegmentedControl` (lifted from EarningsCalendarPage; calendar migrates) · `inputClasses({ density:
'compact' })` + `<Select density="compact">` (explicit sides, no conflict-order override) · DESIGN_SYSTEM §4
"Index list" recipe + retire form-type colour coding · guide §06 demo cards · upstream-sync §16.
The ESLint selector banning `border-l-(2|4|8)` with `rounded-*` is deferred: SummaryBlock.tsx still
carries one. *Done when:* calendar is visually unchanged; guide renders in both themes.

**PR 2 (L, 2–3 days): FilingIndex**
`features/filings/components/FilingIndex.tsx` (FilingIndex, FilingYearGroup, FilingIndexRow,
LatestFilingLead) + `features/filings/lib/filingPeriod.ts` · delete `getFilingTypeStyles` + inline
list; queries/filters/A4/prefetch/focus hand-off stay in the page. *Done when:* unit tests
(periodLabel matrix, aria-expanded/pressed, row name, EDGAR not nested, Latest once, forced-open
year) and e2e (keyboard order; 320/390/768/1280 in both themes; seeded HTML still has `/filing/{id}`
links) pass; §12 greps clean.

**PR 3 (M, 1 day): What changed**
Card recipe · header = title + basis sentence + "Prior 10-K" link (formatLocalDate, caret) · metric
table Metric/Prior/Current/Change (`font-data`, display verbatim, toned by `tone`) · neutral risk
diff · carried-over footnote. *Done when:* tone matrix incl. an inverted metric passes;
`has_changes=false` renders nothing; both surfaces checked in both themes.

**Later (P2 tickets):** TickerFilingsView → FilingIndexRow · NotableFilingCard eyebrow ·
backend `fiscal_period`/`fiscal_year` (XBRL dei) and `has_summary` on the filings payload.

## Decisions (defaults already in the DC)

- **Q1:** "Latest", not "Recommended".
- **Q2:** form types typographic (no colour).
- **Q3:** whole-row link + quiet EDGAR.
- **Q4:** group label "2026" with sr-only "Report year".
- **Q5:** fiscal labels later, from XBRL dei.
- **Q6:** no risk block on the landing demo until verbatim lines exist.

## Must survive the rebuild

Semantic tokens only · dark pairs · `formatLocalDate` · server-seeded top-3 expansion ·
FPI-aware filters · superseded originals readable · "Showing filings since …" + EDGAR
hand-off · full-history focus hand-off.
