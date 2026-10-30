-- E245, the second of two steps: drop waitlist_signups.email_verified, whose value nothing has used
-- since E46 (2). The first step (20261030_waitlist_email_verified_default.sql) stopped mapping it and
-- gave it a database default. This file merges only once the first step's deploy-backend job is green,
-- so the code serving while it runs maps no such column. The review gate holds the order of the two
-- steps, and review holds the wait for that deploy:
-- lessons/ops-drop-a-mapped-column-in-two-deploys.md. Guarded so that a replay, or a table without the
-- column, takes no lock that blocks readers or writers: the guard's catalog read takes ACCESS SHARE. The
-- DROP takes ACCESS EXCLUSIVE for a catalog change, with no table rewrite; apply_migrations.sh bounds the
-- wait for it with lock_timeout and retries. The drop discards the column's values.
-- migration_ledger owns application of this file.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'waitlist_signups'
          AND column_name = 'email_verified'
    ) THEN
        ALTER TABLE waitlist_signups DROP COLUMN email_verified;
    END IF;
END $$;
