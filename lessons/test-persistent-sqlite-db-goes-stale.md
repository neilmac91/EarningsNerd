# The dev SQLite DB (backend/earningsnerd.db) is persistent — rm it after a schema change; the test suite never uses it

Date: 2026-07-06 (revised 2026-10-09)   Area: test

**Context**: The default `DATABASE_URL` is `sqlite:///./earningsnerd.db` — a PERSISTENT file,
not in-memory, created relative to the process's CWD (`backend/earningsnerd.db` under
`cd backend`). `create_all()` only CREATES missing tables; it never ALTERs an existing one.
Until 2026-10-09 the test suite used that same file, so after a model gained a column the on-disk
DB was stale and tests failed with `sqlite3.OperationalError: no such column: <table>.<col>` on
tables the diff never touched (twice in the S5 refactor: `companies.facts_synced_at`, and
`trend_analysis.unverified` after the #560 rebase).

Since 2026-10-09 `backend/tests/conftest.py` gives every pytest process a fresh SQLite file in a
temp directory, built from the current models by `create_all` and removed at exit. A test run can
no longer see a stale schema, and it never reads or writes `backend/earningsnerd.db`.

**Rule**: A `no such column` error from the dev server (`uvicorn main:app` on the SQLite default)
means a stale `backend/earningsnerd.db`: `rm -f backend/earningsnerd.db` and restart
(`create_all` rebuilds the current schema). The same error in a test run is real — the model and
the code disagree — not a stale file.

**Evidence**: PR #567 (the original lesson; two occurrences documented);
`backend/app/database.py` (`create_all` semantics — creates, never alters);
`backend/tests/conftest.py` and `backend/tests/unit/test_suite_isolation.py` (the
per-process temp database).
