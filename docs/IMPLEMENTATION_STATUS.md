# ORION — estado de implementação

Última atualização: 2026-11-16

## Implementado no repositório

- [x] Repositório privado e acesso de escrita confirmado.
- [x] Backend FastAPI com rota de saúde e consulta de oportunidades.
- [x] Cliente PNCP para propostas abertas, publicações, atualizações globais, catálogo de modalidades, detalhes de contratação e metadados de documentos.
- [x] Busca nacional por padrão, com filtro opcional por UF.
- [x] Paginação limitada para propostas abertas e publicações por modalidade, com sinalização de coleta incompleta.
- [x] Persistência PostgreSQL inicial com payload JSONB, hash SHA-256 e chave única por fonte/identificador.
- [x] Comandos de coleta manual de propostas abertas e publicações de todas as modalidades ativas, com gravação via upsert.
- [x] Rotas de referência, detalhe da contratação, listagem e download controlado de documentos; download com limite de tamanho, SHA-256, cabeçalhos de origem e testes automatizados.
- [x] Workflow GitHub Actions para lint e testes (última execução confirmada verde).

## Evidência e limites

A execução CI 43950757649 concluiu Lint (Ruff) e testes com sucesso, com 22 testes aprovados antes da inclusão da consulta de detalhes/documentos. A nova execução CI desta entrega deverá confirmar a contagem atualizada. Os testes são unitários/contratuais simulados: não confirmam conexão com PostgreSQL, consulta real ao PNCP nem homologação ponta a ponta.

## Pendente

- [x] Confirmar execução verde do workflow CI: Ruff aprovado e 19 testes aprovados na execução 43950130869.
- [ ] Testar integração real com PNCP e validar schemas retornados.
- [ ] Validar a semântica de todos os filtros e paginação nos endpoints atuais.
- [ ] Homologar o catálogo e a varredura nacional contra o PNCP real; implementar captura global de atualizações.
- [ ] Implementar agendamento, retentativas com backoff e checkpoint de coleta.
- [ ] Validar persistência em PostgreSQL real e deduplicação em concorrência.
- [x] Consultar detalhes de contratação e listar metadados dos documentos publicados.
- [x] Download controlado de editais/anexos pelo endpoint oficial do PNCP, validação de tamanho, cálculo SHA-256 na resposta e identificação da origem.\n- [x] Criar catálogo PostgreSQL de documentos com SHA-256 único, origem PNCP, referência externa, tipo, tamanho, backend e chave de armazenamento.\n- [x] Implementar adaptador S3 compatível com chave determinística por SHA-256, verificação de objeto existente e registro de metadados PostgreSQL por referência documental.
- [ ] Implementar histórico de alterações completo da contratação e dos documentos.
- [ ] Construir interface web e autenticação multi-organização.
- [ ] Implantar em nuvem, configurar monitoramento, backups e homologar o fluxo ponta a ponta.

## Próximo ciclo

1. Executar teste real controlado do PNCP para detalhes e documentos, confirmando os schemas e URLs retornados.
2. Validar o adaptador com credenciais e bucket reais, e acrescentar trilha de auditoria e política de retenção.
3. Implementar histórico da contratação, itens e documentos.
4. Acrescentar agendamento, retentativas e checkpoints após validação da persistência PostgreSQL.
