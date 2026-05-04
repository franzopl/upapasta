# TODO — Upapasta: Roadmap Completo até v1.0.0

> Última revisão: 2026-05-04 (fase 2 parcial: 219 testes verdes, 1 skipped)
> Princípio: corrigir primeiro, expandir depois. Estabilidade > novas features.

---

## ✅ Implementado (histórico)

- **render_template centralizado** — `config.py` (eliminada duplicação entre `nzb.py` e `orchestrator.py`)
- **`--profile <nome>`** — perfis nomeados em `~/.config/upapasta/<nome>.env`
- **`--test-connection`** — handshake NNTP (CONNECT/LOGIN/QUIT)
- **`--config`** — reconfiguração com preservação de valores
- **`--rar` opt-in** (0.18.0) — inversão de `--skip-rar`; `--password` presume `--rar`
- **Docs JSONL sincronizadas** (0.18.x) — README, DOCS, CHANGELOG corrigidos; F1.1 ✅
- **`test_catalog.py` migrado para JSONL** (0.18.x) — 4 testes corrigidos (`_history_path`); F1.2 ✅
- **`fix_nzb_subjects` corrigido** (0.18.x) — matching robusto sem aspas; F1.3 ✅
- **`test_fallback_to_rename` corrigido** (0.18.x) — mock atualizado; F1.4 ✅
- **`--each` / `--season` / `--watch`** — modos de processamento múltiplo
- **Upload sem staging `/tmp`** (0.9.0) — paths diretos via `cwd=input_path`
- **`managed_popen`** (0.9.0) — SIGTERM→SIGKILL para todos os subprocessos externos
- **Ofuscação atômica via hardlink + try/finally** (0.14.x–0.15.x)
- **Catálogo JSONL + arquivamento NZB via hardlink** (0.12.0)
- **Pool de grupos aleatório** (0.11.0)
- **`from_args` classmethod** (0.12.0) — ponto único de mapeamento args→orchestrator

---

## 🔴 Fase 1 — Estabilidade (v0.19.x)

**Meta: CI verde, cobertura de segurança básica e limpeza. Sem novas features.**
**Status: 145 passed, 1 skipped (`test_season_obfuscation_integration` — suspenso intencionalmente)**

### ~~1.1 · Sincronizar docs ↔ código (catálogo JSONL)~~ ✅ Concluído (commit b0a7636)

### ~~1.2 · Migrar testes de `test_catalog.py` para JSONL~~ ✅ Concluído (commit b0a7636)

### ~~1.3 · Corrigir `fix_nzb_subjects`~~ ✅ Concluído (commit b0a7636)

### ~~1.4 · Corrigir `test_fallback_to_rename`~~ ✅ Concluído (commit d18cd23)

### ~~1.5 · GitHub Actions CI~~ ✅ Concluído (commit ae6b39a)

### ~~1.6 · Limpeza de arquivos órfãos no root do repo~~ ✅ Concluído (commit ae6b39a)

### ~~1.7 · Atualizar/substituir GEMINI.md~~ ✅ Concluído (commit ae6b39a)

### ~~1.8 · Atualizar INSTALL.md~~ ✅ Concluído (commit ae6b39a)

### ~~1.9 · Testes para `resources.py`~~ ✅ Concluído
- 21 testes: `get_mem_available_mb`, `get_total_size`, `calculate_optimal_resources` (overrides, faixas, limites de memória, estrutura do retorno)

### ~~1.10 · Testes para `ui.py` (PhaseBar + _TeeStream)~~ ✅ Concluído
- 27 testes: `format_time`, `_TeeStream` (duplicação, strip ANSI, mascaramento de senhas, encoding), `PhaseBar` lifecycle completo (pending→active→done→skipped→error)

### ~~1.11 · Mascarar senhas em `_TeeStream.write`~~ ✅ Concluído (commit ae6b39a)

