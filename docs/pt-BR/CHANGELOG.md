# Changelog

Versão em inglês disponível em [CHANGELOG.md](../../CHANGELOG.md).

Todas as mudanças notáveis para este projeto serão documentadas neste arquivo.

## 0.30.0 - 2026-05-09

### Funcionalidades
- **Simplificação de Flags**: Refatoração da interface de compressão. Substituída a flag `--compressor {rar,7z}` por flags explícitas `--rar` e `--7z`. Introduzida a flag genérica `--compress` (ou `-c`) que respeita o padrão definido no `.env`.
- **Padrões Inteligentes**: O uso de `--password` agora utiliza automaticamente o `DEFAULT_COMPRESSOR` do `.env`. Adicionado um fallback global para **RAR** em sistemas sem preferência configurada.
- **Exclusividade Mútua**: Garantido que `--rar`, `--7z` e `--compress` não possam ser usadas simultaneamente, evitando conflitos de configuração.

## 0.29.0 - 2026-05-09

### Funcionalidades
- **Suporte ao 7z**: Adicionada compatibilidade total com 7-Zip como alternativa ao RAR. Inclui suporte a volumes múltiplos (`.7z.001`), criptografia de cabeçalhos (`-mhe=on`) e barra de progresso em tempo real no Dashboard.
- **Compressor Padrão**: Nova configuração `DEFAULT_COMPRESSOR` no `.env` e no assistente inicial para escolher entre `rar` e `7z`.
- **Neutralidade de Empacotamento**: Refatoração interna do pipeline e UI para usar terminologia genérica "PACK", permitindo suporte transparente a diferentes formatos de container.

## 0.28.0 - 2026-05-09

### Funcionalidades
- **Suporte ao Windows**: Adicionada compatibilidade nativa completa com ambientes Windows. Removida a dependência de `SIGTERM` em favor de terminação segura, aprimorada a detecção de utilitários como parpar/nyuu (incluindo fallback local do `npm`) e eliminação de janelas de console indesejadas em processos em background.

## 0.27.0 - 2026-05-09

### Funcionalidades
- **Elite Obfuscation Suite**: Implementação do modo "schizo" com nomes variáveis (10-30 chars), emails de poster aleatórios via tokens do nyuu, embaralhamento da ordem de upload e jitter no tamanho do artigo (`ARTICLE_SIZE`).
- **Fragmentação Multigrupo**: Uploads para múltiplos grupos agora suportam divisão cruzada avançada via configuração javascript do nyuu.

## 0.26.5 - 2026-05-08

### Performance

- **Geração PAR2**: Aumentado significativamente o limite máximo de threads da CPU para o `parpar` no processamento de arquivos pequenos a médios (< 50GB), se igualando à alocação de processamento do RAR. Isso reduz a lentidão no processo de paridade sem esgotar a largura de banda de memória do sistema.

## 0.26.4 - 2026-05-08

### Melhorias

- **UI/UX**: Substituição do log sequencial por um dashboard de progresso moderno.
- **Dashboard**: Adicionada exibição de metadados em tempo real (Tamanho, Ofuscação, Senha) e um mini-log para eventos recentes.
- **Redução de Ruído**: Silenciada a lista detalhada de limpeza e logs internos de ferramentas (parpar/rar) para focar em informações relevantes.
- **Resumo**: Refatoração do cabeçalho e resumo da operação para uma visão geral pós-upload mais limpa.

## 0.26.3 - 2026-05-07

### Correções

- **UI/UX**: Barras de progresso padronizadas e responsivas para as fases RAR, PAR2 e Upload.
- **Parsing de Progresso**: Adicionado suporte para backspace (`\b`) e códigos de controle ANSI (`\x1b[0G`) no parser de progresso para lidar corretamente com a saída do `rar` e `nyuu`.
- **Buffering**: Mudança para streams binários sem buffer (unbuffered I/O) para evitar atrasos nas atualizações de UI vindas de pipes.
- **Ferramentas Externas**: Melhoria no reporte de progresso do `nyuu` e `parpar` forçando o uso de `stderr` para evitar block-buffering do `stdout`.
- **Segurança de Tipos**: Corrigido erro `NameError: PhaseBar` em `_progress.py` usando `from __future__ import annotations`.

## 0.26.2 - 2026-05-07

### Melhorias

