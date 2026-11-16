CREATE TABLE document_sync_operations (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(32) NOT NULL DEFAULT 'PNCP',
    external_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    listed INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    removed INTEGER NOT NULL DEFAULT 0,
    failures JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX ix_document_sync_operations_external_id
    ON document_sync_operations (external_id);
CREATE INDEX ix_document_sync_operations_status
    ON document_sync_operations (status);
CREATE INDEX ix_document_sync_operations_started_at
    ON document_sync_operations (started_at DESC);
