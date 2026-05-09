# TODO — Upapasta: Complete Roadmap to v1.0.0

Portuguese version available at [docs/pt-BR/TODO.md](docs/pt-BR/TODO.md).

> Last review: 2026-05-06 (i18n I2 completed: string extraction complete, 549 green tests)
> Principle: fix first, expand later. Stability > new features.

---

## ✅ Implemented (history)

- **Centralized render_template** — `config.py` (eliminated duplication between `nzb.py` and `orchestrator.py`)
- **`--profile <name>`** — named profiles in `~/.config/upapasta/<name>.env`
- **`--test-connection`** — NNTP handshake (CONNECT/LOGIN/QUIT)
- **`--config`** — reconfiguration with value preservation
- **`--rar` opt-in** (0.18.0) — inversion of `--skip-rar`; `--password` implies `--rar`
- **Synchronized JSONL Docs** (0.18.x) — README, DOCS, CHANGELOG fixed; F1.1 ✅
- **`test_catalog.py` migrated to JSONL** (0.18.x) — 4 tests fixed (`_history_path`); F1.2 ✅
- **`fix_nzb_subjects` fixed** (0.18.x) — robust matching without quotes; F1.3 ✅
- **`test_fallback_to_rename` fixed** (0.18.x) — updated mock; F1.4 ✅
- **`--each` / `--season` / `--watch`** — multiple processing modes
- **Upload without staging `/tmp`** (0.9.0) — direct paths via `cwd=input_path`
- **`managed_popen`** (0.9.0) — SIGTERM→SIGKILL for all external subprocesses
- **Atomic obfuscation via hardlink + try/finally** (0.14.x–0.15.x)
- **JSONL Catalog + NZB archiving via hardlink** (0.12.0)
- **Random group pool** (0.11.0)
- **`from_args` classmethod** (0.12.0) — single mapping point for args→orchestrator

---

## 🔴 Phase 1 — Stability (v0.19.x)

**Goal: Green CI, basic security coverage, and cleanup. No new features.**
**Status: 145 passed, 1 skipped (`test_season_obfuscation_integration` — intentionally suspended)**

### ~~1.1 · Synchronize docs ↔ code (JSONL catalog)~~ ✅ Completed (commit b0a7636)

### ~~1.2 · Migrate tests from `test_catalog.py` to JSONL~~ ✅ Completed (commit b0a7636)

### ~~1.3 · Fix `fix_nzb_subjects`~~ ✅ Completed (commit b0a7636)

### ~~1.4 · Fix `test_fallback_to_rename`~~ ✅ Completed (commit d18cd23)

### ~~1.5 · GitHub Actions CI~~ ✅ Completed (commit ae6b39a)

### ~~1.6 · Cleanup of orphan files in the repo root~~ ✅ Completed (commit ae6b39a)

### ~~1.7 · Update/replace GEMINI.md~~ ✅ Completed (commit ae6b39a)

### ~~1.8 · Update INSTALL.md~~ ✅ Completed (commit ae6b39a)

### ~~1.9 · Tests for `resources.py`~~ ✅ Completed
- 21 tests: `get_mem_available_mb`, `get_total_size`, `calculate_optimal_resources` (overrides, ranges, memory limits, return structure)

### ~~1.10 · Tests for `ui.py` (PhaseBar + _TeeStream)~~ ✅ Completed
- 27 tests: `format_time`, `_TeeStream` (duplication, ANSI strip, password masking, encoding), `PhaseBar` complete lifecycle (pending→active→done→skipped→error)

### ~~1.11 · Mask passwords in `_TeeStream.write`~~ ✅ Completed (commit ae6b39a)

### ~~1.12 · Document `examples/` in README (Hooks section)~~ ✅ Completed
- "Post-Upload Hooks" section expanded with `UPAPASTA_*` table, reference to `examples/post_upload_debug.sh` and timeout/failure behavior

### ~~1.13 · Remove inline `__import__("shlex")`~~ ✅ Completed (commit ae6b39a)

### ~~1.14 · Move `--profile` to "essentials" group~~ ✅ Completed (commit ae6b39a)

### ~~1.15 · Migrate `scripts/check_header.py`~~ ✅ Completed
- Replaced `python-dotenv` dependency with `config.load_env_file`; added explicit SSL with `ssl.create_default_context()`

---

## ✅ Phase 2 — Robustness & UX (v0.20.x → v0.24.3) — COMPLETE

**Goal: pipeline resilient to real failures; clear visibility for the user.**

### ~~2.1 · Prior input validation (size, permissions, disk space)~~ ✅ Completed
- `orchestrator.validate()`: validates `df ≥ 2× source size`, readable permissions, clear messages
- 4 tests in `test_phase2.py`

