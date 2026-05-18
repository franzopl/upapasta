# TODO: UpaPasta Lean Roadmap 🚀

O objetivo atual é transformar o **UpaPasta** em um orquestrador de UX e metadados, delegando a computação pesada (Upload, PAR2, Ofuscação, Watch) para o **Pesto** (engine em Rust).

---

## 🛠️ Fase 1: Refatoração Lean (Delegação para o Pesto)
*Substituir implementações complexas em Python por chamadas nativas ao Pesto.*

- [ ] **Delegação de Ofuscação:**
    - [ ] Deprecar a criação manual de diretórios e hardlinks em `orchestrator.py`.
    - [ ] Implementar passagem automática de `--obfuscate=full` para o Pesto.
- [ ] **Delegação de Compressão:**
    - [ ] Usar `--compress` e `--password` nativos do Pesto para casos sem volumes divididos.
- [ ] **Watch Mode Nativo:**
    - [ ] Substituir o `watch.py` por uma chamada ao `pesto --watch`.
    - [ ] Capturar eventos JSON do watch mode do Pesto para exibir na TUI.
- [ ] **Batch Mode Nativo:**
    - [ ] Usar `--each` e `--season` do Pesto para processar diretórios, eliminando loops manuais em Python.
    - [ ] Implementar suporte a `--jobs` para paralelismo real via Pesto.
- [ ] **PAR2 Nativo:**
    - [ ] Desativar `makepar.py` por padrão quando o Pesto for detectado (usar `--par2` do Pesto).

---

## 🧠 Fase 2: Excelência em Metadados e UX
*Focar no que torna o UpaPasta único e que o Pesto não faz.*

- [ ] **Enriquecimento de NFO:**
    - [ ] Criar lógica para "beautify" o NFO básico do Pesto.
    - [ ] Integrar dados do TMDb (sinopse, poster) nos templates de NFO de forma pós-upload.
- [ ] **Busca Preventiva em Indexadores:**
    - [ ] Melhorar a verificação de duplicatas via Newznab/Prowlarr *antes* de iniciar o upload.
- [ ] **TUI 2.0 (Event-Driven):**
    - [ ] Refinar o monitoramento de processos Pesto via stream de JSON.
    - [ ] Mostrar estatísticas agregadas de múltiplos jobs do Pesto na interface.
- [ ] **Wizard de Configuração:**
    - [ ] Adicionar suporte a múltiplos perfis NNTP que o Pesto suporta (`[[servers]]`).

---

## 📦 Fase 3: Infraestrutura e Distribuição
- [ ] **Mover Nyuu/ParPar para Legacy:**
    - [ ] Criar módulo `legacy_tools.py` para isolar o suporte ao Nyuu.
    - [ ] Definir Pesto como o motor padrão e recomendado.
- [ ] **Bundling:**
    - [ ] Incluir binários do Pesto na pasta `bin/` nas distribuições portáteis.
- [ ] **Documentação:**
    - [ ] Atualizar o README para focar no modelo "UpaPasta (UI) + Pesto (Engine)".

---

## 🧹 Limpeza de Código (Deprecação)
- [ ] Marcar `watch.py` como obsoleto.
- [ ] Simplificar `upfolder.py` (remover redundâncias de NFO e verificações STAT manuais).
- [ ] Reduzir complexidade do `orchestrator.py` eliminando gestão de arquivos temporários.

---
*Atualizado em: Maio de 2026*
