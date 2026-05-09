# CLAUDE.md

> Este arquivo é a fonte canônica de contexto para qualquer agente (Claude, GPT, Gemini, Haiku, Sonnet) trabalhando no UpaPasta. Mantenha-o sincronizado com o código — ele é lido **primeiro** em qualquer sessão.

---

## 0. Regras de Economia de Tokens (sempre siga primeiro)

- Para tarefas de exploração, leitura, busca, grep ou mapeamento de código, use preferencialmente o subagent **Explore** (Haiku).
- Nunca use subagents Opus/Sonnet para leitura ou exploração simples.
- Mantenha respostas de subagents curtas, em bullet points.
- Evite paralelismo excessivo de subagents (use só quando realmente necessário).
- Seja extremamente específico nos prompts.
- `clear` ou nova sessão ao trocar de tarefa grande.

---

## 1. Project Overview (estado em 2026-05)

**UpaPasta** é uma ferramenta CLI Python que automatiza o pipeline completo de upload para Usenet com o mínimo de configuração possível.

Versão atual: **0.25.0** (pyproject.toml). Filosofia: menos flags, mais autonomia. Defaults inteligentes, wizard de primeira execução, **stdlib-only** (zero dependências Python externas além de stdlib + binários do sistema).

Pipeline padrão executado por `UpaPastaOrchestrator.run()`:

1. Geração de NFO (mediainfo / ffprobe / tree+stats).
2. Verificação antecipada de conflito de NZB.
3. (Opcional) Criação de RAR5 — **somente** com `--rar`, ou implícito via `--password`, ou para arquivo único com `--obfuscate`/`--password`.
4. (Opcional) Normalização de extensões (`.bin`) com `--rename-extensionless`.
5. Geração de PAR2 (parpar default; preserva estrutura via `filepath-format=common`).
6. Upload via nyuu **sem staging em /tmp** (paths diretos).
7. Pós-processamento do NZB (subjects corrigidos, senha injetada, verificação XML).
8. Cleanup de RAR/PAR2 (a menos que `--keep-files`).
9. Reversão de ofuscação / extensões.
10. Registro em catálogo + execução de hook pós-upload.

---

## 2. Fluxo Recomendado 2026

**RAR não é mais o padrão.** Para pastas com subpastas, o parpar preserva a hierarquia dentro dos `.par2` (`filepath-format=common`) e SABnzbd/NZBGet recentes reconstroem a árvore no download.

```bash
upapasta Pasta/ --obfuscate --backend parpar \
    --filepath-format common --par-profile safe
```

- **RAR-com-senha**: overkill em 2026. Ofuscação forte de subject + nomes + PAR2 já protege contra scans automáticos. Use `--rar --password` somente para sinal social ou downloaders legados.
- **SABnzbd**: desativar "Recursive Unpacking" (preserva `.zip` internos); revisar "Unwanted Extensions" — combinar com `--rename-extensionless` quando há arquivos sem extensão (impede `.txt` automático).
- **Pastas vazias**: NÃO são preservadas sem RAR (NNTP só carrega arquivos). O orchestrator detecta em runtime e avisa. Workaround: `--rar` (preserva diretórios vazios no container) ou arquivos sentinela `.keep`.

---

## 3. Arquitetura Modular (v0.22.3)

Diretório: `upapasta/` (17 módulos, ~5.3k linhas Python). Linhas atualizadas via `wc -l upapasta/*.py`.

