CREATE TABLE opportunity_versions (
    id BIGSERIAL PRIMARY KEY,
    opportunity_id BIGINT NOT NULL
        REFERENCES opportunities(id) ON DELETE CASCADE,
    payload_hash CHAR(64) NOT NULL,
    raw_payload JSONB NOT NULL,
    source_endpoint VARCHAR(120) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_opportunity_versions_opportunity_observed
    ON opportunity_versions (opportunity_id, observed_at DESC);

CREATE INDEX ix_opportunity_versions_payload_hash
    ON opportunity_versions (payload_hash);
