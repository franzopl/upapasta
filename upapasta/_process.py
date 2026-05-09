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
from typing import Any, Generator


def _terminate_process(proc: subprocess.Popen[Any], timeout: int = 5) -> None:
    """
    Encerra o processo filho de forma segura.

    No Unix, envia SIGTERM e depois SIGKILL se necessário.
    No Windows, terminate() e kill() ambos encerram o processo abruptamente.
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
    *args: Any,
    **kwargs: Any,
) -> Generator[subprocess.Popen[Any], None, None]:
    """
    Context manager que garante encerramento do processo filho em qualquer situação.

    No Windows, adiciona creationflags=subprocess.CREATE_NO_WINDOW por padrão
    para evitar janelas de console "pipocando" para subprocessos, a menos que
    já fornecido. Também ativa shell=True no Windows para melhor compatibilidade
    com wrappers .cmd/.bat.
    """
    if sys.platform == "win32":
        if "creationflags" not in kwargs:
            # 0x08000000 = CREATE_NO_WINDOW
            kwargs["creationflags"] = 0x08000000
        if "shell" not in kwargs:
            kwargs["shell"] = True

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
