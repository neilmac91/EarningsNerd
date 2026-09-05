# Give deploy-owned tables a name nothing else could have created; CREATE TABLE IF NOT EXISTS adopts strangers

Date: 2026-09-05   Area: ops

**Context**: ADR-0007's migration ledger was created by `backend/scripts/apply_migrations.sh` with
`CREATE TABLE IF NOT EXISTS schema_migrations (filename, sha256, applied_at)`. The first production
deploy (CI run 33941732087, main `c6eaddf`) failed with `column "sha256" does not exist`: prod
already had a `schema_migrations` table of a different shape, created outside this repository at
some point in the past (no commit ever mentioned the name before the ADR). `IF NOT EXISTS` adopted
it silently, the ledger read failed, and the deploy stopped before touching Cloud Run. The
`migrations-postgres` CI job passed three times on the same commit because its database is fresh —
a fresh database can never contain a stranger.

**Rule**: State that a deploy script owns and creates for itself (ledgers, locks, bookkeeping) gets
a project-specific name (`migration_ledger`), never a conventional one (`schema_migrations`,
`migrations`, `versions`, `alembic_version`) that another tool or a past hand could plausibly have
created. Pair `CREATE TABLE IF NOT EXISTS` with a gate that proves the script does not depend on the
conventional name: CI plants a decoy table under that name before the first pass. When a deploy
fails on a table the code "just created", suspect a pre-existing table before suspecting the DDL.

**Evidence**: `backend/scripts/apply_migrations.sh` (header + ledger DDL); `.github/workflows/ci.yml`
`migrations-postgres` → "Plant a decoy schema_migrations table"; `tests/unit/test_migration_lock_safety.py`
(`LEGACY_LEDGER_NAME`, decoy-before-pass-1 pin); `docs/adr/0007-schema-migrations-ledger.md`
amendment 2026-09-05; failed run
https://github.com/neilmac91/EarningsNerd/actions/runs/33941732087/job/101240714066.