- **Estabilidade**: Refatoração da lógica de leitura de pipes e silenciamento de UI para evitar flicker.

## 0.26.1 - 2026-05-06

### Melhorias

- **Documentação**: Tradução do README, INSTALL, CHANGELOG e TODO para inglês.
- **CI**: Adição de validação automatizada de headers e integridade de i18n.

### Correções

- **Linting**: Corrigido shadowing de variáveis (`_` → `_d`) para evitar conflitos com gettext.
- **Typing**: Resolvidos problemas remanescentes de mypy strict.

## 0.26.0 - 2026-05-06

### Novas funcionalidades

- **Infraestrutura i18n**: Suporte completo para internacionalização usando gettext.
- **Detecção de Locale**: Seleção automática de idioma via `UPAPASTA_LANG` ou configurações do sistema.

## 0.25.1 - 2026-05-06

### Correções

- **mypy `--strict`**: corrigido erro `arg-type` em `ui.py` — `_ThreadDispatchTeeStream` agora aceita `io.TextIOBase` (em vez de `TextIOWrapper`) e usa `cast` no call-site para `sys.__stdout__`. Remove `type: ignore` desnecessário.

## 0.25.0 - 2026-05-06

### Novas funcionalidades

- **Múltiplos inputs posicionais** (`upapasta a b c`): processa em sequência ou `--jobs N` em paralelo usando `concurrent.futures.ThreadPoolExecutor`.
- **Workflow de publicação no PyPI** (`.github/workflows/publish.yml`): on `gh release create` → build → `pypa/gh-action-pypi-publish` via OIDC Trusted Publisher (sem token no repositório).

### Melhorias

- `pyproject.toml`: classifiers, keywords e urls adicionados para melhor visibilidade no PyPI.

## 0.24.2 - 2026-05-05

### Correções

- **`--rar` em arquivo único**: a flag `--rar` agora é sempre honrada para arquivos únicos, mesmo sem `--obfuscate` ou `--password`. Antes, o orchestrator ignorava a flag e forçava `skip_rar=True` nesses casos.
- **`revert_obfuscation` após cleanup**: quando o hardlink já foi removido pelo cleanup, o original (mesmo inode) é corretamente removido usando o `obfuscated_map`.
- **`will_create_rar` simplificado**: condição reduzida para `not self.skip_rar` (correto após refatoração do significado de `skip_rar`).

### Testes

- `test_orchestrator_file_skip_rar_sets_input_target_and_skip_flag`: corrigido para passar `skip_rar=True` (padrão sem `--rar`).
- `test_orchestrator_file_with_rar_flag_creates_rar`: novo teste verificando que `--rar` explícito cria RAR em arquivo único.
- `test_rar_only_file_creates_rar`: atualizado para refletir comportamento correto (RAR criado com `--rar` explícito).

## 0.24.1 - 2026-05-04

### Correções

- **`--dry-run` com `--password`/`--rar`**: path sugerido do RAR mostrava extensão dupla (`arquivo.mkv.rar`). Corrigido para usar `stem` em vez de `name`, gerando o caminho correto (`arquivo.rar`).

### Testes

- Adicionado `tests/test_password_flag.py` (6 testes) cobrindo todas as combinações de `--password`: sem argumento (senha aleatória de 16 chars), com senha explícita, ativação implícita de `--rar`, e unicidade entre gerações consecutivas.

## 0.24.0 - 2026-05-04

### Novas Features

- **F2.9 — Múltiplos servidores NNTP com failover**: configure `NNTP_HOST_2`, `NNTP_HOST_3` ... `NNTP_HOST_9` no `.env` para failover automático. Em caso de falha, o próximo servidor da lista é tentado na próxima retry. Campos não definidos (porta, user, pass, SSL) herdam do servidor primário. Atualizado `.env.example` com exemplo comentado.
- **F2.10 — `--resume` / upload parcial**: retoma upload interrompido via Ctrl+C ou falha de rede. Antes de iniciar, salva `.upapasta-state.json` junto ao NZB. Em `--resume`, detecta arquivos já postados via NZB parcial existente, faz upload apenas dos restantes, mescla os NZBs e remove o state file ao final.
- **F2.12 — NFO multi-track**: o NFO de pastas agora exibe faixas de áudio e legendas para arquivos `.mkv`/`.mp4` com múltiplos idiomas (ex: `Audio: POR, ENG | Legendas: POR`). Também exibido por arquivo na árvore de diretórios. Usa `ffprobe -of json` para uma única chamada (consolidado com F2.11).

