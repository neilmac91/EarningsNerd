-- PB-02: the complimentary Pro grant ledger for invited private-beta accounts (docs/ops/complimentary-access.md).
-- Provenance only: the plan stays the is_pro fallback entitlements.py resolves, and this row records that an
-- operator's grant set it. No backfill: no account holds a complimentary grant before the first apply.
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
