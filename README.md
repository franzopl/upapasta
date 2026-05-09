# UpaPasta

[Português (pt-BR)](README.pt-BR.md)

**Automated Usenet Uploader.** One command, full pipeline: PAR2 → upload → NZB ready.

```bash
upapasta /tv/Night.of.the.Living.Dead.S01/
```

[![PyPI](https://img.shields.io/pypi/v/upapasta)](https://pypi.org/project/upapasta/)
[![CI](https://github.com/franzopl/upapasta/actions/workflows/ci.yml/badge.svg)](https://github.com/franzopl/upapasta/actions)
[![Python](https://img.shields.io/pypi/pyversions/upapasta)](https://pypi.org/project/upapasta/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## What it does

- Generates PAR2 with redundancy profiles (5 / 10 / 20%)
- Uploads via nyuu without staging in `/tmp` (direct paths)
- Delivers NZB + NFO with video metadata
- (Optional) Creates RAR5 or 7z with password before upload
- Logs everything in a centralized history (JSONL)
- Cross-platform: works on Linux, macOS, and Windows

---

## Installation

```bash
pip install upapasta
```

**System dependencies:**

| Binary | Function | Install |
|---------|--------|----------|
| `nyuu` | NNTP Upload | `npm install -g nyuu` |
| `parpar` | PAR2 Generation (recommended) | `npm install -g @animetosho/parpar` |
| `7z` | Open source packaging (recommended) | `apt install p7zip-full` / `brew install p7zip` |
| `rar` | RAR5 support | `apt install rar` / `brew install rar` |
| `ffprobe` | Video metadata in NFO | `apt install ffmpeg` |
| `mediainfo` | Technical media info in NFO | `apt install mediainfo` |

See [INSTALL.md](INSTALL.md) for detailed instructions per platform.

---

## Configuration

On the first run, an interactive wizard creates your configuration file:

```bash
upapasta --config
```

- **Linux/macOS:** `~/.config/upapasta/.env`
- **Windows:** `%APPDATA%\upapasta\.env`

---

## Use cases

| Case | Command |
|------|---------|
| Entire folder | `upapasta Folder/` |
| Single file | `upapasta Episode.S01E01.mkv` |
| Reversible obfuscation | `upapasta Folder/ --obfuscate` |
| 7z + Password | `upapasta Folder/ --password "abc123" --compressor 7z` |
| RAR + Password | `upapasta Folder/ --password "abc123" --compressor rar` |
| Each file = release | `upapasta /tv/Show.S04/ --each` |
| Season + Single NZB | `upapasta /tv/Show.S04/ --season` |
| Daemon (watch folder) | `upapasta /downloads/ --watch` |
| Resume interrupted upload | `upapasta Folder/ --resume` |

---

## Recommended Workflow 2026

RAR/7z is no longer necessary for most cases. parpar stores the folder hierarchy in `.par2` files, and recent SABnzbd/NZBGet versions rebuild the tree upon download:

```bash
upapasta Folder/ --obfuscate --par-profile safe
```

### Obfuscation

Since v0.28.0, the `--obfuscate` flag provides maximum stealth by default:
- Files and PAR2 volumes are renamed to random strings.
- NZB subjects are obfuscated (protected from indexer "peepers").
- NZB file headers allow downloaders to restore original names automatically.

---

## Main options

```
--rar                    Create RAR5 before upload
--compressor {rar,7z}    Choose compressor (default: from .env)
--password PASSWORD      Encryption password (implies --rar or --compressor)
--obfuscate              Maximum privacy: random names for everything
--par-profile PROFILE    fast (5%) · balanced (10%) · safe (20%)
--jobs N                 Parallel uploads for multiple inputs
--resume                 Resume interrupted upload
--dry-run                Simulate without sending
--skip-upload            Generate files without uploading
--each                   Each file in folder = separate release
--season                 Like --each + single season NZB
--watch                  Daemon: automatically process new items
```

`upapasta --help` lists all options with full descriptions.

---

## History and statistics

```bash
# Last 5 uploads
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool

# Aggregated statistics
upapasta --stats

# Archived NZBs (hardlinks by timestamp)
ls -la ~/.config/upapasta/nzb/
```

---

## Webhooks and hooks

Configure post-upload notifications in `.env`:

```ini
# Discord, Slack, Telegram or any endpoint accepting POST JSON
WEBHOOK_URL=https://discord.com/api/webhooks/...

# External script (receives UPAPASTA_* variables)
POST_UPLOAD_SCRIPT=/home/user/notify.sh
```

See [DOCS.md § Hooks and webhooks](DOCS.md#10-hooks-and-webhooks) for the full list of variables.

---

## Documentation

- **[DOCS.md](DOCS.md)** — full reference: configuration, pipeline, flags, obfuscation, PAR2, multiple servers, resume, catalog, hooks
- **[docs/FAQ.md](docs/FAQ.md)** — frequent errors and direct answers
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — symptom-based diagnosis
- **[INSTALL.md](INSTALL.md)** — dependency installation per platform
- **[CHANGELOG.md](CHANGELOG.md)** — version history

---

## License

MIT — see [LICENSE](LICENSE).

Developed by **franzopl**.
