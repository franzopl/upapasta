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
| `--obfuscate` | Nomes aleatórios nos RAR/PAR2; NZB com nome original |
| `--password` | Senha RAR injetada automaticamente no NZB |
| `--watch` | Daemon que monitora uma pasta e processa o que chegar |

Todos os uploads ficam registrados em `~/.config/upapasta/history.db` com senha, NZB e metadados — tudo recuperável mesmo que os arquivos sejam movidos.

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
