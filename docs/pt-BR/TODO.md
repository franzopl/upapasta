# TODO — Upapasta: Roadmap Completo até v1.0.0

Versão em inglês disponível em [TODO.md](../../TODO.md).

> Última revisão: 2026-05-06 (i18n I2 concluída: extração de strings completa, 549 testes verdes)
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

## ✅ Fase 2 — Robustez & UX (v0.20.x → v0.24.3) — COMPLETA

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

### ~~2.6 · Refatorar `orchestrator.py` → extrair `PathResolver`, `PipelineReporter`, `DependencyChecker`~~ ✅ Concluído
- 1026 linhas → 612 linhas em `orchestrator.py` + `_pipeline.py` com as 3 classes
- Meta: `orchestrator.py < 600 linhas`; cada nova classe testada isoladamente

### 3.0 · Melhorias de Ofuscação
- [x] ✅ Implementar `--strong-obfuscate`: mantém os nomes aleatórios também dentro do NZB (máxima privacidade em indexadores, requer renomeação manual ou via par2 após download). **Implementado em 0.23.0**

### ~~2.7 · Refatorar `makepar.py::obfuscate_and_par` em sub-funções por modo~~ ✅ Concluído
- Função reduzida de 195 linhas → 72 linhas com 5 sub-funções (_obfuscate_folder, _obfuscate_rar_vol_set, _obfuscate_single_file, _rename_par2_files, _cleanup_on_par_failure)
- Meta: função principal < 60 linhas (próximo, ~72 é aceitável)

### ~~2.8 · Deduplicate progress parser → `_progress.py` compartilhado~~ ✅ Concluído
- `_PCT_RE`, `_read_output`, `_process_output` extraídos para `upapasta/_progress.py`
- `makerar.py` e `makepar.py` importam de `_progress.py`
- 5 testes em `test_phase2.py`

### ~~2.9 · Múltiplos servidores NNTP com failover~~ ✅ Concluído (0.24.0)
- `NNTP_HOST_2`...`NNTP_HOST_9` no `.env`; failover automático por tentativa
- Campos sem definição herdam do servidor primário
- 4 testes em `test_phase2.py`

### ~~2.10 · `--resume` / upload parcial via `.upapasta-state` JSON~~ ✅ Concluído (0.24.0)
- State file `.upapasta-state.json` salvo junto ao NZB antes do upload
- Resume detecta arquivos já no NZB parcial, faz upload dos restantes, mescla NZBs
- 5 testes em `test_phase2.py`

### ~~2.11 · NFO `ffprobe` single-call (`-show_streams -show_format`)~~ ✅ Concluído
- `_get_video_info()` substitui `_get_video_duration()` + `_get_video_metadata()` com uma única chamada
- `nfo.py:36-79` — ~50% menos chamadas de subprocesso para pastas com vídeos

### ~~2.12 · NFO multi-track (áudio + legendas embutidas)~~ ✅ Concluído (0.24.0)
- NFO mostra `Audio: POR, ENG | Legendas: POR` na seção de estatísticas e na árvore por arquivo
- `_get_video_info` usa `ffprobe -of json` e retorna `audio_tracks` + `subtitle_tracks`
- 5 testes em `test_phase2.py`

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

### ~~2.16 · `fix_nzb_subjects` reescrito com parser estruturado~~ ✅ Concluído
- `_parse_subject` decompõe subjects em (prefixo, nome, sufixo); suporta `"quoted"`, yEnc `(N/M)`, subjects sem aspas, extensões compostas (.part01.rar, .vol00+01.par2)
- `_deobfuscate_filename` extraída como função standalone testável
- 7 testes em `test_phase2.py` (TestParseSubject)

### ~~2.17 · Cache global de `os.path.getsize` no pipeline~~ ✅ Concluído
- `@lru_cache(maxsize=64)` em `get_total_size` em `resources.py`
- 2 testes em `test_phase2.py`

---

## 🟢 Fase 3 — Features Estratégicas (v0.21.x → v1.0.0)

**Meta: features diferenciadoras; ferramenta autoexplicativa; suporte cross-platform.**

