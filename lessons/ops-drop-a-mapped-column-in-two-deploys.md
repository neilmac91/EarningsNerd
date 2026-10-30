# Drop a column the serving code maps in two deploys: stop mapping it in one, drop it in a later one

**Date:** 2026-10-30 · **Area:** ops / migrations / deploy

## Context

E245 is the repository's first column drop: `waitlist_signups.email_verified`, whose value nothing has used since
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
   every read and insert of a whole row (a count still works), and `ops.yml`'s rollback takes any revision. Name the
   limit in `docs/DEPLOYMENT.md`'s rollback section, where a responder looks, as E245's is.

The review gate holds rule 2's order, not its wait. It fails a pull request whose migration drops a column the base
branch's models still map (`backend/scripts/review_gate.py`, "Dropped columns"; `backend/tests/unit/test_review_gate.py`),
so step 2 cannot merge before step 1, nor with it. It reads the base as the pull request would merge into it, not the
deploy: whether step 1's `deploy-backend` job is green before step 2 merges stays review-checked, as AGENTS.md §6's wait
for a backend merge's deploy does. It reads each migration the pull request adds or changes at its head, and the base's
models from the checkout the workflow makes, by their source. Since the workflow runs the base's script, a change to
the gate first checks the pull request after the one that makes it: E245's step 1 added it, so step 2 is the first drop
it checks. `test_migration_lock_safety.py` holds rule 2's guard. Rules 1 and 3 stay review-checked, and so do a renamed
column, a dropped table and a changed type, which break the serving code the same way.

## Evidence

- `backend/migrations/20261030_waitlist_email_verified_default.sql` is step 1 of E245. On PostgreSQL 16 locally:
  - On a table `create_all` made from the model before step 1, the new model's insert was refused with
    `NotNullViolation` before the file ran, and inserted `false` after it.
  - On the same table, the old model's insert (the code still serving) also inserted `false`.
  - A replay of the file under a held reader went through. Its guard's catalog read takes ACCESS SHARE, so only an
    ACCESS EXCLUSIVE holder blocks it.
  - CI's triple pass runs the file on PostgreSQL 15, but it seeds `create_all` from the new model, so CI runs only
    the file's no-op branch.
- `backend/migrations/20261030_waitlist_email_verified_drop.sql` is step 2, which merges only once step 1's
  `deploy-backend` job is green. On PostgreSQL 16 locally:
  - On tables made both ways and brought to step 1's state, it dropped the column and kept every row, with no table
    rewrite.
  - Under a held reader it hit the lock timeout, which `apply_migrations.sh` retries.
  - Replays of either step were no-ops.
  - The model before step 1 (`f125759e2`) was then refused with `UndefinedColumn`, the failure step 1's deploy had to
    come first to avoid; a count of the table still worked.
  - Through `apply_migrations.sh` after step 1's files it applied alone (applied=1 skipped=51), and after a ledger
    reset all 52 applied again, the column staying dropped.
  - CI's triple pass seeds `create_all` from step 2's models, so it runs only the file's no-op branch: the DROP ran
    only in these local runs, on PostgreSQL 16, where production runs 15.
- `.github/workflows/ci.yml`: the `deploy-backend` steps, migrations first.
- The gate on the real models: step 2's migration fails it against the models before step 1, which map the column
  (step 1 and step 2 in one pull request), and passes it against step 1's.
