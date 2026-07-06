# Never run schema-altering DDL in the serving container's startup path on a rolling-deploy platform

**Area:** deploy · **Date:** 2026-06-24

To make deploys "self-safe" I added a startup migration runner that applied `migrations/*.sql` in the
FastAPI lifespan. It broke the prod deploy: `ALTER TABLE users ADD COLUMN is_beta` needs an
`ACCESS EXCLUSIVE` lock on `users`, but during a Cloud Run **rolling deploy the old revision is still
serving** and holds `AccessShare` locks on `users` — so the ALTER blocked/timed-out and crashed the
new revision's startup ("failed to start and listen on PORT within the timeout"). CI never caught it:
CI runs on **SQLite**, where the Postgres-only runner is skipped, so the PG path was completely
unexercised. (Prod stayed up — Cloud Run keeps the last healthy revision when a new one fails.)

**Rule:** never run schema-altering DDL (ADD COLUMN/constraint/index on a hot table) inside the
serving container's startup/health-check path on a rolling-deploy platform — it races the healthcheck
and contends with the draining old revision. Apply column/table ALTERs **out-of-band**: manually
before the deploy (psql waits patiently for the lock), or via a dedicated pre-deploy migration job —
never in `lifespan`. And remember: a Postgres-only code path that CI exercises only on SQLite is
**effectively untested** — treat it as such before shipping it to prod.
