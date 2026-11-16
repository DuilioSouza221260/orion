# Ingestão PNCP em lotes

Os coletores nacionais de publicações e atualizações aceitam persistência por página. Os comandos `ingest_published` e `ingest_updated` gravam cada página no PostgreSQL assim que ela é recebida, em transações independentes, sem manter todo o resultado nacional em memória.

## Comportamento

- Percorre todas as modalidades ativas do catálogo oficial do PNCP, sem filtro estadual quando `--uf` não é informado.
- Persiste cada página antes de avançar para a próxima.
- Mantém a deduplicação por origem e identificador externo e registra versões apenas quando o payload muda.
- Continua para as modalidades seguintes quando uma modalidade falha; o resumo identifica modalidade, páginas e erro.
- Retorna código de saída `2` quando a coleta não foi integralmente concluída.
- Uma nova execução sobre o mesmo intervalo é segura para repetição: os upserts são idempotentes e não criam versões para payloads inalterados.

## Limites e retomada

O processamento por página limita o consumo de memória e reduz o tamanho das transações. Se o processo parar, as páginas já confirmadas permanecem persistidas. A retomada atual é feita repetindo o mesmo intervalo: os registros já gravados serão reconhecidos pelo upsert. Checkpoints persistentes de página/modalidade e agendamento automático ainda são etapas futuras; não se deve interpretar a execução como retomada automática a partir da última página.

## Exemplos

```bash
python -m orion_api.ingest_published --start-date 2026-11-01 --end-date 2026-11-16
python -m orion_api.ingest_updated --start-date 2026-11-15 --end-date 2026-11-16
```

`--uf` é opcional e deve ser usado apenas quando uma coleta estadual for intencional. O padrão é nacional.
