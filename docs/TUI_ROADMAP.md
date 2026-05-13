# TUI Roadmap — UpaPasta File Manager

> Decisão arquitetural: **TUI via `textual`** (não Web UI).
> Justificativa: uso primário é homelab headless via SSH; TUI funciona nativo sem servidor, sem porta aberta, integrado ao workflow CLI existente.
> Instalação opcional: `pip install upapasta[tui]` — não quebra a regra stdlib-only para usuários que não querem a TUI.

---

## Visão Geral

O modo TUI transforma o UpaPasta de "ferramenta de upload" em **gerenciador visual de conteúdo para Usenet**. O usuário navega pelo filesystem e vê instantaneamente o que já foi enviado, o que está pendente e o que falhou — sem precisar lembrar flags ou consultar o catálogo JSONL manualmente.

**Entry point:** `upapasta --tui` ou comando `upapasta-tui`

**Foco do produto:** conteúdo de mídia (filmes, séries, documentários) e cursos/conteúdo educativo em pasta. Não é gerenciador de backup genérico — mas nada impede esse uso.

---

## Stack Técnica

| Componente | Escolha | Justificativa |
|---|---|---|
| Framework TUI | `textual >= 0.60` | Mais maduro do ecossistema Python; suporte a layout, widgets, CSS-like theming, mouse |
| Extras install | `upapasta[tui]` | `textual` não entra no core; usuários CLI não são afetados |
| Módulo principal | `upapasta/tui/` | Sub-package separado do core |
| Dados | Lê `catalog.jsonl` existente | Sem novo formato; zero migração |
| Integração upload | Reutiliza `UpaPastaOrchestrator` | Sem duplicação de lógica |

---

## Estrutura de Módulos (alvo)

```
upapasta/
└── tui/
    ├── __init__.py
    ├── app.py              # Textual App principal, roteamento de telas
    ├── catalog_index.py    # Índice em memória do catalog.jsonl, keyed por path
    ├── fs_scanner.py       # Walk do filesystem, cross-referencia catalog_index
    ├── status.py           # Enum de status: UPLOADED / PENDING / FAILED / IN_PROGRESS
    ├── widgets/
    │   ├── file_tree.py    # TreeView customizado com ícones de status coloridos
    │   ├── status_bar.py   # Barra inferior com path, size, data de upload
    │   ├── upload_panel.py # Painel de progresso de upload em tempo real
    │   └── dashboard.py    # Painel direito com stats e saúde do catálogo
    └── screens/
        ├── main.py         # Tela principal (file manager)
        ├── upload.py       # Tela de confirmação e configuração de upload
        └── stats.py        # Tela de estatísticas expandida
```

---

## Fase 1 — Fundação de Dados (`v1.2.0`)

**Meta:** camada de dados que alimenta toda a TUI. Nenhuma UI ainda.

### 1.1 · `catalog_index.py` — Índice em Memória

Carrega `~/.config/upapasta/history.jsonl` e constrói um dicionário:

```python
# path normalizado → entrada mais recente do catálogo
index: dict[str, CatalogEntry]
```

- Normaliza paths (resolve symlinks, expande `~`)
- Lida com entradas duplicadas (múltiplos uploads do mesmo path) — mantém o mais recente
- Suporte a lookup por prefixo de diretório (para marcar pastas como "parcialmente enviadas")
- Re-carregamento incremental: detecta crescimento do arquivo JSONL sem recarregar tudo

### 1.2 · `fs_scanner.py` — Scanner de Filesystem

Walk iterativo de um diretório raiz, retorna `FileNode`:

```python
@dataclass
class FileNode:
    path: Path
    is_dir: bool
    size: int
    status: UploadStatus      # calculado via catalog_index
    upload_date: datetime | None
    nzb_path: Path | None
    children: list[FileNode]  # só se is_dir
```

Status calculados:
- `UPLOADED` — path está no catálogo com sucesso
- `PARTIAL` — pasta onde alguns filhos foram enviados mas não todos
- `PENDING` — não está no catálogo
- `FAILED` — está no catálogo com erro na última tentativa
- `IN_PROGRESS` — lock file de upload ativo (futuro)

### 1.3 · `status.py` — Enum + Cores

