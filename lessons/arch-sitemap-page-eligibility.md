# Match sitemap eligibility to the existing page predicates

Date: 2026-09-06   Area: arch

**Context**: The sitemap accepted any nonempty summary and every company with a filing.
The filing server rejects the exact `Generating summary` substring, and the company route
rejects curated unsupported foreign issuers before consulting even a stale database row.

**Rule**: Apply the existing displayable-summary predicate before the filing URL limit and
reuse `unsupported_foreign_name` for company eligibility. Preserve genuine partial content;
this is page parity, not a new summary-quality threshold. Keep hourly cache ownership and
truthful dates unchanged. A filing-only cap does not bound the whole sitemap document.

**Evidence**: `backend/tests/unit/test_sitemap.py` checks placeholder exclusion before the cap,
case-sensitive partial-content retention, and unsupported company exclusion with a supported
foreign peer. Existing cases protect static entries, dates, cache reuse and single-flight.
The page rules live in `frontend/lib/serverApi.ts::summaryHasDisplayableContent` and
`backend/app/services/company_coverage.py::unsupported_foreign_name`.
