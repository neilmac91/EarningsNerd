# Multi-Period Analysis: data notes, aligned figures, a compact table — design proposal and implementation brief

Date: 2026-10-10 · Scope: `/analysis` results surface (KPI strip, Sources & methods, charts, narrative,
metrics table, period picker) and the PDF, Excel and PNG exports that mirror it · Status: the five original §9
decisions are taken (2026-10-10); amended decision 4 and decisions 6–9 were adopted on 2026-10-11 under the founder's delegation to Astra's recommendation; Phase 1 items 1–10 and 11 of §7 are merged (#1199, #1200, #1202, #1203, #1206) and Phase 2 in #1225 (the status note under §7's Phase 2 says where it departs from the brief and what stays open);
the follow-ups in §11 are open; this document itself ships nothing; on 2026-10-25 the table window
(§4.5) was retired with the metrics-table number system (see the note under §4.5's window control), and
the current table rule is `frontend/DESIGN_SYSTEM.md` §4, Analysis table; the same day the founder also narrowed the marking rule (`docs/brand/decisions-log.md` D-061), so the
figure affix (§4.2), the strip (§4.3) and the web row of §4.10 are superseded where their notes say,
while §9's decisions stand · Support material:
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

   **Superseded (2026-10-25)** for items 2 and 3: the founder narrowed the marking rule on 2026-10-25 (`docs/brand/decisions-log.md` D-061). A figure carries no
   dagger, and a letter only where its note questions the number (a review note with any reason other
   than the record-only `legacy_calculation`), in the neutral note ink; the strip is one line of fine print
   under the metrics table. Every note stays in the evidence dialog and the data notes, and §9's decisions
   stand. The current rules are `DESIGN.md`'s Calculation Provenance Rule and `frontend/DESIGN_SYSTEM.md`
   §4 (Data note mark, Data notes strip); this section keeps the October 2026 record as it was.
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
   counts; the narrative stays readable, the Sources & methods appendix keeps full precision.

Measured on the prototype with the real Meta Platforms 12-quarter dataset in its production-like
state, with probes that read the rendered text and visit every scroll rest position (§2.3): no page
overflow, no card content outside its KPI card, no clipped cell text and no period column half-hidden
under the sticky metric column at 1480, 1054, 1024, 768, 390 and 320 CSS px, in both themes, at 2x
device-scale emulation of 200% browser zoom, and at 200% text size at 1480, 390 and 320; twelve
columns fit at 1480 px without scrolling; the "Newest 6" window fits without scrolling from 768 px up.
Two rules make the 200%-text phone configurations pass: the cards go one-up when the page is narrower
than 17 em of its own text size (§4.4), and the metric column stops sticking when the scroll area
cannot show a whole period column beside it (§4.5). Earlier builds measured less than this: the first
overflowed on phones, and the first two runs' probes compared element boxes rather than text and read
one row at the far right; the Track A verification and the comprehensive review of 2026-10-10 caught
both (§11). The current build at `97293e7`, measured the same way, overflows the device by 39 px at
390 and 93 px at 320 (78 px at 1480 with 200% text; 425 and 495 px at 390 and 320 with 200% text, where
the figures themselves run 51 and 86 px past their cards), places a label 54 px past its card edge at
390 (126 px at 1480 with 200% text; 303 and 338 px on the phones with 200% text), and lays the table out
2,076 px wide at every width (4,151 px with 200% text).

## 2. Observed

This section describes `main` at `97293e7`, the build this review measured. Phase 1 items 1–2 and 11
of §7 landed on `main` in #1199, items 3–4 in #1200, item 5 in #1202 and items 6–9 in #1203 on
2026-10-10, while this proposal was in review; the current page no longer shows the labels, the table,
the dialog, the narrative or the picker described here. The section is kept as the record of what the
redesign answers.

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
- `build_observation_catalogue` (`trend_analysis/observations.py`, re-exported by `trend_analysis_service.py`) renders each red flag as the detector's sentence
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

Probes (both harnesses, after the comprehensive review of 2026-10-10): page overflow against the
configured viewport; KPI containment from the rendered text (text-node rectangles and `scrollWidth`
against `clientWidth` of every block, `.sr-only` excluded), not from element boxes alone; cell text
against the cell's content box on both sides; sticky-column occlusion (a header straddling the sticky
edge) at the start, at every column boundary and at the far-right end of the scroll range, not only at
the far right, with the table's `scroll-snap-type` recorded; every probe asserts how many elements it
found. The recorded run of the current build (`measurements/current.json`) was retaken
with the widened probes on the same `97293e7` build: every earlier number reproduced exactly (the
labels, the table and column widths, the 54 / 89 / 126 px card overflow, the 39 / 93 / 78 px page
overflow), no cell text is clipped (its columns size to their content, which is the defect), and the
occlusion probe now measures the half-hidden column that only the production screenshots had shown:
the table does not snap (`scroll-snap-type: none`), so a scroll rests wherever it stops, and every
position between two column boundaries leaves a period column straddling the sticky edge; at the
boundaries themselves only the far-right end does, at every width (2025Q1 at 1480, 2025Q2 at 1054 and
1024, 2025Q3 at 768 and at 1480 with 200% zoom or text, 2026Q2 at 390 and 320 and at 390 with 200%
text) except 320 with 200% text, where the range ends on a boundary. Until Codex's thirty-third round
the probe stepped by the first period column's width, an arbitrary grid in a table of 77–240 px
columns, and reported 9 of 11 such positions at 1480, 16 of 18 at 390 and 17 of 19 at 320. The run was retaken once more
after Codex's seventh round with the phone 200%-text profiles the prototype harness already ran; the
sixteen earlier records reproduced exactly again.

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
| 390 at 200% text | **815** | 33 | **302.6 px** (and the figures: 51.4 px) | 105 / 137 / 169 / 137 | 4,151 / 228 |
| 320 at 200% text | **815** | 33 | **337.6 px** (and the figures: 86.4 px) | 105 / 137 / 169 / 137 | 4,151 / 158 |

Document widths are measured against the configured viewport (mobile Chromium widens the layout
viewport to the content, so `window.innerWidth` cannot detect overflow). Table columns: warned
period columns 234–240 px, clean ones 77–105 px (469–481 vs 154–209 at 200% text). The 33 labels are four texts: "Source check needed", "Growth source check needed", "24 source
checks needed" and "Source checks needed". The far-right sticky-column occlusion the founder saw is
reproduced by the retaken run (the far-right rest position leaves 2025Q1 straddling the sticky edge at
1480 and 2026Q2 at 390 and 320; the first probe had been blind, §11); the mechanism, a scroll range that
is not a whole number of columns, is real, and the prototype reproduced it before its range rule (§4.5).

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
- Notes are lettered a, b, c by kind: review notes first, then notes for figures without a validation
  record, then unavailability notes. Within a kind, letters follow first appearance in one traversal of
  the report's values (series order, then period order), and the notes that only comparisons raise
  (comparison-only or mixed reason sets) follow the value notes, in the same traversal order. This is
  the order `lib/dataNotes.ts` on `main` assigns (#1199) and the one Phase 2 must reproduce; a note is
  keyed by its canonical set of reason codes, whatever order the operands supplied them. Letters are
  stable within a snapshot; a new snapshot may re-letter.
- The grouping must also carry: a populated value whose record has no provenance at all (older
  snapshots) as a "no validation record" note that claims nothing; a legacy `reconciled: false`
  without provenance under the `source_check_needed` key; annual CAGR and window-pp comparisons
  (`cagr_provenance`, `window_pp_provenance`) in the comparison counts; and a comparison whose reason
  set matches no value's (a comparison-only or mixed set) as its own lettered note.
- Copy per reason reuses `provenance.ts` `REASONS`, rewritten to one sentence of plain English each
  (the current `legacy_calculation` sentence stays: "This saved calculation predates the current source
  checks. Its inputs need review.").

What a reader sees in the three states (the strip's summary line; state 2 is the production-like one):

- State 1: "Data notes · No figures need review · 230 checked · 10 unavailable (a) · 101 calculated †".
  Open: note a (unavailable) "Not available in this dataset. EPS (basic), EPS (diluted) (Q4 2023, Q4
  2024, Q4 2025); Capital expenditures, Free cash flow (Q3 2023, Q4 2023) · 10 values shown as — ·
  growth is not computed across a gap."
- State 2: "Data notes · 10 figures need review (a) · 24 comparisons carry note a · 10 unavailable (b) ·
  101 calculated †". Open: note a "This saved calculation predates the current source checks. Its inputs
  need review. Operating margin (Q2 2025, Q2 2026); Net margin (Q2 2025, Q2 2026); Working capital (Q4
  2023, Q1 2024, Q2 2026); Current ratio (Q4 2023, Q1 2024, Q2 2026) · Comparisons: Operating margin (Q2
  2025, Q3 2025, Q2 2026); Net margin (Q2 2025, Q3 2025, Q2 2026); Working capital (Q4 2023, Q1 2024, Q2
  2024, Q4 2024, Q1 2025, Q2 2026); Current ratio (Q4 2023, Q1 2024, Q2 2024, Q4 2024, Q1 2025, Q2 2026)
  · 10 figures · 24 comparisons carry this note: 14 quarter-over-quarter changes in the table and 10 year-over-year changes, of which
  the headline cards show one and the exports carry all · figures are shown as stored; their source
  lineage is not recorded"; note b as in state 1.
- State 3: "Data notes · 3 figures need review (a) · 6 comparisons carry note a · 10 unavailable (b) ·
  101 calculated †". Open: note a "Available sources disagree on this figure. Revenue (Q2 2026);
  Operating margin (Q2 2026); Net margin (Q2 2026) · Comparisons: Revenue (Q2 2026); Operating margin (Q2
  2026); Net margin (Q2 2026) · 3 figures · 6 comparisons carry this note: 3
  quarter-over-quarter changes in the table and 3 year-over-year changes, of which the headline cards
  show two, the revenue growth chart shows one and the exports carry all · check the original filing before
  relying on these figures";
  note b as above.
- When the table window is narrower than the report (Newest 6, Earliest 6), the table clause adds how
  many of those changes are in the quarters shown, since the report-wide count no longer describes the
  page: state 2 with Newest 6 reads "14 quarter-over-quarter changes in the table (8 in the 6 quarters
  shown)", state 3 with Earliest 6 "3 quarter-over-quarter changes in the table (none in the 6 quarters
  shown)"; with the full window the clause is unchanged. (Retired with the table window on 2026-10-25:
  the table clause now counts the whole table; see the note under §4.5's window control.)
- A year-over-year change the table shows as the labelled fallback of a cell without a quarter-over-quarter
  change (§4.5) is counted among the places that show it: "…, of which the headline cards show one, the
  table shows one as its labelled fallback, … and the exports carry all". None of the three fixture states
  has a noted fallback (their four fallback cells, EPS in Q1 2025 and Q1 2026, pass their checks), so the
  clause appears only with a dataset that has one.

The summary names each note's letter beside its count, so the resting line is the key to the marks on
the page: each clause names the letters of the notes it counts, so a note with values and comparisons
appears in both of its clauses, a comparison-only note (a passed figure whose comparison carries a
concern or has no validation record) appears in the comparison clause alone, and "No figures need
review · N checked" leads whenever every populated figure passed, even when a comparison carries a
note. An open note lists the metrics and periods of its values and, on a second line, those of its
comparisons ("Comparisons: Revenue (Q2 2026)"), so a comparison-only note still says where it is. The
counts of comparisons are the dataset's (every comparison the backend computed from an
affected figure, which the exports carry), and the note says where on the page they appear rather than
claiming a surface that does not show them (the charts plot values; the one comparison a chart shows is
revenue's YoY growth line, which the locator counts when it carries the note). The strip
`DataNotes.tsx` shipped in #1200 prints "10 figures need review · 24 comparisons need review"; the
letters, the "carry note a" wording and the locator sentence are the open copy change (§11).

"Checked" and "automated checks passed" mean exactly what the backend records: a reported figure was
taken from the company's XBRL data as filed with the SEC (`normalize_companyfacts` admits SEC's own
structured data, rejecting only a negative amount), and a calculation combined inputs that passed with
compatible periods and units (`calculated_provenance`). Nothing is "verified", nothing is compared with
a second source, and the strip's prose says so: "Automated checks confirm that reported figures come
from the company's SEC XBRL data and that calculations combine compatible periods and units; they are
not an audit of the company's accounts." The word "verified" does not appear; a clean report says "No
figures need review", never a sage count of figures that "passed".

### 4.2 The figure affix: what stays visible beside an affected number

Beside a figure, at most two marks in the data face, never wrapping and never wider than two characters:

- `†` in secondary ink for `method == calculated` (unchanged meaning).
- a superscript letter for the figure's note: warning ink (`warning-light` / `warning-dark`) only for a
  review note, the muted pair `DataNoteMark` uses (tertiary in light, secondary in dark; 5.2:1 and
  5.8:1 on panel) for a no-validation-record note and after "—" for an unavailable value; the same
  letter, on the change line, for a comparison that carries a note. Warning ink claims an unresolved
  concern; a missing record and a gap claim nothing (`DESIGN.md`, the Calculation Provenance Rule).

The letter is the signal, not the colour, so the meaning survives colour-vision deficiency and
monochrome print. Letters are 11 px (the dense-annotation floor) at every size; they ride a zero
line-height superscript so a row with notes is no taller than one without.

Accessible name of the figure's button: "Net margin, Q2 2026: 26.1%, calculated, data note a,
comparison carries data note a. View source and calculation": the display form the button shows (WCAG
2.5.3, Label in Name; the raw value and raw period key the first implementation used were replaced in
#1203), with the stored value in the dialog. The glyphs are `aria-hidden`, on the change line too; the
comparison's note is announced once, in the figure's name, never again by a mark of its own.

On click, Enter, Space or tap the figure opens the evidence dialog (§4.6). The letter itself is not a
separate control (it would add dozens of Tab stops); the Data notes strip and the dialog both explain
it, and the notes chip on a chart or the narrative header jumps to the strip.

**Superseded (2026-10-25).** The founder narrowed the marking rule on 2026-10-25 (`docs/brand/decisions-log.md` D-061): no `†` beside a figure (a sentence above
the table names the calculated metrics, and the figure's name still says "calculated"), and a letter, in
the note ink and never warning ink, only for a note that questions the number. A record-only, unknown or
unavailable note marks nothing and is named in the dialog, not in the figure's name. The Q4 column
header's `†` and the period picker's stay: they mark periods. §9's decisions stand; the current rule is
`frontend/DESIGN_SYSTEM.md` §4, Data note mark.

### 4.3 Data notes strip

Position: under the KPI strip, where `SourcesMethods` sits today, so it is the legend for everything
below. Form: a hairline-topped and -bottomed strip in the trust-strip manner, not a card; a
`<details>` whose summary is the one-line count (title in primary ink, counts in the data face, review
counts in warning ink, the all-passed count in sage). Open, it lists the notes as a two-column list
(letter, then sentence / where / counts) followed by the existing Sources & methods prose (calculated
figures, Q4 derivation, EPS, FCF definition, data as of, snapshot). Every chart's "Notes a" chip and the
narrative header's chip open this strip and scroll to the note. Owner: a new `DataNotes.tsx` that
replaces `SourcesMethods.tsx`.

**Superseded (2026-10-25).** The founder narrowed the marking rule on 2026-10-25 (`docs/brand/decisions-log.md` D-061): the data notes are one line of fine print
8px under the metrics table, with no hairlines and no warning ink. The summary names each marked note by
its letter, places and words and counts the gaps, the figures with no check recorded and the calculated
figures; "No figures need review" (decision 9) never stands beside a record-only note. The open detail
lists every note, and the comparison locators are gone. §9's decisions stand; the current rule is
`frontend/DESIGN_SYSTEM.md` §4, Data notes strip.

### 4.4 KPI strip

- `<dl>` grid, `grid-cols-2 lg:grid-cols-4`; each card `grid-rows-subgrid` spanning three rows (label,
  value, period + delta) so the three rows share heights across the strip and every value sits on the
  same line. (Subgrid: Chrome 117, Safari 16, Firefox 71.) Two-up holds at 320 px and 100% text
  (decision 4). When the page container is narrower than 17 em of its own text size (a 390 px phone at
  200% text is 11 em; 320 px at 100% text is 20 em) the cards go one-up: a 48 px figure cannot share a
  173 px card, and the measured overflow at 390 / 320 with 200% text was 55 / 90 px before this rule and
  0 after it (§9, amendment to decision 4).
- Label: the metric name only, eyebrow style, allowed to wrap. Value: 24 px data face with the affix.
  Third row: "Q2 2026 · YoY +28.0%" as two inline items that wrap independently on narrow cards; when
  the card's period is older than the dataset's latest period, "· latest available" in secondary ink
  follows the period, so a metric whose newest quarter is missing is never read as current.
- The value is the button that opens evidence; no label element sits in the card.
- Measured (prototype, state 2): label-to-edge overflow 0 at every width; value tops equal within a row
  at every width (37 px; at 320 the second row is 55 px because "Free cash flow" wraps there, aligned
  with its neighbour).

### 4.5 Metrics table

Shipped in #1202 (`DataTable`'s opt-in `layout="fixed"`, `colWidths`, `cellPadding="compact"`,
`scrollRegion`, `snapColumns` and `Column.rowHeader`; `MetricsTable`'s window, basis line and token
budget in `lib/tableFormat.ts`). The rules, with the corrections of §11:

- `table-layout: fixed` with explicit widths: metric column 8.25 rem (132 px), period columns 4.75 rem
  (76 px) from 768 px up; 6.5 rem and 4.25 rem below (2026-10-25: #1606 widened the phone column to 4.375 rem
  for the 2px each footnote mark keeps; `frontend/DESIGN_SYSTEM.md` §4 holds the current widths). Widths are in rem so they scale with the reader's
  text size. Content never sizes a column, so the cell's content must fit its box: the padding is part of
  the geometry (the prototype uses 0.25 rem per side on phones and 0.5 rem above; #1202 uses the compact
  inset), and a figure is formatted to a glyph budget before it is placed (#1202's `tableTokenBudget`:
  normal precision first, then fewer decimals, compact scale or scientific notation; signs and units stay;
  a non-USD currency code moves to the row heading). That rounding is a presentation decision outside
  the §9 decisions and is recorded there for the founder. Columns stretch when the table is narrower
  than its card (77 px at 1480 with twelve columns, 137 px in "Newest 6"): the gate asserts equal widths
  and the rem minimum, never a pinned pixel value.
- Cell: value line (`$60.8B†ᵃ`), then the change line in the series' financial tone with the sign only
  (`+8.0%`, `−9.7ppᵃ`, `n/m`); the basis is stated once, in the metric column's header ("value · Δ vs
  prior quarter") and in the caption. Twelve columns of "QoQ " disappear. The one exception keeps its
  label: a quarter with no QoQ comparison (a gap before it) prints the YoY comparison with an explicit
  "YoY" prefix and an sr-only "change vs same quarter last year"; that line is the one change line wider
  than a period column, so it wraps to two lines ("YoY" / "+35.6%") with top-aligned cells, and the
  caption says what the label means. Clipping is measured on both sides of the content box: a
  right-aligned overflow runs to the inline start, which `scrollWidth` never counts.
- Header: quarter over year on two lines ("Q2" / "’26"); a `†` after the year of a derived Q4 column
  marks the period's flow figures as calculated from annual totals (the balance-sheet figures in that
  column are reported; the per-figure † stays the figure's own mark).
- Unavailable: "—" with the note letter, a button only when there is a note to explain.
- Sticky metric column plus a **whole-column scroll range**: the scroll container gets an inline-end pad
  of `(columnWidth − (range mod columnWidth)) mod columnWidth`, recomputed when the container or the
  table resizes (a window or mode change resizes the table, not the container), so the far-right rest
  position starts exactly on a column edge; `scroll-snap-type: x mandatory` with
  `scroll-padding-inline-start` equal to the metric column snaps every rest position to a column. The
  probe visits every rest position: 0 straddling columns at any of them, at every width; with the pad
  removed at 1024 (range 110 px, column 76 px) the probe reports the "Q4 ’23" column straddling the
  sticky edge at the far right, which is the mutation proof for the rule.
- **The metric column sticks only while the scroll area leaves room for one whole period column beside
  it.** At 200% text on a 390 px phone the scroll area is 244 px and the metric column 208 px: the
  column stops sticking, `scroll-padding-inline-start` drops to 0 and the table scrolls as a whole, labels
  included (WCAG 1.4.10 allows two-dimensional scrolling for a data table; a permanently half-hidden
  column is worse than a scrolling label); the label column is then a snap position of its own, so the
  labels can be scrolled back into view (with period columns as the only snap points, mandatory snapping
  settles on the first period column and the labels are never fully visible). The sticky cell stays opaque on row hover in dark (#1206
  replaced the `dark:group-hover:bg-white/[0.03]` wash that let columns show through with the panel fill,
  and its gate measures the painted background).
- **Window control** on the table header (`SegmentedControl`, `size="md"`, full width on phones): All N ·
  Newest 6 · Earliest 6, shown only when the report has more than six periods, with a `role="status"` line
  "Showing 6 of 12 quarters" (years in annual mode). The default is always All: nothing is dropped
  silently, the window is the reader's explicit choice, and charts, headline figures, the data-note totals
  and the exports are not affected by it. Choosing a window keeps focus on the control.
  **Superseded (2026-10-25).** The window, its status line and the locators' "in the N quarters shown"
  clause are retired with the metrics-table number system, reversing this decision (#1202, refined in
  #1273): the table shows every period and scrolls sideways with whole-column snapping, and phones open
  on the newest period with the "← Earlier quarters" hint. At 1280–1920 px every period fits with no
  scroll, and on a 390 px phone the full table and Newest 6 each showed three whole periods, so the window
  only hid data. The current rule is `frontend/DESIGN_SYSTEM.md` §4, Analysis table; this section keeps the
  October 2026 record as it was.
- **Annual mode** uses the same table: basis "Δ vs prior year", the window in years, and the CAGR /
  window-change column last, at the period width, inside the snap set, with its window ("FY2016–FY2025")
  in the header. The landing page's `AnalysisDemo` and the `AnalysisTeaser` render the annual sample with
  the fixed columns and without the window control.
- **Keyboard and focus**: the scroll container is a named `region` that is a Tab stop only while it
  overflows; Left/Right move one column, Home/End the ends, handled only when the region itself has focus
  (a cell's dialog bubbles its keys through the React tree); a focused cell is scrolled whole into view,
  clear of the sticky column. Focus picks the snap stop itself: the column's own stop when it starts left of
  the sticky column's edge, else the first stop that shows its far edge, never past the column's own stop; with the column unstuck,
  the label column is a stop of its own. The browser's focus scroll followed by the mandatory snap can otherwise
  settle on a stop that leaves the value past the edge (11% of one showed at 320 px with 200% text in the
  prototype, until this rule). On phones the table starts scrolled to the newest quarter with the hint "← Earlier
  quarters" shown while the table is scrolled away from its start; at wider widths it starts at the
  earliest quarter without a hint.
- **Print**: disclosures open on `beforeprint` so a printed page carries the notes and the evidence.
- **When contained scrolling is appropriate:** when the table keeps every column at full readable
  width, the row labels stay sticky, the scroll region is a focusable landmark that names itself, every
  rest position shows whole columns, and a visible hint says what is off-screen. Under those conditions
  it is better than shrinking, truncating, dropping periods or stacking twelve periods into 240 rows of
  cards. It is not appropriate when the reason for the overflow is a label (today), when a column can be
  half-hidden (today), or when the page itself scrolls sideways (today on phones).
- Measured (prototype, state 2, light and dark identical, text-aware probes): 1480 → 1,062 px in a
  1,062 px card, no scroll, 77 px columns; 1054 → 1,044 in 964 (scrolls 152 px with the pad); 1024 →
  1,044 in 934; 768 → 1,044 in 678; 390 → 920 in 316 (68 px columns); 320 → 920 in 246; 200% zoom →
  920 in 650; 200% text → 2,088 in 1,302 at 1480 (152 px columns), 1,840 in 244 at 390 and 1,840 in 174
  at 320 with the metric column unstuck. Newest 6 fits without scrolling at every width from 768 up and
  at 200% zoom; at 390 and 320 it cuts the range from 612 to 204 px. No cell text clipped on either side
  of its box, no column straddling the sticky edge at any rest position, at any width.

### 4.6 Evidence dialog (`SourceValue`)

Shipped in #1203 (display figure, stored value, method with substituted arithmetic, checks, lineage,
the comparison block); the vocabulary corrections of §11 remain. The shared `Modal`, size `lg`, titled
"Net margin · Q2 2026" with "Quarter ended 26 Jul 2026" beneath it (the fiscal basis of "Q2 2026"):

1. **Figure**: display form in the data face (26.1%; 2.23×; $1.7B; $6.23) with the affix, then "As
   stored: 26.0653607671%" / "2.2255627095 (ratio)" / "1,746,000,000 USD": the stored number in its
   shortest round-trip form, never re-rounded and never called "exact" (the engine stores a float). The
   storage unit `pure` never reaches the reader; a per-share figure keeps its currency; an operand's
   unit goes through the same display map.
2. **Status**: "Automated checks passed" with the sentence that says what passed ("Taken from the
   company's XBRL data as filed with the SEC." for a reported figure; "Calculated from reported figures
   with compatible periods and units." for a calculation), or "Needs review · note a" with the reason
   sentence, or "Unavailable · note b" with the reason and, for a gap, "Changes that need this quarter are
   not shown.", or "No validation record" with "No automated check result is recorded for this figure.
   No verification claim is made." Never "verified"; never "withheld" (a reader hears EarningsNerd
   holding a number back; the record is unavailable).
3. **Method**: "Reported in the source filing." or "Calculated by EarningsNerd from reported inputs."
   with the formula in words and, when the operands are known, the substituted arithmetic with the
   operands bound by the concept the formula names, never by their position in the stored list (the
   stored inputs of a margin are `[revenue, income]` while the formula is `income / revenue`):
   "15,848,000,000 ÷ 60,801,000,000 × 100 = 26.0653607671%". Same-concept period arithmetic ("FY −
   YTD9") binds by period span. An unbindable formula shows its words only.
4. **Inputs and source filings**: one row per operand (concept, stored value, period, its own method
   and status, "Open filing ↗" with a distinct name per link, accession, XBRL tag), nested one level
   for a derived quarter (FCF = OCF − capex, where OCF = YTD6 − Q1 shows both reported rows with their
   filings). For a legacy record: "Source lineage is not recorded for this saved calculation. The figure
   is shown as stored. Check the original filing before relying on it." (No promise about a repair: the
   repair is a separate authorisation.) A source link the record itself carries is shown whether or not
   it has inputs (a calculated record never carries one). No source is ever constructed on the client.
5. **Change vs prior quarter** (or "vs same quarter last year", "vs prior year"): the comparison's
   display, its own status, and when it carries a note the sentence "Carries note a: it uses Operating
   margin, Q2 2025, which needs review", so a figure whose own checks passed but whose change line shows
   a letter is explained in its own dialog; then the comparison's formula and inputs.
6. The FCF definition for that series, and the existing "not an audit" line.

Opens from pointer, keyboard (Enter/Space on the figure button) and touch; focus moves in, Tab cycles
(the trailing "Technical source details" summaries are in the `Modal` focus list, so Tab does not leave the
dialog: on `main` they carry `tabIndex={0}`, which its `[tabindex]` selector includes), Escape closes, focus
returns to the figure (the `Modal` contract).

### 4.7 Charts

Shipped in #1203 (chart notes with a placement pass, PNG notes) on the Recharts charts, with the corrections of
§11. Since the trend charts' renderer replaced them (E195, D-064), `docs/design/analysis-trend-charts-spec-2026-10.md`
governs the four trend charts' note marks (its §3.3 and §0.5) under D-061's rule (§4.10's note); the filled bars
stay. The rules:

- No note is drawn inside a plot. An observation whose note questions the number puts its letter in the notes band,
  a 16 px row always reserved under the period axis, centred under its period, in the chart's note ink, never warning
  ink: against the honey series the warning pair measures 1.6:1 in dark and 2.1:1 in light. An affected bar keeps its
  fill (a dashed or hollow bar reads as an estimate in a financial chart). Colours are SVG attributes taken from the
  chart theme, never CSS classes or variables, because the PNG export serializes the SVG in isolation.
- The footnote lines under the plot explain each letter: its series, periods and reason. A gap's line names its
  periods in words with no letter, and a calculated value carries no glyph, its periods named in a footnote line.
- The legend row ends with a "Notes a" provenance chip that names exactly the footnotes' letters, opens the strip and
  moves focus to the note. Gaps stay gaps.
- The plot is a named scroll region that is a Tab stop only while it overflows. After it, the chart's values stop, a
  slider over the periods, speaks each period's readout and its marked notes by letter ("data note a").
- The PNG prints the card's footnote lines, the FCF definition, source date and disclosure, wrapped beneath the plot.

### 4.8 Narrative

Shipped in #1203 (`lib/narrativeDisplay.ts`: compact amounts, the 1.00× threshold kept, colliding
amounts kept precise; the evidence fold; `lib/figureDisplay.ts`). The rules, with the corrections of §11:

- Amounts in the compact display form the rest of the page uses ($60.8B, $1.7B, 26.1%, 2.23×,
  −12.1pp); periods as "Q2 2026"; citation chips unchanged, with the note letter inside the chip of a
  cited figure that carries one. **Relation-safe compaction is a rule of this design, not the engine's**
  (`_ratio_threshold_value` in `trend_analysis/formatting.py` prints four or more decimals and never two): a figure is shortened only
  while every relation the sentence states stays visibly true, against 1.00× and against the other
  operand of a comparison; otherwise decimals are added until the figures differ (as the engine's
  `_ordered_percentage_values` does for percentages). 2.2256x prints as 2.23×; 1.0033x, above 1.00×,
  keeps "1.0033×"; free cash flow of 12,846,000,000 below net income of 12,849,000,000 prints "$12.846B
  … $12.849B", never "$12.8B was below net income of $12.8B". Relations themselves are computed on raw
  values; percentage tokens are left as the engine emitted them. The stored value stays in the Sources
  entry ("$60.8B (60,801,000,000)"), so the appendix keeps full precision and the fidelity scan, which
  licenses compact-scale tokens, keeps passing.
- Header chips: "39 sources" (quiet), "Notes a" (provenance chip, opens the strip and moves focus to the
  note), "Cached".
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
> ▸ Show the 20 source figures behind this · figures carry note a

The disclosure opens a four-column list (Quarter · Figure · Value · Source chip) of the same twenty
citations, in the page, keyboard-operable, scrolling inside its box at 200% text, and the PDF prints the
list in full under the finding. **Only a list of more than three figures folds.** The detector sentences
carry their citations in the operand tail, so a fold would strip every chip and letter from the reading
line; a shorter list stays inline, in display form, with its chips ("Operating margin 41.3%, Q4 2025
[13]; 40.6%, Q1 2026 [15]; 30.9%, Q2 2026 [12]ᵃ"), and a fold's summary names the letters its figures
carry, so a flag resting on a figure that needs review never reads unqualified. The rows of a fold come
from the citations the markers name, never from parsing the operand text (negative amounts and annual
periods would lose their row); Phase 2 ships them as the structured `evidence` list of the completion's `narrative_presentation` (#1225).

### 4.9 Period selector

Shipped in #1203 (presets, From/To selects, the unavailable Quarterly segment). The rules, with the
corrections of §11:

- `SegmentedControl` Annual · Quarterly (the design system's single-choice group, replacing the
  hand-rolled toggle), `size="md"`, full width on phones. A mode without data is an `aria-disabled`
  option that stays focusable and carries its reason ("Quarterly data isn't available for this company"),
  the established unavailable recipe, never native `disabled` (#1203 shipped a native `disabled` option;
  §11).
- Presets as plain actions in the secondary ink with Button sm's shape (not the ghost Button, whose sage
  label D-030 keeps off a count): Last 4 · Last 8 · Last 12 (Last 5 ·
  Last 10 in annual mode), without `aria-pressed` and without a selected tint: the mode control is the
  one single-choice group in this toolbar, and the summary line already states the range (#1203 shipped
  tinted `aria-pressed` pills; §11).
- Two compact selects, From and To, named by their visible labels, in the data face through the raw
  `<select>` with `inputClasses({ select: true, density: 'compact', autoWidth: true })` (the `Select`
  component renders full width and keeps the font off the element), listing every available period with
  its availability marks (a `†` for a calculated Q4; an unavailable option for an annual period without
  core data). From moves only the start, To only the end; a choice that would exceed the 12-quarter cap
  moves the other endpoint and says so in a `role="status"` line: "To moved to Q2 2014 to keep 12
  quarters". Nothing is clamped silently.
- One summary line: "Q3 2023 – Q2 2026 · 12 quarters", then "† Fourth quarters are calculated from
  annual totals. Fiscal quarters. Data from Q2 2011; up to 12 quarters at a time.", then Run analysis.
  (The Run button keeps native `disabled` while running: `analysis-api.spec.ts` pins it, a rule-6
  contract; #1203's one-line change to that spec was the pre-approved contract change for the chips.)
- The 61-chip grid is retired. On phones the selects are full width and 44 px tall; from 640 px up they
  are 36 px toolbar fields beside the segmented control.

### 4.10 One vocabulary across exports

| Surface | Affected value | Comparison built on it | Unavailable value | Summary | Full precision |
|---|---|---|---|---|---|
| Web | `26.1%†ᵃ` | `−9.7ppᵃ` | `—ᵇ` | Data notes strip (counts + grouped notes) | evidence dialog, Sources list |
| PDF | the same letters as `<sup>` footnote marks in the grid and after narrative citations (never the U+1D43 modifier letter, which the bundled fonts may lack) | on the appendix YoY/QoQ rows, the only place the PDF prints comparisons | `—ᵇ` | "Data notes" list in the same order under the grid, replacing "[note n]" / "[unreconciled]" | Sources & methods appendix (unchanged, with a Note column appended as column 17; columns 1–16 are positional and pinned) |
| Excel | the letter in the cell's number format (`#,##0" (a)"`), so the cell stays numeric, sorts and prints; the sentence in the cell comment | the same on the growth cells the workbook has (window and top-line YoY) | empty cell with the comment | "Data notes" block on the cover sheet with the same counts | Sources & methods sheet (unchanged, with the Note column) |
| PNG | hollow marker / filled bar + letter | letter on the growth line | gap | "Note a: …" lines under the plot | not applicable |

**Superseded (2026-10-25)** for the Web and PNG rows: the founder narrowed the marking rule on 2026-10-25 (`docs/brand/decisions-log.md` D-061). On the page a
figure reads `26.1%` (no dagger) and carries `ᵃ` only where its note questions the number, a gap is `—`
alone, and the summary is the fine print under the table; a chart's PNG prints its card's footnote lines, which
name the marked letters and state a gap in words (§4.7, E195). The PDF and Excel rows move with the exports' own change. §9's decisions stand.

Period headers in Excel read "Q2 2026" (the straight form; a typed filter cannot match a typographic
apostrophe) and the data columns keep the period keys the API uses. The PDF's compact money formatter
matches the web's ("$1.2T", "$1.0B"; today's prints "$1.23T" and "$1000.0M"). The backend owns the
grouping and the sentences so the four cannot disagree (Phase 2); the exports read the same stored list
(`resolve_data_notes`, which regroups only when a saved snapshot lacks it; #1225).

## 5. Keyboard, screen reader and touch

- Reading order: picker → headline cards (each a definition group: term, value button, period and
  delta) → Data notes (a disclosure; open, a list of notes) → chart panels (heading, legend, Notes chip,
  controls, the plot as a named scrollable region while it overflows, its arrow keys scrolling it, then its values
  stop, a slider whose arrow keys step the periods) → narrative
  (headings, paragraphs with citation chips, evidence disclosures, Sources list) → table window control
  → table region → cells.
- Table: the scroll container is `role="region"` named "Metrics by period, table of 12 quarters", a Tab
  stop (`tabIndex=0`) only while it overflows; with focus, Left/Right scroll by the snap unit (one
  column), Home/End to the ends, handled only when the region itself is the event target (keys from a
  cell's portalled dialog bubble through the React tree and must not scroll the hidden table). The table
  has a caption that states the basis of the change line and the fiscal basis of the periods. Row
  headers are `<th scope="row">`, column headers `<th scope="col">` with an sr-only long form ("Q4
  2023, calculated"). Each value is a button named in display form as in §4.2; a cell's change line
  carries an sr-only "change vs prior quarter" (or "vs same quarter last year" for the labelled
  fallback); the comparison's note letter is `aria-hidden` because the name already states it. No cell
  text is clipped or truncated on either side of its box.
- Announcements: the strip's summary is plain text; opening a note is a disclosure, not a live region;
  the "Showing 6 of 12 quarters" line and the picker's clamp line are persistent `role="status"`
  regions. The evidence dialog is `aria-modal`, labelled by its title; the status line reads "Needs
  review · note a" before the reason; Escape returns focus to the figure. Chips that open a note move
  focus to the note's list item (`tabIndex=-1`, visible ring) without forced smooth scrolling.
- Touch: `SegmentedControl` `size="adaptive"` is 36 px below the `sm` breakpoint and 26 px from it;
  the mode and window controls use `size="md"` (36 px) and full width on phones; the range selects are
  44 px on phones. Figure buttons are not inline text: they meet WCAG 2.5.8 by size (the KPI buttons) or
  by the spacing exception (table rows about 41 px apart, columns at least 68 px); repeated "Open filing
  ↗" links carry distinct names. The table scrolls by swipe and snaps to columns; the chart plot scrolls
  by swipe inside its region, never the page.
- Colour: letters carry the meaning; tones carry direction, as today. Since D-061 no figure carries a `†`
  and no letter takes warning ink: a figure's letter is the note ink, and a chart's, in its notes band, the
  chart's note ink (§4.7). Warning ink (6.4:1 on cream, 5.2:1 inside its tint; amber-500 on navy in dark)
  stays for the evidence dialog's "Needs review" on a note that questions the number. The muted letter pair
  is 5.2:1 / 5.8:1 on panel.
- Gates: the analysis route joins `tests/e2e/text-floors.spec.ts` in both themes; the layout gate (#1206,
  `tests/e2e/analysis-layout.spec.ts`) asserts the region's role, name and Tab stop, the header counts and
  every figure control's name; still owed there, as follow-ups: the conditional Tab stop, a focused cell
  whole in view (clear of the sticky column and inside the far edge) at 390 and 1024, Home/End changing `scrollLeft` and never `scrollY`,
  the window control keeping focus and updating its status, the Notes chip moving focus to
  `#analysis-data-note-a`, and the dialog's name and focus return.

## 6. Before and after

| Measure (state 2) | Current build (`97293e7`) | Prototype |
|---|---|---|
| Repeated source-check labels on the page | 33 | 0 (40 one-letter affixes; one strip) |
| Document width at 390 / 320 / 1480 at 200% text | 429 / 413 / 1,558 | 390 / 320 / 1,480 |
| Document width at 390 / 320 with 200% text | 815 / 815 | 390 / 320 |
| Widest card content past a KPI card edge at 390 / 320 / 1480 at 200% text | 54 / 89 / 126 px | 0 / 0 / 0 |
| Widest card content past a KPI card edge at 390 / 320 with 200% text | 303 / 338 px (the figures: 51 / 86 px) | 0 / 0 (one-up) |
| KPI value tops at 390 | 37 / 53 / 53 / 53 | 37 / 37 / 37 / 37 |
| Table width at 1480 | 2,076 (container 1,054) | 1,062 (container 1,062, no scroll) |
| Period column widths at 1480 | 77–105 clean, 234–240 warned | 77 all |
| Table at 1024 / 768 / 390 | 2,076 at every width | 1,044 / 1,044 / 920; Newest 6 fits ≥ 768 |
| Cell text outside its content box (both sides) | not measured | 0 at every width, 200% text included |
| A column straddling the sticky edge at rest | no snapping, so at any position between two column boundaries; at the boundaries, the far-right end at every width but 320 with 200% text | 0: the table snaps to column boundaries and its range is a whole number of columns, at every width |
| Count the reader sees | "24 source checks needed" (26 in production) | "10 figures need review (a) · 24 comparisons carry note a · 10 unavailable (b)" |
| Evidence for a legacy margin | "26.06536077 pure", no inputs | "26.1% · As stored: 26.0653607671% · Needs review · note a · lineage not recorded" |
| Red flags, FCF finding | 1 sentence + 20 inline operands | 1 sentence + "Show the 20 source figures behind this · figures carry note a" |

Screenshots for every configuration are regenerated by the harnesses (`--shots`); they are not
committed.

## 7. Implementation brief

**Status (2026-10-10, evening).** Phase 1 items 1–2 and 11 are on `main` (#1199: `lib/dataNotes.ts`,
`DataNoteMark`, `DataNotesContext`, `DataNotesLink`, the presentation allowlist gate
`tests/unit/analysisDataNotePresentation.spec.ts`, the `DESIGN.md` / `DESIGN_SYSTEM.md` entries and
`lessons/frontend-variable-text-must-not-size-a-wrapping-row.md`); items 3–4 are on `main` (#1200:
`KpiStrip` as a definition list with subgrid rows and "latest available", `DataNotes.tsx` in place of
the sources card, `formatAnalysisPeriod` in `lib/periodLabels.ts`); item 5 is on `main` (#1202:
`DataTable`'s opt-in `layout`, `colWidths`, `cellPadding`, `scrollRegion`, `snapColumns` and
`Column.rowHeader`, `MetricsTable`'s equal rem columns, table-only window, keyboard scroll region,
bounded token formatting in `lib/tableFormat.ts`, with `tests/unit/data-table-scroll.spec.tsx` and
`analysis-table-format.spec.ts`); items 6–9 are on `main` (#1203: `SourceValue` with display figure,
stored value, bound arithmetic, checks and the comparison block; `lib/narrativeDisplay.ts` and
`lib/figureDisplay.ts` with the evidence fold; chart notes with `lib/chartNoteLayout.ts` and PNG
notes; `PeriodPicker` with presets and From/To selects; the one-line `analysis-api.spec.ts` change as
the pre-approved rule-6 contract change, each item except the parts that wait on decisions 7–9, named
under items 6, 8 and 9, and item 7's three-figure rule and summary letters, open under item 7); item 10 and
the dark sticky-hover fix are on `main` (#1206:
`tests/e2e/analysis-layout.spec.ts` with its fixtures, the `ci.yml` flag, the `DataTable` hover fill; the
status note under item 10 says what that gate still owes); Phase 2 landed in #1225 (the status note under
its heading says where it departs from the brief). Open: the follow-ups the comprehensive review
lists in `tasks/analysis-redesign-2026-10/review-2026-10-10.md`, Phase 2's open parts among them. Each
landed PR recorded its own gate tail and browser measurements in its body.

Risk tier per `AGENTS.md` §5: Phase 1 is frontend-only (routine); Phase 2 touches
`trend_analysis/*`, `trend_analysis_service.py`, the export services and `fact_provenance.py`
consumers (routine), never the facts service (`facts_service.py`, a facade since #1210, and the `facts/`
package behind it), prompts or evals. The quarterly data repair is a separate
operational action and is not part of this brief.

### Phase 1 — frontend, no backend change, works on today's payload (one PR per item or two PRs)

1. **`features/analysis/lib/dataNotes.ts`** (S): `groupDataNotes(dataset)` per §4.1, `noteFor(point)`,
   `noteForComparison(point, basis)`. Unit test with a synthetic dataset covering review, unavailable,
   mixed and clean cases, and a pinned count test against a trimmed Meta fixture. Keep `provenance.ts`'s
   `REASONS` as the one copy source; rewrite sentences there.
2. **`DataNoteMark.tsx`** (S) replaces `ReconciliationBadge.tsx` at every analysis site (`KpiStrip`,
   `MetricsTable`, `TrendCharts`, `NarrativePane` and its citation list; `SourceValue` does not use
   it). `ReconciliationBadge` stays for its fundamentals and peers consumers (#1199 moved it to
   `features/fundamentals/components/SourceCheckBadge.tsx` for them)
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
6. **`SourceValue.tsx`** (M; partly landed in #1203: the display form, the stored value, the bound
   operands, the comparison block and the lineage copy; the status vocabulary of decision 9, "Unavailable"
   for "Withheld", authorized by the 2026-10-11 decision): display form, the stored value, the formula with
   its operands bound by concept, the status vocabulary, the comparison block, the lineage block with the
   absent-lineage copy; never a storage unit (§4.6). Leftovers on `main`: `review-2026-10-10.md` items 1
   and 13, item 28's "As stored" label, and the authorized vocabulary follow-up (item 16 and the rest of 28 are satisfied
   there).
7. **`NarrativePane.tsx`** (M; partly landed in #1203: the render-time compaction, the evidence fold, the
   header chips and the Sources lines; `main` folds every operand list and its summary names only the count,
   so the three-figure rule and the letters on the fold's summary are open): compact amounts and periods at render time until Phase 2
   renders them server-side, under the relation-safe rule of §4.8; the evidence disclosure for lists of
   more than three figures, shorter lists inline, letters on the fold's summary, rows from the citations
   the markers name; header chips; Sources list lines. Update `narrative-pane.spec.tsx`. Leftovers on
   `main`: `review-2026-10-10.md` items 2 and 11.
8. **`TrendCharts.tsx`** (S; partly landed in #1203: the hollow markers with their letters, the chip and
   the PNG notes; filled affected bars are authorized by decision 7 (2026-10-11), and `main` still draws a
   dashed outline): `dot` render for hollow markers with the letter above,
   affected bars keeping their fill with the letter above (never a dashed outline: §4.7, decision 7),
   letters in the chart label ink as SVG attributes from the chart theme, "Notes a" chip, PNG note
   sentences from `groupDataNotes`. Leftovers on `main`: `review-2026-10-10.md` items 25 and 29 (29 is
   the filled affected bar, authorized under decision 7; item 22's label ink is satisfied there). Update
   `trend-charts-annotation.spec.tsx`, `trend-charts-legend.spec.tsx` (it owns the warning and PNG
   metadata assertions) and `chart-export.spec.ts`.
9. **`PeriodPicker.tsx`** (M; partly landed in #1203 as a rule-6 contract change: the `SegmentedControl`,
   the From/To selects and the summary line; plain preset buttons are authorized by decision 8 (2026-10-11),
   and `main` still renders an `aria-pressed` group): `SegmentedControl`, presets as
   plain buttons, From/To selects with the announced clamp, summary line (§4.9); `chipsFor`/`nextRange`
   become option builders. Update `period-picker-helpers.spec.ts`. Leftovers on `main`:
   `review-2026-10-10.md` item 19, which carries the authorized preset follow-up.
   `SegmentedControl` has no unavailable-option API today and the picker disables Quarterly when a
   company has no quarterly coverage: add an `aria-disabled` option (early return in the handler, the
   DS unavailable recipe, never native `disabled`) so that state survives the migration. Note the Run
   button keeps native `disabled` until the rule-6 item in `tasks/todo.md` is resolved.
10. **Gate** (M, high tier because it edits `ci.yml`): `tests/e2e/analysis-layout.spec.ts` with
    `tests/e2e/fixtures/analysisApi.ts` in the shape of `filing3Api.ts`; nothing is read from `tasks/`.
    *Landed in #1206* as `tests/e2e/analysis-layout.spec.ts` with `tests/e2e/fixtures/analysis-layout.json`
    and `analysisLayoutApi.ts`: 42 cases (the three prototype states × light and dark × 320, 390, 768, 1024
    and 1480, 200% text at 1480, 2x zoom emulation at 740); text-range overflow against the configured
    viewport and the layout viewport, card spills and value tops, clipped glyph ranges in every cell, equal
    period widths, the exact note letter and kind of every cell, a region with role, name and Tab stop,
    the far-right endpoint (reachable, nothing partly under the sticky column, the last period readable),
    the window control's "Showing N of 12 quarters" with the KPIs, notes and charts unchanged and no second
    dataset or stream request, and the painted background of the hovered sticky cell; `ci.yml` sets the
    flag for the e2e build and start; the committed mutation proof was a repeated nowrap label in the KPI
    component. Its fixture is the prototype data under `tasks/analysis-redesign-2026-10/prototype/data` in
    its three states, hash-pinned to `22ead2f` and declared simulated by its own header, not the production
    capture. Still owed in that spec, as follow-ups: 390 at 200% text (after the founder's decision 4
    amendment), every scroll rest position rather than the far-right endpoint, Home/End on `scrollLeft`,
    the focus assertions of §5, the capture-based fixture cases below and the table `text-nowrap`
    mutation; the region's Tab stop is asserted unconditionally, so making it conditional (§4.5) changes
    that assertion. The specification below stays the reference for those.
    - *CI*: the e2e build and start steps set `NEXT_PUBLIC_ENABLE_ANALYSIS: 'true'` (today they set only
      the API URL and `WAITLIST_MODE`, and `app/analysis/layout.tsx` answers 404 without the flag); the
      flag also shows the analysis links in the Header, Footer, ProDepth and the watchlist, so the whole
      suite re-runs. The spec fails on a 404; it never skips.
    - *Routes* on the house `API_ORIGIN` (`new URL(process.env.NEXT_PUBLIC_API_BASE_URL ||
      'http://localhost:8000').origin`), answered in the browser: `/api/auth/me`,
      `/api/subscriptions/{subscription,usage}` (the `analysis_used` / `analysis_limit` field names),
      `/api/companies/META`, `/api/analysis/META/coverage`; `POST /api/analysis/META/dataset` asserting
      the body `{mode:'quarterly', start_period:'2023Q3', end_period:'2026Q2'}`; `POST
      /api/analysis/META/stream` as SSE (`progress` then `complete` with the dataset's `snapshot_id`);
      every other path 404, recorded and asserted empty; non-localhost hosts aborted; a page error fails.
    - *Fixtures*: `tests/unit/fixtures/meta-data-notes.json` (the captured production dataset, sha-pinned)
      plus a small map adding `unit`, `tone` and the period fields per metric, as the captured, clean and
      discrepancy states; one YoY-fallback cell with a note letter, one `n/m`, one "latest available"
      card, a `source_check_needed` figure, a mixed reason set in both operand orders, a value without a
      validation record, a legacy `reconciled: false`, and (annual) `cagr` / `window_pp` comparisons.
    - *Setup*: `reducedMotion: 'reduce'`, the house `cookie_consent` value, light theme (light and dark
      measure identically); go to `/analysis?ticker=META`, choose Quarterly, Run; ready when 4 cards,
      20 table rows and the Sources eyebrow exist; then `document.fonts.ready`, `settled()` and an empty
      `document.getAnimations()`; no fixed sleeps, no `networkidle`; 200% text through an injected
      `:root{font-size:200%}` before Run.
    - *Matrix* (about nine page loads): the captured state at 320 and 390 (mobile), 768, 1024, 1480, 1480
      and 390 at 200% text; clean and discrepancy at 390.
    - *Assertions* (soft, 0.5 px): (a) `document.documentElement.scrollWidth` ≤ the configured viewport
      width (never `window.innerWidth`) and nothing in `main` past it; (b) exactly 4 KPI cards, every
      element rect and text-node rect inside its card, text blocks `scroll ≤ client + 1`, no
      `text-overflow` or line clamp (`.sr-only` and svg excluded); (c) label, value and third-row tops
      equal across a row, 2 columns below 1024 and 4 from it; (d) one Data notes strip between the cards
      and the charts with the shipped summary wording per state; (e) the table region by role and name,
      12 period headers of equal width (0.5 px) and at least 4.75 rem (4.25 rem below 768), every cell's
      text inside its content box on both sides, value lines aligned across each row; (f) for every rest
      position (k·w and k·w + 0.4·w, polled until settled) the offset is a multiple of w or the maximum,
      the maximum itself a multiple of w, and no period header straddles the sticky edge; End, Home and
      the arrow keys land on the same grid; scroll area minus sticky column ≥ w while the column sticks;
      phones start at the far right; (g) "Newest 6" shows "Showing 6 of 12 quarters" and 6 headers with
      no scroll from 768 up, "All 12" restores; (h) the keyboard and screen-reader assertions of §5; (i)
      the sticky cell stays opaque on dark hover. Grid tracks that hold a scrolling plot or table are
      `minmax(0, 1fr)` with `min-width: 0` on the item (`lessons/frontend-variable-text-must-not-size-a-wrapping-row.md`).
    - *Mutation proof*, committed: `text-nowrap` on the KPI `dt` (vitest stays green because the
      presentation gate matches `whitespace-nowrap` only; assertion (b) fails at 320 and at 390 with 200%
      text). Scratch proofs cited in the PR: the pad removed (f, at 1024: range 110 px, 76 px columns), one
      column at 5 rem (e), `min-w-0` dropped from a card (a), the "Showing" line removed (g).
    - *Ownership*: the presentation spec keeps `Badge`, nowrap and the 11 px floor (and grows to
      `text-nowrap` and `truncate`); `data-notes.spec.ts` keeps the grouping counts; this spec covers
      rendered geometry and interaction only. Assert invariants, never recorded pixel values; the
      numbers in this document are one environment's run (Chromium 141 on Linux with Inter and Geist Mono
      loaded, the browser the harnesses pin).
11. **Docs** (records, same PR as item 2): `DESIGN.md` Calculation Provenance Rule ("Amber 'Source check
    needed'" → the lettered note, "Unavailable" → "— with its note letter; 'Unavailable' in the evidence
    view and exports"), `frontend/DESIGN_SYSTEM.md` §4 (a "Data note mark" entry; the table scroll-range
    rule) and `frontend/DESIGN_SYSTEM.md` §10 (chart marks, PNG notes), sidecar through the
    `design-docs-maintenance` skill.

### Phase 2 — backend, one verified deploy

*Landed in #1225* on 2026-10-11, after the founder accepted the live Phase 1 report, in one PR reviewed at the
high tier for its approved contract change (two key-set anchors in `test_trend_refactor_anchors.py` admit
`narrative_presentation`). Where it departs from the items below, each is a branch the brief allowed or a
safer one. Item 1: the list **is stored** on the dataset (`dataset.py` writes `data_notes`; the fingerprint
excludes `data_notes` and `narrative_presentation`, the shipped-list branch), built by the new
`trend_analysis/data_notes.py` (re-exported by `dataset_quality.py`; `resolve_data_notes` returns the saved
envelope, errors on a present but malformed one and regroups only when the field is absent;
`citation_data_notes` appends citation-only notes after the report letters) and admitted on the web at the
API boundary (`lib/dataNotesContract.ts` rejects malformed or mismatched metadata; `resolveDataNotes` falls
back to `groupDataNotes` only when the field is absent; `issueFor` is the exported `dataNoteIssue`), with the
shared fixture `backend/tests/fixtures/analysis_data_notes.json` exercised by `test_analysis_data_notes.py`
and `data-notes.spec.ts`. Item 2: the one table is `data_notes.py`'s `REASONS`, shipped as
`data_notes[].message` and read by the exports (`analysis_export_metadata.py`'s table and its "needs
rebuilding" are gone; workbook comments open "Data note a: …"; "(marked Computed)" is gone from
`NarrativePane.tsx`); open: `provenance.ts` keeps its own table and "Source check needed" without a parity
test, and the `/source check|\bverif/i` spec does not exist. Item 3: `<sup class="data-note">` letters and a
Data notes section in the PDF, the summary and note comments in the workbook, "Q2 2026" period labels
(`period_label`, display only) and separate counts of unknown figures and unknown comparisons; its other
details are in #1225's body. Item 4: the selected observations are rendered **after** selection
(`trend_analysis/presentation.py`, through `render_observation_selection`'s `render_item`), leaving the
catalogue and prompt bytes unchanged, so `PROMPT_VERSION` is untouched and the observation-selector gate did
not apply; a `NARRATIVE_FORMAT_VERSION` travels inside the saved dataset JSON (`narrative_presentation`:
structured operands, UTF-16 spans, the combined notes, the snapshot id), no column and no migration;
`presentation_is_current` gates the cache re-serve (an older presentation regenerates on the
system-invalidated path) and the exports (409, "This analysis uses an older presentation format. Re-run it
before exporting."); the inline operand sentence stays in the stored Markdown for the PDF and already-open
tabs, and the web replaces its exact spans with evidence disclosures.

1. **`trend_analysis/dataset_quality.py`** (M): `data_notes(dataset)` as a line-for-line port of
   `frontend/features/analysis/lib/dataNotes.ts` (the shipped rule, not the §4.1 prose and not the
   prototype's `buildNotes`): `issueFor`'s kinds (`dataNoteIssue` since #1225) (a populated value whose validation is neither passed nor
   needs_review is "unknown", keyed by its supplied reasons, so several unknown notes are possible),
   unavailability notes keyed by the reason set, letters continuing "aa" after "z", periods missing from a
   series as `not_in_dataset`, a comparison without provenance a review item only when `*_reconciled ===
   false` and otherwise unknown (excluded from the review comparison count), annual `yoy + cagr +
   window_pp` counts, `groupQualityNotes` continuing the lettering for citation-only notes; keys must be
   byte-identical to the frontend's (`json.dumps(..., separators=(',', ':'))`; `{}` is truthy in JS; `0`
   and `"nm"` are real comparisons, test `is None`). The list is **not stored on the dataset**: the
   snapshot fingerprint is recomputed in three places from everything but `snapshot_id` and
   `data_as_of`, so a stored list would change `snapshot_id`, invalidate every cached narrative and make
   the exports answer 409. The exports call `data_notes(dataset)` on the dataset they render; if the API
   ships the list, add `data_notes` to the fingerprint's exclusion set and extend
   `test_quarterly_trust_dataset.py`. Citation-only notes need the completion's citations: computed
   client-side on the web and from `citations_json` for the PDF. The frontend keeps its grouping for
   deploy skew and for the checked-in samples (`AnalysisTeaser`, `AnalysisDemo`), not for old snapshots.
   A shared JSON fixture pins both implementations to identical key, id, letter, message and counts.
2. **One copy source** (S): the reason sentences live in one backend table that the API ships as
   `data_notes[].message` and the exports read; `provenance.ts`'s `REASONS` stays as the fallback with a
   parity test (today three tables disagree: `provenance.ts`, the prototype, and
   `analysis_export_metadata.py`, whose `legacy_calculation` promises "needs rebuilding"; the backend
   lacks `legacy_calculation_not_supported`, `not_in_dataset`, `legacy_unknown` and `source_conflict`).
   `legacy_calculation`: "This saved calculation predates the current source checks. Its inputs need
   review." `source_check_needed`: "This figure has not passed EarningsNerd's automated consistency
   checks; check it against the filing before relying on it." `legacy_unknown`: "No automated check
   result is recorded for this figure." A spec fails on `/source check|\bverif/i` in `features/analysis`
   copy; "calculated" and † everywhere ("derived Q4", "(marked Computed)" retire).
3. **Exports** (M): §4.10; the PDF grid holds values only, so comparison letters go on the appendix
   YoY/QoQ rows; Excel growth comments exist only on the window and top-line YoY cells; the Note column
   is column 17 of Sources & methods (columns 1–16 are positional and pinned in `test_excel_export.py`);
   letters as `<sup>` in the PDF; one compact money formatter matching `Intl`. Tests:
   `test_export_service.py`, `test_excel_export.py`, `test_data_completeness.py`'s export pins.
4. **Narrative rendering** (M): compact amounts, "Q2 2026" periods and the relation-safe rule of §4.8
   rendered at catalogue time from the structured fields (`_point_value` display form), keeping the
   dataset bytes stable (the detector sentences carry dated periods that sit inside the fingerprint, so
   rewriting them would change `snapshot_id` and 409 every saved PDF); the red-flag operands as a
   structured `evidence` list derived in `analysis_completion` from the inflection markers plus the
   citations, never persisted, with the inline sentence kept for the PDF. **Bump `PROMPT_VERSION`**
   rather than adding a `NARRATIVE_FORMAT_VERSION`: the model has no column for a second version and a
   new column is a migration (rule 3, high tier). Cached narratives then regenerate lazily, metered as
   system-invalidated (exempt from the user meter, one or two selection calls per re-viewed range, and
   existing PDF exports answer 409 until the analysis is re-run: state both in the PR). The prompt file
   is untouched, but the catalogue text is model input (the model selects observation IDs from lines that
   carry the rendered sentences), so this item is an AI-facing change: the evidence is the RUNBOOK's
   "Multi-Period Analysis observation-selector gate" (offline tests, three companies in both modes, cache
   re-serve identity, `analysis_inference_cost`), not B1, which scores filing summaries and cannot see
   this change; add an offline test that renders the whole catalogue for both modes, negatives, the T
   scale and ratios near 1 and asserts `scan_numeric_fidelity == []`, because the scan otherwise fails
   closed after the paid model call.

### Not in this brief

- Running the quarterly data repair (`docs/quarterly-data-repair.md`); the UI above is designed to look
  right before it (state 2: ten lineage-less calculations) and after it (the engine's own output carries
  lineage for every calculation; the clean state models that, while the captured production fixture
  keeps its own `not_in_dataset` and `legacy_calculation_not_supported` gaps, so "after the repair" is
  not state 1 byte for byte).
- Any frontend override that marks a legacy record validated, hides a note, or shows "verified".
  (Narrowed 2026-10-25, D-061: every note stays in the evidence dialog and the data notes; only a note
  that questions the number keeps a mark beside the figure. Never marking a legacy record validated and
  never saying "verified" stand.)
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
The amendment to decision 4 and decisions 6–9, under "Amended and added by the comprehensive review"
below, were adopted on 2026-10-11 under the founder's open-items-sweep instruction: "I will go with
the Astra agent’s expert recommend for all points above." The recommendation is to adopt all five:
text-relative stacking prevents the measured 200%-text overflow; the glyph budget keeps columns
readable while exact values remain available; filled bars avoid implying estimates; plain presets
avoid a second competing selection state; and neutral status copy avoids promising substantive
verification. Implementation and its measurement gates remain separate from this decision.

1. Letters (a, b, c) as the note mark, or one warning glyph for all notes. Recommended: letters.
2. `scroll-snap-type: x mandatory` (every rest position whole columns) or `proximity` (gentler
   trackpad feel, alignment not guaranteed). Recommended: mandatory with the range rule.
3. The "Q2 2026" / "Q2 ’26" period vocabulary for the analysis surfaces and their exports. Recommended:
   adopt; the filing and company pages keep their own vocabulary.
4. Keep the KPI strip two-up at 320 px (measured fine, "Free cash flow" wraps) or go one-up below 360.
   Recommended: two-up.
5. Whether the table window should also drive the charts. Recommended: no. (Moot from 2026-10-25: the
   table window is retired; see the note under §4.5's window control.)

**Amended and added by the comprehensive review (2026-10-10, evening).** Each is implemented in the
prototype as recommended; the founder may overrule any of them. Historical release checkpoint:
on `main` at `dd7b9ce` (2026-10-11), decision 6 was merged in #1202 and was ratified by the
2026-10-11 sweep; amended 4 and decisions 7, 8 and 9 still awaited implementation. That dated
checkpoint does not describe later implementation branches. Branch updates below record code
available for review, separately from a verified merge and deployment.

**Branch implementation (2026-10-12).** Decision 9 is implemented on this branch in #1264: evidence dialogs say "Unavailable" and
clean reports say "No figures need review", independently of comparison concerns. Merge and
deployment verification remain pending.

**Branch implementation (2026-10-12).** Decision 4 (amended) is implemented on this branch in #1273:
the KPI cards remain two-up at ordinary phone text and become one-up below 17 em of their own
text size. Merge and deployment verification for this geometry change remain pending.

**Branch implementation (2026-10-12).** Decision 7 is implemented on this branch in #1274: affected bars retain their series fill
and carry the note letter above, with SVG/PNG halos. Merge and deployment verification
remain pending.

**Branch implementation (2026-10-12).** Decision 8 is implemented on this branch in #1275: recent-period presets are plain buttons
without a second pressed selection state. Merge and deployment verification remain pending.

4 (amended). Decision 4 was measured at 100% text only. At 200% text a 390 px phone shows 55 px of
   card overflow two-up and 90 px at 320. Recommended and implemented: two-up stays at 320 px and 100%
   text; the cards go one-up when the page is narrower than 17 em of its own text size (§4.4).
6. Table figures are rounded to a glyph budget (#1202: fewer decimals, compact scale or scientific
   notation for a token that would not fit) with the stored value one click away. This is a
   presentation decision the brief did not take; it shipped. Recommended: keep it, with the rounding note
   the table shows and the gate's clipping probe.
7. Affected bars keep their fill with the letter above (§4.7), instead of a dashed outline that reads
   as an estimate. Recommended: filled.
8. Presets are plain buttons, not a second single-choice toggle group beside the mode control (§4.9).
   Recommended: plain buttons.
9. "Withheld" becomes "Unavailable" in the dialog status (§4.6), and the clean report says "No figures
   need review" instead of a sage count of figures that "passed" (§4.1). Recommended: adopt.

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
- **Font-dependent widths** differ between environments, even in one pinned Chromium build. The Track A
  reviewer's run measured the table at 2,044 px (KPI overflow 49.1 / 84.1 / 115.3 px). The founder's review
  of 2026-10-11 measured 2,044 px too, in Chromium 141.0.7390.37 on linux x64 with matching source, fixture,
  font and install hashes; all 20 of its geometry records differed from the recording's, whose table is
  2,076 px. The proposal's numbers are this review's run, and checks assert invariants, not pixels (§7).
- **Fixture vs production.** The fixture is companyfacts-only modelled legacy state (230 / 10 / 14 + 10),
  not the captured production snapshot (236 / 4 / 16 + 10); both remain distinct fixtures (§2.2).
- **Pruned provenance is not the API schema** (§2.2).
- **Ratio precision** keeps the threshold rule (§4.8).
- **YoY fallback in the table** keeps an explicit label (§4.5).
- **Grouping edge cases**: legacy `reconciled: false`, populated values without a validation record,
  annual CAGR / window changes, comparison-only and mixed reason sets (§4.1).
- **`ReconciliationBadge` consumers** outside analysis stay (#1199 moved the badge to
  `features/fundamentals/components/SourceCheckBadge.tsx` for them); `SourceValue` is not a site (§7, item 2).
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

### Corrections from the comprehensive review (2026-10-10, evening)

Six review lenses (design system, accessibility, frontend brief against `main`, backend and exports,
measurement and gate design, product and copy) and seven Codex rounds reviewed PR #1197; every finding
was verified against `main` at `af543b6` before it was accepted. The ranked list, with what each finding
changed and what remains open, is `tasks/analysis-redesign-2026-10/review-2026-10-10.md`. Where each
correction landed in this document:

- **The probes were blind** (element boxes, `scrollWidth` only, one row at the far right, 200% text at
  1480 only): widened in both harnesses and the prototype's `measure`; both recorded runs were
  regenerated (the current build's on the same `97293e7` build, reproducing every earlier number and
  adding the occlusion count, first on a grid of the first period column's width and, since Codex's
  thirty-third round, at the start, every column boundary and the far-right end, with the table's
  `scroll-snap-type` recorded, since that build does not snap; after Codex's seventh round it also runs the phone
  200%-text profiles, where that build overflows the device by 425 / 495 px and its figures run 51 /
  86 px past their cards); §1, §2.3, §4.5, §6 state what is measured now. The widened probes found four clipped
  change-line cells at every width (the YoY fallback) and seventeen at phone widths, 55 / 90 px of card
  overflow and a swallowed scroll area at 200% text on phones: fixed by the two-line fallback, the phone
  cell padding, the one-up rule (§4.4) and the un-sticking rule (§4.5), all measured at 0 afterwards.
- **"Passed" overclaimed** ("matches the company's XBRL as filed" for calculated figures; "compare figures
  with the company's XBRL"): the honest definitions in §4.1 and §4.6; "No figures need review" for a
  clean report.
- **The fold stripped letters and citations** from short Red-flag lists: the more-than-three rule, inline
  short lists and letters on the summary (§4.8); evidence rows from the citations the markers name.
- **Relation-safe compaction** is a new rule, not the engine's (§4.8); money pairs compact together.
- **The dialog bound operands by position** (a margin's inputs are stored as `[revenue, income]`): bound
  by the formula's concepts (§4.6); "As stored" replaces "exact"; units through one display map;
  "Unavailable" replaces "Withheld"; the comparison block and the gap copy added to §4.6; the Modal's
  focus list must include the dialog's summaries (satisfied on `main`: they carry `tabIndex={0}`).
- **Warning ink only for review notes**; the muted pair for no-record and unavailable letters (§4.2);
  chart letters in the chart label ink as SVG attributes (§4.7); filled bars.
- **The strip's locator was wrong** ("in the headline figures and charts" for YoY comparisons that only
  the revenue growth line shows, and only revenue's) and the resting line named no letters (§4.1).
- **Annual mode, the teaser and the landing demo** render the same table and were unspecified (§4.5).
- **Accessibility**: figure names in display form (shipped in #1203); Home/End guarded by the event
  target; regions tabbable only while they overflow; status regions for the window and the clamp;
  comparison letters announced once; recharts' accessibility layer; touch sizes corrected (§5).
- **Item 10 could not run in CI** (`NEXT_PUBLIC_ENABLE_ANALYSIS` unset; high tier); the gate is now
  specified in full (§7, item 10) and the current-build harness finds the shipped markup by data
  attribute and asserts its counts. #1206 then landed the gate with the flag set for the e2e build and
  start; the status note under §7 item 10 says what it still owes.
- **Phase 2**: `data_notes` computed at render time, never stored (the fingerprint); a line-for-line port
  of the shipped `dataNotes.ts`; one copy source; `PROMPT_VERSION` bump rather than a new column; the
  observation-selector gate, not B1; export mechanics and pins (§7, Phase 2; #1225 then took the stored-list
  and format-version branches, recorded in §7's status note and the "Phase 2 landed" bullet below).
- **Fixtures**: the production capture on `main` (`meta-data-notes.json`) keeps its own gaps, so
  "after the repair" is not state 1 (§7, Not in this brief); the gate builds on the capture plus
  synthetic cases, and `prototype/data` stays a visual reference.
- **Picker**: presets as plain buttons; the unavailable segment `aria-disabled`, not native `disabled`;
  raw selects with `autoWidth`; clamps announced; fiscal basis stated (§4.9).
- **Exports**: Excel letters in the number format, straight apostrophes in headers, `<sup>` in the PDF,
  the Note column appended, one compact money formatter (§4.10).
- **Three overstated phrases**: "scrolls 80 px" (152 with the pad), "halves the scroll" (612 to 204 px),
  and §1's silence on the current build's 78 px overflow at 200% text; all corrected.
- **The prototype itself**: letters continue "aa" after "z"; the From/To selects are named by their
  labels; choosing a window keeps focus on the control; the hint and the start-at-newest position apply
  below 640 px only; the Notes chips move focus to the note; the KPI delta no longer reads "year over
  year YoY"; the sections' `aria-labelledby` targets exist; the fixture builder's restoration check is
  real; the revenue panel's growth line draws (its path had opened one move per missing quarter, which
  is invalid path data, so no fixture state had drawn it; the pen now opens once per run of populated
  comparisons); an affected growth point carries its letter above it, with the halo of §4.7; the strip
  letters a comparison-only note in its comparison clause; a note without a validation record keeps the
  reasons its record supplied (keyed by the canonical set, `legacy_unknown` only for an empty one, as
  `lib/dataNotes.ts` does); an open note lists where its comparisons are; the dialog explains the
  displayed change (§4.6 item 5) with its status, the operand that carries the note, its formula and its
  inputs; the open note's locator counts the revenue growth chart, which plots revenue's YoY comparisons
  with their letters; the sticky row header keeps an opaque fill on dark hover (the prototype had carried
  the same translucent wash #1206 removed from `DataTable`; its harness now hovers a row in every proposed
  configuration and fails on a translucent fill); the table's legend carries a clickable Notes chip naming
  every letter its cells and change lines show, in the strip's order (it had shown a hard-coded "a" only
  when a review note existed, so a table whose only notes were unavailable values had no key); a chart
  panel's Notes chip includes the letters of its unavailable values and the unavailable-periods line names
  them, while a gap still draws no marker; each operand's "Open filing ↗" link is named by its concept
  and period; a citation chip scrolls instantly and tints its source row without a transition under
  `prefers-reduced-motion`, as `main`'s `flashAndScrollToSource` does; in the un-stuck mode (200% text
  on a phone) the label column is a snap position of its own: the hover probe found that mandatory
  snapping settled on the first period column, so `scrollLeft = 0` rested at 208 px and the labels could
  never be scrolled back into view (§4.5). The probe aims the pointer at the visible part of the row
  header itself, with the prototype bar not taking the pointer, and proves the hover landed (the row's
  cells change fill) before it judges the header's fill. The picker's presets are plain buttons, without
  `aria-pressed` or a selected tint (§4.9, as decision 8 recommends; the summary line states the range);
  the open note's table clause says how many of its quarter-over-quarter changes are in the quarters
  shown when the table window is narrower than the report (retired with the table window on
  2026-10-25: the clause now counts the whole table; see the note under §4.5's window control), and
  counts the year-over-year changes the table shows as its labelled fallback (§4.1); the evidence
  dialog's status follows the notes model's own resolution, so a stored figure without a provenance
  record whose reconciled flag is false reads "Needs review" with its reason, as its affix and its
  note do, instead of "No validation record". The phone table's "← Earlier quarters" hint hides at
  the scroll start and shows only while the table is scrolled away from it, as §4.5 says (it had
  shown whenever the table overflowed); the disclosure caret and the button fills do not transition
  under `prefers-reduced-motion`. The chart regions are Tab stops only while they overflow their
  panels, measured after paint and on every resize as the table's region is, and their
  names carry the scroll hint only then (§4.7, §5; they had been unconditional Tab stops, four inert ones at
  1480 px). Each "Original filing" link in the narrative's Sources list is named by its source number, figure
  and period ("Original filing for source 3: Revenue, Q2 2026"), so a screen reader's link list tells them
  apart (§5). The prototype harness records the fonts a `--fonts` run serves by content hash and writes the
  committed recording only from the pinned ones (the README gives the fetch and the hash), since the font
  bytes set every measured width. `measure-current.mjs` refuses to write
  `measurements/current.json`, the recording of `97293e7`, for any other served build (a fresh measurement
  needs `--out`, and an `--out` holding a recording of another commit is refused too). The served build is
  the checkout `--build` names (default: the harness's own repository): the harness reads its commit, its
  `frontend/` tree hash, its uncommitted files, its `.next/BUILD_ID` and the build's time, refuses a build
  older than that checkout's last commit touching `frontend/` (it cannot see which tree a build came from),
  verifies before measuring that the server serves that build id, and records them with its own commit and
  uncommitted files, and the fixtures `--data` names by a content hash of their files and, inside the
  repository, by their tree hash with their uncommitted files (a run of another directory had recorded the
  committed fixtures' tree); the baseline is written only for the legacy state from the committed fixtures
  and only from clean trees, so its recorded state, commit and hashes identify the measured code and data,
  and its revision is enforced whether `--out` names that file or it is the default (a missing or malformed
  recording had let an explicit `--out` through); the fixtures' content hash is pinned in the harness, so a
  later committed fixture edit cannot retake the baseline without a new pin; and the baseline needs a build
  that `build-stamped.mjs` stamped with its source tree right after `npm run build` from the clean checkout
  (`frontend/.next/SOURCE_TREE.json`; `.next` is ignored by git, so the build-time check alone could not tell
  which tree a build came from), a stamp the harness validates against the served build id and the
  checkout's `frontend/` tree whenever one is present and records; the build's inputs outside the tree are
  pinned too, since `next build` reads git-ignored env files and the caller's environment (twenty-one
  `NEXT_PUBLIC_*` variables at `97293e7`, the API base URL and the analysis flag among them) and `next/font` downloads fonts
  from Google: `build-stamped.mjs` refuses untracked env files, builds with an allowlisted environment and
  records the public variables and a content hash of `.next/static/media`, which the harness checks against
  the served build and, for the baseline, against the pinned pair of variables and the pinned font hash; the
  stamp also hashes the build's whole output (everything under `.next` but Next's caches, among them the pages
  `next start` caches while it serves), which the harness checks on every run, so a bundle or server file
  edited, added or removed after the stamp is refused rather than measured as `97293e7`; and no unrecorded code
  runs inside the build: `build-stamped.mjs` runs `next build` itself rather than through npm, whose npmrc files
  and `npm_config_*` variables can add Node options to every script it runs, and passes `NODE_OPTIONS` only while
  it holds nothing but heap sizes, which the stamp records (a `--require` or `--import` preload would run in every
  build process); it reinstalls `node_modules` with `npm ci` from the lockfile right before the build, with npm's
  node-options and script-shell settings set back to its defaults, and refuses an install that is not the one the
  lockfile describes (`node_modules` is ignored by git, so an install made for another revision or edited since
  would otherwise build silently); the baseline needs a stamp of the format that guarantees all of this, measured
  on a server the harness starts itself, `next start` through Next's own CLI in the same controlled environment,
  which the recording describes, and the build's output and its `node_modules` must still hash as the stamp recorded
  them before the run and again after it, or nothing is written; `97293e7` has no harness, so the baseline
  is retaken by this tree's harness with `--build` pointing at a worktree of that revision, built there with
  `build-stamped.mjs`. The harness compares its output and data paths as canonical paths, so a symbolic link
  to the baseline, a path through a linked directory, or a hard link on the baseline's inode (compared by device
  and inode, which `realpath` does not collapse) is the baseline and meets every baseline guard, while a
  dangling link and any other output with more than one hard link are refused rather than written through.
  Both harnesses write their recording only in the browser `harness/browser-pin.mjs` pins, Chromium
  141.0.7390.37 on linux x64 (Playwright 1.56.1's build), checked right after launch, since the browser sets
  every width as the fonts do: measured in Chromium 153, the frontend's own Playwright's, the same `97293e7`
  build differs in all 20 configurations (the table 2,035 px wide instead of 2,076, 4,070 instead of 4,151 with
  200% text, and no header straddling the sticky edge at 1480). The pin is necessary, not sufficient: in the
  same Chromium build another machine measured that table at 2,044 px (the "Font-dependent widths" entry
  above), so acceptance checks assert invariants (§7) and a run elsewhere writes with `--out`.
- **Moved modules**, checked against `main` at `dd7b9ce` (#1222) on 2026-10-11: `normalize_companyfacts`
  lives in `facts/companyfacts.py` (#1210) behind the `facts_service.py` facade; `build_observation_catalogue`
  and `_point_value` in `trend_analysis/observations.py`, `_ratio_threshold_value` and
  `_ordered_percentage_values` in `trend_analysis/formatting.py`, `analysis_completion` in
  `trend_analysis/stream_events.py` (#1204, #1205, #1209), all re-exported by `trend_analysis_service.py`;
  `ReconciliationBadge.tsx` became `features/fundamentals/components/SourceCheckBadge.tsx` (#1199). Every
  other path and symbol this document names resolves on that `main`.
- **Phase 2 landed**, checked against `main` at `1268e8e` (#1225) on 2026-10-11: the status note under §7's
  Phase 2 says what shipped and where it departs from the brief (the stored, fingerprint-excluded list;
  rendering after selection instead of at catalogue time; a format version inside the saved dataset instead
  of a `PROMPT_VERSION` bump), so the briefing prompt's bounded paid-run exception lapsed with the prompt
  bytes unchanged; `issueFor` is the exported `dataNoteIssue`, `groupDataNotes` is the fallback behind
  `resolveDataNotes`, and `analysis_export_metadata.py` lost its reason table. Every other path and symbol
  this document names resolves on that `main`.
