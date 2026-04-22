# UpaPasta

**UpaPasta** é uma ferramenta de linha de comando (CLI) em Python para automatizar o processo completo de upload de arquivos e pastas para a Usenet. Na maioria dos casos, um único comando é suficiente:

```bash
upapasta /caminho/para/pasta
```

O fluxo completo cobre:

1. **Compactação em RAR5** (store, sem compressão) para preservar estrutura e hashes
2. **Geração de paridade PAR2** para recuperação de artigos faltando
3. **Upload via nyuu** para o newsgroup configurado
4. **Geração de NZB e NFO** automaticamente
5. **Limpeza automática** de RAR e PAR2 após upload

## Comportamento padrão

| Entrada | Comportamento |
|---------|---------------|
| Pasta | RAR (store) + PAR2 + upload → NZB + NFO |
| Arquivo único | PAR2 + upload direto (sem RAR) → NZB + NFO |
| Pasta com `--each` | Cada arquivo vira um release separado com seu próprio NZB |

**Quando `--obfuscate` ou `--password` é usado com arquivo único**, o UpaPasta cria o RAR automaticamente — sem a necessidade de flags adicionais.

## Pré-requisitos

| Binário | Obrigatório | Função |
|---------|-------------|--------|
| `rar` | Sim | Compactação RAR5 (store) |
| `nyuu` | Sim | Upload para Usenet |
| `parpar` ou `par2` | Sim | Geração de arquivos de paridade |
| `ffmpeg` / `ffprobe` | Recomendado | Metadados de vídeo no NFO de pastas |
| `mediainfo` | Recomendado | NFO de arquivos únicos e séries |

## Instalação

### Via PyPI

```bash
pip install upapasta
```

### Para desenvolvimento