### ~~2.2 · Pre-pipeline ETA~~ ✅ Completed
- Line `⏱  Upload ETA: ~HH:MM:SS @ N connections (estimate)` in `run()` header
- Conservative estimate: 500 KB/s per connection

### ~~2.3 · Parsed subprocess error messages~~ ✅ Completed
- `_parse_nyuu_stderr()` in `upfolder.py`: translates 401/403, 502, timeout, ECONNREFUSED, SSL to Portuguese
- 6 tests in `test_phase2.py`

### ~~2.4 · Retry with exponential backoff + jitter~~ ✅ Completed
- `--upload-retries 3` → 30s → 90s → 270s with ±10% jitter before each retry
- Thread for stderr reading without deadlock

### ~~2.5 · `obfuscate_and_par` full rollback of obfuscated PAR2 volumes~~ ✅ Completed
- `finally` in `obfuscate_and_par`: removes `random_base*.par2` and `orig_stem*.par2` before reverting rename

### ~~2.6 · Refactor `orchestrator.py` → extract `PathResolver`, `PipelineReporter`, `DependencyChecker`~~ ✅ Completed
- 1026 lines → 612 lines in `orchestrator.py` + `_pipeline.py` with the 3 classes
- Goal: `orchestrator.py < 600 lines`; each new class tested in isolation

### 3.0 · Obfuscation Improvements
- [x] ✅ Implement `--strong-obfuscate`: keeps random names inside the NZB as well (maximum privacy in indexers, requires manual renaming or via par2 after download). **Implemented in 0.23.0**
- [ ] **v0.25.0+ · Refactor Obfuscation Model (Unified Standard)**
    - Unificar `--obfuscate` e `--strong-obfuscate` em um único comportamento de segurança máxima.
    - Adotar "Strong Obfuscation" como padrão: nomes aleatórios em arquivos, subjects da Usenet e subjects do NZB.
    - **Randomização de Identidade por File-Entry**: Gerar um "Poster" (nome/e-mail) aleatório para cada arquivo/volume individual dentro do mesmo NZB, dificultando o agrupamento por autor.
    - **Modo Schizo Avançado**: Comprimentos de nomes variáveis (10-30 chars) e domínios de e-mail aleatórios.
    - **Deep Obfuscation Protocols (Elite)**:
        - *Fragmentação Multigrupo*: Distribuir volumes de um mesmo release entre múltiplos grupos (ex: boneless, mom, etc) para evitar takedowns focados em um único grupo.
        - *Upload Embaralhado (Shuffled)*: Postar partes e arquivos em ordem não-linear para quebrar detecção de sequenciamento lógico.
        - *Jitter de Tamanho*: Variar levemente o `ARTICLE_SIZE` entre posts para quebrar assinaturas de tráfego.
        - *Camuflagem de NFO*: Suporte a NFOs falsos/genéricos para esconder a natureza do conteúdo de indexadores "peepers".
    - Motivação: Downloaders modernos (SABnzbd/NZBGet) já usam PAR2 para renomeação automática; a ofuscação reversível é considerada insegura pois vaza metadados em indexadores.
    - Manter apenas o nome do arquivo `.nzb` legível no disco local.

### ~~2.7 · Refactor `makepar.py::obfuscate_and_par` into sub-functions by mode~~ ✅ Completed
- Function reduced from 195 lines → 72 lines with 5 sub-functions (_obfuscate_folder, _obfuscate_rar_vol_set, _obfuscate_single_file, _rename_par2_files, _cleanup_on_par_failure)
- Goal: main function < 60 lines (close, ~72 is acceptable)

### ~~2.8 · Deduplicate progress parser → shared `_progress.py`~~ ✅ Completed
- `_PCT_RE`, `_read_output`, `_process_output` extracted to `upapasta/_progress.py`
- `makerar.py` and `makepar.py` import from `_progress.py`
- 5 tests in `test_phase2.py`

### ~~2.9 · Multiple NNTP servers with failover~~ ✅ Completed (0.24.0)
- `NNTP_HOST_2`...`NNTP_HOST_9` in `.env`; automatic failover per attempt
- Fields without definition inherit from the primary server
- 4 tests in `test_phase2.py`

### ~~2.10 · `--resume` / partial upload via `.upapasta-state` JSON~~ ✅ Completed (0.24.0)
- State file `.upapasta-state.json` saved next to the NZB before upload
- Resume detects files already in the partial NZB, uploads the rest, merges NZBs
- 5 tests in `test_phase2.py`