```python
class UploadStatus(Enum):
    UPLOADED    = ("✅", "green")
    PARTIAL     = ("🔶", "yellow")
    PENDING     = ("❌", "red")
    FAILED      = ("🔄", "orange")
    IN_PROGRESS = ("⏳", "cyan")
    IGNORED     = ("—",  "dim")
```

### 1.4 · Testes

- `tests/tui/test_catalog_index.py` — parsing de JSONL, lookup, deduplicação
- `tests/tui/test_fs_scanner.py` — status calculado corretamente para cada caso

**Critérios de saída da Fase 1:**
- [ ] `CatalogIndex` carrega e faz lookup em < 50ms para catálogos de 10k entradas
- [ ] `fs_scanner` classifica corretamente todos os 5 status
- [ ] Testes cobrindo ≥ 90% dos novos módulos
- [ ] `ruff` + `mypy --strict` passando nos novos módulos

---

## Fase 2 — File Manager Core (`v1.3.0`)

**Meta:** navegação visual no filesystem com indicadores de status. Sem upload ainda.

### Layout Principal

```
┌─ UpaPasta ─────────────────────────────────────────────────────────────────┐
│ 📁 /mnt/media/                                           [q]Sair [?]Ajuda  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ▼ 📁 Series/                                                              │
│    ✅ Breaking.Bad.S01.BluRay.1080p/    [2025-01-15 · 42 GB · NZB ✓]     │
│    ✅ Breaking.Bad.S02.BluRay.1080p/    [2025-01-16 · 44 GB · NZB ✓]     │
│    ❌ Breaking.Bad.S03.BluRay.1080p/    [Não enviado · 45 GB]             │
│    ⏳ Breaking.Bad.S04.BluRay.1080p/    [Enviando... 34%]                 │
│  ▼ 📁 Movies/                                                              │
│    ✅ Dune.Part.One.2021.4K.HDR/        [2025-02-03 · 87 GB · NZB ✓]     │
│    ❌ Dune.Part.Two.2024.4K.HDR/        [Não enviado · 92 GB]             │
│  ▼ 📁 Courses/                                                             │
│    🔶 Python.Advanced.Udemy/            [Parcial: 12/18 aulas enviadas]   │
│    ❌ Rust.For.Beginners.2024/          [Não enviado · 4.2 GB]            │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│ Breaking.Bad.S03 · 45 GB · Última mod: 2024-11-20 · Status: Pendente      │
└────────────────────────────────────────────────────────────────────────────┘
```

### Funcionalidades

**Navegação:**
- `↑/↓` — mover cursor
- `→/Enter` — expandir pasta / entrar
- `←` — recolher / voltar ao pai
- `Space` — selecionar item (multi-select)
- `g/G` — ir para topo/fim
- `Tab` — alternar entre painéis (quando dashboard ativo)

**Filtros rápidos (teclas):**
- `1` — mostrar somente `PENDING` (o que precisa ser enviado)
- `2` — mostrar somente `UPLOADED`
- `3` — mostrar somente `FAILED`
- `0` — mostrar tudo
- `/` — busca por nome dentro da pasta atual

**Informações no rodapé:**
- Path completo do item sob cursor
- Tamanho, data de modificação, status detalhado
- Para `UPLOADED`: data de envio, tamanho do NZB, path do NZB arquivado

### `widgets/file_tree.py`

- Subclasse de `textual.widgets.Tree`
- Renderiza cada nó com ícone de status + cor
- Lazy loading de subdiretórios (não carrega tudo de uma vez para pastas grandes)
- Indicador de progresso para `IN_PROGRESS` (barra ASCII inline)
- Atualização incremental: re-scan só dos nós visíveis quando catálogo muda

**Critérios de saída da Fase 2:**
- [ ] Navegação fluida em diretórios com 1000+ itens
- [ ] Status visualmente claros e distinguíveis sem cores (para terminais sem cor)
- [ ] `Space` multi-select funcional
- [ ] Filtros `1/2/3/0` funcionando
- [ ] Busca `/` com highlight

---

## Fase 3 — Integração de Upload (`v1.4.0`)

**Meta:** disparar uploads diretamente da TUI, com progresso em tempo real.

### Fluxo de Upload pela TUI

