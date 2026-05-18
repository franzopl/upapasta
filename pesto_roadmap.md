# Roadmap: Integração Completa do Pesto no UpaPasta

O objetivo é substituir o `nyuu` e o `parpar` pelo `pesto`, aproveitando sua performance em Rust e capacidades nativas de geração de PAR2 e ofuscação.

## 1. Pesquisa e Mapeamento de Parâmetros (CONCLUÍDO)
- Identificado que o `pesto` suporta:
    - `--par2 <PERCENT>`: Geração nativa de PAR2.
    - `--obfuscate[=<MODE>]`: Ofuscação nativa (none, subject, full).
    - `--compress [<FORMAT>]`: Compactação nativa (rar, 7z, zip).
    - `--password [<PASS>]`: Senha nativa.
    - `--nfo`: Geração nativa de NFO.

## 2. Atualização do `upfolder.py` (CONCLUÍDO)
- [x] Modificar `_run_pesto` para aceitar `redundancy` e `obfuscate`.
- [x] Ajustar o comando enviado ao `pesto` para usar `--par2 {redundancy}` em vez de `--par2 0`.
- [x] Passar `--obfuscate=full` quando solicitado.
- [x] Garantir que o parser de JSON do `pesto` continue funcionando para o progresso.

## 3. Refatoração do `orchestrator.py` (CONCLUÍDO)
- [x] Adicionar detecção proativa do `pesto` no início do workflow.
- [x] Se `pesto` for detectado:
    - [x] Ignorar `run_makepar` (delegar ao `pesto`).
    - [x] Ignorar `run_obfuscation` manual (delegar ao `pesto`).
    - [x] Ajustar lógica de compactação para decidir entre `makerar.py` ou `pesto --compress` (inicialmente manteremos `makerar.py` para compatibilidade total com volumes customizados).
- [x] Garantir fallback transparente para `nyuu` + `parpar` caso o `pesto` não esteja disponível.

## 4. Integração de Ofuscação e NZB (CONCLUÍDO)
- [x] Sincronizar os mapas de ofuscação. Delegado ao `pesto` nativamente.
- [x] Garantir que o UpaPasta use o NZB gerado pelo `pesto`.

## 5. Validação e Testes (CONCLUÍDO)
- [x] Criar mocks para testes de dry-run.
- [x] Validar delegação de PAR2 e OBF no orquestrador.
- [x] Garantir compatibilidade com fallback `nyuu`.

## 6. Cleanup de Dependências (EM ANDAMENTO)
- [ ] Atualizar documentação recomendando apenas `pesto` e `7z/rar`.
- [ ] Marcar `parpar` e `nyuu` como dependências opcionais/legadas no `INSTALL.md`.
