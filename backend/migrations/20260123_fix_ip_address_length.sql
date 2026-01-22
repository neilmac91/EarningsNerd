-- Fix ip_address column length for SHA-256 hashes
-- SQLite does not support altering column type directly, so we just add a comment for documentation
-- In SQLite, VARCHAR length constraints are not enforced anyway, so the existing schema works fine.
-- This file serves as documentation that we expect 64-char strings now.

-- For PostgreSQL (if migrated later):
-- ALTER TABLE contact_submissions ALTER COLUMN ip_address TYPE VARCHAR(64);
