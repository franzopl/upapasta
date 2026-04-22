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

1. Cria arquivos RAR a partir de pastas ou arquivos
2. Gera arquivos PAR2 de paridade
3. Faz upload via nyuu (sem copia temporaria — paths diretos)
4. Gera arquivos NZB e NFO
5. Limpa arquivos temporarios

Filosofia: menos flags, mais autonomia. Defaults inteligentes, wizard de primeira execucao, sem dependencias pesadas.

Development Setup

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

Binarios externos necessarios: rar, nyuu, parpar (ou par2).
Opcionais: ffmpeg, ffprobe, mediainfo (para geracao de NFO).

Core Modules

- main.py — UpaPastaOrchestrator + CLI (~1100 linhas). Orquestra o pipeline completo. Contem tambem: UpaPastaSession (context manager de cleanup), PhaseBar (barra de 4 fases), _TeeStream (logging dual console+arquivo), funcoes setup_logging / teardown_session_log.
- _process.py — managed_popen: context manager obrigatorio para todos os subprocessos externos. Garante SIGTERM → espera → SIGKILL em qualquer situacao (excecao, KeyboardInterrupt).
- makerar.py — Cria RAR5 com progresso ao vivo. Retorna codigos de erro inteiros.
- makepar.py — Gera PAR2 com 3 perfis (fast, balanced - default, safe). Suporta backends parpar e par2. Inclui obfuscate_and_par (renomeia + paridade com rollback garantido) e slice dinamico baseado no tamanho total.
- upfolder.py — Upload via nyuu sem staging em /tmp (opera com paths diretos). Retry automatico. Gera NZB, resolve conflitos de nome e cria NFOs.
- config.py — Centraliza: perfis PAR2 (PROFILES dict), credenciais NNTP (REQUIRED_CRED_KEYS), prompt interativo de primeiro uso (prompt_for_credentials), leitura de .env (load_env_file).

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
- Comportamentos importantes: --dry-run, --obfuscate, --skip-rar.
- Obfuscacao: obfuscate_and_par em makepar.py renomeia e reverte em erro (bloco finally garantido).

Logging

- --log-file <path>: ativa gravacao de log da sessao inteira.
- _TeeStream: stream duplo que escreve em stdout e em arquivo simultaneamente, removendo sequencias ANSI do arquivo.
- Funcoes de ciclo de vida: setup_logging, setup_session_log, teardown_session_log (todas em main.py).

Common Commands

pytest tests/                          todos os testes
pytest tests/test_orchestrator.py      teste especifico
upapasta /path/to/folder --dry-run     teste sem upload real

Estilo: Comentarios e README em portugues. Usa apenas stdlib + subprocess para binarios externos (sem dependencias pesadas).
