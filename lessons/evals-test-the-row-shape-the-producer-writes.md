# Test a consumer on the row shape its real producer writes, not on a neighbour's

Date: 2026-09-16   Area: evals

**Context**: `evals.judge_report` (#898) was built to judge any retained eval report and tested on
rows copied from the weekly-readout fixture, which carry the cohort's `accession_number`. The runner's
own rows carry `ticker`, `filing_type` and `run` with `accession_number: None` (only the weekly readout
stamps the accession on). Fifteen green tests and a full gate later, the first real artifact (PR #899,
run 35146584090) was refused with "Foreign attempt identity" before a single judge call.

**Rule**: When a consumer reads records another module writes, at least one test uses a record in the
producer's actual shape (copied from a real artifact or built by the producer's own row constructor),
and the identity rule the consumer relies on is asserted against the committed data it will meet
(`test_the_committed_golden_set_identifies_every_verified_filing_by_ticker_and_form`). A fixture that
mirrors a sibling consumer's fixture proves only that the two fixtures agree.

**Evidence**: #898 tests versus the first `eval-report-35146584090` row; fix in
`backend/evals/judge_report.py::resolve_filing` with runner-shaped fixture rows.
