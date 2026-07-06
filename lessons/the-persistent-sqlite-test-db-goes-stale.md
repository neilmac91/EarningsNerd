# The test SQLite DB (earningsnerd.db) is a persistent file — rm it after a schema change or rebase

**Area:** testing · **Date:** 2026-07-06

The test `DATABASE_URL` is `sqlite:///./earningsnerd.db` — a PERSISTENT file, not in-memory. `create_all()` only CREATES missing tables; it never ALTERs an existing one. So after a model gains a column (a merge/rebase that adds one), the on-disk DB is stale and tests fail with `sqlite3.OperationalError: no such column: <table>.<col>`. Hit twice this refactor (`companies.facts_synced_at` in S5; `trend_analysis.unverified` after the #560 rebase).

**Rule:** when a full-suite run fails with `no such column` on a table you didn't touch, it's the stale persistent DB — `rm -f backend/earningsnerd.db` and re-run (create_all rebuilds the current schema). Suspect this immediately after a rebase onto main or a merged model change; it is orthogonal to your diff.
