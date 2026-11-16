# ORION — estado de implementação

Última atualização: 2026-11-16

## Implementado no repositório

- [x] Repositório privado e acesso de escrita confirmado.
- [x] Backend FastAPI com rota de saúde e consulta de oportunidades.
- [x] Cliente PNCP para propostas abertas, publicações por período e catálogo de modalidades ativas.
- [x] Busca nacional por padrão, com filtro opcional por UF.
- [x] Paginação limitada para propostas abertas e publicações por modalidade, com sinalização de coleta incompleta.
- [x] Persistência PostgreSQL inicial com payload JSONB, hash SHA-256 e chave única por fonte/identificador.
- [x] Comandos de coleta manual de propostas abertas e publicações de todas as modalidades ativas, com gravação via upsert.
- [x] Rota de referência para modalidades e testes automatizados para paginação, catálogo, varredura parcial, contrato da API e hash.
- [x] Workflow GitHub Actions para lint e testes (última execução confirmada verde).

## Evidência e limites

A execução CI 43950130869 concluiu Lint (Ruff) com sucesso e 19 testes automatizados aprovados. Isso valida lint e testes unitários/contratuais simulados, mas não confirma conexão com PostgreSQL, consulta real ao PNCP ou homologação ponta a ponta. A varredura automatizada do catálogo de modalidades está implementada; sua operação contra o serviço real ainda precisa ser homologada.

## Pendente

- [x] Confirmar execução verde do workflow CI: Ruff aprovado e 19 testes aprovados na execução 43950130869.
- [ ] Testar integração real com PNCP e validar schemas retornados.
- [ ] Validar a semântica de todos os filtros e paginação nos endpoints atuais.
- [ ] Homologar o catálogo e a varredura nacional contra o PNCP real; implementar captura global de atualizações.
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
