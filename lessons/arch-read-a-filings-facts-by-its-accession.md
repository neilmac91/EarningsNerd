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
and a 20-F, older or newest, a lone current-year USD bar beside its CNY lines for such a line: an
early sync's convenience row, or the current sync's at a filer that switched reporting currency
(Hello Group, Vipshop, JOYY), whose USD list `currency.series_unit` keeps. Condition 4 closes that
wherever the writer stored an annual row of the report; a report it stored no annual row of keeps
the bar (below). Once the WP5b writer stored own-report rows, an older report's line the writer read
nothing of reached its period end through one and charted its oldest year beside its own, the year
between missing (REGN's FY2018 and FY2019 10-Ks); condition 6 closes that. Its first form counted
any two rows more than a year apart as a missing year, so a fiscal-year change's transition period or a
fresh-start split year dropped every stand-in of a line, and the newest report after the change, synced
first and owning no row, lost its flow lines: it now counts only a year another of the company's rows
holds.

**Rule**: select one filing's facts with `company_id == filing.company_id` and
`accession == filing.accession_number`, current or not; for its annual figures, call
`facts/filing_scope.annual_filing_rows` rather than restating its conditions. Treat `filing_id` as
ownership only (which writer stored a row: `is_(None)` / `isnot(None)`), never as a key to a
filing's figures, and name the onclause of any join between the fact table and `filings` (the key
SQLAlchemy infers is `filing_id`). The rows the per-filing writer stored (`filing_id` set) count
but for condition 6. A row another writer stored under the accession counts only when every one of
these holds:

1. the per-filing writer has run on the filing (`processed_facts_at` is set);
2. the row is not withheld: provenance `validation` of `unavailable` (a repair-retired row, or one
   the publication policy withholds) never counts;
3. it is a reported item, or a calculation with recorded operands, every one under the same
   accession (`fact_provenance.operands_within_accession`, which is true for a record with no
   operands, so check `inputs` too): a companyfacts calculation takes its first operand's accession,
   so its other operand may be a later filing's, and a legacy calculation with no operands proves
   nothing;
4. it is in the filing's currency. In a line the filing owns rows of, its unit is one of theirs. In
   any other line, its currency (a ratio's is its recorded operands', `currency._operand_unit`) is
   the one the filing's own rows rank first by the per-filing extractor's rule
   (`currency._reporting_currency`: the most period ends, then a non-USD code; presence at the
   filing's own year breaks no tie), since the extractor chose it for this report; own rows in two
   currencies (a USD read, then a native one) take the one with more years, the native one on a tie.
   A sync can hold a line only in USD, as an early one read the USD lists alone and a current one
   does for a filer that switched currency, and that line's own-year translation alone reaches the
   period end. Only when no own row carries a currency do the stand-ins rank their own: the sync
   held every annual cell the writer read, in the writer's currency (the newest report synced first,
   at a domestic filer or after a native sync), or the writer stored no annual row (an interim
   report, or one it read nothing annual from);
