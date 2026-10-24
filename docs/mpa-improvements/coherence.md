# Multi-Period Analysis: notation, data notes and cross-cutting coherence

2026-10-24 · base `a41c6e4` · scope: what †, "a" and "b" mean and how often they fire; one notation
system; the data notes; a heuristic evaluation and competitor teardown; the exports as files; the
order in which this work and the sibling plans (charts, analysis, table) should land.
Evidence lives beside this file: [`verification/`](verification/), [`screens/`](screens/),
[`exports/`](exports/), [`competitors/`](competitors/), [`prototype/`](prototype/) and the
[methods appendix](methods.md).

**Revised the same day.** The first version recommended ringed review letters, "needs a source
check" on the KPI cards and a key beside every mark. The founder found that dramatic and
distrust-inducing. A blind test of four designs agreed, so the recommendation is now the quiet scheme in §2.
The ring design stays on record in [`prototype/notation-prototype.diff`](prototype/notation-prototype.diff)
and [`screens/variants/ring-light-full.png`](screens/variants/ring-light-full.png).

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
3. **Mark only what questions the number; keep everything else one click away (§2).** Competitors
   mark nothing (§4.3). EarningsNerd's difference is that every figure opens its source, method and
   inputs. That holds without a mark on every figure. In a blind test, four designs shown on one
   REGN data state were each read by two fresh evaluators (§2.8). It included a planted restatement
   note on FY2018–FY2019 revenue:

   | Design | Trust in FCF $4.1B (correct) | Page told them FY2018 revenue was in question | Clean | Feels trustworthy |
   |---|---|---|---|---|
   | Current (dagger + warning-ink letters) | 3, 4 | both | 3, 3 | 3, 3 |
   | Ring (the first proposal) | 3, 3 | both | 3, 3 | 3, 4 |
   | **Quiet** (recommended) | **4, 4** | **both** | **4, 4** | **4, 4** |
   | No marks at all | 4, 4 | **neither** | 4, 4 | 4, 4 |

   Removing the marks from correct figures raised trust and calm. Removing every mark hid the one
   real problem: the no-marks readers caught it only by cross-checking rows and from memory. Both
   asked for a mark on that figure. The quiet scheme:
   - no dagger on any figure; one sentence above the table names the calculated metrics;
   - a small neutral letter, with no ring and no warning ink, only where a note questions the number;
   - the legacy-calculation notes and gaps go unmarked, but remain in the fine print and the
     evidence dialog;
   - the Data notes strip becomes one line of fine print under the table;
   - the exports follow the same rule.

   After the backfill, most companies would show no mark at all. A mark that does appear keeps its
   meaning.
4. **Data notes: one neutral line under the table, in plain words (§3).** The comprehension
   rounds settled the words, and they carry over: "Not in our data … shown as —, never as zero";
   "Calculated before 10 October 2026, when we began keeping each calculation's inputs".
   - **The comprehension test.** The reader of the current page put the $4.1B free cash flow at
     2/5 and had to guess what "a" meant.
   - **The blind test.** Readers of the current page put it at 3 and 4. Under the quiet scheme it
     carries no letter, and both readers put it at 4. Each reconciled it from the evidence on the
     page: operating cash flow minus capex.
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
   2. The quiet notation, after #1597.
   3. The data-notes words.
   4. The exports, split so each piece follows the sibling that owns its file and #1601.
   5. Surfaces and the results header, last.
   6. The restatement note, alongside the data-notes words (its own backend change).
7. **One decision for the founder before step 2 (§2.9).** The 2026-10 redesign records the
   founder's rule "never hide a note". A P0 review enforced it for exactly the case the quiet
   scheme stops marking: a figure whose only note is `legacy_calculation`. The proposed wording is
   "every note stays in the evidence dialog and the data notes; only a note that questions the
   number keeps a mark beside the figure". The change stays presentation-only:
   - note kinds and totals are unchanged;
   - a legacy figure is never shown as validated;
   - the fine print never says "No figures need review" while a legacy note exists.

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
reported, which is still stored as a non-latest row of that accession, add a note: "restated
in a later filing". It does question the number, so under the quiet scheme it is one of the few
notes that marks a figure (§2.1), in neutral ink. The blind test's quiet-design readers found the
note, but read it as housekeeping (§2.8). So the change also covers:
- **The dialog** names both values and both filings, with their dates.
- **Growth across the restatement** (FY2017→FY2018 here) reads as not comparable (n/m) rather
  than −12.4%, because its two years come from different scopes.
- **Calculated figures** whose input carries the note (FY2018–FY2019 margins) inherit its letter,
  as growth already does.

Before choosing the tolerance, count how often the note fires across the 27 companies with the
census method.

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

