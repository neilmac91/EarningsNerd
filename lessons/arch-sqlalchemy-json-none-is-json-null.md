# A JSON column's None is a JSON null, not SQL NULL: read "no value yet" off a scalar column

Date: 2026-10-13   Area: arch

**Context**: `filing_section_text.diff_summary` is a SQLAlchemy `JSON` column that holds a filing's
cached comparison counts, and `compute_diff_summary` writes `None` to it while the filing has no
comparison yet (the prior is not extracted, there is no prior, the form is unsupported). PR B's
first draft read "filings with a comparison" as `diff_summary IS NOT NULL`. SQLAlchemy's `JSON`
type defaults to `none_as_null=False`, so the Python `None` is stored as the JSON value `null`,
which `IS NOT NULL` admits; the row came back, `summary.get("items_total")` read 0, and every Pro
recipient of an alert or digest for such a filing would have been told "Risk factor wording: no changes
since the prior 10-K", with the dashboard card saying the same (the flag was off: nothing shipped). Reproduced through the real extractor on
SQLite and on PostgreSQL 16 by two refuters in the review round.

**Rule**: never test a `JSON` column against `None` to mean "nothing stored yet", in a filter or in
Python. Store absence in a scalar column that is SQL NULL when absent (`diff_prior_filing_id`,
`completed_at`) and read it there; keep the JSON column for the value. When a JSON column must
itself carry absence, declare it `JSON(none_as_null=True)` at the model and say so in a comment,
because the default is the trap. A reader that gets the JSON value still checks its shape
(`isinstance(summary, dict)`) before indexing it.

**Evidence**: `backend/app/services/filing_section_service.py::wording_change_summaries` (the
filter on `diff_prior_filing_id` and the docstring), pinned by
`backend/tests/unit/test_alert_wording_line.py::test_a_row_without_a_comparison_yet_is_not_a_zero_comparison`.
Partly gated: `backend/tests/unit/test_wording_summaries_access_allowlist.py` fails any comparison
of `diff_summary` with `None` under `app/`; other JSON columns are review-checked.
