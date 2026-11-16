# ORION — estado de implementação

Última atualização: 2026-11-16

## Implementado no repositório

- [x] Repositório privado e acesso de escrita confirmado.
- [x] Backend FastAPI com rota de saúde e consulta de oportunidades.
- [x] Cliente PNCP para propostas abertas e publicações por período.
- [x] Busca nacional por padrão, com filtro opcional por UF.
- [x] Paginação limitada com sinalização de coleta incompleta.
- [x] Persistência PostgreSQL inicial com payload JSONB, hash SHA-256 e chave única por fonte/identificador.
- [x] Comando de coleta manual de propostas abertas e gravação via upsert.
- [x] Migração SQL inicial e testes automatizados para paginação e hash.
- [x] Workflow GitHub Actions para lint e testes (última execução confirmada verde).

## Evidência e limites

A execução CI 43949504992 foi concluída com sucesso: Ruff aprovado e 13 testes automatizados aprovados. Isso valida lint e testes unitários/contratuais simulados, mas não confirma conexão com PostgreSQL, consulta real ao PNCP ou homologação ponta a ponta. O coletor atual cobre a rota de propostas abertas; ainda não é uma varredura histórica completa de todas as modalidades.

## Pendente

- [x] Confirmar execução verde do workflow CI: Ruff aprovado e 13 testes aprovados na execução 43949504992.
- [ ] Testar integração real com PNCP e validar schemas retornados.
- [ ] Validar a semântica de todos os filtros e paginação nos endpoints atuais.
- [ ] Implementar captura de publicações por modalidades ativas e atualizações globais.
- [ ] Implementar agendamento, retentativas com backoff e checkpoint de coleta.
- [ ] Validar persistência em PostgreSQL real e deduplicação em concorrência.
- [ ] Implementar histórico de alterações, download de editais/anexos e armazenamento de objetos.
- [ ] Construir interface web e autenticação multi-organização.
- [ ] Implantar em nuvem, configurar monitoramento, backups e homologar o fluxo ponta a ponta.

## Próximo ciclo

1. Executar teste real controlado do PNCP e validar o contrato dos dados recebidos.
2. Completar a coleta de publicações e atualizações com catálogo de modalidades validado.
3. Acrescentar agendamento, retentativas e checkpoints após validação da persistência.
4. Validar persistência PostgreSQL real, concorrência e histórico de alterações.