```
Usuário seleciona itens (Space) → pressiona [U]
    ↓
Tela de confirmação:
  • Lista de itens selecionados com tamanho total
  • Estimativa de PAR2 gerado
  • Estimativa de tempo (baseado em velocidade histórica do catálogo)
  • Opções inline: --obfuscate, --rar, --par-profile
  → [Enter] confirmar / [Esc] cancelar
    ↓
Painel de progresso in-TUI (reutiliza lógica de _progress.py):
  Phase: PAR2 [████████░░] 80% · 2.1 GB/2.6 GB
  Phase: Upload [████░░░░░░] 40% · 4.2 GB/10.5 GB · 12 MB/s
  ETA: 8m 23s
    ↓
Resultado: NZB salvo + catálogo atualizado + status muda para ✅ ao vivo
```

### `widgets/upload_panel.py`

- Painel lateral que aparece durante upload ativo
- Barra de progresso por fase (PAR2, Upload, Verificação)
- Speed atual e ETA calculado
- Log de output do nyuu/parpar em área scrollável
- Botão `[X]` para cancelar (envia SIGTERM via `managed_popen`)

### `screens/upload.py`

- Tela modal de confirmação pré-upload
- Exibe configurações que serão usadas (inferidas do `.env` ativo)
- Permite sobrescrever flags pontualmente sem precisar da CLI

**Critérios de saída da Fase 3:**
- [x] Upload completo disparado da TUI sem abrir terminal separado
- [x] Progresso em tempo real (stdout capturado linha a linha + barra de fase)
- [x] Cancelamento limpo via Esc (SIGTERM → subprocess termina)
- [x] Status do arquivo na árvore atualiza ao concluir (reload() automático)
- [x] Erros exibidos no log com estilo vermelho + código de saída

---

## Fase 4 — Dashboard de Saúde (`v1.5.0`)

**Meta:** painel lateral com visão agregada do catálogo e alertas.

### Layout com Dashboard Ativo

```
┌─ UpaPasta ──────────────────────┬─ Dashboard ──────────────────────────────┐
│ 📁 /mnt/media/                  │                                          │
│                                 │  📊 Visão Geral                          │
│  ✅ Breaking.Bad.S01/           │  ─────────────────────────────────────   │
│  ✅ Breaking.Bad.S02/           │  Enviados:   847 GB  (63 itens)          │
│  ❌ Breaking.Bad.S03/           │  Pendentes:  312 GB  (21 itens)          │
│  ⏳ Breaking.Bad.S04/           │  Falhas:       0 GB  ( 0 itens)          │
│  ✅ Dune.Part.One/              │                                          │
│  ❌ Dune.Part.Two/              │  📈 Uploads (últimos 30 dias)            │
│  🔶 Python.Advanced/           │  ─────────────────────────────────────   │
│  ❌ Rust.For.Beginners/         │   Jan ▂▂▄▄▆▆█▆▄▂▂▂▄▄▄▆▆▆▄▄▂▂▁▁▂▂▂▂▄   │
│                                 │   0 GB ────────────────────── 150 GB    │
│                                 │                                          │
│                                 │  ⚠️  Alertas                            │
│                                 │  ─────────────────────────────────────   │
│                                 │  • 3 itens com > 90 dias sem verificação │
│                                 │  • Python.Advanced: upload incompleto    │
│                                 │                                          │
├─────────────────────────────────┴──────────────────────────────────────────┤
│ Breaking.Bad.S03 · 45 GB · Pendente                     [D] Toggle Dashboard│
└────────────────────────────────────────────────────────────────────────────┘
```

### `widgets/dashboard.py`

**Métricas calculadas do catálogo:**
- Total enviado (GB + contagem de itens)
- Total pendente (GB + contagem)
- Falhas recentes (últimas 48h)
- Taxa de sucesso histórica

**Sparkline de uploads:**
- ASCII chart dos últimos 30 dias de atividade
- Baseado em `upload_date` do catálogo JSONL
- Escala automática por GB

**Alertas ativos:**
- Itens com mais de N dias enviados sem re-verificação (configurável)
- Itens com status `PARTIAL` (pasta enviada parcialmente)
- Falhas consecutivas no mesmo item

