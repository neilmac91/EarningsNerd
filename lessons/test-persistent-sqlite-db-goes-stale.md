# The test SQLite DB (backend/earningsnerd.db) is a persistent file — rm it after a schema change or rebase

Date: 2026-07-06   Area: test

**Context**: The test `DATABASE_URL` is `sqlite:///./earningsnerd.db` — a PERSISTENT file,
not in-memory. `create_all()` only CREATES missing tables; it never ALTERs an existing one.
So after a model gains a column (your change, or a merge/rebase that brings one in), the
on-disk DB is stale and tests fail with
`sqlite3.OperationalError: no such column: <table>.<col>` on tables the diff never touched.
The executing session hit this twice during the refactor: `companies.facts_synced_at` in the
S5 sweep, and `trend_analysis.unverified` after the #560 rebase.

**Rule**: When a full-suite run fails with `no such column` on a table you didn't touch,
suspect the stale persistent DB first — `rm -f backend/earningsnerd.db` and re-run
(`create_all` rebuilds the current schema). Check for this immediately after a rebase onto
main or any merged model change; it is orthogonal to your diff.

**Evidence**: PR #567 (the executing session's seed lesson; two occurrences documented);
`backend/app/database.py` (`create_all` semantics — creates, never alters).
