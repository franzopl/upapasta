# TODO — Upapasta: Melhorias e Problemas a Resolver

> Guia de trabalho futuro. Itens ordenados por prioridade dentro de cada categoria.
> Última revisão: 2026-04-23

## ✅ Implementado Recentemente

- **--config flag** (2026-04-23): Flag para reconfiguração de credenciais com preservação de valores existentes
- **Melhorias de NFO** (2026-04-22): Geração aprimorada de NFOs de pastas, remoção de lógica de produtor
- **Refactor NFO** (2026-04-21): Removida lógica duplicada de produtor e [DESCONHECIDO] do título

---

## 🔴 Bugs / Problemas Imediatos

> *(Nenhum bug crítico aberto no momento)*

---

## 🟡 Melhorias de Qualidade e Robustez

### 1. Cobertura de testes — cenários ainda sem cobertura
- Testes para `managed_popen`: verificar SIGTERM/SIGKILL em subprocessos, cleanup em KeyboardInterrupt, comportamento em processo já finalizado.
- Geração de NFO para pastas com vídeos multi-track e legendas embutidas (requer ffprobe mock).
- Testes de integração para os 5 falhos pré-existentes em `test_upfolder.py` / obfuscation (NFO single-file).

### 2. Dívida técnica: template parsing duplicado
- `main.py` e `upfolder.py` resolvem `{filename}`, `{title}` etc. de forma independente.
- **Fix:** centralizar em `render_template(template: str, **vars) -> str` em `config.py` ou novo `nzb.py`.

### 3. Sem verificação de tipo estática
- Nenhum uso de `mypy` ou `pyright`.
- **Proposta:** adicionar type hints em todas as funções públicas e rodar `mypy --strict` no CI.

---

## 🟢 Funcionalidades Novas

### 4. Suporte a `--resume` / upload parcial
- Viável porque não usamos pasta temporária (nyuu opera sobre paths diretos).
- **Proposta:** nyuu suporta `--input` para re-upload de artigos específicos. Implementar salvamento do estado de upload (arquivo `.upapasta-state`) e resume automático ao detectar estado salvo.

### 5. Suporte a múltiplos servidores Usenet
- Atualmente apenas um servidor NNTP é configurado.
- **Proposta:** suporte a lista de servidores com prioridade (primary + fallback), lido do `.env` como `NNTP_HOST_2`, `NNTP_PASS_2` etc., ou via JSON simples.

### 6. Geração de NFO melhorada
- FFprobe pode ser chamado múltiplas vezes por vídeo.
- **Fix:** uma única chamada com `-show_streams -show_format`.
- **Melhoria:** detectar áudio multi-track, legendas embutidas e incluir no NFO.
- **Melhoria:** suporte a template de NFO customizável via `NFO_TEMPLATE` no `.env` (abordagem de templates externos).

### 7. Perfis de configuração nomeados ⭐ PRÓXIMO
- **Proposta:** `--profile <nome>` carrega `~/.config/upapasta/<nome>.env` para quem usa múltiplos provedores.
- **Nota:** `--config` permite reconfiguração, mas perfis distintos ainda não existem.

### 8. NZB com `<meta>` enriquecido
- **Proposta:** injetar `<meta type="title">`, `<meta type="poster">`, `<meta type="category">` baseado em heurísticas do nome / NFO.

### 9. Estimativa de tempo de upload
- Antes de iniciar, exibir tamanho total + conexões configuradas como ETA simples.

### 10. Suporte a entrada múltipla
- **Proposta:** `upapasta file1 file2 folder1` — processar em sequência (ou paralelo com `--jobs N`).

### 11. Suporte a `--watch <dir>`
- Monitorar diretório e fazer upload automático de novos arquivos/pastas.
- **Proposta:** modo daemon simples com polling via `inotify` (Linux) ou `watchdog`.

### 12. Suporte a compressão alternativa (7-zip)
- RAR5 requer licença para criar (binário `rar` pago em Linux).
- **Proposta:** `--compressor 7z`, gerando volumes `.7z.001` etc.

---

## 🔵 Dívida Técnica / Refactoring

