# Make destructive bulk deletes FK-safe by construction, not by trusting the test DB

Date: 2026-06-30   Area: arch

**Context**: `saved_summaries.summary_id → summaries.id` has no `ondelete`, so in Postgres a bulk `DELETE FROM summaries` referenced by a bookmark RAISES (NO ACTION). SQLite (the test DB) doesn't enforce FKs by default, so no test would surface it. The bulk reset-all endpoint therefore skips pinned rows by design. A forced precompute later deleted the summary before regenerating it, with no such skip (2026-10-15 bug hunt, finding 7; fixed in P11 by regenerating in place).

**Rule**: A destructive bulk delete must be FK-safe by construction, not by trusting the test DB — SQLite-green ≠ Postgres-safe for referential integrity.

**Gate** (partly gated, 2026-10-22): `backend/tests/unit/test_summary_delete_sites_allowlist.py` lists every delete of `summaries` rows its scan can see in the code, scripts, migrations, ops and task SQL, shell scripts and workflows, and pins that nothing deletes them by cascade, so a new delete it sees fails until a review has checked it is FK-safe and listed it. Whether a listed site is FK-safe is review-checked, and so is a delete the scan cannot see (named in its docstring: a model or table chosen at run time, SQL assembled with `%`, `.format` or `join`, a row handed to a helper in a module that never names the model). A test that needs PostgreSQL's FK behaviour on SQLite turns on `PRAGMA foreign_keys=ON` (`test_precompute_service.py` does).

**Evidence**: `saved_summaries.summary_id → summaries.id` with no `ondelete`; Postgres NO ACTION raises on `DELETE FROM summaries`; SQLite doesn't enforce FKs by default.
