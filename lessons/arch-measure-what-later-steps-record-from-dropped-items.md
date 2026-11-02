# Measure every record a dropping rule changes, the meta a repair reads included, not only the rows

Date: 2026-11-02   Area: arch

**Context**: E291 and E292 drop a quarterly report's year that holds part of one inside the companyfacts collector's
admission, before the calendar step. Both censuses compared rows, which moved only as intended, and missed that the
calendar records each rolling year it keeps out of the rows in `meta["calendar_exclusions"]`: the only evidence
`quarterly_fact_repair._calendar_relabels` quarantines a legacy rolling row by. E291 had already taken LMB's record
away (its financing cash flow from its inception), and E292 took AMZN's trailing twelve months and ARTW's two
March-February years. #1962's high-tier review found it; a meta census over the 696 cached payloads sized it.

**Rule**: When a rule drops items before later steps, measure everything those steps keep from them over the census
corpus, with the rule and without it: the rows, the authority, and every meta key a reader consumes (here
`calendar_exclusions`, `quarterly_exclusions`, `history`). A rule that decides which items compete never decides what
the record says: hand the dropped items to the step that keeps the record, for the record alone.

**Evidence**: `backend/app/services/facts/fiscal_naming.py::partial_years`, the `partial` sink in
`facts/companyfacts.py::_collect_companyfacts_values`, `facts/calendar.py::fiscal_duration_values`;
`backend/tests/unit/test_partial_years.py` (the calendar's record section, the quarterly repair's quarantine by it, and
`test_only_the_collector_reads_the_years_the_rule_drops`); #1962.
