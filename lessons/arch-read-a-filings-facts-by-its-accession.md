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
prior year-end balance FY and stores it under the 10-Q's accession while the 10-Q filed it last) and
an older 10-K a lone oldest-year bar for each line the per-filing writer read no current year of.

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
4. its line reaches the filing's own period end: some row of that concept, in the line's one
   currency, ends at `Filing.period_end_date`, within a 52/53-week calendar's drift
   (`fiscal_naming.DRIFT_DAYS`). With no period end on record, no such row counts. Short of it, the
   rows another writer left there are only the cells the filing reported last (an older report's
   oldest year and older balance, an interim report's prior year-end balance), and a line of those
   alone reads as all it disclosed.

Keep another company's rows out (a combined report shares one accession), keep each line in one
currency (the filing's own rows', else the reporting currency among the others), and show a row
another writer stored under the year counted, back or forward, from the latest period end the
filing's own rows name (never from another such row's), under its own label only when the filing
owns no row to count from: writer generations name a year differently.

**Evidence**: `backend/app/services/facts/filing_scope.py::annual_filing_rows` and `filing_years`,
read by `facts/fundamentals.get_filing_fundamentals`; the Copilot already scoped by accession
(`copilot_tools._scope`). Each condition is pinned on the bad case by
`backend/tests/unit/test_filing_fundamentals_by_accession.py`. Partly gated by
`backend/tests/unit/test_filing_facts_read_by_accession.py`, which counts every mention of
`FinancialFact.filing_id` through the model (the column, an ownership test, a lookup by name, a join
with no onclause to or from the model or `Filing`, a relationship on or to the model) in
`backend/app`, `backend/scripts`, `backend/evals` and the top-level backend modules against a
reviewed list; a comparison of a loaded row's `filing_id` or a copied state's key, a name built at
run time, and a new reader that restates the conditions above instead of calling `filing_scope` are
review-checked.
