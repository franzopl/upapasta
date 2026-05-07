"""
_progress.py

Parser de progresso compartilhado entre makerar.py, makepar.py e upfolder.py.
Integrado com a nova UI baseada em 'rich'.
"""

from __future__ import annotations

import re
import shutil
import sys
from queue import Queue
from typing import IO, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .ui import PhaseBar

# Tolerante a "label: 50%", "50%", "[50.0%]", "Uploading... 50%", etc.
# Prioriza capturar o valor numérico.
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_LABEL_CLEAN_RE = re.compile(r"^[\[\s\-#]*|[\s\-#]*$")

_CHUNK_SIZE = 4096  # bytes por read() — reduz syscalls vs. read(1)


def _read_output(pipe: Optional[IO[str]], queue: Queue[Optional[str]]) -> None:
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
                # Prioriza \r\n, depois \r ou \n isolados
                idx_rn = buf.find("\r\n")
                idx_r = buf.find("\r")
                idx_n = buf.find("\n")

                # Encontra o primeiro separador
                indices = [i for i in (idx_rn, idx_r, idx_n) if i != -1]
                if not indices:
                    break

                first_idx = min(indices)
                if first_idx == idx_rn:
                    sep_len = 2
                else:
                    sep_len = 1

                token = buf[:first_idx]
                buf = buf[first_idx + sep_len :]
                if token:
                    queue.put(token)
    finally:
        if buf:
            queue.put(buf)
        queue.put(None)


def _process_output(
    queue: Queue[Optional[str]], bar: Optional[PhaseBar] = None
) -> tuple[int, bool]:
    """Consome linhas da fila e atualiza o progresso.

    Se 'bar' for fornecido, atualiza a barra Rich.
    Caso contrário, usa o fallback legado de print(\r).
    """
    last_percent = -1
    teve_percentual = False
    bar_width = 25
    spinner = "|/-\\"
    spin_idx = 0
    last_label = ""

    term_columns = 80
    if not bar:
        try:
            term_columns = shutil.get_terminal_size().columns
        except Exception:
            pass

    clear = "\r" + " " * (term_columns - 1) + "\r"

    while True:
        line = queue.get()
        if line is None:
            break

        line = line.strip()
        if not line:
            continue

        m = _PCT_RE.search(line)
        if m:
            try:
                pct_val = float(m.group(1))
                if 0.0 <= pct_val <= 100.0:
                    last_percent = int(pct_val)
                    teve_percentual = True

                    # Tenta extrair um label útil removendo a porcentagem e lixo visual
                    label_candidate = _PCT_RE.sub("", line).strip()
                    label_candidate = _LABEL_CLEAN_RE.sub("", label_candidate)
                    if label_candidate:
                        last_label = label_candidate

                    if bar:
                        bar.update_progress(pct_val, last_label)
                        continue

                    # Fallback TTY
                    sys.stdout.write(clear)
                    filled = int((pct_val / 100.0) * bar_width)
                    prog_bar = "#" * filled + "-" * (bar_width - filled)
                    prefix = f"[{prog_bar}] {pct_val:5.1f}%"
                    if last_label:
                        available = term_columns - 1 - len(prefix) - 2
                        label_trunc = last_label[:available] if available > 0 else ""
                        msg = f"{prefix}  {label_trunc}" if label_trunc else prefix
                    else:
                        msg = prefix
                    sys.stdout.write(msg[: term_columns - 1])
                    sys.stdout.flush()
                    continue
            except (ValueError, TypeError):
                pass

        if bar:
            # Se não tem porcentagem, atualiza apenas o label se for relevante
            # Remove lixo de barras de progresso ASCII do label
            clean_line = _LABEL_CLEAN_RE.sub("", line)
            if clean_line and len(clean_line) < 60:
                bar.update_progress(float(max(0, last_percent)), clean_line)
            continue

        # Fallback Spinner
        sys.stdout.write(clear)
        msg = f"{spinner[spin_idx % len(spinner)]} {line}"
        sys.stdout.write(msg[: term_columns - 1])
        sys.stdout.flush()
        spin_idx += 1

    if not bar:
        sys.stdout.write("\n")
        sys.stdout.flush()

    return last_percent, teve_percentual
