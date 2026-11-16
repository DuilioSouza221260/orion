CREATE TABLE ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(32) NOT NULL DEFAULT 'PNCP',
    endpoint VARCHAR(32) NOT NULL CHECK (endpoint IN ('publicacao', 'atualizacao')),
    filters JSONB NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'completed', 'partial', 'failed')),
    counters JSONB NOT NULL DEFAULT '{}'::jsonb,
    failures JSONB NOT NULL DEFAULT '[]'::jsonb,
    heartbeat_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX ix_ingestion_runs_status ON ingestion_runs (status);
CREATE INDEX ix_ingestion_runs_started_at ON ingestion_runs (started_at DESC);
CREATE INDEX ix_ingestion_runs_lease_expires_at ON ingestion_runs (lease_expires_at);

CREATE TABLE ingestion_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    ingestion_run_id BIGINT NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    modality_id INTEGER NOT NULL CHECK (modality_id > 0),
    page INTEGER NOT NULL CHECK (page > 0),
    pages_total INTEGER CHECK (pages_total IS NULL OR pages_total > 0),
    records_received INTEGER NOT NULL DEFAULT 0 CHECK (records_received >= 0),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ingestion_checkpoint_run_modality_page
        UNIQUE (ingestion_run_id, modality_id, page)
);

CREATE INDEX ix_ingestion_checkpoints_run_id ON ingestion_checkpoints (ingestion_run_id);
