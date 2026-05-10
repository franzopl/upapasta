# TODO — Upapasta: Roadmap Completo até v1.0.0

Versão em inglês disponível em [TODO.md](../../TODO.md).

> Última revisão: 2026-05-09 (Suporte Windows e 7z concluídos, reta final para v1.0.0)
> Princípio: corrigir primeiro, expandir depois. Estabilidade > novas features.

---

## ✅ Implementado (histórico)
...
- **Random group pool** (0.11.0)
- **`from_args` classmethod** (0.12.0) — ponto único de mapeamento args→orchestrator

---

## ✅ Fase 1 — Estabilidade — CONCLUÍDA

**Meta: CI verde, cobertura básica de segurança e limpeza. Sem novas features.**

---

## ✅ Fase 2 — Robustez & UX — CONCLUÍDA

**Meta: pipeline resiliente a falhas reais; visibilidade clara para o usuário.**

---

## 🟢 Fase 3 — Features Estratégicas (v0.21.x → v1.0.0)

**Meta: diferenciais competitivos; ferramenta autoexplicativa; suporte multiplataforma.**

### ~~3.1 · Múltiplas entradas posicionais: `upapasta a b c`~~ ✅ Concluído (commit 2b1be9a)

### ~~3.2 · Compressor alternativo: `--7z` e `--compress` (v0.30.0)~~ ✅ Concluído
- Suporte a volumes 7z (.7z.001), senhas (-mhe=on) e UI de progresso ao vivo
- CLI simplificada: flags explícitas `--rar`, `--7z` e genérica `--compress`

### ~~3.3 · Webhooks nativos: Discord/Telegram/Slack via `WEBHOOK_URL`~~ ✅ Concluído

### ~~3.4 · Integração TMDb: NFO enriquecido (v0.31.0)~~ ✅ Concluído
- Busca automática de metadados; heurística estrita; log de sugestões
- Novo utilitário: `upapasta --tmdb-search "termo"`

### ~~3.5 · Metadados enriquecidos no NZB (v0.31.0)~~ ✅ Concluído
- Injeção de title, poster, imdbid, genres, tagline no NZB <head> (Newznab standard)

### 3.6 · Template de NFO customizável: `--nfo-template <arquivo>` `Média · Médio esforço`
- Suporte a arquivos de texto customizados com placeholders: `{{title}}`, `{{synopsis}}`, `{{size}}`, `{{files}}`
- Permite que usuários desenhem seu próprio estilo de NFO

### 3.17 · Sistema de Plugins: Hooks em Python `Média · Alto esforço`
- Suporte nativo a lógica pós-upload via scripts `.py` em `~/.config/upapasta/hooks/`
- Padronização do objeto de metadados passado para os hooks

### ~~3.7 · `upapasta --stats` (histórico agregado)~~ ✅ Concluído

### ~~3.9 · `--dry-run --verbose` imprime argv completo dos subprocessos~~ ✅ Concluído

### ~~3.10 · Suporte Windows nativo testado (CI matrix)~~ ✅ Concluído (0.28.0)

### ~~3.11 · Separar `profiles.py` de `config.py`~~ ✅ Concluído

### ~~3.12 · `mypy --strict` no CI~~ ✅ Concluído

### ~~3.13 · Cobertura de testes ≥ 90% nos módulos core~~ ✅ Concluído

### ~~3.14 · Documentação completa (man page, FAQ, troubleshooting)~~ ✅ Concluído

### ~~3.15 · Publicação no PyPI com workflow automatizado~~ ✅ Concluído

### 3.8 · Modo interativo TUI (`--interactive`) `Baixa · Alto esforço`
- **Movido para o roadmap pós-v1.0.0**
- Menu interativo para histórico e disparo simplificado de uploads

### 3.16 · Migrar para Python 3.10+ no `requires-python` (pós-v1.0) `Baixa · Baixo esforço`
- Permite `match/case`, `tomllib`
- Somente após v1.0.0 stable

---

## 🏁 Critérios de v1.0.0

- [x] Todas as Fases 1 e 2 concluídas ✅
- [x] CI verde (pytest + mypy + ruff) ✅
- [x] Cobertura ≥ 90% nos módulos core ✅
- [ ] **F3.6** e **F3.17** implementados
- [ ] **Polimento Final**: Revisão 100% de Docs e testes de casos de borda
- [x] PyPI publicado ✅
- [x] Suporte Multiplataforma (Linux/macOS/Windows) ✅

---

## 📋 Resumo de Prioridades

| Fase | Versão | Foco | Itens-chave |
|-------|---------|-------|-----------|
| 1-2 | v0.25.0 | Core | Estabilidade, i18n, Processos, Validação |
| 3 | v0.31.0 | Features | TMDb, 7z, Webhooks, Windows |
| Final | v1.0.0 | Packaging | Templates NFO, Hooks Python, 100% QA |

**Reta final para v1.0.0** (em ordem):
1. **F3.6** → Template de NFO customizável
2. **F3.17** → Sistema de Plugins (Hooks em Python)
3. **Validação** → Foco 100% em Documentação e Testes
