ALTER TABLE document_assets
    ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'present';

CREATE TABLE document_asset_versions (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL
        REFERENCES document_assets(id) ON DELETE CASCADE,
    sha256 CHAR(64) NOT NULL,
    filename VARCHAR(512),
    content_type VARCHAR(160) NOT NULL,
    byte_size INTEGER NOT NULL,
    storage_backend VARCHAR(32) NOT NULL,
    storage_key VARCHAR(512) NOT NULL,
    status VARCHAR(16) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_document_asset_versions_asset_observed
    ON document_asset_versions (asset_id, observed_at DESC);
