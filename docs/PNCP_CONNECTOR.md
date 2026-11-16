# Conector PNCP — contrato inicial

## Fonte e endpoints

Fonte oficial: API de consulta do PNCP, documentada no Swagger oficial:
https://pncp.gov.br/api/consulta/swagger-ui/index.html

Base URL: `https://pncp.gov.br/api/consulta`

- `GET /v1/contratacoes/proposta`: contratações com recebimento de propostas aberto. O conector envia `dataFinal` e `pagina`; filtros opcionais podem incluir modalidade e UF.
- `GET /v1/contratacoes/publicacao`: publicações por período. O conector envia `dataInicial`, `dataFinal`, `codigoModalidadeContratacao` e `pagina`.

A busca nacional é o padrão: o filtro de UF só é enviado quando solicitado. A consulta por publicação exige modalidade; uma varredura abrangente deverá iterar sobre a lista oficial de modalidades ativas, sem presumir que um código represente todas.

## Regras de implementação

- Datas enviadas no formato `AAAAMMDD`.
- Páginas iniciam em 1.
- O tamanho de página é limitado a 50 para estes endpoints de contratações.
- Preservar o JSON bruto retornado para auditoria e reprocessamento.
- Registrar posteriormente timestamp UTC de coleta, endpoint, parâmetros, status HTTP e hash do payload.
- Tratar erros do PNCP como falha de fonte, sem transformar falha em lista vazia.
- O conector percorre páginas para propostas abertas e para publicações de uma modalidade informada, com limite de segurança e sinalização explícita de coleta incompleta.

## Limites conhecidos

A coleta paginada por modalidade já está implementada, mas a varredura nacional automática de todas as modalidades ativas ainda não existe. A persistência PostgreSQL está implementada para o fluxo de propostas abertas; a publicação por modalidade ainda não tem comando de ingestão próprio. O conector não baixa editais/anexos nem executa análise por IA. Essas capacidades não devem ser anunciadas como concluídas.


## Persistência inicial

O primeiro armazenamento usa PostgreSQL com chave única composta por fonte e `numeroControlePNCP`. O payload original é mantido em JSONB e cada coleta atualiza o hash do payload e o horário da última observação, permitindo detectar alterações sem perder a referência ao registro original.

Migração inicial: `backend/migrations/0001_create_opportunities.sql`.

Com a variável `ORION_DATABASE_URL` configurada, a coleta de propostas abertas pode ser executada no backend:

```bash
python -m orion_api.ingest_open --end-date 2026-11-16 --max-pages 100
```

A execução é deliberadamente manual nesta etapa. O agendamento contínuo será habilitado depois que os limites operacionais, a observabilidade e a recuperação de falhas forem validados.