### ~~3.1 · Múltiplas entradas posicionais: `upapasta a b c`~~ ✅ Concluído (commit 2b1be9a)
- Múltiplos inputs posicionais processados em sequência ou `--jobs N` em paralelo

### 3.2 · Compressor alternativo: `--compressor 7z` (novo `make7z.py`) `Média · Alto esforço` ← depende de 2.6
- RAR continua default; 7z gera `.7z.001` etc. (livre, sem licença comercial)
- Testes de round-trip

### ~~3.3 · Webhooks nativos: Discord/Telegram/Slack via `WEBHOOK_URL`~~ ✅ Concluído
- `_webhook.py`: `send_webhook()` + `_build_payload()` com detecção automática Discord/Slack/Telegram/genérico
- `WEBHOOK_URL` no `.env.example`; chamado em `_pipeline.py` após `run_post_upload_hook`
- 10 testes em `test_phase3.py`

### 3.4 · TMDb integration: enriquece NFO com sinopse/poster URL/IMDB ID `Alta · Alto esforço` ← depende de 2.12
- Detecta filme/série, faz lookup, enriquece NFO
- Flag opt-in `--tmdb`

### 3.5 · NZB com `<meta>` enriquecido (title/poster/category) `Média · Médio esforço` ← depende de 3.4
- Injetar `<meta type="title">`, `<meta type="poster">`, `<meta type="category">`
- Teste XML

### 3.6 · Template de NFO customizável: `--nfo-template <arquivo>` `Média · Médio esforço` ← depende de 2.12
- Placeholders: `{title}`, `{size}`, `{files}`, `{video_info}`, `{tmdb}`
- Fallback automático para geração automática se template não existir

### ~~3.7 · `upapasta --stats` (histórico agregado)~~ ✅ Concluído
- Lê `history.jsonl`; imprime totais, top categorias, GB/mês (últimos 6), grupo mais usado, duração média

### 3.8 · Modo interativo TUI (`--interactive`) `Baixa · Alto esforço` ← depende de 3.7
- `curses` da stdlib; menu de upload + histórico

### ~~3.9 · `--dry-run --verbose` imprime argv completo dos subprocessos~~ ✅ Concluído
- `make_parity` agora imprime o comando completo de `parpar`/`par2` quando `dry_run=True`
- `upload_to_usenet` já imprimia o comando nyuu completo; orchestrator parou de interceptar antes

### 3.10 · Suporte Windows nativo testado (CI matrix) `Média · Alto esforço` ← depende de 1.5
- GitHub Actions roda em Windows; paths normalizados; sem regressões

### ~~3.11 · Separar `profiles.py` de `config.py`~~ ✅ Concluído
- `PROFILES` e `DEFAULT_PROFILE` movidos para `upapasta/profiles.py`
- `config.py` re-exporta para compatibilidade retroativa; `makepar.py` importa direto de `profiles.py`

### ~~3.12 · `mypy --strict` no CI~~ ✅ Concluído
- Zero erros em 20 arquivos (84 erros corrigidos): `dict/list/Queue/Popen` tipados, todas as funções com assinaturas completas
- `pyproject.toml` atualizado com `strict = true`; CI atualizado com `mypy upapasta/ --strict`

### 3.13 · Cobertura de testes ≥ 90% por módulo `Crítica · Alto esforço` ← depende de 2.x
- `pytest --cov` ≥ 90% para `cli/orchestrator/makerar/makepar/upfolder/nzb`
- ≥ 75% global
- Lacunas prioritárias: `--season` end-to-end (L1), `handle_par_failure` retry (L7), catálogo JSONL corrompido (L9), `_validate_flags` matrix (L12)

### 3.14 · Documentação completa (man page, FAQ, troubleshooting) `Alta · Médio esforço` ← depende de 3.x
- `man upapasta`, `docs/FAQ.md`, `docs/TROUBLESHOOTING.md`

### ~~3.15 · Publicação no PyPI com workflow automatizado~~ ✅ Concluído
- `.github/workflows/publish.yml`: on release published → build → pypa/gh-action-pypi-publish via OIDC
- Pacote já existe no PyPI (v0.24.3); classifiers + urls adicionados ao `pyproject.toml`
- Para publicar: criar Trusted Publisher no PyPI (environment: `pypi`) e `gh release create vX.Y.Z`

