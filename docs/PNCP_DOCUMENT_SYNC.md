# ORION — sincronização de documentos do PNCP

## Execução

Com o backend instalado e as variáveis ORION_DATABASE_URL e ORION_S3_BUCKET configuradas, execute a partir da pasta backend:

```bash
python -m orion_api.sync_pncp_documents --cnpj 00000000000000 --year 2026 --sequence 1
```

O comando consulta a lista oficial de arquivos da contratação, baixa cada documento dentro do limite ORION_PNCP_MAX_DOCUMENT_BYTES, armazena o conteúdo no bucket S3/compatível e registra metadados e versões no PostgreSQL.

A saída é JSON e inclui a quantidade listada, arquivada e removida, documentos arquivados e falhas individuais. O processo termina com código 0 quando a sincronização é completa e 2 quando houve falha em pelo menos um documento. Erros fatais de configuração, referência ou listagem inválida interrompem a execução.

## Pré-requisitos e segurança operacional

- Aplicar previamente todas as migrações SQL em backend/migrations, inclusive 0005_document_asset_version_history.sql.
- Provisionar o bucket e conceder apenas as permissões S3 necessárias; o comando não cria infraestrutura.
- Usar credenciais por mecanismo seguro do ambiente (por exemplo, role gerenciada) sempre que disponível.
- Validar conectividade e permissões no ambiente de homologação antes de executar em produção.
- Uma listagem inválida não reconcilia documentos ausentes. Falhas de download são reportadas individualmente e não fazem o documento listado ser marcado como removido.
- O upload no storage precede a gravação dos metadados; uma falha posterior no banco pode deixar objeto órfão. A limpeza desses objetos ainda requer rotina própria.

## Estado de homologação

O comando e seus testes automatizados não comprovam acesso a PostgreSQL, bucket ou PNCP reais. A homologação integrada deve ser executada no ambiente provisionado, com credenciais e contratação de teste autorizada.
