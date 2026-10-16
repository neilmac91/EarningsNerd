# Repair a stored fiscal label only from a label the reference writer derived from evidence; skip and count the rest, never infer one

Date: 2026-10-16   Area: sec / facts

**Context**: The per-filing writer stored annual facts under the calendar year of their end, the
companyfacts writer under the issuer's fiscal year, and the fact identity leaves `fiscal_year` out
(2026-10-15 bug hunt, finding 8). The repair (`backend/scripts/relabel_filing_fy_facts.py`) copies
the companyfacts year onto the filing-owned rows. The companyfacts writer is not uniformly
trustworthy: it names a fiscal-year-end balance older than every fiscal year it knows (its oldest
opening balance) by calendar year (`facts/companyfacts.py`, `reported_fiscal_year(record, end) or
end.year`), which for a January year is the next year's label, and nothing in the stored row says
which path wrote it. Rows from different syncs can also name different years for one period end.
And where the per-filing writer stored an identity first, the companyfacts sync skipped it, so the
reference row a repair would read is simply missing.

**Rule**: Copy a label from another writer's stored rows only where the stored columns prove the
writer took it from its evidence: for companyfacts FY labels, every companyfacts-reported FY row
at that period end names one year and at least one of them is a duration (a duration's year comes
from its fiscal-year window; an instant-only label may be the calendar fallback). Exclude rows a
repair already retired. When the rows disagree, when only instants exist, or when no row exists,
skip and count the reason per period end; never pick one, never infer a year from neighbouring
years, and never treat a missing reference row as agreement. Change only the label column, journal
every change in `financial_fact_revision` so the audited rollback can revert it, dry-run by
default, and leave a row that already agrees untouched so re-runs report zero.

**Evidence**: `backend/scripts/relabel_filing_fy_facts.py` (`_trusted_year`, `plan_company`);
gate `backend/tests/unit/test_relabel_filing_fy_facts_script.py` (the instant-only opening
balance is never copied; disagreeing, retired and missing evidence skip; a second apply reports
zero; the production writers' stale-sync order is repaired and its newest year is held as
`no_companyfacts_fy`); runbook `docs/fiscal-year-label-repair.md`.
