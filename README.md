# UpaPasta

**UpaPasta** é uma ferramenta de linha de comando (CLI) em Python para automatizar o processo completo de upload de arquivos e pastas para a Usenet. O fluxo cobre:

1. **Compactação em volumes RAR**: Cria arquivos `.rar` em múltiplas partes quando necessário (prática recomendada na Usenet).
2. **Geração de paridade PAR2**: Garante a integridade e permite recuperação mesmo com artigos faltando.
3. **Upload via nyuu**: Envia os arquivos ao newsgroup configurado.
4. **Geração de NZB e NFO**: Cria automaticamente o `.nzb` e um `.nfo` detalhado.
5. **Limpeza automática**: Remove arquivos temporários após o upload.

## Funcionalidades

- **Workflow automatizado**: Um único comando orquestra todas as etapas.
- **Volumes RAR inteligentes**: Arquivos até 10 GB geram um RAR único; acima disso são divididos em volumes de no mínimo 1 GB — no máximo 100 partes.
- **Arquivo único nativo**: Envio de arquivos `.mkv`, `.mp4` etc. sem criar RAR.
- **Perfis PAR2**: Três perfis pré-configurados (`fast`, `balanced`, `safe`) com opção de redundância manual e override de slice size (`--par-slice-size`).
- **Ofuscação real**: Renomeia fisicamente os arquivos RAR/PAR2 no disco com nomes aleatórios (`--obfuscate`). O NZB é salvo com o nome original. Sets de volumes (`nome.part*.rar`) são renomeados atomicamente.
- **Senha RAR automática**: Com `--obfuscate`, uma senha segura de 16 caracteres é gerada via `secrets` e injetada no `.nzb` como `<meta type="password">` para extração automática por SABnzbd, NZBGet e outros clientes. Personalizável com `--password`.
- **Retry automático de upload**: `--upload-retries N` reexecuta o nyuu em caso de falha transitória.
- **Timeout de conexão**: `--upload-timeout N` passa o timeout ao nyuu.
- **Verificação pós-upload do NZB**: Valida existência, tamanho e estrutura XML do `.nzb` gerado após o upload.
- **Logging estruturado**: Flag `--verbose` ativa nível DEBUG para diagnóstico detalhado.
- **Geração de NFO automática**:
  - Para arquivos únicos: saída do `mediainfo`.
  - Para pastas de séries (padrão `SXX`/`SXXEXX`): `mediainfo` do primeiro episódio.
  - Para pastas genéricas: estrutura em árvore, estatísticas e metadados de vídeo (duração, resolução, codec, bitrate).
  - Banner ASCII art customizável via variável `NFO_BANNER` no `.env`.
- **Dry Run**: Simula toda a execução sem criar ou enviar nada (`--dry-run`).
- **Limpeza automática**: Remove `.rar` e `.par2` após upload (desative com `--keep-files`).
- **Controle de conflitos NZB**: Define o comportamento quando um `.nzb` já existe (`rename`, `overwrite`, `fail`).

## Pré-requisitos

Antes de instalar, certifique-se de ter os seguintes binários externos disponíveis no `PATH`:

| Binário | Obrigatório | Função |
|---|---|---|
| `rar` | Sim | Compactação em formato RAR5 |
| `nyuu` | Sim | Upload para Usenet |
| `parpar` ou `par2` | Sim | Geração de arquivos de paridade |
| `ffmpeg` / `ffprobe` | Recomendado | Metadados de vídeo no NFO de pastas |
| `mediainfo` | Recomendado | NFO de arquivos únicos e séries |

## Instalação

### Via PyPI (recomendado)

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

O UpaPasta armazena as configurações em `~/.config/upapasta/.env`.

### Primeira execução

Na primeira execução, um questionário interativo solicita as informações essenciais e gera o arquivo `.env` completo automaticamente:

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

O arquivo gerado contém **todas** as variáveis configuráveis com comentários explicativos — basta abri-lo para ajustar qualquer opção avançada.

### Configuração manual

```bash
mkdir -p ~/.config/upapasta
cp .env.example ~/.config/upapasta/.env
# edite o arquivo com seus dados
```

### Variáveis principais

| Variável | Descrição | Padrão |
|---|---|---|
| `NNTP_HOST` | Servidor NNTP do provedor | — |
| `NNTP_PORT` | Porta (563 = TLS) | `563` |
| `NNTP_SSL` | Usar SSL/TLS | `true` |
| `NNTP_USER` | Usuário NNTP | — |
| `NNTP_PASS` | Senha NNTP | — |
| `NNTP_CONNECTIONS` | Conexões simultâneas | `50` |
| `USENET_GROUP` | Grupo de upload | `alt.binaries.boneless` |
| `ARTICLE_SIZE` | Tamanho máximo de artigo | `700K` |
| `NZB_OUT` | Caminho do `.nzb` gerado | `{filename}.nzb` |
| `SKIP_ERRORS` | Comportamento em erros (`all`/`none`) | `all` |

Consulte `.env.example` para a lista completa com descrições detalhadas.

