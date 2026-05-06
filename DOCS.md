# UpaPasta — Documentação de Referência

> Válido para UpaPasta ≥ 0.25.0. Para versões anteriores, consulte o [CHANGELOG](CHANGELOG.md).

---

## Índice

1. [Configuração](#1-configuração)
2. [Pipeline](#2-pipeline)
3. [Referência de flags](#3-referência-de-flags)
4. [Modos de operação](#4-modos-de-operação)
5. [Ofuscação](#5-ofuscação)
6. [PAR2 e backends](#6-par2-e-backends)
7. [Múltiplos servidores NNTP](#7-múltiplos-servidores-nntp)
8. [Resume](#8-resume)
9. [Catálogo](#9-catálogo)
10. [Hooks e webhooks](#10-hooks-e-webhooks)
11. [Perfis](#11-perfis)
12. [Pastas vazias](#12-pastas-vazias)

---

## 1. Configuração

### Wizard interativo

Na primeira execução (ou com `upapasta --config`), um wizard interativo cria `~/.config/upapasta/.env`:

```
╔══════════════════════════════════════════════════════╗
║         Configuração inicial do UpaPasta             ║
╚══════════════════════════════════════════════════════╝

── Servidor NNTP ─────────────────────────────────────
  Servidor NNTP (ex: news.eweka.nl): news.eweka.nl
  Porta NNTP [563]:
  Usar SSL/TLS? [true]:
  Usuário NNTP: meu_usuario
  Senha NNTP:

── Upload ────────────────────────────────────────────
  Grupo Usenet [alt.binaries.boneless]:
  Conexões simultâneas [50]:
  Tamanho do artigo [700K]:
  Caminho de saída do .nzb [{filename}.nzb]:
```

Enter mantém o valor atual. Para forçar reconfiguração completa: `upapasta --config`.

### Variáveis do `.env`

#### Servidor NNTP principal

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `NNTP_HOST` | Endereço do servidor NNTP | — |
| `NNTP_PORT` | Porta (119 = sem TLS, 443/563 = TLS) | `563` |
| `NNTP_SSL` | Usar TLS | `true` |
| `NNTP_IGNORE_CERT` | Ignorar erro de certificado SSL | `false` |
| `NNTP_USER` | Usuário NNTP | — |
| `NNTP_PASS` | Senha NNTP | — |
| `NNTP_CONNECTIONS` | Conexões simultâneas | `50` |

#### Servidores de failover (opcional)

Veja [§ 7 Múltiplos servidores NNTP](#7-múltiplos-servidores-nntp).

#### Upload

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `USENET_GROUP` | Grupo(s) de upload (vírgula para pool) | `alt.binaries.boneless` |
| `ARTICLE_SIZE` | Tamanho máximo de artigo | `700K` |
| `NZB_OUT` | Template de caminho do `.nzb` (`{filename}` = nome) | `{filename}.nzb` |
| `NZB_OUT_DIR` | Diretório de saída dos `.nzb` | diretório atual |
| `NZB_OVERWRITE` | Sobrescrever NZB existente | `true` |

#### Verificação pós-upload

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `CHECK_CONNECTIONS` | Conexões para verificar artigos | `5` |
| `CHECK_TRIES` | Tentativas por artigo | `2` |
| `CHECK_DELAY` | Intervalo entre tentativas | `5s` |
| `CHECK_RETRY_DELAY` | Delay antes de retry após falha | `30s` |

#### Comportamento

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SKIP_ERRORS` | Ignorar erros de upload (`all` / `none`) | `all` |
| `QUIET` | Suprimir saída do nyuu | `false` |
| `LOG_TIME` | Exibir timestamp nos logs | `true` |
| `NYUU_EXTRA_ARGS` | Args extras repassados ao nyuu | — |
| `DUMP_FAILED_POSTS` | Pasta para salvar posts que falharam | — |

#### Notificações

| Variável | Descrição |
|----------|-----------|
| `WEBHOOK_URL` | URL para notificação pós-upload (Discord/Slack/Telegram/genérico) |
| `POST_UPLOAD_SCRIPT` | Script externo executado após upload bem-sucedido |

Consulte `.env.example` incluído no repositório para o arquivo completo com comentários.

---

## 2. Pipeline

O que acontece ao executar `upapasta Pasta/`:

```
1. Geração de NFO        ← mediainfo / ffprobe
2. Verificação NZB       ← conflito de nome detectado antecipadamente
3. (--rar) RAR5          ← somente com --rar, --password, ou arquivo único com --obfuscate/--password
4. (--rename-extensionless) renomeia arquivos sem extensão para .bin
5. PAR2                  ← parpar (padrão) ou par2; preserva hierarquia via filepath-format=common
6. Upload via nyuu       ← sem staging em /tmp; paths diretos
7. Pós-processamento NZB ← subjects corrigidos, senha injetada, verificação XML
8. Cleanup               ← remove RAR/PAR2, a menos que --keep-files
9. Reversão              ← desfaz ofuscação e renomeação .bin
10. Catálogo             ← registra em history.jsonl + copia NZB
11. Hook/webhook         ← POST_UPLOAD_SCRIPT + WEBHOOK_URL
```

### Quando cada etapa é pulada

| Etapa | Condição para pular |
|-------|---------------------|
| RAR | sem `--rar` (e sem `--password`, e sem arquivo único com `--obfuscate`) |
| Rename extensionless | sem `--rename-extensionless` |
| PAR2 | `--skip-par` |
| Upload | `--skip-upload` ou `--dry-run` |
| Cleanup | `--keep-files` |

---

## 3. Referência de flags

### Essenciais

| Flag | Descrição |
|------|-----------|
| `--profile NOME` | Usa `~/.config/upapasta/<NOME>.env` como configuração |
| `--watch` | Daemon: monitora pasta, processa novos itens automaticamente |
| `--each` | Cada arquivo da pasta = release separado com NZB próprio |
| `--season` | Como `--each`, mas gera também um NZB único com toda a temporada |
| `--obfuscate` | Nomes aleatórios no RAR/PAR2; NZB restaura nomes originais |
| `--strong-obfuscate` | Nomes aleatórios em tudo, inclusive nos subjects do NZB |
| `--password [SENHA]` | Senha RAR injetada no NZB; presume `--rar`; sem argumento gera senha aleatória |
| `--rar` | Cria RAR5 antes do upload |
| `--dry-run` | Simula tudo sem criar ou enviar arquivos |
| `--jobs N` | Uploads paralelos quando múltiplos inputs (padrão: 1) |

### Ajuste

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--par-profile` | `fast` (5%), `balanced` (10%), `safe` (20%) | `balanced` |
| `-r N` / `--redundancy N` | Redundância PAR2 em % (sobrescreve `--par-profile`) | — |
| `--keep-files` | Mantém RAR e PAR2 após upload | desativado |
| `--log-file PATH` | Grava log completo em arquivo | — |
| `--upload-retries N` | Tentativas extras em caso de falha | `0` |
| `--verbose` | Log de debug com timestamps ISO | desativado |
| `--watch-interval N` | Intervalo de varredura em segundos | `30` |
| `--watch-stable N` | Segundos estável antes de processar | `60` |

### Avançadas

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--backend` | `parpar` ou `par2` | `parpar` |
| `--filepath-format` | Como parpar grava paths: `common` / `keep` / `basename` / `outrel` | `common` |
| `--post-size SIZE` | Tamanho alvo de post (ex: `700K`, `20M`) | do perfil |
| `--par-slice-size SIZE` | Override do slice PAR2 (ex: `1M`, `2M`) | automático |
| `--rar-threads N` | Threads para RAR | CPUs disponíveis |
| `--par-threads N` | Threads para PAR2 | CPUs disponíveis |
| `--max-memory MB` | Limite de memória para PAR2 | automático |
| `-s` / `--subject` | Subject da postagem | nome do arquivo/pasta |
| `-g` / `--group` | Newsgroup de destino | do `.env` |
| `--nzb-conflict` | `rename` / `overwrite` / `fail` ao encontrar NZB existente | `rename` |
| `--env-file PATH` | `.env` alternativo | `~/.config/upapasta/.env` |
| `--upload-timeout N` | Timeout de conexão nyuu em segundos | sem limite |
| `-f` / `--force` | Sobrescreve RAR/PAR2 existentes | desativado |
| `--skip-par` | Pula geração de paridade | desativado |
| `--skip-upload` | Gera arquivos sem fazer upload | desativado |
| `--parpar-args STR` | Args extras para parpar (tokenizado via shlex) | — |
| `--nyuu-args STR` | Args extras para nyuu (tokenizado via shlex) | — |
| `--rename-extensionless` | Renomeia arquivos sem extensão para `.bin` (round-trip) | desativado |
| `--resume` | Retoma upload interrompido | desativado |

### Utilitários (sem input obrigatório)

| Flag | Descrição |
|------|-----------|
| `--config` | Wizard de configuração (preserva valores existentes) |
| `--stats` | Estatísticas agregadas do histórico |
| `--test-connection` | Valida handshake NNTP (host, porta, credenciais) |
| `--insecure` | Desativa verificação de certificado SSL no `--test-connection` |

---

## 4. Modos de operação

### Padrão (pasta ou arquivo único)

```bash
upapasta /tv/Night.of.the.Living.Dead.S01/
upapasta /movies/Nosferatu.1922.mkv
```

Uma pasta vira um release. Um arquivo vira um release.

### `--each` — cada arquivo = release

```bash
upapasta /tv/Show.S04/ --each --obfuscate
```

Percorre todos os arquivos da pasta e faz um upload separado para cada um. Ideal para temporadas onde cada episódio deve ter seu próprio NZB.

### `--season` — episódios + NZB da temporada

```bash
upapasta /tv/The.Boys.S04/ --season --obfuscate
```

Como `--each`: cada episódio tem seu NZB individual. Ao final, gera um NZB consolidado da temporada com o prefixo do episódio nos subjects. Útil para indexadores que exibem temporadas completas.

### `--jobs N` — paralelo

```bash
upapasta /pasta1/ /pasta2/ /pasta3/ --jobs 3
```

Processa múltiplos inputs em paralelo. Sem `--jobs`, são processados em sequência.

### `--watch` — daemon

```bash
upapasta /downloads/ --watch --obfuscate
upapasta /downloads/ --watch --watch-interval 60 --watch-stable 120
```

Monitora a pasta continuamente. Quando um novo item aparece e fica estável por `--watch-stable` segundos, inicia o pipeline. Ctrl+C encerra de forma limpa. Incompatível com `--each` e `--season`.

### `--dry-run` — simulação

```bash
upapasta Pasta/ --dry-run --verbose
```

Executa todo o pipeline sem criar ou enviar arquivos. Com `--verbose`, imprime o argv completo dos subprocessos (parpar, nyuu), útil para depurar configurações antes do upload real.

### `--skip-upload` — gerar sem enviar

```bash
upapasta Pasta/ --skip-upload --keep-files
```

Gera RAR (se ativado), PAR2 e NFO localmente sem fazer upload. Com `--keep-files`, os arquivos ficam no diretório de saída.

---

## 5. Ofuscação

### Comparação dos modos

| Modo | Nomes nos arquivos | Nomes no NZB | Pode ser lido sem PAR2? |
|------|--------------------|--------------|-------------------------|
| (nenhum) | originais | originais | sim |
| `--obfuscate` | aleatórios | **originais** (restaurados) | sim |
| `--strong-obfuscate` | aleatórios | aleatórios | não (renomear manualmente ou via PAR2) |

### `--obfuscate` (ofuscação reversível)

```bash
upapasta Pasta/ --obfuscate
upapasta Pasta/ --obfuscate --rar           # com RAR
upapasta Pasta/ --obfuscate --password abc  # com senha RAR
```

O que acontece:

1. Arquivos renomeados para nomes aleatórios antes do upload
2. PAR2 gerado sobre os nomes aleatórios
3. Upload feito com os nomes aleatórios
4. `fix_nzb_subjects` restaura os nomes originais nos subjects do NZB
5. Arquivos locais renomeados de volta para os nomes originais

Resultado: na Usenet, os artigos têm nomes ininteligíveis. Quem tem o NZB vê os nomes originais e pode baixar normalmente.

**Rollback garantido:** se o processo for interrompido (Ctrl+C, erro), os nomes locais são restaurados automaticamente via `finally`. Se a restauração automática falhar (ex: disco cheio), o UpaPasta imprime instruções manuais de reversão.

### `--strong-obfuscate`

```bash
upapasta Pasta/ --strong-obfuscate
```

Implica `--obfuscate`, mas `fix_nzb_subjects` **não** restaura os nomes no NZB. Resultado: nomes aleatórios em absolutamente tudo — arquivos na Usenet, subjects no NZB e subjects nos indexadores.

Quem baixar via NZB verá arquivos com nomes aleatórios. A estrutura é recuperável via PAR2, mas o nome original precisa ser fornecido manualmente ou estar em algum metadado externo.

Use apenas quando privacidade máxima for crítica.

### Arquivo único + ofuscação

Arquivo único com `--obfuscate` ou `--password` cria RAR automaticamente:

| Input | Flags | Comportamento |
|-------|-------|---------------|
| `arquivo.mkv` | — | upload direto |
| `arquivo.mkv` | `--obfuscate` | cria RAR → ofusca → upload |
| `arquivo.mkv` | `--password abc` | cria RAR com senha → upload |
| `arquivo.mkv` | `--obfuscate --password abc` | cria RAR com senha → ofusca → upload |

### `--password` sem `--rar`

`--password` presume `--rar` automaticamente. Para pastas, o RAR é criado primeiro. Para arquivos únicos, também. A combinação `--skip-rar --password` é erro fatal (sem container RAR não há como aplicar senha).

---

## 6. PAR2 e backends

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

## 7. Múltiplos servidores NNTP

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

## 8. Resume

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

## 9. Catálogo

Todos os uploads bem-sucedidos são registrados automaticamente em `~/.config/upapasta/history.jsonl` (JSONL, append-only). Os NZBs são arquivados em `~/.config/upapasta/nzb/` via hardlink — recuperáveis mesmo que os arquivos originais sejam movidos ou deletados.

### Campos registrados

| Campo | Descrição |
|-------|-----------|
| `data_upload` | Timestamp ISO-8601 UTC |
| `nome_original` | Nome do arquivo ou pasta enviada |
| `nome_ofuscado` | Subject usado com `--obfuscate` |
| `senha_rar` | Senha do RAR — crítica se o NZB for perdido |
| `tamanho_bytes` | Tamanho total dos dados enviados |
| `categoria` | `Movie` · `TV` · `Anime` · `Generic` (detectada automaticamente) |
| `grupo_usenet` | Grupo efetivamente usado (pós-seleção do pool) |
| `servidor_nntp` | Host NNTP utilizado |
| `redundancia_par2` | Percentual de paridade aplicado |
| `duracao_upload_s` | Duração total em segundos |
| `num_arquivos_rar` | Quantidade de volumes RAR gerados |
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

## 10. Hooks e webhooks

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
| `UPAPASTA_SENHA` | Senha do RAR (vazia se não houver) |
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

## 11. Perfis

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

## 12. Pastas vazias

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