### 3.16 · Migrar para Python 3.10+ no `requires-python` (pós-v1.0) `Baixa · Baixo esforço`
- Permite `match/case`, `tomllib`
- Apenas após v1.0.0

### 3.17 · Plugin system: hooks Python em `~/.config/upapasta/hooks/<name>.py` `Baixa · Alto esforço`
- Hook recebe dict; documentado; pós-v1.0

---

## 🌐 Internacionalização (i18n) — v0.26.x → v0.28.0

**Meta: inglês como idioma canônico (docs + mensagens); pt-BR como tradução de primeira classe via `gettext`.**

**Decisões de arquitetura:**
- Inglês é o padrão (README.md, docs/, man page, mensagens CLI)
- pt-BR via `locale/pt_BR/LC_MESSAGES/upapasta.{po,mo}` + `README.pt-BR.md` + `docs/pt-BR/`
- Detecção automática via `LANG`/`LC_ALL` do sistema; override via `UPAPASTA_LANG=pt_BR`; sem wizard de primeiro uso
- `gettext` da stdlib — zero novas dependências

### ~~I1 · Infraestrutura gettext `v0.26.0`~~ ✅ Concluído (0.26.0)

- [x] Criar `upapasta/i18n.py`: `gettext.translation()` com `NullTranslations` fallback; detecta `UPAPASTA_LANG` → `locale.getlocale()` → `LANG` → `en`
- [x] Criar estrutura `upapasta/locale/en/LC_MESSAGES/` e `upapasta/locale/pt_BR/LC_MESSAGES/`
- [x] Adicionar `upapasta/locale/Makefile` de i18n: targets `extract` (`xgettext`), `init` (`msginit`), `compile` (`msgfmt`), `update` (`msgmerge`)
- [x] Incluir `.mo` compilados no pacote via `pyproject.toml` (`package-data`) + `MANIFEST.in`
- [x] 8 testes em `tests/test_i18n.py`: detecção de locale, fallback para inglês, `NullTranslations` quando `.mo` ausente, `install()`, `_()`

### I2 · Extração e tradução de strings `v0.26.x` `Alta · Alto esforço` — depende de I1

Envolver todas as strings visíveis ao usuário com `_()` e criar entradas em `pt_BR.po`.
Ordem por impacto (mais strings visíveis primeiro):

- [x] I2.1 · `cli.py` — help strings, erros de validação de flags (~60 strings) ✅ Concluído (commit 66bd22d)
- [x] I2.2 · `orchestrator.py` + `_pipeline.py` — banner, sumário, avisos de pastas vazias (~80 strings) ✅ Concluído (commit e5e3857)
- [x] I2.3 · `ui.py` — labels do PhaseBar, fases NFO/RAR/PAR2/UPLOAD/DONE (~20 strings) ✅ Concluído (já estava internacionalizado)
- [x] I2.4 · `upfolder.py` — `_parse_nyuu_stderr`, mensagens de retry/backoff (~30 strings) ✅ Concluído (commit bcc74ee)
- [x] I2.5 · `makepar.py` + `makerar.py` — progresso, erros de execução (~40 strings) ✅ Concluído (commit 0bf1f60)
- [x] I2.6 · `nzb.py` + `nfo.py` + `catalog.py` — mensagens de conflito, hook, categoria (~30 strings) ✅ Concluído (commit 42a7757)
- [x] I2.7 · `config.py` + `main.py` + `watch.py` + `nntp_test.py` — wizard, daemon, NNTP (~25 strings) ✅ Concluído (commit a ser gerado)

### ~~I3 · Documentação em inglês `v0.27.0`~~ ✅ Concluído (v0.27.0)

