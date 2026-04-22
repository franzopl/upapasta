# Changelog

All notable changes to this project will be documented in this file.

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
