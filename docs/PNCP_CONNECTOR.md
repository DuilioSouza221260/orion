# Conector PNCP — contrato inicial

## Fonte e endpoints

Fonte oficial: API de consulta do PNCP, documentada no Swagger oficial:
https://pncp.gov.br/api/consulta/swagger-ui/index.html

Base URL: `https://pncp.gov.br/api/consulta`

- `GET /v1/contratacoes/proposta`: contratações com recebimento de propostas aberto. O conector envia `dataFinal` e `pagina`; filtros opcionais podem incluir modalidade e UF.
- `GET /v1/contratacoes/publicacao`: publicações por período. O conector envia `dataInicial`, `dataFinal`, `codigoModalidadeContratacao` e `pagina`.
- `GET /v1/contratacoes/atualizacao`: contratações alteradas no período, inclusive registros publicados anteriormente que receberam atualização. Usa `dataInicial`, `dataFinal`, `codigoModalidadeContratacao` e `pagina`.

A busca nacional é o padrão: o filtro de UF só é enviado quando solicitado. A consulta por publicação exige modalidade. O catálogo de modalidades e os recursos de detalhe/documentos são consultados na API de integração, em `https://pncp.gov.br/api/pncp`; não se deve chamar esses recursos pela base `/api/consulta`.

## Detalhes e documentos de uma contratação

A API de integração documenta os seguintes recursos para uma contratação identificada por CNPJ do órgão, ano e sequencial:

- `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}`: dados completos da contratação.
- `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos`: metadados dos documentos publicados (sequencial, URL, tipo, título e data de publicação).
- `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos/{sequencialDocumento}`: download de um documento específico.

O backend já disponibiliza as rotas de consulta dos detalhes e da lista de documentos. A transferência binária e a persistência dos arquivos em armazenamento de objetos serão implementadas em etapa própria; nesta entrega, o ORION retorna os metadados e a URL oficial fornecida pelo PNCP. O CNPJ, ano e sequencial são validados antes da chamada externa.

## Regras de implementação

- Datas enviadas no formato `AAAAMMDD`.
- Páginas iniciam em 1.
- O tamanho de página é limitado a 50 para estes endpoints de contratações.
- Preservar o JSON bruto retornado para auditoria e reprocessamento.
- Registrar posteriormente timestamp UTC de coleta, endpoint, parâmetros, status HTTP e hash do payload.
- Tratar erros do PNCP como falha de fonte, sem transformar falha em lista vazia.
- O conector percorre páginas para propostas abertas, publicações e atualizações globais, com limite de segurança e sinalização explícita de coleta incompleta.
- A varredura de atualizações globais percorre todas as modalidades ativas, continua após falhas isoladas e só marca o lote completo quando todas as modalidades terminam.

## Limites conhecidos

O catálogo de modalidades ativas, a varredura de publicações e de atualizações globais por modalidade, a consulta de detalhes de contratação e a listagem de documentos estão implementados. Falhas de uma modalidade são registradas no resultado sem ocultar as demais; a coleta global só é marcada completa quando todas terminam. O comando de ingestão de publicações persiste os resultados coletados no PostgreSQL e retorna código de saída 2 quando a varredura fica parcial. A integração real com o serviço PNCP e a persistência PostgreSQL ainda precisam de homologação operacional. O conector ainda não transfere os arquivos binários para armazenamento próprio nem executa análise por IA.


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


A coleta de contratações alteradas globalmente pode ser executada por intervalo de datas:

```bash
python -m orion_api.ingest_updated --start-date 2026-11-15 --end-date 2026-11-16 --max-pages-per-modality 100
```

Essa rotina complementa a busca por data de publicação: ela permite reencontrar registros antigos que sofreram alterações, mantendo a atualização do mesmo registro pela chave PNCP já usada no repositório. A data de atualização não deve ser confundida com a data de publicação.
