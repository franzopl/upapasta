# Installation — UpaPasta

[Português (pt-BR)](docs/pt-BR/INSTALL.md)

## 1. Install UpaPasta

### Option A: Portable (Recommended for Windows / Non-technical users)

Download the latest `upapasta-portable-windows.zip` (or linux) from the [Releases](https://github.com/franzopl/upapasta/releases) page.

1. Extract the ZIP to a folder.
2. Run `upapasta.exe` (Windows) or `./upapasta` (Linux).
3. All core dependencies (pesto, ParPar, 7z) are included in the `bin/` folder.

### Option B: Via pip

```bash
pip install upapasta
```

For development:

```bash
git clone https://github.com/franzopl/upapasta.git
cd upapasta
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.9+.

---

## 2. Install system dependencies

UpaPasta orchestrates external binaries. Install the ones you will use:

### pesto (recommended — NNTP upload)

`pesto` is a fast, pure-Rust poster that replaces nyuu. UpaPasta automatically
prefers it when found in PATH.

```bash
# Build from source (requires Rust — https://rustup.rs)
git clone https://github.com/franzopl/pesto.git
cd pesto
cargo build --release
# Then copy target/release/pesto to a directory in PATH
```

Confirm with: `pesto --help`

### nyuu (fallback — NNTP upload)

Only needed when `pesto` is not available.

```bash
# Via npm
npm install -g nyuu
```

Confirm with: `nyuu --version`

### parpar (legacy fallback for PAR2)

Only needed if `pesto` is NOT available. UpaPasta recommends Pesto as it generates PAR2
internally and much faster.

```bash
# Cross-platform via npm
npm install -g @animetosho/parpar
```

Confirm with: `parpar --version`

### 7z (Recommended default)

UpaPasta now uses **7z** as the default compressor for its open-source nature.

```bash
# Debian / Ubuntu
sudo apt install p7zip-full

# macOS
brew install p7zip

# Windows
# Bundled in Portable version. Otherwise: https://www.7-zip.org/
```

Confirm with: `7z --help`

### rar (Optional — only with `--rar`)

If not found, UpaPasta will offer to **automatically download** the proprietary binary from RARLAB during its first use with the `--rar` flag.

```bash
# Debian / Ubuntu
sudo apt install rar

# macOS
brew install rar

# Windows
# Auto-downloaded by UpaPasta if missing, or install WinRAR manually.
```

Confirm with: `rar --version`

### ffprobe (optional — video metadata in NFO)

```bash
# Debian / Ubuntu
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from: https://ffmpeg.org/download.html and add to PATH
```

### mediainfo (optional — technical media info in NFO)

```bash
# Debian / Ubuntu
sudo apt install mediainfo

# macOS
brew install mediainfo

# Windows
# Download from: https://mediaarea.net/en/MediaInfo/Download
```

---

## 3. Initial Configuration

On the first run, UpaPasta will ask for credentials and create `~/.config/upapasta/.env`:

```bash
upapasta --config
```

To configure manually, copy the template and edit it:

```bash
cp .env.example ~/.config/upapasta/.env
nano ~/.config/upapasta/.env
```

---

## 4. Verify Installation

```bash
# Confirm that the command is available
upapasta --help

# Test connection with the configured NNTP server
upapasta --test-connection
```

If `upapasta` is not found after `pip install`, add the pip script directory to your PATH:

```bash
# ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```
