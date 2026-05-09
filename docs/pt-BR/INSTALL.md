# Instalação — UpaPasta

## 1. Instalar o UpaPasta

```bash
pip install upapasta
```

Para desenvolvimento:

```bash
git clone https://github.com/franzopl/upapasta.git
cd upapasta
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requer Python 3.9+.

---

## 2. Instalar dependências do sistema

O UpaPasta orquestra binários externos. Instale os que for usar:

### nyuu (obrigatório — upload NNTP)

```bash
# Via npm (recomendado)
npm install -g nyuu
```

Confirmar: `nyuu --version`

### parpar (obrigatório para PAR2 — recomendado)

```bash
# Multiplataforma via npm
npm install -g @animetosho/parpar
```

Confirmar: `parpar --version`

### 7z (alternativa recomendada ao RAR)

```bash
# Debian / Ubuntu
sudo apt install p7zip-full

# macOS
brew install p7zip

# Windows
# Instalar de: https://www.7-zip.org/
```

Confirmar: `7z --help`

### rar (opcional — apenas com `--rar`)

```bash
# Debian / Ubuntu
sudo apt install rar

# macOS
brew install rar

# Windows
# Instalar WinRAR (rar.exe fica no PATH) ou baixar rar.exe standalone do RARLAB
```

Confirmar: `rar --version`

### ffprobe (opcional — metadados de vídeo no NFO)

```bash
# Debian / Ubuntu
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Baixar de: https://ffmpeg.org/download.html e adicionar ao PATH
```

### mediainfo (opcional — informações técnicas de mídia no NFO)

```bash
# Debian / Ubuntu
sudo apt install mediainfo

# macOS
brew install mediainfo

# Windows
# Baixar de: https://mediaarea.net/en/MediaInfo/Download
```

---

## 3. Configuração inicial

Na primeira execução, o UpaPasta solicita as credenciais e cria `~/.config/upapasta/.env`:

```bash
upapasta --config
```

Para configurar manualmente, copie o template e edite:

```bash
cp .env.example ~/.config/upapasta/.env
nano ~/.config/upapasta/.env
```

---

## 4. Verificar instalação

```bash
# Confirmar que o comando está disponível
upapasta --help

# Testar conexão com o servidor NNTP configurado
upapasta --test-connection
```

Se `upapasta` não for encontrado após `pip install`, adicione o diretório de scripts do pip ao PATH:

```bash
# ~/.bashrc ou ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```