5. its line reaches the filing's own period end: some row of the line that counts (the filing's own,
   or one meeting 1-4) ends within `fiscal_naming.DRIFT_DAYS` days of `Filing.period_end_date`,
   counted in days, never calendar years (a year ending by September and its first quarter end in
   one calendar year). With no period end on record, no such row counts. Short of it, the rows
   another writer left there are only the cells the filing reported last (an older report's oldest
   year and older balance, an interim report's prior year-end balance), and a line of those alone
   reads as all it disclosed. `period_end_date` is EDGAR's submissions `reportDate`, which names the
   XBRL year end itself in nearly every annual report, 52/53-week calendars included (1,048 of 1,050
   sampled from 99 filers). The 18 days absorb the odd one a day off and stay well inside the
   quarter that keeps a 10-Q's prior year-end out. A sample of 63 reports from 52/53-week filers had
   two misses: one a day off, and Legacy Reserves' fresh-start predecessor span 21 days off, whose
   flow lines' stand-ins fall short while its balances, at `reportDate`, still reach. The two misses
   of the first sample, Tractor Supply's 2014 and 2015 10-Ks, give the filing date, 53 days on: such
   a report keeps its own rows only, as before this reader;
6. no year its line misses lies after it, which holds the filing's own rows too: where two rows of
   the line that count (the filing's own, or ones meeting 1-5), next by period end, lie more than a
   year and `DRIFT_DAYS` apart, and the company holds an FY row of the concept a whole number of years
   after the earlier one and more than `DRIFT_DAYS` before the later one, the filing reported that
   year but its row sits under another accession, and the line shows only its rows from the later one
   on (`filing_scope._first_years_after_a_missing_one`). On the chart's categorical axis the two would
   stand side by side as consecutive years. An older report's line the writer read nothing of has such
   a gap where a later report restated its own year: the sync holds the oldest year, which the report
   filed last, and the own year, WP5b's own-report row (`facts/own_reports.py`), while the year
   between sits under the next report's accession (REGN's FY2017 under its FY2019 10-K; 728 days for a
   year ending by September, 2020-09-26 to 2022-09-24), so the line shows its own year alone, as its
   report gave it. A report some sync saw as the newest holds the year between itself, as a demoted
   winner, and its line is whole; one no sync saw as the newest (an older report when the company was
   first synced) does not. A line misses a year too where the audited repair withheld the year between,
   and where the extractor gave the own year alone beside the oldest-year stand-in (main charted that
   one with the year between missing). The rule reads the rows, not their writer, so the chart is the
   same whichever writer ran first: the own year is the own-report row synced first, the filing's own
   row processed first. A gap no FY row of the company fills is the company's own, no missing year,
   and the line charts as main does, in either order: a fiscal-year change's transition period (30
   September 2019 to 31 December 2020, 458 days; 31 December 2021 to 30 June 2023, 546), a fresh-start
   split year, a year no filing reported. Nor does a row off the earlier row's cadence fill one (a
   recast calendar year three months after the old fiscal year end), nor a withheld row. A 53-week
   year (371 days) is no gap.