### ~~1.12 · Documentar `examples/` no README (seção Hooks)~~ ✅ Concluído
- Seção "Hooks Pós-Upload" expandida com tabela `UPAPASTA_*`, referência a `examples/post_upload_debug.sh` e comportamento de timeout/falha

### ~~1.13 · Remover `__import__("shlex")` inline~~ ✅ Concluído (commit ae6b39a)

### ~~1.14 · Mover `--profile` para grupo "essenciais"~~ ✅ Concluído (commit ae6b39a)

### ~~1.15 · Migrar `scripts/check_header.py`~~ ✅ Concluído
- Substituída dependência `python-dotenv` por `config.load_env_file`; adicionado SSL explícito com `ssl.create_default_context()`

---

## 🟡 Fase 2 — Robustez & UX (v0.20.x)

**Meta: pipeline resiliente a falhas reais; visibilidade clara ao usuário.**

### ~~2.1 · Validação prévia de input (tamanho, permissões, espaço em disco)~~ ✅ Concluído
- `orchestrator.validate()`: valida `df ≥ 2× tamanho fonte`, permissões legíveis, mensagens claras
- 4 testes em `test_phase2.py`

### ~~2.2 · ETA pré-pipeline~~ ✅ Concluído
- Linha `⏱  ETA upload: ~HH:MM:SS @ N conexões (estimativa)` no header de `run()`
- Estimativa conservadora: 500 KB/s por conexão

### ~~2.3 · Mensagens de erro de subprocesso parseadas~~ ✅ Concluído
- `_parse_nyuu_stderr()` em `upfolder.py`: traduz 401/403, 502, timeout, ECONNREFUSED, SSL para português
- 6 testes em `test_phase2.py`

### ~~2.4 · Retry com backoff exponencial + jitter~~ ✅ Concluído
- `--upload-retries 3` → 30s → 90s → 270s com ±10% jitter antes de cada retry
- Thread para leitura de stderr sem deadlock

### ~~2.5 · `obfuscate_and_par` rollback completo de volumes PAR2 ofuscados~~ ✅ Concluído
- `finally` em `obfuscate_and_par`: remove `random_base*.par2` e `orig_stem*.par2` antes de reverter rename

### 2.6 · Refatorar `orchestrator.py` → extrair `PathResolver`, `PipelineReporter`, `DependencyChecker` `Alta · Alto esforço` ← depende de 1.5
- 1026 linhas, quebra Single Responsibility
- Meta: `orchestrator.py < 600 linhas`; cada nova classe testada isoladamente

### 3.0 · Melhorias de Ofuscação
- [ ] Implementar `--strong-obfuscate`: mantém os nomes aleatórios também dentro do NZB (máxima privacidade em indexadores, requer renomeação manual ou via par2 após download).

### 2.7 · Refatorar `makepar.py::obfuscate_and_par` em sub-funções por modo `Média · Alto esforço` ← depende de 2.6
- Função tem 195 linhas com 4 ramos (folder/rar-volset/single-file/erro)
- Meta: função principal < 60 linhas

### ~~2.8 · Deduplicate progress parser → `_progress.py` compartilhado~~ ✅ Concluído
- `_PCT_RE`, `_read_output`, `_process_output` extraídos para `upapasta/_progress.py`
- `makerar.py` e `makepar.py` importam de `_progress.py`
- 5 testes em `test_phase2.py`

### 2.9 · Múltiplos servidores NNTP com failover `Alta · Alto esforço` ← depende de 2.3
- `NNTP_HOST_1/2/3` no `.env`; primeira falha → tenta próximo
- Teste de switch automático

### 2.10 · `--resume` / upload parcial via `.upapasta-state` JSON `Alta · Alto esforço` ← depende de 2.6
- nyuu suporta retomada via `--input <file>` com lista de artigos
- Salvar hash do conteúdo + último artigo confirmado
- Teste: Ctrl+C durante upload + rerun retoma de onde parou