## Como usar

```bash
upapasta /caminho/para/pasta [OPÇÕES]
```

### Exemplos

**Upload básico de uma pasta:**
```bash
upapasta /home/user/Series/Show.S01E01
```

**Arquivo único (sem RAR):**
```bash
upapasta /home/user/Videos/filme.mkv
```

**Simular sem enviar nada:**
```bash
upapasta /home/user/pasta --dry-run
```

**Redundância PAR2 maior e manter arquivos gerados:**
```bash
upapasta /home/user/pasta --par-profile safe --keep-files
```

**Upload ofuscado com senha RAR aleatória:**
```bash
upapasta /home/user/pasta --obfuscate
# Gera senha aleatória, renomeia RAR/PAR2, injeta senha no .nzb
```

**Upload ofuscado com senha customizada:**
```bash
upapasta /home/user/pasta --obfuscate --password "MinhaSenh@Segura"
```

**Upload com retry automático e timeout:**
```bash
upapasta /home/user/pasta --upload-retries 3 --upload-timeout 60
```

**Diagnóstico com log detalhado:**
```bash
upapasta /home/user/pasta --verbose
```

**Envio em lote — aborta se NZB já existe:**
```bash
for video in /home/user/Videos/*.mkv; do
    upapasta "$video" --nzb-conflict fail
done
```

**Envio em lote de pastas:**
```bash
for pasta in /home/user/Pastas/*/; do
    upapasta "$pasta" --nzb-conflict fail
done
```

### Opções de linha de comando

| Opção | Descrição | Padrão |
|---|---|---|
| `input` | **(Obrigatório)** Arquivo ou pasta a enviar | — |
| `--dry-run` | Simula a execução sem criar ou enviar arquivos | desativado |
| `--par-profile` | Perfil PAR2: `fast`, `balanced`, `safe` | `balanced` |
| `-r`, `--redundancy` | Redundância PAR2 em % (sobrescreve `--par-profile`) | conforme perfil |
| `--backend` | Backend PAR2: `parpar` ou `par2` | `parpar` |
| `--post-size` | Tamanho alvo de cada post (ex: `20M`, `700k`) | conforme perfil |
| `--par-slice-size` | Override manual do tamanho de slice PAR2 (ex: `5M`) | automático |
| `-s`, `--subject` | Assunto da postagem | nome da pasta/arquivo |
| `-g`, `--group` | Newsgroup de destino | valor do `.env` |
| `--skip-rar` | Pula a criação do `.rar` | desativado |
| `--skip-par` | Pula a geração de paridade | desativado |
| `--skip-upload` | Pula o upload | desativado |
| `-f`, `--force` | Sobrescreve `.rar` e `.par2` existentes | desativado |
| `--obfuscate` | Renomeia fisicamente RAR/PAR2 para nomes aleatórios; gera senha RAR automática | desativado |
| `--password` | Senha para o RAR (com `--obfuscate`, gerada automaticamente se omitida) | automática |
| `--keep-files` | Mantém `.rar` e `.par2` após o upload | desativado |
| `--rar-threads` | Threads para criação do RAR | número de CPUs |
| `--par-threads` | Threads para geração do PAR2 | número de CPUs |
| `--upload-retries` | Número de tentativas extras em caso de falha de upload | `0` |
| `--upload-timeout` | Timeout de conexão para o nyuu (segundos) | sem timeout |
| `--nzb-conflict` | Conflito de NZB: `rename`, `overwrite`, `fail` | `rename` |
| `--env-file` | Caminho alternativo para o arquivo `.env` | `~/.config/upapasta/.env` |
| `--verbose` | Ativa logging em nível DEBUG | desativado |

## Lógica de volumes RAR

O UpaPasta decide automaticamente se divide o arquivo em partes:

| Tamanho total | Comportamento |
|---|---|
| ≤ 10 GB | RAR único (sem volumes) |
| > 10 GB | Volumes calculados para não ultrapassar 100 partes (mínimo 1 GB por volume) |

Isso garante compatibilidade máxima com newsreaders, facilita repair parcial via PAR2 e evita downloads interrompidos sem recuperação.

## Estrutura do projeto

```
upapasta/
├── upapasta/
│   ├── __init__.py    # Inicialização do pacote
│   ├── config.py      # Carregamento e validação de configuração
│   ├── main.py        # Orquestrador principal e CLI
│   ├── makerar.py     # Criação de arquivos RAR em volumes
│   ├── makepar.py     # Geração de arquivos PAR2
│   ├── nfo.py         # Geração de arquivos NFO
│   ├── nzb.py         # Geração de arquivos NZB
│   └── upfolder.py    # Upload via nyuu
├── tests/             # Testes unitários
├── .env.example       # Exemplo de configuração
├── pyproject.toml     # Metadados e dependências do pacote
├── CHANGELOG.md       # Histórico de versões
└── README.md          # Este arquivo
```

## Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contribuição

Contribuições são bem-vindas! Se você encontrar um bug ou tiver uma sugestão de melhoria, abra uma *issue* ou envie um *pull request*.
