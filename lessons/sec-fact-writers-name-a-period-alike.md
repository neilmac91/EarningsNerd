# Name a fact's fiscal year from its filing's DEI focus, never the calendar year of its end; every fact writer must name a period alike

Date: 2026-10-16   Area: sec / facts

**Context**: `financial_fact` has two writers for the same periods: the per-filing writer (a
reader opens a 10-K, `facts/upsert.normalize_standardized_to_facts`) and the companyfacts sync
(`facts/companyfacts.py`). The identity (concept, period_end, fiscal_period, unit, accession)
leaves the fiscal year out, so whichever writer stores an identity first keeps its label and the
other is skipped. The companyfacts writer named a year from SEC's timely original annual reports;
the per-filing writer labelled only 10-Q points from the DEI focus and named every 10-K point by
`period_end.year`. For a retailer whose year ending 1 February 2025 is fiscal 2024 (Target, Home
Depot, Lowe's) and for a 52-week year ending 1 January (Johnson & Johnson), the two disagreed. The
Multi-Period Analysis axis lost a year and spread YoY and CAGR over the wrong spans, the filing
chart drew two FY2023 bars, and a later companyfacts sync could not repair the rows because it
skipped the occupied identities. The one test of the fallback used Apple, whose September year
names the same year either way.

**Rule**: Derive every per-filing fiscal label from the filing's own DEI focus and the point's
whole-period distance from the report date (`edgar/fiscal_periods.filing_point_label`, shared by
the instance extractor and the companyfacts fallback), bounded the way the companyfacts writer
bounds it. When two writers can store the same identity, they must compute the same label from the
same evidence; prove it by running both orders over a non-calendar issuer, not a calendar-aligned
one. A reader that indexes by label must refuse a label that current rows give to two different
period ends, not let query order pick one. Rows already stored under the old label need a
separate, founder-run repair.

**Evidence**: `backend/app/services/edgar/fiscal_periods.py`, `edgar/xbrl_instance._finish_instance`,
`edgar/xbrl_companyfacts.append_items`, `trend_analysis/dataset._index_facts`; gate
`backend/tests/unit/test_annual_fact_fiscal_labels.py` (both writers in three orders for Target,
Home Depot, Johnson & Johnson and Apple calendars, the filing chart, the fallback, and the dataset
refusal).
