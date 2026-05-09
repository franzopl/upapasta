# Changelog

All notable changes to this project will be documented in this file.

Portuguese version available at [docs/pt-BR/CHANGELOG.md](docs/pt-BR/CHANGELOG.md).

## 0.30.0 - 2026-05-09

### Features
- **Simplified CLI Flags**: Refactored compression interface. Replaced `--compressor {rar,7z}` with explicit `--rar` and `--7z` flags. Added a generic `--compress` (or `-c`) flag that respects the `.env` default.
- **Intelligent Defaults**: `--password` now automatically uses the `DEFAULT_COMPRESSOR` from `.env`. Added a global fallback to **RAR** for systems without a configured preference.
- **Mutual Exclusivity**: Ensured that `--rar`, `--7z`, and `--compress` cannot be used together, preventing configuration conflicts.

## 0.29.0 - 2026-05-09

### Features
- **7z Support**: Added full support for 7-Zip as an alternative to RAR. Includes multi-volume archives (`.7z.001`), header encryption (`-mhe=on`), and live progress tracking in the Dashboard.
- **Default Compressor**: New `DEFAULT_COMPRESSOR` setting in `.env` and configuration wizard to choose between `rar` and `7z`.
- **Packaging Neutrality**: Refactored internal pipeline and UI to use generic "PACK" terminology, ensuring seamless support for any container format.

## 0.28.0 - 2026-05-09

### Features
- **Windows Support**: Added full native compatibility for Windows environments. Fixed `SIGTERM` reliance, improved CLI tool discovery including local `node_modules` fallback, and ensured background processes do not spawn visible console windows.

## 0.27.0 - 2026-05-09

### Features
- **Elite Obfuscation**: Introduced variable name lengths, randomized poster domains via nyuu tokens, upload list shuffling, and `ARTICLE_SIZE` jitter for robust stealth.
- **Cross-Group Fragmentation**: Enhanced `--obfuscate` to distribute multi-group uploads efficiently via nyuu JavaScript configuration.

## 0.26.5 - 2026-05-08

### Performance

- **PAR2 Generation**: Significantly increased the maximum allowed CPU threads for `parpar` when processing small-to-medium files (< 50GB), matching the thread allocation strategy used for RAR creation. This reduces the processing time bottleneck without exhausting memory bandwidth.

## 0.26.4 - 2026-05-08

### Improvements

- **UI/UX**: Replaced the sequential log with a modern progress dashboard.
- **Dashboard**: Added live metadata display (Size, Obfuscation, Password) and a mini-log for recent events.
- **Noise Reduction**: Silenced detailed cleanup lists and internal tool logs (parpar/rar) to focus on relevant information.
- **Summary**: Refined the operation header and summary for a cleaner post-upload overview.

## 0.26.3 - 2026-05-07

### Fixes

- **UI/UX**: Standardized and responsive progress bars for RAR, PAR2, and Upload phases.
- **Progress Tracking**: Added support for backspace (`\b`) and ANSI control codes (`\x1b[0G`) in the progress parser to handle `rar` and `nyuu` output correctly.
- **Buffering**: Switched to unbuffered binary I/O for external tool pipes to prevent stalled UI updates.
- **External Tools**: Improved `nyuu` and `parpar` progress reporting by forcing `stderr` usage to avoid stdout block-buffering.
- **Type Safety**: Fixed `PhaseBar` NameError in `_progress.py` using `from __future__ import annotations`.

## 0.26.2 - 2026-05-07

### Improvements

- **Stability**: Refactored internal pipe reading and UI silencing logic to prevent flickering.

## 0.26.1 - 2026-05-06

### Improvements

- **Documentation**: Translated README, INSTALL, CHANGELOG, and TODO to English.
- **CI**: Added automated header validation and i18n checks.

### Fixes

- **Linting**: Fixed variable shadowing (`_` → `_d`) to avoid conflicts with gettext.
- **Typing**: Resolved remaining mypy strict issues.

## 0.26.0 - 2026-05-06

### New Features

- **i18n Infrastructure**: Full support for internationalization using gettext.
- **Locale Detection**: Automatic language selection via `UPAPASTA_LANG` or system settings.

## 0.25.1 - 2026-05-06

### Fixes

