# Conector PNCP — contrato inicial

## Fonte e endpoints

Fonte oficial: API de consulta do PNCP, documentada no Swagger oficial:
https://pncp.gov.br/api/consulta/swagger-ui/index.html

Base URL: `https://pncp.gov.br/api/consulta`

- `GET /v1/contratacoes/proposta`: contratações com recebimento de propostas aberto. O conector envia `dataFinal` e `pagina`; filtros opcionais podem incluir modalidade e UF.
- `GET /v1/contratacoes/publicacao`: publicações por período. O conector envia `dataInicial`, `dataFinal`, `codigoModalidadeContratacao` e `pagina`.

A busca nacional é o padrão: o filtro de UF só é enviado quando solicitado. A consulta por publicação exige modalidade. O catálogo de modalidades é consultado separadamente na API de integração, em `https://pncp.gov.br/api/pncp/v1/modalidades?statusAtivo=true`; não se deve chamar esse recurso pela base `/api/consulta`.

## Regras de implementação

- Datas enviadas no formato `AAAAMMDD`.
- Páginas iniciam em 1.
- O tamanho de página é limitado a 50 para estes endpoints de contratações.
- Preservar o JSON bruto retornado para auditoria e reprocessamento.
- Registrar posteriormente timestamp UTC de coleta, endpoint, parâmetros, status HTTP e hash do payload.
- Tratar erros do PNCP como falha de fonte, sem transformar falha em lista vazia.
- O conector percorre páginas para propostas abertas e para publicações de uma modalidade informada, com limite de segurança e sinalização explícita de coleta incompleta.

## Limites conhecidos

O catálogo de modalidades ativas e a varredura de publicações por modalidade estão implementados. Falhas de uma modalidade são registradas no resultado sem ocultar as demais; a coleta global só é marcada completa quando todas terminam. O comando de ingestão de publicações persiste os resultados coletados no PostgreSQL e retorna código de saída 2 quando a varredura fica parcial. A integração real com o serviço PNCP e a persistência PostgreSQL ainda precisam de homologação operacional. O conector não baixa editais/anexos nem executa análise por IA.


## Persistência inicial

O primeiro armazenamento usa PostgreSQL com chave única composta por fonte e `numeroControlePNCP`. O payload original é mantido em JSONB e cada coleta atualiza o hash do payload e o horário da última observação, permitindo detectar alterações sem perder a referência ao registro original.

Migração inicial: `backend/migrations/0001_create_opportunities.sql`.

Com as variáveis `ORION_DATABASE_URL`, `ORION_PNCP_BASE_URL` e `ORION_PNCP_DOMAIN_BASE_URL` configuradas, a coleta de propostas abertas pode ser executada no backend:

```bash
python -m orion_api.ingest_open --end-date 2026-11-16 --max-pages 100
```

A coleta de publicações de todas as modalidades ativas pode ser executada manualmente por intervalo de datas:

```bash
python -m orion_api.ingest_published --start-date 2026-11-01 --end-date 2026-11-16 --max-pages-per-modality 100
```

A execução é deliberadamente manual nesta etapa. O agendamento contínuo será habilitado depois que os limites operacionais, a observabilidade e a recuperação de falhas forem validados.
