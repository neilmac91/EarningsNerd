-- In-app notification bell: per-user "last opened the bell" timestamp.
-- Unread count = notification_log rows newer than this (or all rows if NULL).
--
-- Additive only, idempotent (safe to re-run). The column does NOT auto-add via
-- Base.metadata.create_all() since `users` already exists, so this file is required for prod.

BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS notifications_seen_at TIMESTAMPTZ;

COMMIT;
