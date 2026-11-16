# ORION — histórico de operações de sincronização PNCP

A migração 0006 cria o registro persistente de cada sincronização iniciada pelo comando `python -m orion_api.sync_pncp_documents`. O registro começa como `running` e termina como `completed`, `partial` ou `failed`; contagens e falhas ficam disponíveis para auditoria.

Endpoints de consulta:
- `GET /api/v1/document-sync-operations?page=1&page_size=20`: lista paginada, mais recentes primeiro.
- `GET /api/v1/document-sync-operations/{operation_id}`: detalhe da operação.

Antes de usar os endpoints, aplique a migração `0006_document_sync_operations.sql`. O histórico ainda não tem autenticação/autorização própria nem isolamento multi-tenant; não exponha a API publicamente antes de implementar esses controles. Operações interrompidas abruptamente podem permanecer como `running`; recuperação/expiração de leases será tratada em etapa própria.
