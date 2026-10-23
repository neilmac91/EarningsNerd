# Name a fact's fiscal year from its filing's trusted DEI focus, else the calendar year of its end, never NULL, and move an annual filing's years onto a year chain companyfacts already stores; every fact writer must name a period alike, counting years and trusting a focus through `facts/fiscal_naming` alone

Date: 2026-10-16, updated 2026-10-23   Area: sec / facts

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
disagreed again, now for calendar-year filers. The narrowed trust still let one 10-K mislabel an
issuer that names a January year by its end when that 10-K's focus lags: Salesforce's report for
the year ended 31 January 2026 (`0001108524-26-000060`, its fiscal 2026) carries focus 2025, and
one filing cannot tell it from Target. Review found seven such reports that main had named right
(Salesforce FY2021 and FY2026, CrowdStrike FY2023 to FY2025, Veeva FY2022, Best Buy FY2021); the
founder chose to take the year companyfacts already names. A Multi-Period Analysis refusal of a
label that two period ends carry was reverted in review: main's reader orders rows by period end,
so such a label resolves to its latest end, the axis bucket's own, which was the correctly labelled
row in every clash the old writer left, and the refusal turned those values into gaps. Three gaps
stayed open (records PR #1504). The companyfacts writer named an FY-end balance older than every
year window (an equity statement's oldest opening balance) by one report's `fy` or the calendar year
of its end: Target's balance of 30 January 2021 became 2021, not fiscal 2020, so its label depended
on which writer ran first, and while that row was current the stored-row relabel held the filing's
next year-end balance as `label_collision`. A year chain with no annual report filed within 180 days
of its end fell back to calendar years while the per-filing labellers named fiscal ones. And a 10-K
whose focus lags, opened before companyfacts stored any trusted year, kept the year before, because
the relabel never touched a label a labeller set.

**Rule**: Derive every per-filing fiscal label from the filing's own DEI focus and the point's
whole-period distance from the report date (`edgar/fiscal_periods.filing_point_label`, shared by the
instance extractor and the companyfacts fallback). Trust an annual focus only inside the
companyfacts writer's year bound, and more narrowly: an annual form
(`facts/fiscal_naming.ANNUAL_FORMS`), an FY focus, the end year or the year before, and the year
before only where most of the year lies in it. The labeller sees no filing date, so it cannot apply
that writer's 180-day timeliness bound; that writer names a chain no timely report names under the
labeller's own trust instead (below). Without a trusted focus, or for a point that is not a whole
number of years from the report date, keep the calendar year of its end; never write a NULL year,
which drops the period from Multi-Period Analysis and the filing chart's axis. Where companyfacts
already stores a trusted fiscal year for one of an annual report's period ends, move every FY row of
that filing onto it by one offset (`facts/fiscal_evidence.adopt_trusted_fiscal_years`, in
`facts/upsert.process_filing_facts`): trust only companyfacts-reported FY rows that the
fiscal-year-window writer stored (provenance version `PROVENANCE_VERSION`; a NULL-provenance row
names every year by calendar year) and only where they name one year and include a duration; keep
the filing's own labels when the offsets disagree, and never move a quarter. Never adopt year by
year: a 10-K processed before companyfacts stores its newest year would give that year the label of
the year before it. Both writers count whole years back from an anchor (`years_back`) and trust a
report's own focus (`focus_years`) through one module, `facts/fiscal_naming`; never write a second
copy of either rule. The companyfacts writer names a year chain that no timely report names from its
late reports' own periods (a report's own period is the latest year it reports, never one of its
comparatives) under `focus_years`, and only then by calendar year; it names an FY-end balance
outside every year window by the year that ends on its date, whole years before the next window's
(`year_ending_on`). When two writers can store the same identity, they must compute the same label
from the same evidence; prove it by running both orders over a non-calendar issuer and over a
calendar issuer whose one filing carries an outlier focus, not only a calendar-aligned one. Rows
already stored under the old label need a separate, founder-run repair.

**Evidence**: `backend/app/services/edgar/fiscal_periods.py`, `edgar/xbrl_instance._finish_instance`,
`edgar/xbrl_companyfacts.append_items`, `facts/fiscal_naming.py` (the counting and trust rules both
writers share, and the late-chain and opening-balance naming), `facts/fiscal_evidence.py` (the trust
rule the stored-row relabel, #1372, imports) and `facts/upsert.process_filing_facts`; gate
`backend/tests/unit/test_annual_fact_fiscal_labels.py` (both writers in three orders for Target,
Home Depot, Johnson & Johnson, Apple, a December filer with a lagging focus and two March 20-F
filers, with their annual reports filed on time and all filed late; the oldest opening balance in
both orders; a late report's own period, never its comparative, naming its chain; a late chain's
quarter; Salesforce, CrowdStrike, Veeva and Best Buy opened after a sync through the prior report
or this one, with Target as the zero offset; missing, legacy, instant-only and disagreeing
companyfacts years; a 10-Q; a late year chain synced first; the audited repair of rows stored
before the 2026-10-23 rules; every annual form and amendment; the filing chart; the fallback; the
dataset's balance read), `backend/tests/unit/test_fiscal_year_rules_single_home.py` (no second copy
of the whole-year divisor or the 183-day midpoint under the two writers' packages) and
`backend/tests/unit/test_relabel_filing_fy_facts_script.py` for the relabel's one-offset move.

**Known limits.**
- A lagging focus on a year ending January to early July, in an annual report opened before
  companyfacts stores a trusted year for any of its period ends (no sync yet, or only rows from
  before the fiscal-year-window writer): one filing cannot outvote that focus, so the writer stores
  the year before. The stored-row relabel (#1372) moves such a filing by its one offset, where every
  trusted year of the filing gives that offset and its read of the current writer names the same
  year (`docs/fiscal-year-label-repair.md`); until a founder-run relabel, the row stays.
- Rows the companyfacts writer stored before the 2026-10-23 rules keep their labels, since a sync is
  insert-only: an oldest opening balance one year high (Target, Home Depot, J&J), and a delinquent
  filer's late chain under calendar years. When such a filer's next annual report syncs, the years it
  re-reports are stored under fiscal labels beside the older calendar ones, so one label can sit on
  two period ends until the repair runs. The audited quarterly repair
  (`scripts/repair_quarterly_facts.py`) relabels the current companyfacts rows; superseded rows keep
  the old year, so the evidence at such an end can read as `companyfacts_disagree`. Instant-only
  evidence stays untrusted (`facts/fiscal_evidence.trusted_year`): a stored opening balance from
  before the rules carries the same provenance version as one from after.
- A late chain whose reports name no own period by a trusted year (a December year under a lagging
  focus) keeps calendar years; so does the per-filing labeller, which trusts that focus no more. A
  late chain whose only own-period year comes from a lagging focus on a January year named by its
  end (a Salesforce-shaped report filed late) is named one year low by both writers, as one filing
  cannot tell it from Target; more late reports in the chain outvote it. Abstaining on a late
  filing is not a fix: it would move the clash onto a late report, or a late amendment, that
  follows a timely one, which both writers name alike.
