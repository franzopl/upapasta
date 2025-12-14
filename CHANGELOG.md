# Changelog

All notable changes to this project will be documented in this file.

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
