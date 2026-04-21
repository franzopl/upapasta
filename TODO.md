# TODO — Upapasta: Melhorias e Problemas a Resolver

> Guia de trabalho futuro. Itens ordenados por prioridade dentro de cada categoria.
> Última revisão: 2026-04-19

---

## 🔴 Bugs / Problemas Imediatos

> *(Nenhum bug crítico aberto no momento)*

---

## 🟡 Melhorias de Qualidade e Robustez

### 3. Cobertura de testes — cenários ainda sem cobertura
- Geração de NFO para pastas com vídeos multi-track e legendas embutidas (requer ffprobe mock)
- Testes de integração dos 5 falhos pré-existentes em `test_upfolder.py` / obfuscation (NFO single-file)

---

## 🟢 Funcionalidades Novas

### 7. Suporte a `--resume` / upload parcial
- Se o upload for interrompido (queda de rede, SIGINT), é necessário recomeçar do zero.
- **Proposta:** nyuu suporta `--input` para re-upload de artigos específicos. Implementar salvamento do estado de upload e resume automático.

### 8. Suporte a múltiplos servidores Usenet
- Atualmente apenas um servidor NNTP é configurado.
- **Proposta:** suporte a lista de servidores com prioridade (primary + fallback), lido do `.env` como JSON ou via flags `--server2-host`, etc.

### ~~9. Progress bar unificado~~ ✅ implementado

### 10. Perfis de configuração nomeados
- Atualmente só existe um `.env`. Se o usuário usa múltiplos provedores Usenet, precisa editar manualmente.
- **Proposta:** suporte a `--profile <nome>` que carrega `~/.config/upapasta/<nome>.env`.

### 11. Suporte a `--watch <dir>`
- Monitorar diretório e fazer upload automático de novos arquivos/pastas.
- **Proposta:** modo daemon simples com polling via `inotify` (Linux) ou `watchdog`.

### 12. Geração de NFO melhorada
- FFprobe pode ser chamado múltiplas vezes por vídeo.
- **Fix:** uma única chamada com `-show_streams -show_format`.
- **Melhoria:** detectar áudio multi-track, legendas embutidas e incluir no NFO.
- **Melhoria:** suporte a template de NFO customizável (`NFO_TEMPLATE` no `.env`).

### 13. Suporte a entrada múltipla (`upapasta file1 file2 folder1`)
- Atualmente só aceita um input por invocação.
- **Proposta:** aceitar lista de arquivos/pastas, processar em sequência (ou paralelo com `--jobs N`).

### 14. NZB com `<meta>` enriquecido
- O NZB gerado pelo nyuu tem `<meta>` mínimo.
- **Proposta:** injetar `<meta type="title">`, `<meta type="poster">`, `<meta type="category">` baseado em heurísticas do nome do arquivo / NFO.

### 15. Suporte a compressão alternativa (7-zip)
- RAR5 requer licença para criar (binário `rar` pago em Linux).
- **Proposta:** suporte opcional a `7z` como backend de compressão (`--compressor 7z`), gerando volumes `.7z.001`, etc.

### 16. Estimativa de tempo de upload
- Antes de iniciar, exibir tamanho total + conexões configuradas como ETA simples.

---

## 🔵 Dívida Técnica / Refactoring

### 17. `main.py` com ~900 linhas é difícil de manter
- `UpaPastaOrchestrator` faz orquestração, resolução de caminhos, formatação de saída e lógica de negócio.
- **Proposta:** extrair responsabilidades em classes/módulos dedicados:
  - `PathResolver` — resolução de NZB/NFO output paths
  - `PipelineReporter` — output/progress formatting
  - `DependencyChecker` — verificação de binários externos

### 18. Template `{filename}` parsing duplicado
- `main.py` e `nzb.py` fazem `replace("{filename}", ...)` de forma independente.
- **Fix:** centralizar em `render_template(template: str, **vars) -> str` em `config.py` ou `nzb.py`.

### 19. Suporte a Python 3.8 limita features modernas
- `match/case` (3.10), `tomllib` (3.11), `ExceptionGroup` (3.11) não podem ser usados.
- **Proposta:** avaliar elevar o mínimo para 3.10 (Ubuntu 22.04 LTS vem com 3.10).

### 20. `config.py` mistura perfis PAR2 e defaults de configuração
- Sem separação clara entre "configurável pelo usuário" e "constantes internas".
- **Proposta:** mover constantes de perfil para `profiles.py` e manter `config.py` apenas para leitura de `.env`.

### 21. Sem verificação de tipo estática
- Nenhum uso de `mypy` ou `pyright`.
- **Proposta:** adicionar type hints em todas as funções públicas e rodar `mypy --strict` no CI.

### 22. CI/CD ausente
- Não há GitHub Actions ou similar.
- **Proposta mínima:**
  - `pytest` em push/PR
  - `mypy` para type checking
  - `ruff` para linting

---

## 📋 Referência Rápida — Por onde começar

| Prioridade | Item | Esforço |
|------------|------|---------|
| 1 | #1 Cleanup com regex única | Médio |
| 2 | #3 Aumentar cobertura de testes | Alto |
| 3 | #6 --log-file | Baixo |
| 4 | #4 Error handling específico | Médio |
| 5 | #2 Padronizar retorno de make_rar() | Baixo |
| 6 | #12 NFO com ffprobe único + multi-track | Médio |
| 7 | #17 Refatorar main.py | Alto |
| 8 | #21 Type checking com mypy | Médio |
| 9 | #22 CI/CD GitHub Actions | Médio |
