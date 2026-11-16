ALTER TABLE document_sync_operations
    ADD COLUMN heartbeat_at TIMESTAMPTZ,
    ADD COLUMN lease_expires_at TIMESTAMPTZ,
    ADD COLUMN last_error VARCHAR(1000);

UPDATE document_sync_operations
SET heartbeat_at = COALESCE(heartbeat_at, started_at),
    lease_expires_at = COALESCE(lease_expires_at, started_at + INTERVAL '15 minutes')
WHERE status = 'running';

WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY external_id
               ORDER BY started_at DESC, id DESC
           ) AS position
    FROM document_sync_operations
    WHERE status = 'running'
)
UPDATE document_sync_operations AS operation
SET status = 'failed',
    finished_at = NOW(),
    lease_expires_at = NULL,
    last_error = 'Encerrada na migração: havia outra operação ativa para a mesma contratação.',
    failures = '[{"error":"Encerrada na migração por duplicidade de operação ativa."}]'::jsonb
FROM ranked
WHERE operation.id = ranked.id
  AND ranked.position > 1;

CREATE INDEX ix_document_sync_operations_lease_expires_at
    ON document_sync_operations (lease_expires_at)
    WHERE status = 'running';

CREATE UNIQUE INDEX uq_document_sync_operations_one_running_per_external_id
    ON document_sync_operations (external_id)
    WHERE status = 'running';
