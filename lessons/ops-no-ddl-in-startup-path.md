# Never run schema-altering DDL in the serving container's startup path

Date: 2026-06-24   Area: ops

**Context**: A startup migration runner applying `migrations/*.sql` in the FastAPI lifespan broke the prod deploy: the ALTER needs an ACCESS EXCLUSIVE lock on `users`, but during a Cloud Run rolling deploy the old revision still serves and holds AccessShare locks — so the ALTER blocked/timed out and crashed the new revision's startup. CI never caught it because CI runs on SQLite where the Postgres-only runner is skipped. Prod stayed up only because Cloud Run keeps the last healthy revision.

**Rule**: Never run schema-altering DDL (ADD COLUMN/constraint/index on a hot table) inside the serving container's startup/health-check path on a rolling-deploy platform — it races the healthcheck and contends with the draining old revision. Apply ALTERs out-of-band: manually before the deploy (psql waits for the lock) or via a dedicated pre-deploy migration job — never in `lifespan`. Treat a Postgres-only code path that CI exercises only on SQLite as effectively untested.

**Evidence**: `ALTER TABLE users ADD COLUMN is_beta` needs `ACCESS EXCLUSIVE`; Cloud Run error "failed to start and listen on PORT within the timeout"; CI runs on SQLite so the PG path was unexercised.
