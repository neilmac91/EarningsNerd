# Multi-Period Analysis: data notes, aligned figures, a compact table — design proposal and implementation brief

Date: 2026-10-10 · Scope: `/analysis` results surface (KPI strip, Sources & methods, charts, narrative,
metrics table, period picker) and the PDF, Excel and PNG exports that mirror it · Status: the §9
decisions are taken (2026-10-10); Phase 1 items 1–4 and 11 of §7 are merged (#1199, #1200); items
5–10 and Phase 2 are open; this document itself ships nothing · Support material:
[`tasks/analysis-redesign-2026-10/`](../../tasks/analysis-redesign-2026-10/README.md) (runnable
prototype, measurement harnesses, recorded measurements).

This document separates what was **observed** (the current code, the production screenshots, and
measurements taken on the repository's own frontend build) from what is **proposed**. Every number
in the "Observed" tables was measured in this review unless it is attributed to the founder's
investigation.

## 1. Summary

The quality layer that #1191 added to the analysis page is right about the data and wrong about its
presentation. It attaches a full-width amber label to every figure that carries a concern and to every
comparison that inherits one, so one underlying issue (ten saved calculations without recorded lineage)
surfaces as thirty-odd identical labels, a "26 source checks needed" count that measures labels rather
than issues, KPI cards whose labels leave the card on phones, and a metrics table whose warned columns
are three times the width of clean ones.

The proposal replaces label-per-instance with **note-per-issue**:

1. A **Data notes** model, computed once from the dataset: each distinct issue (reason code) becomes a
   lettered note (a, b, c) that lists the values it affects and counts, separately, the comparisons
   built on them (quarter-over-quarter in the table, year-over-year in the headline cards and charts).
2. A **figure affix** instead of a label: the figure keeps its typography and column; it gains at most
   two small marks, `†` for calculated and a letter in warning ink for a note. Nothing that can widen a
   card or a column sits next to a number any more.
3. One **Data notes strip** under the headline cards (a hairline strip, not a card) with the counts and
   the grouped notes, replacing the "N source checks needed" badge.
4. A **KPI strip** whose label, value and delta rows are shared across cards (CSS subgrid) and whose
   period line names each figure's actual period.
5. A **metrics table** with fixed, equal period columns (76 px desktop, 68 px phone, scaling with text
   size), a change line without the repeated "QoQ" prefix, a sticky metric column, a scroll range kept
   to whole columns (so the sticky column never half-hides a value), an explicit All 12 / Newest 6 /
   Earliest 6 window, and contained scrolling only where it is honest.
6. An **evidence dialog** that shows the figure in financial display form (26.1%, not "26.06536077
   pure"), the exact value, the formula with the operands substituted, the check status with the note,
   and the real source lineage; when the backend has none recorded it says so instead of inventing it.
7. A **narrative** that reads amounts as $60.8B, keeps the Red flags sentences short, and moves the
   operand lists (twenty figures on the free-cash-flow finding) into a disclosure under each finding.
8. A **period selector** of presets, two compact selects and one summary line, in place of 61 equally
   weighted chips.
9. One vocabulary across web, PDF, Excel and PNG: the same letters, the same note sentences, the same
   counts; the narrative stays readable, the Sources & Methods appendix keeps full precision.

Measured on the prototype with the real Meta Platforms 12-quarter dataset in its production-like
state: no page overflow and no card-child overflow at 1480, 1054, 1024, 768, 390 and 320 CSS px, in
both themes, at 2x device-scale emulation of 200% browser zoom and at 200% text size; twelve columns
fit at 1480 px without scrolling; the "Newest 6" window fits without scrolling from 768 px up; no
column is ever partly hidden under the sticky metric column. (The first prototype build overflowed
on phones: its chart panels kept their 480 px min-content width inside `1fr` grid tracks, and both
harnesses hid it by comparing the document with `window.innerWidth`, which mobile Chromium widens to
the content. The Track A verification on the PR caught both; the panels now sit in `minmax(0, 1fr)`
tracks with `min-width: 0`, and the harnesses compare the document with the configured viewport.
§11 lists every correction.) The current build, measured the same way, overflows the device
by 39 px at 390 and 93 px at 320, places a label 54 px past its card edge at 390 (126 px at 200% text),
and lays the table out 2,076 px wide at every width.

## 2. Observed

This section describes `main` at `97293e7`, the build this review measured. Phase 1 items 1–2 and 11
of §7 landed on `main` in #1199 and items 3–4 in #1200 on 2026-10-10, while this proposal was in
review; the current page no longer shows the labels described here. The section is kept as the
record of what the redesign answers.

### 2.1 How the labels arise (code)

- `features/analysis/components/ReconciliationBadge.tsx` renders `<Badge variant="warning">` when
  `needsSourceCheck()` is true: a non-interactive `span` with `whitespace-nowrap` from
  `components/ui/Badge.tsx`, with the reason only in `title`.
- `KpiStrip.tsx` renders it after the value and again inside the delta line ("Growth source check
  needed"). `MetricsTable.tsx` renders it inside every cell's value row and again in the delta row.
  `TrendCharts.tsx` renders one per panel. `NarrativePane.tsx` renders one in the header and one per
  affected Sources entry. `SourcesMethods.tsx` counts points plus comparisons and shows "N source
  checks needed", where the comparison basis is QoQ when present, else YoY.
- The backend already models the distinction the UI collapses. `fact_provenance.provenance_for_fact`
  gives a row without stored provenance `validation: needs_review` with the single reason
  `legacy_calculation`; `dataset_quality.add_comparisons` computes every QoQ/YoY comparison with
  `calculated_provenance`, which inherits the operands' validation. So every comparison that uses a
  legacy value is `needs_review` with the same reason. Ten records therefore become ten labels plus one
  label per comparison, plus the chart, narrative, citation and summary labels.
- `SourceValue.tsx` prints `value.toLocaleString(maximumFractionDigits: 8)` followed by `point.unit`,
  which for a margin is the stored unit `pure`: "26.06536077 pure". A legacy record has
  `provenance.inputs == []`, so the dialog shows neither operands nor links.
- `trend_analysis_service.build_observation_catalogue` renders each red flag as the detector's sentence
  plus `" Source operands: " + "; ".join(...)` over every marker the detector cites;
  `detect_fcf_ni_divergence` cites every historical FCF/net-income pair, twenty operands on the Meta run.
- `PeriodPicker.tsx` renders one chip per coverage period (61 quarters for Meta) with a hand-rolled
  mode toggle rather than the design system's `SegmentedControl`.

### 2.2 The dataset used for this review

The real Meta Platforms, Inc. companyfacts payload (`CIK0001326801.json`, fetched 2026-10-10) was run
through the repository's own engine in a private SQLite database: `normalize_companyfacts` →
`upsert_facts_bulk` → `build_dataset(quarterly, 2023Q3..2026Q2)` → observation catalogue → citation
resolution → fidelity scan. The output reproduces the production screenshots' figures (revenue
$60,801M, net margin 26.0653…%, free cash flow $1,746M, current ratio 2.2256, long-term debt +355.1%,
the three inflections and the twenty-operand finding). Three states were recorded:

| State | How it was produced | Review items |
|---|---|---|
| 1 clean | fresh ingest; every calculation carries lineage | 0 values; 10 unavailable (EPS on three calculated Q4s, capex and FCF for Q3–Q4 2023, which are real gaps) |
| 2 incomplete history | ten computed rows have their stored provenance removed, as rows written before #1191 are (the `legacy_calculation` path), modelled on the cells the production screenshots show warned | 10 values; 14 QoQ + 10 YoY comparisons; 10 unavailable |
| 3 genuine discrepancy | the latest reported revenue and the two margins calculated from it carry `source_conflict` (a simulation of the engine's output when sources disagree) | 3 values; 3 QoQ + 3 YoY comparisons; 10 unavailable |

Production counted 26 because its comparison count is QoQ-only and its legacy set differs slightly
from the modelled one (production: 236 populated values, 4 gaps, 16 QoQ + 10 YoY concerns; the
fixture: 230, 10, 14 + 10); the mechanism is the same. `source_conflict` is a reason the frontend
maps but no backend code path produces today, so state 3 simulates a reason the model must handle,
not one the engine emits. The prototype's data modules are pruned for rendering (the provenance
`version` and the comparison operands' shape are flattened); they are a visual reference, not a
lineage-contract fixture.

### 2.3 Measurements of the current components

Taken on the repository's frontend (`next build` + `next start`, `NEXT_PUBLIC_ENABLE_ANALYSIS=true`)
with every API answered in the browser, state 2, light theme (dark theme measured identical):
`tasks/analysis-redesign-2026-10/measurements/current.json`.

| Viewport (CSS px) | Document width | Labels on page | KPI label past card edge | KPI value top per card | Table width / container |
|---|---|---|---|---|---|
| 1480 | 1480 | 33 | 0 | 37 / 37 / 37 / 37 | 2,076 / 1,054 |
| 1054 | 1054 | 33 | 0 | 37 / 37 / 37 / 37 | 2,076 / 956 |
| 1024 | 1024 | 33 | 0 | 37 / 37 / 37 / 37 | 2,076 / 926 |
| 768 | 768 | 33 | 0 | 37 / 37 / 37 / 37 | 2,076 / 670 |
| 390 (phone) | **429** | 33 | **54.3 px** ("Growth source check needed") | 37 / 53 / 53 / 53 | 2,076 / 308 |
| 320 (phone) | **413** | 33 | **89.3 px** | 53 / 53 / 69 / 53 | 2,076 / 238 |
| 1480 at 200% zoom (740 CSS px) | 740 | 33 | 0 | 37 / 37 / 37 / 37 | 2,076 / 642 |
| 1480 at 200% text | **1,558** | 33 | **125.6 px** | 73 / 105 / 105 / 105 | 4,151 / 1,286 |

Document widths are measured against the configured viewport (mobile Chromium widens the layout
viewport to the content, so `window.innerWidth` cannot detect overflow). Table columns: warned
period columns 234–240 px, clean ones 77–105 px (469–481 vs 154–209 at 200% text). The 33 labels are four texts: "Source check needed", "Growth source check needed", "24 source
checks needed" and "Source checks needed". The far-right sticky-column occlusion the founder saw was
not reproduced at the rest position my probe measures; the mechanism, a scroll range that is not a
whole number of columns, is real, and the prototype reproduced it before its range rule (§4.5).

These agree with the founder's investigation (table about 2,158 px in a 1,054 px viewport; warned
columns 229–235 px against 77–103; document 426 px at 390; the net-margin growth badge 49 px beyond its
card; the badge fitting at 1480 with default text). The slightly different widths come from the
modelled legacy set.

### 2.4 Secondary observations

- The four surfaces use four period vocabularies: "(2026Q2)" in KPI labels, "2023Q3" in table
  headers, "Q3 '23" on chart axes and picker chips, "2026Q2" in the narrative and Sources list.
- The KPI label carries the period in parentheses, which wraps to two lines below 768 px and misaligns
  the values across cards (the "value top" column above).
- The narrative prints "USD 60,801,000,000" where the Sources list already carries the exact figure.
- The "34 source entries" chip, the amber "Source checks needed" chip and "Cached" sit in one row with
  the heading; the row of chips itself does not wrap (only the outer group that holds the buttons
  does), so on phones the chips run past the heading's row.
- `SourcesMethods` is a full `Card` whose resting state is one summary line.

## 3. Diagnosis

1. **Instance labelling.** A concern is attached to each displayed instance (value, comparison, chart,
   citation) instead of once to the record that carries it. Everything derived from the record repeats
   the label.
2. **Text as layout.** The label is a nowrap pill inside the figure's own box, so its width, not the
   figure's, sizes KPI cards and table columns, and its line breaks move the figures.
3. **Counting labels, not issues.** "26 source checks needed" is the number of labelled instances in
   one surface's comparison basis; the KPI/chart surfaces use another basis, so no two counts agree and
   none tells the reader what is wrong.
4. **Evidence without semantics.** The dialog prints storage units and raw precision, and for legacy
   records has nothing to show, so the one place a reader could resolve a concern tells them least.
5. **Narrative as audit log.** The code-rendered sentence carries every operand inline because the
   grounding contract wants every claim citable, but the citations already live in the Sources list.

## 4. Proposal

Design rules applied throughout: one sage accent, cards that lift, the data face for every figure,
12 px running copy and an 11 px floor for dense annotations, warning ink only for an unresolved
concern, financial tone from the series' `tone`, both themes, the shared `Modal`, `SegmentedControl`
and provenance-chip recipes, no new dialog primitive, no new colour. The Calculation Provenance Rule in
`DESIGN.md` keeps its substance (a calculation is an origin, not a failed check; missing validation
makes no claim); its wording changes where §7 says.

### 4.1 Data notes model

A pure function over the dataset, `groupDataNotes(dataset)` (frontend, Phase 1) with the same rule
shipped by the backend as `dataset.data_notes` (Phase 2, so exports agree):

- A **review note** is one distinct set of reason codes among values with `validation ==
  needs_review` (`legacy_calculation`; `source_conflict`; `unit_mismatch`; …). It lists the affected
  values grouped by metric with their periods, and counts the comparisons whose provenance carries the
  same reasons, per basis: QoQ (the table) and YoY (the headline cards, the revenue growth line, the
  narrative's growth sentences).
- An **unavailability note** is one distinct reason among values that are null: the stored reason when
  the provenance carries one (`unsupported_eps_calculation`, `repair_rolled_back`) or "not available in
  this dataset" when the point has no record (capex and FCF for Q3–Q4 2023).
- Notes are lettered a, b, c in order of first appearance (series order, then period order), review
  notes before unavailability notes. Letters are stable within a snapshot; a new snapshot may re-letter.
- The grouping must also carry: a populated value whose record has no provenance at all (older
  snapshots) as a "no validation record" note that claims nothing; a legacy `reconciled: false`
  without provenance under the `source_check_needed` key; annual CAGR and window-pp comparisons
  (`cagr_provenance`, `window_pp_provenance`) in the comparison counts; and a comparison whose reason
  set matches no value's (a comparison-only or mixed set) as its own lettered note.
- Copy per reason reuses `provenance.ts` `REASONS`, rewritten to one sentence of plain English each
  (the current `legacy_calculation` sentence stays: "This saved calculation predates the current source
  checks. Its inputs need review.").

What a reader sees in the three states (prototype output, state 2 is the production-like one):

- State 1: "Data notes · 230 figures passed automated source checks · 10 unavailable · 101 calculated †".
  Open: note a (unavailable) "Not available in this dataset. EPS (basic), EPS (diluted) (Q4 2023, Q4
  2024, Q4 2025); Capital expenditures, Free cash flow (Q3 2023, Q4 2023) · 10 values shown as — ·
  growth is not computed across a gap."
- State 2: "Data notes · 10 values need review · 24 comparisons built on them · 10 unavailable · 101
  calculated †". Open: note a "Saved calculation predates the current source checks; its inputs are not
  recorded. Operating margin (Q2 2025, Q2 2026); Net margin (Q2 2025, Q2 2026); Working capital (Q4
  2023, Q1 2024, Q2 2026); Current ratio (Q4 2023, Q1 2024, Q2 2026) · 10 values · 24 comparisons
  inherit this note (14 quarter-over-quarter in the table, 10 year-over-year in the headline figures and
  charts) · figures are shown as stored; their source lineage is not recorded"; note b as in state 1.
- State 3: "Data notes · 3 values need review · 6 comparisons built on them · 10 unavailable · 101
  calculated †". Open: note a "Available sources disagree on this figure. Revenue (Q2 2026); Operating
  margin (Q2 2026); Net margin (Q2 2026) · 3 values · 6 comparisons inherit this note (3 quarter-over-
  quarter in the table, 3 year-over-year in the headline figures and charts) · review the original
  filing before relying on these figures"; note b as above.

"Passed automated source checks" is the server's own `validation == passed`, stated as what it is; the
strip's prose adds "automated checks compare figures with the company's XBRL and are not an audit of its
accounts". The word "verified" does not appear.

### 4.2 The figure affix: what stays visible beside an affected number

Beside a figure, at most two marks in the data face, never wrapping and never wider than two characters:

- `†` in secondary ink for `method == calculated` (unchanged meaning).
- a superscript letter in warning ink (`warning-light` / `warning-dark`) for the figure's note; the
  same letter, on the change line, for a comparison that inherits it; a letter in tertiary ink after
  "—" for an unavailable value with a note.

The letter is the signal, not the colour, so the meaning survives colour-vision deficiency and
monochrome print. Letters are 11 px (the dense-annotation floor) at every size; they ride a zero
line-height superscript so a row with notes is no taller than one without.

Accessible name of the figure's button: "Net margin, Q2 2026: 26.1%, calculated, data note a,
comparison carries data note a. View source and calculation". The glyphs are `aria-hidden`.

On click, Enter, Space or tap the figure opens the evidence dialog (§4.6). The letter itself is not a
separate control (it would add dozens of Tab stops); the Data notes strip and the dialog both explain
it, and the notes chip on a chart or the narrative header jumps to the strip.

### 4.3 Data notes strip

Position: under the KPI strip, where `SourcesMethods` sits today, so it is the legend for everything
below. Form: a hairline-topped and -bottomed strip in the trust-strip manner, not a card; a
`<details>` whose summary is the one-line count (title in primary ink, counts in the data face, review
counts in warning ink, the all-passed count in sage). Open, it lists the notes as a two-column list
(letter, then sentence / where / counts) followed by the existing Sources & methods prose (calculated
figures, Q4 derivation, EPS, FCF definition, data as of, snapshot). Every chart's "Notes a" chip and the
narrative header's chip open this strip and scroll to the note. Owner: a new `DataNotes.tsx` that
replaces `SourcesMethods.tsx`.

### 4.4 KPI strip

- `<dl>` grid, `grid-cols-2 lg:grid-cols-4`; each card `grid-rows-subgrid` spanning three rows (label,
  value, period + delta) so the three rows share heights across the strip and every value sits on the
  same line. (Subgrid: Chrome 117, Safari 16, Firefox 71.)
- Label: the metric name only, eyebrow style, allowed to wrap. Value: 24 px data face with the affix.
  Third row: "Q2 2026 · YoY +28.0%" as two inline items that wrap independently on narrow cards; when
  the card's period is older than the dataset's latest period, "· latest available" in secondary ink
  follows the period, so a metric whose newest quarter is missing is never read as current.
- The value is the button that opens evidence; no label element sits in the card.
- Measured (prototype, state 2): label-to-edge overflow 0 at every width; value tops equal within a row
  at every width (37 px; at 320 the second row is 55 px because "Free cash flow" wraps there, aligned
  with its neighbour).

### 4.5 Metrics table

- `table-layout: fixed` with explicit widths: metric column 8.25 rem (132 px), period columns 4.75 rem
  (76 px) from 768 px up; 6.5 rem and 4.25 rem below. Widths are in rem so they scale with the reader's
  text size and never clip a figure (at 200% text the columns are 152 px and the table scrolls, which
  WCAG 1.4.10 allows for data tables). Content never sizes a column.
- Cell: value line (`$60.8B†ᵃ`), then the change line in the series' financial tone with the sign only
  (`+8.0%`, `−9.7ppᵃ`, `n/m`); "QoQ" is stated once, in the metric column's header ("value · Δ vs
  prior quarter") and in the caption. Twelve columns of "QoQ " disappear. The one exception keeps its
  label: today's table falls back to the YoY comparison when a quarter has no QoQ comparison (a gap
  before it), and such a cell prints "YoY −3.1%" explicitly, with the caption saying that a cell
  marked YoY compares with the same quarter a year earlier.
- Header: quarter over year on two lines ("Q2" / "’26"), a `†` after the year of a calculated Q4 column.
- Unavailable: "—" with the note letter, a button only when there is a note to explain.
- Sticky metric column (exists today) plus a **whole-column scroll range**: the scroll container gets an
  inline-end pad of `(columnWidth − (range mod columnWidth)) mod columnWidth`, recomputed on resize,
  so the far-right rest position starts exactly on a column edge; `scroll-snap-type: x mandatory` with
  `scroll-padding-inline-start` equal to the metric column snaps every rest position to a column. Without
  the pad, mandatory snapping still lets the scroller rest at its range end, half-hiding a column
  (reproduced on the prototype before the rule; zero after it, at every width).
- **Window control** on the table header (`SegmentedControl`): All 12 · Newest 6 · Earliest 6, with the
  line "Showing 6 of 12 quarters" when a window is active. The default is always All 12: nothing is
  dropped silently, the window is the reader's explicit choice, and charts and headline figures are not
  affected by it.
- **When contained scrolling is appropriate:** when the table keeps every column at full readable
  width, the row labels stay sticky, the scroll region is a focusable landmark that names itself, every
  rest position shows whole columns, and a visible hint says what is off-screen. Under those conditions
  it is better than shrinking, truncating, dropping periods or stacking twelve periods into 240 rows of
  cards. It is not appropriate when the reason for the overflow is a label (today), when a column can be
  half-hidden (today), or when the page itself scrolls sideways (today on phones).
- Measured (prototype, state 2, light and dark identical): 1480 → 1,062 px in a 1,062 px card, no
  scroll, 77 px columns; 1054 → 1,044 in 964 (scrolls 80 px); 1024 → 1,044 in 934; 768 → 1,044 in
  678; 390 → 920 in 316 (68 px columns); 320 → 920 in 246; 200% zoom → 920 in 650; 200% text → 2,088 in
  1,302 (152 px columns). Newest 6 fits without scrolling at every width from 768 up and at 200% zoom;
  at 390 and 320 it halves the scroll (512 px). No cell text clipped, no column occluded, at any width.
- Phones: the table starts scrolled to the newest quarter with "← earlier quarters · scroll or use the
  arrow keys · snaps to whole columns" above it; the window control sits above the table; the KPI strip
  already answers "what is the latest" without scrolling.

### 4.6 Evidence dialog (`SourceValue`)

The shared `Modal`, size `lg`, titled "Net margin · Q2 2026":

1. **Figure**: display form in the data face (26.1%; 2.23×; $1.7B; $6.23) with the affix, then "exact
   26.06536077%" / "exact 2.2255627095 (ratio)" / "exact 1,746,000,000 USD". The storage unit `pure`
   never reaches the reader.
2. **Method**: "Reported in the source filing." or "Calculated by EarningsNerd from reported inputs."
   with the formula in words and, when both operands are known, the substituted arithmetic:
   "15,848,000,000 ÷ 60,801,000,000 × 100 = 26.06536077%".
3. **Checks**: "Automated source checks passed" (sage check), or "Needs review · Note a" (warning
   ink) with the reason sentence, or "Withheld · Note b", or "No validation record. No verification
   claim is made." Never "verified".
4. **Inputs and source filings**: one row per operand (concept, exact value, period, its own method
   and check status, "Open filing ↗", accession, XBRL tag), nested one level for a derived quarter
   (FCF = OCF − capex, where OCF = YTD6 − Q1 shows both reported rows with their filings). For a legacy
   record: "Source lineage is not recorded for this saved calculation. The figure is shown as stored.
   Check the original filing before relying on it." (No promise about a repair: the repair is a separate
   authorisation.) A source link the record itself carries is shown whether or not it has inputs. No
   source is ever constructed on the client.
5. The FCF definition for that series, and the existing "not an audit" line.

Opens from pointer, keyboard (Enter/Space on the figure button) and touch; focus moves in, Tab cycles,
Escape closes, focus returns to the figure (the `Modal` contract).

### 4.7 Charts

- An affected point is a hollow marker in the series colour with the note letter above it; an affected
  bar is outlined (dashed) rather than filled; the legend row ends with a "Notes a" provenance chip that
  opens the strip. Gaps stay gaps.
- PNG export notes carry the same sentences as the strip: "Note a: Saved calculation predates …
  (Operating margin Q2 2025, Q2 2026 …)", the unavailability line, the calculated line, the FCF
  definition, source date and disclosure, wrapped beneath the plot as today.
- Dense-period behaviour (minimum plot width, every tick, the scroll region) is unchanged.

### 4.8 Narrative

- Amounts in the compact display form the rest of the page uses ($60.8B, $1.7B, 26.1%, 2.23×,
  −12.1pp); periods as "Q2 2026"; citation chips unchanged, with the note letter inside the chip of a
  cited figure that carries one. Ratios keep the engine's threshold rule (`_ratio_threshold_value`):
  2.2256x prints as 2.23×, but a ratio within rounding of 1.00× keeps the decimals that show which side
  of 1.00× it is on (1.00004× is never printed as "1.00×, above 1.00×"). The exact value stays in the Sources entry ("$60.8B
  (60,801,000,000)"), so the appendix keeps full precision and the fidelity scan, which licenses
  compact-scale tokens, keeps passing.
- Header chips: "39 sources" (quiet), "Notes a" (provenance chip, opens the strip), "Cached".
- Sources list: "1 · Revenue · Q2 2026 · $60.8B (60,801,000,000) · Original filing ↗" / "† calculated
  from filing figures", one line each, wrapping at phone widths.

**Red flags, before (production, verbatim):**

> Free-cash-flow conversion fell to 0.11× net income in 2026Q2 vs a 1.11× historical average —
> earnings and cash are diverging. Source operands: Free cash flow USD 12,846,000,000 in 2024Q1 [16];
> Net income USD 12,369,000,000 in 2024Q1 [17]; Free cash flow USD 11,197,000,000 in 2024Q2 [18]; …
> (sixteen more) …; Free cash flow USD 1,746,000,000 in 2026Q2 [11]; Net income USD 15,848,000,000 in
> 2026Q2 [2].

**After:**

> Free-cash-flow conversion fell to 0.11× net income in Q2 2026 vs a 1.11× historical average —
> earnings and cash are diverging.
> ▸ Show the 20 figures behind this

The disclosure opens a four-column list (Quarter · Figure · Value · Source chip) of the same twenty
citations, in the page, keyboard-operable, and the PDF prints the list in full under the finding. The
sentence keeps the two figures it asserts; the evidence is one click away rather than in the reading
line. The same treatment applies to the margin (3 figures) and debt (2 figures) findings.

### 4.9 Period selector

- `SegmentedControl` Annual · Quarterly (the design system's single-choice group, replacing the
  hand-rolled toggle).
- Presets as quiet pills: Last 4 · Last 8 · Last 12 (Last 5 · Last 10 in annual mode), the active one
  tinted.
- Two compact selects, From and To, in the data face, listing every available period with its
  availability marks (a `†` for a calculated Q4; a disabled option for an annual period without core
  data); choosing one clamps the other to the 12-quarter cap.
- One summary line: "12 quarters · Q3 2023 – Q2 2026 · 3 calculated Q4 columns (†) · data available
  Q2 2011 – Q2 2026 · up to 12 at a time", then Run analysis.
- The 61-chip grid is retired. On phones the selects are full width and 42 px tall; from 640 px up they
  are 36 px toolbar fields beside the segmented control.

### 4.10 One vocabulary across exports

| Surface | Affected value | Comparison built on it | Unavailable value | Summary | Full precision |
|---|---|---|---|---|---|
| Web | `26.1%†ᵃ` | `−9.7ppᵃ` | `—ᵇ` | Data notes strip (counts + grouped notes) | evidence dialog, Sources list |
| PDF | the same letters as footnote marks in the grid and after narrative citations | same | `—ᵇ` | "Data notes" list in the same order under the grid, replacing "[note n]" / "[unreconciled]" | Sources & Methods appendix (unchanged) |
| Excel | cell comment "Data note a: …" (replacing the limitation sentence) | same on growth cells | empty cell with the comment | "Data notes" block on the cover sheet with the same counts | Sources & Methods sheet (unchanged, with a Note column) |
| PNG | hollow marker + letter | hollow marker + letter | gap | "Note a: …" lines under the plot | not applicable |

The backend owns the grouping so the four cannot disagree (Phase 2).

## 5. Keyboard, screen reader and touch

- Reading order: picker → headline cards (each a definition group: term, value button, period and
  delta) → Data notes (a disclosure; open, a list of notes) → chart panels (heading, legend, Notes chip,
  controls, the plot as a named scrollable region; arrow keys scroll it) → narrative (headings,
  paragraphs with citation chips, evidence disclosures, Sources list) → table window control → table
  region → cells.
- Table: the scroll container is `role="region"`, `tabIndex=0`, named "Metrics by period, scrollable
  table of 12 quarters"; with focus, Left/Right scroll by the snap unit (one column), Home/End to the
  ends. The table has a caption that states the basis of the change line. Row headers are `<th
  scope="row">`, column headers `<th scope="col">`. Each value is a button named as in §4.2; a cell's
  change line carries an sr-only "change vs prior quarter". No cell text is clipped or truncated.
- Announcements: the strip's summary is plain text; opening a note is a disclosure, not a live region.
  The evidence dialog is `aria-modal`, labelled by its title; the note status line reads "Needs review,
  note a" before the reason.
- Touch: 36 px segments from 640 px up and 36–42 px on phones for the mode, window and range controls;
  figure buttons are inline text targets (the WCAG 2.5.8 inline exception) and the dialog is also
  reachable from the Sources list; the table scrolls by swipe and snaps to columns; the chart plot
  scrolls by swipe inside its region, never the page.
- Colour: letters and `†` carry the meaning; tones carry direction, as today. Warning ink is 6.4:1 on
  cream and inside its tint 5.2:1; amber-500 on navy in dark. Hollow markers keep a 2 px stroke of the
  series colour (≥ 3:1 on both grounds).

## 6. Before and after

| Measure (state 2) | Current build | Prototype |
|---|---|---|
| Repeated source-check labels on the page | 33 | 0 (41 one-letter affixes; one strip) |
| Document width at 390 / 320 | 429 / 413 | 390 / 320 |
| Widest label past a KPI card edge at 390 / 320 / 200% text | 54 / 89 / 126 px | 0 / 0 / 0 |
| KPI value tops at 390 | 37 / 53 / 53 / 53 | 37 / 37 / 37 / 37 |
| Table width at 1480 | 2,076 (container 1,054) | 1,062 (container 1,062, no scroll) |
| Period column widths at 1480 | 77–105 clean, 234–240 warned | 77 all |
| Table at 1024 / 768 / 390 | 2,076 at every width | 1,044 / 1,044 / 920; Newest 6 fits ≥ 768 |
| Column half-hidden under the sticky column | observed in production | 0 at every width |
| Count the reader sees | "24 source checks needed" (26 in production) | "10 values need review · 24 comparisons built on them · 10 unavailable" |
| Evidence for a legacy margin | "26.06536077 pure", no inputs | "26.1% · exact 26.06536077% · Needs review · Note a · lineage not recorded" |
| Red flags, FCF finding | 1 sentence + 20 inline operands | 1 sentence + "Show the 20 figures behind this" |

Screenshots for every configuration are regenerated by the harnesses (`--shots`); they are not
committed.

## 7. Implementation brief

**Status (2026-10-10).** Phase 1 items 1–2 and 11 are on `main` (#1199: `lib/dataNotes.ts`,
`DataNoteMark`, `DataNotesContext`, `DataNotesLink`, the presentation allowlist gate
`tests/unit/analysisDataNotePresentation.spec.ts`, the `DESIGN.md` / `DESIGN_SYSTEM.md` entries and
`lessons/frontend-variable-text-must-not-size-a-wrapping-row.md`); items 3–4 are on `main` (#1200:
`KpiStrip` as a definition list with subgrid rows and "latest available", `DataNotes.tsx` in place of
the sources card, `formatAnalysisPeriod` in `lib/periodLabels.ts`). Items 5–10 and Phase 2 are open.
Each of those PRs recorded its own gate tail and browser measurements in its body.

Risk tier per `AGENTS.md` §5: Phase 1 is frontend-only (routine); Phase 2 touches
`trend_analysis/*`, `trend_analysis_service.py`, the export services and `fact_provenance.py`
consumers (routine), never `facts_service.py`, prompts or evals. The quarterly data repair is a separate
operational action and is not part of this brief.

### Phase 1 — frontend, no backend change, works on today's payload (one PR per item or two PRs)

1. **`features/analysis/lib/dataNotes.ts`** (S): `groupDataNotes(dataset)` per §4.1, `noteFor(point)`,
   `noteForComparison(point, basis)`. Unit test with a synthetic dataset covering review, unavailable,
   mixed and clean cases, and a pinned count test against a trimmed Meta fixture. Keep `provenance.ts`'s
   `REASONS` as the one copy source; rewrite sentences there.
2. **`DataNoteMark.tsx`** (S) replaces `ReconciliationBadge.tsx` at every analysis site (`KpiStrip`,
   `MetricsTable`, `TrendCharts`, `NarrativePane` and its citation list; `SourceValue` does not use
   it). `ReconciliationBadge` stays for its fundamentals and peers consumers
   (`FundamentalsTrendChart`, `PeerComparisonPanel`) until those surfaces adopt the mark;
   `Badge variant="warning"` stays for its other uses. Gate: an allowlist spec
   that fails on `Badge` or `whitespace-nowrap` inside `features/analysis/components/{KpiStrip,MetricsTable}.tsx`
   and on any `text-[` smaller than 11 px in `features/analysis`.
3. **`KpiStrip.tsx`** (S): `<dl>` + subgrid rows, period line, "latest available" marker, value button.
   Update `kpi-strip.spec.tsx` (it pins the "Growth source check needed" text, which goes).
4. **`DataNotes.tsx`** (M) replaces `SourcesMethods.tsx`: strip, counts, notes list, the existing prose,
   `id` per note for the chips to target. Update `analysis-source-quality.spec.tsx` (it pins the
   "Source check needed" text; it does not assert the "N source checks needed" count).
5. **`DataTable.tsx`** (M): `layout: 'fixed'` with `colWidths`, a `scrollRegion` option (role, name,
   arrow keys, Home/End), `snapColumns` (snap type, padding and the whole-column inline-end pad with a
   `ResizeObserver`), and opt-in row-header semantics (`rowHeader` renders the first cell as
   `<th scope="row">`). **`MetricsTable.tsx`** (M): column widths, header basis line, change line without
   prefix, "—ᵇ", window control (`SegmentedControl`), start-at-newest on phones with the hint, 12-of-12
   caption. Update `metrics-table.spec.tsx`.
6. **`SourceValue.tsx`** (S): display form + exact value, substituted formula, checks block, lineage
   block with the absent-lineage copy; never a storage unit.
7. **`NarrativePane.tsx`** (M): compact amounts and periods at render time until Phase 2 renders them
   server-side (a display transform over the code-generated text; the fidelity scan already licenses the
   compact forms); fold "Source operands: …" into an evidence disclosure (the prefix is a code constant;
   export and pin it); header chips; Sources list lines. Update `narrative-pane.spec.tsx`.
8. **`TrendCharts.tsx`** (S): `dot` render for hollow markers with the letter, dashed outline for a bar
   with a note, "Notes a" chip, PNG note sentences from `groupDataNotes`. Update
   `trend-charts-annotation.spec.tsx`, `trend-charts-legend.spec.tsx` (it owns the warning and PNG
   metadata assertions) and `chart-export.spec.ts`.
9. **`PeriodPicker.tsx`** (M): `SegmentedControl`, presets, From/To `Select`s with the cap clamp,
   summary line; `chipsFor`/`nextRange` become option builders. Update `period-picker-helpers.spec.ts`.
   `SegmentedControl` has no unavailable-option API today and the picker disables Quarterly when a
   company has no quarterly coverage: add an `aria-disabled` option (early return in the handler, the
   DS unavailable recipe, never native `disabled`) so that state survives the migration. Note the Run
   button keeps native `disabled` until the rule-6 item in `tasks/todo.md` is resolved.
10. **Gate** (M): `tests/e2e/analysis-layout.spec.ts` on the real page with the API answered in the
    browser (the harness in `tasks/analysis-redesign-2026-10/harness/measure-current.mjs` is the draft):
    no document overflow at 320/390/768/1024/1480 and at 200% text; no KPI child past its card; value
    tops equal within a row; period columns equal; no cell text clipped; no column partly under the sticky
    column at the far-right rest position; the window control's "Showing 6 of 12" line; the strip's counts
    for the three fixture states. The overflow probe compares `document.documentElement.scrollWidth`
    with the configured viewport width, never with `window.innerWidth` (mobile Chromium widens the
    layout viewport to the content). Grid tracks that hold a scrolling plot or table are
    `minmax(0, 1fr)` with `min-width: 0` on the item, the class of defect
    `lessons/frontend-variable-text-must-not-size-a-wrapping-row.md` describes. One mutation proof: reintroduce a nowrap label in a KPI card and show the
    spec failing.
11. **Docs** (records, same PR as item 2): `DESIGN.md` Calculation Provenance Rule ("Amber 'Source check
    needed'" → the lettered note, "Unavailable" → "— with its note letter; 'Unavailable' in the evidence
    view and exports"), `frontend/DESIGN_SYSTEM.md` §4 (a "Data note mark" entry; the table scroll-range
    rule) and `frontend/DESIGN_SYSTEM.md` §10 (chart marks, PNG notes), sidecar through the
    `design-docs-maintenance` skill.

### Phase 2 — backend, one verified deploy

1. **`trend_analysis/dataset_quality.py`** (M): `data_notes(dataset)` with the §4.1 rule; attached as
   `dataset["data_notes"]` in `build_dataset` (outside the fingerprint, like `data_as_of`); a shared
   JSON fixture pins the frontend and backend grouping to identical output. The frontend prefers the
   server's list and keeps the local grouping for snapshots that predate it.
2. **Exports** (M): `analysis_export_metadata.py` note labels; PDF grid footnote letters and the "Data
   notes" list; Excel cover-sheet block and comment text; PNG unchanged (frontend). Tests:
   `test_export_service.py`, `test_excel_export.py`, `test_data_completeness.py`'s export pins.
3. **Narrative rendering** (M): `_point_value` display form and "Q2 2026" periods for the catalogue;
   the red-flag operands as a structured `evidence` list on the completion (frontend renders the
   disclosure from it) with the inline sentence kept for the PDF; a `NARRATIVE_FORMAT_VERSION` beside
   `PROMPT_VERSION` in the cache key so cached narratives regenerate lazily, metered as system-invalidated
   (the existing `invalidated` path). `scan_numeric_fidelity` needs no change (compact tokens are
   licensed by `_FIDELITY_SCALES`; period tokens are skipped). The prompt file is untouched, but the
   catalogue text is model input (the model selects observation IDs from lines that carry the
   rendered sentences), so this item is an AI-facing change: run the eval RUNBOOK's regression gate
   (B1) and judge the artifact as for a prompt change, and expect the lazy regeneration to cost
   inference even though it is unmetered for users.

### Not in this brief

- Running the quarterly data repair (`docs/quarterly-data-repair.md`); the UI above is designed to look
  right before it (state 2) and after it (state 1).
- Any frontend override that marks a legacy record validated, hides a note, or shows "verified".
- Changing what counts as `needs_review` or `unavailable`.

## 8. Where this review departs from the brief

- The brief asks for "a sticky metric column". It exists (#C2, 2026-07). The table's problem is label
  geometry plus an unbounded scroll range; fixed rem columns and the whole-column range rule are the
  fix. Twelve quarters then fit at 1480 px with no scroll at all.
- The brief treats the 26 as a wrong count. It is the right count of the wrong thing. The strip keeps
  both numbers (values, comparisons) because they answer different questions, and adds the basis split.
- The brief suggests the narrative repair is backend work. Folding "Source operands:" is a one-line
  presentation rule the frontend can apply to every cached narrative today; the structured evidence
  payload follows. Shipping the fold first means no regeneration spend for the readable form.
- On phones I rejected stacking (12 periods × 20 metrics = 240 rows of cards) and transposing (20
  columns); contained, snapped, sticky, keyboard-reachable scrolling with an explicit window is the
  honest treatment for a data table, and the brief's own exemption for twelve unreadable columns is met
  by never shrinking them.
- A single page-level banner for exceptions was rejected: it would say that something is wrong without
  saying where. The letter beside each affected figure keeps material exceptions apparent at the point
  of use at a cost of two characters.
- The period selector keeps availability information that the chips carry today (calculated Q4s,
  years without core data) inside the select options; a compact control must not drop it.

## 9. Decisions for the founder

Taken on 2026-10-10: the founder aligned with all five recommendations below ("regarding decisions for
founder - i'm aligned with your recommendations"). They are recorded here and in
`tasks/analysis-redesign-2026-10/astra-prompt.md`, the hand-over prompt for the implementing agent.

1. Letters (a, b, c) as the note mark, or one warning glyph for all notes. Recommended: letters.
2. `scroll-snap-type: x mandatory` (every rest position whole columns) or `proximity` (gentler
   trackpad feel, alignment not guaranteed). Recommended: mandatory with the range rule.
3. The "Q2 2026" / "Q2 ’26" period vocabulary for the analysis surfaces and their exports. Recommended:
   adopt; the filing and company pages keep their own vocabulary.
4. Keep the KPI strip two-up at 320 px (measured fine, "Free cash flow" wraps) or go one-up below 360.
   Recommended: two-up.
5. Whether the table window should also drive the charts. Recommended: no.

## 10. Running the prototype and the harnesses

`tasks/analysis-redesign-2026-10/README.md` explains the folder; in short: open
`tasks/analysis-redesign-2026-10/prototype/index.html`, switch state, view (proposed / today's markup),
table window, theme and 200% text in the bar at the top; the readout shows page overflow, KPI
containment and the table's width live. The harnesses regenerate `measurements/*.json` and screenshots.

## 11. Corrections from the Track A verification (2026-10-10)

The implementing agent verified the proposal against `main` and ran both harnesses before building
(PR #1197, Track A comment). Each finding and where it landed:

- **Phone overflow in the prototype.** The chart panels kept their 480 px min-content width inside
  `1fr` tracks (522 px items at 390 and 320), and the table toolbar overflowed at 320; both harnesses
  compared the document with `window.innerWidth`, which hid it. Fixed in the prototype
  (`minmax(0, 1fr)` tracks, `min-width: 0`, wrapping toolbar); both harnesses now compare with the
  configured viewport; the recorded runs were regenerated; §1, §2.3 and §6 state the corrected rule.
- **"200% browser zoom"** in the harnesses is 2x device-scale emulation at half the CSS width, not
  native browser zoom; stated in §1.
- **Font-dependent widths** reproduce within a few pixels, not exactly (the reviewer's run: table
  2,044 px, KPI overflow 49.1 / 84.1 / 115.3 px); the proposal's numbers are this review's run.
- **Fixture vs production.** The fixture is companyfacts-only modelled legacy state (230 / 10 / 14 + 10),
  not the captured production snapshot (236 / 4 / 16 + 10); both remain distinct fixtures (§2.2).
- **Pruned provenance is not the API schema** (§2.2).
- **Ratio precision** keeps the threshold rule (§4.8).
- **YoY fallback in the table** keeps an explicit label (§4.5).
- **Grouping edge cases**: legacy `reconciled: false`, populated values without a validation record,
  annual CAGR / window changes, comparison-only and mixed reason sets (§4.1).
- **`ReconciliationBadge` consumers** outside analysis stay; `SourceValue` is not a site (§7, item 2).
- **A record's own source link** is shown whether or not it has inputs (§4.6).
- **Narrative header chips** do not wrap today; only the outer group does (§2.4).
- **`SegmentedControl`** needs an unavailable-option API for the picker's Quarterly state (§7, item 9).
- **`DataTable`** needs opt-in row-header semantics (§7, item 5).
- **No repair promise** in the dialog copy (§4.6).
- **`source_conflict`** has no backend producer today; state 3 is a simulation (§2.2).
- **Catalogue wording is model input**; Phase 2 item 3 goes through the eval gate, and regeneration
  costs inference even when unmetered (§7).
- **Test pins**: `trend-charts-legend.spec.tsx` also changes; the source-quality spec pins text, not the
  count (§7, items 4 and 8).
