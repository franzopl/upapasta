# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**UpaPasta** is a Python CLI tool that automates the complete Usenet upload workflow:
1. Creates RAR archives from input folders/files
2. Generates PAR2 parity files
3. Uploads to Usenet via `nyuu`
4. Generates NZB and NFO metadata files
5. Cleans up temporary files

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

External binaries required: `rar`, `nyuu`, and `parpar` (or `par2`). Optional: `ffmpeg`/`ffprobe`, `mediainfo` (for NFO generation).

## Common Commands

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_orchestrator.py

# Run a single test by name
pytest tests/test_upfolder.py::test_upload_to_usenet_dry_run_single_file -v

# Run the CLI in dry-run mode
upapasta /path/to/folder --dry-run
```

## Architecture

The project has four core modules in `upapasta/`:

- **`main.py`** — `UpaPastaOrchestrator` class + CLI. Parses 40+ CLI options, loads credentials from `~/.config/upapasta/.env`, and orchestrates the 4-stage pipeline (RAR → PAR2 → NFO → Upload). Handles timing stats, dry-run simulation, obfuscation, and cleanup on error.

- **`makerar.py`** — `make_rar(folder_path, force, threads)`. Creates RAR5 archives with live progress. Returns int error codes (0=success, 2=invalid input, 3=exists, 4=rar not found, 5=exec error).

- **`makepar.py`** — `make_parity(rar_path, redundancy, force, backend, profile, threads)`. Generates PAR2 parity with three profiles:
  - `fast`: 5% redundancy, 20M slices
  - `balanced` (default): 10%, 10M slices
  - `safe`: 20%, 5M slices
  Backends: `parpar` (preferred) or `par2`.

- **`upfolder.py`** — `upload_to_usenet(input_path, env_vars, dry_run, subject, group, skip_rar)`. Builds and runs `nyuu`, handles folder uploads via temp dir, generates `.nzb`, resolves NZB conflicts (rename/overwrite/fail), and creates anonymous uploader identities.

## Error Code Convention

All module functions return integer codes: `0` = success, `1`–`6` = specific failures (documented in each function's docstring). The orchestrator checks these codes to decide whether to continue or abort.

## Configuration

Credentials and defaults live in `~/.config/upapasta/.env` (or `--env-file` override). See `.env.example` for all variables: NNTP connection params, `USENET_GROUP`, `ARTICLE_SIZE`, `NZB_OUT`, `NZB_CONFLICT`, `NFO_BANNER` (ASCII art prepended to folder `.nfo` files).

## Key Behaviors

- **Single-file uploads**: Detected automatically; RAR creation is skipped by default (`--skip-rar` implied).
- **NFO generation**: Single files use `mediainfo` output; folders get a tree + stats + optional `ffprobe` video metadata.
- **Obfuscation** (`--obfuscate`): Replaces the upload subject with a random alphanumeric string.
- **NZB conflict pre-check**: Happens before any processing starts to avoid partial work.

## Notes

- README and inline comments are written in Portuguese.
- No Python package dependencies beyond the stdlib — all heavy lifting is done by external binaries via `subprocess`.
