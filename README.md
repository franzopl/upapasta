# UpaPasta

**UpaPasta** automatiza o upload completo para Usenet em um único comando: compacta em RAR5, gera paridade PAR2, faz o upload via nyuu e entrega o NZB pronto.

```bash
upapasta /caminho/para/pasta
```

→ **[Documentação completa](DOCS.md)**

## O que faz

| Entrada | Comportamento |
|---------|---------------|
| Pasta | RAR5 + PAR2 + upload → NZB + NFO |
| Arquivo único | PAR2 + upload direto (sem RAR) → NZB + NFO |
| `--each` | Cada arquivo da pasta vira um release separado |
| `--obfuscate` | RAR/PAR2 com nomes aleatórios no disco + senha automática; NZB salvo com nome original |
| `--watch` | Daemon que monitora uma pasta e processa o que chegar |

> `--obfuscate` renomeia RAR/PAR2 com nomes aleatórios e gera senha automaticamente.
> Use `--password SENHA` para definir a senha você mesmo — com ou sem `--obfuscate`.

Todos os uploads ficam registrados em `~/.config/upapasta/history.db` com senha, NZB e metadados — tudo recuperável mesmo que os arquivos sejam movidos.

## Uso rápido

```bash
# Upload comum — temporada completa ou filme único
upapasta /tv/Night.of.the.Living.Dead.S01/
upapasta /movies/Nosferatu.1922.mkv
upapasta /courses/'Learn Python in 24 hours'

# Upload ofuscado com senha automática
upapasta /tv/Night.of.the.Living.Dead.S01/ --obfuscate
upapasta /movies/Nosferatu.1922.mkv --obfuscate
upapasta /courses/'Learn Python in 24 hours' --obfuscate

# Monitorar pasta e processar automaticamente o que chegar
upapasta /downloads/ --watch
upapasta /files/ --watch --obfuscate

# Upload de todos os arquivos de uma pasta separadamente
upapasta /movies/ --each
upapasta /tv/Night.of.the.Living.Dead.S01/ --each --obfuscate

```

## Pré-requisitos

`rar` · `nyuu` · `parpar` (ou `par2`) — obrigatórios  
`ffmpeg` / `ffprobe` · `mediainfo` — recomendados (NFO com metadados de vídeo)

## Instalação

```bash
pip install upapasta
```

Na primeira execução, um assistente configura o servidor NNTP e salva em `~/.config/upapasta/.env`.

## Licença

MIT — veja [LICENSE](LICENSE).  
Contribuições são bem-vindas via *issue* ou *pull request*.
