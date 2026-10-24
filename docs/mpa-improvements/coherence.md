# Multi-Period Analysis: notation, data notes and cross-cutting coherence

2026-10-24 · base `a41c6e4` · scope: what †, "a" and "b" mean and how often they fire; one notation
system; the data notes; a heuristic evaluation and competitor teardown; the exports as files; the
order in which this work and the sibling plans (charts, analysis, table) should land.
Evidence lives beside this file: [`verification/`](verification/), [`screens/`](screens/),
[`exports/`](exports/), [`competitors/`](competitors/), [`prototype/`](prototype/) and the
[methods appendix](methods.md).

## 0. The answer first

1. **Fix the data before the design.** In production, "needs review" is on 16.9% of the newest
   annual figures. That is 82 of the 484 latest-year cells across the 27 companies that hold annual
   facts. Twenty-three of those 27 companies (85.2%) show it on a headline figure: revenue, net
   income, free cash flow, or operating or net margin. On the calculated metrics it is the norm:
   net margin 84.6%, free cash flow 78.9%, operating margin 77.8%. Of the 82 flags, 77 (94%)
   have the same cause, `legacy_calculation`: a calculated row written before lineage existed
   (#1191, 2026-10-10). No later write can add lineage to such a row, because ingestion skips an
   identity that already exists and the quarterly repair excludes filing-owned rows. For REGN, all
   11 flagged figures reproduce exactly from their reported inputs. A journaled lineage backfill
   (§1.5) would clear them without changing a single value. No presentation work can do that.
2. **The checks miss a real error that the flags cannot show.** REGN's FY2018 and FY2019 revenue
   come from the FY2020 10-K's re-tagged comparatives: $5,145.6M and $6,557.6M. The years' own
   10-Ks reported $6,710.8M and $7,863.4M. The page therefore shows FY2018 revenue growth of
   −12.4%, where the original filings give +14.3%, and an operating margin of 49.3% that is about
   37.8% on the original revenue. Both pass every automated check (§1.6). The trust signal is
   inverted: "a" sits on 11 correct figures while a materially restated one reads clean.
3. **The marks need one system, not a resize.** Today the dagger takes the size of whatever figure
   it follows, 24px on a KPI card. A letter's meaning changes from company to company: "a" is
   "needs review" on REGN, but "unavailable" on a company with no review notes. And "needs review"
   uses the same footnote form as "not in our data". §2 defines one flag component:
   - every flag is set at the 11px data-xs size;
   - a review letter is ringed, so it never depends on colour alone;
   - a gap letter is plain;
   - the dagger is fixed and quiet;
   - one key travels with every surface that shows a mark.
4. **Data notes should answer "how far can I trust this, and where are the weak figures?" in one
   line** (§3). Readers were tested on the current page and on three prototype rounds, each read
   by a fresh model instance with no context. The current page earned trust in the $4.1B free cash
   flow of 2/5, and the reader had to guess what "a" meant. Rounds 2 and 3 earned 3/5, "plausible
   but unconfirmed", with the meaning stated from the page. That is the calibration the data
   supports until the backfill lands.
5. **The page and the exports drift apart.**
   - Independent re-scores of the page: severity sum 50 → 48 → 43 across the current page and two
     prototype rounds; severity-3 problems 7 → 4 → 4 (§4).
   - The exports passed 44 of 70 file checks; 16 were partial and 10 failed (§5).
   - The PDF and workbook print the company in EDGAR capitals and raw ISO timestamps.
   - The PDF's key sits one page away from its table.
   - The workbook hides every review flag in a comment.
   - Neither chart PNG states its period range.
6. **Order (§6):**
   1. The lineage backfill. It shares no code file with any UI plan.
   2. The flag component and its tokens, after #1597.
   3. The data-notes words.
   4. The exports, split so each piece follows the sibling that owns its file and #1601.
   5. Surfaces and the results header, last.
   6. The restatement note, alongside the data-notes words (its own backend change).

## 1. What the notation means, and how often it fires

### 1.1 The exact conditions

| Mark | Fires when | Where the code decides |
|---|---|---|
| † | `provenance.method == "calculated"`. A legacy row without a stored record counts as calculated when its `source` is `derived`, or when it is a formula concept (net/operating/gross margin, free cash flow, working capital, current ratio) whose `raw_tag` is empty or equals the concept. In the table, a quarterly Q4 header dagger means some flow figures in that column were calculated from annual totals less nine months. | [`fact_provenance.py:82`](../../backend/app/services/fact_provenance.py), [`data_notes.py`](../../backend/app/services/trend_analysis/data_notes.py) `_value_notes` |
| review letter (REGN: "a") | `provenance.validation == "needs_review"`. A stored record says so; or a legacy row is calculated (reason `legacy_calculation`); or a legacy reported row has `reconciled` not true (reason `source_check_needed`). A comparison (YoY, QoQ, CAGR, window pp) inherits it when either input needs review. | [`fact_provenance.py:88`](../../backend/app/services/fact_provenance.py), `calculated_provenance` at [`:169`](../../backend/app/services/fact_provenance.py) |
| unknown letter | validation missing or unrecognised: "no validation record". Never counted as passed. | [`data_notes.py:45`](../../backend/app/services/trend_analysis/data_notes.py) |
| unavailable letter (REGN: "b") | no value: no row for that metric and period, or a withheld value (`validation == "unavailable"`, for example a derived quarterly EPS). | [`data_notes.py:45`](../../backend/app/services/trend_analysis/data_notes.py), [`fact_provenance.py:97`](../../backend/app/services/fact_provenance.py) |

**Letters belong to a report, not to a meaning.** Notes are grouped by (kind, sorted reasons). They
are ordered review, then unknown, then unavailable, and lettered a, b, c… in that order
([`data_notes.py:96`](../../backend/app/services/trend_analysis/data_notes.py)). Citation-only
notes get the letters after the report's. So "a" means "the first group in this report". The local
reproduction shows it. A fresh ingest of REGN under current code has no review notes, and its three
missing long-term-debt years take "a". Production's REGN has 11 review figures, which take "a",
and the same missing years become "b". DESIGN_SYSTEM.md already calls the letters "snapshot-local".
A subscriber has no way to know that.

### 1.2 Frequency in production

Method in brief: 17,862 read-only requests to the public peers endpoint, covering the 687
companies in the production sitemap and all 26 annual concepts. This gives each company's newest
`is_latest` annual row per metric, with the same provenance projection the analysis reads. A
second pass read the per-year state of each company's filing-owned rows. Sector comes from SEC's
SIC codes, because production stores none. The scripts are in the [methods appendix](methods.md).
The full tables are [verification/flag-frequency-census.md](verification/flag-frequency-census.md)
and [verification/flag-frequency-by-year.md](verification/flag-frequency-by-year.md).

Only 27 of the 687 sitemap companies hold annual facts at all. The analysis ingests a company on
first use, so the corpus is the companies people have analysed.

| Cut | Cells | Needs review (a) | Share | Of which `legacy_calculation` |
|---|---:|---:|---:|---:|
| All latest-year cells | 484 | 82 | **16.9%** | 77 |
| Net margin | 26 | 22 | 84.6% | 22 |
| Free cash flow | 19 | 15 | 78.9% | 15 |
| Operating margin | 18 | 14 | 77.8% | 14 |
| Gross margin | 8 | 6 | 75.0% | 6 |
| Working capital / current ratio | 17 / 17 | 10 / 10 | 58.8% | 10 / 10 |
| Reported metrics (revenue, net income, assets, cash flows…) | 379 | 5 | 1.3% | 0 (5 × `source_check_needed`) |
| Manufacturing / Pharma & biotech / Services | 66 / 83 / 152 | 18 / 18 / 28 | 27.3% / 21.7% / 18.4% | 18 / 15 / 26 |
| Retail / Transport & utilities / Finance | 42 / 40 / 101 | 5 / 5 / 8 | 11.9% / 12.5% / 7.9% | 5 / 5 / 8 |

- Sector differences follow how many calculated metrics a sector reports. Banks report no gross
  or operating margin, so Finance is lowest. Nothing points to a sector-specific cause.
- **By year**, on filing-owned rows (1,340 cells, 19 companies): 20.5% in FY2022, 21.2% in
  FY2023, 21.2% in FY2024, 21.1% in FY2025 and 17.7% in FY2026. The flag sits in the newest three
  fiscal years, the comparatives of each company's latest 10-K. Those are the years a subscriber
  reads first.
- Of 269 filing-owned calculated cells, 256 are `legacy_calculation`.
- The 13 that pass were written after 2026-10-10. Today's writer attaches lineage
  (`annotate_filing_calculations(..., initialize_reported=True)`,
  [`facts/upsert.py:88`](../../backend/app/services/facts/upsert.py)), so no new legacy rows are
  being made.
- **Companies:** 4 of 27 show no review cell in their latest year; 9 show 1–2, 7 show 3–5 and 7
  show more than 5.

### 1.3 REGN, the whole window

The local reproduction (§1.4) matches production's strip exactly. Across 200 figure slots, 186
passed, 11 need review (a), 3 are unavailable (b) and 50 are calculated (†). Of the 192
comparisons, 16 carry "a": 13 YoY, 1 CAGR and 2 window pp. The flagged figures are all
calculated, and all sit in FY2023–FY2025:
- operating margin, net margin and free cash flow for FY2023–FY2025;
- working capital and current ratio for FY2024.

Production serves them from the FY2025 10-K's filing-owned rows, accession `0000872589-26-000008`.
They are filed with `reconciled = true` and no stored lineage.

### 1.4 How the page and exports were reproduced

The analysis routes need a Pro session, so the page and exports were rebuilt on a local stack at
this commit. REGN was ingested by the app's own coverage route, then the local database was
calibrated to production by removing the lineage record from the 11 cells above. The data-notes
strip then matched production character for character. Details are in the
[methods appendix](methods.md#local-reproduction-of-the-regn-page).

### 1.5 Upstream fix 1: a journaled lineage backfill for filing-owned calculations

**The cause.** These rows are never re-annotated:
- `upsert_facts` skips an identity that already exists
  ([`facts/upsert.py:280`](../../backend/app/services/facts/upsert.py),
  [`:343`](../../backend/app/services/facts/upsert.py));
- the quarterly repair excludes filing-owned rows by design
  ([`quarterly_fact_repair.py:301`](../../backend/app/services/quarterly_fact_repair.py)).

So 256 filing-owned calculations will carry "needs review" until something writes their lineage.

**The change.** A bounded maintenance path in the style of the quarterly repair: a dry-run preview,
a journaled apply through `FinancialFactRevision`, an audited rollback, and Ops operations
`repair-lineage-dry-run` and `repair-lineage-apply` behind the founder's `ops-apply` approval.
1. For each company, select the filing-owned rows whose concept has a formula
   (`METRIC_FORMULAS`), whose `raw_tag` is empty or equals the concept, and whose stored lineage is
   missing or not version 1.
2. Group them with the filing's own rows by `_scope` (company, accession, period end, fiscal year
   and period).
3. Run `annotate_filing_calculations` on each group.
4. Write `provenance` and `reconciled` only. Never write a value, a fiscal label or `is_latest`.

A row whose inputs are found and whose value matches passes. A mismatch keeps the review state
under the specific reason `calculation_mismatch`, and missing inputs under
`missing_calculation_inputs`. These are honest concerns that the notation can then show as real.

**Expected effect.** The dry run decides. The evidence so far:
- All 11 REGN cells reproduce from their reported inputs to 1e-9.
- 77 of production's 82 latest-year review flags have this cause.

**Tier and gates.** High: `facts/**`, `ops.yml` and a script under `backend/scripts/`. A
mutation-proven test that a filing-owned legacy calculation gains lineage and nothing else moves.
The Ops wiring gate (`test_ops_workflow_wiring.py`) and the lock-timeout gate
(`test_migration_lock_safety.py`).

### 1.6 Upstream fix 2: a figure restated by a later filing passes every check

The checks confirm that a reported value matches a filed XBRL fact
(`reconciled`/`validation`). They do not ask whether a later filing's comparative replaced what the
year's own report said. For REGN, `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`
carries two values for each of calendar 2018 and 2019:

| Year | Value in that year's own 10-K | Value in the FY2020 10-K's comparatives | Value the dataset shows (`is_latest`, newest filing wins) |
|---|---:|---:|---:|
| 2018 | $6,710.8M (`0001532176-19-000009`) | $5,145.6M (`0001804220-21-000008`) | $5,145.6M |
| 2019 | $7,863.4M (`0001532176-20-000008`) | $6,557.6M (`0001804220-21-000008`) | $6,557.6M |

The series joins two scopes. FY2017 and FY2020 onward use total revenues; FY2018 and FY2019 use
the smaller re-tagged figure. Displayed FY2018 growth is −12.4% where the filings as reported give
+14.3%. FY2019 growth is +27.4% where they give +17.2%. Every margin in those years is overstated:
FY2018 operating margin shows 49.3% against about 37.8%.

A blind evaluator flagged this from memory (set Z, F6). It was then confirmed against SEC's XBRL
API ([verification](verification/heuristic-rescore-transcripts.md#set-z--prototype-round-2)).

**The change (WP5).** The dataset already reads every row of the company. When a fiscal year's
`is_latest` value differs by more than a set tolerance from the value its own annual filing
reported, which is still stored as a non-latest row of that accession, add a note kind "restated
in a later filing". That note is a fact, not a fault: it shows in neutral ink, names both values
and filings, and the evidence modal shows both. Before choosing the tolerance, count how often it
fires across the 27 companies with the census method.

**Owner.** Data (`trend_analysis/dataset.py`, `dataset_quality.py`, `data_notes.py`), routine
tier. Its letter, word and colour belong to this notation system (§2.2).

### 1.7 The full-population measurement

[`ops/detection/mpa_notation_frequency.sql`](../../ops/detection/mpa_notation_frequency.sql)
computes the same frequencies over every company and fiscal year, in one read-only snapshot.
Set 1 is by dimension: all, concept, fiscal year, SIC division, owner and reason, with the review,
dagger, legacy and inherited-YoY shares. Set 2 is per-company exposure in the newest ten years.

Its classifier was checked against `provenance_for_fact` on a local PostgreSQL. It covered every
branch: stored v1 passed, needs review and unavailable; legacy calculated; legacy derived;
`raw_tag == concept`; derived EPS; an unknown record version; legacy reported, reconciled and not.
The review, withheld and dagger counts and the reason breakdown were identical.

It runs only from main, through the Ops workflow's `detection-sql` operation. Run it after this
lands, and again after the backfill's apply, to confirm the drop.

## 2. The notation as one system

### 2.1 Principles

- **Quiet for the routine, loud for a concern.** Calculation is routine: production calculates
  105 of 484 latest-year figures, and REGN 50 of 200. A concern should be rare once §1.5 lands:
  production's latest year would drop from 82 review cells to at most 5 plus whatever the dry run
  finds. So the dagger recedes, and a concern always carries a word as well as a mark.
- **Shape before colour.** A review letter is ringed; a gap letter is plain. Warning ink adds
  emphasis but is never the only signal (WCAG 1.4.1).
- **One size.** Every flag is set at the data-xs step (11px), raised, and never scaled by the figure
  it follows. A 24px dagger beside "$4.1B" reads as part of the number.
- **One key beside every mark.** No surface shows a mark whose meaning is only in a collapsed
  disclosure.
- **One vocabulary.** The flag words join
  [`evidenceLabels.ts`](../../frontend/features/filings/lib/evidenceLabels.ts), the single home
  the evidence-label lesson and `evidenceVocabulary.spec.ts` enforce. They are:
  - "calculated";
  - "needs a source check";
  - "not in our data";
  - "no check recorded";
  - "restated in a later filing" (WP5).

### 2.2 The flag component

`FigureFlag`, an evolution of `DataNoteMark`, renders at most two flags after a figure: the
calculation flag, then the note flag. The prototype is in
[`prototype/notation-prototype.diff`](prototype/notation-prototype.diff).

| State | Glyph | Size / weight | Light ink | Dark ink | Shape | Placement | Hover text and accessible name |
|---|---|---|---|---|---|---|---|
| Calculated | † | data-xs (0.6875rem), 500, Inter | `text-tertiary-light` #636A77 (5.2:1 on panel) | `text-secondary-dark` #9CA3AF (5.8:1) | none | raised, 0.125rem after the figure (compact: 0.5px in table cells) | "† calculated by EarningsNerd from filed figures" |
| Needs a source check | the report's letter | data-xs, 500 | `warning-light` #92400E (6.8:1) | `warning-dark` #F59E0B (6.8:1) | 1px ring in the same ink, full radius, 1.35em box | after the dagger if any, raised | "Note a: needs a source check" |
| Not in our data / no check recorded | the report's letter | data-xs, 500 | `text-tertiary-light` | `text-secondary-dark` | none | raised; on a missing value it follows "—" | "Note b: not in our data" / "Note c: no check recorded" |
| Restated in a later filing (WP5) | the report's letter | data-xs, 500 | `text-secondary-light` | `text-secondary-dark` | none | raised | "Note d: restated in a later filing" |

Kind decides the shape, so a reader can tell a check from a gap without the key. Letters stay
report-local, as footnotes do in a filing. The key travels with them.

### 2.3 Tokens, in DESIGN.md's frontmatter format

```yaml
typography:
  flag:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: "1"
components:
  figure-flag-calculated:
    textColor: "{colors.text-tertiary-light}"
    typography: "{typography.flag}"
  figure-flag-calculated-dark:
    textColor: "{colors.text-secondary-dark}"
  figure-flag-review:
    textColor: "{colors.warning-light}"
    typography: "{typography.flag}"
    rounded: "{rounded.full}"
    height: "1.35em"
    padding: "0 0.2em"
  figure-flag-review-dark:
    textColor: "{colors.warning-dark}"
  figure-flag-gap:
    textColor: "{colors.text-tertiary-light}"
    typography: "{typography.flag}"
  figure-flag-gap-dark:
    textColor: "{colors.text-secondary-dark}"
  notation-key:
    textColor: "{colors.text-secondary-light}"
    typography: "{typography.flag}"
```

The ring is a 1px border in `currentColor`. The frontmatter has no border key, so it is described
in prose, as the existing components do. Inter carries the dagger; the PDF currently falls back to
DejaVu for it (§5). The change refreshes `DESIGN.md`, `.impeccable/design.json` and
`DESIGN_SYSTEM.md` together and runs `designSnapshotParity.spec.ts`. A mutation-proven gate keeps
the rule in place (CLAUDE.md rule 12): a figure affix in `features/analysis` that sets the dagger
or a note letter outside `FigureFlag` fails `dataXsAllowlist.spec.ts`'s extension.

### 2.4 The key

`NotationKey` lists only the marks its surface shows, each with its word: "† calculated · ⓐ needs a
source check · b not in our data". Each letter links to its note. It sits:
- in the Data notes summary;
- in the metrics table header, replacing the "Notes a, b" chip and the separate "† calculated";
- under each chart's legend, replacing the "Notes a" chip and adding "○ hollow point: figure
  carries a note";
- in the narrative's sources heading;
- on the PDF's table page;
- in the workbook's Metrics header row;
- in the chart PNG footer.

### 2.5 Per-surface rules

| Surface | Rule |
|---|---|
| KPI card | Flags after the figure at flag size. A review note also writes "needs a source check" in warning ink on the period line, because the headline is what most readers see. |
| Metrics table | Compact flags (0.5px gap). One flag pair per value and per comparison. The ring must not raise the row: in the prototype the ring made flagged rows a few pixels taller, so the implementation sets the ring's box inside the row's existing line height. |
| Charts | Hollow point plus the ringed letter (SVG ring = 1px circle stroke) for a review note, a plain letter for a gap. The letter takes the flag ink, not the chart label ink, and keeps its panel-colour halo. The key under the legend explains the hollow point. Amber review ink beside the amber `chart-2` series is separated by the ring, not by hue. |
| Narrative and sources | Citation chip followed by the note flag (as now, ringed). In the source list, the dagger and the words "calculated from recorded inputs" or "calculated, inputs not linked" replace "Calculated figure". Raw precision belongs to the analysis plan (§7). |
| Data notes | §3. |
| PDF | The key under the table on the same page. The dagger and note letters in Inter. The summary words match the page's: "carry note a", not "need review". |
| Excel | A visible flag in the grid without breaking numbers: the number format carries the mark, so `0.0%" †"` and `#,##0" †ⓐ"` keep each cell numeric. Review cells also take warning-ink font. The comment stays for the reason. The key goes on the Metrics header row as well as the Overview. |
| Chart PNG | The period range in the subtitle ("REGN · Margins · FY2016–FY2025"). The key line, including the hollow point. Ringed review letters. |

### 2.6 Reconciling with the sibling reports

No sibling report exists yet. `docs/mpa-improvements/` was absent on every branch on 2026-10-24
at 20:05 UTC and again at 21:10 UTC, across all 42 remote branches. So nothing conflicts today.
For when they land:
- This report owns notation semantics: the states, words, glyphs, sizes, colours, key and
  vocabulary.
- The charts plan owns marker geometry and placement, but consumes `figure-flag-*` and
  `NotationKey`.
- The table plan owns cell layout and density, but uses the compact `FigureFlag` and keeps the key
  in the header.
- The analysis plan owns narrative wording and the source list, but marks figures through
  `FigureFlag`.

A sibling proposal that adds a mark, recolours one or moves the key off its surface is resolved in
favour of §2, unless it brings comprehension-test evidence as strong as §3.4's. Merge order (§6)
puts the component first, so each sibling builds on it rather than beside it.

### 2.7 What the prototype changes and breaks

The prototype ([`prototype/notation-prototype.diff`](prototype/notation-prototype.diff)) applies
cleanly to `a41c6e4`. It touches `DataNoteMark.tsx`, `DataNotes.tsx`, `KpiStrip.tsx` and
`MetricsTable.tsx`. Against the analysis unit specs, 17 tests fail, all in files that pin today's
markup and copy. Those specs are the implementation's to-do list, not regressions to argue away:
- `analysis-source-quality.spec.tsx`: 9, the note letters, the "Notes" chip and the locator copy;
- `narrative-pane.spec.tsx`: 4, the citation mark markup;
- `metrics-table.spec.tsx`: 1, the dagger markup;
- `analysisPeriodWindows.spec.tsx`: 1, the en-dash join, which the prototype's `placesSentence`
  does itself;
- and others.

The `placesSentence` en-dash must move into the period formatter
(`analysisPeriodWindows.spec.tsx` pins that). The prototype is a design instrument; it is not the
code to merge.

## 3. Data notes from the subscriber's side

### 3.1 Cognitive walkthrough (current page)

**Goal:** "I opened REGN. How much can I trust this, and which figures are weak?"

1. **The KPI cards.** "$4.1B†ᵃ" and "31.4%†ᵃ": a 24px dagger glued to the number, a tiny brown
   superscript after it. *Is the number wrong? Is † a footnote or part of the value?* Nothing on
   the card answers.
2. **The strip below:** "Data notes · 11 figures need review (a) · 16 comparisons carry note a · 3
   unavailable (b) · 50 calculated †", in 12px mono, half of it amber. *Need review by whom? Are
   these wrong?* "Comparisons carry note a" is internal language. The routine "50 calculated" has
   the same weight as the concerns. The strip is closed, so "where" is one click away.
3. **The open strip.**
   - Note a reads "This saved calculation predates the current source checks. Its inputs need
     review." It doesn't say whether the figure may be wrong, why it matters, or what to do.
   - Then a list of affected figures, then a mono count line.
   - Then three locator sentences ("13 year-over-year comparisons carry this note. The table shows
     13. Exports carry all 13.") that describe the page's plumbing.
   - The one useful action, "Select a figure to inspect its source", sits at the end, in the
     legend paragraph.
4. **Opening a flagged figure** shows "Source lineage is not recorded for this saved calculation"
   and no inputs, so the reader cannot do the check the note asks for. The backfill (§1.5) fixes
   that; copy cannot.

**Outcome.** The first-round reader put trust at 2/5 and had to guess at "a". They called the note
jargon and found the two superscripts easy to confuse
([transcript](verification/comprehension-transcripts.md#current-design-production-as-of-2026-10-24)).

### 3.2 The design

One summary line answers trust and severity. One line answers where. Details sit beneath.

```
Data notes   Of 200 figures, 186 passed automated checks   ⓐ 11 need a source check   ᵇ 3 not in our data   † 50 calculated   Details
             Ringed letters mark figures to check before relying on them: Operating margin, Net margin and Free cash flow
             (FY2023–FY2025); Working capital and Current ratio (FY2024). 16 growth figures built on them carry the same note.

ⓐ  Inputs not linked. We calculated these figures before 10 October 2026, when we began recording each calculation's
    inputs. This note says the record is incomplete, not that the figure is wrong: it is shown as stored, without links to
    its inputs. Before relying on one, open it and compare it with the filing.
    Operating margin (FY2023, FY2024, FY2025); … · 11 figures · 13 YoY · 1 CAGR · 2 window pp
    ▸ Growth figures that carry this note
ᵇ  Not in our data for these periods. Shown as —, never as zero.  Long-term debt (FY2016, FY2017, FY2018). 3 figures.
```

The screens are [`final-light-datanotes-closed.png`](screens/final-light-datanotes-closed.png),
[`final-light-datanotes-open.png`](screens/final-light-datanotes-open.png),
[`final-dark-datanotes-open.png`](screens/final-dark-datanotes-open.png) and
[`final-light-kpis.png`](screens/final-light-kpis.png); the before states are in the same folder.

- The "where" sentence groups metrics that share a span ("Operating margin, Net margin and Free
  cash flow (FY2023–FY2025)").
- Comparison locators move into a nested disclosure.
- When nothing needs review, the strip says so in one line, as now.
- The copy moves to `data_notes.REASONS` on the backend, so the PDF, workbook and PNG print the
  same words. The prototype maps reasons on the frontend only.

### 3.3 Wording

| Place | Today | Proposed |
|---|---|---|
| Summary, review | "11 figures need review (a)" | "ⓐ 11 need a source check" |
| Summary, comparisons | "16 comparisons carry note a" | "16 growth figures built on them carry the same note" (in the where-line) |
| Summary, total | (absent) | "Of 200 figures, 186 passed automated checks" |
| Summary, gaps | "3 unavailable (b)" | "ᵇ 3 not in our data" |
| `legacy_calculation` | "This saved calculation predates the current source checks. Its inputs need review." | "Inputs not linked. We calculated these figures before 10 October 2026, when we began recording each calculation's inputs. This note says the record is incomplete, not that the figure is wrong: it is shown as stored, without links to its inputs. Before relying on one, open it and compare it with the filing." |
| `source_check_needed` | "A source check remains unresolved. Review the original filing before use." | "Not yet matched to the filing. Our automated check could not confirm these figures against the company's filed data. Open one to compare it with the filing." |
| `not_in_dataset` | "Not available in this dataset." | "Not in our data for these periods. Shown as —, never as zero." |
| Legend | "Letters identify data notes; † marks a calculated figure, not an error." | "A ringed letter marks a figure that needs a source check; a plain letter marks a gap; † marks a figure we calculated, not an error." |
| KPI card | (nothing) | "FY2025 · needs a source check" |

Each sentence promises only what the code enforces. "10 October 2026" is #1191's merge date. "Not
in our data" makes no claim about whether the company reported the figure.

### 3.4 Comprehension test

Each round gave one image to a separate model instance with no context, asking what "a", "b" and
"†" mean, how far it would trust the $4.1B free cash flow, what it would check, and what it would
do. The full transcripts are in
[verification/comprehension-transcripts.md](verification/comprehension-transcripts.md).

| Round | "a" read as | Certainty | "b" | "†" | Trust in FCF | Action for "a" |
|---|---|---|---|---|---|---|
| Current | "computed before the latest checks, not re-verified" | a guess | not available | calculated | 2/5 | open it, compare; resolution unclear |
| 1 | inputs not recorded | a guess | a gap, not zero | calculated | 3/5 | open it, compare with the filing |
| 2 | "incomplete record, not a wrong figure" | stated from the page | a gap, not zero | calculated | 3/5 "plausible but unconfirmed" | open it, compare with the filing |
| 3 | the same | stated from the page | a gap, not zero | calculated | 3/5 | names the formulas to check: OCF − capex, NI ÷ revenue |

### 3.5 What the test leaves open

- The ring and plain distinction still leans on the legend sentence; the round-3 reader found it
  in the fine print. The key in the summary line (§2.4) carries it in the shipping version; the
  prototype placed the key in the table header only.
- "11 need a source check" beside "16 growth figures" reads as two different counts. Name the
  growth figures inline ("13 YoY, 1 CAGR and 2 window changes") instead of in the mono line.
- Flagged growth figures keep their green and red direction ink. Keep it: direction and trust are
  separate axes. But the ringed letter must stay adjacent so the colour is not read as
  confirmation.
- Amber still reads as alarm for a record that is only incomplete. The backfill removes the case;
  until it lands, the words carry the nuance.

## 4. Evaluating the page

### 4.1 Heuristic evaluation (author; current page, both themes, desktop and phone)

Nielsen's ten heuristics; severity 0–4.

| # | Heuristic | Where | Problem | Sev |
|---|---|---|---|---|
| N1 | H1 | Results, both themes | No results heading ties the KPIs, charts and table to "REGN · FY2016–FY2025 · Annual"; after scrolling, the context is gone | 2 |
| N2 | H1 | AI card; data notes | "Cached · served from an earlier run" without the run's date. "Source data as of" sits two disclosures deep | 2 |
| N3 | H2 | Data notes, KPI, table | "Needs review" in amber on figures whose only issue is missing lineage (77 of 82 production flags) reads as "probably wrong" | 3 |
| N4 | H2 | KPI cards | "FY2025 CAGR +12.8%" reads as a one-year figure. The FY2016–FY2025 window is only in a `title` tooltip, which a touch reader never sees | 3 |
| N5 | H2 | Sources list | Raw machine precision ("24.945443390109393%", "0.1277642638015346 (growth fraction)") | 2 |
| N6 | H2 | Table cash-flow rows | Growth on negative bases (−7,527.1%) shown as a percentage | 2 |
| N7 | H4 | KPI cards | The dagger inherits the figure's 24px size ("$4.1B†") and reads as part of the value. The founder's annotation | 3 |
| N8 | H4 | Every mark | A letter's meaning changes by company and run ("a" = review on REGN, "a" = unavailable on a clean company) | 3 |
| N9 | H4 | Page, PDF, workbook | One state, several words: "carry note a" (page) and "need review" (PDF, workbook); "Calculated figure" and "Calculated from recorded inputs"; "Unavailable" and "Not available in this dataset" | 2 |
| N10 | H4 | Charts | Note letters in neutral chart ink, while the table and KPIs use amber. Hollow points unexplained | 2 |
| N11 | H4 | Page against PDF/workbook | "Regeneron Pharmaceuticals, Inc." on the page and PNG; "REGENERON PHARMACEUTICALS, INC." in the PDF and workbook | 2 |
| N12 | H5 | AI "Red flags" | The red flag rests entirely on three flagged margins with no caveat in the prose | 3 |
| N13 | H6 | Every mark | The meanings of †, a and b live only inside the closed Data notes. The "Notes a" chips do not define them | 3 |
| N14 | H8 | Data notes summary | Five counts in 12px mono; the routine "50 calculated" weighs the same as the concerns | 2 |
| N15 | H8 | Data notes, open | Locator sentences describe the page's plumbing ("The table shows 13. Exports carry all 13.") | 2 |
| N16 | H8 | Footer area | Three near-identical disclaimers (AI card, page, site footer) | 1 |
| N17 | H8 | Phone, both themes | The floating Feedback button covers the Revenue KPI's value ("$14.3B" reads "4.3B") | 3 |
| N18 | H9 | Note a | Doesn't say whether the figure may be wrong or what to do | 3 |
| N19 | H10 | Sources [8]–[11], [13] | Calculated figures with no inputs, formula or filing link: the check the page asks for can't be done there | 2 |
| N20 | H4 | Dark theme | Amber letters (#F59E0B) are the brightest marks on the slate panel, so the smallest glyph carries the most visual weight | 1 |

**Totals:** 20 findings, severity sum 46: severity 3 × 8, severity 2 × 10, severity 1 × 2. Both
themes share every finding except N20. In the dark theme, warning ink carries more weight than in
the light theme.

### 4.2 Independent re-scores (blind, one fresh evaluator per set)

| Set | What | Findings | Sev 1 / 2 / 3 / 4 | Severity sum | Most damaging, in its words |
|---|---|---:|---|---:|---|
| X | current page | 24 | 5 / 12 / 7 / 0 | **50** | "The 'a' review flag … is undefined at point of use" |
| Y | prototype round 1 | 27 | 10 / 13 / 4 / 0 | **48** | "The ⓐ … without ever saying what failed or how to verify it" |
| Z | prototype round 2 | 22 | 5 / 13 / 4 / 0 | **43** | "FY2018 revenue $5.1B … carries no flag … inverting the trust signals" (§1.6) |

Each set had a single evaluator, and finding granularity differs between them, so treat the totals
as directional. The steadier signals:
- Severity-3 problems fell from 7 to 4.
- The undefined-mark problem moved off the top spot.
- Z's top problem is a data error no notation can repair.

The severity-3 problems left in Z are four:
- flagged sources with no inputs (§1.5);
- the dual-axis charts (charts plan);
- the unflagged restated revenue (§1.6);
- "never says what failed". Z's desktop tiles show Data notes closed; the summary's where-line now
  answers this.

All four transcripts are in
[verification/heuristic-rescore-transcripts.md](verification/heuristic-rescore-transcripts.md).

### 4.3 Competitor teardown

Three paid products' equivalent views, captured with Playwright for REGN, are in
[`competitors/`](competitors/). Alpha Spread is a supplement: its AI financial profile, before its
bot check closed the door.

| Product (paid tier) | View | Surfaces and elevation | How figure states are marked | Worth taking |
|---|---|---|---|---|
| Roic.ai | Financials: 15 fiscal years, chart over statement ([light](competitors/roic-financials-chart-light.jpg), [dark](competitors/roic-financials-chart-dark.jpg), statement [light](competitors/roic-financials-statement-light.jpg) / [dark](competitors/roic-financials-statement-dark.jpg)) | One flat white surface, one bordered statement panel, hairline rows, no card stack | None: no calculated or quality marks; negatives in red | Colour swatches on table rows tie each row to its chart series; an "As of date" row of period ends under the year header; $ /sh % YoY unit toggles |
| Yahoo Finance (Finance Plus) | Financials › Income Statement ([chart](competitors/yahoo-financials-chart-light.jpg), [statement](competitors/yahoo-financials-statement-light.jpg)); no dark theme signed out | One surface; the table is the page; rows carry checkboxes that add them to the chart | Padlocks mark paid ranges (10Y, 20Y, ALL, Download); no quality marks | Unit control (Auto/K/MM/B), an order toggle, row-to-chart selection, a TTM column |
| Finviz (Elite) | Statements on the quote page ([light](competitors/finviz-statements-light.jpg), [dark](competitors/finviz-statements-dark.jpg)) | Zebra rows on one panel; the upgrade panel covers locked years | A padlock with words for locked years; no quality marks | A per-row sparkline beside each metric; "Period End Date" and "Period Length" rows; Data / YoY / YoY % toggles |
| Alpha Spread (supplement) | AI financial profile ([light](competitors/alphaspread-financial-profile-light.jpg)) | A narrative band above the fold | "Sources:" link at the foot of the AI text, not per figure | Narrative-level sourcing is the floor; EarningsNerd's per-figure citations go further |

What the teardown shows:
1. None of the three marks calculated or checked figures. Per-figure provenance is EarningsNerd's
   difference, and it is a liability only when it is loud for the routine and quiet for the real.
   §2's principle is the remedy.
2. All three present a multi-year statement on one surface. EarningsNerd stacks nine equal cards.
3. All three show period-end dates in the table itself. EarningsNerd shows them only in the
   evidence dialog.
4. Where competitors mark state (a padlock), they pair the glyph with words on the same surface.

### 4.4 The surface, elevation and spacing system the gaps call for

The table plan's surface proposal has not landed (§2.6), so this follows DESIGN.md's Lifted Paper
Rule and its existing tokens, and it leaves the table's interior to that plan.

| Level | Token | Holds | Change from today |
|---|---|---|---|
| Ground | `background` | The page title, the **results header** (new: "Regeneron Pharmaceuticals, Inc. · REGN · Annual FY2016–FY2025 · data as of 24 Oct 2026", then the notation key), the Data notes strip, the disclaimer | The results header is new; Data notes moves up to sit under it, since it governs every module below |
| Control | `panel`, hairline, **no shadow** | The company and period form | Drops from `shadow-e2` to a hairline. An input area is not content, and today it outranks the results |
| Content | `panel`, hairline, `shadow-e2` light / fill + hairline dark | KPI strip, charts, AI analysis, metrics table: one card per module | Unchanged; the chart grid stays one card per chart |
| Overlay | `shadow-e4` / `e5` | Evidence modal, popovers | Unchanged |

**Spacing.**
- 12px (`gap-3`) between the results header and Data notes, and between Data notes and the KPI
  strip. They read as one block.
- 24px (`gap-6`) between content modules on desktop and 16px (`gap-4`) below `sm`.
- Module insets keep `p-cap-6`.
- Flags keep the 0.125rem gap (§2.2).
- The floating Feedback launcher reserves the KPI strip's area on phones by offsetting above it,
  the same way the consent inset works (`bottomChromeLadder.spec.ts` gates the ladder).

## 5. Exports as files

The REGN exports were generated in both themes through the real UI and opened with pdfplumber,
openpyxl and Pillow. The full pass/fail table is in
[verification/export-inspection.md](verification/export-inspection.md) and the files are in
[`exports/`](exports/). Totals: 70 checks, 44 pass, 16 partial, 10 fail.

| Artefact | Misses |
|---|---|
| PDF (identical across themes apart from timestamps: correct, it is a print layout) | Company in EDGAR capitals. Generated/exported/data-as-of printed as raw ISO with microseconds. The †/letter key on p4 while the table is on p3. The summary says "16 comparisons need review", where the page says "carry note a". 52 daggers, 614 bullets and 2 arrows set in a DejaVu fallback font. Legacy calculated sources print raw keys ("operating_margin") and no filing link. Sources & methods runs p4–p45 of 46. No document title metadata; untagged (no structure tree). |
| Excel (identical across themes apart from export timestamps: correct) | Company in EDGAR capitals. Raw ISO timestamps. 14 review cells and 52 calculated cells carry only a comment triangle, so a figure that needs a check looks like any calculated one. The dagger appears only in the Overview count line. No print setup (orientation, fit to width). Title metadata empty, creator "openpyxl". |
| Chart PNG (follows the page theme; background = panel token) | No fiscal-year range in the image, only '16–'25 ticks; the range is in the file name. On the Margins chart, the hollow-ring marker isn't in the key and the note letters are grey, not review ink. No DPI tag: at 6.5in wide it prints at 154 dpi, with axis text about 9pt. |

Theme behaviour is consistent but undocumented. The PDF and workbook are always light; the PNG
follows the page. Keep that, and say so in the export menu ("Image matches your theme").

## 6. Sequencing by measured overlap

Live branches are measured: `git diff --name-only` against each branch's merge base. This plan's
work packages list the files each edits. The sibling scopes list the files each area owns, because
no sibling branch exists yet. The computation is reproducible from the
[methods appendix](methods.md).

| | WP0 | WP1 | WP2 | WP3 | WP4 | WP5 | charts | analysis | table | #1601 | #1597 | section-nav | #1583 | #1600 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **WP0 lineage backfill** (10 files) | — | · | · | · | · | · | · | · | · | · | 1 | 1 | 1 | 1 |
| **WP1 flag + key + tokens** (18) | · | — | 1 | · | 4 | 1 | 3 | 1 | 3 | · | 4 | 2 | · | 1 |
| **WP2 data-notes words** (9) | · | 1 | — | 1 | 1 | 3 | · | · | · | · | · | · | · | · |
| **WP3 exports** (8) | · | · | 1 | — | · | · | 2 | 1 | 1 | 2 | · | · | · | · |
| **WP4 surfaces + results header** (9) | · | 4 | 1 | · | — | · | 1 | · | 1 | · | 2 | 2 | · | · |
| **WP5 restatement note** (7) | · | 1 | 3 | · | · | — | · | · | · | · | · | · | · | · |
| **charts plan (scope)** (7) | · | 3 | · | 2 | 1 | · | — | · | 1 | · | 1 | 1 | · | · |
| **analysis plan (scope)** (7) | · | 1 | · | 1 | · | · | · | — | · | 1 | · | · | · | · |
| **table plan (scope)** (7) | · | 3 | · | 1 | 1 | · | 1 | · | — | · | 1 | 1 | · | · |
| **#1601 export-source** (6) | · | · | · | 2 | · | · | · | 1 | · | — | 1 | · | · | · |
| **#1597 status-line** (17) | 1 | 4 | · | · | 2 | · | 1 | · | 1 | 1 | — | 3 | 1 | 1 |
| **section-nav, no PR** (9) | 1 | 2 | · | · | 2 | · | 1 | · | 1 | · | 3 | — | 1 | 1 |
| **#1583 per-filing currency** (9) | 1 | · | · | · | · | · | · | · | · | · | 1 | 1 | — | 1 |
| **#1600 waitlist-source** (5) | 1 | 1 | · | · | · | · | · | · | · | · | 1 | 1 | 1 | — |

Every shared file by pair is listed under the matrix in
[verification/file-overlap.md](verification/file-overlap.md). Two shared files are worth naming:
- `DESIGN.md` and `DESIGN_SYSTEM.md` (WP1, WP4, #1597, section-nav). The edit sites are disjoint:
  #1597 edits DESIGN.md line 343 and DESIGN_SYSTEM.md 907 and 2191–2203; section-nav edits 482 and
  1210–1241; WP1 edits the frontmatter, line 498, 492–500, 645–660 and 2083–2095. Git merges them,
  but `designSnapshotParity` reads the whole file, so rebase and rerun it after each.
- `export_service.py` (WP3, #1601, analysis). #1601 edits the summary export at lines 87–90 and
  187. WP3 edits the analysis PDF at 306–500. Disjoint, but both edit `test_export_service.py`.

**Order and merge points.** Each step ships something a subscriber can see, and none waits on an
unresolved conflict.

| Step | Lands | After | Visible result |
|---|---|---|---|
| 1 | **WP0** lineage backfill: high tier; the apply needs the founder's approval | #1583's deploy is verified (one unverified backend deploy at a time; its only shared file is `tasks/todo.md`) | Up to 77 of 82 latest-year "needs review" flags disappear in production. REGN's 11 if the dry run matches the local check |
| 2 | **WP1** flag, key and tokens: routine | #1597 merges (it shares the design docs and both e2e floors). The section-nav branch rebases on whichever lands first | Fixed-size dagger, ringed review letters, the key beside every mark |
| 3 | **WP2** data-notes words and **WP5** restatement note, one after the other (they share `data_notes.py` and its test) | WP1 (they use `FigureFlag`) | Plain-words summary and where-line. REGN's FY2018–FY2019 revenue gains a "restated in a later filing" note |
| 4a | **charts plan**, then **WP3-png** (`chartExport.ts`) | WP1 | Chart letters ringed, key under the legend; PNG states its period range |
| 4b | **table plan**, then **WP3-xlsx** (`excel_export_service.py`) | WP1 | Table header key; flags visible in the workbook grid |
| 4c | **#1601**, then the **analysis plan**, then **WP3-pdf** (`export_service.py`) | WP1, #1601 | Formatted company name, readable dates, key on the table page, Inter dagger |
| 5 | **WP4** surfaces and results header | 4a–4c (it moves every module) | Results header, quieter control card, the Feedback launcher clear of the KPIs |

4a, 4b and 4c can run in parallel: their only shared file is `DESIGN_SYSTEM.md`, in sections that
don't overlap. Step 1 shares no file with steps 2–5 except `tasks/todo.md`, so it can start today.

## 7. Findings for the other plans

These came out of this evaluation but sit in the sibling areas.

- **Charts:**
  - Same-unit USD series split across two axes, so FY2025 FCF ($4.1B) plots above net income
    ($4.5B) while the text says it is below (Y-F6, Z-F7).
  - Year ticks run together on phones.
  - Irregular top ticks, and "$0.00" on billion-dollar axes.
- **Analysis:**
  - Red flags and "What to watch" assert conclusions from flagged figures with no caveat (X-F12,
    Y-F2).
  - "Compressed 5.9pp" beside 30.9% → 24.9%, a rounding artefact (Y-F19).
  - Raw machine precision in the source list.
  - Templated repetition.
  - "Calculated figure" against "Calculated from recorded inputs".
- **Table:**
  - Growth on negative bases (−7,527.1%).
  - Unexplained "—" in the window column.
  - Inconsistent direction colour (current liabilities red, capex grey) with no legend.
  - "Showing 10 of 10 years" on a phone that shows two.
  - The CAGR header over percentage-point rows.
- **Page:**
  - The Feedback launcher over the Revenue KPI on phones (N17; X-F6, Y-F8, Z-F15), assigned to
    WP4.
  - "Last 5" and "Last 10" show no selected state.
  - The nav reads "Multi-period analysis" and the title "Multi-Period Analysis".

## 8. Limits

- **The frequency census covers the companies in the production sitemap through public endpoints.**
  It gives each company's newest annual value per metric, plus the per-year state of filing-owned
  rows. Companies outside the sitemap and the per-year state of companyfacts-owned rows wait for
  `mpa_notation_frequency.sql` (§1.7).
- **The page and exports are a local reproduction calibrated to production (§1.4), not production
  captures.** Production's own page could not be opened without a Pro session.
- **Each heuristic set had one evaluator.** The comprehension test is one model instance per round,
  not a panel of subscribers, so it shows misreadings, not their rates.
- **The composites shown to the current-page and round-1 readers stacked Data notes closed above
  Data notes open.** Both readers reported "the block appears twice", which is an artefact of the
  composite, not of the page.
- **The competitor captures are signed-out views.** Their paid tiers show more. Six other paid
  products turned away the headless browser, and one served a captcha, which was left unsolved.
- **The production census ran from a cloud container at about 7 requests a second over about 40
  minutes, all reads.** The company-filings read used for the per-year pass refreshes from SEC in
  the background, as any page view does. It was made once for each of 27 companies.

## 9. Independent verification

### a. Flag-frequency table (from §1.2)

| Cut | Cells | Needs review | Share |
|---|---:|---:|---:|
| Production, latest annual value, all metrics (27 companies) | 484 | 82 | 16.9% |
| Calculated metrics only (margins, FCF, WC, CR) | 105 | 77 | 73.3% |
| Reported metrics | 379 | 5 | 1.3% |
| Filing-owned rows, FY2022 / FY2023 / FY2024 / FY2025 / FY2026 | 127 / 288 / 372 / 394 / 113 | 26 / 61 / 79 / 83 / 20 | 20.5% / 21.2% / 21.2% / 21.1% / 17.7% |
| REGN, FY2016–FY2025 figures / comparisons | 200 / 192 | 11 / 16 | 5.5% / 8.3% |
| Companies with a headline figure needing review | 27 | 23 | 85.2% |

The full breakdowns by metric, sector, year, reason and method are in
[verification/flag-frequency-census.md](verification/flag-frequency-census.md) and
[verification/flag-frequency-by-year.md](verification/flag-frequency-by-year.md). The
full-population SQL is [`ops/detection/mpa_notation_frequency.sql`](../../ops/detection/mpa_notation_frequency.sql).

### b. Heuristic evaluation, before and after (blind re-scores)

| Set | Severity sum | Sev 1 / 2 / 3 / 4 | Findings |
|---|---:|---|---:|
| X, current page | 50 | 5 / 12 / 7 / 0 | 24 |
| Y, prototype round 1 | 48 | 10 / 13 / 4 / 0 | 27 |
| Z, prototype round 2 | 43 | 5 / 13 / 4 / 0 | 22 |
| Author's own evaluation, current page (§4.1) | 46 | 2 / 10 / 8 / 0 | 20 |

The before and after screenshots are in [`screens/`](screens/), and the transcripts in
[verification/heuristic-rescore-transcripts.md](verification/heuristic-rescore-transcripts.md).

### c. Comprehension-test transcript

[verification/comprehension-transcripts.md](verification/comprehension-transcripts.md) holds four
rounds, verbatim, with the images they were given. §3.4 summarises them.

### d. Export inspection, pass/fail

| Artefact × theme | Pass | Partial | Fail |
|---|---:|---:|---:|
| PDF light / dark | 5 / 5 | 3 / 3 | 1 / 1 |
| Excel light / dark | 6 / 6 | 2 / 2 | 2 / 2 |
| PNG revenue light / dark | 6 / 6 | 1 / 1 | 1 / 1 |
| PNG margins light / dark | 5 / 5 | 2 / 2 | 1 / 1 |
| **Total (70 checks)** | **44** | **16** | **10** |

Every check with its evidence is in
[verification/export-inspection.md](verification/export-inspection.md).

### e. File-overlap matrix

The matrix is in §6; the full pairwise file list is in
[verification/file-overlap.md](verification/file-overlap.md).

### f. Competitor screenshots

[`competitors/`](competitors/) holds:
- Roic.ai: financials chart and statement, light and dark;
- Yahoo Finance: financials chart and statement, light (no dark theme signed out);
- Finviz: statements, light and dark;
- Alpha Spread: AI financial profile, light (supplement);
- `captures.json`, the URL and theme each was captured from.
