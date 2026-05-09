# UpaPasta — Reference Documentation

[Português (pt-BR)](docs/pt-BR/DOCS.md)

> Valid for UpaPasta ≥ 0.30.0. For earlier versions, consult the [CHANGELOG](CHANGELOG.md).

---

## Index

1. [Configuration](#1-configuration)
2. [Pipeline](#2-pipeline)
3. [Flag reference](#3-flag-reference)
4. [Operating modes](#4-operating-modes)
5. [Obfuscation](#5-obfuscation)
6. [Compression and packaging](#6-compression-and-packaging)
7. [PAR2 and backends](#7-par2-and-backends)
8. [Multiple NNTP servers](#8-multiple-nntp-servers)
9. [Resume](#9-resume)
10. [Catalog](#10-catalog)
11. [Hooks and webhooks](#11-hooks-and-webhooks)
12. [Profiles](#12-profiles)
13. [Empty folders](#13-empty-folders)

---

## 1. Configuration

### Interactive Wizard

On the first run (or with `upapasta --config`), an interactive wizard creates your configuration file:

- **Linux/macOS:** `~/.config/upapasta/.env`
- **Windows:** `%APPDATA%\upapasta\.env`

```
╔══════════════════════════════════════════════════════╗
║         UpaPasta Initial Configuration              ║
╚══════════════════════════════════════════════════════╝

── NNTP Server ───────────────────────────────────────
  ...
── Upload ────────────────────────────────────────────
  Usenet Group [alt.binaries.boneless]:
  Simultaneous connections [50]:
  Article size [700K]:
  Default compressor (rar or 7z) [rar]:
  .nzb output path [{filename}.nzb]:
```

Pressing Enter keeps the current value. If `DEFAULT_COMPRESSOR` is missing, **RAR** is used as the global fallback.

### `.env` Variables

#### Main NNTP Server

... (NNTP vars same as before) ...

#### Behavior

| Variable | Description | Default |
|----------|-------------|---------|
| `SKIP_ERRORS` | Ignore upload errors (`all` / `none`) | `all` |
| `DEFAULT_COMPRESSOR` | Default tool for packaging (`rar` / `7z`) | `rar` |
| `QUIET` | Suppress nyuu output | `false` |
| `LOG_TIME` | Display timestamps in logs | `true` |
| `NYUU_EXTRA_ARGS` | Extra args passed to nyuu | — |
| `DUMP_FAILED_POSTS` | Folder to save failed posts | — |

---

## 2. Pipeline

What happens when you run `upapasta Folder/`:

```
1. NFO Generation        ← mediainfo / ffprobe
2. NZB Verification      ← name conflict detected in advance
3. PACK (RAR or 7z)      ← only with --rar, --password, or if default is set
4. Normalization         ← renames files without extension to .bin
5. PAR2                  ← parpar (default) or par2; preserves hierarchy
6. Upload via nyuu       ← direct paths; no temp staging
7. NZB Post-processing   ← obfuscated subjects, injected password, XML check
8. Cleanup               ← removes temporary archive and PAR2
9. Reversion             ← undoes obfuscation and normalization
10. Catalog              ← logs in history.jsonl + archives NZB
11. Hook/webhook         ← POST_UPLOAD_SCRIPT + WEBHOOK_URL
```

### When each stage is skipped

| Stage | Condition to skip |
|-------|-------------------|
| PACK | without `--rar`, `--7z`, `--compress`, `--password`, or if not a folder/obfuscated single file |
| Rename extensionless | without `--rename-extensionless` |
| PAR2 | `--skip-par` |
| Upload | `--skip-upload` or `--dry-run` |
| Cleanup | `--keep-files` |

---

## 3. Flag reference

### Essentials

| Flag | Description |
|------|-------------|
| `--profile NAME` | Uses `~/.config/upapasta/<NAME>.env` as configuration |
| `--watch` | Daemon: monitors folder, processes new items automatically |
| `--each` | Each file in the folder = separate release with its own NZB |
| `--season` | Like `--each`, but also generates a single NZB with the entire season |
| `--obfuscate` | Maximum privacy: random names for files, PAR2 and NZB subjects |
| `--tmdb` | Enrich NFO with TMDb metadata (requires API Key in `.env`) |
| `--password [PASS]` | Encryption password; uses `DEFAULT_COMPRESSOR` if unspecified |
| `--compress` / `-c` | Activates packaging using default compressor from `.env` |
| `--rar` | Forces RAR5 packaging (ignores `.env`) |
| `--7z` | Forces 7z packaging (ignores `.env`) |
| `--dry-run` | Simulates everything without creating or sending files |
| `--jobs N` | Parallel uploads for multiple inputs (default: 1) |

> **Note:** `--rar`, `--7z`, and `--compress` are mutually exclusive.


### Adjustment

| Flag | Description | Default |
|------|-------------|---------|
| `--par-profile` | `fast` (5%), `balanced` (10%), `safe` (20%) | `balanced` |
| `-r N` / `--redundancy N` | PAR2 redundancy in % (overrides `--par-profile`) | — |
| `--keep-files` | Keeps RAR and PAR2 after upload | disabled |
| `--log-file PATH` | Writes full log to a file | — |
| `--upload-retries N` | Extra retries in case of failure | `0` |
| `--verbose` | Debug log with ISO timestamps | disabled |
| `--watch-interval N` | Scanning interval in seconds | `30` |
| `--watch-stable N` | Stable seconds before processing | `60` |

### Advanced

| Flag | Description | Default |
|------|-------------|---------|
| `--backend` | `parpar` or `par2` | `parpar` |
| `--filepath-format` | How parpar records paths: `common` / `keep` / `basename` / `outrel` | `common` |
| `--post-size SIZE` | Target post size (e.g., `700K`, `20M`) | from profile |
| `--par-slice-size SIZE` | Override PAR2 slice (e.g., `1M`, `2M`) | automatic |
| `--rar-threads N` | Threads for PACK stage (RAR or 7z) | available CPUs |
| `--par-threads N` | Threads for PAR2 | available CPUs |
| `--max-memory MB` | Memory limit for PAR2 | automatic |
| `-s` / `--subject` | Posting subject | file/folder name |
| `-g` / `--group` | Destination newsgroup | from `.env` |
| `--nzb-conflict` | `rename` / `overwrite` / `fail` when finding existing NZB | `rename` |
| `--env-file PATH` | Alternative `.env` | `~/.config/upapasta/.env` |
| `--upload-timeout N` | nyuu connection timeout in seconds | no limit |
| `-f` / `--force` | Overwrites existing RAR/PAR2 | disabled |
| `--skip-par` | Skips parity generation | disabled |
| `--skip-upload` | Generates files without uploading | disabled |
| `--parpar-args STR` | Extra args for parpar (tokenized via shlex) | — |
| `--nyuu-args STR` | Extra args for nyuu (tokenized via shlex) | — |
| `--rename-extensionless` | Renames files without extension to `.bin` (round-trip) | disabled |
| `--resume` | Resumes interrupted upload | disabled |

### Utilities (no input required)

| Flag | Description |
|------|-------------|
| `--config` | Configuration wizard (preserves existing values) |
| `--stats` | Aggregated history statistics |
| `--test-connection` | Validates NNTP handshake (host, port, credentials) |
| `--insecure` | Disables SSL certificate verification in `--test-connection` |

---

## 4. Operating modes

### Default (folder or single file)

```bash
upapasta /tv/Night.of.the.Living.Dead.S01/
upapasta /movies/Nosferatu.1922.mkv
```

A folder becomes a release. A file becomes a release.

### `--each` — each file = release

```bash
upapasta /tv/Show.S04/ --each --obfuscate
```

Iterates through all files in the folder and performs a separate upload for each. Ideal for seasons where each episode should have its own NZB.

### `--season` — episodes + season NZB

```bash
upapasta /tv/The.Boys.S04/ --season --obfuscate
```

Like `--each`: each episode has its individual NZB. Finally, generates a consolidated season NZB with the episode prefix in subjects. Useful for indexers that display full seasons.

### `--jobs N` — parallel

```bash
upapasta /folder1/ /folder2/ /folder3/ --jobs 3
```

Processes multiple inputs in parallel. Without `--jobs`, they are processed sequentially.

### `--watch` — daemon

```bash
upapasta /downloads/ --watch --obfuscate
upapasta /downloads/ --watch --watch-interval 60 --watch-stable 120
```

Monitors the folder continuously. When a new item appears and stays stable for `--watch-stable` seconds, the pipeline starts. Ctrl+C shuts down cleanly. Incompatible with `--each` and `--season`.

### `--dry-run` — simulation

```bash
upapasta Folder/ --dry-run --verbose
```

Runs the entire pipeline without creating or sending files. With `--verbose`, it prints the full argv of subprocesses (parpar, nyuu), useful for debugging configurations before a real upload.

### `--skip-upload` — generate without sending

```bash
upapasta Folder/ --skip-upload --keep-files
```

Generates RAR (if enabled), PAR2, and NFO locally without uploading. With `--keep-files`, the files remain in the output directory.

---

## 5. Obfuscation

Since v0.28.0, UpaPasta uses a unified obfuscation strategy centered on **Maximum Stealth**.

### Reversible Obfuscation (`--obfuscate`)

```bash
upapasta Folder/ --obfuscate
upapasta Folder/ --obfuscate --7z
```

What happens:

1. Files renamed to random strings before packaging/upload
2. PAR2 generated based on random names
3. NZB generated with obfuscated subjects (subjects look like `[89af32] "x1z.001" yEnc (1/1)`)
4. Downloaders (SABnzbd/NZBGet) use the `filename` header inside the NZB to restore original names automatically.

Result: No metadata leaks to Usenet or indexers. Only users with the NZB can see what the files are.

### Single file + obfuscation

A single file with `--obfuscate` or `--password` creates a temporary archive automatically:

| Input | Flags | Behavior |
|-------|-------|----------|
| `file.mkv` | — | direct upload |
| `file.mkv` | `--obfuscate` | creates archive → obfuscates → upload |
| `file.mkv` | `--password abc` | creates passworded archive → upload |

---

## 6. Compression and packaging

UpaPasta supports two main backends for creating multi-volume archives:

### RAR (Legacy / Proprietary)
- Requires `rar` binary.
- Produces `.rar`, `.part01.rar`, etc.
- Support for encryption with `-hp` (via `--password`).

### 7z (Open Source / Recommended)
- Requires `p7zip-full`.
- Produces `.7z`, `.7z.001`, etc.
- Support for encryption with header encryption (`-mhe=on`).
- Enabled via `--compressor 7z` or `DEFAULT_COMPRESSOR=7z` in `.env`.

### When is PACK stage active?
1. If the input is a **Folder** (always needs a container).
2. If the input is a single file but `--rar`, `--compressor` or `--password` is used.
3. If the input is a single file and `--obfuscate` is used (to avoid leaking original extensions on Usenet).

---

## 7. PAR2 and backends


### parpar vs par2

| | `parpar` | `par2` |
|--|----------|--------|
| Speed | much faster | slow |
| Subfolder support | yes (`filepath-format`) | no |
| Recommended | yes (default) | only if parpar is unavailable |

```bash
upapasta Folder/ --backend parpar   # default
upapasta Folder/ --backend par2     # legacy
```

### `--filepath-format`

Controls how parpar records paths in `.par2` files. Only for `--backend parpar`.

| Value | Behavior |
|-------|----------|
| `common` | Discards common prefix, preserves relative subfolders. **Default and recommended.** |
| `keep` | Preserves full absolute path |
| `basename` | Discards all paths (flat — no subfolders) |
| `outrel` | Relative to output directory |

```bash
# Preserve subfolder structure (default)
upapasta Folder/ --filepath-format common

# Flat: all files at the same level
upapasta Folder/ --filepath-format basename
```

### Redundancy Profiles

| Profile | Redundancy | Recommended Use |
|---------|------------|-----------------|
| `fast` | 5% | large files with high space cost |
| `balanced` | 10% | general use (default) |
| `safe` | 20% | important files or groups with high turnover |

```bash
upapasta Folder/ --par-profile safe
upapasta Folder/ --redundancy 15   # custom value in %
```

### Dynamic Slice

UpaPasta automatically calculates the PAR2 slice based on total size:

| Total Size | Factor |
|------------|--------|
| ≤ 50 GB | base (`ARTICLE_SIZE × 2`) |
| ≤ 100 GB | × 1.5 |
| ≤ 200 GB | × 2 |
| > 200 GB | × 2.5 |

Clamp: 1 MiB – 4 MiB. For manual override: `--par-slice-size 2M`.

### Automatic PAR2 Retry

If generation fails, UpaPasta tries a second time with half the threads and the `safe` profile. If it still fails, it preserves the RAR and instructs the user to resume with:

```bash
upapasta file.rar --force --par-profile safe
```

---

## 8. Multiple NNTP servers

Configure additional servers in `.env` for automatic failover. In case of primary server failure, the next upload attempt automatically uses the following server.

```ini
# Primary server (mandatory)
NNTP_HOST=news.primary.com
NNTP_PORT=563
NNTP_SSL=true
NNTP_USER=user1
NNTP_PASS=pass1
NNTP_CONNECTIONS=50

# Failover server 2
NNTP_HOST_2=news.backup.com
NNTP_PORT_2=563
NNTP_SSL_2=true
NNTP_USER_2=user2
NNTP_PASS_2=pass2
NNTP_CONNECTIONS_2=20

# Failover server 3 (missing fields inherit from primary)
NNTP_HOST_3=news.another.com
NNTP_CONNECTIONS_3=10
# NNTP_USER_3 and NNTP_PASS_3 inherited from NNTP_USER / NNTP_PASS
```

Supports up to `NNTP_HOST_9`. Fields not defined for server N inherit from the primary server (user, password, port, SSL).

The server actually used in each upload is recorded in the catalog (`servidor_nntp`).

---

## 9. Resume

If an upload is interrupted (Ctrl+C, network drop, error), resume with `--resume`:

```bash
upapasta Folder/ --resume      # same flags as original upload
```

UpaPasta:
1. Detects the `.upapasta-state.json` state file saved next to the partial NZB
2. Identifies which files were already posted successfully
3. Uploads only the remaining files
4. Merges NZBs (partial + new) into a complete final NZB
5. Removes the state file upon completion

### State file status

The `.upapasta-state.json` is automatically created before the upload starts. If the file goes missing (manually deleted, disk formatted), resume won't work — a full re-upload will be necessary.

To discard the state and start from scratch:
```bash
rm .upapasta-state.json
upapasta Folder/
```

---

## 10. Catalog

All successful uploads are automatically recorded in `~/.config/upapasta/history.jsonl` (JSONL, append-only). NZBs are archived in `~/.config/upapasta/nzb/` via hardlink — recoverable even if original files are moved or deleted.

### Recorded Fields

| Field | Description |
|-------|-------------|
| `data_upload` | ISO-8601 UTC timestamp |
| `nome_original` | Original name of uploaded file or folder |
| `nome_ofuscado` | Subject used with `--obfuscate` |
| `senha_rar` | RAR password — critical if NZB is lost |
| `tamanho_bytes` | Total size of uploaded data |
| `categoria` | `Movie` · `TV` · `Anime` · `Generic` (auto-detected) |
| `grupo_usenet` | Usenet group actually used (post-pool selection) |
| `servidor_nntp` | NNTP host used |
| `redundancia_par2` | Percentage of applied parity |
| `duracao_upload_s` | Total duration in seconds |
| `num_arquivos_rar` | Quantity of generated RAR volumes |
| `caminho_nzb` | `.nzb` path on disk |
| `subject` | Posting subject |

### Automatic Category Detection

| Pattern in Name | Category |
|-----------------|----------|
| `[SubGroup] Title - 01` · `EP01` | `Anime` |
| `S01E01` · `1x01` · `Season 2` · `MINISERIES` | `TV` |
| Isolated year in title (`Dune.2021.1080p`) | `Movie` |
| None of the above | `Generic` |

### Useful Queries

```bash
# Last 5 formatted uploads
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool

# Aggregated statistics (GB sent, categories, GB/month, etc.)
upapasta --stats

# Archived NZBs
ls -la ~/.config/upapasta/nzb/
```

```python
# Search by name
import json, pathlib, sys
term = "Dune"
for line in pathlib.Path("~/.config/upapasta/history.jsonl").expanduser().read_text().splitlines():
    e = json.loads(line)
    if term.lower() in e.get("nome_original", "").lower():
        print(json.dumps(e, indent=2, ensure_ascii=False))
```

```python
# Total sent in GB
import json, pathlib
total = sum(json.loads(l).get("tamanho_bytes", 0)
            for l in pathlib.Path("~/.config/upapasta/history.jsonl").expanduser().read_text().splitlines())
print(f"{total / 1e9:.2f} GB")
```

### Group Pool

If `USENET_GROUP=g1,g2,g3,...` in `.env`, UpaPasta randomly selects a group for each upload, distributing posts and making selective removals harder:

```ini
USENET_GROUP=alt.binaries.movies,alt.binaries.hdtv,alt.binaries.multimedia,alt.binaries.boneless
```

---

## 11. Hooks and webhooks

### Native Webhook (`WEBHOOK_URL`)

Configure in `.env`:

```ini
# Discord
WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token>

# Slack
WEBHOOK_URL=https://hooks.slack.com/services/<T>/<B>/<token>

# Telegram
WEBHOOK_URL=https://api.telegram.org/bot<token>/sendMessage?chat_id=<id>

# Generic (any endpoint accepting POST JSON)
WEBHOOK_URL=https://my-server.com/webhook
```

UpaPasta automatically detects destination type by URL pattern and formats the payload accordingly (Discord uses `embeds`, Telegram uses `text`, Slack uses `blocks`, generic uses free JSON).

### External Hook (`POST_UPLOAD_SCRIPT`)

```ini
POST_UPLOAD_SCRIPT=/home/user/notify.sh
```

The script is executed after each successful upload and receives information via environment variables:

| Variable | Content |
|----------|---------|
| `UPAPASTA_NZB` | Full path of generated `.nzb` |
| `UPAPASTA_NFO` | Full path of generated `.nfo` |
| `UPAPASTA_SENHA` | RAR password (empty if none) |
| `UPAPASTA_NOME_ORIGINAL` | Original file/folder name |
| `UPAPASTA_NOME_OFUSCADO` | Obfuscated name (same as original if without `--obfuscate`) |
| `UPAPASTA_TAMANHO` | Total size in bytes |
| `UPAPASTA_GRUPO` | Usenet group actually used |

60-second timeout. Non-zero return generates a warning but does not affect UpaPasta exit code.

```bash
# examples/post_upload_debug.sh — prints all received variables
POST_UPLOAD_SCRIPT=/path/to/upapasta/examples/post_upload_debug.sh
```

Usage Examples:

```bash
#!/bin/sh
# Send NZB via FTP
curl -T "$UPAPASTA_NZB" "ftp://user:password@server/nzbs/"

# Telegram Notification
curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=$CHAT_ID" \
  -d "text=Upload: $UPAPASTA_NOME_ORIGINAL ($UPAPASTA_GRUPO)"
```

---

## 12. Profiles

Profiles allow having distinct configurations for different servers or use cases:

```bash
# Uses ~/.config/upapasta/work.env
upapasta Folder/ --profile work

# Uses ~/.config/upapasta/backup.env
upapasta Folder/ --profile backup
```

Each profile is an independent `.env` with the same format. Missing fields **do not** inherit from the main `.env` — the profile is loaded in isolation.

To create a new profile, copy the main `.env` and edit:

```bash
cp ~/.config/upapasta/.env ~/.config/upapasta/work.env
```

---

## 13. Empty folders

**Usenet posts articles (files), not directories.** PAR2 also doesn't preserve empty directories. Consequence: subfolders without files disappear at the destination when `--rar` is not active.

Subfolders with files are reconstructed normally from paths recorded by parpar (`--filepath-format common`).

### Workarounds

```bash
# Option 1: use RAR (preserves empty directories inside the container)
upapasta MyProject/ --rar

# Option 2: sentinel file in each empty directory
touch MyProject/empty_subdir/.keep
upapasta MyProject/
```

The orchestrator detects empty subfolders at runtime when `--rar` is not active and prints a warning with workaround instructions.
