# Runtime per-filing facts carry no duration — abstain, never substitute an annual-looking label

Date: 2026-09-12   Area: sec / verification

**Context**: Attaching a verified citation to "revenue for the fiscal year ended March 31, 2025"
needs proof that the fact behind it spans that year. The obvious proof is its own reported
duration, and per-filing facts do not have one: `facts_service.normalize_standardized_to_facts`
never writes `period_start`, and both retained #825 Copilot assessments show `period_start: null`
on every successful `get_financial_fact` result. The first implementation substituted an
annual-report form, `period_of_report` equality and the `FY` label. Review showed that is not a
substitute, and the actual production path proves it end to end: a three-month revenue point
ending on the fiscal year end survives `edgar/xbrl_service.py`'s `filter_and_sort`, which only
*ranks* the durations sharing a period end and never rejects a lone quarterly one; `append_items`
then drops its `start`; and `facts_service._fiscal_period` stamps `FY` from the FORM. A Q4 figure
therefore reaches the fact table wearing an annual label with no duration, and passes
`_valid_fact_provenance`. The form test and the `FY` label are one signal, not two, and
comparative cadence cannot separate them either.

**Rule**: Before gating on a fact field, read the writer and a real retained artifact, not just
the nullable column. When the evidence a claim needs is absent, abstain — do not substitute a
weaker signal that correlates with it. Adding an affirmative, *verified* marker on unproven scope
is a new error of our own making and is worse than the uncited prose it replaces; shipping
uncited is the safe direction. Say plainly that the abstaining case is unfixed rather than
reporting the mechanism as a fix. The selected-instance path DOES filter duration
(`instance_extractor.duration_in_window`), but it consumes that proof at extraction and records
nothing, so downstream the two paths are indistinguishable — carrying duration forward is the
real repair.

**Evidence**: `backend/app/services/edgar/xbrl_service.py` (`_duration_penalty`, `filter_and_sort`,
`append_items`); `backend/app/services/edgar/instance_extractor.py::duration_in_window`;
`backend/app/services/facts_service.py::_fiscal_period` and `normalize_standardized_to_facts`;
`backend/app/services/copilot_service.py::_fact_certifies_claim`;
`backend/tests/unit/test_copilot_citation_repair.py::test_quarterly_point_in_an_annual_filing_never_certifies`
drives the whole transformation through production code.

**Correction (2026-09-12, later the same day):** extraction now preserves the source duration
forward-only, so the first sentence above describes existing rows, not new ones. The per-filing instance
path carries the selected fact's own start: `instance_extractor.duration_series_with_starts` (the
proof `duration_in_window` already applied, no longer discarded at the tuple boundary),
`normalise_series` passes the key through and `normalize_standardized_to_facts` stores it in the
existing nullable column. The companyfacts fallback still drops its start — the locked T9 anchor
pins those emitted points by full-dict equality, so carrying it there is a contract change needing
pre-approval; those facts keep an unknown duration and keep abstaining.
Selection, precedence and the upsert's skip semantics are unchanged, and a short-duration point in
an annual filing is still KEPT — annual filings legitimately disclose quarters — but now carries
its real duration so a consumer can refuse it for an annual claim. The rule is unchanged and now
has teeth: a start is taken only from the selected source fact, never inferred, and equal-valued
facts that disagree on their start leave it NULL. Rows written before this still carry NULL and
still abstain; there is no backfill.