### Testes

- 14 novos testes em `test_phase2.py` cobrindo F2.9 (`_build_server_list`), F2.10 (`_get_uploaded_files_from_nzb`, `_save_upload_state`, `_load_upload_state`) e F2.12 (`_get_video_info` com monkeypatch do ffprobe JSON).
- Total: 293 passed, 1 skipped.

## 0.23.1 - 2026-05-04

### Correções (CI/Linting)

- **Linting ruff**: Corrigidos 150+ erros de ruff (imports desordenados, variáveis não utilizadas, tabs vs espaços).
  - Reorganizados imports em ordem correta (stdlib → terceiros → locais) em todos os módulos de teste.
  - Removidas variáveis atribuídas mas nunca usadas (`quiet`, `log_time`, `check_connections`, etc.) em `upfolder.py`.
  - Convertidos tabs para espaços em `makerar.py` (W191).
  - Corrigidos nomes ambíguos de variáveis (`l` → `line`).
- **CI/GitHub Actions**: Testes agora passam 100% em Python 3.9, 3.11, 3.12. Ruff check ✅, mypy ✅, pytest ✅ (252 passed, 1 skipped).

## 0.23.0 - 2026-05-04

### Novas Features

- **`--strong-obfuscate`**: novo flag para máxima privacidade — mantém nomes aleatórios também dentro do NZB (ninguém em indexadores sabe o conteúdo). Diferente de `--obfuscate` (reversível), requer renomeação manual ou via PAR2 após download. Implica automaticamente `--obfuscate`. Use para releases privados ou conteúdo sensível.

### Melhorias

- **Ofuscação reversível bem documentada**: DOCS.md e README.md agora explicam claramente a diferença entre `--obfuscate` (proteção DMCA + conveniência) e `--strong-obfuscate` (privacidade máxima).
- **CLAUDE.md atualizado**: seção "Comportamentos Sutis" documenta a implementação de ofuscação em `fix_nzb_subjects` e fluxo em `obfuscate_and_par`.

## 0.22.3 - 2026-05-04

### Correções (Bugfix)

- **Ofuscação de Assuntos e Extensões**: Corrigido bug onde o nome original vazava no NZB e extensões eram mal identificadas em uploads ofuscados.
  - Substituído uso de `-s` (subject) por `-t` (comment) no `nyuu` para preservar formatação padrão de assuntos com nomes de arquivos.
  - Refatorada a função `fix_nzb_subjects` para extrair nomes de arquivos diretamente dos assuntos do NZB, eliminando erros de mapeamento por ordem.
  - Adicionado suporte a deofuscação de arquivos `.par2` e volumes `.volNN+MM.par2` no NZB.
  - Corrigido bug onde arquivos `.par2` não recebiam o prefixo de pasta em uploads de temporada (`--season`).

## 0.22.2 - 2026-05-04

### Correções (Bugfix)

- **`--obfuscate` sem `--password`**: corrigido bug onde arquivo único com ofuscação criava RAR automaticamente (gerava senha aleatória). Agora segue a filosofia de 2026: `--obfuscate` sem `--password` = ofuscação + PAR2 direto, sem RAR. Apenas `--password` (explícito) presume `--rar` automaticamente.
- **Barra de progresso do nyuu**: restaurada exibição da barra de progresso durante upload. O stderr do nyuu agora vai para o terminal normalmente (estava sendo redirecionado para captura de erros).

## 0.22.1 - 2026-05-04

### Correções (Bugfix)