- **mypy `--strict`**: fixed `arg-type` error in `ui.py` — `_ThreadDispatchTeeStream` now accepts `io.TextIOBase` (instead of `TextIOWrapper`) and uses `cast` at the call-site for `sys.__stdout__`. Removes unnecessary `type: ignore`.

## 0.25.0 - 2026-05-06

### New Features

- **Multiple positional inputs** (`upapasta a b c`): processes in sequence or `--jobs N` in parallel using `concurrent.futures.ThreadPoolExecutor`.
- **PyPI publication workflow** (`.github/workflows/publish.yml`): on `gh release create` → build → `pypa/gh-action-pypi-publish` via OIDC Trusted Publisher (no token in the repository).

### Improvements

- `pyproject.toml`: classifiers, keywords, and URLs added for better visibility on PyPI.

## 0.24.2 - 2026-05-05

### Fixes

- **`--rar` on single file**: the `--rar` flag is now always honored for single files, even without `--obfuscate` or `--password`. Previously, the orchestrator ignored the flag and forced `skip_rar=True` in these cases.
- **`revert_obfuscation` after cleanup**: when the hardlink has already been removed by cleanup, the original (same inode) is correctly removed using the `obfuscated_map`.
- **Simplified `will_create_rar`**: condition reduced to `not self.skip_rar` (correct after refactoring the meaning of `skip_rar`).

### Tests

- `test_orchestrator_file_skip_rar_sets_input_target_and_skip_flag`: fixed to pass `skip_rar=True` (default without `--rar`).
- `test_orchestrator_file_with_rar_flag_creates_rar`: new test verifying that explicit `--rar` creates RAR on a single file.
- `test_rar_only_file_creates_rar`: updated to reflect correct behavior (RAR created with explicit `--rar`).

## 0.24.1 - 2026-05-04

### Fixes

- **`--dry-run` with `--password`/`--rar`**: suggested RAR path showed double extension (`file.mkv.rar`). Fixed to use `stem` instead of `name`, generating the correct path (`file.rar`).

### Tests

- Added `tests/test_password_flag.py` (6 tests) covering all combinations of `--password`: no argument (random 16-char password), with explicit password, implicit `--rar` activation, and uniqueness between consecutive generations.

## 0.24.0 - 2026-05-04

### New Features

- **F2.9 — Multiple NNTP servers with failover**: configure `NNTP_HOST_2`, `NNTP_HOST_3` ... `NNTP_HOST_9` in `.env` for automatic failover. In case of failure, the next server in the list is tried on the next retry. Unset fields (port, user, pass, SSL) inherit from the primary server. Updated `.env.example` with commented example.
- **F2.10 — `--resume` / partial upload**: resumes interrupted upload via Ctrl+C or network failure. Before starting, saves `.upapasta-state.json` next to the NZB. In `--resume`, detects files already posted via existing partial NZB, uploads only the remaining ones, merges NZBs, and removes the state file at the end.
- **F2.12 — Multi-track NFO**: folder NFO now displays audio tracks and subtitles for `.mkv`/`.mp4` files with multiple languages (e.g., `Audio: POR, ENG | Subtitles: POR`). Also displayed per file in the directory tree. Uses `ffprobe -of json` for a single call (consolidated with F2.11).

### Tests

- 14 new tests in `test_phase2.py` covering F2.9 (`_build_server_list`), F2.10 (`_get_uploaded_files_from_nzb`, `_save_upload_state`, `_load_upload_state`), and F2.12 (`_get_video_info` with ffprobe JSON monkeypatch).
- Total: 293 passed, 1 skipped.

## 0.23.1 - 2026-05-04

### Fixes (CI/Linting)

- **Ruff linting**: Fixed 150+ ruff errors (unsorted imports, unused variables, tabs vs spaces).
  - Reorganized imports in correct order (stdlib → third-party → local) in all test modules.
  - Removed variables assigned but never used (`quiet`, `log_time`, `check_connections`, etc.) in `upfolder.py`.
  - Converted tabs to spaces in `makerar.py` (W191).
  - Fixed ambiguous variable names (`l` → `line`).
- **CI/GitHub Actions**: Tests now pass 100% on Python 3.9, 3.11, 3.12. Ruff check ✅, mypy ✅, pytest ✅ (252 passed, 1 skipped).

