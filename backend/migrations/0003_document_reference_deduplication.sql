ALTER TABLE document_assets
    DROP CONSTRAINT IF EXISTS uq_document_assets_sha256;

ALTER TABLE document_assets
    ADD CONSTRAINT uq_document_assets_source_reference
    UNIQUE (source, external_id, document_sequence);

CREATE INDEX IF NOT EXISTS ix_document_assets_sha256
    ON document_assets (sha256);