| Módulo | Linhas | Responsabilidade |
|---|---|---|
| `__init__.py` | 1 | Marcador de package |
| `_process.py` | 89 | **OBRIGATÓRIO**: `managed_popen` (context manager SIGTERM→SIGKILL para todo subprocess externo) |
| `nntp_test.py` | 93 | `--test-connection`: handshake CONNECT/LOGIN/QUIT via `nntplib` (gracefully degraded em Python 3.14+) |
| `resources.py` | 118 | `calculate_optimal_resources` (threads + memória escalonadas por tamanho da fonte e CPUs); leitura de `/proc/meminfo` |
| `watch.py` | 141 | Modo daemon `--watch` (polling + janela de estabilidade) |
| `ui.py` | 255 | `PhaseBar` (5 fases NFO→RAR→PAR2→UPLOAD→DONE), `_TeeStream` (logging dual stdout+arquivo, strip ANSI), `setup_logging` / `setup_session_log` / `teardown_session_log` |
| `catalog.py` | 269 | **JSONL** local (`~/.config/upapasta/history.jsonl`) + arquivamento de NZB via hardlink em `~/.config/upapasta/nzb/`; detecção de categoria (Anime/TV/Movie/Generic); `run_post_upload_hook` (timeout 60s, env vars `UPAPASTA_*`) |
| `main.py` | 303 | Entry point (~150 linhas reais). Parse args; resolve env via `--profile` ou `--env-file`; despacha para `--config`/`--test-connection` ou para o orquestrador via `from_args`; modos `--each`/`--season`/`--watch` |
| `nfo.py` | 341 | mediainfo (single file) + tree/stats/ffprobe (folder). Detecção de pasta de série via regex `S\d{2}` |
| `config.py` | 287 | `PROFILES` PAR2 (fast/balanced/safe), `REQUIRED_CRED_KEYS`, `DEFAULT_GROUP_POOL` (10 grupos), `prompt_for_credentials`, `load_env_file`, `render_template`, `resolve_env_file(profile)` |
| `makerar.py` | 237 | RAR5 com progresso ao vivo; volumes dinâmicos (≤10 GB → único; senão ≥1 GB por volume, máx 100 partes, redondo a 5 MB); flags `-m0 -ma5 -hp$PASSWORD`; aceita arquivo único e pasta |
| `nzb.py` | 491 | `resolve_nzb_template`, `resolve_nzb_basename`, `resolve_nzb_out`, `handle_nzb_conflict` (rename/overwrite/fail), `inject_nzb_password` (`<meta type="password">`), `fix_nzb_subjects` (deofuscação + path), `fix_season_nzb_subjects`, `merge_nzbs`, `collect_season_nzbs` |
| `cli.py` | 476 | `argparse` com 3 grupos (essenciais/ajuste/avançadas), `_USAGE_SHORT`, `_DESCRIPTION`, `_EPILOG`, `check_dependencies`, `_validate_flags` |
| `upfolder.py` | 664 | `upload_to_usenet`: nyuu **sem cópia para /tmp** (paths relativos preservam subpastas); pool de grupos via `random.choice`; uploader anônimo aleatório; retry automático; verificação XML do NZB; injeção de senha pós-upload |
| `makepar.py` | 856 | parpar (default) ou par2; slice dinâmico baseado em `ARTICLE_SIZE`; `make_parity` aceita `filepath_format` e `parpar_extra_args`; `obfuscate_and_par` refatorado em subfunções (_obfuscate_folder, _obfuscate_rar_vol_set, _obfuscate_single_file, _rename_par2_files, _cleanup_on_par_failure); `handle_par_failure` (retry conservador automático) |
| `_pipeline.py` | 633 | Classes auxiliares do orchestrator: `DependencyChecker` (valida entrada/disco), `PathResolver` (NZB/NFO/PAR2 paths), `PipelineReporter` (banner/stats/sumário/catálogo); funções standalone: `normalize_extensionless`, `revert_extensionless`, `do_cleanup_files`, `revert_obfuscation`, `recalculate_resources` |
| `orchestrator.py` | 602 | `UpaPastaOrchestrator` (workflow completo, delegando às classes de `_pipeline.py`) + `UpaPastaSession` (context manager de cleanup); `from_args` classmethod |

---

## 4. Convenções OBRIGATÓRIAS

