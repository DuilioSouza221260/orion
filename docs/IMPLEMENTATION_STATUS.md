# ORION — estado de implementação

Última atualização: 2026-11-16

## Verificado no repositório

- [x] Repositório privado `DuilioSouza221260/orion` identificado e permissão de escrita confirmada.
- [x] README e documentação inicial.
- [x] Estrutura inicial da API FastAPI.
- [x] Cliente HTTP do PNCP para propostas abertas e publicações.
- [x] Testes unitários com transporte HTTP simulado.
- [x] Rotas de saúde e consulta básica.

## Ainda não homologado

- [ ] Instalação de dependências e execução dos testes em CI.
- [ ] Teste de integração real contra o PNCP.
- [ ] Coleta de todas as páginas e modalidades ativas.
- [ ] Persistência PostgreSQL e deduplicação.
- [ ] Armazenamento de payloads e documentos.
- [ ] Interface web.
- [ ] Implantação em nuvem.
- [ ] Segurança multi-tenant e homologação ponta a ponta.

## Próximo ciclo técnico

1. Adicionar workflow de CI para instalar e executar lint/testes.
2. Validar contrato do PNCP em execução real, sem assumir sucesso com base apenas na documentação.
3. Implementar paginação controlada, coleta incremental e persistência.
4. Só então conectar a interface web ao conjunto de oportunidades persistidas.
