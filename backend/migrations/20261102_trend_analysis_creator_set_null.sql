-- PB-02 (EN-BETA-2026-11): deleting an account that had generated a cached Multi-Period Analysis failed on PostgreSQL.
-- trend_analysis.created_by_user_id references users(id) with no ON DELETE action, so the account's DELETE broke that
-- reference, and a complimentary beta grant opens analysis generation to every invited tester. The analysis is a shared
-- cache row (one per company, mode and period range), so the account's deletion now clears its stamp and keeps the row
-- for its other readers: the reference becomes ON DELETE SET NULL, as the model declares it.
--
-- The reference is found by its column, not by a name, and is replaced only while it does not already set null. The new
-- one is added NOT VALID and validated after, so the lock on users lasts only for the catalog change: every row already
-- satisfies the reference it had. Each step reads the catalog first, so a re-run changes nothing.
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
        SELECT c.conname INTO stale FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = to_regclass('trend_analysis') AND c.contype = 'f' AND c.confrelid = to_regclass('users')
          AND a.attname = 'created_by_user_id' AND c.confdeltype <> 'n'
        LIMIT 1;
        EXECUTE 'ALTER TABLE trend_analysis DROP CONSTRAINT ' || quote_ident(stale);
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
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('trend_analysis') AND conname = 'trend_analysis_created_by_user_id_fkey'
          AND NOT convalidated
    ) THEN
        ALTER TABLE trend_analysis VALIDATE CONSTRAINT trend_analysis_created_by_user_id_fkey;
    END IF;
END $$;
