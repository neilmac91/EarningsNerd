# Multi-Period Analysis: notation, data notes and cross-cutting coherence

2026-10-24 · base `a41c6e4` · scope: what †, "a" and "b" mean and how often they fire; one notation
system; the data notes; a heuristic evaluation and competitor teardown; the exports as files; the
order in which this work and the sibling plans (charts, analysis, table) should land.
Evidence lives beside this file: [`verification/`](verification/), [`screens/`](screens/),
[`exports/`](exports/), [`prototype/`](prototype/) and the [methods appendix](methods.md).
File and line citations are at the base `a41c6e4` unless they name another revision; #1606 and the
merges after it have moved many of them, so each work package re-pins its own before it edits.

**Revised the same day.** The first version recommended ringed review letters, "needs a source
check" on the KPI cards and a key beside every mark. The founder found that dramatic and
distrust-inducing. A blind test of four designs agreed, so the recommendation is now the quiet scheme in §2.
The ring design stays on record in [`prototype/notation-prototype.diff`](prototype/notation-prototype.diff)
and [`screens/variants/ring-light-full.png`](screens/variants/ring-light-full.png).

**Approved 2026-10-25.** The founder approved the quiet scheme and the narrowed rule ("approved,
narrow the rule") and asked for the plan to be implemented. The founder then confirmed the
revision the census brought (§1.6): a later filing's value for a year gets evidence, not a mark.
The competitor captures stay out of the repository, which is public (§4.3). D-061 in
`docs/brand/decisions-log.md` records all three. In the day since this report was written, the
sibling plans have landed:
- the table plan merged as `neilmac91/EarningsNerd#1606`;
- the charts plan merged steps 1–5 (`neilmac91/EarningsNerd#1602`, `#1603`, `#1607`, `#1609`,
  `#1617`) and step 6's gates (`#1620`, `#1624`, `#1631`). Step 6's remainder (E194) takes this
  report's rule for the notes band.

§2.6 reconciles with them, and §6 re-measures the order.

## 0. The answer first

1. **Fix the data before the design.** In production, "needs review" is on 16.9% of the newest
   annual figures. That is 82 of the 484 latest-year cells across the 27 companies that hold annual
   facts. Twenty-three of those 27 companies (85.2%) show it on a headline figure: revenue, net
   income, free cash flow, or operating or net margin. On the calculated metrics it is the norm:
   net margin 84.6%, free cash flow 78.9%, operating margin 77.8%. Of the 82 flags, 77 (94%)
   have the same cause, `legacy_calculation`: a calculated row written before lineage existed
   (#1191, 2026-10-10). No later write can add lineage to such a row, because ingestion skips an
   identity that already exists and the quarterly repair excludes filing-owned rows. A journaled
   lineage backfill (§1.5) gives each such row its record without changing a single value: a
   pass where its inputs agree, a specific concern where they don't. Its dry run measures how many
   it can reach, since inputs saved before 2026-09-13 lack the start dates the calculator needs.
   No presentation work can do that.
2. **The checks miss a real error that the flags cannot show.** REGN's FY2018 and FY2019 revenue
   come from the FY2020 10-K's re-tagged comparatives: $5,145.6M and $6,557.6M. The years' own
   10-Ks reported $6,710.8M and $7,863.4M. The page therefore shows FY2018 revenue growth of
   −12.4%, where the original filings give +14.3%, and an operating margin of 49.3% that is about
   37.8% on the original revenue. Both pass every automated check (§1.6). The trust signal is
   inverted: "a" sits on 11 correct figures while a figure that changed basis reads clean. A census
   of 59 companies found later filings change 5% of annual figures by more than 1%, mostly
   legitimate recasts. So the fix is evidence in the dialog and n/m growth across the change, with
   a mark only for a sign or scale disagreement (§1.6).
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
   - a later filing's value for a year goes unmarked too: both filings in the dialog, one line in
     the fine print, and n/m growth across the change of basis (§1.6);
   - the Data notes strip becomes one line of fine print under the table;
   - the exports follow the same rule.

   Under this scheme most companies already show no mark. 77 of production's 82 latest-year flags
   are legacy calculations. The other 5 cells are all `source_check_needed`, in 3 of the 27
   companies, so at most 3 keep a marked value in their newest year. That count leaves out growth
   figures inheriting an older year's note. The backfill then clears the legacy notes from the
   fine print and the dialog as well. A mark
   that does appear keeps its meaning.
4. **Data notes: one neutral line under the table, in plain words (§3).** The comprehension
   rounds settled the words, and they carry over: "Not in our data … shown as —, never as zero";
   "Calculated before 10 October 2026, when we began keeping each calculation's inputs".
   - **The comprehension test.** The reader of the current page put the $4.1B free cash flow at
     2/5 and had to guess what "a" meant.
   - **The blind test.** Readers of the current page put it at 3 and 4. Under the quiet scheme it
     carries no letter, and both readers put it at 4. Each reconciled it from the evidence on the
     page: operating cash flow minus capex.
5. **The page and the exports drift apart.**
   - An independent heuristic re-score of the current page found 24 problems, 7 of them severity 3
     (§4.2). The ring prototypes it also scored are superseded for the notation by §2.8.
   - The exports passed 44 of 70 file checks; 16 were partial and 10 failed (§5).
   - The PDF and workbook print the company in EDGAR capitals and raw ISO timestamps.
   - The PDF's key sits one page away from its table.
   - The workbook hides every review flag in a comment.
   - Neither chart PNG states its period range.
6. **Order (§6):**
   1. The lineage backfill. It shares no code file with any UI plan.
   2. The quiet notation, built on main now that the table plan (`neilmac91/EarningsNerd#1606`)
      has merged.
   3. The data-notes words, then the later-filing evidence (WP5, revised by measurement, §1.6;
      they share `data_notes.py`).
   4. The exports, split by file; the siblings they waited for (#1601, #1609) have merged.
   5. Surfaces and the results header, last.

   E206 in `tasks/todo.md` tracks them in this order. The proxy-statement fix the census found
   (§1.6) went first: it merged as #1622, and its repair of the rows stored before it, E211, is
   E206's first item.
7. **The founder's decision, taken 2026-10-25 (§2.9).** The 2026-10 redesign records the
   founder's rule "never hide a note". A P0 review enforced it for exactly the case the quiet
   scheme stops marking: a figure whose only note is `legacy_calculation`. The founder approved
   narrowing it to "every note stays in the evidence dialog and the data notes; only a note that
   questions the number keeps a mark beside the figure". The same day the founder confirmed the
   census's revision (§1.6): a later filing's value for a year gets evidence, not a mark, so REGN's
   FY2018 revenue, the blind test's payoff case, now carries none. D-061 in
   `docs/brand/decisions-log.md` records both. The change stays presentation-only:
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
2. Pass every row of the company in those accessions to `annotate_filing_calculations`, which
   matches inputs by `_scope` (company, accession, period end, fiscal year and period). An input
   can be owned by either writer, because the identity skip lets whichever ran first own it.
3. Convert each value to a float first. `FinancialFact.value` reads back as a `Decimal`, which the
   calculator's comparison does not accept, so every row would otherwise read as a mismatch.
4. Write `provenance` and `reconciled` only. Never write a value, a fiscal label or `is_latest`.

**The outcomes:**
- **Passes.** A row whose inputs are found and agree passes, as long as every input passes.
- **Inherits its input's state.** A row whose input needs review inherits that input's reasons,
  as today's writer does.
- **Written as a concern.** A row whose recomputed value disagrees is written as
  `calculation_mismatch`. That is a real inconsistency, which the quiet scheme marks.
- **Held unchanged and counted.** The backfill writes nothing for any of these:
  - a row whose inputs cannot be found (most often inputs saved before the per-filing writer kept
    their start dates, 2026-09-13);
  - a row whose input is withheld;
  - a row the old local check had flagged;
  - a row whose input is itself a legacy calculation.

  Writing `missing_calculation_inputs` for a row nobody doubts would put a new mark on a correct
  number.

**Expected effect.** Unknown until the dry run, which is the measurement.
- **REGN.** The local check (all 11 REGN cells reproduce to 1e-9) ran on rows the local ingest
  wrote through companyfacts. Production's rows are filing-owned, and their inputs may lack start
  dates. So REGN's 11 clear only if the dry run finds their inputs.
- **The 77 flags.** Of production's 82 latest-year review flags, 77 are `legacy_calculation`. Some
  of those are companyfacts-owned annual calculations, which belong to the quarterly repair, not
  to this backfill.
- **What the dry run reports.** Writes by outcome, holds by reason, and the newest-year figures
  cleared, marked and held, so the founder approves knowing which.

**Tier and gates.** High: `.github/workflows/ops.yml` and the approval hook's docstring. The
service (`backend/app/services/filing_lineage_repair.py`) sits outside `facts/`. A mutation-proven
test that a filing-owned legacy calculation gains lineage and nothing else moves.
The Ops wiring gate (`test_ops_workflow_wiring.py`) and the lock-timeout gate
(`test_migration_lock_safety.py`).

### 1.6 Upstream fix 2: a later filing's value replaces the year's own, and every check passes

The checks confirm that a reported value matches a filed XBRL fact (`reconciled`/`validation`).
They do not ask whether a later filing's comparative replaced what the year's own report said.
For REGN, `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` carries two values for each
of calendar 2018 and 2019:

| Year | Value in that year's own 10-K | Value a later 10-K gives | Value the dataset shows (`is_latest`, newest filing wins) |
|---|---:|---:|---:|
| 2018 | $6,710.8M (`0001532176-19-000009`) | $5,145.6M (FY2020 10-K, `0001804220-21-000008`) | $5,145.6M |
| 2019 | $7,863.4M (`0001532176-20-000008`) | $6,557.6M (FY2021 10-K, `0001804220-22-000007`) | $6,557.6M |

The later 10-Ks reuse the tag for a narrower figure: no us-gaap tag in them carries $6,710.8M, and
net income did not move. So the series joins two scopes. FY2017 and FY2020 onward use total
revenues; FY2018 and FY2019 use the narrower figure.
- **Growth.** FY2018 growth shows −12.4% where the filings as reported give +14.3%. FY2019 shows
  +27.4% where they give +17.2%.
- **Margins.** Every margin in those years is overstated: FY2018 operating margin shows 49.3%
  against about 37.8%.

A blind evaluator flagged this from memory (set Z, F6). It was then confirmed against SEC's XBRL
API ([verification](verification/heuristic-rescore-transcripts.md#set-z--prototype-round-2)).

**How often a later filing changes a year's value: measured.** The question was put to SEC's
companyfacts for 59 large filers, read through the app's own transport and grouped exactly as
ingest groups it. That gave 8,616 cells (company × concept × fiscal year, newest ten years). Its
output is [verification/restatement-census.md](verification/restatement-census.md), whose header
holds the run's time and every definition it used. The script, `backend/scripts/restatement_census.py`,
was written on a WP5 branch that was never pushed, and it went with its session, so this repository
cannot rerun it; WP5 commits a rerunnable census with its evidence (E206).
- **At a 1% tolerance,** a later filing's value differs from the year's own report in 438 cells
  (5.1%), at 52 of the 59 companies.
- **Noise.** Every rounding difference sits below 0.1%.
- **None of the 25 largest gaps is an error correction:**
  - 15 are retrospective accounting changes or discontinued-operations recasts (ASC 606, ASU
    2016-15/18, the insurance standard, spin-offs);
  - 4 are a stock split's basis;
  - 3 are reclassifications;
  - 3 are XBRL errors: one ×1000 scale in an own filing, and two exact sign flips in a later one.

  No 10-K/A ever replaced a value.
- **REGN** is a change of scope, not a restatement.

So "restated" is the wrong word, and a mark on every difference would mark about 4% of all
figures. Most of those carry the later filing's value, which is the comparable basis for the years
after it. That is the overkill this scheme exists to avoid.

**The change (WP5), revised by the measurement:**
1. **Keep the year's own value.** Ingest keeps each year's own-report value, within the winning
   tag, as a non-latest row (high tier: `facts/**`). Companyfacts stores only the winner today, so
   REGN's $6,710.8M exists nowhere in our data.
2. **Evidence on demand, with no mark.** The evidence dialog shows: "First reported as $6.7B in its
   own annual report (10-K, filed …); a later filing (filed …) reports $5.1B, shown here." The
   data notes' open detail carries one line with a count and the places, which also explains the
   n/m of item 3: "A later filing reports a different value for 2 figures (Revenue FY2018,
   FY2019); growth across the change reads n/m. Select one to see both filings."
3. **Growth across a change of basis reads n/m.** That is any comparison whose two years sit on
   different bases relative to what each year first reported (the ratio of shown to first-reported
   moves by more than 1%). The dialog gives the growth as first reported. For REGN, revenue growth
   FY2018–FY2020 reads n/m, with +14.3%, +17.2% and the rest in the dialog. A whole run recast on
   one basis keeps its numbers.
4. **A mark only where the two filings disagree in a way that signals a tagging error:** an exact
   sign flip, or an exact factor of 1,000ⁿ (4 of 8,616 cells in the census). The words say what
   was found: "A later filing reports this figure with the opposite sign" or "at 1,000 times the
   scale of the year's own report". Neither side is called correct.
5. **Calculated figures** whose input differs (REGN's FY2018–FY2019 margins) carry the same
   evidence in their dialog, not a mark.

What stays imperfect: the data cannot tell a change of scope like REGN's from a legitimate recast.
So REGN's FY2018 margin still shows 49.3% unmarked, with the explanation one tap away and the
broken growth reading n/m. A fix for the scope change itself belongs in concept selection
(`facts/concepts.py`), a separate decision tracked in E206 (`tasks/todo.md`).

**A separate data bug the census found.** Since 2023, proxy statements carry a pay-versus-performance
table that tags five years of net income, filed after the 10-K. Ingest takes the latest-filed item
of any form, so the proxy's value wins.
- **Size.** 120 cells across 24 of the 59 companies.
- **Where it differs.** At 12 companies the value differs from the 10-K's. FDX's August 2026 proxy
  tags its net income in plain dollars (3,826 for FY2022), and MRK's is 5.4% off for FY2021.
- **Nothing flags it.** Companyfacts rows skip the reconciliation checks.

The fix (ingest skips proxy and information statements, plus a read-only query that sizes the
production rows) went first, as it could put a wrong number on the page (FDX's FY2022–FY2026 net
income, 3,826 where the 10-K gives $3,826M): it merged as #1622 on 2026-10-25 (high tier), with
`ops/detection/proxy_form_winners.sql` to measure the rows production holds. The next sync heals
some of them; the journaled repair of the rest is E211, the first item in E206 (`tasks/todo.md`;
#1622's body says which rows a sync heals).

**Its first run** ([Ops run 40236489889](https://github.com/neilmac91/EarningsNerd/actions/runs/40236489889), main `15ee1e89`, 2026-10-25 21:39Z) found the cohort small, though not all
of it can be checked from the database:
- **Set 1.** 65 current rows that a proxy statement (DEF 14A) supplied, all `net_income`, at 9
  companies: BIIB, BMRN, CRM, FTNT, JPM, META, NVDA, RDDT and REGN. Of the 65, 35 are annual
  rows (FY2021–FY2026) and 30 are Q4 quarters derived from them.
- **The 12 with a report row behind them** (at BIIB, JPM and NVDA) are close: 8 differ from it,
  none by more than 1%, and the largest gap is JPM's, 0.1%.
- **The other 53 have none,** so the database cannot say how far they are from the 10-K. E211's
  dry run reads the 10-K's figure for them; the repair has to fetch it rather than promote a
  stored row.
- **Set 3.** 35 `net_margin` rows built on them, at 9 company and period keys across 6 companies.
- **Set 4.** None found: no filing row that the old cross-check replaced with a proxy's figure, of
  those the query can see. A replacement made before #1191 records no original, so only a stored
  proxy row witnesses it, and one with no witness is outside the query.

FDX, the case that found the defect, holds none of them.

**Owner.** Data, in two parts:
- the history rows in `facts/**` (high tier);
- the evidence, its line in the data notes, the n/m rule and the sign-or-scale mark in
  `trend_analysis/` (routine tier).

The mark's words and ink belong to this notation system (§2.2).

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
lands, and again after the backfill's apply, to confirm the drop. E206 (`tasks/todo.md`) holds
both runs.

**The first run** ([Ops run 40236489889](https://github.com/neilmac91/EarningsNerd/actions/runs/40236489889), main `15ee1e89`, 2026-10-25 21:39Z, before WP0's apply), over
31 companies and 6,939 cells in every fiscal year:
- **The review letter** marks 787 cells (11.3%), and 773 of them for `legacy_calculation` alone.
  The other 14 are `source_check_needed`. No cell is withheld.
- **It sits on the calculated metrics:** gross margin 62.7%, free cash flow 58.0%, net margin
  57.8%, operating margin 51.1%, working capital and current ratio 45.3% each. No reported metric
  is above 1.0%.
- **By owner,** filing-owned rows (19 companies, 1,073 cells) carry it at 23.7%, and companyfacts
  rows (22 companies, 5,866 cells) at 9.1%.
- **By year,** it stays at 9.4–11.8% from FY2008 to FY2022, then reads 13.9% in FY2023, 15.0% in
  FY2024, 13.9% in FY2025 and 16.4% in FY2026 (six companies). §1.2's 16.9% is another cut, each
  company's latest annual cells, so the two are not the same quantity.
- **Per company, in its newest ten years:** 9 of 31 show no review cell, 2 show 1–5, 6 show
  6–10, 7 show 11–20 and 7 more than 20.

**These are the notation as it ships today, not as D-061 draws it** (chief design on #1646).
Under D-061 (WP1) a `legacy_calculation` note is record-only and draws no letter. So of these
cells, a reader would see a letter on 14 (0.2%): the `source_check_needed` cells.
- They sit on reported figures only: EPS and diluted EPS 4 each, operating income and financing
  cash flow 2 each, cash and investing cash flow 1 each.
- They are at 5 of the 31 companies. Today 22 show a letter in their newest ten years alone.

The second run, after WP0's apply, measures the change against these figures. WP0 can turn a
legacy cell into one whose recomputation passes, or into one that disagrees, which D-061 marks. So
the review share can fall while the count readers see rises. That run reads two numbers:
- the review count less the record-only reasons (14 now);
- the legacy share (62.2% now).

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
  - a later filing and the year's own report disagree by sign or by a factor of 1,000ⁿ (WP5, §1.6),
    or the filings disagree (`source_conflict`);
  - a reported value could not be matched to the filed data (`source_check_needed`);
  - a calculation disagrees with its inputs, cannot find them, or combines inputs that do not fit
    together. Examples are `calculation_mismatch` and `missing_calculation_inputs` (the backfill's
    honest outcomes, §1.5), and `unit_mismatch` and `period_mismatch`.

  A note about the record rather than the value gets no mark. Today that is `legacy_calculation`
  alone: 77 of production's 82 latest-year review flags, and all 11 REGN cells reproduce exactly
  from their inputs. A gap shows "—" and needs no letter. A missing validation record makes no
  claim either way. The list of record-only reasons is closed. Any other reason marks the figure, so
  a new reason fails loud, not silent. WP5's later-filing note (§1.6) joins the unmarked list: it
  shows the comparable basis, not a doubtful value.
- **Calculation is routine, so it goes unmarked.** One sentence above the table names the
  calculated metrics. Each figure's evidence dialog states the method and inputs. Its accessible
  name keeps "calculated", so a screen reader still hears what the dagger used to say.
- **Small and neutral.** The letter is raised and set at the 11px data-xs size in the `note` ink
  (§2.3). It never scales with the figure, and it has no ring and no warning ink. A mark that
  appears rarely does not need to shout, and both quiet-design readers found it (§2.8).
- **Filtered, never reclassified.** The scheme decides only which notes put a mark beside a
  figure.
  - Note kinds, reasons and totals stay as the backend computes them.
  - The fine print names and counts every note, legacy included. The dialog names each figure's
    own note.
  - The page never says "No figures need review" while a legacy note exists.
  - The page never calls a legacy figure validated.
- **One rule on every surface.** The page, PDF, workbook and chart PNG mark the same notes. One
  reason list decides, held by `data_notes.py` and `lib/dataNotes.ts`, and the shared notes fixture
  (`backend/tests/fixtures/analysis_data_notes.json`) pins the two copies equal.

### 2.2 What each note shows, and where

| Note | On the figure | In the fine print under the table | In the evidence dialog |
|---|---|---|---|
| Questions the number (a sign or scale disagreement between filings, filings disagree, unmatched, calculation mismatch) | A neutral raised letter. The growth figures built on it carry the same letter, as now | The letter, its places and one sentence, in the summary line | The note in full. For a disagreement between filings: both values, both filings and their dates |
| A later filing reports a different value for the year (WP5, §1.6; REGN's FY2018–FY2019 revenue) | nothing. Growth across the change of basis reads n/m. Figures calculated from it (REGN's FY2018–FY2019 margins) stay unmarked | One line in the open detail, with a count and places, which also explains the n/m: "A later filing reports a different value for 2 figures (Revenue FY2018, FY2019); growth across the change reads n/m. Select one to see both filings." | Both values, both filings and their dates, and the growth as first reported. A figure calculated from it shows the same evidence |
| Calculated, inputs linked | nothing | Named in the sentence above the table | Method, formula, linked inputs |
| Calculated before lineage existed (`legacy_calculation`) | nothing | One sentence, its places and its counts (figures, and the growth built on them), in the open detail | "Calculated before 10 October 2026 …; shown as stored, inputs not linked" |
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
    textColor: "{colors.note-light}"
    typography: "{typography.data-xs}"
  figure-note-mark-dark:
    textColor: "{colors.note-dark}"
  data-notes-fine-print:
    textColor: "{colors.text-secondary-light}"
  data-notes-fine-print-dark:
    textColor: "{colors.text-secondary-dark}"
```

The mark's ink is the `note` token that the table plan (`neilmac91/EarningsNerd#1606`) adds for
neutral marks on the figure surfaces: #636A77 light (Lc 75.4) and #D1D5DB dark (−80.3). It keeps
#1606's mark type: 11px figure face, zero line-height, its gutter in the table. Only the
dagger, the staircase step and the warning ink go.

The change mostly removes rules. The dagger's sizing goes, the warning-ink letters go, and the
strip's place under the KPI cards goes.
- **Legibility.** The fine print's `text-secondary-light` (#374151) and `text-secondary-dark`
  both clear 4.5:1. #1606 raises the dark value from #9CA3AF to #D1D5DB.
  `text-floors.spec.ts` re-checks the fine print.
- **Type.** The fine print is 12px running copy (`text-xs`), not `data-xs`, so the exact caps in
  `dataXsAllowlist.spec.ts` don't move.
- **Same-PR refresh.** `DESIGN.md`'s Calculation Provenance Rule, `.impeccable/design.json`
  (`designSnapshotParity.spec.ts`) and `DESIGN_SYSTEM.md` are refreshed in the same PR (§2.9).
- **The rule-12 gate.** A unit spec over the shared notes fixture: every questioning reason renders
  a mark on the page, the PDF and the PNG, and every record-only reason renders none. A mutation
  that flips either direction fails it.

### 2.4 The key

There is almost nothing to key, so there is no key beside every mark:
- **Above the table**, one sentence replaces the "† calculated" label. It is built from the
  calculated metrics the run actually shows, so a run without working capital does not name it.
  For REGN: "Figures are rounded for display; margins, free cash flow, working capital and the
  current ratio are calculated from filed figures. Select any value for its source and full
  precision."
- **Notes chips.** The table's chip lists only the visible marked letters and opens the fine print
  at that note. Each chart's chip does the same. A hollow point appears only where a note is
  marked, and the chart's chip explains it ("Notes a · hollow point: figure carries note a"). The
  PNG footer carries the same line.
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
| PDF | No dagger after each value (`export_service.py:349`). As on the page, the calculated sentence sits above the table and the fine print under it, on the same page. Letters for marked notes only, with the page's reason sentences. |
| Excel | Every note stays as a cell comment, which is the workbook's evidence dialog. A marked note also shows its letter in the grid through the number format (`#,##0" a"`), so the cell stays numeric. No warning-ink fonts. The fine print goes on the Metrics header row. |
| Chart PNG | The period range in the subtitle ("REGN · Margins · FY2016–FY2025"). The footer names marked letters only. |

### 2.6 Reconciling with the sibling plans

This report owns notation semantics: which notes mark a figure, the words, the glyph, size and ink,
and the vocabulary. The sibling plans own their surfaces' geometry. On 2026-10-25 both siblings
exist in code.

**The table plan, `neilmac91/EarningsNerd#1606`** (merged 2026-10-25, `99fda0f6`). Its number
system makes every mark one footnote type: 11px figure face and zero line-height, in its own ink,
hung in a one-mark gutter in the table. It also adds the `note` ink and raises dark secondary text
to #D1D5DB. It keeps the dagger, set as a staircase below the letter, and review letters in
`warning.data-dark`. The quiet scheme keeps #1606's type, gutter and ink. It removes:
- the dagger from figures, and with it the staircase step;
- the warning ink from letters, so a marked letter takes `note`.

WP1 builds on main, where #1606 landed; they share 21 files (§6).

**The charts plan.**
- **Merged:** steps 1–3, the spec engine and the PNG's font (`neilmac91/EarningsNerd#1602`); today's
  charts on the engine's axes (`#1603`); labelled charts that widen (`#1607`). Then, on
  2026-10-25: step 4, the spec renderer behind `NEXT_PUBLIC_CHARTS_V2` (`#1609`, `0009fb90`), and
  its records (`#1611`); step 5, reading a chart (E193, `#1617`); step 6's gates (E194: `#1620`,
  `#1624`, `#1631`); the data face's fallback and the plots' font wait (E199, `#1636`).
- **Open:** step 7 (E195), after the founder's switch (F66). Step 6's remainder, the notes band
  on this report's rule (below), landed with E194 on 2026-10-26.
- **The spec.** `docs/design/analysis-trend-charts-spec-2026-10.md` §3.3 (A5) takes note marks off
  the plot and puts them in a band under the period axis: a letter for every note on a plotted
  value (unavailable notes included, so "every missing point has a letter"), † for a partly
  calculated series, and review letters in review ink. Its A5 (§3.3) and D9 now carry dated
  pointer lines to this section (2026-10-25, D-061).

Under the approved scheme the band follows the marking rule:
- A cell shows only the letters of notes that question the number, in the mark's neutral ink.
- No † glyph. The spec's own footnote lines 2 and 3 already say in words which series are
  calculated, which is the sentence the quiet scheme uses.
- A missing value is the gap the spec already draws, with its chart-specific sentence (for
  example "Long-term debt isn't in this dataset for this window (not shown as $0)"). It gets no
  letter.
- Footnote line 1 lists only the marked letters. The fine print under the table carries every
  note, as everywhere else.

The rule lives in one helper (§2.1), which WP1 adds to `lib/dataNotes.ts`. The band can call it,
so the renderer needs no copy of the rule. E194 built the band on it (2026-10-26).

**The analysis plan.** It has no PR. Its chips mark through the same helper.

A sibling change that marks routine figures, recolours a mark or brings back a strip of counts is
resolved in favour of §2, unless it brings blind-test evidence as strong as §2.8's.

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
  - Between the runs, the quiet copy also changed, in answer to the first-run quiet readers:
    - "the company's filings disagree" became "restated in a later filing; we show the later
      value";
    - the legacy count left the summary line;
    - the restatement sentence in the closed detail was reworded, which the readers could not
      see.
  - R2 is therefore not copy-controlled against R. Both first-run quiet readers had already found
    the revenue from the page with the older words.

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
4. **What the quiet design still lacks goes to WP5** (revised after the census, §1.6: dialog evidence
   and n/m growth for a later filing's value, a mark only for a sign or scale disagreement).
   - One of the two quiet readers found the restatement note "worded like a routine housekeeping
     footnote".
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

**Approved by the founder on 2026-10-25.** The founder's "never hide a note" is recorded in
`tasks/analysis-redesign-2026-10/astra-prompt.md:74` and `review-2026-10-10.md:36`. A P0 review
enforced it for exactly the case the scheme stops marking: a `legacy_calculation` figure.
- **The decision.** The founder approved narrowing it to "every note stays in the evidence dialog
  and the data notes; only a note that questions the number keeps a mark beside the figure"
  ("approved, narrow the rule"). It is recorded as D-061 in `docs/brand/decisions-log.md` (this
  PR). WP1 points both task files (`tasks/analysis-redesign-2026-10/astra-prompt.md:74`,
  `review-2026-10-10.md:36`) at it.
- **Confirmed the same day.** The founder confirmed the census's revision (§1.6): a later filing's
  value for a year gets evidence, not a mark. REGN's FY2018 revenue, the blind test's payoff case
  (§2.8), now carries no mark: its growth across the change of basis reads n/m, its evidence dialog
  shows both filings, and a line in the data notes counts it. The FY2018–FY2019 margins stay
  unmarked, with the evidence in their dialogs. D-061 records it, with the founder's call to keep
  the competitor captures out of this public repository (§9.f).
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
| Token and mark (#1606's, on main at `0dfee8cc`) | `frontend/tailwind.config.js:134` (`warning.data-dark`); `DataNoteMark.tsx:26-32` (the staircase comment and the dagger's offset) | Retire both once no letter takes warning ink and no figure carries a dagger. Only `DataNoteMark.tsx` reads the token. It is pinned by `figureSurfaceInks.spec.ts:35` and `:108` and `data-note-mark.spec.tsx:39`, and named in `DESIGN.md:59`, `:375` and `:383`, `.impeccable/design.json:331` and `frontend/DESIGN_SYSTEM.md:28`, `:601` and `:2390`. No other code uses the staircase. Beside the Rule and recipes above, `DESIGN.md:416` (the Footnote mark type), `data-note-mark.spec.tsx:24` and `analysis-layout.spec.ts:918` describe it. The letter keeps its raise. |
| Lesson | `lessons/arch-reconciliation-follows-values-and-growth.md:20` | "Keep a mark at each affected figure" becomes "at each figure whose note questions the number; every note in the dialog, the data notes and the exports". The process lesson from this correction is already in this branch: `lessons/brand-test-a-trust-mark-blind-against-quieter-and-none.md`. |
| Design record | `docs/design/analysis-data-notes-redesign-2026-10.md` §1, §4.2, §4.3, §4.10 | A dated supersession note. Its §9 decisions stay in force. |
| In-product copy | `NarrativePane.tsx:121`, `DataNotes.tsx:103` | Both promise a † that no longer appears (§2.5). |
| Landing | `AnalysisDemo.tsx:45`, `AnalysisTeaser.tsx:41` | Move the notes below the table, as on the page. |
| Unit specs | the six files in §2.7, plus `analysis-table-format.spec.ts:41` (the dagger's glyph is freed under decision 6) | Re-pin as §2.7 says. |
| Browser gate | `tests/e2e/analysis-layout.spec.ts` and `fixtures/analysisLayoutApi.ts` | Dagger counts, legacy and unavailable letters, the chip's name and the summary text. Keep the discrepancy state's letters as proof. |

**With the exports (WP3).** These pins move with the exports:
- `test_export_service.py:648` and `:675`: the PDF's dagger.
- `:677`: its gap letter.
- `:761`: its single Data notes heading.
- `:813`: the count line of the PDF and the workbook's Overview.
- `test_export_voice.py:188`: the heading order.
- `frontend/tests/unit/chart-export.spec.ts:67-98`: the PNG's note for a legacy YoY.

The workbook already keeps notes in comments (`test_excel_export.py:218`).

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

**Outcome.** The current-page reader put trust at 2/5 and had to guess at "a". They called the note
jargon and found the two superscripts easy to confuse
([transcript](verification/comprehension-transcripts.md#current-design-production-as-of-2026-10-24)).

### 3.2 The design

The first design put a plain-words summary, a "where" line and the key in a strip under the KPI
cards. After the founder's review and the blind test (§2.8), the data notes become fine print under
the metrics table: neutral ink, 12px, one line while closed, and the detail one click away.

```
▸ Data notes · 3 not in our data, shown as — · 50 calculated from filed figures

  A later filing reports a different value for 2 figures (Revenue FY2018, FY2019); growth across the change reads n/m.
     Select one to see both filings.
  Calculated before 10 October 2026, when we began keeping each calculation's inputs; shown as stored, with its inputs
     not linked. Operating margin FY2023, FY2024, FY2025; Net margin FY2023, FY2024, FY2025; Free cash flow FY2023,
     FY2024, FY2025; Working capital FY2024; Current ratio FY2024. 11 figures; 16 growth figures built on them.¹
  Not in our data for these periods; shown as —, never as zero. Long-term debt FY2016, FY2017, FY2018.
  Select any figure to see its source filing, method and inputs. Automated checks confirm that reported figures come
     from the company's filed data (XBRL); they are not an audit of the company's accounts.
```

¹ The prototype's detail has no counts, as the screens below show. This design adds them, because
the fine print must keep counting legacy notes (§2.1).

This is REGN under the confirmed scheme (D-061): no note questions a number, so the summary line
names no letter. The screens below show the blind test's planted version instead: a marked "a" on
the same two figures ("restated in a later filing; we show the later value"). After the census,
WP5 marks only a sign or scale disagreement (§1.6).

The screens are [`quiet-light-datanotes-closed.png`](screens/variants/quiet-light-datanotes-closed.png),
[`quiet-light-datanotes-open.png`](screens/variants/quiet-light-datanotes-open.png),
[`quiet-dark-datanotes-open.png`](screens/variants/quiet-dark-datanotes-open.png) and the full
page, [`quiet-light-full.png`](screens/variants/quiet-light-full.png). The ring design's strip
is in [`screens/`](screens/) as `final-*`.

- **The summary line.** It names each marked note with its places and words. It counts the gaps,
  any figures with no check recorded, and the calculated figures. Nothing is in warning ink.
  - With no marked note it reads "Data notes · 3 not in our data, shown as — · 50 calculated from
    filed figures".
  - When every populated figure passed and no note exists, it keeps "No figures need review" with
    the checked count (founder decision 9). It never says that while a legacy note exists.
- **Legacy notes** appear only in the detail. Their sentence says the record is incomplete, not
  the figure.
- **A later filing's value** appears only in the detail too: one line with a count and the places,
  which also explains the n/m growth beside them (§1.6).
- **Comparison locators move off the page.** "13 year-over-year comparisons carry this note. The
  table shows 13. Exports carry all 13." describes plumbing. The letter on each growth figure
  locates the comparison.
- **Chips.** The native `<details>` stays, so a Notes chip can open the fine print at its note.
- **The landing sample** keeps its "sample data (one saved run)" label in the fine print (D-046).
- **Where the copy lives.** WP2 writes the new words into both copies of the reason map:
  - `data_notes.REASONS` on the backend reaches the page, PDF, workbook and PNG through the notes
    envelope's `message`.
  - `REASONS` in `frontend/features/analysis/lib/provenance.ts:41` serves local grouping without an
    envelope, the per-figure fallback in `SourceValue` and the fundamentals badges.

  The shared fixture `backend/tests/fixtures/analysis_data_notes.json` pins the two copies equal.
  The prototype maps reasons on the frontend only.

### 3.3 Wording

| Place | Today | Proposed |
|---|---|---|
| Summary, a note that questions the number | "11 figures need review (a)" (every review note in one count) | "ᵃ {places}: {words}": the letter, its places and its words, no count. The blind test's planted "ᵃ Revenue FY2018, FY2019: restated in a later filing; we show the later value" is unmarked under WP5 (the WP5 rows below) |
| Summary, legacy calculations | inside the same count | detail only |
| Summary, gaps | "3 unavailable (b)" | "3 not in our data, shown as —" |
| Summary, no validation record | "N figures have no validation record (c)" (`DataNotes.tsx:94`) | "N with no check recorded" |
| Summary, calculated | "50 calculated †" | "50 calculated from filed figures" |
| `legacy_calculation` | "This saved calculation predates the current source checks. Its inputs need review." | "Calculated before 10 October 2026, when we began keeping each calculation's inputs; shown as stored, with its inputs not linked." |
| WP5, a later filing changes the value: the dialog (no mark) | (none: the figure reads clean) | "First reported as {value} in its own annual report ({form}, filed {date}). A later filing (filed {date}) reports {value}, shown here." |
| WP5, a later filing changes the value: the fine print's detail | (none) | "A later filing reports a different value for {n} figures ({places}); growth across the change reads n/m. Select one to see both filings." |
| WP5, a sign or scale disagreement (marked) | (none) | "A later filing reports this figure with the opposite sign" / "at 1,000 times the scale of the year's own annual report. One of them is likely a tagging error; select it to see both filings." |
| `source_conflict` (filings disagree, no later restatement) | "Available sources disagree on this figure." | "The company's filings report different values for this figure. We show the most recent filing's value; select it to compare." |
| `source_check_needed` | "A source check remains unresolved. Review the original filing before use." | "Not yet matched to the filing: our automated check could not confirm this figure against the company's filed data. Select it to compare with the filing." |
| `not_in_dataset` | "Not available in this dataset." | "Not in our data for these periods; shown as —, never as zero." |
| Legend | "Letters identify data notes; † marks a calculated figure, not an error." | "Select any figure to see its source filing, method and inputs. Automated checks confirm that reported figures come from the company's filed data (XBRL); they are not an audit of the company's accounts." |
| Above the table | "Figures are rounded for display. Select a value for full precision." | It names the calculated metrics the run shows (§2.4). For REGN: "Figures are rounded for display; margins, free cash flow, working capital and the current ratio are calculated from filed figures. Select any value for its source and full precision." |
| KPI card | "$4.1B†ᵃ" | "$4.1B": a letter only for a note that questions the figure |

Each sentence promises only what the code enforces:
- "10 October 2026" is #1191's merge date.
- "Not in our data" makes no claim about whether the company reported the figure.
- The later-filing words name what the data shows, that a later filing reports a different value,
  never a restatement. The census found almost none of the differences were error corrections. A plain disagreement keeps the `source_conflict` sentence. Of the first-run quiet readers,
  one found "the company's filings disagree" alarming and both found it unresolved, so that
  sentence names what is shown and how to compare.

**As shipped (WP2, #1659).** A reason's words print on every surface: the page's detail, the
dialog, the PDF, the workbook and the chart PNG. They are read for one figure (the dialog, a
workbook cell's comment) and once for all of a note's figures (the detail, the PDF's and the
workbook's lists, the chart footnotes). The proposed sentences changed for that:
- `not_in_dataset` reads "Not in our data; never shown as zero." The table, the PDF and the bar
  charts print a gap as the dash, a line chart breaks its line and the workbook leaves the cell
  empty, so "shown as —" stays in the page's summary line ("3 not in our data, shown as —"),
  drawn beside the table's own dash. The voice rule also keeps "—" out of a sentence.
- `source_conflict` and `source_check_needed` stop before "select it to compare": nothing can be
  selected in an export. On the page, the detail's closing line ("Select any figure to see its
  source filing, method and inputs") and the dialog give the way to compare.
- No reason's words point at one figure. "Different values for this figure" printed above three
  places in the open detail (chief design's review of #1659), so `source_conflict` reads "The
  company's filings report different values. We show the most recent filing's value." and every
  other sentence says "the" or names nothing: "Zero where the previous period had a value."
- `source_conflict`'s summary clause reads "the filings report different values (the most recent
  shown)": the summary lists places with "; ", so a clause's own semicolon split the line where
  the places did.

`backend/tests/unit/test_analysis_data_notes.py` fails a reason's words that ask for a page action,
say how a figure is drawn or point at one figure ("this", "these"), and a summary clause with a
semicolon. WP5's "select it to see both filings" therefore belongs to the page, not to a reason's
sentence.

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

- **One reader took the restatement note for housekeeping** (§2.8, R2 retail). The census (§1.6)
  then showed most later-filing differences are legitimate recasts, so WP5 marks only sign and
  scale disagreements. Every other difference shows both values and both filings, with their
  dates, in the dialog; one line in the fine print's detail counts and places them; and growth
  across the change of basis reads n/m. The founder confirmed this on 2026-10-25 (D-061).
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

Three paid products' equivalent views were captured with Playwright for REGN (§9.f). Alpha Spread
is a supplement: its AI financial profile, before its bot check closed the door.

| Product (paid tier) | View | Surfaces and elevation | How figure states are marked | Worth taking |
|---|---|---|---|---|
| Roic.ai | Financials: 15 fiscal years, chart over statement (light and dark) | One flat white surface, one bordered statement panel, hairline rows, no card stack | None: no calculated or quality marks; negatives in red | Colour swatches on table rows tie each row to its chart series; an "As of date" row of period ends under the year header; $ /sh % YoY unit toggles |
| Yahoo Finance (Finance Plus) | Financials › Income Statement (chart and statement, light); no dark theme signed out | One surface; the table is the page; rows carry checkboxes that add them to the chart | Padlocks mark paid ranges (10Y, 20Y, ALL, Download); no quality marks | Unit control (Auto/K/MM/B), an order toggle, row-to-chart selection, a TTM column |
| Finviz (Elite) | Statements on the quote page (light and dark) | Zebra rows on one panel; the upgrade panel covers locked years | A padlock with words for locked years; no quality marks | A per-row sparkline beside each metric; "Period End Date" and "Period Length" rows; Data / YoY / YoY % toggles |
| Alpha Spread (supplement) | AI financial profile (light) | A narrative band above the fold | "Sources:" link at the foot of the AI text, not per figure | Narrative-level sourcing is the floor; EarningsNerd's per-figure citations go further |

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

The table plan's surface landed with #1606 (§2.6): the figures on a sheet inside the panel card.
This follows DESIGN.md's Lifted Paper Rule and its existing tokens, and it leaves the table's
interior to that plan.

| Level | Token | Holds | Change from today |
|---|---|---|---|
| Ground | `background` | The page title, the **results header** (new: "Regeneron Pharmaceuticals, Inc. · REGN · Annual FY2016–FY2025 · data as of 24 Oct 2026"), the disclaimer | The results header is new. Data notes move from under the KPI cards to fine print on the ground, directly under the metrics table card (§3.2) |
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

**Under the quiet scheme (§2.5) the exports follow the page.**
- **Settled.** The 52 DejaVu daggers go with the per-value dagger.
- **Partly settled.** In the workbook, a figure in question gets a visible letter in the grid, and
  the comment triangle stays the evidence for every note. A legacy cell keeps its comment only,
  as it carries no mark on the page.

The PDF's key-on-another-page miss becomes fine print under the table, on the same page.

Theme behaviour is consistent but undocumented. The PDF and workbook are always light; the PNG
follows the page. Keep that, and say so in the export menu ("Image matches your theme").

## 6. Sequencing by measured overlap

Re-measured on 2026-10-25. Each open branch is measured with `git diff --name-only` against its
merge base. Each work package lists the files it edits.
- **Measured:** the table plan (#1606) and the charts plan's step 4 (#1609).
- **Scopes:** the charts plan's later steps and the analysis plan have no branch, so their rows
  stay scopes.
- **Dropped:** #1597, #1600, #1602, #1603 and #1607 have merged, and the section-nav branch is gone.
- **Now merged:** #1609 (`0009fb90`, 08:13 UTC), #1601, #1608 and #1606 (`99fda0f6`, 16:22 UTC);
  only #1583 is open. The matrix keeps the measurement as taken: a count against a merged PR now
  names files a work package edits on main, not a branch to wait for. The charts plan's steps 5
  and 6 have merged in part too (E193 `#1617`; E194's gates `#1620`, `#1624`, `#1631`), so its
  scope row stands for step 6's remainder (E194) and step 7 (E195).

The computation is in the [methods appendix](methods.md).

| | WP0 | WP1 | WP2 | WP3 | WP4 | WP5 | charts | analysis | #1606 | #1609 | #1601 | #1583 | #1608 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **WP0 lineage backfill** (10) | — | · | · | · | · | · | · | · | · | 1 | 1 | 1 | 2 |
| **WP1 quiet notation** (29) | · | — | 4 | · | 6 | 2 | 3 | 2 | 21 | 3 | · | · | · |
| **WP2 data-notes words** (10) | · | 4 | — | 1 | · | 3 | · | · | 3 | 1 | · | · | · |
| **WP3 exports** (9) | · | · | 1 | — | · | · | 2 | 1 | 1 | 1 | 3 | · | · |
| **WP4 surfaces + results header** (8) | · | 6 | · | · | — | · | 1 | · | 5 | 1 | · | · | · |
| **WP5 restatement note** (7) | · | 2 | 3 | · | · | — | · | · | 2 | · | · | · | · |
| **charts steps 5-7 (scope)** (8) | · | 3 | · | 2 | 1 | · | — | · | 3 | 5 | · | · | · |
| **analysis plan (scope)** (7) | · | 2 | · | 1 | · | · | · | — | 2 | · | 1 | · | · |
| **#1606 table plan** (125) | · | 21 | 3 | 1 | 5 | 2 | 3 | 2 | — | 5 | · | 1 | · |
| **#1609 charts renderer** (26) | 1 | 3 | 1 | 1 | 1 | · | 5 | · | 5 | — | 1 | 1 | 2 |
| **#1601 export-source** (12) | 1 | · | · | 3 | · | · | · | 1 | · | 1 | — | 1 | 1 |
| **#1583 per-filing-currency** (11) | 1 | · | · | · | · | · | · | · | 1 | 1 | 1 | — | 2 |
| **#1608 admin units** (12) | 2 | · | · | · | · | · | · | · | · | 2 | 1 | 2 | — |

Every shared file by pair is listed under the matrix in
[verification/file-overlap.md](verification/file-overlap.md). Four points are worth naming:
- **WP1 and the table plan share 21 files.** These include the mark, the table, the KPI strip, the
  data notes, the narrative, the landing demo, the design docs and the browser gate. #1606 merged
  on 2026-10-25, so WP1 builds on main, on those files as #1606 left them.
- **WP1, WP2 and WP4 land strictly in sequence.** WP1 shares four files with WP2 and six with
  WP4.
- **`chartExport.ts` is shared by WP3, #1606 and #1609.** Both have merged, so WP3's PNG part
  builds on main.
- **`export_service.py` is shared by WP3, #1601 and the analysis plan.** #1601 edits the summary
  export, and WP3 edits the analysis PDF, so their lines are disjoint. Both edit
  `test_export_service.py` and `test_export_voice.py`. #1601 has merged, so WP3's PDF part builds
  on main.

**Order and merge points.** Each step ships something a subscriber can see, and none waits on an
unresolved conflict.

| Step | Lands | After | Visible result |
|---|---|---|---|
| 1 | **WP0** lineage backfill: high tier; the apply needs the founder's approval | One unverified backend deploy at a time. Its only file shared with open work is `tasks/todo.md` (#1608, which also edited `test_migration_lock_safety.py`, has merged) | The legacy notes the dry run can reach leave the fine print and the dialogs, as passes or as specific concerns. The dry run counts them, and the holds, before the founder approves the apply |
| 2 | **WP1** quiet notation: routine tier | Nothing open: it builds on main, where #1606 merged | No dagger on figures. A neutral letter only where a note questions the number. Data notes as fine print under the table |
| 3 | **WP2** data-notes words and **WP5** later-filing evidence, one after the other (they share `data_notes.py` and its test) | WP1 (they share its notes files and its marking rule) | The fine print's words come from the backend, so the exports match. REGN's FY2018–FY2019 revenue shows both filings in its dialog, its growth across the change reads n/m, and one line in the fine print's detail counts and places it |
| 4a | **WP3-png** (`chartExport.ts`) | #1609 (merged) | Chart marks only for notes in question; the PNG states its period range |
| 4b | **WP3-xlsx** (`excel_export_service.py`) | WP1 | A letter in the workbook grid for figures in question |
| 4c | **WP3-pdf** (`export_service.py`) | WP1 (#1601 has merged) | Formatted company name and readable dates. Fine print on the table's page. No per-value dagger |
| 5 | **WP4** surfaces and results header | WP1 (it moves the KPI strip, under the heading rail #1606 landed) | Results header, quieter control card, the Feedback launcher clear of the KPIs |

4a, 4b and 4c can run in parallel. Step 1 shares no file with steps 2–5 except `tasks/todo.md`,
so it can start today.

**Tracking.** One row, E206 in `tasks/todo.md`, holds this report's work in order. The
proxy-statement fix went first and merged as #1622; what it left leads the row:
1. E211, the journaled repair of the proxy rows stored before #1622 (§1.6, high tier);
2. WP0–WP5 in the order above (WP5 also commits a rerunnable restatement census);
3. the concept-selection decision for REGN's change of scope (§1.6);
4. the `detection-sql` runs before and after the backfill's apply (§1.7).

## 7. Findings for the other plans

These came out of this evaluation but sit in the sibling areas.

- **Charts:**
  - Fixed on main by #1603 (`a7d4ea2a`): cash generation has one axis, so FY2025 FCF ($4.1B) no
    longer plots above net income ($4.5B) (Y-F6, Z-F7), and every value axis takes the engine's
    round ticks, with "$0" at zero. The balance sheet keeps equity's right axis on today's charts;
    the spec renderer draws equity as its own panel.
  - Still open on today's charts: year ticks run together on phones. The spec renderer (#1609,
    merged) replaces them; production waits on the founder's switch (F66).
- **Analysis:**
  - Red flags and "What to watch" assert conclusions from flagged figures with no caveat (X-F12,
    Y-F2).
  - "Compressed 5.9pp" beside 30.9% → 24.9%, a rounding artefact (Y-F19).
  - Raw machine precision in the source list.
  - Templated repetition.
  - "Calculated figure" against "Calculated from recorded inputs": the words are settled in §2.5.
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

### b. Independent heuristic re-scores (X the current page; Y and Z the ring prototypes, superseded for the notation by §2.8)

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

The captures behind §4.3 (Roic.ai, Yahoo Finance, Finviz and Alpha Spread, signed out, with
Playwright on 2026-10-24) were taken for the teardown and are not committed, since the repository
is public (founder, 2026-10-25; D-061). The scripts are in the
[methods appendix](methods.md#competitor-captures).

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