Keep another company's rows out (a combined report shares one accession), and show a row another
writer stored under the year counted, back or forward, from the latest period end the filing's own
rows name (never from another such row's); it keeps its own label when the filing owns no row to
count from, or when no whole number of years lies between the two (`fiscal_naming.years_back`
gives none, as across a transition period): writer generations name a year differently.

Known shapes outside the rule. Reaching the period end with no year missing does not make a line
whole. Condition 4 closed the first shape found: a sync of 2026-10-10 to #1365 read the USD lists
alone and stored under each 20-F's accession a ratio (a margin, the current ratio) over its own-year
convenience figures, operands recorded, so an older report's margin line the writer read nothing of
reached through it and charted its oldest year and own year without the one between (a balance-sheet
ratio has no year between: a 20-F gives two balance years). The same rows cost ratio lines in one
processing order, when the per-filing writer first ran on a report after the native sync, which
skipped the identities they hold. The newest 20-F then owns no row of a margin or current-ratio line
and its own year has no CNY ratio, so the line falls short. An older 20-F loses its current-ratio
line the same way: the native sync holds its older balance's ratio and the early sync its own
year's, so the writer owns none, and the CNY older balance alone falls short (a margin line it read
is owned through the middle year, and shows). Had the writer run before the native sync, it owns the
CNY ratios that sync had not stored (a margin's two earlier years, a current ratio's earlier balance
year), the line is owned, and every year shows. Main charted none of these lines either: it read the
writer's rows alone. The quarterly repair recomputes a stored ratio from native operands only where
the sync's candidate shares its identity (`docs/quarterly-data-repair.md`). That holds for the
newest report's own-year rows, so its lines return once the repair runs, and not for an older
report's, whose native own-year ratio sits under the later report's accession, so its current ratio
does not. The repair runs only as the Ops `repair-quarterly-apply` the founder approves for named
tickers; nothing schedules it, and whether it has run is unknown (`tasks/todo.md` F61 (2)). Few
filings can be in that state: only summarized filings are processed, and F61 (1)'s count of
2026-10-23 found one classified CNY summary and 5 with no recorded currency. WP5b's own-report rows
are the reports' own figures, so they stand in like any row: REGN's FY2018 10-K charts the 6,710.8M
its own report gave for its own year, never the FY2020 10-K's 5,145.6M, and the FY2020 10-K charts
5,145.6M. Where one holds an older report's own-year cell, the writer skips that cell, as it skips any
stored identity, and the row stands in for it. A line the writer read nothing of reaches the period end
through it: beside the oldest year the line misses the year between, and condition 6 shows the own
year alone (main charted nothing for it); a balance line, whose older balance the report filed last, is
whole and shows both balances (main charted none of it). Where later filings hold the report's earlier
years too (an 8-K recast the next 10-K repeats), such a line holds the own year alone and charts it.
So a line the writer read nothing of shows its own year where a later filing restated that year, and
nothing (its oldest year alone, short of the period end) where none did: a shape the rule leaves, like
the one-year lines that follow. A report the writer stored no annual row of takes the stand-ins' own
currency (condition 4), so at a switched
filer, or at a foreign filer not re-synced since #1365 whose only stand-ins are the early sync's USD
rows, it charts its USD translations, one year a line, on the older and the newest 20-F alike (main
charted nothing for it). And a 40-F is never processed: the summary pipeline fetches XBRL for 10-K,
10-Q and 20-F only (`summary_stages/enrichment.py`), so a 40-F's processed gate stays shut and its
chart empty, as before this reader; its test case holds for when one is.

**Evidence**: `backend/app/services/facts/filing_scope.py::annual_filing_rows` and `filing_years`,
read by `facts/fundamentals.get_filing_fundamentals`; the Copilot already scoped by accession
(`copilot_tools._scope`). Each condition is pinned on the bad case by
`backend/tests/unit/test_filing_fundamentals_by_accession.py`, condition 4's currency shapes
(an early sync's rows alone and beside a native sync, a switched filer, a ratio's operands in a
line the report owns no row of and in one it owns, a per-share line, own rows in two currencies
tied and not, the stand-ins' own tie), condition 5's distance in days, and condition 6 on the
own-report rows' shapes (REGN's FY2018 to FY2021 10-Ks in either processing order, a year ending by
September and its 53-week year, a CNY 20-F with its own rows and with none, a 10-Q that recasts the
prior balance, an earlier sync's whole line and its withheld year between, a line read for its own
year alone in either order, restated or not, and the one-year line it leaves) and on the gaps it
leaves (a September-to-December and a December-to-June fiscal-year change, the first with a recast
calendar year, and a fresh-start split year, each in either order, the change report and the one
after it charting as on main, which the same tests pass on) included. The Copilot reads the same rows
and computes no growth across a gap: its prior year lies 357 to 373 days back
(`copilot_tools._prior_comparable`). Partly gated by
`backend/tests/unit/test_filing_facts_read_by_accession.py`, which counts the mentions of
`FinancialFact.filing_id` through the model it can see (the column, an ownership test, a lookup by
name, a join with no onclause to or from the model or `Filing` in its method, function or table
form, a relationship on or to the model) in `backend/app`, `backend/scripts`, `backend/evals` and
the top-level backend modules against a reviewed list; a comparison of a loaded row's `filing_id`
or a copied state's key, a name built at run time, a join whose tables are unpacked or reached
through a bound name, a call or a re-exported SQLAlchemy module, a mention in `backend/tests`, and
a new reader that restates the conditions above instead of calling `filing_scope` are
review-checked.
