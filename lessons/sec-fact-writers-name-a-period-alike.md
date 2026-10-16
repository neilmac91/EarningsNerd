# Name a fact's fiscal year from its filing's trusted DEI focus, else the calendar year of its end, never NULL; every fact writer must name a period alike

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
names the same year either way. The first fix trusted any focus naming the end year or the year
before, which is only the companyfacts writer's year bound: that writer also outvotes one filing's
outlier `fy` across the year chain (`facts/calendar._consistent_year_chain`). So a December 10-K
with a lagging focus moved that filer's years on the per-filing side only, and the two writers
disagreed again, now for calendar-year filers.

**Rule**: Derive every per-filing fiscal label from the filing's own DEI focus and the point's
whole-period distance from the report date (`edgar/fiscal_periods.filing_point_label`, shared by
the instance extractor and the companyfacts fallback). Trust an annual focus only inside the
companyfacts writer's year bound, and more narrowly: an annual form (`facts/calendar.ANNUAL_FORMS`),
an FY focus, the end year or the year before, and the year before only where most of the year lies
in it. The labeller sees no filing date, so it cannot apply that writer's 180-day timeliness bound
(see the known limits). Without a trusted focus, or for a point that is not a whole number of
years from the report date, keep the calendar year of its end; never write a NULL year, which drops
the period from Multi-Period Analysis and the filing chart's axis. When two writers can store the
same identity, they must compute the same label from the same evidence; prove it by running both
orders over a non-calendar issuer and over a calendar issuer whose one filing carries an outlier
focus, not only a calendar-aligned one. A reader that indexes flows by label must refuse a label
that current rows give to two different period ends, not let query order pick one, and must read
a balance at its period's own end. Rows already stored under the old label need a separate,
founder-run repair.

**Evidence**: `backend/app/services/edgar/fiscal_periods.py`, `edgar/xbrl_instance._finish_instance`,
`edgar/xbrl_companyfacts.append_items`, `trend_analysis/dataset._index_facts` and `_series_points`;
gate `backend/tests/unit/test_annual_fact_fiscal_labels.py` (both writers in three orders for
Target, Home Depot, Johnson & Johnson, Apple, a December filer with a lagging focus and two March
20-F filers; every annual form and amendment; the filing chart; the fallback; the dataset's flow
refusal and balance read).

**Known limits.**
- One filing cannot outvote a lagging focus on a year ending January to early July, which the
  companyfacts writer's year chain can.
- A year chain with no timely annual report. The companyfacts writer names a year only from an
  annual report filed within 180 days of the year's end (`facts/calendar.reported_fiscal_year`);
  where a contiguous chain holds none, it falls back to calendar years
  (`facts/calendar._consistent_year_chain`), and `_label_quarters` names the chain's quarters from
  the same years. The per-filing labellers still name the fiscal year from each report's focus.
  The two differ only for an issuer whose fiscal year is named for the calendar year before its
  end: in practice a year ending in January or February, a 52-week year ending in early January,
  or a March 20-F named by its start. For such a delinquent filer, per-filing-only concepts
  (`return_on_assets`) and companyfacts-only concepts sit under different labels for one period
  end, and a colliding identity keeps whichever writer stored it first. Companyfacts first, the
  Multi-Period Analysis axis gets two buckets ending on one date. Filing first, the year just
  older than the filing's comparatives keeps a calendar label equal to the next year's fiscal one,
  so one label lands on two period ends: the dataset refuses that flow and coverage loses a year
  (the oldest, in a short history). Main named these annual rows by calendar year on both sides:
  one year off, but unmixed. A 10-Q filer's quarter rows were already mixed on main (the 10-Q
  labeller names the fiscal year), so for it the annual labeller extends an existing quarterly
  mix to the annual rows; a 20-F filer has no per-filing quarter rows, so for it the annual mix
  is new. Abstaining on a late filing is not the fix: it moves the clash onto a late report, or a
  late amendment, that follows a timely one, which both writers now name alike. The open
  follow-up is for the companyfacts writer to name an all-late chain from a late annual report's
  own-period `fy`, under the same FY, year-bound and midpoint trust; that fixes the chain's
  quarter labels too.
