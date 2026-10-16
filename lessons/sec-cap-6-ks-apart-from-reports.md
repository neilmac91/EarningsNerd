# Cap 6-Ks apart from the reports: one row cap across forms lets a daily 6-K filer hide its 20-F

Date: 2026-10-16   Area: sec

**Context**: With foreign-issuer forms on, the company filings list serves 10-K, 10-Q, 20-F, 6-K
and 40-F under ONE row cap: 50 rows materialized from SEC's recent submissions window
(`edgar/client.py::get_filings_multi`) and 20 rows on the DB-first serve
(`filing_list_service.cached_filings`). The cap's comment assumed every listed form is "a few per
year". A 6-K is not: BP, Shell and HSBC furnish one most business days (buyback notices). About 50
of them fill the live cap within ten weeks, so a 20-F filed earlier in the window was never returned
or stored by the list path, and 20 of them hid even a stored 20-F from the default list. The
company page lost the issuer's annual report, its year groups and the "Compare periods" pair.

**Rule**: A cap on a mixed-form filings list budgets per form group, not across all forms: 6-K
and 6-K/A take a budget of their own, and the other forms keep theirs. Both paths read the group
from `FilingType.is_interim`, so they cannot drift apart. An explicit `?limit=N` caps each group,
so a foreign issuer's response can hold up to 2N rows. A domestic list (no 6-K
requested, or none filed) stays exactly the newest N. Before adding a cap or a `LIMIT` to any list
that mixes form types, ask which form can be filed daily (6-K; 8-K and Form 4 if they ever join a
list) and give it its own budget. A bounded single-latest caller that asked for the newest N across
forms keeps that meaning.

**Evidence**: `backend/app/services/edgar/client.py` (`_take_recent`, `RECENT_FILINGS_MATERIALIZE_CAP`),
`backend/app/services/filing_list_service.py::cached_filings`. Partly gated:
`backend/tests/unit/test_filings_endpoint_db_first.py` (`test_live_list_keeps_the_20f_behind_sixty_newer_6ks`,
`test_cached_list_keeps_the_20f_behind_sixty_newer_6ks`, `test_domestic_lists_are_unchanged_by_the_6k_budget`)
pins the company filings list; a new mixed-form list surface is review-checked.
