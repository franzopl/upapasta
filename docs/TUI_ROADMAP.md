# TUI Roadmap — UpaPasta File Manager

> Decisão arquitetural: **TUI via `textual`** (não Web UI).
> Justificativa: uso primário é homelab headless via SSH; TUI funciona nativo sem servidor, sem porta aberta, integrado ao workflow CLI existente.
> Instalação opcional: `pip install upapasta[tui]` — não quebra a regra stdlib-only para usuários que não querem a TUI.

> **Documento vivo.** Este roadmap é a fonte canônica do trabalho na TUI. Atualize-o ao concluir itens (marque `[x]`), ao descobrir bugs (adicione em "Correções"), e ao decidir novas features.
> Última revisão: 2026-05-16 (auditoria completa do código em `dev`).

---

## 1. Visão Geral

O modo TUI transforma o UpaPasta de "ferramenta de upload" em **gerenciador visual de conteúdo para Usenet**. O usuário navega pelo filesystem e vê instantaneamente o que já foi enviado, o que está pendente e o que falhou — sem precisar lembrar flags ou consultar o catálogo JSONL manualmente.

- **Entry points:** `upapasta --tui [--tui-root CAMINHO]` ou comando standalone `upapasta-tui [caminho]`
- **Foco do produto:** conteúdo de mídia (filmes, séries, documentários) e cursos em pasta.
- **Stack:** `textual >= 0.60` (extra `[tui]`), sub-package `upapasta/tui/`, lê `history.jsonl`, dispara upload via subprocess `upapasta`.

---

## 2. Estado Atual (auditoria 2026-05-16)

A TUI Textual está **funcional de ponta a ponta**: navegar → selecionar → confirmar → upload → ver NZB. As Fases 1–5 do plano original foram majoritariamente implementadas. 320 testes passando (`tests/tui/`), `ruff` + `mypy --strict` limpos.

### 2.1 · Estrutura de módulos implementada

```
upapasta/tui/
├── app.py                      # App principal: layout, bindings, roteamento de telas
├── catalog_index.py            # Índice em memória do history.jsonl + NZBs externos
├── fs_scanner.py               # Walk do filesystem, cruza com catálogo → FileNode
├── external_nzb.py             # Índice de .nzb externos (EXTERNAL_NZB_DIR)
├── status.py                   # Enums UploadStatus + IndexerStatus (ícone/cor/label)
├── widgets/
│   ├── file_tree.py            # Árvore com status, lazy load, seleção, busca indexador
│   ├── dashboard.py            # Painel lateral de estatísticas + sparkline
│   ├── upload_panel.py         # Painel de progresso de upload (subprocess por item)
│   └── status_bar.py           # Barra inferior com detalhe do item em foco
└── screens/
    ├── confirm.py              # Modal de confirmação pré-upload
    ├── upload_progress.py      # Tela cheia de progresso de upload
    ├── pattern_select.py       # Modal de seleção inteligente por padrão
    └── nzb_viewer.py           # Visualizador inline de NZB pós-upload
```

> Nota: o wizard `upapasta --config` (`tui_config.py` / `tui_widgets.py`, ~2.000 linhas) é uma TUI **separada baseada em curses**, não em Textual. Ver item de unificação na Fase 8.

### 2.2 · Funcionalidades concluídas

