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
- (Optional) Creates RAR5 with password before upload
- Logs everything in `~/.config/upapasta/history.jsonl`

Zero Python dependencies — system binaries only.

---

## Installation

```bash
pip install upapasta
```

**System dependencies:**

| Binary | Function | Install |
|---------|--------|----------|
| `nyuu` | NNTP Upload | `npm install -g nyuu` |
| `parpar` | PAR2 Generation (recommended) | `pip install parpar` |
| `par2` | parpar alternative | `apt install par2` |
| `rar` | RAR5 (only with `--rar`) | `apt install rar` |
| `ffprobe` | Video metadata in NFO | `apt install ffmpeg` |
| `mediainfo` | Technical media info in NFO | `apt install mediainfo` |

See [INSTALL.md](INSTALL.md) for detailed instructions per platform.

---

## Configuration

On the first run, an interactive wizard creates `~/.config/upapasta/.env`:

```bash
upapasta --config
```

To configure failover with multiple NNTP servers, edit `.env` directly — see [DOCS.md § Multiple NNTP servers](DOCS.md#7-multiple-nntp-servers).

---

## Use cases

| Case | Command |
|------|---------|
| Entire folder | `upapasta Folder/` |
| Single file | `upapasta Episode.S01E01.mkv` |
| Multiple inputs | `upapasta A/ B/ C/` |
| Parallel | `upapasta A/ B/ C/ --jobs 3` |
| Reversible obfuscation | `upapasta Folder/ --obfuscate` |
| Maximum privacy | `upapasta Folder/ --strong-obfuscate` |
| RAR Password | `upapasta Folder/ --password "abc123"` |
| Each file = release | `upapasta /tv/Show.S04/ --each` |
| Season + Single NZB | `upapasta /tv/Show.S04/ --season` |
| Daemon (watch folder) | `upapasta /downloads/ --watch` |
| No upload (files only) | `upapasta Folder/ --skip-upload` |
| Dry run (simulate) | `upapasta Folder/ --dry-run` |
| Resume interrupted upload | `upapasta Folder/ --resume` |

---

## Recommended Workflow 2026

RAR is no longer necessary for most cases. parpar stores the folder hierarchy in `.par2` files, and recent SABnzbd/NZBGet versions rebuild the tree upon download:

```bash
upapasta Folder/ --obfuscate --backend parpar \
    --filepath-format common --par-profile safe
```

Use `--rar` only when you need a password (legacy cases) or when the downloader does not support reconstruction via PAR2.

### Obfuscation levels

| Flag | What is obfuscated | NZB shows original name? |
|------|-------------|--------------------------|
| (none) | nothing | yes |
| `--obfuscate` | files + PAR2 | yes (reversible) |
| `--strong-obfuscate` | files + PAR2 + NZB subjects | no |

---

## Main options

```
--rar                    Create RAR5 before upload
--obfuscate              Random names; NZB restores original names
--strong-obfuscate       Maximum privacy: random names for everything
--password PASSWORD      RAR password (automatically implies --rar)
--par-profile PROFILE    fast (5%) · balanced (10%) · safe (20%)
--jobs N                 Parallel uploads for multiple inputs
--resume                 Resume interrupted upload
--dry-run                Simulate without sending
--skip-upload            Generate RAR/PAR2/NFO without uploading
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