### ~~2.11 · NFO `ffprobe` single-call (`-show_streams -show_format`)~~ ✅ Concluído
- `_get_video_info()` substitui `_get_video_duration()` + `_get_video_metadata()` com uma única chamada
- `nfo.py:36-79` — ~50% menos chamadas de subprocesso para pastas com vídeos

### 2.12 · NFO multi-track (áudio + legendas embutidas) `Média · Médio esforço` ← depende de 2.11
- NFO deve mostrar: `Áudio: PT, EN, JP | Legendas: PT` para `.mkv` multi-track

### ~~2.13 · Logging estruturado com timestamps + níveis~~ ✅ Concluído
- `--verbose` ativa timestamp ISO `%Y-%m-%dT%H:%M:%S` no handler de stream
- Modo padrão: sem timestamp (output limpo)
- 2 testes em `test_phase2.py`

### ~~2.14 · Testes para `--watch` daemon~~ ✅ Concluído
- 4 testes em `test_phase2.py`: `_item_size` (arquivo, pasta, inexistente) + `_watch_loop` com mock de polling

### ~~2.15 · `nntp_test.py` SSL verification opt-in (default verify)~~ ✅ Concluído
- Default agora usa CA certs do sistema (`ssl.create_default_context()` sem modificação)
- `--insecure` desativa verificação; propagado via CLI → `main.py` → `test_nntp_connection(insecure=...)`
- 2 testes em `test_phase2.py`

### 2.16 · `fix_nzb_subjects` reescrito com parser estruturado `Média · Médio esforço` ← depende de 1.3
- Substituir lógica de matching por aspas por parser real
- Suportar `(\d+/\d+)`, yEnc, subjects sem aspas

### ~~2.17 · Cache global de `os.path.getsize` no pipeline~~ ✅ Concluído
- `@lru_cache(maxsize=64)` em `get_total_size` em `resources.py`
- 2 testes em `test_phase2.py`

---

## 🟢 Fase 3 — Features Estratégicas (v0.21.x → v1.0.0)

**Meta: features diferenciadoras; ferramenta autoexplicativa; suporte cross-platform.**

### 3.1 · Múltiplas entradas posicionais: `upapasta a b c` `Média · Médio esforço` ← depende de 2.6
- Processar em sequência ou `--jobs N` em paralelo

### 3.2 · Compressor alternativo: `--compressor 7z` (novo `make7z.py`) `Média · Alto esforço` ← depende de 2.6
- RAR continua default; 7z gera `.7z.001` etc. (livre, sem licença comercial)
- Testes de round-trip

### 3.3 · Webhooks nativos: Discord/Telegram/Slack via `WEBHOOK_URL` `Alta · Médio esforço` ← depende de 2.13
- POST JSON ao final de cada upload; templates simples; stdlib `urllib`
- Teste com mock httpserver

### 3.4 · TMDb integration: enriquece NFO com sinopse/poster URL/IMDB ID `Alta · Alto esforço` ← depende de 2.12
- Detecta filme/série, faz lookup, enriquece NFO
- Flag opt-in `--tmdb`

### 3.5 · NZB com `<meta>` enriquecido (title/poster/category) `Média · Médio esforço` ← depende de 3.4
- Injetar `<meta type="title">`, `<meta type="poster">`, `<meta type="category">`
- Teste XML

### 3.6 · Template de NFO customizável: `--nfo-template <arquivo>` `Média · Médio esforço` ← depende de 2.12
- Placeholders: `{title}`, `{size}`, `{files}`, `{video_info}`, `{tmdb}`
- Fallback automático para geração automática se template não existir

### 3.7 · `upapasta --stats` (histórico agregado) `Média · Médio esforço` ← depende de 2.13
- Lê `history.jsonl`; imprime top categorias, GB/mês, grupo mais usado
- Teste com fixture

