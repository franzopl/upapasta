# TODO — Upapasta: Roadmap Completo até v1.0.0

Versão em inglês disponível em [TODO.md](../../TODO.md).

> Última revisão: 2026-05-09 (Suporte Windows e 7z concluídos, v0.29.0 ready)
> Princípio: corrigir primeiro, expandir depois. Estabilidade > novas features.

---

## ✅ Implementado (histórico)

- **render_template centralizado** — `config.py` (eliminada duplicação entre `nzb.py` e `orchestrator.py`)
- **`--profile <nome>`** — perfis nomeados em `~/.config/upapasta/<nome>.env`
- **`--test-connection`** — handshake NNTP (CONNECT/LOGIN/QUIT)
- **`--config`** — reconfiguração com preservação de valores
- **`--rar` opt-in** (0.18.0) — inversão de `--skip-rar`; `--password` presume `--rar`
- **Docs JSONL sincronizadas** (0.18.x) — README, DOCS, CHANGELOG corrigidos; F1.1 ✅
- **`test_catalog.py` migrado para JSONL** (0.18.x) — 4 testes corrigidos (`_history_path`); F1.2 ✅
- **`fix_nzb_subjects` corrigido** (0.18.x) — matching robusto sem aspas; F1.3 ✅
- **`test_fallback_to_rename` corrigido** (0.18.x) — mock atualizado; F1.4 ✅
- **`--each` / `--season` / `--watch`** — modos de processamento múltiplo
- **Upload sem staging `/tmp`** (0.9.0) — paths diretos via `cwd=input_path`
- **`managed_popen`** (0.9.0) — SIGTERM→SIGKILL para todos os subprocessos externos
- **Ofuscação atômica via hardlink + try/finally** (0.14.x–0.15.x)
- **Catálogo JSONL + arquivamento NZB via hardlink** (0.12.0)
- **Random group pool** (0.11.0)
- **`from_args` classmethod** (0.12.0) — ponto único de mapeamento args→orchestrator

---

## 🟢 Fase 3 — Features Estratégicas (v0.21.x → v1.0.0)

**Meta: features diferenciadoras; ferramenta autoexplicativa; suporte cross-platform.**

### ~~3.1 · Múltiplas entradas posicionais: `upapasta a b c`~~ ✅ Concluído (commit 2b1be9a)

### ~~3.2 · Compressor alternativo: `--7z` e `--compress` (v0.30.0)~~ ✅ Concluído
- Suporte a volumes 7z (.7z.001), senhas (-mhe=on) e UI de progresso ao vivo
- CLI simplificada: flags explícitas `--rar`, `--7z` e genérica `--compress`

### ~~3.3 · Webhooks nativos: Discord/Telegram/Slack via `WEBHOOK_URL`~~ ✅ Concluído
- `_webhook.py`: `send_webhook()` + `_build_payload()` com detecção automática Discord/Slack/Telegram/genérico
- `WEBHOOK_URL` no `.env.example`; chamado em `_pipeline.py` após `run_post_upload_hook`
- 10 testes em `test_phase3.py`

### 3.4 · TMDb integration: enriquece NFO com sinopse/poster URL/IMDB ID `Alta · Alto esforço` ← depende de 2.12
- Detecta filme/série, faz lookup, enriquece NFO
- Flag opt-in `--tmdb`

### 3.5 · NZB com `<meta>` enriquecido (title/poster/category) `Média · Médio esforço` ← depende de 3.4
- Injetar `<meta type="title">`, `<meta type="poster">`, `<meta type="category">`
- Teste XML

### 3.6 · Template de NFO customizável: `--nfo-template <arquivo>` `Média · Médio esforço` ← depende de 2.12
- Placeholders: `{title}`, `{size}`, `{files}`, `{video_info}`, `{tmdb}`
- Fallback automático para geração automática se template não existir

### ~~3.7 · `upapasta --stats` (histórico agregado)~~ ✅ Concluído
- Lê `history.jsonl`; imprime totais, top categorias, GB/mês (últimos 6), grupo mais usado, duração média

### 3.8 · Modo interativo TUI (`--interactive`) `Baixa · Alto esforço` ← depende de 3.7
- `curses` da stdlib; menu de upload + histórico

### ~~3.9 · `--dry-run --verbose` imprime argv completo dos subprocessos~~ ✅ Concluído
- `make_parity` agora imprime o comando completo de `parpar`/`par2` quando `dry_run=True`

### ~~3.10 · Suporte Windows nativo testado (CI matrix)~~ ✅ Concluído (0.28.0)
- GitHub Actions roda em Windows; paths normalizados; sem regressões

### ~~3.11 · Separar `profiles.py` de `config.py`~~ ✅ Concluído

### ~~3.12 · `mypy --strict` no CI~~ ✅ Concluído

### ~~3.13 · Cobertura de testes ≥ 90% nos módulos core~~ ✅ Concluído

### ~~3.14 · Documentação completa (man page, FAQ, troubleshooting)~~ ✅ Concluído
- Manual atualizado para refletir novos fluxos de ofuscação e 7z.

### ~~3.15 · Publicação no PyPI com workflow automatizado~~ ✅ Concluído

### 3.16 · Migrar para Python 3.10+ no `requires-python` (pós-v1.0) `Baixa · Baixo esforço`

### 3.17 · Plugin system: hooks Python em `~/.config/upapasta/hooks/<name>.py` `Baixa · Alto esforço`

---

## 🏁 Critérios de v1.0.0

- [x] Todas as Fases 1 e 2 concluídas ✅
- [x] CI verde (pytest + mypy + ruff) via GitHub Actions ✅
- [x] Cobertura ≥ 90% nos módulos core ✅
- [x] `--resume` funcional ✅
- [x] Múltiplos servidores NNTP ✅
- [x] Documentação completa e atualizada ✅
- [x] PyPI publicado ✅
- [x] Zero dependências Python externas ✅
- [x] Suporte Multiplataforma (Linux/macOS/Windows) ✅
- [x] Suporte 100% Open Source (7z + parpar) ✅

---

## 📋 Resumo de Prioridades

**Próximos passos imediatos** (em ordem):
1. **F3.6** → Template de NFO customizável: `--nfo-template <arquivo>` `Média · Médio esforço`
2. **F3.8** → Modo interativo TUI (`--interactive`) `Baixa · Alto esforço`
3. **3.17** → Sistema de Plugins: hooks Python `Baixa · Alto esforço`