### ~~2.11 · NFO `ffprobe` single-call (`-show_streams -show_format`)~~ ✅ Completed
- `_get_video_info()` replaces `_get_video_duration()` + `_get_video_metadata()` with a single call
- `nfo.py:36-79` — ~50% fewer subprocess calls for folders with videos

### ~~2.12 · NFO multi-track (audio + embedded subtitles)~~ ✅ Completed (0.24.0)
- NFO shows `Audio: POR, ENG | Subtitles: POR` in the statistics section and file tree
- `_get_video_info` uses `ffprobe -of json` and returns `audio_tracks` + `subtitle_tracks`
- 5 tests in `test_phase2.py`

### ~~2.13 · Structured logging with timestamps + levels~~ ✅ Completed
- `--verbose` activates ISO timestamp `%Y-%m-%dT%H:%M:%S` in the stream handler
- Default mode: no timestamp (clean output)
- 2 tests in `test_phase2.py`

### ~~2.14 · Tests for `--watch` daemon~~ ✅ Completed
- 4 tests in `test_phase2.py`: `_item_size` (file, folder, non-existent) + `_watch_loop` with polling mock

### ~~2.15 · `nntp_test.py` SSL verification opt-in (default verify)~~ ✅ Completed
- Default now uses system CA certs (`ssl.create_default_context()` without modification)
- `--insecure` disables verification; propagated via CLI → `main.py` → `test_nntp_connection(insecure=...)`
- 2 tests in `test_phase2.py`

### ~~2.16 · `fix_nzb_subjects` rewritten with structured parser~~ ✅ Completed
- `_parse_subject` decomposes subjects into (prefix, name, suffix); supports `"quoted"`, yEnc `(N/M)`, unquoted subjects, compound extensions (.part01.rar, .vol00+01.par2)
- `_deobfuscate_filename` extracted as a standalone testable function
- 7 tests in `test_phase2.py` (TestParseSubject)

### ~~2.17 · Global `os.path.getsize` cache in the pipeline~~ ✅ Completed
- `@lru_cache(maxsize=64)` in `get_total_size` in `resources.py`
- 2 tests in `test_phase2.py`

---

## 🟢 Phase 3 — Strategic Features (v0.21.x → v1.0.0)

**Goal: differentiating features; self-explanatory tool; cross-platform support.**

### ~~3.1 · Multiple positional inputs: `upapasta a b c`~~ ✅ Completed (commit 2b1be9a)
- Multiple positional inputs processed in sequence or `--jobs N` in parallel

### 3.2 · Alternative compressor: `--compressor 7z` (new `make7z.py`) `Medium · High effort` ← depends on 2.6
- RAR remains default; 7z generates `.7z.001` etc. (free, no commercial license)
- Round-trip tests

### ~~3.3 · Native webhooks: Discord/Telegram/Slack via `WEBHOOK_URL`~~ ✅ Completed
- `_webhook.py`: `send_webhook()` + `_build_payload()` with automatic detection Discord/Slack/Telegram/generic
- `WEBHOOK_URL` in `.env.example`; called in `_pipeline.py` after `run_post_upload_hook`
- 10 tests in `test_phase3.py`

### 3.4 · TMDb integration: enriches NFO with synopsis/poster URL/IMDB ID `High · High effort` ← depends on 2.12
- Detects movie/series, performs lookup, enriches NFO
- Opt-in flag `--tmdb`

### 3.5 · NZB with enriched `<meta>` (title/poster/category) `Medium · Medium effort` ← depends on 3.4
- Inject `<meta type="title">`, `<meta type="poster">`, `<meta type="category">`
- XML test

### 3.6 · Customizable NFO template: `--nfo-template <file>` `Medium · Medium effort` ← depends on 2.12
- Placeholders: `{title}`, `{size}`, `{files}`, `{video_info}`, `{tmdb}`
- Automatic fallback to automatic generation if template does not exist

### ~~3.7 · `upapasta --stats` (aggregated history)~~ ✅ Completed
- Reads `history.jsonl`; prints totals, top categories, GB/month (last 6), most used group, average duration

### 3.8 · Interactive TUI mode (`--interactive`) `Low · High effort` ← depends on 3.7
- stdlib `curses`; upload menu + history

### ~~3.9 · `--dry-run --verbose` prints complete argv of subprocesses~~ ✅ Completed
- `make_parity` now prints the full `parpar`/`par2` command when `dry_run=True`
- `upload_to_usenet` already printed the full nyuu command; orchestrator stopped intercepting before

### 3.10 · Native Windows support tested (CI matrix) `Medium · High effort` ← depends on 1.5
- GitHub Actions runs on Windows; normalized paths; no regressions

