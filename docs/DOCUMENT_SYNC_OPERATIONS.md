# ORION — histórico de operações de sincronização PNCP

A migração 0006 cria o registro persistente de cada sincronização iniciada pelo comando `python -m orion_api.sync_pncp_documents`. O registro começa como `running` e termina como `completed`, `partial` ou `failed`; contagens e falhas ficam disponíveis para auditoria.

Endpoints de consulta:
- `GET /api/v1/document-sync-operations?page=1&page_size=20`: lista paginada, mais recentes primeiro.
- `GET /api/v1/document-sync-operations/{operation_id}`: detalhe da operação.

Aplique as migrações `0006_document_sync_operations.sql` e `0007_document_sync_leases.sql`. A migração 0007 adiciona heartbeat e lease de 15 minutos, encerra duplicidades antigas e cria uma restrição parcial que impede mais de uma operação `running` para a mesma contratação. O sincronizador renova o lease antes e depois de cada documento; operações sem heartbeat são marcadas como `failed` na próxima tentativa de sincronização daquela contratação. Uma colisão concorrente é rejeitada sem iniciar uma segunda execução.

O histórico ainda não tem autenticação/autorização própria nem isolamento multi-tenant; não exponha a API publicamente antes de implementar esses controles.
