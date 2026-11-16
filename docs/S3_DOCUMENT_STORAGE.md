# ORION — armazenamento documental S3

## Configuração

O backend aceita storage S3 ou compatível (por exemplo, serviço gerenciado ou MinIO) por variáveis de ambiente:

- `ORION_S3_BUCKET`: bucket já provisionado.
- `ORION_S3_ENDPOINT_URL`: endpoint opcional para provedores compatíveis.
- `ORION_S3_REGION`: região do bucket.
- `ORION_S3_ACCESS_KEY_ID` e `ORION_S3_SECRET_ACCESS_KEY`: credenciais. Em AWS, prefira roles/credenciais do ambiente em vez de chaves estáticas.

O bucket não é criado automaticamente. A política de acesso deve conceder apenas leitura de metadados e gravação dos objetos necessários.

## Chaves e deduplicação

Cada binário é endereçado pelo SHA-256: `sha256/<dois-primeiros-hex>/<sha256>`.
Antes do envio, o adaptador consulta `HeadObject`. Se o objeto já existir, não o envia novamente. O mesmo binário pode ser referenciado por mais de uma contratação; o catálogo PostgreSQL identifica cada documento pela origem, identificador PNCP e sequência, mantendo o hash como chave de conteúdo.

## Consistência

O objeto é gravado antes dos metadados PostgreSQL. Se a gravação no banco falhar após o upload, poderá restar um objeto órfão; uma rotina de reconciliação/limpeza deverá ser executada antes de habilitar retenção automática. O adaptador não apaga objetos em caso de falha de banco.

## Limites ainda não homologados

A implementação está coberta por testes simulados. Ainda é necessário configurar credenciais e bucket reais, executar migrações em PostgreSQL e validar upload, leitura, permissões, criptografia, versionamento e recuperação.
