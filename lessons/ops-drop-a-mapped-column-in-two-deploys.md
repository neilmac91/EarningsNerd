# Drop a column the serving code maps in two deploys: stop mapping it in one, drop it in a later one

**Date:** 2026-10-30 · **Area:** ops / migrations / deploy

## Context

E245 is the repository's first column drop: `waitlist_signups.email_verified`, which nothing has read or set since
E46 (2).

`deploy-backend` applies a merge's migrations before anything that runs its code: the task worker, the service and
the job images (`ci.yml`: "Apply database migrations" runs first). Until those finish, the old code serves, and its
model maps the column into every read and insert of the table. A drop in the same deploy that unmaps the column would
fail those reads and writes for the window, `GET /api/waitlist/status/{email}` among them. A failed deploy is not
retried, so a deploy that failed after its migrations would leave them failing until someone noticed.

The unmapping step has a trap of its own. A NOT NULL column the model stops mapping needs a database default, or the
new code's inserts fail. `create_all` gives a column only its `server_default`, never the model's Python-side
`default=`. On a table `create_all` made from the old model, the new model's insert was refused with
`NotNullViolation` until the step-1 migration set `DEFAULT FALSE`. On the table the CREATE migration made, which
declared the default, the same file was a no-op.

## Rule

1. **Step 1, its own pull request:**
   - The model stops mapping the column.
   - If the column is NOT NULL, a guarded migration gives it a database default where it lacks one
     (`ALTER COLUMN … SET DEFAULT`) or drops NOT NULL, so the old code and the new can both insert during the
     rollout.
   - A database `create_all` made from the old model, a local one included, needs that migration too.
2. **Step 2, a later pull request, once step 1's `deploy-backend` job is green:** a guarded migration drops the
   column (`DO $$ … IF EXISTS (… information_schema.columns …) THEN ALTER TABLE … DROP COLUMN … END IF $$`), per
   `lessons/ops-migrations-need-lock-timeout.md`.
3. **After step 2, roll traffic back no further than step 1's revision.** An older revision maps the column and fails
   every read of the table, and `ops.yml`'s rollback takes any revision.

E245's step 2 lands a gate for rule 2: a pull request whose migration drops a column that main's models still map
fails. Until then, review checks it.

## Evidence

- `backend/migrations/20261030_waitlist_email_verified_default.sql` is step 1 of E245. On PostgreSQL 16 locally:
  - On a table `create_all` made from main's model, the new model's insert was refused with `NotNullViolation` before
    the file ran, and inserted `false` after it.
  - On the same table, the old model's insert (the code still serving) also inserted `false`.
  - A replay of the file under a held reader went through. Its guard's catalog read takes ACCESS SHARE, so only an
    ACCESS EXCLUSIVE holder blocks it.
  - CI's triple pass runs the file on PostgreSQL 15, but it seeds `create_all` from the new model, so CI runs only
    the file's no-op branch.
- `.github/workflows/ci.yml`: the `deploy-backend` steps, migrations first.