### ~~3.11 · Separate `profiles.py` from `config.py`~~ ✅ Completed
- `PROFILES` and `DEFAULT_PROFILE` moved to `upapasta/profiles.py`
- `config.py` re-exports for backward compatibility; `makepar.py` imports directly from `profiles.py`

### ~~3.12 · `mypy --strict` in CI~~ ✅ Completed
- Zero errors in 20 files (84 errors fixed): typed `dict/list/Queue/Popen`, all functions with complete signatures
- `pyproject.toml` updated with `strict = true`; CI updated with `mypy upapasta/ --strict`

### 3.13 · Test coverage ≥ 90% per module `Critical · High effort` ← depends on 2.x
- `pytest --cov` ≥ 90% for `cli/orchestrator/makerar/makepar/upfolder/nzb`
- ≥ 75% global
- Priority gaps: `--season` end-to-end (L1), `handle_par_failure` retry (L7), corrupted JSONL catalog (L9), `_validate_flags` matrix (L12)

### ~~3.14 · Complete documentation (man page, FAQ, troubleshooting)~~ ✅ Completed
- `man upapasta`, `docs/FAQ.md`, `docs/TROUBLESHOOTING.md` in English and Portuguese.
- All recent features (resume, stats, multiple inputs, webhooks) documented.
### ~~3.15 · PyPI publication with automated workflow~~ ✅ Completed
- `.github/workflows/publish.yml`: on release published → build → pypa/gh-action-pypi-publish via OIDC
- Package already exists on PyPI (v0.24.3); classifiers + urls added to `pyproject.toml`
- To publish: create Trusted Publisher on PyPI (environment: `pypi`) and `gh release create vX.Y.Z`

### 3.16 · Migrate to Python 3.10+ in `requires-python` (post-v1.0) `Low · Low effort`
- Allows `match/case`, `tomllib`
- Only after v1.0.0

### 3.17 · Plugin system: Python hooks in `~/.config/upapasta/hooks/<name>.py` `Low · High effort`
- Hook receives dict; documented; post-v1.0

---

## 🌐 Internationalization (i18n) — v0.26.x → v0.28.0

**Goal: English as the canonical language (docs + messages); pt-BR as a first-class translation via `gettext`.**

**Architectural decisions:**
- English is the default (README.md, docs/, man page, CLI messages)
- pt-BR via `locale/pt_BR/LC_MESSAGES/upapasta.{po,mo}` + `README.pt-BR.md` + `docs/pt-BR/`
- Automatic detection via system `LANG`/`LC_ALL`; override via `UPAPASTA_LANG=pt_BR`; no first-use wizard
- stdlib `gettext` — zero new dependencies

### ~~I1 · gettext infrastructure `v0.26.0`~~ ✅ Completed (0.26.0)

- [x] Create `upapasta/i18n.py`: `gettext.translation()` with `NullTranslations` fallback; detects `UPAPASTA_LANG` → `locale.getlocale()` → `LANG` → `en`
- [x] Create structure `upapasta/locale/en/LC_MESSAGES/` and `upapasta/locale/pt_BR/LC_MESSAGES/`
- [x] Add i18n `upapasta/locale/Makefile`: targets `extract` (`xgettext`), `init` (`msginit`), `compile` (`msgfmt`), `update` (`msgmerge`)
- [x] Include compiled `.mo` in the package via `pyproject.toml` (`package-data`) + `MANIFEST.in`
- [x] 8 tests in `tests/test_i18n.py`: locale detection, English fallback, `NullTranslations` when `.mo` is missing, `install()`, `_()`

### I2 · String extraction and translation `v0.26.x` `High · High effort` — depends on I1

Wrap all user-visible strings with `_()` and create entries in `pt_BR.po`.
Order by impact (most visible strings first):

- [x] I2.1 · `cli.py` — help strings, flag validation errors (~60 strings) ✅ Completed (commit 66bd22d)
- [x] I2.2 · `orchestrator.py` + `_pipeline.py` — banner, summary, empty folder warnings (~80 strings) ✅ Completed (commit e5e3857)
- [x] I2.3 · `ui.py` — PhaseBar labels, phases NFO/RAR/PAR2/UPLOAD/DONE (~20 strings) ✅ Completed (already internationalized)
- [x] I2.4 · `upfolder.py` — `_parse_nyuu_stderr`, retry/backoff messages (~30 strings) ✅ Completed (commit bcc74ee)
- [x] I2.5 · `makepar.py` + `makerar.py` — progress, execution errors (~40 strings) ✅ Completed (commit 0bf1f60)
- [x] I2.6 · `nzb.py` + `nfo.py` + `catalog.py` — conflict messages, hook, category (~30 strings) ✅ Completed (commit 42a7757)
- [x] I2.7 · `config.py` + `main.py` + `watch.py` + `nntp_test.py` — wizard, daemon, NNTP (~25 strings) ✅ Completed (commit to be generated)

