-- PB-02: the complimentary Pro grant ledger for invited private-beta accounts (docs/ops/complimentary-access.md).
-- Provenance only: the plan stays the is_pro fallback entitlements.py resolves, and this row records that an
-- operator's grant set it. No backfill: no account holds a complimentary grant before the first apply.
--
-- Locks. Creating the table's reference to users takes SHARE ROW EXCLUSIVE on users for a catalog change (the
-- reference's triggers are on users): reads of users go on, and writes wait until the CREATE commits. While it waits
-- for that lock, writes to users wait behind it, so this file waits at most 2 s (not the session's 10 s) before
-- apply_migrations.sh retries it; tests/integration/test_subscription_event_transactions.py reads the lock it holds.
-- A re-run finds the table and takes no lock on users.
SET lock_timeout = '2s';
CREATE TABLE IF NOT EXISTS earningsnerd_complimentary_access_grants (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    cohort VARCHAR(64) NOT NULL,
    reason VARCHAR(200) NOT NULL,
    review_on DATE NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL,
    granted_by VARCHAR(64) NOT NULL,
    manifest_sha256 VARCHAR(64) NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by VARCHAR(64),
    revoke_reason VARCHAR(200),
    CONSTRAINT ck_earningsnerd_complimentary_access_grants_revocation CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL)
        OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revoke_reason IS NOT NULL)
    )
);
RESET lock_timeout;
