# Pin a commit that follows a SAVEPOINT with a commit spy; under SQLite the RELEASE already committed the row

Date: 2026-10-09   Area: test

**Context**: Lane B moved the get-by-ticker and company-filings miss paths'
`resolve_or_create_company_by_cik(...); db.commit()` into services (#1163, #1164). Review round 2
on both PRs found the same blind spot: the tests proved the commit only by reading the new row
back. The resolver writes inside `with db.begin_nested():`.

pysqlite's legacy transaction control sends no `BEGIN` before a SELECT. When no write comes before
`begin_nested()`, its SAVEPOINT is the outermost transaction on the connection, and `RELEASE`
commits it. So a service that skipped its own commit (`if db.dirty or db.new: db.commit()`) passed
every test in both suites. The same mutant placed in the base companies router passed that
router's tests too, so the gap predates the move. On Postgres the same mutant leaves the
row inside an outer transaction that the request's close rolls back: the response serves an id
that was never stored.

Counting the session's `after_commit` events does not isolate the commit either. They fire for the
SAVEPOINT's release as well, so one explicit commit counted as 2.

**Rule**:
- When the code under test commits after a `begin_nested()` block, a row count or read-back
  assertion does not prove that commit ran. Pin the commit itself:
  - Serve the route a session whose `commit` is wrapped by a counter, through a `get_db`
    override.
  - Assert the count where it matters, for example before the next await.
- Don't count `after_commit` events for this, because the SAVEPOINT release fires them too.
- Prove the pin with the conditional-commit mutant (`if db.dirty or db.new: db.commit()`). It must
  fail, and every other test in the file should still pass.

**Evidence**:
- `backend/app/services/company_resolution.py` (`with db.begin_nested():` in
  `resolve_or_create_company_by_cik`).
- `backend/tests/unit/test_company_routes.py::test_miss_persists_the_sec_hit_under_its_primary_ticker`
  (#1163, `_spy_commits`). The mutant fails it with `[] == [0]`.
- `backend/tests/unit/test_filings_routes.py::test_company_miss_persists_the_sec_company_and_serves_its_live_list`
  (#1164). `after_commit` counted `[2]` before the live fetch; the explicit-commit spy counts `[1]`;
  the mutant fails it with `[0] == [1]`.
