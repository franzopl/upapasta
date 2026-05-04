"""
_progress.py

Parser de progresso compartilhado entre makerar.py e makepar.py.
"""

from __future__ import annotations

import re
import shutil
import sys
from queue import Queue
from typing import Tuple

# Tolerante a "label: 50%", "50%", "[50.0%]", etc.
_PCT_RE = re.compile(r"(?:^(.+?)[:\s]+)?(\d{1,3}(?:\.\d+)?)\s*%")

_CHUNK_SIZE = 4096  # bytes por read() — reduz syscalls vs. read(1)


def _read_output(pipe, queue: Queue) -> None:
    """Thread worker: lê pipe em chunks de 4 KB, envia linhas para a fila.

    Trata \\r e \\n como separadores (barras de progresso usam \\r sem \\n).
    """
    if pipe is None:
        queue.put(None)
        return
    buf = ""
    try:
        while True:
            chunk = pipe.read(_CHUNK_SIZE)
            if not chunk:
                break
            buf += chunk
            while True:
                for sep in ("\r\n", "\r", "\n"):
                    idx = buf.find(sep)
                    if idx != -1:
                        token = buf[:idx]
                        buf = buf[idx + len(sep):]
                        if token:
                            queue.put(token)
                        break
                else:
                    break
    finally:
        if buf:
            queue.put(buf)
        queue.put(None)


def _process_output(queue: Queue) -> Tuple[int, bool]:
    """Consome linhas da fila e exibe progresso no terminal.

    Exibição:
      - Linha com "XX%" → barra de progresso animada.
      - Caso contrário → spinner + texto truncado (fallback robusto).

    Retorna (last_percent, teve_percentual).
    """
    last_percent = -1
    teve_percentual = False
    bar_width = 25
    spinner = "|/-\\"
    spin_idx = 0
    last_label = ""

    try:
        term_columns = shutil.get_terminal_size().columns
    except Exception:
        term_columns = 80

    clear = "\r" + " " * (term_columns - 1) + "\r"

    while True:
        line = queue.get()
        if line is None:
            break

        line = line.strip()
        if not line:
            continue

        sys.stdout.write(clear)

        m = _PCT_RE.search(line)
        if m:
            label_raw = (m.group(1) or "").strip().rstrip(":").strip()
            if label_raw:
                last_label = label_raw
            try:
                pct_val = float(m.group(2))
                if 0.0 <= pct_val <= 100.0:
                    last_percent = int(pct_val)
                    teve_percentual = True
                    filled = int((pct_val / 100.0) * bar_width)
                    bar = "#" * filled + "-" * (bar_width - filled)
                    prefix = f"[{bar}] {pct_val:5.1f}%"
                    if last_label:
                        available = term_columns - 1 - len(prefix) - 2
                        label_trunc = last_label[:available] if available > 0 else ""
                        msg = f"{prefix}  {label_trunc}" if label_trunc else prefix
                    else:
                        msg = prefix
                    sys.stdout.write(msg[:term_columns - 1])
                    sys.stdout.flush()
                    continue
            except (ValueError, TypeError):
                pass

        msg = f"{spinner[spin_idx % len(spinner)]} {line}"
        sys.stdout.write(msg[:term_columns - 1])
        sys.stdout.flush()
        spin_idx += 1

    sys.stdout.write("\n")
    sys.stdout.flush()

    return last_percent, teve_percentual