```bash
git clone https://github.com/franzopl/upapasta.git
cd upapasta
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuração

Na primeira execução, um assistente interativo solicita as informações essenciais e gera o arquivo `~/.config/upapasta/.env` automaticamente:

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

O arquivo gerado contém todas as variáveis configuráveis com comentários. Para reconfigurar, delete o `.env` e execute o UpaPasta novamente.

### Variáveis principais do `.env`

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `NNTP_HOST` | Servidor NNTP | — |
| `NNTP_PORT` | Porta (563 = TLS) | `563` |
| `NNTP_SSL` | Usar SSL/TLS | `true` |
| `NNTP_USER` | Usuário NNTP | — |
| `NNTP_PASS` | Senha NNTP | — |
| `NNTP_CONNECTIONS` | Conexões simultâneas | `50` |
| `USENET_GROUP` | Grupo de upload | `alt.binaries.boneless` |
| `ARTICLE_SIZE` | Tamanho máximo de artigo | `700K` |
| `NZB_OUT` | Caminho do `.nzb` gerado | `{filename}.nzb` |

Consulte `.env.example` para a lista completa com descrições detalhadas.

## Como usar

### Uso básico

```bash
upapasta <caminho> [opções]
```

Sem argumentos, o UpaPasta exibe um guia rápido de uso.

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
> Itera todos os arquivos da pasta. Cada `.mkv` vira um NZB independente.

**Release com nomes ofuscados:**
```bash
upapasta Pasta/ --obfuscate
```
> Renomeia RAR e PAR2 com nomes aleatórios antes do upload. O NZB é salvo com o nome original.

**Release com senha RAR:**
```bash
upapasta Pasta/ --password "MinhaSenh@"
```
> A senha é injetada no NZB como `<meta type="password">` para extração automática por SABnzbd/NZBGet.

**Ofuscado com senha (independentes, podem ser combinados):**
```bash
upapasta Pasta/ --obfuscate --password "abc123"
```

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

**Upload com retry e timeout:**
```bash
upapasta Pasta/ --upload-retries 3 --upload-timeout 60
```

**Processar vários itens em sequência:**
```bash
for pasta in /home/user/Uploads/*/; do
    upapasta "$pasta" --nzb-conflict fail
done
```

### Opções de linha de comando

#### Opções essenciais

| Opção | Descrição |
|-------|-----------|
| `--each` | Processa cada arquivo da pasta individualmente (ideal para temporadas) |
| `--obfuscate` | Nomes aleatórios nos arquivos RAR/PAR2 antes do upload |
| `--password SENHA` | Protege o RAR com senha; injetada no NZB automaticamente |
| `--skip-rar` | Não cria RAR — envia arquivos como estão. Incompatível com `--password` |
| `--dry-run` | Simula tudo sem criar ou enviar arquivos |

#### Opções de ajuste

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--par-profile` | Perfil PAR2: `fast` (5%), `balanced` (10%), `safe` (20%) | `balanced` |
| `-r`, `--redundancy N` | Redundância PAR2 em % (sobrescreve `--par-profile`) | conforme perfil |
| `--keep-files` | Mantém RAR e PAR2 após o upload | desativado |
| `--log-file PATH` | Grava log completo da sessão em arquivo | — |
| `--upload-retries N` | Tentativas extras em caso de falha de upload | `0` |
| `--verbose` | Ativa log de debug detalhado | desativado |

#### Opções avançadas

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
| `--skip-upload` | Pula o upload (gera apenas RAR/PAR2) | desativado |

## Regras de comportamento

### RAR automático para arquivos únicos

Por padrão, arquivos únicos são enviados sem RAR. Mas nas situações abaixo o RAR é criado automaticamente:

| Situação | Comportamento |
|----------|---------------|
| `arquivo.mkv` | Upload direto, sem RAR |
| `arquivo.mkv --obfuscate` | Cria RAR → renomeia → upload |
| `arquivo.mkv --password abc` | Cria RAR com senha → upload |
| `arquivo.mkv --obfuscate --password abc` | Cria RAR com senha → renomeia → upload |

### Aviso de subpastas com `--skip-rar`

Quando `--skip-rar` é usado em uma pasta que contém subpastas, o UpaPasta exibe um aviso: PAR2 não preserva hierarquia de diretórios de forma confiável entre diferentes clientes Usenet. Para pastas com subpastas, o RAR é sempre recomendado.

### `--skip-rar` + `--password` é erro

Sem RAR não há container para proteger com senha. O UpaPasta encerra com mensagem clara de erro.

## Lógica de volumes RAR

| Tamanho total | Comportamento |
|---------------|---------------|
| ≤ 10 GB | RAR único (sem volumes) |
| > 10 GB | Volumes calculados para não ultrapassar 100 partes (mínimo 1 GB por volume) |

O RAR usa modo **store (`-m0`)** — sem compressão. Vídeos e áudios já são comprimidos; tentar comprimí-los novamente não reduz o tamanho e apenas consome CPU e tempo. O modo store é significativamente mais rápido e preserva os hashes dos arquivos originais após extração.

## Catálogo de uploads

O UpaPasta mantém um histórico local de todos os uploads bem-sucedidos em `~/.config/upapasta/history.db` (SQLite). Nenhuma configuração é necessária — o banco é criado automaticamente.

### O que é salvo a cada upload

| Campo | Descrição |
|-------|-----------|
| `data_upload` | Timestamp ISO-8601 UTC |
| `nome_original` | Nome do arquivo ou pasta enviada |
| `nome_ofuscado` | Subject usado quando `--obfuscate` está ativo |
| `senha_rar` | Senha do RAR — crítica se você perder o `.nzb` |
| `tamanho_bytes` | Tamanho total dos dados enviados |
| `categoria` | Detectada automaticamente: `Movie`, `TV`, `Anime` ou `Generic` |
| `grupo_usenet` | Grupo efetivamente usado (pós-seleção do pool) |
| `servidor_nntp` | Host NNTP utilizado |
| `redundancia_par2` | Percentual de paridade aplicado |
| `duracao_upload_s` | Duração total em segundos |
| `num_arquivos_rar` | Quantidade de volumes RAR gerados |
| `caminho_nzb` | Caminho do `.nzb` no disco |
| `nzb_blob` | Conteúdo binário do `.nzb` — recuperável mesmo que o arquivo seja movido ou apagado |
| `subject` | Subject da postagem |

### Detecção automática de categoria

O UpaPasta analisa o nome do arquivo para inferir a categoria sem precisar de flags manuais:

| Padrão detectado | Categoria |
|-----------------|-----------|
| `[SubGroup] Título - 01` · `EP01` | `Anime` |
| `S01E01` · `1x01` · `Season 2` · `MINISERIES` | `TV` |
| `Título.2024.qualidade` (ano isolado no nome) | `Movie` |
| Nenhum padrão acima | `Generic` |

Para consultar o histórico diretamente:

```bash
sqlite3 ~/.config/upapasta/history.db \
  "SELECT data_upload, nome_original, categoria, tamanho_bytes FROM uploads ORDER BY id DESC LIMIT 20;"
```

Para recuperar um NZB perdido:

```bash
sqlite3 ~/.config/upapasta/history.db \
  "SELECT nzb_blob FROM uploads WHERE nome_original LIKE '%Dune%';" | xxd -r -p > recuperado.nzb
```

## Hook pós-upload

Você pode configurar um script externo para ser executado após cada upload bem-sucedido. Adicione ao seu `.env`:

```env
POST_UPLOAD_SCRIPT=/home/user/meu_script.sh
```

O UpaPasta executa o script e passa as informações via variáveis de ambiente — sem argumentos posicionais, para que novos campos possam ser adicionados no futuro sem quebrar scripts existentes:

| Variável | Conteúdo |
|----------|----------|
| `UPAPASTA_NZB` | Caminho do `.nzb` gerado |
| `UPAPASTA_NFO` | Caminho do `.nfo` gerado |
| `UPAPASTA_SENHA` | Senha do RAR (vazia se não houver) |
| `UPAPASTA_NOME_ORIGINAL` | Nome original do arquivo/pasta |
| `UPAPASTA_NOME_OFUSCADO` | Nome ofuscado (vazio se não houver) |
| `UPAPASTA_TAMANHO` | Tamanho em bytes |
| `UPAPASTA_GRUPO` | Grupo Usenet usado |

**Exemplos de uso:**

```bash
#!/bin/sh
# Enviar NZB por FTP após upload
curl -T "$UPAPASTA_NZB" "ftp://usuario:senha@servidor/nzbs/"

# Notificação via Telegram
curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=$CHAT_ID" \
  -d "text=Upload concluído: $UPAPASTA_NOME_ORIGINAL ($UPAPASTA_GRUPO)"

# POST em fórum (ex: FileSharingTalk)
curl -s -X POST "$FORUM_URL/api/post" \
  -F "subject=$UPAPASTA_NOME_ORIGINAL" \
  -F "nzb=@$UPAPASTA_NZB"
```

O script tem timeout de 60 segundos. Se falhar ou exceder o tempo, o UpaPasta exibe um aviso mas **não** considera o upload com falha — o resultado do hook não afeta o código de saída principal.

## Pool de grupos Usenet

Em vez de um único grupo, você pode configurar uma lista separada por vírgulas no `.env`. O UpaPasta seleciona um grupo aleatoriamente a cada upload, distribuindo os posts e dificultando remoções seletivas:

```env
USENET_GROUP=alt.binaries.movies,alt.binaries.hdtv,alt.binaries.multimedia,alt.binaries.boneless
```

O grupo efetivamente utilizado em cada upload fica registrado no catálogo (`grupo_usenet`).

## Estrutura do projeto

```
upapasta/
├── upapasta/
│   ├── __init__.py      # Inicialização do pacote
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
├── tests/               # Testes unitários
├── .env.example         # Exemplo de configuração
├── pyproject.toml       # Metadados e dependências
├── CHANGELOG.md         # Histórico de versões
└── README.md            # Este arquivo
```

## Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contribuição

Contribuições são bem-vindas! Se você encontrar um bug ou tiver uma sugestão, abra uma *issue* ou envie um *pull request*.
