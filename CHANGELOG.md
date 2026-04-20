# Changelog

All notable changes to this project will be documented in this file.

## 0.8.12 - 2026-04-20
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
