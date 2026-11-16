# ORION — estado de implementação

Última atualização: 2026-11-16

## Implementado no repositório

- [x] Backend FastAPI com rota de saúde e consultas ao PNCP.
- [x] Cliente PNCP para propostas abertas, publicações, atualizações, modalidades, detalhes e documentos.
- [x] Coleta nacional paginada por modalidades ativas, com sinalização de coleta incompleta.
- [x] Persistência PostgreSQL inicial com deduplicação por fonte e identificador.
- [x] Adaptador S3 compatível com armazenamento por SHA-256 e catálogo documental.
- [x] Comando manual para arquivar documentos do PNCP.
- [x] Histórico de versões de oportunidades: primeira captura e alterações de payload por hash, com endpoint de origem e horário de observação.
- [x] CI automatizado para lint e testes.

## Validação e limites

A primeira execução do CI para a funcionalidade de histórico falhou no lint por uma importação não utilizada. O código foi corrigido nesta revisão; a nova execução precisa concluir para confirmar lint e testes. Os testes usam banco e armazenamento simulados: não comprovam conexão com PostgreSQL/S3 reais, consulta real ao PNCP nem homologação ponta a ponta. A migração 0004 deve ser aplicada no PostgreSQL antes de ativar o histórico.

## Pendente

- [ ] Expor API paginada para consultar versões por oportunidade.
- [ ] Registrar alterações de documentos, inclusive substituições e remoções.
- [ ] Aplicar migrações e validar upsert concorrente em PostgreSQL real.
- [ ] Validar PNCP real e armazenamento S3 real.
- [ ] Implementar agendamento, checkpoints e retentativas.
- [ ] Construir interface web, autenticação e isolamento por organização.
- [ ] Implantar em nuvem, configurar observabilidade, backups e homologar fluxo ponta a ponta.
