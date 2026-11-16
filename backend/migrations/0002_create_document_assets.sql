CREATE TABLE IF NOT EXISTS document_assets (
    id BIGSERIAL PRIMARY KEY,
    sha256 VARCHAR(64) NOT NULL,
    source VARCHAR(32) NOT NULL,
    external_id VARCHAR(100) NOT NULL,
    document_sequence INTEGER NOT NULL CHECK (document_sequence >= 1),
    filename VARCHAR(512),
    content_type VARCHAR(160) NOT NULL,
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    storage_backend VARCHAR(32) NOT NULL,
    storage_key VARCHAR(512) NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_document_assets_sha256 UNIQUE (sha256)
);

CREATE INDEX IF NOT EXISTS ix_document_assets_external_id
    ON document_assets (external_id);
CREATE INDEX IF NOT EXISTS ix_document_assets_last_seen_at
    ON document_assets (last_seen_at DESC);