| Área | Funcionalidade | Estado |
|---|---|---|
| Navegação | Árvore de arquivos com lazy loading de subdiretórios | ✅ |
| Navegação | Ícones + cores de status por item (`✅ 🔶 ❌ ⏳ 🌐`) | ✅ |
| Navegação | Busca por nome (`/`) com highlight do match | ✅ |
| Navegação | Filtros por status (`0` todos / `1` pendentes / `2` enviados / `3` parciais) | ✅ |
| Navegação | Barra de status inferior com detalhe do item em foco | ✅ |
| Seleção | Multi-seleção (`Space`), sel. todos (`a`), inverter (`i`), limpar (`Ctrl+D`) | ✅ |
| Seleção | Seleção inteligente por padrão (`p`): status, tamanho, temporada, regex | ✅ |
| Seleção | Preview ao vivo de quantos itens casam o padrão | ✅ |
| Upload | Fluxo confirmar → progresso → resumo, sem sair da TUI | ✅ |
| Upload | Modal de confirmação com opções `--obfuscate` / `--rar` / `--par-profile` | ✅ |
| Upload | Estimativa de tamanho PAR2 no modal de confirmação | ✅ |
| Upload | Progresso ao vivo: fase, %, velocidade, ETA, spinner, elapsed | ✅ |
| Upload | Fila sequencial multi-item com pausa/resume (`p`) e ETA da fila | ✅ |
| Upload | Cancelamento (`Esc`) e resumo final com contagem de sucesso/falha | ✅ |
| Dashboard | Painel lateral (`d`): enviados, pendentes, parciais, média/item | ✅ |
| Dashboard | Sparkline de atividade com timeframe ajustável (`[` / `]`) | ✅ |
| Dashboard | Top grupos, top categorias, alertas de itens parciais | ✅ |
| Indexador | Busca Newznab de itens visíveis (`x`) com badge de status | ✅ |
| Indexador | Download de NZB encontrado no indexador (`n`) | ✅ |
| NZB | Visualizador inline pós-upload: metadados + tabela de arquivos | ✅ |
| Outros | NZBs externos (`EXTERNAL_NZB_DIR`) reconhecidos como status `🌐` | ✅ |
| Outros | Confirmação de saída (`q`) quando há itens selecionados | ✅ |
| Outros | Degradação graciosa se `textual` ausente | ✅ |

---

## 3. Correções Necessárias

Itens identificados na auditoria do código. Prioridade: **P0** = bug que afeta correção/dados, **P1** = bug funcional ou violação de convenção, **P2** = polimento.

### P0 — Correção / Integridade de dados

- [ ] **C1 · Matching de catálogo por nome, não por path** (`fs_scanner.py`)
  O catálogo só guarda `nome_original` (basename). Dois itens de mesmo nome em pastas diferentes são tratados como idênticos → falso "Enviado". Mitigação possível: registrar path completo (ou hash) no catálogo e cruzar por path; ou exibir aviso de ambiguidade quando há colisão de nome.

- [ ] **C2 · `subprocess.Popen` direto em vez de `managed_popen`** (`upload_panel.py:_run_one`)
  Viola a convenção #1 do projeto e o próprio critério deste roadmap. Sem escalada `SIGTERM → SIGKILL`: se o `upapasta` filho ignorar o `terminate()`, fica zumbi ao cancelar/sair. Migrar para `managed_popen` de `_process.py` (ou replicar a escalada com timeout).

### P1 — Bug funcional / convenção

- [ ] **C3 · Mutação de `self.BINDINGS` (atributo de classe)** (`upload_progress.py:on_upload_panel_finished`)
  `self.BINDINGS.append(...)` muta a lista **compartilhada da classe**. A cada upload concluído, bindings duplicados se acumulam permanentemente no processo. Usar `_bindings` de instância, `check_action`/`refresh_bindings`, ou um flag para só adicionar uma vez.

- [ ] **C4 · Busca de indexador ignora pastas recolhidas** (`file_tree.py:_collect_visible_file_nodes`)
  `start_indexer_search` só percorre `TreeNode`s já carregados (pastas expandidas). Itens em pastas recolhidas são silenciosamente ignorados. Ou escanear o filesystem direto, ou avisar que só itens visíveis foram buscados.

- [ ] **C5 · `--porcelain` aplicado em dobro** (`confirm.py:build_upload_cmd` + `upload_panel.py:_run_one`)
  O comando recebe a flag `--porcelain` *e* o env `UPAPASTA_PORCELAIN=1`. Redundante (não quebra). Escolher um mecanismo só — preferir o env, que não polui a linha de comando exibida no log.

- [ ] **C6 · TUI não usa i18n** (todos os módulos `tui/`)
  Zero uso de `from .i18n import _`. Strings hardcoded em português. O resto do projeto é internacionalizado via gettext. Decidir: (a) envolver strings da TUI em `_()`, ou (b) documentar explicitamente que a TUI é PT-only por ora.

### P2 — Polimento

