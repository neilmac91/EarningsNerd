-- PB-02 (EN-BETA-2026-11): deleting an account that had generated a cached Multi-Period Analysis failed on PostgreSQL.
-- trend_analysis.created_by_user_id references users(id) with no ON DELETE action, so the account's DELETE broke that
-- reference, and a complimentary beta grant opens analysis generation to every invited tester. The analysis is a shared
-- cache row (one per company, mode and period range), so the account's deletion now clears its stamp and keeps the row
-- for its other readers: the reference becomes ON DELETE SET NULL, as the model declares it.
--
-- Locks. apply_migrations.sh runs this file through psql outside a transaction block, so each statement below commits
-- on its own; tests/integration/test_subscription_event_transactions.py reads the locks each one holds.
-- 1. The swap drops the reference that does not set null and adds one that does, NOT VALID: catalog changes, no scan.
--    Dropping a foreign key takes ACCESS EXCLUSIVE on users as well as on trend_analysis (the reference's triggers are
--    on users), held until the swap commits. While the swap waits for that lock, every new query on users waits behind
--    it, so this file waits at most 2 s (not the session's 10 s) before apply_migrations.sh retries it (5 attempts,
--    15 s apart). Deploy it in a quiet window (docs/ops/complimentary-access.md, "Deploying").
-- 2. The validation then commits on its own: VALIDATE CONSTRAINT takes SHARE UPDATE EXCLUSIVE on trend_analysis and
--    ROW SHARE on users, which stop no read or write of either while it checks every row against users.
-- Each step reads the catalog first, so a re-run, or a retry after the swap committed, repeats nothing it did.
SET lock_timeout = '2s';
DO $$
DECLARE
    stale TEXT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = to_regclass('trend_analysis') AND c.contype = 'f' AND c.confrelid = to_regclass('users')
          AND a.attname = 'created_by_user_id' AND c.confdeltype <> 'n'
    ) THEN
        FOR stale IN
            SELECT c.conname FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.conrelid = to_regclass('trend_analysis') AND c.contype = 'f' AND c.confrelid = to_regclass('users')
              AND a.attname = 'created_by_user_id' AND c.confdeltype <> 'n'
        LOOP
            EXECUTE 'ALTER TABLE trend_analysis DROP CONSTRAINT ' || quote_ident(stale);
        END LOOP;
    END IF;
    IF to_regclass('trend_analysis') IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = to_regclass('trend_analysis') AND c.contype = 'f' AND c.confrelid = to_regclass('users')
          AND a.attname = 'created_by_user_id'
    ) THEN
        ALTER TABLE trend_analysis ADD CONSTRAINT trend_analysis_created_by_user_id_fkey
            FOREIGN KEY (created_by_user_id) REFERENCES users (id) ON DELETE SET NULL NOT VALID;
    END IF;
END $$;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('trend_analysis') AND conname = 'trend_analysis_created_by_user_id_fkey'
          AND NOT convalidated
    ) THEN
        ALTER TABLE trend_analysis VALIDATE CONSTRAINT trend_analysis_created_by_user_id_fkey;
    END IF;
END $$;
RESET lock_timeout;
