# Changelog

All notable changes to this project will be documented in this file.

## 0.3.1 - 2025-12-14
- Fix: Prevent duplicate `.nfo` file creation in dry-run for single-file uploads.
- Feature: Accept single-file uploads (skip RAR by default) and generate PAR2, PAR2 generation improvements.
- Feature: Generate `.nfo` for single-file uploads using `mediainfo` and save to NZB_OUT folder; `.nfo` not uploaded to Usenet.
- Tests: Added/updated tests covering `.nfo` generation and upload flows.
