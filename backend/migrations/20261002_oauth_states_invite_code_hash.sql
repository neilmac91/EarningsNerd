-- A closed-beta invite carried through a social sign-in (GET /api/auth/google|apple?invite=...)
-- rides on the OAuth state row as its SHA-256 hash, so the callback can validate and redeem it
-- when it creates the account. NULL for a plain sign-in. Nullable and additive for safe rolling
-- deployment; database.ensure_additive_columns self-heals it at startup as well.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'oauth_states'
          AND column_name = 'invite_code_hash'
    ) THEN
        ALTER TABLE oauth_states ADD COLUMN invite_code_hash VARCHAR(64);
    END IF;
END $$;
