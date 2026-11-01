# Read a filer whose latest annual report is IFRS as an IFRS filer; never present its last US-GAAP year as its latest figures

Date: 2026-11-01   Area: sec (financial facts)

**Context**: F61 call (2)'s forced sync stored companyfacts series for ITUB and TM. Both companies had
no stored figure before. Both reported under US GAAP once (ITUB to 2010, Toyota to the year ended
2020-03-31) and under IFRS since, and the sync reads us-gaap only. So their series ended where their
US-GAAP reporting stopped. Multi-Period Analysis and the peers endpoint read those figures as each
company's latest (TM: revenue for the year ended 2020-03-31), and the analysis page's "data as of"
named the sync time, not the age of the figures. The product already tells a reader when a filer
reports under IFRS ("Multi-period analysis for IFRS filers is coming later"), but only for a payload
with no us-gaap data at all. The founder chose to treat such filers as IFRS filers (2026-11-01).

**Rule**: Decide a filer's reporting basis from its latest annual report, never from whether any
us-gaap data exists (`facts/reporting_basis.py::reports_under_ifrs`).
- The latest annual report is the newest original 10-K, 20-F or 40-F that us-gaap or ifrs-full
  items name. Amendments are left out, since a 20-F/A may tag only its cover.
- When that report tags more items under ifrs-full than under us-gaap, the filer is an IFRS filer.
  A tie, a few ifrs-full items in a US-GAAP report, or IFRS reports from years before the latest
  US-GAAP report leave it a US-GAAP filer.
- A payload with no ifrs-full data never reaches the count, so a domestic filer's sync is unchanged.

An IFRS filer's sync stores nothing and retires from current use the series earlier companyfacts
syncs stored for it (`retire_ifrs_series`). It retires only rows with no filing owner, reported
(`companyfacts`) or calculated from them (`derived`). Rows are never deleted: a filing's own rows stay
current, and every filing's rows stay readable by accession. Never hide such a series in a reader
instead: Multi-Period Analysis, the peers endpoint and the quarterly repair all read `is_latest`, so
retiring the rows keeps them consistent, and the repair refuses the payload as it refuses an
IFRS-only filer's.

**Evidence**: `backend/app/services/facts/reporting_basis.py`;
`backend/app/services/facts/companyfacts.py` (`normalize_companyfacts`' first branch);
`backend/app/services/facts/ingest.py` (`_persist_companyfacts_payload`);
`backend/tests/unit/test_companyfacts_reporting_basis.py` (16 tests, ten mutants killed); F61 in
`tasks/todo.md`; the peers endpoint read of 2026-11-01 (TM: JPY revenue for the year ended 2020-03-31;
ITUB: BRL net interest income for FY2010).