## 0.23.0 - 2026-05-04

### New Features

- **`--strong-obfuscate`**: new flag for maximum privacy — keeps random names also inside the NZB (nobody on indexers knows the content). Unlike `--obfuscate` (reversible), requires manual renaming or via PAR2 after download. Automatically implies `--obfuscate`. Use for private releases or sensitive content.

### Improvements

- **Well-documented reversible obfuscation**: `DOCS.md` and `README.md` now clearly explain the difference between `--obfuscate` (DMCA protection + convenience) and `--strong-obfuscate` (maximum privacy).
- **Updated `CLAUDE.md`**: "Subtle Behaviors" section documents obfuscation implementation in `fix_nzb_subjects` and `obfuscate_and_par` flow.

## 0.22.3 - 2026-05-04

### Fixes (Bugfix)

- **Subject and Extension Obfuscation**: Fixed bug where the original name leaked in the NZB and extensions were misidentified in obfuscated uploads.
  - Replaced use of `-s` (subject) with `-t` (comment) in `nyuu` to preserve default subject formatting with filenames.
  - Refactored `fix_nzb_subjects` function to extract filenames directly from NZB subjects, eliminating order-based mapping errors.
  - Added support for de-obfuscation of `.par2` files and `.volNN+MM.par2` volumes in the NZB.
  - Fixed bug where `.par2` files did not receive the folder prefix in season uploads (`--season`).

## 0.22.2 - 2026-05-04

### Fixes (Bugfix)

- **`--obfuscate` without `--password`**: fixed bug where single file with obfuscation automatically created RAR (generated random password). Now follows 2026 philosophy: `--obfuscate` without `--password` = obfuscation + direct PAR2, no RAR. Only explicit `--password` automatically presumes `--rar`.
- **nyuu progress bar**: restored progress bar display during upload. nyuu's stderr now goes to the terminal normally (it was being redirected for error capture).

## 0.22.1 - 2026-05-04

### Fixes (Bugfix)

