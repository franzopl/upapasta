# UpaPasta

[English (en)](README.md)

**Uploader automatizado para Usenet.** Um comando, pipeline completo: PAR2 → upload → NZB pronto.

```bash
upapasta /tv/Night.of.the.Living.Dead.S01/
```

[![PyPI](https://img.shields.io/pypi/v/upapasta)](https://pypi.org/project/upapasta/)
[![CI](https://github.com/franzopl/upapasta/actions/workflows/ci.yml/badge.svg)](https://github.com/franzopl/upapasta/actions)
[![Python](https://img.shields.io/pypi/pyversions/upapasta)](https://pypi.org/project/upapasta/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## O que faz

- Gera PAR2 com perfis de redundância (5 / 10 / 20%)
- Faz upload via nyuu sem staging em `/tmp` (paths diretos)
- Entrega NZB + NFO com metadados de vídeo
- (Opcional) Cria RAR5 ou 7z com senha antes do upload
- Registra tudo em um histórico centralizado (JSONL)
- Multiplataforma: funciona em Linux, macOS e Windows

---

## Instalação

```bash
pip install upapasta
```

**Dependências do sistema:**

| Binário | Função | Instalar |
|---------|--------|----------|
| `nyuu` | Upload NNTP | `npm install -g nyuu` |
| `parpar` | Geração de PAR2 (recomendado) | `npm install -g @animetosho/parpar` |
| `7z` | Empacotamento open-source (recomendado) | `apt install p7zip-full` / `brew install p7zip` |
| `rar` | Suporte a RAR5 | `apt install rar` / `brew install rar` |
| `ffprobe` | Metadados de vídeo no NFO | `apt install ffmpeg` |
| `mediainfo` | Info técnica de mídia no NFO | `apt install mediainfo` |

Veja [INSTALL.md](INSTALL.md) para instruções detalhadas por plataforma.

---

## Configuração

Na primeira execução, um wizard interativo cria seu arquivo de configuração:

```bash
upapasta --config
```

- **Linux/macOS:** `~/.config/upapasta/.env`
- **Windows:** `%APPDATA%\upapasta\.env`

---

## Casos de uso

| Caso | Comando |
|------|---------|
| Pasta inteira | `upapasta Pasta/` |
| Arquivo único | `upapasta Episodio.S01E01.mkv` |
| Ofuscação reversível | `upapasta Pasta/ --obfuscate` |
| Pack + Senha (padrão) | `upapasta Pasta/ --password "abc123"` |
| Forçar 7z | `upapasta Pasta/ --7z` |
| Forçar RAR | `upapasta Pasta/ --rar` |
| Cada arquivo = release | `upapasta /tv/Show.S04/ --each` |
| Temporada + NZB único | `upapasta /tv/Show.S04/ --season` |
| Daemon (monitorar pasta) | `upapasta /downloads/ --watch` |
| Retomar upload interrompido | `upapasta Pasta/ --resume` |

---

## Fluxo recomendado 2026

RAR/7z não é mais necessário para a maioria dos casos. O parpar grava a hierarquia de pastas nos `.par2` e SABnzbd/NZBGet recentes reconstroem a árvore no download:

```bash
upapasta Pasta/ --obfuscate --par-profile safe
```

Use empacotamento (`--compress`, `--rar` ou `--7z`) apenas quando precisar de senha ou quando o downloader não suporta reconstrução de pastas via PAR2.

### Ofuscação

Desde a v0.28.0, a flag `--obfuscate` oferece stealth máximo por padrão:
- Arquivos e volumes PAR2 são renomeados para strings aleatórias.
- Os subjects do NZB são ofuscados (protegidos de "peepers" de indexadores).
- Os cabeçalhos de arquivo no NZB permitem que o downloader restaure os nomes originais automaticamente.

---

## Opções principais

```
-c, --compress           Ativa compactação usando compressor padrão do .env
--rar                    Força empacotamento em RAR5 (ignora .env)
--7z                     Força empacotamento em 7z (ignora .env)
--password SENHA         Senha de criptografia (usa compressor padrão se não especificado)
--obfuscate              Máxima privacidade: nomes aleatórios em tudo
--tmdb                   Enriquece o .nfo com dados do TMDb (requer API Key)
--tmdb-search TERMO      Busca manual no TMDb e lista IDs (utilitário)
--par-profile PERFIL     fast (5%) · balanced (10%) · safe (20%)
--jobs N                 Uploads paralelos quando múltiplos inputs
--resume                 Retoma upload interrompido
--dry-run                Simula sem enviar
--skip-upload            Gera arquivos sem fazer upload
--each                   Cada arquivo da pasta = release separado
--season                 Como --each + NZB único da temporada
--watch                  Daemon: processa automaticamente novos itens
```

`upapasta --help` lista todas as opções com descrições completas.

---

## Histórico e estatísticas

```bash
# Últimos 5 uploads
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool

# Estatísticas agregadas
upapasta --stats

# NZBs arquivados (hardlinks por timestamp)
ls -la ~/.config/upapasta/nzb/
```

---

## Webhooks e hooks

Configure notificações pós-upload no `.env`:

```ini
# Discord, Slack, Telegram ou qualquer endpoint que aceite POST JSON
WEBHOOK_URL=https://discord.com/api/webhooks/...

# Script externo (recebe variáveis UPAPASTA_*)
POST_UPLOAD_SCRIPT=/home/user/notificar.sh
```

Veja [DOCS.md § Hooks e webhooks](DOCS.md#hooks-e-webhooks) para a lista completa de variáveis.

---

## Documentação

- **[DOCS.md](DOCS.md)** — referência completa: configuração, pipeline, flags, ofuscação, PAR2, múltiplos servidores, resume, catálogo, hooks
- **[docs/FAQ.md](docs/FAQ.md)** — erros frequentes e respostas diretas
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — diagnóstico por sintoma
- **[INSTALL.md](INSTALL.md)** — instalação de dependências por plataforma
- **[CHANGELOG.md](CHANGELOG.md)** — histórico de versões

---

## Licença

MIT — veja [LICENSE](LICENSE).

Desenvolvido por **franzopl**.
