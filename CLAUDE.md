# CLAUDE.md

Regras de Economia de Tokens (sempre siga primeiro)

- Para qualquer tarefa de exploracao, leitura, busca, grep ou mapeamento no codigo, use preferencialmente o subagent code-explorer (model Haiku).
- Nunca use subagents com modelo Opus ou Sonnet para tarefas simples de leitura ou exploracao.
- Mantenha respostas de subagents curtas, objetivas e em bullet points.
- Evite paralelismo excessivo de subagents. Use apenas quando realmente necessario.
- Seja extremamente especifico nos prompts.
- Use clear ou abra uma nova sessao ao mudar de tarefa grande.

Project Overview

UpaPasta e uma ferramenta CLI em Python que automatiza o upload completo para Usenet.

1. Cria arquivos RAR a partir de pastas ou arquivos
2. Gera arquivos PAR2 de paridade
3. Faz upload via nyuu
4. Gera arquivos NZB e NFO
5. Limpa arquivos temporarios

Development Setup

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

Binarios externos necessarios: rar, nyuu, parpar (ou par2).
Opcionais: ffmpeg ffprobe, mediainfo (para geracao de NFO).

Core Modules

- main.py - UpaPastaOrchestrator + CLI. Orquestra o pipeline completo, gerencia mais de 40 opcoes CLI, dry-run, obfuscation e cleanup.
- makerar.py - Cria RAR5 com progresso ao vivo. Retorna codigos de erro inteiros.
- makepar.py - Gera PAR2 com 3 perfis (fast, balanced - default, safe). Suporta backends parpar e par2.
- upfolder.py - Upload via nyuu, gera NZB, resolve conflitos de nome e cria NFOs.

Key Conventions

- Todas as funcoes principais retornam codigos inteiros: 0 = sucesso, 1-6 = erros especificos (veja docstrings).
- Upload de arquivo unico pula criacao de RAR automaticamente (skip-rar implicito).
- NFO usa mediainfo para arquivos unicos e tree + stats + metadados de video para pastas.
- Configuracao fica em ~/.config/upapasta/.env (veja .env.example).
- Comportamentos importantes: --dry-run, --obfuscate, --skip-rar.

Common Commands

pytest tests/                          todos os testes
pytest tests/test_orchestrator.py      teste especifico
upapasta /path/to/folder --dry-run     teste sem upload real

Estilo: Comentarios e README em portugues. Usa apenas stdlib + subprocess para binarios externos (sem dependencias pesadas).