This section was revised after the founder's review. §2.8 has the test that replaced the first
version: ringed review letters, "needs a source check" on the KPI cards and a key beside every
mark. That version is kept in [`prototype/notation-prototype.diff`](prototype/notation-prototype.diff).

### 2.1 Principles

- **Evidence on demand.** Every figure opens its source filing, method, inputs and checks in the
  shared evidence dialog. That is where provenance lives. None of the three competitors offers it,
  and none marks a figure's origin (§4.3). The evidence is the difference; a mark on every figure
  is not.
- **A mark means the number itself is in question.** A figure carries a mark only when a note
  doubts that the value is what the filings support:
  - a later filing restated it (WP5's note, §1.6), or the filings disagree (`source_conflict`);
  - a reported value could not be matched to the filed data (`source_check_needed`,
    `value_mismatch`, `unit_mismatch`, `period_mismatch`);
  - a calculation disagrees with its inputs or cannot find them (`calculation_mismatch`,
    `missing_calculation_inputs`; the backfill's honest outcomes, §1.5).

  A note about the record rather than the value gets no mark. Today that is `legacy_calculation`
  alone: 77 of production's 82 latest-year review flags, and all 11 REGN cells reproduce exactly
  from their inputs. A gap shows "—" and needs no letter. A missing validation record makes no
  claim either way. The list of record-only reasons is closed. Any other reason marks the figure, so
  a new reason fails loud, not silent.
- **Calculation is routine, so it goes unmarked.** One sentence above the table names the
  calculated metrics. Each figure's evidence dialog states the method and inputs. Its accessible
  name keeps "calculated", so a screen reader still hears what the dagger used to say.
- **Small and neutral.** The letter is raised and set at the 11px data-xs size in secondary text
  ink. It never scales with the figure, and it has no ring and no warning ink. A mark that appears
  rarely does not need to shout, and both quiet-design readers found it (§2.8).
- **Filtered, never reclassified.** The scheme decides only which notes put a mark beside a
  figure.
  - Note kinds, reasons and totals stay as the backend computes them.
  - The fine print and the dialog still name every note, legacy included.
  - The page never says "No figures need review" while a legacy note exists.
  - The page never calls a legacy figure validated.
- **One rule on every surface.** The page, PDF, workbook and chart PNG mark the same notes. One
  reason list decides, held by `data_notes.py` and `lib/dataNotes.ts`, and the shared notes fixture
  (`backend/tests/fixtures/analysis_data_notes.json`) pins the two copies equal.

### 2.2 What each note shows, and where

| Note | On the figure | In the fine print under the table | In the evidence dialog |
|---|---|---|---|
| Questions the number (restated, filings disagree, unmatched, calculation mismatch) | A neutral raised letter. The growth figures built on it carry the same letter, as now. Figures calculated from it should too (WP5: FY2018 margins built on restated revenue) | The letter, its places and one sentence, in the summary line | The note in full. For a restatement: both values, both filings and their dates |
| Calculated, inputs linked | nothing | Named in the sentence above the table | Method, formula, linked inputs |
| Calculated before lineage existed (`legacy_calculation`) | nothing | One sentence and its places, in the open detail | "Calculated before 10 October 2026 …; shown as stored, inputs not linked" |
| Not in our data | "—" | A count in the summary; one sentence in the detail | "Not in our data" |
| No validation record | nothing | A count in the summary; one sentence in the detail | "No check recorded" |

**Letters.** Letters stay report-local, as a filing's footnotes do. Only marked notes need a letter
the reader can see, so WP2 letters the marked notes first, and a page's first visible letter is "a".
Saved snapshots keep their stored letters. An old snapshot can show "b" alone, and the fine print
maps it. A figure's accessible name follows what is visible: it names a marked note and says
"calculated" where the figure is calculated. A record-only note is read in the dialog, where
sighted readers find it too.

**The prototype.** [`prototype/notation-quiet.diff`](prototype/notation-quiet.diff), captured in
[`screens/variants/`](screens/variants/): `quiet-light-full`, `quiet-dark-full`, both phone widths,
the KPI cards, and the fine print closed and open.
- It filters marks in `DataNotesContext`, `DataNotesLink` and `NarrativePane`.
- It prints the fine print from `QuietDataNotes.tsx`.
- Its record-only list is `legacy_calculation` alone. Unavailable and unknown notes are unmarked
  by kind.
- Its summary sentence covers only the restatement case.

It is a design instrument, not the code to merge.

### 2.3 Tokens, in DESIGN.md's frontmatter format

```yaml
components:
  figure-note-mark:
    textColor: "{colors.text-secondary-light}"
    typography: "{typography.data-xs}"
  figure-note-mark-dark:
    textColor: "{colors.text-secondary-dark}"
  data-notes-fine-print:
    textColor: "{colors.text-secondary-light}"
  data-notes-fine-print-dark:
    textColor: "{colors.text-secondary-dark}"
```

The change mostly removes rules. The dagger's sizing goes, the warning-ink letters go, and the
strip's place under the KPI cards goes.
- **Legibility.** `text-secondary-light` (#374151) and `text-secondary-dark` (#9CA3AF, 5.8:1 on
  the dark panel) both clear 4.5:1. `text-floors.spec.ts` re-checks the fine print.
- **Type.** The fine print is 12px running copy (`text-xs`), not `data-xs`, so the exact caps in
  `dataXsAllowlist.spec.ts` don't move.
- **Same-PR refresh.** `DESIGN.md`'s Calculation Provenance Rule, `.impeccable/design.json`
  (`designSnapshotParity.spec.ts`) and `DESIGN_SYSTEM.md` are refreshed in the same PR (§2.9).
- **The rule-12 gate.** A unit spec over the shared notes fixture: every questioning reason renders
  a mark on the page, the PDF and the PNG, and every record-only reason renders none. A mutation
  that flips either direction fails it.

### 2.4 The key

There is almost nothing to key, so there is no key beside every mark:
- **Above the table**, one sentence replaces the "† calculated" label: "Figures are rounded for
  display; margins, free cash flow, working capital and the current ratio are calculated from
  filed figures. Select any value for its source and full precision."
- **Notes chips.** The table's chip lists only the visible marked letters and opens the fine print
  at that note. Each chart's chip does the same. A hollow point appears only where a note is
  marked.
- **Fine print.** Its summary line names each marked letter with its places and words. Its open
  detail lists every note.
- **Exports.** The PDF puts the same line under its table, on the same page. The workbook puts it
  on the Metrics header row.

### 2.5 Per-surface rules

| Surface | Rule |
|---|---|
| KPI card | The figure and its period line. A letter appears only when the headline figure's own note questions it. No warning words on the card. For REGN today, all four cards are clean ([`quiet-light-kpis.png`](screens/variants/quiet-light-kpis.png)). |
| Metrics table | The sentence above the table. A compact letter (0.5px gap) on marked values and the comparisons built on them. A gap is "—" with no letter. The Q4 column-header dagger and the period picker's "Q4 2023 †" mark periods, not figures. WP1 decides whether to keep them or turn them into words ("Q4 derived"). Either way, the picker must still show which Q4s are calculated (redesign doc :915–916). |
| Charts | Hollow point and letter for marked notes only. A gap breaks the line, as now. The letter takes the mark's ink and keeps its panel-colour halo. |
| Narrative and sources | A citation chip carries a letter only for a marked note. In the source list, "Calculated figure" and "Calculated from recorded inputs" become "calculated from filed figures" and "calculated before we kept its inputs". "Sources identify filed figures or calculated figures (marked †)" becomes "Sources identify filed and calculated figures". Raw precision belongs to the analysis plan (§7). |
| Data notes | One line of fine print under the table (§3). |
| PDF | No dagger after each value (`export_service.py:349`). The calculated sentence and the fine print sit under the table, on the same page. Letters for marked notes only, with the page's reason sentences. |
| Excel | Every note stays as a cell comment, which is the workbook's evidence dialog. A marked note also shows its letter in the grid through the number format (`#,##0" a"`), so the cell stays numeric. No warning-ink fonts. The fine print goes on the Metrics header row. |
| Chart PNG | The period range in the subtitle ("REGN · Margins · FY2016–FY2025"). The footer names marked letters only. |

### 2.6 Reconciling with the sibling reports

No sibling report exists yet. On 2026-10-24, `docs/mpa-improvements/` held none on any remote
branch: 42 checked at 20:05 UTC and 21:10 UTC, 44 at 22:18 UTC. So nothing conflicts today. For
when they land:
- This report owns notation semantics: which notes mark a figure, the words, the glyph, size and
  ink, and the vocabulary.
- The charts plan owns marker geometry and placement, and uses `figure-note-mark` and the marking
  rule (§2.1).
- The table plan owns cell layout and density. It uses the compact mark and the sentence above the
  table.
- The analysis plan owns narrative wording and the source list. Its chips mark through the same
  rule.

A sibling proposal that marks routine figures, recolours a mark or brings back a strip of counts is
resolved in favour of §2, unless it brings blind-test evidence as strong as §2.8's. Merge order
(§6) puts the notation first, so each sibling builds on it rather than beside it.

### 2.7 What the prototype changes and breaks

[`prototype/notation-quiet.diff`](prototype/notation-quiet.diff) applies to `a41c6e4`.
- It edits `AnalysisPageClient.tsx`, `DataNoteMark.tsx`, `DataNotesContext.tsx`,
  `DataNotesLink.tsx`, `MetricsTable.tsx` and `NarrativePane.tsx`.
- It adds `QuietDataNotes.tsx` and `notationVariant.ts`.
- The switch defaults to `current`, so all 233 tests in the 14 analysis unit spec files pass
  unchanged.

With `NEXT_PUBLIC_NOTATION_VARIANT=quiet`, 23 tests fail in six files. Each one pins something
the scheme removes: a legacy-calculation letter, an unavailable letter, the "† calculated" label,
or the rounding sentence that the calculated-metrics sentence replaces.
- `trend-charts-annotation.spec.tsx`: 7. Chips ("Review data notes a"), hollow points and tooltip
  notes, all built on legacy and gap letters.
- `analysis-source-quality.spec.tsx`: 6. The chip's unavailable letter ("Review data notes z, a"),
  the unavailable cell's accessible name, the locators, and "† calculated" in the Q4 case.
- `narrative-pane.spec.tsx`: 6. Legacy-calculation chips and their accessible names ("… data note
  a").
- `metrics-table.spec.tsx`: 2. "† calculated", and the old rounding sentence.
- `kpi-strip.spec.tsx`: 1. A value's accessible name that included a note the scheme leaves
  unmarked.
- `trend-charts-legend.spec.tsx`: 1. The chart chip "Review data notes a, b".

They are the implementation's to-do list. The fix switches each case to a questioning reason where
the mark is the point (`source_conflict`), and asserts no mark where the note is record-only. That
keeps proof that questioning notes stay marked. The browser gate `analysis-layout.spec.ts` and its
fixture move the same way (§2.9).

### 2.8 Four designs, tested blind

The method, the full table and the quotes are in
[verification/notation-variant-test.md](verification/notation-variant-test.md). Every verdict, in
full, is in [its JSON](verification/notation-variant-test.json).

**Setup.**
- **Data.** One local REGN data state. FY2018–FY2019 revenue was planted as a restatement note
  (`source_conflict`), standing in for WP5. In production these cells read clean today.
- **Designs.** Four, unlabelled (P–S): current, ring, quiet and no marks. Each was a full page at
  1440px.
- **Readers.** Two fresh model instances per design: a paying retail investor and a sceptical
  fund analyst. Each saw only its page and declared any outside knowledge.
- **Re-run.** The quiet and no-marks builds first leaked letters into the narrative's citation
  chips. Both were re-run after the fix (R2, S2).

| Design | Overall trust | FCF $4.1B (correct) | FY2018 revenue $5.1B (restated) | The page flagged the revenue | Clean | Trustworthy |
|---|---|---|---|---|---|---|
| Current | 3, 3 | 3, 4 | 2, 2 | both | 3, 3 | 3, 3 |
| Ring | 3, 3 | 3, 3 | 2, 2 | both | 3, 3 | 3, 4 |
| **Quiet** (fixed) | 3, 3 | **4, 4** | 2, 2 | **both** | **4, 4** | **4, 4** |
| No marks (fixed) | 3, 3 | 4, 4 | 2, 2 | **neither** | 4, 4 | 4, 4 |

1. **Taking the marks off correct figures costs nothing.** Trust in the correct $4.1B rose, and
   cleanliness and trustworthiness rose from 3 to 4. Overall trust is 3 in every verdict, so the
   marks never bought trust.
2. **Removing every mark hides the one real problem.**
   - Both no-marks readers wrote that nothing on the page flags FY2018 revenue. They doubted it
     only by cross-checking rows (revenue −12.4% beside operating income +21.9%) and from memory.
     A reader who doesn't cross-check takes the false −12.4% as real.
   - Both quiet readers found it from the page.
3. **Readers of every design asked for the same thing.** Mark only the doubtful figure, quietly,
   and say what is wrong where it appears. The ring design's analyst: "Don't remove the flags, and
   don't push them all into the fine print. The FY2018 revenue flag is the most useful thing on
   the page, and if I later found an unflagged wrong number, I'd stop trusting the whole product."
   The no-marks readers both asked for a mark on that cell.
4. **What the quiet design still lacks goes to WP5.**
   - The restatement note read "like a routine housekeeping footnote".
   - Readers want the as-filed value, the restating filing and its date one tap away.
   - Growth across the restatement should read as not comparable.
   - Figures computed from the restated value should inherit its letter.

**Decision.** Quiet. Removal scored the same on cleanliness, trust in the correct figure and
trustworthiness, so a mark on the doubtful figure costs nothing. Without it, the page would be
silent when the data is wrong. EarningsNerd's sourcing difference would then become a promise the
page no longer keeps where it matters.

### 2.9 What the quiet scheme must update, and the one founder decision

A read-only agent searched the repository for everything the quiet scheme contradicts. Its full
findings, with file, line and exact words, are in
[verification/notation-variant-test.md](verification/notation-variant-test.md#the-rules-check-one-agent-read-only-over-the-whole-repository).

**Needs the founder first.** The founder's "never hide a note" is recorded in
`tasks/analysis-redesign-2026-10/astra-prompt.md:74` and `review-2026-10-10.md:36`. A P0 review
enforced it for exactly the case the scheme stops marking: a `legacy_calculation` figure.
- **The decision.** A one-line confirmation narrowing it to "every note stays in the evidence
  dialog and the data notes; only a note that questions the number keeps a mark beside the figure".
  It is recorded as a decision row in `docs/brand/decisions-log.md`, with both task files pointing
  at it.
- **What still holds.** The rule's other two clauses: never mark a legacy record validated, and
  never say "verified".
- **What is out of scope.** Reclassifying `legacy_calculation` in the backend changes what counts
  as needs-review (redesign doc :896), a separate call. It would also break the strict note-kind
  decoder (`dataNotesContract.ts:59`) for tabs already open.

**Not blocked.**
- No ADR or D-0xx decision requires the dagger, warning ink or the strip under the KPI cards. The
  Calculation Provenance Rule came from #1191's design work.
- No marketing, pricing, legal or brand page promises a visible per-figure mark.
- The founder's 2026-10-10 analysis decisions stay compatible: letters as the note mark, the glyph
  budget, "Unavailable" and "No figures need review".

**Same PR as the notation (WP1).**

| Kind | Where | Change |
|---|---|---|
| Rule and sidecar | `DESIGN.md:498`, `.impeccable/design.json:602` | Rewrite the Calculation Provenance Rule for §2.1 and keep "a calculation describes a figure's origin, not a failed check". `designSnapshotParity.spec.ts` checks both copies. |
| Recipes | `frontend/DESIGN_SYSTEM.md:492` (note mark), `:564` (table chip, Q4 dagger), `:645` (Data notes strip), `:2083` (§10) | Rewrite each for §2.2–§2.5. Keep the native `<details>` so a chip can open a note. Keep the sample's "sample data (one saved run)" label (D-046). |
| Lesson | `lessons/arch-reconciliation-follows-values-and-growth.md:20` | "Keep a mark at each affected figure" becomes "at each figure whose note questions the number; every note in the dialog, the data notes and the exports". The process lesson from this correction is already in this branch: `lessons/brand-test-a-trust-mark-blind-against-quieter-and-none.md`. |
| Design record | `docs/design/analysis-data-notes-redesign-2026-10.md` §1, §4.2, §4.3, §4.10 | A dated supersession note. Its §9 decisions stay in force. |
| In-product copy | `NarrativePane.tsx:121`, `DataNotes.tsx:103` | Both promise a † that no longer appears (§2.5). |
| Landing | `AnalysisDemo.tsx:45`, `AnalysisTeaser.tsx:41` | Move the notes below the table, as on the page. |
| Unit specs | the six files in §2.7, plus `analysis-table-format.spec.ts:41` (the dagger's glyph is freed under decision 6) | Re-pin as §2.7 says. |
| Browser gate | `tests/e2e/analysis-layout.spec.ts` and `fixtures/analysisLayoutApi.ts` | Dagger counts, legacy and unavailable letters, the chip's name and the summary text. Keep the discrepancy state's letters as proof. |

**With the exports (WP3).** `test_export_service.py:648`, `:675`, `:677`, `:761` and `:813`, plus
`test_export_voice.py:188`, pin the PDF's dagger, its gap letter and the order of its Data notes
heading. The workbook already keeps notes in comments (`test_excel_export.py:218`).

**Scope notes.**
- The filing page's "Change†" (`FinancialMetricsTable.tsx:222`) keeps its dagger. The two surfaces
  now differ on purpose, and the PR should say so.
- The brand audit's T11 finding, "the disclaimer forgot to be a product" (`docs/brand/00-audit.md:55`),
  supports moving the notes below the table.

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

The first design put a plain-words summary, a "where" line and the key in a strip under the KPI
cards. After the founder's review and the blind test (§2.8), the data notes become fine print under
the metrics table: neutral ink, 12px, one line while closed, and the detail one click away.

```
▸ Data notes · ᵃ Revenue FY2018, FY2019: restated in a later filing; we show the later value · 3 not in our data, shown as — · 50 calculated from filed figures

  a. Restated in a later filing: the year's own annual report gave a different value. We show the later filing's value;
     select one to see both filings. Revenue FY2018, FY2019.
  Calculated before 10 October 2026, when we began keeping each calculation's inputs; shown as stored, with its inputs
     not linked. Operating margin FY2023, FY2024, FY2025; Net margin FY2023, FY2024, FY2025; Free cash flow FY2023,
     FY2024, FY2025; Working capital FY2024; Current ratio FY2024.
  Not in our data for these periods; shown as —, never as zero. Long-term debt FY2016, FY2017, FY2018.
  Select any figure to see its source filing, method and inputs. Automated checks confirm that reported figures come
     from the company's filed data (XBRL); they are not an audit of the company's accounts.
```

The screens are [`quiet-light-datanotes-closed.png`](screens/variants/quiet-light-datanotes-closed.png),
[`quiet-light-datanotes-open.png`](screens/variants/quiet-light-datanotes-open.png),
[`quiet-dark-datanotes-open.png`](screens/variants/quiet-dark-datanotes-open.png) and the full
page, [`quiet-light-full.png`](screens/variants/quiet-light-full.png). The ring design's strip
is in [`screens/`](screens/) as `final-*`.

- **The summary line.** It names each marked note with its places and words. It counts the gaps
  and the calculated figures, and nothing is in warning ink.
  - With no marked note it reads "Data notes · 3 not in our data, shown as — · 50 calculated from
    filed figures".
  - When every populated figure passed and no note exists, it keeps "No figures need review" with
    the checked count (founder decision 9). It never says that while a legacy note exists.
- **Legacy notes** appear only in the detail. Their sentence says the record is incomplete, not
  the figure.
- **Comparison locators move off the page.** "13 year-over-year comparisons carry this note. The
  table shows 13. Exports carry all 13." describes plumbing. The letter on each growth figure
  locates the comparison.
- **Chips.** The native `<details>` stays, so a Notes chip can open the fine print at its note.
- **The landing sample** keeps its "sample data (one saved run)" label in the fine print (D-046).
- **Where the copy lives.** The copy moves to `data_notes.REASONS` on the backend (WP2), so the PDF,
  workbook and PNG print the same words. The prototype maps reasons on the frontend only.

### 3.3 Wording

| Place | Today | Proposed |
|---|---|---|
| Summary, a note that questions the number | "11 figures need review (a)" (every review note in one count) | "ᵃ Revenue FY2018, FY2019: restated in a later filing; we show the later value": places and words, no count |
| Summary, legacy calculations | inside the same count | detail only |
| Summary, gaps | "3 unavailable (b)" | "3 not in our data, shown as —" |
| Summary, calculated | "50 calculated †" | "50 calculated from filed figures" |
| `legacy_calculation` | "This saved calculation predates the current source checks. Its inputs need review." | "Calculated before 10 October 2026, when we began keeping each calculation's inputs; shown as stored, with its inputs not linked." |
| WP5 restatement | (none: the figure reads clean) | "Restated in a later filing: the year's own annual report gave a different value. We show the later filing's value; select one to see both filings." |
| `source_conflict` (filings disagree, no later restatement) | "Available sources disagree on this figure." | "The company's filings report different values for this figure. We show the most recent filing's value; select it to compare." |
| `source_check_needed` | "A source check remains unresolved. Review the original filing before use." | "Not yet matched to the filing: our automated check could not confirm this figure against the company's filed data. Select it to compare with the filing." |
| `not_in_dataset` | "Not available in this dataset." | "Not in our data for these periods; shown as —, never as zero." |
| Legend | "Letters identify data notes; † marks a calculated figure, not an error." | "Select any figure to see its source filing, method and inputs. Automated checks confirm that reported figures come from the company's filed data (XBRL); they are not an audit of the company's accounts." |
| Above the table | "Figures are rounded for display. Select a value for full precision." | "Figures are rounded for display; margins, free cash flow, working capital and the current ratio are calculated from filed figures. Select any value for its source and full precision." |
| KPI card | "$4.1B†ᵃ" | "$4.1B": a letter only for a note that questions the figure |

Each sentence promises only what the code enforces:
- "10 October 2026" is #1191's merge date.
- "Not in our data" makes no claim about whether the company reported the figure.
- "Restated in a later filing" needs WP5's check that the year's own filing reported another
  value. A plain disagreement keeps the `source_conflict` sentence. The first-run quiet readers
  found "the company's filings disagree" alarming and unresolved, so that sentence names what is
  shown and how to compare.

### 3.4 Comprehension test

These rounds tested the ring design's words, before the founder's review. Two of their findings
carry over to the quiet scheme:
- the gap sentence ("never as zero");
- the legacy sentence's point that the record is incomplete, not the figure.

The marks they explained are gone. The quiet design's own test is §2.8.

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

### 3.5 What the tests leave open

- **The restatement note reads like housekeeping** (§2.8, R2). WP5's dialog must show both values
  and both filings with their dates. Growth across the restatement should read as not comparable,
  and figures calculated from the restated value should inherit the letter.
- **A legacy figure carries no mark.** A reader learns of its incomplete record only in the fine
  print's detail or the dialog. That is the founder decision in §2.9, and the backfill (§1.5)
  removes the case.
- **Growth figures keep their direction ink when marked.** Direction and doubt are separate axes.
  The neutral letter sits next to the colour, so the colour is not read as confirmation.
- **Closed by the quiet scheme:**
  - amber read as alarm for a record that is only incomplete;
  - ringed versus plain letters needed the legend;
  - "11 need a source check" beside "16 growth figures" read as two different counts.

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
These sets scored the ring prototype. For the notation itself, the blind variant test (§2.8)
supersedes them.

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
   The quiet scheme (§2) matches them on routine figures and keeps the evidence one click away. It
   marks only a figure in question, which none of them can do, because none of them checks.
2. All three present a multi-year statement on one surface. EarningsNerd stacks nine equal cards.
3. All three show period-end dates in the table itself. EarningsNerd shows them only in the
   evidence dialog.
4. Where competitors mark state (a padlock), they pair the glyph with words on the same surface.

### 4.4 The surface, elevation and spacing system the gaps call for

The table plan's surface proposal has not landed (§2.6), so this follows DESIGN.md's Lifted Paper
Rule and its existing tokens, and it leaves the table's interior to that plan.

| Level | Token | Holds | Change from today |
|---|---|---|---|
| Ground | `background` | The page title, the **results header** (new: "Regeneron Pharmaceuticals, Inc. · REGN · Annual FY2016–FY2025 · data as of 24 Oct 2026"), the disclaimer | The results header is new. Data notes leave the ground for fine print under the metrics table (§3.2) |
| Control | `panel`, hairline, **no shadow** | The company and period form | Drops from `shadow-e2` to a hairline. An input area is not content, and today it outranks the results |
| Content | `panel`, hairline, `shadow-e2` light / fill + hairline dark | KPI strip, charts, AI analysis, metrics table: one card per module | Unchanged; the chart grid stays one card per chart |
| Overlay | `shadow-e4` / `e5` | Evidence modal, popovers | Unchanged |

**Spacing.**
- 12px (`gap-3`) between the results header and the KPI strip, so they read as one block.
- 8px between the metrics table card and the Data notes fine print beneath it.
- 24px (`gap-6`) between content modules on desktop and 16px (`gap-4`) below `sm`.
- Module insets keep `p-cap-6`.
- A mark keeps the 0.125rem gap after its figure, and 0.5px in table cells (§2.5).
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

**Under the quiet scheme (§2.5) the exports follow the page.** That settles two of the misses
above outright:
- The 52 DejaVu daggers go with the per-value dagger.
- In the workbook, a figure in question gets a visible letter in the grid, while the comment
  triangle stays the evidence for every note.

The PDF's key-on-another-page miss becomes fine print under the table, on the same page.

Theme behaviour is consistent but undocumented. The PDF and workbook are always light; the PNG
follows the page. Keep that, and say so in the export menu ("Image matches your theme").

## 6. Sequencing by measured overlap

Live branches are measured: `git diff --name-only` against each branch's merge base. This plan's
work packages list the files each edits. The sibling scopes list the files each area owns, because
no sibling branch exists yet. The computation is reproducible from the
[methods appendix](methods.md).

| | WP0 | WP1 | WP2 | WP3 | WP4 | WP5 | charts | analysis | table | #1601 | #1597 | section-nav | #1583 | #1600 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **WP0 lineage backfill** (10) | — | · | · | · | · | · | · | · | · | · | 1 | 1 | 1 | 1 |
| **WP1 quiet notation** (29) | · | — | 4 | · | 6 | 2 | 3 | 2 | 5 | · | 3 | 2 | · | · |
| **WP2 data-notes words** (9) | · | 4 | — | 1 | · | 3 | · | · | · | · | · | · | · | · |
| **WP3 exports** (9) | · | · | 1 | — | · | · | 2 | 1 | 1 | 3 | · | · | · | · |
| **WP4 surfaces + results header** (8) | · | 6 | · | · | — | · | 1 | · | 1 | · | 2 | 2 | · | · |
| **WP5 restatement note** (7) | · | 2 | 3 | · | · | — | · | · | · | · | · | · | · | · |
| **charts plan (scope)** (7) | · | 3 | · | 2 | 1 | · | — | · | 1 | · | 1 | 1 | · | · |
| **analysis plan (scope)** (7) | · | 2 | · | 1 | · | · | · | — | · | 1 | · | · | · | · |
| **table plan (scope)** (7) | · | 5 | · | 1 | 1 | · | 1 | · | — | · | 1 | 1 | · | · |
| **#1601 export-source** (6) | · | · | · | 3 | · | · | · | 1 | · | — | 1 | · | · | · |
| **#1597 status-line** (19) | 1 | 3 | · | · | 2 | · | 1 | · | 1 | 1 | — | 3 | 2 | 1 |
| **section-nav (no PR)** (9) | 1 | 2 | · | · | 2 | · | 1 | · | 1 | · | 3 | — | 1 | 1 |
| **#1583 per-filing-currency** (9) | 1 | · | · | · | · | · | · | · | · | · | 2 | 1 | — | 1 |
| **#1600 waitlist-source** (5) | 1 | · | · | · | · | · | · | · | · | · | 1 | 1 | 1 | — |

Every shared file by pair is listed under the matrix in
[verification/file-overlap.md](verification/file-overlap.md). Two shared files are worth naming:
- `DESIGN.md` and `DESIGN_SYSTEM.md` (WP1, WP4, #1597, section-nav). The edit sites are disjoint:
  #1597 edits DESIGN.md line 343 and DESIGN_SYSTEM.md 907 and 2191–2203. Section-nav edits 482
  and 1210–1241. WP1 edits DESIGN.md's frontmatter components and line 498, and DESIGN_SYSTEM.md
  492–500, 564, 645–661 and 2083–2095. Git merges them, but `designSnapshotParity` reads the whole
  file, so rebase and rerun it after each.
- The quiet WP1 is wider than the ring version: 29 files against 18 (re-measured 22:18 UTC). It
  shares four files with WP2 and six with WP4, so the three land strictly in sequence. It also
  takes `NarrativePane.tsx` from the analysis plan's scope and `tableFormat.ts` from the table
  plan's, which is one more reason the siblings follow it.
- `export_service.py` (WP3, #1601, analysis). #1601 edits the summary export at lines 87–90 and
  187. WP3 edits the analysis PDF at 306–500. Disjoint, but both edit `test_export_service.py`.

**Order and merge points.** Each step ships something a subscriber can see, and none waits on an
unresolved conflict.

| Step | Lands | After | Visible result |
|---|---|---|---|
| 1 | **WP0** lineage backfill: high tier; the apply needs the founder's approval | #1583's deploy is verified (one unverified backend deploy at a time; its only shared file is `tasks/todo.md`) | Up to 77 of 82 latest-year "needs review" flags disappear in production. REGN's 11 if the dry run matches the local check |
| 2 | **WP1** quiet notation: routine tier, after the founder's decision (§2.9) | #1597 merges (it shares the design docs and the text-floor gate). The section-nav branch rebases on whichever lands first | No dagger on figures. A neutral letter only where a note questions the number. Data notes as fine print under the table |
| 3 | **WP2** data-notes words and **WP5** restatement note, one after the other (they share `data_notes.py` and its test) | WP1 (they share its notes files and its marking rule) | The fine print's words come from the backend, so the exports match. REGN's FY2018–FY2019 revenue gains a "restated in a later filing" letter, with both filings in the dialog |
| 4a | **charts plan**, then **WP3-png** (`chartExport.ts`) | WP1 | Chart marks only for notes in question; the PNG states its period range |
| 4b | **table plan**, then **WP3-xlsx** (`excel_export_service.py`) | WP1 | The sentence above the table. A letter in the workbook grid for figures in question |
| 4c | **#1601**, then the **analysis plan**, then **WP3-pdf** (`export_service.py`) | WP1, #1601 | Formatted company name and readable dates. Fine print on the table's page. No per-value dagger |
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
- **The variant test (§2.8) had two readers per design.** They were model instances, not
  subscribers, and they saw a static page with no hover and no dialog. Its restatement note was
  planted locally. Production carries none until WP5. Read it as directional. It is still the
  only test that put the four designs side by side on one data state.
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

### g. Notation variant test (added after the founder's review)

| Design | FCF $4.1B trust | Revenue flagged from the page | Clean | Trustworthy |
|---|---|---|---|---|
| Current | 3, 4 | both | 3, 3 | 3, 3 |
| Ring | 3, 3 | both | 3, 3 | 3, 4 |
| Quiet | 4, 4 | both | 4, 4 | 4, 4 |
| No marks | 4, 4 | neither | 4, 4 | 4, 4 |

The method, every verdict and the rules check are in
[verification/notation-variant-test.md](verification/notation-variant-test.md) and
[its JSON](verification/notation-variant-test.json). The four pages are in
[`screens/variants/`](screens/variants/).
