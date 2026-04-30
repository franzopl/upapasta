# CLAUDE.md

Regras de Economia de Tokens (sempre siga primeiro)

- Para qualquer tarefa de exploracao, leitura, busca, grep ou mapeamento no codigo, use preferencialmente o subagent Explore (model Haiku).
- Nunca use subagents com modelo Opus ou Sonnet para tarefas simples de leitura ou exploracao.
- Mantenha respostas de subagents curtas, objetivas e em bullet points.
- Evite paralelismo excessivo de subagents. Use apenas quando realmente necessario.
- Seja extremamente especifico nos prompts.
- Use clear ou abra uma nova sessao ao mudar de tarefa grande.

Project Overview

UpaPasta e uma ferramenta CLI em Python que automatiza o upload completo para Usenet com o minimo de configuracao necessaria.

1. (Opcional) Cria arquivos RAR a partir de pastas
2. Gera arquivos PAR2 de paridade (parpar por padrao; preserva estrutura de pastas)
3. Faz upload via nyuu (sem copia temporaria — paths diretos)
4. Gera arquivos NZB e NFO
5. Limpa arquivos temporarios

Filosofia: menos flags, mais autonomia. Defaults inteligentes, wizard de primeira execucao, sem dependencias pesadas.

Fluxo Recomendado 2026

Para pastas com subpastas, o fluxo moderno descarta o RAR e confia no parpar
para preservar a hierarquia dentro dos .par2 (campo filepath-format=common,
default). SABnzbd/NZBGet recentes reconstroem a arvore no download.

  upapasta Pasta/ --skip-rar --backend parpar --obfuscate \
      --filepath-format common --par-profile safe

- RAR-com-senha: na pratica overkill em 2026. Ofuscacao forte de subject +
  nomes + PAR2 ja protege contra scans automaticos de copyright. Use senha
  apenas se realmente precisar do sinal social ou para downloaders legados.
- SABnzbd: desativar "Recursive Unpacking" para preservar .zip internos
  (caso contrario o cliente os extrai recursivamente, quebrando hash). Revisar
  "Unwanted Extensions" — usar --rename-extensionless quando ha arquivos sem
  extensao (impede o SAB de adicionar .txt).

Development Setup

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

Binarios externos necessarios: rar, nyuu, parpar (ou par2).
Opcionais: ffmpeg, ffprobe, mediainfo (para geracao de NFO).

Core Modules

- main.py — Ponto de entrada (~150 linhas). Parse de args, modos --each/--watch, instancia UpaPastaOrchestrator.
- cli.py — Argparse, _USAGE_SHORT, _DESCRIPTION, _EPILOG, validacao de flags incompativeis, check_dependencies.
- orchestrator.py — UpaPastaOrchestrator (workflow completo) + UpaPastaSession (context manager de cleanup) + helpers normalize_extensionless / revert_extensionless.
- watch.py — Modo daemon --watch (polling com janela estavel).
- catalog.py — SQLite history.db (registro de uploads, deteccao de categoria, hooks pos-upload).
- makerar.py — RAR5 com progresso ao vivo. Retorna codigos inteiros.
- makepar.py — PAR2 com perfis fast/balanced/safe e backends parpar/par2. make_parity aceita filepath_format e parpar_extra_args. obfuscate_and_par renomeia + paridade com rollback garantido (try/finally que cobre KeyboardInterrupt). Slice dinamico baseado em ARTICLE_SIZE.
- upfolder.py — Upload via nyuu sem staging em /tmp; paths relativos preservam subpastas. Retry automatico.
- nzb.py — Resolve nome do .nzb, trata conflitos (rename/overwrite/fail), injeta senha quando aplicavel.
- nfo.py — Geracao de NFO via mediainfo/ffprobe; tree para pastas, metadados de video para arquivos unicos.
- config.py — PROFILES dict (perfis PAR2), REQUIRED_CRED_KEYS, prompt_for_credentials, load_env_file, render_template.
- ui.py — PhaseBar (barra de 4 fases), _TeeStream (logging dual console+arquivo, strip ANSI no arquivo), setup_logging / teardown_session_log.
- resources.py — calculate_optimal_resources (threads e memoria conforme tamanho da fonte e CPUs disponiveis).
- _process.py — managed_popen: context manager obrigatorio para todos os subprocessos externos. SIGTERM → espera → SIGKILL em qualquer situacao (excecao, KeyboardInterrupt).

Key Conventions

OBRIGATORIO: Todo binario externo (rar, nyuu, parpar, par2) deve ser executado exclusivamente via managed_popen de _process.py. Nunca use subprocess.Popen ou subprocess.run diretamente para binarios externos.

OBRIGATORIO: Toda sessao de orquestracao deve usar UpaPastaSession como context manager para garantir cleanup de recursos.

- Funcoes principais retornam codigos inteiros: 0 = sucesso, erros especificos por modulo:
  - makerar: 1
  - makepar: 2 (entrada invalida), 3 (PAR2 ja existe), 4 (binario nao encontrado), 5 (erro execucao)
  - upfolder: 1 (path invalido), 2 (credenciais), 3 (PAR2 nao encontrado), 4 (nyuu nao encontrado), 5 (erro nyuu), 6 (conflito NZB)
- Upload de arquivo unico pula criacao de RAR automaticamente (skip-rar implicito).
- Upload sem copia: upfolder.py passa paths diretos ao nyuu; sem staging em /tmp.
- NFO usa mediainfo para arquivos unicos e tree + stats + metadados de video para pastas.
- Configuracao fica em ~/.config/upapasta/.env (gerado automaticamente no primeiro uso).
- Comportamentos importantes: --dry-run, --obfuscate, --skip-rar, --filepath-format, --parpar-args, --rename-extensionless.
- Obfuscacao: obfuscate_and_par em makepar.py renomeia (so o root para pastas) e reverte em erro/Ctrl+C via bloco finally garantido.
- Passthrough parpar: make_parity injeta -f <filepath_format> e tokens de parpar_extra_args no argv. Default filepath_format=common (preserva subpastas relativas). Backend par2 ignora -f.
- Normalizacao de extensoes: normalize_extensionless renomeia arquivos sem extensao para .bin antes do upload (mapa de reversao em self._extensionless_map). revert_extensionless executa em _cleanup_on_error e ao final do run() bem-sucedido. Ativacao via --rename-extensionless e so com --skip-rar.

Logging

- --log-file <path>: ativa gravacao de log da sessao inteira.
- _TeeStream (em ui.py): stream duplo que escreve em stdout e em arquivo simultaneamente, removendo sequencias ANSI do arquivo.
- Funcoes de ciclo de vida: setup_logging, setup_session_log, teardown_session_log (todas em ui.py).

Common Commands

pytest tests/                          todos os testes
pytest tests/test_orchestrator.py      teste especifico
upapasta /path/to/folder --dry-run     teste sem upload real

Estilo: Comentarios e README em portugues. Usa apenas stdlib + subprocess para binarios externos (sem dependencias pesadas).
