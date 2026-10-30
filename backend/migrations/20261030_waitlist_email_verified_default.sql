-- E245, the first of two steps: WaitlistSignup no longer maps email_verified, so the serving code's
-- inserts leave the column out. It stays NOT NULL until the second step drops it, so an insert that
-- omits it needs a database default. The table's CREATE migration gave it DEFAULT FALSE, but a table
-- that create_all made first has none (the model's default was Python-side), so set it where it is
-- missing. Guarded so that a replay, or a table that already has the default, takes no lock that
-- blocks readers or writers: the guard's catalog read takes ACCESS SHARE, which only an ACCESS
-- EXCLUSIVE holder blocks. migration_ledger owns application of this file.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'waitlist_signups'
          AND column_name = 'email_verified' AND column_default IS NULL
    ) THEN
        ALTER TABLE waitlist_signups ALTER COLUMN email_verified SET DEFAULT FALSE;
    END IF;
END $$;
