# UpaPasta — Documentação de Referência

[English (en)](../../DOCS.md)

> Válido para UpaPasta ≥ 0.30.0. Para versões anteriores, consulte o [CHANGELOG](../../CHANGELOG.md).

---

## Índice

1. [Configuração](#1-configuração)
2. [Pipeline](#2-pipeline)
3. [Referência de flags](#3-referência-de-flags)
4. [Modos de operação](#4-modos-de-operação)
5. [Ofuscação](#5-ofuscação)
6. [Compressão e Empacotamento](#6-compressão-e-empacotamento)
7. [PAR2 e backends](#7-par2-e-backends)
8. [Múltiplos servidores NNTP](#8-múltiplos-servidores-nntp)
9. [Resume](#9-resume)
10. [Catálogo](#10-catálogo)
11. [Hooks e webhooks](#11-hooks-e-webhooks)
12. [Perfis](#12-perfis)
13. [Pastas vazias](#13-pastas-vazias)

---

## 1. Configuração

### Wizard interativo

Na primeira execução (ou com `upapasta --config`), um wizard interativo cria seu arquivo de configuração:

- **Linux/macOS:** `~/.config/upapasta/.env`
- **Windows:** `%APPDATA%\upapasta\.env`

```
╔══════════════════════════════════════════════════════╗
║         Configuração inicial do UpaPasta             ║
╚══════════════════════════════════════════════════════╝

── Servidor NNTP ─────────────────────────────────────
  ...
── Upload ────────────────────────────────────────────
  Grupo Usenet [alt.binaries.boneless]:
  Conexões simultâneas [50]:
  Tamanho do artigo [700K]:
  Compressor padrão (rar ou 7z) [rar]:
  Caminho de saída do .nzb [{filename}.nzb]:
```

Enter mantém o valor atual. Se `DEFAULT_COMPRESSOR` não estiver definido, o programa assume **RAR** como fallback global.

### Variáveis do `.env`

#### Servidor NNTP principal

... (mesmas variáveis) ...

#### Comportamento

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SKIP_ERRORS` | Ignorar erros de upload (`all` / `none`) | `all` |
| `DEFAULT_COMPRESSOR` | Ferramenta padrão para empacotamento (`rar` / `7z`) | `rar` |
| `QUIET` | Suprimir saída do nyuu | `false` |
| `LOG_TIME` | Exibir timestamp nos logs | `true` |
| `NYUU_EXTRA_ARGS` | Args extras repassados ao nyuu | — |
| `DUMP_FAILED_POSTS` | Pasta para salvar posts que falharam | — |

---

## 2. Pipeline

O que acontece ao executar `upapasta Pasta/`:

```
1. Geração de NFO        ← mediainfo / ffprobe
2. Verificação NZB       ← conflito de nome detectado antecipadamente
3. PACK (RAR ou 7z)      ← somente com --rar, --password ou se definido no .env
4. Normalização          ← renomeia arquivos sem extensão para .bin
5. PAR2                  ← parpar (padrão) ou par2; preserva hierarquia
6. Upload via nyuu       ← paths diretos; sem staging temporário
7. Pós-processamento NZB ← subjects ofuscados, senha injetada, verificação XML
8. Cleanup               ← remove arquivo temporário e PAR2
9. Reversão              ← desfaz ofuscação e normalização .bin
10. Catálogo             ← registra em history.jsonl + arquiva NZB
11. Hook/webhook         ← POST_UPLOAD_SCRIPT + WEBHOOK_URL
```

### Quando cada etapa é pulada

... (mesma tabela, apenas atualizar referências se necessário) ...

---

## 3. Referência de flags

### Essenciais

| Flag | Descrição |
|------|-----------|
| `--profile NOME` | Usa `~/.config/upapasta/<NOME>.env` como configuração |
| `--watch` | Daemon: monitora pasta, processa novos itens automaticamente |
| `--each` | Cada arquivo da pasta = release separado com NZB próprio |
| `--season` | Como `--each`, mas gera também um NZB único com toda a temporada |
| `--obfuscate` | Stealth máximo: nomes aleatórios em arquivos, PAR2 e subjects do NZB |
| `--tmdb` | Enriquece o .nfo com dados do TMDb (requer API Key no `.env`) |
| `--password [SENHA]` | Senha de criptografia; usa `DEFAULT_COMPRESSOR` se não especificado |
| `--compress` / `-c` | Ativa compactação usando o compressor padrão do `.env` |
| `--rar` | Força empacotamento em RAR5 (ignora `.env`) |
| `--7z` | Força empacotamento em 7z (ignora `.env`) |
| `--dry-run` | Simula tudo sem criar ou enviar arquivos |
| `--jobs N` | Uploads paralelos quando múltiplos inputs (padrão: 1) |

> **Nota:** `--rar`, `--7z` e `--compress` são mutuamente exclusivos.

...

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--backend` | `parpar` ou `par2` | `parpar` |
| `--filepath-format` | Como parpar grava paths: `common` / `keep` / `basename` / `outrel` | `common` |
| `--post-size SIZE` | Tamanho alvo de post (ex: `700K`, `20M`) | do perfil |
| `--par-slice-size SIZE` | Override do slice PAR2 (ex: `1M`, `2M`) | automático |
| `--rar-threads N` | Threads para etapa PACK (RAR ou 7z) | CPUs disponíveis |
| `--par-threads N` | Threads para PAR2 | CPUs disponíveis |
| `--max-memory MB` | Limite de memória para PAR2 | automático |

...

---

## 5. Ofuscação

Desde a v0.28.0, o UpaPasta utiliza uma estratégia de ofuscação unificada focada em **Stealth Máximo**.

### Ofuscação Reversível (`--obfuscate`)

```bash
upapasta Pasta/ --obfuscate
upapasta Pasta/ --obfuscate --compressor 7z
```

O que acontece:

1. Arquivos renomeados para strings aleatórias antes do empacotamento/upload
2. PAR2 gerado sobre os nomes aleatórios
3. NZB gerado com subjects ofuscados (ex: `[89af32] "x1z.001" yEnc (1/1)`)
4. Downloaders (SABnzbd/NZBGet) usam o cabeçalho `filename` dentro do NZB para restaurar nomes originais automaticamente.

Resultado: Nenhum metadado vaza para a Usenet ou indexadores. Apenas quem tem o NZB sabe do que se trata o conteúdo.

### Arquivo único + ofuscação

Arquivo único com `--obfuscate` ou `--password` cria um arquivo temporário automaticamente:

| Input | Flags | Comportamento |
|-------|-------|---------------|
| `arquivo.mkv` | — | upload direto |
| `arquivo.mkv` | `--obfuscate` | cria arquivo temp → ofusca → upload |
| `arquivo.mkv` | `--password abc` | cria arquivo temp com senha → upload |

---

## 6. Compressão e Empacotamento

O UpaPasta suporta dois motores para criação de volumes:

### RAR (Legado / Proprietário)
- Requer binário `rar`.
- Produz `.rar`, `.part01.rar`, etc.
- Suporte a criptografia com `-hp` (via `--password`).
- Forçado via `--rar`.

### 7z (Open Source / Recomendado)
- Requer `p7zip-full`.
- Produz `.7z`, `.7z.001`, etc.
- Suporte a criptografia com ocultação de nomes (`-mhe=on`).
- Forçado via `--7z`.

### Quando a etapa PACK é ativada?
1. Se a entrada for uma **Pasta** (comportamento padrão: empacota a menos que se use `--skip-rar`).
2. Se a entrada for um arquivo único mas `--rar`, `--7z`, `--compress` ou `--password` for usado.
3. Se a entrada for um arquivo único e `--obfuscate` for usado (para evitar vazar extensões originais na rede).


---

## 7. PAR2 e backends

### parpar vs par2

| | `parpar` | `par2` |
|--|----------|--------|
| Velocidade | muito mais rápido | lento |
| Suporte a subpastas | sim (`filepath-format`) | não |
| Recomendado | sim (padrão) | somente se parpar não disponível |

```bash
upapasta Pasta/ --backend parpar   # padrão
upapasta Pasta/ --backend par2     # legado
```

### `--filepath-format`

Controla como o parpar registra os paths nos `.par2`. Apenas para `--backend parpar`.

| Valor | Comportamento |
|-------|---------------|
| `common` | Descarta o prefixo comum, preserva subpastas relativas. **Padrão e recomendado.** |
| `keep` | Preserva o caminho absoluto completo |
| `basename` | Descarta todos os paths (flat — sem subpastas) |
| `outrel` | Relativo ao diretório de saída |

```bash
# Preservar estrutura de subpastas (padrão)
upapasta Pasta/ --filepath-format common

# Flat: todos os arquivos no mesmo nível
upapasta Pasta/ --filepath-format basename
```

### Perfis de redundância

| Perfil | Redundância | Uso recomendado |
|--------|-------------|-----------------|
| `fast` | 5% | arquivos grandes com custo de espaço alto |
| `balanced` | 10% | uso geral (padrão) |
| `safe` | 20% | arquivos importantes ou grupos com alta rotatividade |

```bash
upapasta Pasta/ --par-profile safe
upapasta Pasta/ --redundancy 15   # valor personalizado em %
```

### Slice dinâmico

O UpaPasta calcula automaticamente o slice PAR2 com base no tamanho total:

| Tamanho total | Fator |
|---------------|-------|
| ≤ 50 GB | base (`ARTICLE_SIZE × 2`) |
| ≤ 100 GB | × 1.5 |
| ≤ 200 GB | × 2 |
| > 200 GB | × 2.5 |

Clamp: 1 MiB – 4 MiB. Para override manual: `--par-slice-size 2M`.

### Retry automático de PAR2

Se a geração falhar, o UpaPasta tenta uma segunda vez com metade dos threads e perfil `safe`. Se ainda falhar, preserva o RAR e instrui o usuário a retomar com:

```bash
upapasta arquivo.rar --force --par-profile safe
```

---

## 8. Múltiplos servidores NNTP

Configure servidores adicionais no `.env` para failover automático. Em caso de falha no servidor primário, a próxima tentativa de upload usa automaticamente o servidor seguinte.

```ini
# Servidor primário (obrigatório)
NNTP_HOST=news.primary.com
NNTP_PORT=563
NNTP_SSL=true
NNTP_USER=usuario1
NNTP_PASS=senha1
NNTP_CONNECTIONS=50

# Servidor de failover 2
NNTP_HOST_2=news.backup.com
NNTP_PORT_2=563
NNTP_SSL_2=true
NNTP_USER_2=usuario2
NNTP_PASS_2=senha2
NNTP_CONNECTIONS_2=20

# Servidor de failover 3 (campos ausentes herdam do primário)
NNTP_HOST_3=news.another.com
NNTP_CONNECTIONS_3=10
# NNTP_USER_3 e NNTP_PASS_3 herdados de NNTP_USER / NNTP_PASS
```

Suporta até `NNTP_HOST_9`. Campos não definidos no servidor N herdam do servidor primário (usuário, senha, porta, SSL).

O servidor efetivamente usado em cada upload é registrado no catálogo (`servidor_nntp`).

---

## 9. Resume

Se um upload for interrompido (Ctrl+C, queda de rede, erro), retome com `--resume`:

```bash
upapasta Pasta/ --resume      # mesmas flags do upload original
```

O UpaPasta:
1. Detecta o state file `.upapasta-state.json` salvo junto ao NZB parcial
2. Identifica quais arquivos já foram postados com sucesso
3. Faz upload apenas dos arquivos restantes
4. Mescla os NZBs (parcial + novo) em um NZB final completo
5. Remove o state file ao concluir

### Estado do state file

O `.upapasta-state.json` é criado automaticamente antes do início do upload. Se o arquivo sumir (deletado manualmente, disco formatado), o resume não funciona — será necessário refazer o upload completo.

Se quiser descartar o state e começar do zero:
```bash
rm .upapasta-state.json
upapasta Pasta/
```

---

## 10. Catálogo

Todos os uploads bem-sucedidos são registrados automaticamente em `~/.config/upapasta/history.jsonl` (JSONL, append-only). Os NZBs são arquivados em `~/.config/upapasta/nzb/` via hardlink — recuperáveis mesmo que os arquivos originais sejam movidos ou deletados.

### Campos registrados

| Campo | Descrição |
|-------|-----------|
| `data_upload` | Timestamp ISO-8601 UTC |
| `nome_original` | Nome do arquivo ou pasta enviada |
| `nome_ofuscado` | Subject usado com `--obfuscate` |
| `senha_rar` | Senha de criptografia — crítica se o NZB for perdido |
| `tamanho_bytes` | Tamanho total dos dados enviados |
| `categoria` | `Movie` · `TV` · `Anime` · `Generic` (detectada automaticamente) |
| `grupo_usenet` | Grupo efetivamente usado (pós-seleção do pool) |
| `servidor_nntp` | Host NNTP utilizado |
| `redundancia_par2` | Percentual de paridade aplicado |
| `duracao_upload_s` | Duração total em segundos |
| `num_arquivos_rar` | Quantidade de volumes (RAR ou 7z) gerados |
| `caminho_nzb` | Caminho do `.nzb` no disco |
| `subject` | Subject da postagem |

### Detecção automática de categoria

| Padrão no nome | Categoria |
|----------------|-----------|
| `[SubGroup] Título - 01` · `EP01` | `Anime` |
| `S01E01` · `1x01` · `Season 2` · `MINISERIES` | `TV` |
| Ano isolado no título (`Dune.2021.1080p`) | `Movie` |
| Nenhum padrão acima | `Generic` |

### Consultas úteis

```bash
# Últimos 5 uploads formatados
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool

# Estatísticas agregadas (GB enviado, categorias, GB/mês, etc.)
upapasta --stats

# NZBs arquivados
ls -la ~/.config/upapasta/nzb/
```

```python
# Buscar por nome
import json, pathlib, sys
termo = "Dune"
for line in pathlib.Path("~/.config/upapasta/history.jsonl").expanduser().read_text().splitlines():
    e = json.loads(line)
    if termo.lower() in e.get("nome_original", "").lower():
        print(json.dumps(e, indent=2, ensure_ascii=False))
```

```python
# Total enviado em GB
import json, pathlib
total = sum(json.loads(l).get("tamanho_bytes", 0)
            for l in pathlib.Path("~/.config/upapasta/history.jsonl").expanduser().read_text().splitlines())
print(f"{total / 1e9:.2f} GB")
```

### Pool de grupos

Se `USENET_GROUP=g1,g2,g3,...` no `.env`, o UpaPasta seleciona um grupo aleatoriamente a cada upload, distribuindo os posts e dificultando remoções seletivas:

```ini
USENET_GROUP=alt.binaries.movies,alt.binaries.hdtv,alt.binaries.multimedia,alt.binaries.boneless
```

---

## 11. Hooks e webhooks

### Webhook nativo (`WEBHOOK_URL`)

Configure no `.env`:

```ini
# Discord
WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token>

# Slack
WEBHOOK_URL=https://hooks.slack.com/services/<T>/<B>/<token>

# Telegram
WEBHOOK_URL=https://api.telegram.org/bot<token>/sendMessage?chat_id=<id>

# Genérico (qualquer endpoint que aceite POST JSON)
WEBHOOK_URL=https://meu-servidor.com/webhook
```

O UpaPasta detecta automaticamente o tipo de destino pelo padrão da URL e formata o payload adequadamente (Discord usa `embeds`, Telegram usa `text`, Slack usa `blocks`, genérico usa um JSON livre).

### Hook externo (`POST_UPLOAD_SCRIPT`)

```ini
POST_UPLOAD_SCRIPT=/home/user/notificar.sh
```

O script é executado após cada upload bem-sucedido e recebe as informações via variáveis de ambiente:

| Variável | Conteúdo |
|----------|----------|
| `UPAPASTA_NZB` | Caminho completo do `.nzb` gerado |
| `UPAPASTA_NFO` | Caminho completo do `.nfo` gerado |
| `UPAPASTA_SENHA` | Senha de compactação (vazia se não houver) |
| `UPAPASTA_NOME_ORIGINAL` | Nome original do arquivo/pasta |
| `UPAPASTA_NOME_OFUSCADO` | Nome ofuscado (igual ao original se sem `--obfuscate`) |
| `UPAPASTA_TAMANHO` | Tamanho total em bytes |
| `UPAPASTA_GRUPO` | Grupo Usenet efetivamente usado |

Timeout de 60 segundos. Retorno diferente de 0 gera aviso mas não afeta o código de saída do UpaPasta.

```bash
# examples/post_upload_debug.sh — imprime todas as variáveis recebidas
POST_UPLOAD_SCRIPT=/caminho/para/upapasta/examples/post_upload_debug.sh
```

Exemplos de uso:

```bash
#!/bin/sh
# Enviar NZB por FTP
curl -T "$UPAPASTA_NZB" "ftp://usuario:senha@servidor/nzbs/"

# Notificação Telegram
curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=$CHAT_ID" \
  -d "text=Upload: $UPAPASTA_NOME_ORIGINAL ($UPAPASTA_GRUPO)"
```

---

## 12. Perfis

Perfis permitem ter configurações distintas para servidores ou casos de uso diferentes:

```bash
# Usa ~/.config/upapasta/trabalho.env
upapasta Pasta/ --profile trabalho

# Usa ~/.config/upapasta/backup.env
upapasta Pasta/ --profile backup
```

Cada perfil é um `.env` independente com o mesmo formato. Campos ausentes **não** herdam do `.env` principal — o perfil é carregado de forma isolada.

Para criar um novo perfil, copie o `.env` principal e edite:

```bash
cp ~/.config/upapasta/.env ~/.config/upapasta/trabalho.env
```

---

## 13. Pastas vazias

**Usenet posta artigos (arquivos), não diretórios.** PAR2 também não preserva diretórios vazios. Consequência: subpastas sem arquivos somem no destino quando `--rar` não está ativo.

Subpastas com arquivos são reconstruídas normalmente a partir dos paths registrados pelo parpar (`--filepath-format common`).

### Workarounds

```bash
# Opção 1: usar RAR (preserva diretórios vazios dentro do container)
upapasta MeuProjeto/ --rar

# Opção 2: arquivo sentinela em cada diretório vazio
touch MeuProjeto/subdir_vazio/.keep
upapasta MeuProjeto/
```

O orchestrator detecta subpastas vazias em runtime quando `--rar` não está ativo e imprime aviso com instrução de workaround.
time quando `--rar` não está ativo e imprime aviso com instrução de workaround.
