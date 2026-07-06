# Make destructive bulk deletes FK-safe by construction, not by trusting the test DB

Date: 2026-06-30   Area: arch

**Context**: `saved_summaries.summary_id → summaries.id` has no `ondelete`, so in Postgres a bulk `DELETE FROM summaries` referenced by a bookmark RAISES (NO ACTION). SQLite (the test DB) doesn't enforce FKs by default, so no test would surface it. The bulk reset-all endpoint therefore skips pinned rows by design.

**Rule**: A destructive bulk delete must be FK-safe by construction, not by trusting the test DB — SQLite-green ≠ Postgres-safe for referential integrity.

**Evidence**: `saved_summaries.summary_id → summaries.id` with no `ondelete`; Postgres NO ACTION raises on `DELETE FROM summaries`; SQLite doesn't enforce FKs by default.
