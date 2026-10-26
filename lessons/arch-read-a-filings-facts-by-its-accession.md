# Read a filing's facts at its company and accession, never by `filing_id`: it names the writer, not the filing

Date: 2026-10-26   Area: arch

**Context**: the filing page's annual chart (`GET /api/filings/{id}/fundamentals`) read
`financial_fact` rows with `filing_id == id`. The fact identity (company, concept, period end,
fiscal period, unit, accession) holds the accession, and both fact writers skip an identity already
stored. A companyfacts sync stores each period's winner under the accession of the filing that
reported it last, with no filing owner, so when a sync ran before a filing's own facts were written
the per-filing writer stored nothing for those cells: the newest 10-K got no rows at all (its chart
was empty) and an older one lost its oldest year and older balance. WP5b's own-report rows (a
year's value from its own report, kept beside a restated winner) hold an older report's own-year
cell the same way. Reproduced through both real writers in
`backend/tests/unit/test_filing_fundamentals_by_accession.py`. Reading those rows back needs care: its
review found that, unchecked, they also gave a 10-Q's page an "annual" chart (the sync labels the
prior year-end balance FY and stores it under the 10-Q's accession while the 10-Q filed it last),
an older 10-K a lone oldest-year bar for each line the per-filing writer read no current year of,
and an older 20-F a lone current-year USD bar for such a line (an early sync's convenience row).

**Rule**: select one filing's facts with `company_id == filing.company_id` and
`accession == filing.accession_number`, current or not; for its annual figures, call
`facts/filing_scope.annual_filing_rows` rather than restating its conditions. Treat `filing_id` as
ownership only (which writer stored a row: `is_(None)` / `isnot(None)`), never as a key to a
filing's figures, and name the onclause of any join between the fact table and `filings` (the key
SQLAlchemy infers is `filing_id`). The rows the per-filing writer stored (`filing_id` set) always
count. A row another writer stored under the accession counts only when every one of these holds:

1. the per-filing writer has run on the filing (`processed_facts_at` is set);
2. the row is not withheld: provenance `validation` of `unavailable` (a repair-retired row, or one
   the publication policy withholds) never counts;
3. it is a reported item, or a calculation with recorded operands, every one under the same
   accession (`fact_provenance.operands_within_accession`, which is true for a record with no
   operands, so check `inputs` too): a companyfacts calculation takes its first operand's accession,
   so its other operand may be a later filing's, and a legacy calculation with no operands proves
   nothing;
4. its line reaches the filing's own period end: some row of the line that counts (the filing's
   own, or one meeting 1-3), in the line's one currency, ends within `fiscal_naming.DRIFT_DAYS`
   days of `Filing.period_end_date`, counted in days, never calendar years (a year ending by
   September and its first quarter end in one calendar year). With no period end on record, no
   such row counts. Short of it, the rows another writer left there are only the cells the filing
   reported last (an older report's oldest year and older balance, an interim report's prior
   year-end balance), and a line of those alone reads as all it disclosed. `period_end_date` is
   EDGAR's submissions `reportDate`, which names the XBRL year end itself in nearly every annual
   report, 52/53-week calendars included (1,048 of 1,050 sampled from 99 filers). The 18 days absorb
   the odd one a day off (one of 63 in a sample of 52/53-week filers) and stay well inside the
   quarter that keeps a 10-Q's prior year-end out. The two misses of the first sample, Tractor
   Supply's 2014 and 2015 10-Ks, give the filing date, 53 days on: such a report keeps its own rows
   only, as before this reader.

Keep another company's rows out (a combined report shares one accession), keep each line in one
currency (the filing's own rows', else the one with the most period ends among the others, a
non-USD one on a tie, never the one present at the filing's own year: the native row for that year
sits under the later report that re-reported it, while an early sync's USD convenience row for it
stays), and show a row another writer stored under the year counted, back or forward, from the
latest period end the filing's own rows name (never from another such row's); it keeps its own
label when the filing owns no row to count from, or when no whole number of years lies between the
two (`fiscal_naming.years_back` gives none, as across a transition period): writer generations
name a year differently.

Two known shapes stand outside the rule. Reaching the period end does not make a line whole: once
WP5b's own-report rows land, an older report whose own year a later one restated holds that
own-report row beside its oldest year, while the middle year's winner sits under the later
report's accession, so for a line the per-filing writer read nothing of the chart shows the oldest
year and its own without the one between, side by side on the categorical axis. No writer on main
stores such a row yet; whoever lands the WP5b writer settles it, there or with a rule here. And a
40-F is never processed: the summary pipeline fetches XBRL for 10-K, 10-Q and 20-F only
(`summary_stages/enrichment.py`), so a 40-F's processed gate stays shut and its chart empty, as
before this reader; its test case holds for when one is.

**Evidence**: `backend/app/services/facts/filing_scope.py::annual_filing_rows` and `filing_years`,
read by `facts/fundamentals.get_filing_fundamentals`; the Copilot already scoped by accession
(`copilot_tools._scope`). Each condition is pinned on the bad case by
`backend/tests/unit/test_filing_fundamentals_by_accession.py`, condition 4's currency and its
distance in days included. Partly gated by
`backend/tests/unit/test_filing_facts_read_by_accession.py`, which counts every mention of
`FinancialFact.filing_id` through the model (the column, an ownership test, a lookup by name, a join
with no onclause to or from the model or `Filing` in its method, function or table form, a
relationship on or to the model) in `backend/app`, `backend/scripts`, `backend/evals` and the
top-level backend modules against a reviewed list; a comparison of a loaded row's `filing_id` or a
copied state's key, a name built at run time, a join whose tables are unpacked or reached through a
bound name or a call, and a new reader that restates the conditions above instead of calling
`filing_scope` are review-checked.
