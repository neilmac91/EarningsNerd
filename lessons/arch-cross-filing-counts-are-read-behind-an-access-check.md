# Cross-filing counts and review rows are read behind one access-checking caller, never raw

Date: 2026-10-13   Area: arch

**Context**: PR B gave two new readers to the "what changed" data. The dashboard feed read a
review row's `completed_at` raw and called the review "Reviewed" after a re-extraction had retired
its change ids and reopened it (the review endpoint, which reconciles rows against the live
comparison, said otherwise on the same page). And `wording_change_summaries`, which returns a
filing's cached comparison counts with no notion of who is asking, is content that only the flag
and the viewer decide: behind `ENABLE_SECTION_CHANGES`, the alert line goes to a recipient whose
plan has `section_changes` (entitlements rule 4), the dashboard card shows the counts at teaser and
full access and the review progress at full access only, and the Change Report is cut to the
viewer's `SectionAccess`. PR C's review then found the first gates saw only the spelled call: an
aliased import, a relationship declared on `User` as a string, or a raw `diff_summary` read walked
past them.

**Rule**: a reader of `section_reviews` goes through `section_review_service` (`review_state`,
`review_progress`), which filters labels to the live comparison's ids and reports a receipt only
while its fingerprints still match; the cached comparison column (`diff_summary`) is named only in
`filing_section_service`, and its functions that hand the counts out (`wording_change_summaries`,
`build_section_changes`, `cached_diff`) are called only from scopes that check the flag and the plan
or pass the viewer's `SectionAccess` through (`filing_scan_service.alert_wording_changes`,
`dashboard_feed_service._wording_changes`, `change_report_service.build_change_report`, and
`section_review_service._comparison` and `review_progress` for a reader its callers already gated). A new reader is added
to the allow-list with the check it makes, in the same PR, or it fails the gate; the gate pins the
reader, review checks the check.

**Evidence**: gates `backend/tests/unit/test_section_review_rows_read_through_the_service_allowlist.py`
(every reference to `SectionReview` under `app/` by name or as a `relationship()` string, and the
table name in any non-docstring string; the GDPR export is the one listed exception, a verbatim dump)
and `backend/tests/unit/test_wording_summaries_access_allowlist.py` (the column pinned to its owner
module and its listed scopes; every reference to the three functions by file and scope; an aliased
import fails outright). The feed's fix: `dashboard_feed_service._wording_changes` reading
`section_review_service.review_progress`, pinned by the feed test in
`backend/tests/unit/test_section_review_service.py`.
