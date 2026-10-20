# Repair a stored fiscal label only from a label the reference writer derived from evidence; skip and count the rest, never infer one

Date: 2026-10-16   Area: sec / facts

**Context**: The per-filing writer stored annual facts under the calendar year of their end, the
companyfacts writer under the issuer's fiscal year, and the fact identity leaves `fiscal_year` out
(2026-10-15 bug hunt, finding 8). The repair (`backend/scripts/relabel_filing_fy_facts.py`) copies
the companyfacts year onto the filing-owned rows. The companyfacts writer is not uniformly
trustworthy. Before #1191 it named every FY row by calendar year too, and the insert-only sync
keeps those rows; only their NULL provenance (rows since #1191 carry `provenance.version = 1`)
tells them apart. It still names a fiscal-year-end balance older than every fiscal year it knows
(its oldest opening balance) by one report's fy or by calendar year (`facts/companyfacts.py`,
`reported_fiscal_year(record, end) or end.year`), with no window chain behind it. Rows from
different syncs can name different years for one period end. Where the per-filing writer stored an
identity first, the companyfacts sync skipped it, so the reference row is simply missing. And a
first review round found that relabelling each row on its own evidence gave a filing two period
ends with one year (the chart symptom being repaired) when an older neighbour was held.

**Rule**: Copy a label from another writer's stored rows only where the stored columns prove that
writer derived it: for companyfacts FY labels, every row at that period end written by the
fiscal-year-window writer (provenance version 1; pre-#1191 rows are no evidence and never count as
agreement) names one year and at least one of them is a duration. Where no stored row is evidence
at a period end, the same writer's labels from a fresh read of its source, judged by the same rule
and never stored, may stand in; a stored row that is evidence always outranks the read. Exclude rows a repair already
retired. Rewrite only the defect's own signature (here a label equal to the calendar year of the
period end), never a label some labeller set. Before writing, project the whole company: hold any
relabel whose new label another period end of the same filing and concept, or another current row
of the concept, would carry, and re-check, since a held row keeps its label. When the rows
disagree, when only instants or only legacy rows exist and the read names no year, or when no row
exists, stored or read, skip and count the reason; never pick one, never infer a year from neighbouring years, and never treat a missing
reference row as agreement. Report filings left partly repaired. Change only the label column,
journal every change in `financial_fact_revision` so the audited rollback can revert it, dry-run
by default, and leave a row that already agrees untouched so re-runs report zero.

**Evidence**: `backend/app/services/facts/fiscal_evidence.py` (`evidence_kind`, `trusted_year`) and
`backend/scripts/relabel_filing_fy_facts.py` (`companyfacts_read`, `_collisions`, `plan_company`); gate `backend/tests/unit/test_relabel_filing_fy_facts_script.py`
(legacy rows are neither evidence nor agreement; a non-calendar label is never overwritten; an
instant-only label is never copied; disagreeing, retired and missing evidence skip; a relabel that
would give two period ends one year is held, from the production writers; a second apply reports
zero); runbook `docs/fiscal-year-label-repair.md`.
