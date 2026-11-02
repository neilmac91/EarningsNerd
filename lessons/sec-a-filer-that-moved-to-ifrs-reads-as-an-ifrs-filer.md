# Read a filer whose latest periodic report is IFRS as an IFRS filer; never let its companyfacts series present its last US-GAAP year as its latest figures

Date: 2026-11-01   Area: sec (financial facts)

**Context**: F61 call (2)'s forced sync stored companyfacts series for ITUB and TM. Both companies had
no stored figure before. Both reported under US GAAP once (ITUB to 2010, Toyota to the year ended
2020-03-31) and under IFRS since, and the sync reads us-gaap only. So their series ended where their
US-GAAP reporting stopped. Multi-Period Analysis and the peers endpoint read those figures as each
company's latest (TM: revenue for the year ended 2020-03-31), and the analysis page's "data as of"
named the sync time, not the age of the figures. The product already tells a reader when a filer
reports under IFRS ("Multi-period analysis for IFRS filers is coming later"), but only for a payload
with no us-gaap data at all. The founder chose to treat such filers as IFRS filers (2026-11-01).

**Rule**: Decide a filer's reporting basis from its latest periodic report, never from whether any
us-gaap data exists (`facts/reporting_basis.py::reports_under_ifrs`).
- The latest periodic report is the newest original 10-K, 10-Q, 20-F or 40-F that us-gaap or
  ifrs-full items name. Amendments are left out, since a 20-F/A may tag only its cover. A 10-Q counts:
  a filer moving from IFRS to US GAAP may file US-GAAP 10-Qs before its first 10-K (Flutter), and an
  IFRS filer files no 10-Q.
- When that report tags more items under ifrs-full than under us-gaap, the filer is an IFRS filer.
  A tie, a few ifrs-full items in a US-GAAP report, or IFRS reports from years before the latest
  US-GAAP report leave it a US-GAAP filer.
- A payload with no ifrs-full data never reaches the count, so a domestic filer's sync is unchanged.

An IFRS filer's sync stores nothing and retires from current use the series earlier companyfacts
syncs stored for it (`retire_ifrs_series`), taking the company row first as every fact writer does. It
retires only rows with no filing owner, reported (`companyfacts`) or calculated from them (`derived`).
Rows are never deleted: a filing's own rows stay current, and every filing's rows stay readable by
accession. Retire the rows rather than hide the series in a reader: Multi-Period Analysis, the peers
endpoint and the quarterly repair all read `is_latest`, so they agree, and the repair refuses the
payload as it refuses an IFRS-only filer's. The retire covers the companyfacts series only. A row the
per-filing writer stores later from one of the filer's earlier pre-switch US-GAAP reports, when a reader
summarizes it, finds no current row at its key and goes in current, so that report's year (TM: the year
ended 2019-03-31, from its 2019 20-F) can read as the latest again until a stored basis lets the writer
store it behind (E287). The last US-GAAP report's rows are the series' own identities, which the writer
skips. A filer that moves back to US GAAP reads its new reports' years as current; the retired years stay
non-current (a sync skips an identity it holds), except a non-USD filer's amounts, which a sync outside
USD re-promotes without their ratios. The same stored basis would restore them (E287). A 6-K decides
nothing, so a filer that tags its statements only in 6-Ks (CNI) is read from its last periodic report;
none of production's 101 foreign filers reads against its newest items of any form, 6-Ks included (E287). The retire runs only when a sync fetches:
after the rule deploys, force-sync each filer it reads as IFRS that may hold a stored series.

**Evidence**: `backend/app/services/facts/reporting_basis.py`;
`backend/app/services/facts/companyfacts.py` (`normalize_companyfacts`' first branch);
`backend/app/services/facts/ingest.py` (`_persist_companyfacts_payload`);
`backend/tests/unit/test_companyfacts_reporting_basis.py` (23 tests, sixteen mutants killed, the
company-lock order pinned by a statement spy); F61 in
`tasks/todo.md`; the peers endpoint read of 2026-11-01 (TM: JPY revenue for the year ended 2020-03-31;
ITUB: BRL net interest income for FY2010), and the readback after #1931's deploy and its forced sync of 2026-11-02. There, the peers endpoint serves no figure for either, and `detection-sql` (Ops 41389344425) finds no current companyfacts row for them. Count current rows when you read back a retire: a column that counts every row, current or not (set 3's `cf_native`), stays where it was.
