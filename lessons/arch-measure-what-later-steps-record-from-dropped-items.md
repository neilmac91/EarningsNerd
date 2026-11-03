# Measure every record a dropping rule changes, the meta a repair reads included, not only the rows

Date: 2026-11-02   Area: arch

**Context**: E291 and E292 drop a quarterly report's year that holds part of one inside the companyfacts collector's
admission, before the calendar step. Both censuses compared rows, which moved only as intended, and missed that the
calendar records each rolling year it keeps out of the rows in `meta["calendar_exclusions"]`: the only evidence
`quarterly_fact_repair._calendar_relabels` quarantines a legacy rolling row by. E291 had already taken LMB's record
away (its financing cash flow from its inception), and E292 took AMZN's trailing twelve months and ARTW's two
March-February years. #1962's high-tier review found it; a meta census over the 696 cached payloads sized it. Its
third review found the first fix, which handed the calendar each dropped item alone, still short: a year two 10-Qs
carry lost its later copy's record, because the earlier copy no longer lent the year its quarter.

**Rule**: When a rule drops items before later steps, measure everything those steps keep from them over the census
corpus, with the rule and without it: the rows, the authority, and every meta key a reader consumes (here
`calendar_exclusions`, `quarterly_exclusions`, `history`). A rule that decides which items compete never decides what
the record says: the step that keeps the record judges the competition rebuilt without the rule, each dropped item
back in its place, for the record alone. Handed in one by one, a dropped item is judged apart from the items it
competed with.

**Evidence**: `backend/app/services/facts/fiscal_naming.py::partial_years`, the `unruled` winners of
`facts/companyfacts.py::_collect_companyfacts_values` (`_tag_winners`), `facts/calendar.py::fiscal_duration_values`;
`backend/tests/unit/test_partial_years.py` (the calendar's record section:
`test_the_calendars_record_is_the_one_the_rule_never_touched`, the two-10-Q year, the quarterly repair's quarantine by
the record, and `test_only_the_collector_reads_the_years_the_rule_drops`); #1962.
