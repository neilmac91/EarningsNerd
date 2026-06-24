-- Security hardening (roadmap Week 7): enforce one-provider-identity-per-account at the DB level.
-- The OAuth login resolver assumes (provider, provider_account_id) is unique; without this index a
-- race between concurrent OAuth callbacks for the same provider `sub` could insert duplicate links
-- and make `.first()` resolve non-deterministically. Mirrors the UniqueConstraint now on the
-- OAuthAccount model (create_all builds it for fresh DBs; this migration covers the existing one).
-- Idempotent.
--
-- NOTE: assumes no existing duplicate (provider, provider_account_id) rows (true pre-launch). If
-- this errors on a duplicate, dedupe first (keep MIN(id) per pair) and re-run.
BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_oauth_provider_account
    ON oauth_accounts (provider, provider_account_id);

COMMIT;
