# UpaPasta

**UpaPasta** automatiza o upload completo para Usenet em um único comando. Cria RAR5, gera paridade PAR2, faz o upload via nyuu e entrega o NZB pronto — tudo com o mínimo de configuração.

```bash
upapasta /caminho/para/pasta
```

→ **[Documentação completa](DOCS.md)** · **[CHANGELOG](CHANGELOG.md)**

## O que faz

1. **(Opcional)** Cria arquivos RAR5 a partir de pastas
2. **Gera PAR2** com perfis fast/balanced/safe e backends parpar (padrão) ou par2
3. **Faz upload** via nyuu sem cópia temporária — paths diretos
4. **Gera NZB + NFO** com metadados de vídeo
5. **Registra tudo** em `~/.config/upapasta/history.db` com senha, NZB e metadados

## Fluxo Recomendado 2026

Para pastas com subpastas, descarte o RAR e confie no parpar para preservar a hierarquia:

```bash
upapasta Pasta/ --backend parpar --obfuscate \
    --filepath-format common --par-profile safe
```

**Por quê?** SABnzbd/NZBGet recentes reconstroem a árvore no download. Sem RAR (padrão), a proteção vem de:
- Nomes aleatórios no subject e headers
- Estrutura de pastas preservada apenas nos .par2 (invisível em scans básicos)
- RAR-com-senha é opcional, para casos legados ou quando realmente necessário

## Casos de Uso

| Caso | Comando |
|------|---------|
| Pasta com subpastas | `upapasta Pasta/ --backend parpar` (sem RAR por padrão) |
| Arquivo único | `upapasta arquivo.mkv` (sem RAR automaticamente) |
| Ofuscado | `upapasta Pasta/ --obfuscate` |
| Monitoramento automático | `upapasta /downloads/ --watch` |
| Cada arquivo separado | `upapasta /tv/ --each` |
| Episódios + NZB da temporada | `upapasta /tv/Show.S04/ --season` |
| Teste sem upload | `upapasta Pasta/ --dry-run` |

## Uso Rápido

### Básico
```bash
upapasta /tv/Night.of.the.Living.Dead.S01/
upapasta /movies/Nosferatu.1922.mkv
upapasta /courses/'Learn Python'
```

### Com Obfuscação
```bash
# Pasta: obfuscação moderna (sem RAR): nomes aleatórios + parpar
upapasta /tv/Night.of.the.Living.Dead.S01/ --obfuscate

# Pasta: obfuscação + RAR com senha automática
upapasta /tv/Night.of.the.Living.Dead.S01/ --obfuscate --rar

# Pasta: obfuscação + RAR com senha manual
upapasta /tv/Show.S01/ --obfuscate --rar --password "abc123"

# Arquivo: obfuscação (sem RAR): apenas nomes aleatórios
upapasta /movies/Nosferatu.1922.mkv --obfuscate

# Arquivo: cria RAR com senha (não obfusca nomes)
upapasta /movies/Nosferatu.1922.mkv --password "xyz789"
```

### Modo Watch (Daemon)
```bash
upapasta /downloads/ --watch
upapasta /files/ --watch --obfuscate
```

### Modo Season
```bash
upapasta /tv/The.Boys.S04/ --season --obfuscate
```

### Upload Individual de Arquivos
```bash
upapasta /movies/ --each
upapasta /tv/Show.S01/ --each --obfuscate
```

## Pré-requisitos

**Obrigatórios:**
- `nyuu` — upload para NNTP
- `parpar` ou `par2` — geração de paridade (parpar recomendado)
- `rar` — compressão RAR5 (se usar RAR; é omitido com `--skip-rar`)

**Opcionais:**
- `ffmpeg` / `ffprobe` — metadados de vídeo em NFO
- `mediainfo` — informações detalhadas de mídia em NFO

## Instalação

### Via pip
```bash
pip install upapasta
```

### Desenvolvimento
```bash
git clone https://github.com/franzopl/upapasta.git
cd upapasta
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Na primeira execução, um assistente configura o servidor NNTP e salva em `~/.config/upapasta/.env`:

```bash
$ upapasta /path/to/folder
? Endereço NNTP (ex: news.provider.com): news.example.com
? Porta (padrão 119):
? Usuário: user@example.com
? Senha: ••••••••
```

## Opções Principais

**Compressão e Paridade:**
```
--rar                   Cria RAR antes do upload (padrão desativado)
--backend {parpar,par2} Backend de paridade (parpar é padrão)
--par-profile {fast,balanced,safe}  Perfil de redundância (safe = 20%)
--filepath-format       Formato de paths em PAR2: common=relativo, keep=absoluto, basename=flat
```

**Ofuscação e Proteção:**
```
--obfuscate             Nomes aleatórios + senha gerada (senha só usada com RAR)
--password SENHA        Define senha RAR manualmente (presume --rar automaticamente)
```

**Modos de Upload:**
```
--watch                 Modo daemon: monitora e processa automaticamente
--each                  Cada arquivo = um release separado
--season                Episódios individuais + NZB único da temporada
```

**Outros:**
```
--dry-run               Testa tudo sem fazer upload real
--log-file ARQUIVO      Salva log completo da sessão
--rename-extensionless  Renomeia arquivos sem extensão para .bin (evita .txt do SAB)
```

## Histórico

Todos os uploads são registrados em `~/.config/upapasta/history.jsonl` (JSONL, append-only):
- Caminho original
- Senha (se aplicável)
- NZB gerado (arquivado em `~/.config/upapasta/nzb/` via hardlink)
- Metadados (data, tamanho, backend usado)
- Categoria (detectada automaticamente)

```bash
# Inspecionar os últimos 5 uploads
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool

# NZBs arquivados (hardlinks por timestamp)
ls -la ~/.config/upapasta/nzb/
```

Recuperável mesmo que os arquivos sejam movidos ou deletados.

## Hooks Pós-Upload

Configure hooks em `~/.config/upapasta/.env` para executar ações após upload bem-sucedido:

```bash
HOOK_POST_UPLOAD=curl -X POST http://localhost:5000/upload -d '{"nzb": "%NZB%", "path": "%PATH%"}'
```

Variáveis disponíveis:
- `%NZB%` — caminho do arquivo NZB
- `%PATH%` — caminho original
- `%SENHA%` — senha (se aplicável)
- `%CATEGORIA%` — categoria detectada

## Notas Importantes

**Obfuscação e Senha:**
- `--obfuscate` gera uma senha automaticamente, MAS ela só é injetada no NZB se houver RAR (use `--obfuscate --rar`)
- `--password` presume automaticamente `--rar` (proteger com senha requer RAR)
- Fluxo moderno (sem RAR): proteção via nomes aleatórios + parpar apenas
- Arquivo único com `--obfuscate`: upload direto com nomes aleatórios (sem RAR por padrão)
- Arquivo único com `--password`: cria RAR automaticamente com senha

**Pastas e Estrutura:**
- Pastas vazias não são preservadas sem RAR (NNTP carrega apenas arquivos)
- Use `--rename-extensionless` ou `.keep` sentinela nas pastas vazias
- `--filepath-format common` (padrão) preserva subpastas relativas nos .par2

**SABnzbd:**
- Desative "Recursive Unpacking" para preservar `.zip` internos
- Use `--rename-extensionless` se houver arquivos sem extensão (evita .txt do SABnzbd)

**Interrupção:**
- Ctrl+C durante `--obfuscate`: rollback garantido — nomes revertidos automaticamente via `finally`

## Licença

MIT — veja [LICENSE](LICENSE).

Desenvolvido por **franzopl**. Contribuições via *issue* ou *pull request* são bem-vindas.