- [x] I3.1 · `README.md` → inglês; conteúdo movido para `README.pt-BR.md`
- [x] I3.2 · `DOCS.md` → inglês; versão em português em `docs/pt-BR/DOCS.md`
- [x] I3.3 · `docs/FAQ.md` + `docs/TROUBLESHOOTING.md` → inglês; versões em português em `docs/pt-BR/`
- [x] I3.4 · `docs/man/upapasta.1` → inglês
- [x] I3.5 · `INSTALL.md` → inglês; versão em português em `docs/pt-BR/INSTALL.md`
- [x] I3.6 · `CHANGELOG.md` — entradas traduzidas; versão em português em `docs/pt-BR/CHANGELOG.md`
- [x] I3.7 · `CLAUDE.md` — **permanece em português**

### ~~I4 · CI para i18n `v0.27.x`~~ ✅ Concluído

- [x] Passo no GitHub Actions: `msgfmt --check`
- [x] `grep` no CI para detectar strings escapando sem `_()`
- [x] Rodar suite com `UPAPASTA_LANG=pt_BR` e `UPAPASTA_LANG=en` no CI

### ~~I5 · Guia de contribuição de tradução `v0.28.0`~~ ✅ Concluído

- [x] `CONTRIBUTING.md` (inglês): seção "Adding a new language"
- [x] `locale/TRANSLATORS` com créditos
- [x] Estrutura para terceira língua (espanhol) suportada via Makefile

---

## 🏁 Critérios de v1.0.0

- [x] Todas as Fases 1 e 2 concluídas ✅
- [x] CI verde (pytest + mypy + ruff) via GitHub Actions ✅ (F1.5)
- [x] Cobertura ≥ 90% nos módulos core (F3.13) ✅
- [x] `--resume` funcional (F2.10) ✅
- [x] Múltiplos servidores NNTP (F2.9) ✅
- [ ] Documentação completa e atualizada (F3.14) ← **único bloqueador restante**
- [x] PyPI publicado (F3.15) ✅
- [x] Zero dependências Python externas ✅

---

## 📋 Resumo de Prioridades

| Fase | Versão | Foco | Itens-chave |
|------|--------|------|-------------|
| 1 | v0.19.x | Estabilidade | F1.1–1.15: docs sync, testes verdes, CI, segurança básica |
| 2 | v0.20.x | Robustez & UX | F2.1–2.17: validação, retry, refactor, resume, multi-server |
| 3 | v0.21.x→v1.0 | Features | F3.1–3.15: webhooks, TMDb, 7z, stats, publicação |
| i18n | v0.26.x→v0.28 | Internacionalização | I1–I5: gettext, strings en/pt-BR, docs em inglês, CI |

**Próximos passos imediatos** (em ordem):
1. ~~F1.1–F1.15~~ ✅ Fase 1 completa
2. ~~F2.1–F2.17~~ ✅ Fase 2 completa (304 testes, 1 skipped intencional)
3. ~~F3.9~~ ✅ `--dry-run --verbose` imprime argv completo
4. ~~F3.3~~ ✅ Webhooks nativos Discord/Telegram/Slack via `WEBHOOK_URL`
5. ~~F3.7~~ ✅ `upapasta --stats` (histórico agregado)
6. ~~F3.11~~ ✅ `profiles.py` separado de `config.py`
7. ~~F3.12~~ ✅ `mypy --strict` no CI (84 erros corrigidos, 20 arquivos)
8. ~~F3.13~~ ✅ Cobertura ≥ 90% nos módulos core (207 testes; cli=100%, nfo=97%, nzb=94%, orchestrator=91%, makerar=91%, makepar=90%, catalog=90%, upfolder=90%; global=82%)
9. ~~F3.1~~ ✅ Múltiplas entradas posicionais (`upapasta a b c`)
10. ~~F3.15~~ ✅ Publicação no PyPI (workflow automatizado)
11. **F3.14** → documentação completa → **desbloqueador de v1.0.0**
12. **I1** → infraestrutura gettext (pré-requisito de toda a i18n)
13. **I2** → extração de strings (em paralelo com I3)
14. **I3** → documentação em inglês (em paralelo com I2)
15. **I4 + I5** → CI de i18n + guia de contribuição
16. **F3.4** → TMDb (desbloqueia F3.5 e F3.6)
17. **F3.8** → TUI `--interactive` (pós-docs)