### 13. `main.py` com ~1100 linhas é difícil de manter
- `UpaPastaOrchestrator` faz orquestração, resolução de caminhos, formatação de saída e lógica de negócio.
- **Proposta:** extrair responsabilidades em classes/módulos dedicados:
  - `PathResolver` — resolução de NZB/NFO output paths
  - `PipelineReporter` — output/progress formatting
  - `DependencyChecker` — verificação de binários externos

### 14. `config.py` mistura perfis PAR2 e defaults de configuração
- **Proposta:** mover constantes de perfil para `profiles.py` e manter `config.py` apenas para leitura de `.env`.

### 15. Suporte a Python 3.8 limita features modernas
- `match/case` (3.10), `tomllib` (3.11), `ExceptionGroup` (3.11) não podem ser usados.
- **Proposta:** avaliar elevar o mínimo para 3.10 (Ubuntu 22.04 LTS vem com 3.10 por padrão).

### 16. CI/CD ausente
- **Proposta mínima:**
  - `pytest` em push/PR
  - `mypy` para type checking
  - `ruff` para linting

---

## 🏁 Meta v1.0.0 — Critérios de Estabilidade

Para considerar o projeto estável e pronto para uso geral:

- [ ] Cobertura de testes > 90% (incluindo `managed_popen` e cenários de erro)
- [ ] CI/CD com GitHub Actions (pytest + mypy + ruff)
- [ ] `--resume` funcional para uploads interrompidos
- [ ] Retry de upload robusto com fallback configurável
- [ ] Documentação completa (README atualizado + `--help` detalhado)
- [ ] Zero dependências externas além de stdlib (manter atual)

---

## 📋 Referência Rápida — Por onde começar

| Prioridade | Item | Esforço |
|------------|------|---------|
| 1 | #2 render_template centralizado | Baixo |
| 2 | #1 Testes para managed_popen | Médio |
| 3 | #3 Type checking com mypy | Médio |
| 4 | #7 Perfis de configuração nomeados | Baixo |
| 5 | #16 CI/CD GitHub Actions (pytest + mypy + ruff) | Médio |
| 6 | #13 Refatorar main.py em módulos | Alto |
| 7 | #4 --resume / upload parcial | Alto |
| 8 | #6 NFO com ffprobe único + multi-track | Médio |

---

## 💡 Sugestões Adicionais (Identificadas em 2026-04-23)

### A. Validação de entrada antes do RAR
- **Problema:** Se o arquivo/pasta for muito grande ou inválido, só descobre após começar o RAR
- **Solução:** validação rápida de tamanho, permissões e estrutura antes de iniciar pipeline
- **Impacto:** melhor UX, menos re-execuções

### B. Mensagens de erro mais informativas
- **Problema:** Erros de subprocesso (RAR, PAR2, nyuu) às vezes são genéricos
- **Solução:** parsear stderr de cada binário e extrair mensagem específica
- **Exemplo:** `nyuu timeout` → "Servidor NNTP indisponível ou timeout de conexão (verifique credenciais)"

### C. Logging estruturado
- **Atual:** stdout + arquivo de log simples
- **Proposta:** adicionar timestamps e níveis (DEBUG, INFO, WARN, ERROR) ao log
- **Benefício:** rastreamento de problemas em produção + debugging mais fácil

### D. Retry com backoff exponencial
- **Atual:** retry simples em ny uu
- **Proposta:** exponential backoff com jitter para uploads de longa duração
- **Código:** já existe infraestrutura em `upfolder.py`, apenas refiná-la

### E. Teste de conectividade antes de upload
- **Proposta:** antes de RAR/PAR2, fazer handshake rápido com servidor NNTP
- **Ganho:** fail fast, economiza tempo se credenciais estão erradas

### F. Preview do tamanho final antes de começar
- **Proposta:** mostrar tamanho RAR estimado + tamanho total com PAR2 antes de `[Y/n]?`
- **UX:** melhor previsibilidade antes de committed ao processo

### G. Suporte a .nfo customizado via template
- **Atual:** geração automática baseada em metadados
- **Proposta:** permitir `--nfo-template <arquivo>` com placeholders: `{title}`, `{size}`, `{files}`, `{video_info}`, etc.
- **Compatibilidade:** fallback para geração automática se template não existir
