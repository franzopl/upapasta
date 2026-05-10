# TODO — Upapasta: Complete Roadmap to v1.0.0

Portuguese version available at [docs/pt-BR/TODO.md](docs/pt-BR/TODO.md).

> Last review: 2026-05-09 (Windows & 7z support done, nearing v1.0.0)
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

## ✅ Phase 1 — Stability — COMPLETE

**Goal: Green CI, basic security coverage, and cleanup. No new features.**

---

## ✅ Phase 2 — Robustness & UX — COMPLETE

**Goal: pipeline resilient to real failures; clear visibility for the user.**

---

## 🟢 Phase 3 — Strategic Features (v0.21.x → v1.0.0)

**Meta: features differentiating; self-explanatory tool; cross-platform support.**

### ~~3.1 · Multiple positional inputs: `upapasta a b c`~~ ✅ Completed (commit 2b1be9a)

### ~~3.2 · Alternative compressor: `--7z` and `--compress` (v0.30.0)~~ ✅ Completed
- Support for 7z volumes (.7z.001), passwords (-mhe=on), and live progress UI
- Simplified CLI: explicit `--rar`, `--7z`, and generic `--compress` flags

### ~~3.3 · Native webhooks: Discord/Telegram/Slack via `WEBHOOK_URL`~~ ✅ Completed

### ~~3.4 · TMDb integration: enriched NFO (v0.31.0)~~ ✅ Completed
- Auto lookup for movie/tv metadata; strict matching heuristics; suggestions log
- New utility: `upapasta --tmdb-search "term"`

### ~~3.5 · Enriched NZB <meta> (v0.31.0)~~ ✅ Completed
- Inject title, poster, imdbid, genres, tagline into NZB <head> (Newznab standard)

### ~~3.6 · Customizable NFO template: `--nfo-template <file>` (v0.31.x)~~ ✅ Completed
- Support for custom text files with placeholders: `{{title}}`, `{{synopsis}}`, `{{size}}`, `{{files}}`, `{{mediainfo}}`

### ~~3.17 · Plugin system: Python hooks (v0.31.x)~~ ✅ Completed
- Native Python support for post-upload logic in `~/.config/upapasta/hooks/`
- Standardized metadata dictionary passed to hooks

### ~~3.7 · `upapasta --stats` (aggregated history)~~ ✅ Completed

### ~~3.9 · `--dry-run --verbose` prints complete argv of subprocesses~~ ✅ Completed

### ~~3.10 · Native Windows support tested (CI matrix)~~ ✅ Completed (0.28.0)

### ~~3.11 · Separate `profiles.py` from `config.py`~~ ✅ Completed

### ~~3.12 · `mypy --strict` in CI~~ ✅ Completed

### ~~3.13 · Test coverage ≥ 90% per module~~ ✅ Completed

### ~~3.14 · Complete documentation (man page, FAQ, troubleshooting)~~ ✅ Completed

### ~~3.15 · PyPI publication with automated workflow~~ ✅ Completed

### 3.8 · Interactive TUI mode (`--interactive`) `Low · High effort`
- **Moved to post-v1.0.0 roadmap**
- Interactive menu for history and simplified upload triggering

### 3.16 · Migrate to Python 3.10+ in `requires-python` (post-v1.0) `Low · Low effort`
- Allows `match/case`, `tomllib`
- Only after v1.0.0

---

## 🏁 v1.0.0 Criteria

- [x] All Phases 1 and 2 completed ✅
- [x] Green CI (pytest + mypy + ruff) ✅
- [x] Coverage ≥ 90% in core modules ✅
- [x] **F3.6** NFO templates implemented (commit bb9784d) ✅
- [x] **F3.17** Python plugin system implemented (commit fd3abf8) ✅
- [x] **Final Polish**: Documentation updated to v1.0.0 ✅
- [x] PyPI published ✅
- [x] Multi-platform support (Linux/macOS/Windows) ✅

---

## 📋 Summary of Priorities

| Phase | Version | Focus | Key items |
|-------|---------|-------|-----------|
| 1-2 | v0.25.0 | Core | Stability, i18n, Processes, Validation |
| 3 | v0.31.0 | Features | TMDb, 7z, Webhooks, Windows |
| Final | v1.0.0 | Packaging | NFO Templates, Python Hooks, 100% QA |

**Final push to v1.0.0** (in order):
1. **Validation** → 100% Documentation & Testing focus
2. **Launch** → v1.0.0 stable
