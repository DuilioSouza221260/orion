# ORION — estado de implementação

Última atualização: 2026-11-16

## Implementado no repositório

- [x] Repositório privado `DuilioSouza221260/orion` identificado; permissão de escrita confirmada.
- [x] README e documentação inicial.
- [x] API FastAPI com rota de saúde.
- [x] Cliente HTTP PNCP para propostas abertas e contratações por publicação.
- [x] Consulta nacional por padrão; filtro de UF opcional.
- [x] Paginação controlada para coleta de propostas abertas, com limite de segurança e indicação de conclusão.
- [x] Testes automatizados com transporte HTTP simulado.
- [x] Workflow GitHub Actions para lint e testes do backend.
- [x] Configuração inicial e arquivos de exclusão para desenvolvimento.

## Evidência e limites de validação

Os arquivos foram gravados no repositório e os respectivos commits foram retornados pelo GitHub. O status de checks consultado para o último commit ainda não apresentou resultados. Portanto, os testes foram escritos, mas **não estão declarados como executados ou aprovados**. Ainda não houve homologação contra respostas reais do PNCP.

## Pendente

- [ ] Confirmar execução verde do workflow CI.
- [ ] Testar integração real contra o PNCP e validar schemas atuais.
- [ ] Iterar por todas as modalidades oficiais ativas para uma varredura abrangente.
- [ ] Implementar coleta incremental, retentativas e deduplicação por identificador oficial.
- [ ] Persistir oportunidades e histórico em PostgreSQL.
- [ ] Armazenar payloads originais e documentos/anexos.
- [ ] Construir interface web.
- [ ] Implantar em nuvem e configurar observabilidade, backups e segurança.
- [ ] Homologar fluxo ponta a ponta com critérios de aceite.

## Próximo ciclo técnico

1. Fechar o contrato de dados e a matriz de modalidades com base no catálogo oficial.
2. Criar persistência PostgreSQL com migrações e deduplicação.
3. Implementar worker de coleta incremental e histórico de alterações.
4. Executar homologação real de ponta a ponta antes de ampliar o escopo.
