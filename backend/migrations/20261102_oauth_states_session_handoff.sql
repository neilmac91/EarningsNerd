-- Whether an OAuth start asked for the one-time session handoff (E29 (5)): OAuthState.session_handoff
-- (app/models/__init__.py). Only a frontend with the /auth/complete landing page asks. False (a start that did not ask)
-- and NULL (a row written before this column) take the callback path that sets the session cookies on its redirect,
-- so the frontend and the API roll back independently. No backfill: a state row lives ten minutes.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
                   AND table_name = 'oauth_states' AND column_name = 'session_handoff') THEN
        ALTER TABLE oauth_states ADD COLUMN session_handoff BOOLEAN;
    END IF;
END $$;