### 3.8 · Modo interativo TUI (`--interactive`) `Baixa · Alto esforço` ← depende de 3.7
- `curses` da stdlib; menu de upload + histórico

### 3.9 · `--dry-run --verbose` imprime argv completo dos subprocessos `Média · Baixo esforço` ← depende de 1.5
- Imprimir comando completo de `parpar`/`nyuu` em vez de apenas "[DRY-RUN] PAR2 será criado em: ..."

### 3.10 · Suporte Windows nativo testado (CI matrix) `Média · Alto esforço` ← depende de 1.5
- GitHub Actions roda em Windows; paths normalizados; sem regressões

### 3.11 · Separar `profiles.py` de `config.py` `Baixa · Baixo esforço` ← depende de 2.6
- `config.py` mistura perfis PAR2 com leitura de `.env`
- Mover constantes PAR2 para `profiles.py`

### 3.12 · `mypy --strict` no CI `Média · Médio esforço` ← depende de 2.6, 2.7
- Zero warnings; type hints completos em todos os módulos

### 3.13 · Cobertura de testes ≥ 90% por módulo `Crítica · Alto esforço` ← depende de 2.x
- `pytest --cov` ≥ 90% para `cli/orchestrator/makerar/makepar/upfolder/nzb`
- ≥ 75% global
- Lacunas prioritárias: `--season` end-to-end (L1), `handle_par_failure` retry (L7), catálogo JSONL corrompido (L9), `_validate_flags` matrix (L12)

### 3.14 · Documentação completa (man page, FAQ, troubleshooting) `Alta · Médio esforço` ← depende de 3.x
- `man upapasta`, `docs/FAQ.md`, `docs/TROUBLESHOOTING.md`

### 3.15 · Publicação no PyPI com workflow automatizado `Alta · Médio esforço` ← depende de 3.13
- `gh release create` dispara `pypa/gh-action-pypi-publish`
- Confirmar se já existe no PyPI ou se README.md precisa ser corrigido (README.md:103-104)

### 3.16 · Migrar para Python 3.10+ no `requires-python` (pós-v1.0) `Baixa · Baixo esforço`
- Permite `match/case`, `tomllib`
- Apenas após v1.0.0

### 3.17 · Plugin system: hooks Python em `~/.config/upapasta/hooks/<name>.py` `Baixa · Alto esforço`
- Hook recebe dict; documentado; pós-v1.0

---

## 🏁 Critérios de v1.0.0

- [ ] Todas as Fases 1 e 2 concluídas
- [ ] CI verde (pytest + mypy + ruff) via GitHub Actions
- [ ] Cobertura ≥ 90% nos módulos core (F3.13)
- [ ] `--resume` funcional (F2.10)
- [ ] Múltiplos servidores NNTP (F2.9)
- [ ] Documentação completa e atualizada (F3.14)
- [ ] PyPI publicado (F3.15)
- [ ] Zero dependências Python externas (manter atual)

---

## 📋 Resumo de Prioridades

| Fase | Versão | Foco | Itens-chave |
|------|--------|------|-------------|
| 1 | v0.19.x | Estabilidade | F1.1–1.15: docs sync, testes verdes, CI, segurança básica |
| 2 | v0.20.x | Robustez & UX | F2.1–2.17: validação, retry, refactor, resume, multi-server |
| 3 | v0.21.x→v1.0 | Features | F3.1–3.15: webhooks, TMDb, 7z, stats, publicação |

**Próximos passos imediatos** (em ordem):
1. ~~F1.1–F1.15~~ ✅ Fase 1 completa
2. F2.15 — Bug de segurança `ssl.CERT_NONE` em `nntp_test.py` (S1)
3. F2.1 — Validação prévia de input (espaço em disco, permissões)
4. F2.3 — Mensagens de erro de subprocesso parseadas (nyuu stderr)
5. F2.4 — Retry com backoff exponencial + jitter