- [ ] **C7 · Estimativa de tamanho do NZB imprecisa** (`nzb_viewer.py`)
  Usa `_DEFAULT_ARTICLE_SIZE = 750_000` fixo × nº de segmentos. Cada `<segment>` do NZB tem o atributo real `bytes` — somar os valores reais dá o tamanho exato.

- [ ] **C8 · `compute_fs_stats` escaneia só o top-level** (`dashboard.py`)
  Pendências/parciais em subpastas não entram na contagem do dashboard. Avaliar walk recursivo (com cache) ou deixar claro que a métrica é só da raiz.

- [ ] **C9 · `reload()` perde a posição do cursor** (`file_tree.py:_reload_root`)
  Após upload, a árvore é reconstruída; re-expande os paths mas o cursor volta ao topo. Salvar e restaurar o path do nó sob o cursor.

- [ ] **C10 · Preview de regex conta só nós carregados** (`app.py:_open_pattern_select`)
  `visible_names` vem de `query("TreeNode")` — só pastas expandidas. O preview "N de M itens casariam" pode enganar. Coletar nomes via scan do filesystem.

---

## 4. Roadmap de Funcionalidades

Organizado por fase. Cada fase é coesa e pode ser entregue de forma independente. Versões-alvo são sugestões.

### Fase 6 — Robustez e Confiança (`v0.35.x`)

**Meta:** corrigir os itens da seção 3 e fechar lacunas de confiabilidade. **Pré-requisito de qualquer feature nova.**

- [ ] Resolver C1–C10.
- [ ] **Tela de ajuda (`?`)** — modal com todas as teclas agrupadas por contexto. O layout original previa `[?]Ajuda` no cabeçalho.
- [ ] **Tratamento de erro no scan** — pasta raiz inacessível, symlink quebrado, permissão negada: mensagem clara em vez de stack trace.
- [ ] **Indicador de carregamento** — árvores grandes ou catálogos grandes devem mostrar "carregando…" em vez de travar.
- [ ] **Teste de fumaça do `upload_panel`** — hoje os screens são testados, mas a lógica de subprocess/parsing tem pouca cobertura direta.

### Fase 7 — Upload Avançado (`v0.36.x`)

**Meta:** dar à TUI paridade de opções com a CLI, sem precisar editar comando.

- [ ] **Modal de confirmação completo** — adicionar ao `confirm.py`: `--7z`, `--password` (com geração aleatória), `--each`, `--season`, escolha de grupo/pool, `--compress`. Hoje só há 3 opções.
- [ ] **Seleção de perfil inline (`c`)** — selector dos `.env` em `~/.config/upapasta/`; troca o perfil ativo sem sair; indicador do perfil na status bar. (Fase 5.4 original, não feita.)
- [ ] **Presets de upload** — salvar combinações de opções nomeadas ("Filme 4K", "Curso", "Série stealth") e aplicar com um atalho.
- [ ] **Re-upload / retry de falhas** — selecionar itens `FAILED`/`PARTIAL` e reprocessar direto.
- [ ] **Dry-run visual** — botão no modal que mostra o que aconteceria (comando, tamanho PAR2, ETA) sem enviar.

### Fase 8 — Experiência e Visual (`v0.37.x`)

**Meta:** "visualmente agradável e fácil de mexer" — polir a percepção da ferramenta.

- [ ] **Layout responsivo** — dashboard como overlay ou painel colapsável em terminais estreitos; árvore nunca deve quebrar. Hoje o dashboard é fixo em 46 colunas.
- [ ] **Temas** — dark/light + 1–2 temas de destaque, alternáveis em runtime. Textual suporta `theme` nativamente.
- [ ] **Command palette (`Ctrl+P`)** — busca fuzzy de todas as ações. Textual já oferece a base.
- [ ] **Painel de detalhes do item** — ao focar um arquivo: mediainfo (resolução, codec, duração), preview de NFO existente, miniatura de poster TMDb se disponível.
- [ ] **Dashboard ao vivo durante upload** — métricas e sparkline atualizando enquanto a fila roda, não só ao fim.
- [ ] **Unificar o wizard de config** — portar `tui_config.py` (curses) para uma `screens/config.py` em Textual. Elimina a dependência de curses e a inconsistência de dois frameworks de TUI.
- [ ] **Notificações persistentes** — log de notificações acessível (hoje os toasts somem em 2–5 s).

