# A destructive bulk delete must be FK-safe by construction — SQLite-green is not Postgres-safe

**Area:** testing · **Date:** 2026-06-30

`saved_summaries.summary_id → summaries.id` has no `ondelete`, so in **Postgres** a bulk
`DELETE FROM summaries` referenced by a bookmark RAISES (NO ACTION). SQLite (the test DB) doesn't
enforce FKs by default, so a test would NOT surface it. The bulk reset-all endpoint therefore skips
pinned rows by design (FK-safe) regardless of the test DB's leniency.
**Rule:** a destructive bulk delete must be FK-safe by construction, not by trusting the test DB —
SQLite-green ≠ Postgres-safe for referential integrity.
