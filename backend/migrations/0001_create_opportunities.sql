CREATE TABLE IF NOT EXISTS opportunities (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    external_id VARCHAR(100) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    raw_payload JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_opportunities_source_external_id UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS ix_opportunities_source ON opportunities (source);
CREATE INDEX IF NOT EXISTS ix_opportunities_last_seen_at ON opportunities (last_seen_at DESC);