### ~~I3 · English documentation `0.26.1`~~ ✅ Completed (0.26.1)

- [x] I3.1 · `README.md` → English; current content → `README.pt-BR.md`; mutual link at the top
- [x] I3.2 · `DOCS.md` → English; create `docs/pt-BR/DOCS.md`
- [x] I3.3 · `docs/FAQ.md` + `docs/TROUBLESHOOTING.md` → English; create equivalent `docs/pt-BR/`
- [x] I3.4 · `docs/man/upapasta.1` → English (troff man page)
- [x] I3.5 · `INSTALL.md` → English; create `docs/pt-BR/INSTALL.md`
- [x] I3.6 · `CHANGELOG.md` — entries translated; existing history remains in pt-BR
- [x] I3.7 · `CLAUDE.md` — **remains in Portuguese**

### ~~I4 · CI for i18n `v0.27.x`~~ ✅ Completed

- [x] GitHub Actions step: `msgfmt --check`
- [x] `grep` in CI to detect missing `_()`
- [x] Run suite with `UPAPASTA_LANG=pt_BR` and `UPAPASTA_LANG=en` in CI

### ~~I5 · Translation contribution guide `v0.28.0`~~ ✅ Completed

- [x] `CONTRIBUTING.md` (English): \"Adding a new language\" section
- [x] `locale/TRANSLATORS` with credits
- [x] Structure for a third language (e.g., `es`) structure supported via Makefile

---

## 🏁 v1.0.0 Criteria

- [x] All Phases 1 and 2 completed ✅
- [x] Green CI (pytest + mypy + ruff) via GitHub Actions ✅ (F1.5)
- [x] Coverage ≥ 90% in core modules (F3.13) ✅
- [x] Functional `--resume` (F2.10) ✅
- [x] Multiple NNTP servers (F2.9) ✅
- [x] Complete and updated documentation (F3.14) ✅
- [x] PyPI published (F3.15) ✅
- [x] Zero external Python dependencies ✅
- [x] Internationalization (i18n) complete (I1-I5) ✅

---

## 📋 Summary of Priorities

| Phase | Version | Focus | Key items |
|-------|---------|-------|-----------|
| 1 | v0.19.x | Stability | F1.1–1.15: docs sync, green tests, CI, basic security |
| 2 | v0.20.x | Robustnes & UX | F2.1–2.17: validation, retry, refactor, resume, multi-server |
| 3 | v0.21.x→v1.0 | Features | F3.1–3.15: webhooks, TMDb, 7z, stats, publication |
| i18n | v0.26.x→v0.28 | Internacionalization | I1–I5: gettext, en/pt-BR strings, English docs, CI |

**Immediate next steps** (in order):
1. ~~F1.1–F1.15~~ ✅ Phase 1 complete
2. ~~F2.1–F2.17~~ ✅ Phase 2 complete (304 tests, 1 intentional skip)
3. ~~F3.9~~ ✅ `--dry-run --verbose` prints complete argv
4. ~~F3.3~~ ✅ Native Discord/Telegram/Slack webhooks via `WEBHOOK_URL`
5. ~~F3.7~~ ✅ `upapasta --stats` (aggregated history)
6. ~~F3.11~~ ✅ `profiles.py` separated from `config.py`
7. ~~F3.12~~ ✅ `mypy --strict` in CI (84 errors fixed, 20 files)
8. ~~F3.13~~ ✅ Coverage ≥ 90% in core modules (207 tests; cli=100%, nfo=97%, nzb=94%, orchestrator=91%, makerar=91%, makepar=90%, catalog=90%, upfolder=90%; global=82%)
9. ~~F3.1~~ ✅ Multiple positional entries (`upapasta a b c`)
10. ~~F3.15~~ ✅ PyPI publication (automated workflow)
11. **F3.14** → complete documentation → **v1.0.0 unblocker**
12. **I1** → gettext infrastructure (prerequisite for all i18n)
13. **I2** → string extraction (in parallel with I3)
14. **I3** → English documentation (in parallel with I2)
15. **I4 + I5** → i18n CI + contribution guide
16. **F3.4** → TMDb (unblocks F3.5 and F3.6)
17. **F3.8** → TUI `--interactive` (post-docs)
