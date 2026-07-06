# No Alembic — fresh schema via create_all; every table change is an idempotent SQL file re-applied each deploy

**Area:** deploy · **Date:** 2026-07-06

There is no Alembic. A fresh DB gets its schema from `Base.metadata.create_all()` at startup. ANY change to an existing table is a new hand-written `.sql` file in `backend/migrations/`, and CI re-applies ALL of them on every deploy.

**Rule:** every migration must be safe to run repeatedly (`ADD COLUMN IF NOT EXISTS`, guarded constraints). Never edit an applied migration. And never run schema-altering DDL in the serving container's startup path (see the rolling-deploy lesson) — migrations run out-of-band in the deploy job.
