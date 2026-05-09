# Installation — UpaPasta

[Português (pt-BR)](docs/pt-BR/INSTALL.md)

## 1. Install UpaPasta

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

### nyuu (mandatory — NNTP upload)

```bash
# Via npm (recommended)
npm install -g nyuu
```

Confirm with: `nyuu --version`

### parpar (mandatory for PAR2 — recommended)

```bash
# Cross-platform via npm
npm install -g @animetosho/parpar
```

Confirm with: `parpar --version`

### 7z (recommended alternative to RAR)

```bash
# Debian / Ubuntu
sudo apt install p7zip-full

# macOS
brew install p7zip

# Windows
# Install from: https://www.7-zip.org/
```

Confirm with: `7z --help`

### rar (optional — only with `--rar`)

```bash
# Debian / Ubuntu
sudo apt install rar

# macOS
brew install rar

# Windows
# Install WinRAR (rar.exe must be in PATH) or download standalone rar.exe from RARLAB
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
