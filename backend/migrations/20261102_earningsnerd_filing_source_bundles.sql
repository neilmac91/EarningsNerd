-- Default-off immutable primary/exhibit source metadata. No source-body/backfill writes.
CREATE TABLE IF NOT EXISTS earningsnerd_filing_source_bundles (
    id VARCHAR(64) PRIMARY KEY,
    identity_sha256 VARCHAR(64) NOT NULL UNIQUE,
    filing_id INTEGER NOT NULL REFERENCES filings(id),
    cik VARCHAR(20) NOT NULL,
    accession VARCHAR(18) NOT NULL,
    filing_type VARCHAR(10) NOT NULL,
    primary_filename VARCHAR(255) NOT NULL,
    schema_version INTEGER NOT NULL,
    selection_version VARCHAR(60) NOT NULL,
    member_count INTEGER NOT NULL CONSTRAINT ck_filing_source_member_count CHECK (member_count BETWEEN 1 AND 4),
    byte_length INTEGER NOT NULL CONSTRAINT ck_filing_source_bundle_bytes CHECK (byte_length BETWEEN 1 AND 33554432),
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_earningsnerd_filing_source_bundles_filing_id
    ON earningsnerd_filing_source_bundles(filing_id);
CREATE TABLE IF NOT EXISTS earningsnerd_filing_source_members (
    bundle_id VARCHAR(64) NOT NULL REFERENCES earningsnerd_filing_source_bundles(id),
    ordinal INTEGER NOT NULL CONSTRAINT ck_filing_source_member_ordinal CHECK (ordinal BETWEEN 0 AND 3),
    role VARCHAR(10) NOT NULL CONSTRAINT ck_filing_source_member_role CHECK (role IN ('primary', 'exhibit')),
    filename VARCHAR(255) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    byte_length INTEGER NOT NULL CONSTRAINT ck_filing_source_member_bytes CHECK (byte_length BETWEEN 1 AND 33554432),
    representation VARCHAR(60) NOT NULL,
    content_type VARCHAR(160) NOT NULL,
    content_encoding VARCHAR(20) NOT NULL,
    storage_generation VARCHAR(20) NOT NULL,
    PRIMARY KEY (bundle_id, ordinal),
    CONSTRAINT uq_filing_source_member_filename UNIQUE (bundle_id, filename)
);
CREATE TABLE IF NOT EXISTS earningsnerd_filing_source_extractions (
    id VARCHAR(64) PRIMARY KEY,
    bundle_id VARCHAR(64) NOT NULL REFERENCES earningsnerd_filing_source_bundles(id),
    decoder_version VARCHAR(60) NOT NULL,
    extractor_version VARCHAR(60) NOT NULL,
    text_sha256 VARCHAR(64) NOT NULL,
    text_bytes INTEGER NOT NULL CONSTRAINT ck_filing_source_extraction_bytes CHECK (text_bytes BETWEEN 1 AND 134217728),
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_filing_source_extraction_version UNIQUE (bundle_id, decoder_version, extractor_version)
);
