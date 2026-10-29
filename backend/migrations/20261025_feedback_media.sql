-- Private feedback media: durable receipts and object manifests survive account deletion.
-- New tables only; repeat application does not lock an existing business table.
CREATE TABLE IF NOT EXISTS feedback_submissions (
    id VARCHAR(36) PRIMARY KEY,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    submission_key VARCHAR(36) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    state VARCHAR(20) NOT NULL,
    attempt_token VARCHAR(36) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    feedback_id INTEGER REFERENCES feedback(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_feedback_submission_owner_key UNIQUE (owner_id, submission_key)
);
CREATE INDEX IF NOT EXISTS ix_feedback_submissions_owner_created
    ON feedback_submissions(owner_id, created_at);

CREATE TABLE IF NOT EXISTS feedback_attachments (
    id VARCHAR(36) PRIMARY KEY,
    submission_id VARCHAR(36) NOT NULL REFERENCES feedback_submissions(id) ON DELETE RESTRICT,
    attempt_token VARCHAR(36) NOT NULL,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    feedback_id INTEGER REFERENCES feedback(id) ON DELETE SET NULL,
    object_key VARCHAR(200) NOT NULL UNIQUE,
    object_generation VARCHAR(40),
    checksum VARCHAR(64) NOT NULL,
    content_type VARCHAR(30) NOT NULL DEFAULT 'image/png',
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    byte_count INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    state VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    deletion_due_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ,
    cleanup_attempts INTEGER NOT NULL DEFAULT 0,
    last_cleanup_attempt_at TIMESTAMPTZ,
    last_cleanup_error VARCHAR(80)
);
CREATE INDEX IF NOT EXISTS ix_feedback_attachments_cleanup ON feedback_attachments(state, deletion_due_at);
CREATE INDEX IF NOT EXISTS ix_feedback_attachments_feedback ON feedback_attachments(feedback_id);
CREATE INDEX IF NOT EXISTS ix_feedback_attachments_owner ON feedback_attachments(owner_id);
CREATE INDEX IF NOT EXISTS ix_feedback_attachments_submission ON feedback_attachments(submission_id, attempt_token);