- **Ofuscação de arquivo único**: corrigido bug onde parpar era executado com arquivo original em vez de ofuscado, causando inconsistência de nomes no NZB (Part #1 com nome original, PAR2s com ofuscado). Agora metadados do PAR2 são consistentes com nomes ofuscados.

## 0.22.0 - 2026-05-04

### Refatorações internas (sem quebra de API)

- **`_pipeline.py`** (novo módulo, 601 linhas): extrai `DependencyChecker`, `PathResolver` e `PipelineReporter` de `orchestrator.py`; funções auxiliares standalone `normalize_extensionless`, `revert_extensionless`, `do_cleanup_files`, `revert_obfuscation`, `recalculate_resources`.
- **`orchestrator.py`**: 1087 → 599 linhas (Single Responsibility — delega validação, resolução de caminhos e relatório às novas classes).
- **`makepar.py::obfuscate_and_par`**: 195 → 76 linhas; extraídas subfunções `_obfuscate_folder`, `_obfuscate_rar_vol_set`, `_obfuscate_single_file`, `_rename_par2_files`, `_cleanup_on_par_failure`.
- **33 testes novos** em `tests/test_pipeline.py` (252 testes no total).

## 0.21.0 - 2026-05-04

### Novas Features

- **ETA pré-pipeline**: estimativa de tempo de upload exibida antes do início do pipeline, calculada por conexões NNTP (500 KB/s por conexão).
- **Validação antecipada**: `orchestrator.validate()` verifica espaço em disco (≥2× tamanho da fonte) e permissões de leitura antes de iniciar o pipeline.
- **`--insecure` em `--test-connection`**: desativa verificação de certificado CA para servidores com certificados auto-assinados.
- **CA certs por padrão** em `--test-connection`: usa `ssl.create_default_context()` com verificação completa de cadeia.

### Melhorias

- **`_progress.py`** (novo módulo): extrai `_read_output` e `_process_output` de `makerar.py` e `makepar.py`, eliminando duplicação.
- **`nfo._get_video_info()`**: uma única chamada `ffprobe` substitui `_get_video_duration` + `_get_video_metadata` (menos subprocessos).
- **`resources.get_total_size`**: cache `@lru_cache(maxsize=64)` evita re-walk do filesystem durante o pipeline.
- **Retry com backoff exponencial**: uploads repetem com delays 30s→90s→270s + jitter ±10%; stderr do nyuu lido em thread separada para não bloquear retry.
- **Tradução de erros nyuu** em `upfolder._parse_nyuu_stderr()`: mapeia códigos 401, 502, timeout, SSL e ECONNREFUSED para mensagens legíveis.
- **Limpeza de PAR2 parciais** em `obfuscate_and_par`: bloco `finally` remove `random_base*.par2` e `orig*.par2` em caso de falha.
- **Timestamp ISO** nos logs: handler de stream exibe timestamp quando `--verbose`; handler de arquivo sempre exibe.

### Testes

- `tests/test_phase2.py` (389 linhas, 219 testes verdes): cobertura de validação, ETA, retry, tradução de erros, cache de recursos, limpeza PAR2, e refatoração de progress.
- `tests/test_ui.py` (241 linhas): 27 testes para `PhaseBar`, `_TeeStream` e `format_time` (cobertura zero anterior).
- `tests/test_resources.py` (184 linhas): cobertura de `calculate_optimal_resources` e `get_total_size`.
- `tests/test_watch.py`: testes para `_item_size` (arquivo/pasta/inexistente) e `_watch_loop` com mock.

### Correções

- **`scripts/check_header.py`**: removida dependência `python-dotenv`; usa `config.load_env_file` + `ssl.create_default_context` (stdlib-only).
- **`--season` integração**: testes de integração suspensos temporariamente (mock de round-trip pendente).

### Documentação

- **README.md**: seção "Hooks Pós-Upload" expandida com tabela completa de variáveis `UPAPASTA_*` e referência a `examples/`.
- **`examples/post_upload_debug.sh`**: exemplo de hook adicionado ao repositório.

## 0.16.1 - 2026-04-30

### Correções (Fixes)

- **Caminho de saída da Temporada**: corrigido erro onde o NZB e NFO consolidados de uma temporada eram salvos no diretório de instalação do script (ex: `~/.local/bin`) em vez do diretório atual de execução.

## 0.16.0 - 2026-04-30

### Novas Features (New Features)

- **Modo `--season`**: upload individual de cada episódio (como o `--each`), mas ao final gera um NZB e um NFO consolidados para a temporada inteira, sem realizar novos uploads. Ideal para organização de séries onde se deseja tanto os episódios avulsos quanto o pack completo.

## 0.14.2 - 2026-04-29

### Melhorias (Improvements)

- **Ofuscação via Hardlinks**: agora o UpaPasta utiliza hardlinks para ofuscação in-place (fluxo `--skip-rar`). Isso evita que o cliente de torrent perca o acesso aos arquivos originais durante o upload, permitindo continuar o seeding sem interrupções.
- **Fallback de Ofuscação**: caso o sistema de arquivos não suporte hardlinks (ex: cross-device), o sistema reverte automaticamente para a renomeação física (com aviso ao usuário).

## 0.14.1 - 2026-04-29

### Correções (Fixes)

- **Correção na reversão de ofuscação in-place**: no fluxo `--skip-rar --obfuscate`, a pasta original era renomeada permanentemente para o nome ofuscado. Adicionado mecanismo de reversão automática que restaura o nome original após upload bem-sucedido, em falhas de upload, ou quando `--skip-upload` é utilizado.

## 0.14.0 - 2026-04-29

### Novas Features

- **Aviso de pastas vazias em `--skip-rar`**: o orchestrator detecta diretórios vazios em runtime e imprime aviso explicando que NNTP/PAR2 não preservam diretórios sem arquivos, sugerindo remover `--skip-rar` (RAR preserva) ou usar arquivo sentinela.

### Documentação

- Nova seção em `DOCS.md` documentando a limitação de pastas vazias e o workaround com RAR.
- Corrigida nota obsoleta sobre `--skip-rar` em pastas com subpastas (hoje é o fluxo recomendado com parpar `-f common`).

### Testes

- Nova suíte `tests/test_nested_paths.py` (8 testes) cobrindo: profundidade extrema (5+ níveis), unicode/espaços/caracteres especiais, pastas vazias, arquivos ocultos, symlinks, obfuscate combinado com nested upload, e round-trip de `--rename-extensionless` em subdiretórios profundos.

## 0.12.1 - 2026-04-22

### Melhorias

- **Resolução de caminhos NZB**: Melhoria na inteligência de caminhos de saída. Agora o UpaPasta aceita apenas uma pasta no `NZB_OUT` e anexa automaticamente o template `{filename}.nzb`, facilitando a configuração para integração com outras ferramentas.

## 0.12.0 - 2026-04-22

### Novas Features

- **Catálogo de uploads (`catalog.py`)**: arquivo JSONL append-only em `~/.config/upapasta/history.jsonl` criado automaticamente. Registra a cada upload bem-sucedido: timestamp, nome original, nome ofuscado, senha RAR, tamanho, categoria detectada, grupo Usenet efetivo, servidor NNTP, redundância PAR2, duração, número de volumes RAR e caminho do NZB. NZBs são arquivados em `~/.config/upapasta/nzb/` via hardlink — recuperáveis mesmo que o arquivo físico seja movido ou apagado.
- **Detecção automática de categoria**: analisa o nome do arquivo para inferir `Anime` (`[SubGroup] Título - 01`), `TV` (`S01E01`, `1x01`, `Season 2`), `Movie` (ano 19xx/20xx isolado no título) ou `Generic`. Sem flags manuais.
- **Hook pós-upload (`POST_UPLOAD_SCRIPT`)**: configure um script externo no `.env`. O UpaPasta o executa após cada upload bem-sucedido passando informações via variáveis de ambiente `UPAPASTA_*` (NZB, NFO, senha, nome original/ofuscado, tamanho, grupo). Timeout de 60s; falha no hook não afeta o código de saída principal.

### Melhorias Internas

- `UpaPastaOrchestrator.from_args()`: classmethod que centraliza o mapeamento `args → UpaPastaOrchestrator`. Elimina duplicação entre `main.py` e `watch.py` — novos parâmetros precisam ser adicionados em apenas um lugar.

## 0.11.0 - 2026-04-22

### Novas Features

- **Pool de Grupos Usenet**: Suporte a listas de grupos de notícias (pool) com seleção aleatória por upload. Isso aumenta a obfuscação e redundância, evitando que todos os posts fiquem concentrados em um único grupo. O assistente de configuração agora sugere uma pool padrão de 10 grupos populares.
- **Melhoria no NFO**: O módulo de upload (`upfolder.py`) agora é capaz de gerar arquivos NFO tecnicamente descritivos de forma independente para uploads de arquivos únicos.

### Refatoração

- **Arquitetura Modular**: Grande desmembramento do `main.py` (anteriormente com >1400 linhas) em módulos especializados:
  - `cli.py`: Gerenciamento de argumentos e dependências.
  - `orchestrator.py`: Lógica central do workflow.
  - `ui.py`: Interface de usuário, barras de progresso e logging.
  - `watch.py`: Lógica do modo daemon/monitoramento.
  - `main.py`: Ponto de entrada simplificado.

## 0.10.5 - 2026-04-22

### Melhorias

- **UX em `--watch`**: Adição de um cabeçalho estruturado ao iniciar o modo monitoramento.
- **Spinner Interativo**: Substituição de mensagens ociosas repetitivas por um spinner animado (`|`, `/`, `-`, `\`) em uma única linha, mantendo o terminal limpo e indicando atividade sem poluir arquivos de log.
- **Feedback de Processamento**: Mensagens mais claras ao detectar novos itens, verificar estabilidade de tamanho e concluir o processamento de cada tarefa.

## 0.10.4 - 2026-04-22

### Novas Features

- **`--watch`**: modo daemon que monitora um diretório e processa automaticamente cada novo item (arquivo ou pasta) que aparecer. Usa polling via stdlib (sem dependências externas). Cada item detectado passa pelo pipeline completo (RAR → PAR2 → upload → NZB). Compatível com `--obfuscate`, `--password`, `--dry-run`. Ctrl+C encerra graciosamente.
- **`--watch-interval N`**: intervalo de varredura em segundos (padrão: 30).
- **`--watch-stable N`**: segundos que o tamanho do item deve permanecer estável antes de processar — evita processar arquivos ainda sendo copiados (padrão: 60).

## 0.10.3 - 2026-04-22

### Correções

- Fix: PhaseBar da fase RAR permanecia em `⬜` (pending) em arquivo único com `--obfuscate`/`--password`, mesmo com o RAR sendo criado. A condição de ativação da barra agora considera corretamente os casos onde RAR é gerado automaticamente.

## 0.10.2 - 2026-04-22

### Correções

- Fix: `--obfuscate` volta a gerar senha aleatória automaticamente quando `--password` não é fornecida. Ofuscar nome sem proteger conteúdo é proteção pela metade — a senha é injetada no NZB e extraída automaticamente por SABnzbd/NZBGet.

## 0.10.1 - 2026-04-22

### Correções

- Fix: PhaseBar mostrava RAR como `⏭ skipped` em arquivo único com `--obfuscate`/`--password`, mesmo quando o RAR era criado automaticamente
- Fix: Sumário final mostrava "Arquivo: ...mkv" em vez de "RAR: nome_ofuscado.rar" porque checava `os.path.exists` após o cleanup já ter removido o arquivo

## 0.10.0 - 2026-04-22

### Novas Features

- **`--each`**: processa cada arquivo de uma pasta individualmente — cada arquivo vira um release separado com seu próprio NZB. Ideal para temporadas de séries.
- **RAR automático para arquivo único**: ao usar `--obfuscate` ou `--password` com um arquivo único, o UpaPasta agora cria o RAR automaticamente (ofuscação real requer container; senha requer container).
- **`make_rar` aceita arquivo único**: `makerar.py` suporta arquivo único além de pastas, sem volume splitting.
- **Sem argumentos**: `upapasta` sem argumentos exibe mensagem de uso amigável em vez do erro do argparse.

### Mudanças de Comportamento

- **`--obfuscate` e `--password` são independentes**: removida a geração automática de senha ao usar `--obfuscate`. Cada flag tem efeito exclusivo — obfuscate renomeia arquivos, password protege o conteúdo.
- **Aviso de subpastas com `--skip-rar`**: ao usar `--skip-rar` em pasta com subpastas, exibe aviso sobre risco de estrutura quebrada após download.
- **`--skip-rar + --password` é erro fatal**: combinação incompatível encerra com mensagem clara.
- **`--skip-rar + --obfuscate`**: exibe aviso de ofuscação parcial e aguarda 3s antes de continuar.

### CLI

- `--help` reescrito com grupos de argumentos (essenciais / ajuste / avançadas), exemplos e seção de comportamento padrão no epilog.
- Grupos de argumentos no help: opções essenciais, opções de ajuste, opções avançadas.

### Docs

- README reescrito com foco na simplicidade: tabela de comportamento padrão, exemplos por caso de uso, regras de auto-RAR, explicação do modo store `-m0`.
- CLAUDE.md atualizado: `_process.py` documentado, regras OBRIGATÓRIO para `managed_popen` e `UpaPastaSession`, seção de Logging.
- TODO.md revisado: itens implementados removidos, novos desafios adicionados, meta v1.0.0 definida.

## 0.9.0 - 2026-04-21

### Segurança / Correções Críticas

- **Fix [CRÍTICO]**: `upfolder.py` — eliminada a cópia de dados para `/tmp` com `shutil.copytree` antes do upload de pastas. O nyuu agora é invocado com `cwd=input_path` e caminhos relativos construídos via `os.path.relpath`, zerando o I/O extra (era fatal para pastas de dezenas de GB)
- **Fix [ALTO]**: Graceful shutdown em todos os subprocessos (`rar`, `parpar`, `par2`, `nyuu`) — novo módulo `_process.py` com `managed_popen` context manager que garante `SIGTERM → SIGKILL` no processo filho em qualquer saída, incluindo `KeyboardInterrupt` (Ctrl+C). Elimina processos zumbi
- **Fix [ALTO]**: Proteção de dados na ofuscação — `obfuscate_and_par` reescrito com `try/finally` blindado. Novo helper `_revert_obfuscation` com mensagens explícitas de progresso e instruções manuais de fallback. A reversão dos renames do usuário agora é garantida mesmo em Ctrl+C durante a geração do PAR2
- **Fix [MÉDIO]**: Compatibilidade real com Python 3.8 — `from __future__ import annotations` adicionado a todos os módulos; sintaxe `X | Y` em anotações de função substituída por `Optional[X]` / `Tuple[X, Y]` de `typing`. A sintaxe `X | Y` só é válida em runtime no Python 3.10+

### Novas Features Internas

- `upapasta/_process.py`: novo módulo com `managed_popen()` e `_terminate_process()` compartilhados por makerar, makepar e upfolder
- `makepar._revert_obfuscation()`: função centralizada de reversão da ofuscação com feedback detalhado e instruções de recuperação manual


- Feat: questionário inicial reformulado — exibe cabeçalho, duas seções (Servidor / Upload), valida porta e campos obrigatórios, aceita Enter para confirmar defaults e exibe resumo antes de salvar
- Feat: `.env` gerado automaticamente na primeira execução contém todas as variáveis configuráveis com comentários explicativos (igual ao `.env.example`)
- Docs: `.env.example` atualizado — comentários mais descritivos, grupo padrão alterado para `alt.binaries.boneless`, `DUMP_FAILED_POSTS` vazio por padrão
- Docs: README — seção Configuração reescrita com exemplo do questionário e tabela de variáveis principais

## 0.8.1 - 2026-04-19
- Fix: nome do NZB preserva tags completas (ex: `.DUAL-EcK`) — `splitext()` era aplicado duplamente sobre o basename já sem extensão no `obfuscated_map`

## 0.8.0 - 2026-04-19
- Feat: ofuscação real — RAR/PAR2 são renomeados fisicamente no disco com nomes aleatórios de 12 caracteres (`--obfuscate`); NZB salvo com o nome original preservado
- Feat: suporte a volume sets — todos os arquivos `nome.part*.rar` são renomeados atomicamente para `random.part*.rar`; PAR2 gerado depois da renomeação
- Feat: senha RAR automática — com `--obfuscate`, senha segura de 16 caracteres gerada via `secrets` e aplicada com `-hp` (cifra conteúdo E nomes internos)
- Feat: `--password SENHA` para senha RAR customizável (funciona com ou sem `--obfuscate`)
- Feat: senha injetada no `.nzb` como `<meta type="password">` para extração automática por SABnzbd, NZBGet e outros clientes
- Feat: senha e nome ofuscado exibidos no cabeçalho e no sumário final do workflow
- Fix: revert automático da renomeação em caso de falha na geração do PAR2

## 0.7.0 - 2026-04-18
- Feat: logging estruturado com `setup_logging()` e flag `--verbose` para nível DEBUG
- Feat: `--par-slice-size` para override manual do tamanho de slice PAR2
- Feat: `--upload-timeout` passa timeout de conexão ao nyuu (`--timeout N`)
- Feat: `--upload-retries` implementa retry automático em falha de upload (N tentativas extras)
- Feat: verificação pós-upload do NZB gerado (existência, tamanho > 0, elemento `<file>` via XML)
- Fix: error handling diferenciado — `FileNotFoundError`, `PermissionError`, `OSError` em vez de `except Exception` genérico em makerar, makepar e upfolder
- Docs: heurística `target_slices=4` em makepar.py documentada com exemplos e orientação para arquivos grandes
- Tests: +17 testes cobrindo cleanup, multivolume RAR, keep-files, error paths de RAR/PAR2, verificação de NZB e retry de upload

## 0.6.8 - 2026-04-18
- Fix: RAR volume thresholds ajustados — arquivos até 10 GB geram RAR único; acima disso volumes de no mínimo 1 GB (antes: split a partir de 200 MB com partes de 50 MB)

## 0.6.7 - 2026-04-18
- Fix: cleanup now deletes all RAR volumes and PAR2 files after successful upload — previously only the first 2 files were removed due to incorrect .partXX suffix stripping (only 2-digit parts were handled, but rar generates 3-digit parts like .part001)

## 0.6.6 - 2026-04-18
- Fix: make_rar() now returns generated RAR path to fix part001.rar detection for large archives (>99 parts)
- Fix: Added force mode to remove existing partial RAR volumes before creating new ones
- Fix: Improved RAR volume detection to handle both part01.rar and part001.rar naming schemes

## 0.6.5 - 2026-04-18
- Feat: series folders (SXX / SXXEXX pattern) generate NFO using mediainfo of the first episode; generic folders keep the tree+stats layout

## 0.6.4 - 2026-04-18
- Feat: new NFO banner — clean ASCII art "UPAPASTA" with border, fits 80 columns, pure ASCII (compatible with all NFO viewers)

## 0.6.3 - 2026-04-18
- Fix: NFO and NZB filenames now match the source folder name exactly (no _content suffix)
- Fix: NZB basename for RAR volume sets strips the .partXX suffix correctly

## 0.6.2 - 2026-04-18
- Fix: PAR2 generation now covers all RAR volumes in a set (not just part01.rar)
- Fix: upload now sends all RAR volume parts + their PAR2 files
- Fix: PAR2 filename uses the set base name (without .part01 suffix)

## 0.6.1 - 2026-04-18
- Fix: detect RAR volumes (part01.rar…partNN.rar) after creation — single-file check was failing for multi-part sets
- Fix: cleanup now removes all RAR volume parts, not just the first file
- Fix: summary stats now sum all RAR volumes for correct total size display

## 0.6.0 - 2026-04-18
- Feature: Automatic RAR volume splitting for Usenet best practices — folders < 200 MB generate a single RAR; larger folders are split into volumes (min 50 MB each, max 100 parts)
- Docs: Rewrite README with prerequisites table, all CLI options documented, and RAR volume logic explained

## 0.5.0 - 2025-12-18
- Feature: Add configurable ASCII art banner for folder .nfo files via NFO_BANNER env variable
- Feature: Enhanced folder .nfo generation with detailed statistics, tree structure, and video metadata
- Feature: Extract video duration, resolution, codec, and bitrate using ffprobe for rich .nfo content
- Feature: Default UpaPasta ASCII banner when custom banner not configured
- Fix: Sanitize mediainfo "Complete name" field to show only filename for video files
- Docs: Update README with NFO configuration options and ffmpeg dependency information

## 0.4.0 - 2025-12-17
- Feature: Implement obfuscated upload feature with subject obfuscation
- Feature: Add NZB conflict handling (--nzb-conflict option)
- Fix: Move .nfo generation to workflow start for better organization

## 0.3.4 - 2025-12-14
- Fix: Early NZB conflict detection before processing to avoid wasted work
- Fix: Automatic cleanup of temporary PAR2 files when errors occur
- Performance: Skip PAR2 generation when NZB conflict is detected with 'fail' mode

## 0.3.3 - 2025-12-14
- Fix: Correct NZB filename for folders processed with `--skip-rar` flag (remove unwanted "_content" suffix).

## 0.3.2 - 2025-12-14
- Feature: Add NZB conflict handling with `--nzb-conflict` option (rename|overwrite|fail) to control behavior when NZB file already exists.
- Docs: Add example for sequential uploads using `--nzb-conflict fail`.

## 0.3.1 - 2025-12-14
- Fix: Prevent duplicate `.nfo` file creation in dry-run for single-file uploads.
- Feature: Accept single-file uploads (skip RAR by default) and generate PAR2, PAR2 generation improvements.
- Feature: Generate `.nfo` for single-file uploads using `mediainfo` and save to NZB_OUT folder; `.nfo` not uploaded to Usenet.
- Tests: Added/updated tests covering `.nfo` generation and upload flows.