1. **Subprocessos externos** (`rar`, `nyuu`, `parpar`, `par2`, hooks de usuário): SEMPRE via `managed_popen` de `_process.py`. NUNCA `subprocess.Popen`/`subprocess.run` direto para esses binários — cria zumbis em Ctrl+C. (Exceção atualmente tolerada: `nfo.py` usa `subprocess.run` para ffprobe/mediainfo curtos; `catalog.py` para hook do usuário com timeout. Ver dívida #2 abaixo.)
2. **Sessão de orquestração**: SEMPRE com `UpaPastaSession(orch)` como context manager. Ele garante `_cleanup_on_error` em qualquer exceção e tratamento especial de `KeyboardInterrupt`.
3. **Códigos de saída** padronizados por módulo:
   - `makerar`: 1=erro genérico, 2=entrada inválida, 3=já existe, 4=binário ausente, 5=erro execução
   - `makepar`: 2=entrada inválida, 3=par2 já existe, 4=binário ausente, 5=erro execução
   - `upfolder`: 1=path inválido, 2=credenciais, 3=PAR2 não encontrado, 4=nyuu ausente, 5=erro nyuu, 6=conflito NZB
   - `main`: 0=ok, 1=falha genérica, 2=erro PAR2, 3=erro upload/conflito NZB, 130=KeyboardInterrupt
4. **Upload sem cópia**: `upfolder.py` invoca nyuu com `cwd=input_path` e paths relativos. Nunca usar `shutil.copytree` em /tmp (era o bug crítico fixado em 0.9.0).
5. **Ofuscação atômica**: `obfuscate_and_par` usa hardlink quando possível (preserva seeding). Fallback para rename físico se cross-device. **Reversão garantida via try/finally** mesmo em Ctrl+C. Helper `_revert_obfuscation` imprime instruções manuais se a reversão automática falhar.
6. **Estilo de comentários**: português; default é não comentar — só comentar **WHY** não-óbvio (constraints, invariantes ocultos, workarounds para bugs específicos).
7. **Stdlib-only**: zero dependências Python (nem `requests`, nem `dotenv`, nem `pyyaml`). Apenas binários externos (`rar`, `nyuu`, `parpar`/`par2`, `mediainfo`, `ffprobe`).
8. **Type hints**: usar `from __future__ import annotations` em todos os módulos para compatibilidade Python 3.9+.

---

## 5. Estado da Versão (0.25.0 — 2026-05-06)

### Histórico recente (últimas releases relevantes)

- **0.18.0** — Inversão de `--skip-rar` (negativa) → `--rar` (positiva); `--password` presume `--rar`; `--obfuscate` permanece independente.
- **0.17.x** — Fixes de `--each`/`--season` (ignorar hardlinks, NZB_OUT_DIR, `S02E` collection); refatoração do NZB de temporada baseado em varredura.
- **0.16.x** — Modo `--season`: episódios individuais + NZB consolidado da temporada com prefixo por episódio nos subjects.
- **0.15.x** — Deep obfuscation para pastas em `--skip-rar`; ofuscação via hardlinks (preserva seeding); restauração automática do nome original; aviso de pastas vazias.
- **0.14.x** — Hardlink fallback; reversão garantida em `--skip-rar`; cobertura de paths nested (8 testes em `test_nested_paths.py`).
- **0.13.x** — Compatibilidade `nntplib` Python 3.14+ (graceful import).
- **0.12.x** — Catálogo JSONL (`history.jsonl`); detecção automática de categoria; hook pós-upload via `POST_UPLOAD_SCRIPT` + variáveis `UPAPASTA_*`; `from_args` classmethod centralizado.
- **0.11.x** — Pool de grupos Usenet aleatório; refatoração modular (main.py de 1400 linhas → cli/orchestrator/ui/watch).
- **0.10.x** — `--each`, `--watch`, `--watch-interval`, `--watch-stable`; RAR automático para arquivo único quando há `--obfuscate`/`--password`.
- **0.9.0** — `_process.py` (managed_popen) + upload sem cópia em /tmp.

### Mapa de Features

| Feature | Estado |
|---|---|
| RAR opt-in (`--rar`) | ✅ 0.18.0 |
| `--password` presume `--rar` | ✅ 0.18.0 |
| Ofuscação via hardlink + fallback rename | ✅ 0.14.2 |
| Deep obfuscation em `--skip-rar` | ✅ 0.15.x |
| Reversão de ofuscação em Ctrl+C (try/finally) | ✅ 0.9.0+ |
| `managed_popen` para subprocessos | ✅ 0.9.0 |
| Upload sem staging /tmp | ✅ 0.9.0 |
| `--each` (cada arquivo = release) | ✅ 0.10.0 |
| `--season` (episódios + NZB consolidado) | ✅ 0.16.0 |
| `--watch` (daemon polling) | ✅ 0.10.4 |
| Pool de grupos aleatório | ✅ 0.11.0 |
| Catálogo de uploads (JSONL) | ✅ 0.12.0 (docs erradas) |
| Hook pós-upload `POST_UPLOAD_SCRIPT` | ✅ 0.12.0 |
| Detecção automática de categoria | ✅ 0.12.0 |
| Slice PAR2 dinâmico via ARTICLE_SIZE | ✅ |
| `--filepath-format` (common/keep/basename/outrel) | ✅ |
| `--parpar-args` / `--nyuu-args` (passthrough shlex) | ✅ |
| `--rename-extensionless` (`.bin` round-trip) | ✅ |
| `--profile <nome>` (multi-perfil) | ✅ |
| `--config` / `--test-connection` | ✅ |
| Retry automático de upload (`--upload-retries`) | ✅ |
| Verificação XML do NZB pós-upload | ✅ |
| Reset/retry conservador de PAR2 (`handle_par_failure`) | ✅ |
| `--resume` / upload parcial | ❌ Pendente |
| Múltiplos servidores NNTP (failover) | ❌ Pendente |
| CI/CD GitHub Actions | ❌ Pendente |
| `mypy --strict` no CI | ❌ Pendente |
| Webhook nativo (Discord/Telegram) | ❌ Pendente |
| TMDb metadata | ❌ Pendente |
| Múltiplas entradas (`upapasta a b c`) | ❌ Pendente |
| Compressor alternativo (7z) | ❌ Pendente |
| ETA de upload pré-pipeline | ❌ Pendente |
| Suporte Windows nativo testado | ❌ Pendente |

---

## 6. Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Binários do sistema necessários:
- **Obrigatórios**: `rar` (RARLAB), `nyuu` (npm install -g nyuu ou GitHub releases), `parpar` (pip install parpar) ou `par2` (apt install par2).
- **Opcionais**: `ffmpeg`/`ffprobe` (metadados de vídeo no NFO), `mediainfo` (NFO técnico de arquivo único).

Configuração: na primeira execução o wizard interativo cria `~/.config/upapasta/.env`. Para reconfigurar: `upapasta --config` (preserva valores existentes; Enter mantém).

---

## 7. Comandos Comuns

```bash
pytest tests/                              # toda a suíte (~146 testes coletados)
pytest tests/test_orchestrator.py -v       # arquivo específico
pytest -k "obfuscate" -v                   # filtro por padrão
pytest tests/test_nested_paths.py -x       # para no primeiro fail

upapasta /path --dry-run                   # pipeline sem upload real
upapasta /path --skip-upload               # gera RAR/PAR2/NFO localmente
upapasta --config                          # reconfigura credenciais
upapasta --test-connection                 # valida handshake NNTP
upapasta --profile myserver /path          # usa perfil alternativo

# Inspecionar histórico (catálogo é JSONL, não SQLite)
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool

# Recuperar NZB arquivado (hardlinks por timestamp em ~/.config/upapasta/nzb/)
ls -la ~/.config/upapasta/nzb/
```

---

## 8. Logging

- `--verbose` → nível DEBUG no logger `upapasta`.
- `--log-file PATH` → handler de arquivo adicional (DEBUG).
- `setup_session_log(input_name, env_file)` cria `~/.config/upapasta/logs/<TS>_<nome>.log` automaticamente em qualquer execução. `_TeeStream` duplica `stdout` para terminal + arquivo, removendo sequências ANSI antes de gravar.
- `teardown_session_log` restaura `sys.stdout` original.

---

## 9. Comportamentos Sutis

- **Pastas vazias**: NNTP só carrega arquivos. PAR2 idem. Em `--skip-rar` (default agora), subdirs sem arquivos somem no destino. O orchestrator detecta em runtime e imprime aviso. Para preservar: usar `--rar` (RAR mantém diretórios vazios) ou colocar `.keep` sentinela.
- **Ofuscação reversível** (`--obfuscate`): renomeia arquivos antes do upload, mas `fix_nzb_subjects` restaura os nomes originais no NZB usando `obfuscated_map`. A estrutura interna é protegida por `_deep_obfuscate_tree` (renomeia arquivos/diretórios dentro de pastas). Recomendado em 2026: proteção balanceada contra DMCA + conveniência de download.
- **Ofuscação máxima** (`--strong-obfuscate`): implica `--obfuscate`, mas `fix_nzb_subjects` pula a reversão quando `strong_obfuscate=True`. Resultado: nomes aleatórios em TUDO (arquivos, estrutura, subjects). Máxima privacidade; requer renomeação manual ou via PAR2 após download. Use para releases privados ou conteúdo sensível.
- **Senha sem RAR**: `--password` sem `--rar` agora **presume `--rar`** automaticamente (válido a partir de 0.18.0). `--skip-rar` + `--password` ainda é erro fatal (legado).
- **Slice dinâmico**: `make_parity` calcula slice = `ARTICLE_SIZE * 2`, escalonado por tamanho total: ≤50 GB→base; ≤100 GB→×1.5; ≤200 GB→×2; >200 GB→×2.5. Clamp 1 MiB–4 MiB. `-S` (auto-scaling) sempre ativo; `--min-input-slices`/`--max-input-slices` ajustados dinamicamente.
- **`backend=par2` + `--skip-rar` em pasta com subdirs**: aviso explícito — par2 clássico não grava paths. O orchestrator sugere migrar para `parpar`.
- **`from_args` classmethod**: ponto único de mapeamento `args → UpaPastaOrchestrator`. Se adicionar uma flag, ajuste o `argparse` em `cli.py` E o `from_args` em `orchestrator.py`.
- **Retry de PAR2 (`handle_par_failure`)**: se a primeira tentativa falhar, reduz threads pela metade e força perfil `safe`, depois re-tenta uma vez. Se ainda falhar, preserva o RAR e instrui o usuário a retomar com `upapasta <rar> --force --par-profile safe`.
- **Pool de grupos**: se `USENET_GROUP=g1,g2,g3,...`, `upfolder.py` faz `random.choice` por upload. O grupo efetivo fica registrado no catálogo.

---

## 10. Estrutura do Repositório

```
upapasta/
├── upapasta/                    # Pacote Python (16 módulos)
├── tests/                       # Suíte pytest (~146 testes em 22 arquivos)
├── scripts/                     # Utilitários standalone (NÃO integrados ao pacote)
│   ├── check_header.py          # stdlib-only (sem dependências)
│   ├── post_upload_nzbfelipe.sh # ignorado via .gitignore
│   └── usenet_backup3-skip-rar.py  # script legado de 15 KB
├── examples/
│   └── post_upload_debug.sh     # exemplo de hook
├── docs/
│   ├── FAQ.md                   # perguntas frequentes
│   ├── TROUBLESHOOTING.md       # diagnóstico por sintoma
│   └── man/upapasta.1           # man page em troff
├── CHANGELOG.md                 # histórico de versões
├── CLAUDE.md                    # este arquivo
├── DOCS.md                      # referência completa
├── INSTALL.md                   # instalação por plataforma
├── README.md                    # vitrine pública
├── TODO.md                      # roadmap interno
├── pyproject.toml               # version=0.28.0, requires-python>=3.9, mypy/ruff configurados
├── .env.example                 # template completo do .env
├── .gitignore
└── LICENSE                      # MIT
```

---

## 11. Qualidade de Código (CI obrigatório)

Todo código gerado deve passar na suíte completa de qualidade antes de ser commitado. **Não commitar sem verificar.**

```bash
ruff check upapasta/ tests/            # linting (erros bloqueiam CI)
ruff format --check upapasta/ tests/   # formatação
mypy upapasta/                         # checagem de tipos
pytest tests/                          # testes (todos devem passar)
```

### Regras obrigatórias para o agente

1. **Antes de qualquer commit**: rodar `ruff check` e `mypy upapasta/` e corrigir todos os erros encontrados.
2. **Imports**: nunca deixar imports não usados (`F401`). Remover ou usar.
3. **Shadowing**: nunca redeclarar variáveis de escopos externos com o mesmo nome (`F841`, `A002`).
4. **Type hints**: sempre usar `from __future__ import annotations` (já convenção do projeto). Anotar retornos e parâmetros em funções públicas.
5. **`type: ignore`**: só adicionar quando há razão documentada (comentário explicando o porquê).
6. **Formatação**: deixar o `ruff format` decidir indentação, quebras de linha e aspas — não contrariar manualmente.
7. **Se CI falhou num push anterior**: rodar a suíte completa (`ruff` + `mypy` + `pytest`) antes de propor qualquer novo commit.

### Configuração dos linters

Os parâmetros de `ruff` e `mypy` estão em `pyproject.toml`. Consultar lá antes de adicionar `# noqa` ou `# type: ignore` para confirmar se a regra já está ignorada globalmente.