### Fase 9 — Operação Contínua (`v0.38.x`)

**Meta:** transformar a TUI em painel de operação para homelab/SSH.

- [ ] **Modo Watch integrado (`w`)** — TUI vira monitor live; detecta novos itens na raiz via polling; notifica; opção de auto-upload com/sem confirmação. (Fase 5.5 original.)
- [ ] **Upload em background / daemon** — enfileirar e fechar a TUI; processo consome a fila; ao reabrir, o estado é refletido. "Fire and forget" para SSH. (Fase 5.6 original.)
- [ ] **Histórico de sessão** — aba/tela com os uploads desta sessão, com link para log e NZB de cada um.
- [ ] **Verificação de NZB existente** — re-checar integridade de uploads antigos (artigos ainda disponíveis no servidor) direto da árvore.
- [ ] **Reordenar a fila** — arrastar/mover itens na fila antes/durante o processamento.

### Fase 10 — Inteligência (`v0.39.x+`)

**Meta:** features que economizam decisões do usuário. Backlog — priorizar conforme uso real.

- [ ] **ETA preditivo** — estimar tempo de upload a partir da velocidade histórica do catálogo, antes de iniciar.
- [ ] **Detecção de duplicatas** — avisar quando um item a enviar parece já estar no catálogo (match aproximado de nome/tamanho).
- [ ] **Sugestão de categoria/TMDb** — pré-preencher metadados no modal de confirmação.
- [ ] **Visão por coleção** — agrupar séries/temporadas logicamente, não só pela árvore de diretórios.
- [ ] **Exportar relatórios** — do dashboard para CSV/JSON.

---

## 5. Princípios de Design

Para manter a TUI **fácil de mexer, visualmente agradável e útil**, todo trabalho novo deve seguir:

1. **Um widget, uma responsabilidade.** Lógica de dados (`catalog_index`, `fs_scanner`) fica fora dos widgets. Widgets só renderizam e emitem mensagens.
2. **Comunicação por mensagens.** Threads (`@work(thread=True)`) nunca tocam a UI direto — sempre via `post_message` / `call_from_thread`. Já é o padrão; manter.
3. **CSS junto do widget.** `DEFAULT_CSS` no próprio widget; só o layout global fica no `App.CSS`.
4. **Estilo só por tokens de tema.** Usar `$accent`, `$surface`, `$warning`, etc. — nunca cores literais. Garante que temas (Fase 8) funcionem.
5. **Toda ação tem binding visível.** Se uma ação existe, aparece no `Footer` ou na tela de ajuda. Sem funcionalidade escondida.
6. **Degradar com clareza.** Sem indexador, sem `textual`, sem permissão: mensagem acionável, nunca crash.
7. **Subprocessos via `managed_popen`.** Sem exceção (ver C2).
8. **Teste por comportamento.** Usar `App.run_test()` + `Pilot`; testar o que o usuário vê, não internals.
9. **`from __future__ import annotations`** em todo módulo novo; `ruff` + `mypy --strict` limpos antes de commit.

---

## 6. Critérios de Qualidade

```bash
ruff check upapasta/tui/ tests/tui/
ruff format --check upapasta/tui/ tests/tui/
mypy upapasta/tui/
pytest tests/tui/ -q
```

- Todo módulo novo coberto por testes; nenhuma regressão na suíte de 320 testes existente.
- TUI gracefully degradada se `textual` ausente: instrução de instalação + exit 1.
- Status legíveis sem cor (ícones distintos), respeitando `NO_COLOR`.

---

## 7. Ordem de Trabalho Sugerida

1. **Fase 6 primeiro** — sem a base de confiabilidade, features novas herdam bugs (C1 e C2 em especial).
2. **Fase 7** — maior ganho percebido: a TUI passa a substituir a CLI no dia a dia.
3. **Fase 8** — polimento visual; faz a ferramenta "parecer pronta".
4. **Fases 9–10** — conforme demanda real de uso em homelab.

> Ao concluir um item, marque `[x]` aqui e registre no `CHANGELOG.md`. Ao descobrir um bug novo, adicione na seção 3 com prioridade.