**Critérios de saída da Fase 4:**
- [ ] Dashboard toggle com `[D]` sem recarregar a árvore
- [ ] Sparkline renderiza corretamente para catálogos vazios e cheios
- [ ] Alertas calculados de forma lazy (não bloqueia a UI)
- [ ] Métricas atualizam após cada upload concluído

---

## Fase 5 — Funcionalidades Avançadas (`v2.0.0`)

**Meta:** operações em lote, busca inteligente, configuração inline.

### 5.1 · Seleção Inteligente por Padrão

```
[P] Selecionar por padrão...

> Todos os itens PENDING desta pasta
> Todos os itens com > 30 dias sem upload
> Todos os itens com > X GB
> Pastas que começam com S\d{2} (temporadas)
> Regex personalizado
```

### 5.2 · Upload em Fila

- Fila de múltiplos itens com ordem de prioridade
- Pausa/resume da fila
- Estimativa total de tempo para a fila completa
- Execução sequencial (não paralela — evita saturar upload NNTP)

### 5.3 · Visualização de NZB Inline

- Pressionar `[N]` num item `UPLOADED` abre painel com detalhes do NZB
- Mostra: servidor, grupos usados, data, artigos, integridade verificada
- Atalho para abrir o `.nzb` arquivado no diretório de NZBs

### 5.4 · Configuração de Perfil Inline

- `[C]` abre selector de perfil (`.env` disponíveis em `~/.config/upapasta/`)
- Troca o perfil ativo sem sair da TUI
- Indicador do perfil ativo na statusbar

### 5.5 · Modo Watch Integrado

- `[W]` ativa modo watch: TUI vira um monitor live
- Detecta novos arquivos na pasta raiz via polling
- Exibe notificação quando novo item aparece
- Opção de auto-upload de novos itens (com confirmação ou silencioso)

---

## Dependências por Fase

| Fase | Nova dependência | Justificativa |
|---|---|---|
| 1 | nenhuma | Só stdlib + código existente |
| 2 | `textual >= 0.60` | Framework TUI — entra em `[tui]` extra |
| 3 | nenhuma | Reutiliza `UpaPastaOrchestrator` |
| 4 | nenhuma | Cálculos puros sobre catálogo JSONL |
| 5 | nenhuma | Extensões das fases anteriores |

Instalação:
```bash
pip install upapasta[tui]   # instala textual automaticamente
pip install upapasta        # sem TUI, zero dependências externas (comportamento atual)
```

---

## Integração com `pyproject.toml`

```toml
[project.optional-dependencies]
tui = ["textual>=0.60"]

[project.scripts]
upapasta = "upapasta.main:main"
upapasta-tui = "upapasta.tui.app:main"   # atalho direto
```

---

## Critérios Globais de Qualidade

Aplicam os mesmos critérios do projeto principal:

```bash
ruff check upapasta/tui/ tests/tui/
mypy upapasta/tui/
pytest tests/tui/ --cov=upapasta/tui --cov-fail-under=85
```

- Todos os novos módulos com `from __future__ import annotations`
- Subprocessos de upload via `managed_popen` (nunca direto)
- TUI gracefully degradada se `textual` não instalado: `upapasta --tui` imprime instrução de instalação e sai com código 1
- Nenhuma saída de cor obrigatória: status legíveis mesmo sem ANSI (para `NO_COLOR=1`)

---

## Cronograma Estimado

| Fase | Versão alvo | Esforço estimado | Pré-requisito |
|---|---|---|---|
| 1 — Fundação de Dados | v1.2.0 | ~400 linhas | — |
| 2 — File Manager Core | v1.3.0 | ~800 linhas | Fase 1 |
| 3 — Integração Upload | v1.4.0 | ~600 linhas | Fase 2 |
| 4 — Dashboard | v1.5.0 | ~400 linhas | Fase 2 |
| 5 — Avançado | v2.0.0 | ~700 linhas | Fases 3+4 |

**Total estimado:** ~2.900 linhas de código novo + ~600 linhas de testes

---

## Estado Atual

- ✅ `UpaPastaOrchestrator` pronto para ser chamado programaticamente
- ✅ Catálogo JSONL estável e documentado
- ✅ `_progress.py` com lógica de progresso reutilizável
- 📍 Próximo passo: implementar Fase 1 (`catalog_index.py` + `fs_scanner.py`)