- **Single file obfuscation**: fixed bug where parpar was executed with the original file instead of the obfuscated one, causing name inconsistency in the NZB (Part #1 with original name, PAR2s with obfuscated). Now PAR2 metadata is consistent with obfuscated names.

## 0.22.0 - 2026-05-04

### Internal Refactorings (no API break)

- **`_pipeline.py`** (new module, 601 lines): extracts `DependencyChecker`, `PathResolver`, and `PipelineReporter` from `orchestrator.py`; standalone helper functions `normalize_extensionless`, `revert_extensionless`, `do_cleanup_files`, `revert_obfuscation`, `recalculate_resources`.
- **`orchestrator.py`**: 1087 → 599 lines (Single Responsibility — delegates validation, path resolution, and reporting to new classes).
- **`makepar.py::obfuscate_and_par`**: 195 → 76 lines; extracted subfunctions `_obfuscate_folder`, `_obfuscate_rar_vol_set`, `_obfuscate_single_file`, `_rename_par2_files`, `_cleanup_on_par_failure`.
- **33 new tests** in `tests/test_pipeline.py` (252 tests total).

## 0.21.0 - 2026-05-04

### New Features

- **Pre-pipeline ETA**: upload time estimate displayed before the pipeline starts, calculated by NNTP connections (500 KB/s per connection).
- **Early validation**: `orchestrator.validate()` checks disk space (≥2× source size) and read permissions before starting the pipeline.
- **`--insecure` in `--test-connection`**: disables CA certificate verification for servers with self-signed certificates.
- **CA certs by default** in `--test-connection`: uses `ssl.create_default_context()` with full chain verification.

### Improvements

- **`_progress.py`** (new module): extracts `_read_output` and `_process_output` from `makerar.py` and `makepar.py`, eliminating duplication.
- **`nfo._get_video_info()`**: a single `ffprobe` call replaces `_get_video_duration` + `_get_video_metadata` (fewer subprocesses).
- **`resources.get_total_size`**: `@lru_cache(maxsize=64)` avoids re-walking the filesystem during the pipeline.
- **Retry with exponential backoff**: uploads retry with delays 30s→90s→270s + jitter ±10%; nyuu's stderr read in a separate thread to not block retry.
- **nyuu error translation** in `upfolder._parse_nyuu_stderr()`: maps codes 401, 502, timeout, SSL, and ECONNREFUSED to readable messages.
- **Partial PAR2 cleanup** in `obfuscate_and_par`: `finally` block removes `random_base*.par2` and `orig*.par2` in case of failure.
- **ISO Timestamp** in logs: stream handler displays timestamp when `--verbose`; file handler always displays.

### Tests

- `tests/test_phase2.py` (389 lines, 219 green tests): coverage for validation, ETA, retry, error translation, resource cache, PAR2 cleanup, and progress refactoring.
- `tests/test_ui.py` (241 lines): 27 tests for `PhaseBar`, `_TeeStream`, and `format_time` (previously zero coverage).
- `tests/test_resources.py` (184 lines): coverage for `calculate_optimal_resources` and `get_total_size`.
- `tests/test_watch.py`: tests for `_item_size` (file/folder/non-existent) and `_watch_loop` with mock.

### Fixes

- **`scripts/check_header.py`**: removed `python-dotenv` dependency; uses `config.load_env_file` + `ssl.create_default_context` (stdlib-only).
- **`--season` integration**: integration tests temporarily suspended (mock round-trip pending).

### Documentation

- **README.md**: "Post-Upload Hooks" section expanded with complete `UPAPASTA_*` variables table and reference to `examples/`.
- **`examples/post_upload_debug.sh`**: hook example added to the repository.

## 0.16.1 - 2026-04-30

### Fixes

- **Season output path**: fixed error where consolidated NZB and NFO for a season were saved in the script installation directory (e.g., `~/.local/bin`) instead of the current execution directory.

## 0.16.0 - 2026-04-30

### New Features

- **`--season` mode**: individual upload of each episode (like `--each`), but at the end generates consolidated NZB and NFO for the entire season without performing new uploads. Ideal for organizing series where both individual episodes and the complete pack are desired.

## 0.14.2 - 2026-04-29

### Improvements

- **Obfuscation via Hardlinks**: UpaPasta now uses hardlinks for in-place obfuscation (`--skip-rar` flow). This prevents the torrent client from losing access to the original files during upload, allowing seeding to continue without interruption.
- **Obfuscation Fallback**: if the filesystem does not support hardlinks (e.g., cross-device), the system automatically reverts to physical renaming (with a user warning).

## 0.14.1 - 2026-04-29

### Fixes

- **In-place obfuscation reversion fix**: in the `--skip-rar --obfuscate` flow, the original folder was permanently renamed to the obfuscated name. Added automatic reversion mechanism that restores the original name after successful upload, on upload failure, or when `--skip-upload` is used.

## 0.14.0 - 2026-04-29

### New Features

- **Empty folders warning in `--skip-rar`**: the orchestrator detects empty directories at runtime and prints a warning explaining that NNTP/PAR2 do not preserve directories without files, suggesting removing `--skip-rar` (RAR preserves) or using a sentinel file.

### Documentation

- New section in `DOCS.md` documenting empty folder limitation and RAR workaround.
- Fixed obsolete note about `--skip-rar` in folders with subfolders (now recommended flow with parpar `-f common`).

### Tests

- New suite `tests/test_nested_paths.py` (8 tests) covering: extreme depth (5+ levels), unicode/spaces/special characters, empty folders, hidden files, symlinks, obfuscate combined with nested upload, and round-trip of `--rename-extensionless` in deep subdirectories.

## 0.12.1 - 2026-04-22

### Improvements

- **NZB path resolution**: Improved output path intelligence. UpaPasta now accepts just a folder in `NZB_OUT` and automatically appends the `{filename}.nzb` template, simplifying configuration for integration with other tools.

## 0.12.0 - 2026-04-22

### New Features

- **Upload catalog (`catalog.py`)**: append-only JSONL file in `~/.config/upapasta/history.jsonl` created automatically. Records for each successful upload: timestamp, original name, obfuscated name, RAR password, size, detected category, effective Usenet group, NNTP server, PAR2 redundancy, duration, number of RAR volumes, and NZB path. NZBs are archived in `~/.config/upapasta/nzb/` via hardlink — recoverable even if the physical file is moved or deleted.
- **Automatic category detection**: analyzes the filename to infer `Anime` (`[SubGroup] Title - 01`), `TV` (`S01E01`, `1x01`, `Season 2`), `Movie` (isolated year 19xx/20xx in title), or `Generic`. No manual flags needed.
- **Post-upload hook (`POST_UPLOAD_SCRIPT`)**: configure an external script in `.env`. UpaPasta executes it after each successful upload passing information via `UPAPASTA_*` environment variables (NZB, NFO, password, original/obfuscated name, size, group). 60s timeout; hook failure does not affect the main exit code.

### Internal Improvements

- `UpaPastaOrchestrator.from_args()`: classmethod that centralizes `args → UpaPastaOrchestrator` mapping. Eliminates duplication between `main.py` and `watch.py` — new parameters need to be added in only one place.

## 0.11.0 - 2026-04-22

### New Features

- **Usenet Group Pool**: Support for newsgroup lists (pool) with random selection per upload. This increases obfuscation and redundancy, avoiding all posts being concentrated in a single group. The configuration wizard now suggests a default pool of 10 popular groups.
- **NFO Improvement**: The upload module (`upfolder.py`) is now capable of independently generating technically descriptive NFO files for single-file uploads.

### Refactoring

- **Modular Architecture**: Major breakup of `main.py` (previously >1400 lines) into specialized modules:
  - `cli.py`: Argument and dependency management.
  - `orchestrator.py`: Central workflow logic.
  - `ui.py`: User interface, progress bars, and logging.
  - `watch.py`: Daemon/monitoring mode logic.
  - `main.py`: Simplified entry point.

## 0.10.5 - 2026-04-22

### Improvements

- **UX in `--watch`**: Added a structured header when starting monitoring mode.
- **Interactive Spinner**: Replaced repetitive idle messages with an animated spinner (`|`, `/`, `-`, `\`) on a single line, keeping the terminal clean and indicating activity without polluting log files.
- **Processing Feedback**: Clearer messages when detecting new items, verifying size stability, and completing the processing of each task.

## 0.10.4 - 2026-04-22

### New Features

- **`--watch`**: daemon mode that monitors a directory and automatically processes each new item (file or folder) that appears. Uses polling via stdlib (no external dependencies). Each detected item goes through the full pipeline (RAR → PAR2 → upload → NZB). Compatible with `--obfuscate`, `--password`, `--dry-run`. Ctrl+C exits gracefully.
- **`--watch-interval N`**: scan interval in seconds (default: 30).
- **`--watch-stable N`**: seconds that item size must remain stable before processing — avoids processing files still being copied (default: 60).

## 0.10.3 - 2026-04-22

### Fixes

- Fix: RAR phase PhaseBar remained `⬜` (pending) on a single file with `--obfuscate`/`--password`, even with RAR being created. The bar activation condition now correctly considers cases where RAR is automatically generated.

## 0.10.2 - 2026-04-22

### Fixes

- Fix: `--obfuscate` reverts to generating random password automatically when `--password` is not provided. Obfuscating name without protecting content is half-protection — the password is injected into the NZB and automatically extracted by SABnzbd/NZBGet.

## 0.10.1 - 2026-04-22

### Fixes

- Fix: PhaseBar showed RAR as `⏭ skipped` on single file with `--obfuscate`/`--password`, even when RAR was automatically created.
- Fix: Final summary showed "File: ...mkv" instead of "RAR: obfuscated_name.rar" because it checked `os.path.exists` after cleanup had already removed the file.

## 0.10.0 - 2026-04-22

### New Features

- **`--each`**: processes each file in a folder individually — each file becomes a separate release with its own NZB. Ideal for series seasons.
- **Automatic RAR for single file**: when using `--obfuscate` or `--password` with a single file, UpaPasta now automatically creates the RAR (real obfuscation requires container; password requires container).
- **`make_rar` accepts single file**: `makerar.py` supports single file in addition to folders, without volume splitting.
- **No arguments**: `upapasta` without arguments displays a friendly usage message instead of the argparse error.

### Behavioral Changes

- **`--obfuscate` and `--password` are independent**: removed automatic password generation when using `--obfuscate`. Each flag has an exclusive effect — obfuscate renames files, password protects content.
- **Subfolders warning with `--skip-rar`**: when using `--skip-rar` in a folder with subfolders, displays a warning about the risk of broken structure after download.
- **`--skip-rar + --password` is fatal error**: incompatible combination exits with a clear message.
- **`--skip-rar + --obfuscate`**: displays partial obfuscation warning and waits 3s before continuing.

### CLI

- `--help` rewritten with argument groups (essential / adjustment / advanced), examples, and default behavior section in epilog.
- Argument groups in help: essential options, adjustment options, advanced options.

### Docs

- README rewritten with focus on simplicity: default behavior table, examples by use case, auto-RAR rules, explanation of store mode `-m0`.
- CLAUDE.md updated: `_process.py` documented, MANDATORY rules for `managed_popen` and `UpaPastaSession`, Logging section.
- TODO.md revised: implemented items removed, new challenges added, v1.0.0 goal defined.

## 0.9.0 - 2026-04-21

### Security / Critical Fixes

- **Fix [CRITICAL]**: `upfolder.py` — eliminated data copying to `/tmp` with `shutil.copytree` before folder upload. nyuu is now invoked with `cwd=input_path` and relative paths built via `os.path.relpath`, zeroing extra I/O (fatal for tens of GB folders).
- **Fix [HIGH]**: Graceful shutdown in all subprocesses (`rar`, `parpar`, `par2`, `nyuu`) — new module `_process.py` with `managed_popen` context manager that ensures `SIGTERM → SIGKILL` on child process on any exit, including `KeyboardInterrupt` (Ctrl+C). Eliminates zombie processes.
- **Fix [HIGH]**: Data protection in obfuscation — `obfuscate_and_par` rewritten with shielded `try/finally`. New `_revert_obfuscation` helper with explicit progress messages and manual fallback instructions. Reversion of user renames is now guaranteed even on Ctrl+C during PAR2 generation.
- **Fix [MEDIUM]**: Real compatibility with Python 3.8 — `from __future__ import annotations` added to all modules; `X | Y` syntax in function annotations replaced by `Optional[X]` / `Tuple[X, Y]` from `typing`. `X | Y` syntax is only valid at runtime in Python 3.10+.

### Internal New Features

- `upapasta/_process.py`: new module with `managed_popen()` and `_terminate_process()` shared by makerar, makepar, and upfolder.
- `makepar._revert_obfuscation()`: centralized obfuscation reversion function with detailed feedback and manual recovery instructions.

## 0.8.2 - 2026-04-21

### Improvements

- **Refactored Initial Setup**: initial questionnaire redesigned — displays header, two sections (Server / Upload), validates port and mandatory fields, accepts Enter to confirm defaults, and displays summary before saving.
- **Auto-generated `.env`**: `.env` automatically generated on first run contains all configurable variables with explanatory comments (same as `.env.example`).

### Documentation

- **`.env.example` updated**: more descriptive comments, default group changed to `alt.binaries.boneless`, `DUMP_FAILED_POSTS` empty by default.
- **README**: Configuration section rewritten with questionnaire example and main variables table.

## 0.8.1 - 2026-04-19

- Fix: NZB name preserves full tags (e.g., `.DUAL-EcK`) — `splitext()` was applied twice on the basename already without extension in `obfuscated_map`.

## 0.8.0 - 2026-04-19

- Feature: real obfuscation — RAR/PAR2 are physically renamed on disk with random 12-character names (`--obfuscate`); NZB saved with original name preserved.
- Feature: volume set support — all `file.part*.rar` files are renamed atomically to `random.part*.rar`; PAR2 generated after renaming.
- Feature: automatic RAR password — with `--obfuscate`, a secure 16-character password generated via `secrets` and applied with `-hp` (encrypts both content AND internal names).
- Feature: `--password PASSWORD` for customizable RAR password (works with or without `--obfuscate`).
- Feature: password injected into `.nzb` as `<meta type="password">` for automatic extraction by SABnzbd, NZBGet, and other clients.
- Feature: password and obfuscated name displayed in header and final summary of the workflow.
- Fix: automatic rename reversion in case of PAR2 generation failure.

## 0.7.0 - 2026-04-18

- Feature: structured logging with `setup_logging()` and `--verbose` flag for DEBUG level.
- Feature: `--par-slice-size` for manual override of PAR2 slice size.
- Feature: `--upload-timeout` passes connection timeout to nyuu (`--timeout N`).
- Feature: `--upload-retries` implements automatic retry on upload failure (N extra attempts).
- Feature: post-upload verification of generated NZB (existence, size > 0, `<file>` element via XML).
- Fix: differentiated error handling — `FileNotFoundError`, `PermissionError`, `OSError` instead of generic `except Exception` in makerar, makepar, and upfolder.
- Docs: `target_slices=4` heuristic in `makepar.py` documented with examples and guidance for large files.
- Tests: +17 tests covering cleanup, multivolume RAR, keep-files, RAR/PAR2 error paths, NZB verification, and upload retry.

## 0.6.8 - 2026-04-18

- Fix: RAR volume thresholds adjusted — files up to 10 GB generate single RAR; above that volumes of at least 1 GB (previously: split from 200 MB with 50 MB parts).

## 0.6.7 - 2026-04-18

- Fix: cleanup now deletes all RAR volumes and PAR2 files after successful upload — previously only the first 2 files were removed due to incorrect .partXX suffix stripping (only 2-digit parts were handled, but rar generates 3-digit parts like .part001).

## 0.6.6 - 2026-04-18

- Fix: `make_rar()` now returns generated RAR path to fix `part001.rar` detection for large archives (>99 parts).
- Fix: Added force mode to remove existing partial RAR volumes before creating new ones.
- Fix: Improved RAR volume detection to handle both `part01.rar` and `part001.rar` naming schemes.

## 0.6.5 - 2026-04-18

- Feature: series folders (`SXX / SXXEXX` pattern) generate NFO using mediainfo of the first episode; generic folders keep the tree+stats layout.

## 0.6.4 - 2026-04-18

- Feature: new NFO banner — clean ASCII art "UPAPASTA" with border, fits 80 columns, pure ASCII (compatible with all NFO viewers).

## 0.6.3 - 2026-04-18

- Fix: NFO and NZB filenames now match the source folder name exactly (no `_content` suffix).
- Fix: NZB basename for RAR volume sets strips the `.partXX` suffix correctly.

## 0.6.2 - 2026-04-18

- Fix: PAR2 generation now covers all RAR volumes in a set (not just `part01.rar`).
- Fix: upload now sends all RAR volume parts + their PAR2 files.
- Fix: PAR2 filename uses the set base name (without `.part01` suffix).

## 0.6.1 - 2026-04-18

- Fix: detect RAR volumes (`part01.rar…partNN.rar`) after creation — single-file check was failing for multi-part sets.
- Fix: cleanup now removes all RAR volume parts, not just the first file.
- Fix: summary stats now sum all RAR volumes for correct total size display.

## 0.6.0 - 2026-04-18

- Feature: Automatic RAR volume splitting for Usenet best practices — folders < 200 MB generate a single RAR; larger folders are split into volumes (min 50 MB each, max 100 parts).
- Docs: Rewrite README with prerequisites table, all CLI options documented, and RAR volume logic explained.

## 0.5.0 - 2025-12-18

- Feature: Add configurable ASCII art banner for folder `.nfo` files via `NFO_BANNER` env variable.
- Feature: Enhanced folder `.nfo` generation with detailed statistics, tree structure, and video metadata.
- Feature: Extract video duration, resolution, codec, and bitrate using `ffprobe` for rich `.nfo` content.
- Feature: Default UpaPasta ASCII banner when custom banner not configured.
- Fix: Sanitize mediainfo "Complete name" field to show only filename for video files.
- Docs: Update README with NFO configuration options and ffmpeg dependency information.

## 0.4.0 - 2025-12-17

- Feature: Implement obfuscated upload feature with subject obfuscation.
- Feature: Add NZB conflict handling (`--nzb-conflict` option).
- Fix: Move `.nfo` generation to workflow start for better organization.

## 0.3.4 - 2025-12-14

- Fix: Early NZB conflict detection before processing to avoid wasted work.
- Fix: Automatic cleanup of temporary PAR2 files when errors occur.
- Performance: Skip PAR2 generation when NZB conflict is detected with 'fail' mode.

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
