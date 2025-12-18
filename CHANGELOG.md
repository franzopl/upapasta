# Changelog

All notable changes to this project will be documented in this file.

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
