# UpaPasta

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
- (Opcional) Cria RAR5 com senha antes do upload
- Registra tudo em `~/.config/upapasta/history.jsonl`

Zero dependências Python — apenas binários do sistema.

---

## Instalação

```bash
pip install upapasta
```

**Dependências do sistema:**

| Binário | Função | Instalar |
|---------|--------|----------|
| `nyuu` | Upload NNTP | `npm install -g nyuu` |
| `parpar` | Geração de PAR2 (recomendado) | `pip install parpar` |
| `par2` | Alternativa ao parpar | `apt install par2` |
| `rar` | RAR5 (apenas com `--rar`) | `apt install rar` |
| `ffprobe` | Metadados de vídeo no NFO | `apt install ffmpeg` |
| `mediainfo` | Info técnica de mídia no NFO | `apt install mediainfo` |

Veja [INSTALL.md](INSTALL.md) para instruções detalhadas por plataforma.

---

## Configuração

Na primeira execução, um wizard interativo cria `~/.config/upapasta/.env`:

```bash
upapasta --config
```

Para configurar failover com múltiplos servidores NNTP, edite o `.env` diretamente — veja [DOCS.md § Múltiplos servidores NNTP](DOCS.md#múltiplos-servidores-nntp).

---

## Casos de uso

| Caso | Comando |
|------|---------|
| Pasta inteira | `upapasta Pasta/` |
| Arquivo único | `upapasta Episodio.S01E01.mkv` |
| Múltiplos inputs | `upapasta A/ B/ C/` |
| Paralelo | `upapasta A/ B/ C/ --jobs 3` |
| Ofuscação reversível | `upapasta Pasta/ --obfuscate` |
| Máxima privacidade | `upapasta Pasta/ --strong-obfuscate` |
| Senha RAR | `upapasta Pasta/ --password "abc123"` |
| Cada arquivo = release | `upapasta /tv/Show.S04/ --each` |
| Temporada + NZB único | `upapasta /tv/Show.S04/ --season` |
| Daemon (monitorar pasta) | `upapasta /downloads/ --watch` |
| Sem upload (só gera arquivos) | `upapasta Pasta/ --skip-upload` |
| Simular sem enviar | `upapasta Pasta/ --dry-run` |
| Retomar upload interrompido | `upapasta Pasta/ --resume` |

---

## Fluxo recomendado 2026

RAR não é mais necessário para a maioria dos casos. O parpar grava a hierarquia de pastas nos `.par2` e SABnzbd/NZBGet recentes reconstroem a árvore no download:

```bash
upapasta Pasta/ --obfuscate --backend parpar \
    --filepath-format common --par-profile safe
```

Use `--rar` apenas quando precisar de senha (casos legados) ou quando o downloader não suporta reconstrução via PAR2.

### Níveis de ofuscação

| Flag | O que ofusca | NZB mostra nome original? |
|------|-------------|--------------------------|
| (nenhuma) | nada | sim |
| `--obfuscate` | arquivos + PAR2 | sim (reversível) |
| `--strong-obfuscate` | arquivos + PAR2 + subjects do NZB | não |

---

## Opções principais

```
--rar                    Cria RAR5 antes do upload
--obfuscate              Nomes aleatórios; NZB restaura nomes originais
--strong-obfuscate       Máxima privacidade: nomes aleatórios em tudo
--password SENHA         Senha RAR (presume --rar automaticamente)
--par-profile PERFIL     fast (5%) · balanced (10%) · safe (20%)
--jobs N                 Uploads paralelos quando múltiplos inputs
--resume                 Retoma upload interrompido
--dry-run                Simula sem enviar
--skip-upload            Gera RAR/PAR2/NFO sem fazer upload
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
