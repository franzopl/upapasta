"""
_process.py

Utilitário de subprocess com graceful shutdown garantido.

Fornece `managed_popen`, um context manager que envolve subprocess.Popen
e garante que o processo filho seja terminado em qualquer saída — seja por
conclusão normal, exceção Python ou KeyboardInterrupt (Ctrl+C).

Sem este wrapper, pressionar Ctrl+C durante rar/parpar/nyuu pode deixar o
processo filho rodando como zumbi no background.

Uso:
    from upapasta._process import managed_popen

    with managed_popen(cmd, stdout=subprocess.PIPE, ...) as proc:
        # usa proc normalmente
        rc = proc.wait()
"""

from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager
from typing import Generator


def _terminate_process(proc: subprocess.Popen, timeout: int = 5) -> None:
    """
    Encerra o processo filho de forma segura.

    Sequência:
      1. poll() — já terminou? Nada a fazer.
      2. terminate() — envia SIGTERM (graceful).
      3. wait(timeout) — aguarda até `timeout` segundos.
      4. kill() — envia SIGKILL se ainda estiver vivo (força bruta).
      5. wait() — coleta o exit code para evitar zumbi.
    """
    if proc.poll() is not None:
        return  # Já terminou
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait()
        except OSError:
            pass
    except OSError:
        pass  # Processo já pode ter terminado por corrida


@contextmanager
def managed_popen(
    *args,
    **kwargs,
) -> Generator[subprocess.Popen, None, None]:
    """
    Context manager que garante encerramento do processo filho em qualquer situação.

    Uso idêntico a subprocess.Popen() — todos os args e kwargs são repassados
    diretamente. A diferença é que em caso de KeyboardInterrupt, Exception, ou
    saída antecipada, o processo filho recebe SIGTERM (e SIGKILL como fallback).

    Exemplo:
        with managed_popen(cmd, stdout=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout:
                print(line, end='')
            rc = proc.wait()

    Levanta KeyboardInterrupt normalmente após encerrar o filho, para que o
    orquestrador (main.py) possa fazer sua própria limpeza.
    """
    proc = subprocess.Popen(*args, **kwargs)
    try:
        yield proc
    except KeyboardInterrupt:
        sys.stdout.write("\n⚠️  Interrompido pelo usuário. Encerrando processo filho...\n")
        sys.stdout.flush()
        _terminate_process(proc)
        raise  # propaga para o orquestrador lidar com a limpeza
    except Exception:
        _terminate_process(proc)
        raise
    finally:
        # Garante limpeza mesmo em retorno normal antecipado (break, return, etc.)
        _terminate_process(proc)
