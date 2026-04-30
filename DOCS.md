# UpaPasta — Documentação

## Índice

- [Configuração](#configuração)
- [Como usar](#como-usar)
- [Opções de linha de comando](#opções-de-linha-de-comando)
- [Regras de comportamento](#regras-de-comportamento)
- [Pool de grupos Usenet](#pool-de-grupos-usenet)
- [Catálogo de uploads](#catálogo-de-uploads)
- [Hook pós-upload](#hook-pós-upload)
- [Estrutura do projeto](#estrutura-do-projeto)

---

## Configuração

Na primeira execução, um assistente interativo solicita as informações essenciais e gera `~/.config/upapasta/.env` automaticamente:

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

Para reconfigurar, apague o `.env` e execute o UpaPasta novamente.

### Variáveis do `.env`

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `NNTP_HOST` | Servidor NNTP | — |
| `NNTP_PORT` | Porta (563 = TLS) | `563` |
| `NNTP_SSL` | Usar SSL/TLS | `true` |
| `NNTP_USER` | Usuário NNTP | — |
| `NNTP_PASS` | Senha NNTP | — |
| `NNTP_CONNECTIONS` | Conexões simultâneas | `50` |
| `USENET_GROUP` | Grupo(s) de upload | `alt.binaries.boneless` |
| `ARTICLE_SIZE` | Tamanho máximo de artigo | `700K` |
| `NZB_OUT` | Template de caminho do `.nzb` | `{filename}.nzb` |
| `NZB_OUT_DIR` | Diretório de saída dos `.nzb` | diretório atual |
| `POST_UPLOAD_SCRIPT` | Script a executar após upload | — |

Consulte `.env.example` para a lista completa com descrições.

---

## Como usar

```bash
upapasta <caminho> [opções]
```

Sem argumentos, o UpaPasta exibe um guia rápido.

### Exemplos

**Pasta inteira como release único:**
```bash
upapasta Curso.Python.2024/
```

**Arquivo único (sem RAR):**
```bash
upapasta Episodio.S01E01.mkv
```

**Temporada completa — cada episódio como release separado:**
```bash
upapasta Temporada.1/ --each
```

**Release com nomes ofuscados:**
```bash
upapasta Pasta/ --obfuscate
```
> Renomeia RAR e PAR2 com nomes aleatórios antes do upload. O NZB é salvo com o nome original. Senha aleatória gerada automaticamente e injetada no NZB.

**Release com senha RAR:**
```bash
upapasta Pasta/ --password "MinhaSenh@"
```
> Senha injetada no NZB como `<meta type="password">` para extração automática por SABnzbd/NZBGet.

**Arquivo único ofuscado (RAR criado automaticamente):**
```bash
upapasta Episodio.mkv --obfuscate
```

**Mais paridade, mantendo os arquivos gerados:**
```bash
upapasta Pasta/ --par-profile safe --keep-files
```

**Simular sem enviar:**
```bash
upapasta Pasta/ --dry-run
```

**Modo watch — processa automaticamente o que chegar na pasta:**
```bash
upapasta /pasta/de/entrada --watch
```

**Processar vários itens em sequência:**
```bash
for pasta in /home/user/Uploads/*/; do
    upapasta "$pasta" --nzb-conflict fail
done
```

---

## Opções de linha de comando

### Essenciais

| Opção | Descrição |
|-------|-----------|
| `--each` | Processa cada arquivo da pasta individualmente |
| `--obfuscate` | Nomes aleatórios nos arquivos RAR/PAR2 antes do upload |
| `--password SENHA` | Protege o RAR com senha; injetada no NZB automaticamente |
| `--skip-rar` | Não cria RAR — envia arquivos como estão (incompatível com `--password`) |
| `--dry-run` | Simula tudo sem criar ou enviar arquivos |
| `--watch` | Modo daemon: monitora a pasta e processa novos itens automaticamente |

### Ajuste

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--par-profile` | Perfil PAR2: `fast` (5%), `balanced` (10%), `safe` (20%) | `balanced` |
| `-r`, `--redundancy N` | Redundância PAR2 em % (sobrescreve `--par-profile`) | conforme perfil |
| `--keep-files` | Mantém RAR e PAR2 após o upload | desativado |
| `--log-file PATH` | Grava log completo da sessão em arquivo | — |
| `--upload-retries N` | Tentativas extras em caso de falha de upload | `0` |
| `--verbose` | Ativa log de debug detalhado | desativado |

### Avançadas

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--backend` | Backend PAR2: `parpar` ou `par2` | `parpar` |
| `--post-size SIZE` | Tamanho alvo de post (ex: `20M`, `700K`) | conforme perfil |
| `--par-slice-size SIZE` | Override manual do slice PAR2 | automático |
| `--rar-threads N` | Threads para criação do RAR | CPUs disponíveis |
| `--par-threads N` | Threads para geração do PAR2 | CPUs disponíveis |
| `--max-memory MB` | Limite de memória para PAR2 | automático |
| `-s`, `--subject` | Assunto da postagem | nome do arquivo/pasta |
| `-g`, `--group` | Newsgroup de destino | do `.env` |
| `--nzb-conflict` | Conflito de NZB: `rename`, `overwrite`, `fail` | `rename` |
| `--env-file PATH` | Caminho alternativo para o `.env` | `~/.config/upapasta/.env` |
| `--upload-timeout N` | Timeout de conexão para nyuu (segundos) | sem timeout |
| `-f`, `--force` | Sobrescreve RAR/PAR2 existentes | desativado |
| `--skip-par` | Pula geração de paridade | desativado |
| `--skip-upload` | Pula o upload (gera apenas RAR/PAR2/NFO) | desativado |
| `--watch-interval N` | Intervalo de varredura em segundos (modo watch) | `30` |
| `--watch-stable N` | Segundos de tamanho estável antes de processar (modo watch) | `60` |

---

## Regras de comportamento

### RAR automático para arquivos únicos

Por padrão, arquivos únicos são enviados sem RAR. O RAR é criado automaticamente quando necessário:

| Situação | Comportamento |
|----------|---------------|
| `arquivo.mkv` | Upload direto, sem RAR |
| `arquivo.mkv --obfuscate` | Cria RAR → renomeia → upload |
| `arquivo.mkv --password abc` | Cria RAR com senha → upload |
| `arquivo.mkv --obfuscate --password abc` | Cria RAR com senha → renomeia → upload |

### Volumes RAR

| Tamanho total | Comportamento |
|---------------|---------------|
| ≤ 10 GB | RAR único (sem volumes) |
| > 10 GB | Volumes calculados para não ultrapassar 100 partes (mínimo 1 GB por volume) |

O RAR usa modo **store (`-m0`)** — sem compressão. Vídeos e áudios já são comprimidos; recomprimí-los não reduz tamanho e desperdiça CPU. O modo store preserva hashes dos arquivos originais.

### Combinações inválidas

- `--skip-rar` + `--password`: sem container RAR não há como aplicar senha → erro fatal.
- `--watch` + `--each`: modos incompatíveis → erro fatal.
- `--skip-rar` + backend `par2` (clássico) em pasta com subpastas: aviso — par2 não grava paths, hierarquia é perdida. Use `--backend parpar` (default) ou remova `--skip-rar`.

### Pastas vazias não são preservadas

Usenet posta **artigos** (arquivos), não diretórios. Não existe representação de "diretório vazio" no protocolo NNTP nem nos pacotes PAR2. Consequência:

- Em `--skip-rar`, qualquer subpasta sem arquivos somem no destino.
- Subpastas com arquivos são reconstruídas naturalmente pelo downloader a partir dos paths gravados pelo parpar (`-f common`).

**Workaround:** se a estrutura vazia importar (ex.: scaffolding de software, layout esperado por algum tooling), use o fluxo padrão com RAR — o RAR preserva diretórios vazios dentro do container:

```bash
# Pasta com subdirs vazios que precisam sobreviver ao round-trip
upapasta MeuProjeto/                    # cria RAR (default) → preserva tudo
upapasta MeuProjeto/ --skip-rar         # ⚠️ subdirs vazios serão perdidos
```

Alternativa leve: colocar um arquivo sentinela (`.keep`, `placeholder.bin`) em cada diretório vazio antes do upload com `--skip-rar`.

O orchestrator detecta pastas vazias em runtime quando `--skip-rar` está ativo e imprime aviso sugerindo a remoção da flag.

---

## Pool de grupos Usenet

Configure uma lista de grupos separada por vírgulas no `.env`. O UpaPasta seleciona um grupo aleatoriamente a cada upload, distribuindo os posts e dificultando remoções seletivas:

```env
USENET_GROUP=alt.binaries.movies,alt.binaries.hdtv,alt.binaries.multimedia,alt.binaries.boneless
```

O grupo efetivamente usado fica registrado no catálogo.

---

## Catálogo de uploads

Todos os uploads bem-sucedidos são registrados automaticamente em `~/.config/upapasta/history.db` (SQLite). Nenhuma configuração necessária.

### Campos registrados

| Campo | Descrição |
|-------|-----------|
| `data_upload` | Timestamp ISO-8601 UTC |
| `nome_original` | Nome do arquivo ou pasta enviada |
| `nome_ofuscado` | Subject usado com `--obfuscate` |
| `senha_rar` | Senha do RAR — crítica se o `.nzb` for perdido |
| `tamanho_bytes` | Tamanho total dos dados enviados |
| `categoria` | Detectada automaticamente: `Movie`, `TV`, `Anime` ou `Generic` |
| `grupo_usenet` | Grupo efetivamente usado (pós-seleção do pool) |
| `servidor_nntp` | Host NNTP utilizado |
| `redundancia_par2` | Percentual de paridade aplicado |
| `duracao_upload_s` | Duração total em segundos |
| `num_arquivos_rar` | Quantidade de volumes RAR gerados |
| `caminho_nzb` | Caminho do `.nzb` no disco |
| `nzb_blob` | Conteúdo binário do `.nzb` — recuperável mesmo que o arquivo seja movido |
| `subject` | Subject da postagem |

### Detecção automática de categoria

| Padrão no nome | Categoria |
|----------------|-----------|
| `[SubGroup] Título - 01` · `EP01` | `Anime` |
| `S01E01` · `1x01` · `Season 2` · `MINISERIES` | `TV` |
| `Título.2024.qualidade` (ano isolado no nome) | `Movie` |
| Nenhum padrão acima | `Generic` |

### Consultas úteis

Listar os 20 últimos uploads:
```bash
sqlite3 ~/.config/upapasta/history.db \
  "SELECT data_upload, nome_original, categoria, tamanho_bytes FROM uploads ORDER BY id DESC LIMIT 20;"
```

Recuperar um NZB perdido:
```bash
sqlite3 -bail ~/.config/upapasta/history.db \
  "SELECT nzb_blob FROM uploads WHERE nome_original LIKE '%Dune%' LIMIT 1;" \
  | xxd -r -p > recuperado.nzb
```

Total enviado:
```bash
sqlite3 ~/.config/upapasta/history.db \
  "SELECT printf('%.2f GB', SUM(tamanho_bytes) / 1e9) FROM uploads;"
```

---

## Hook pós-upload

Configure um script externo no `.env` para ser executado após cada upload bem-sucedido:

```env
POST_UPLOAD_SCRIPT=/home/user/meu_script.sh
```

O script recebe as informações via variáveis de ambiente `UPAPASTA_*`:

| Variável | Conteúdo |
|----------|----------|
| `UPAPASTA_NZB` | Caminho do `.nzb` gerado |
| `UPAPASTA_NFO` | Caminho do `.nfo` gerado |
| `UPAPASTA_SENHA` | Senha do RAR (vazia se não houver) |
| `UPAPASTA_NOME_ORIGINAL` | Nome original do arquivo/pasta |
| `UPAPASTA_NOME_OFUSCADO` | Nome ofuscado (vazio se não houver) |
| `UPAPASTA_TAMANHO` | Tamanho em bytes |
| `UPAPASTA_GRUPO` | Grupo Usenet usado |

Variáveis de ambiente são preferidas a argumentos posicionais: novos campos podem ser adicionados no futuro sem quebrar scripts existentes.

**Exemplos:**

```bash
#!/bin/sh
# Enviar NZB por FTP
curl -T "$UPAPASTA_NZB" "ftp://usuario:senha@servidor/nzbs/"

# Notificação via Telegram
curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=$CHAT_ID" \
  -d "text=Upload: $UPAPASTA_NOME_ORIGINAL ($UPAPASTA_GRUPO)"

# POST em fórum
curl -s -X POST "$FORUM_URL/api/post" \
  -F "subject=$UPAPASTA_NOME_ORIGINAL" \
  -F "nzb=@$UPAPASTA_NZB"
```

Timeout de 60 segundos. Falha no hook não afeta o código de saída do UpaPasta.

---

## Estrutura do projeto

```
upapasta/
├── upapasta/
│   ├── _process.py      # managed_popen: gerenciamento seguro de subprocessos
│   ├── catalog.py       # Catálogo SQLite de uploads + hook pós-upload
│   ├── cli.py           # Parsing de argumentos e validação de flags
│   ├── config.py        # Configuração, perfis PAR2, wizard de primeiro uso
│   ├── main.py          # Ponto de entrada
│   ├── makerar.py       # Criação de arquivos RAR5
│   ├── makepar.py       # Geração de PAR2 (parpar/par2), obfuscação
│   ├── nfo.py           # Geração de arquivos NFO
│   ├── nzb.py           # Geração e manipulação de NZB
│   ├── orchestrator.py  # Orquestração do workflow completo
│   ├── resources.py     # Cálculo automático de threads e memória
│   ├── ui.py            # PhaseBar, logging dual (console + arquivo)
│   ├── upfolder.py      # Upload via nyuu (sem cópia temporária)
│   └── watch.py         # Modo daemon --watch
├── tests/
├── .env.example
├── CHANGELOG.md
├── DOCS.md              # Esta documentação
└── README.md
```
