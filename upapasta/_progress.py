"""
_progress.py

Parser de progresso compartilhado entre makerar.py, makepar.py e upfolder.py.
Integrado com a nova UI baseada em 'rich'.
"""

from __future__ import annotations

import re
import shutil
import sys
import time
from queue import Queue
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .ui import PhaseBar

# Tolerante a "label: 50%", "50%", "[50.0%]", "Uploading... 50%", etc.
# Prioriza capturar o valor numérico.
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_LABEL_CLEAN_RE = re.compile(r"^[\[\s\-#=>]*|[\s\-#=>]*$")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

_CHUNK_SIZE = 128  # bytes por read() — reduz syscalls vs. read(1), mas mantém responsividade


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _read_output(pipe: Optional[Any], queue: Queue[Optional[str]]) -> None:
    """Thread worker: lê pipe em chunks, envia tokens para a fila.

    Trata \\r, \\n e \\b como separadores.
    Pode receber pipe de bytes (unbuffered) ou str.
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

            if isinstance(chunk, bytes):
                try:
                    chunk_str = chunk.decode("utf-8", errors="replace")
                except Exception:
                    chunk_str = chunk.decode("latin1", errors="replace")
            else:
                chunk_str = chunk

            buf += chunk_str
            while True:
                # Procura separadores comuns: \r\n, \r, \n, \b e códigos ANSI de retorno de carro
                idx_rn = buf.find("\r\n")
                idx_r = buf.find("\r")
                idx_n = buf.find("\n")
                idx_b = buf.find("\b")
                idx_esc0g = buf.find("\x1b[0G")
                idx_esc1g = buf.find("\x1b[1G")

                # Encontra o primeiro separador
                indices = [
                    i for i in (idx_rn, idx_r, idx_n, idx_b, idx_esc0g, idx_esc1g) if i != -1
                ]
                if not indices:
                    break

                first_idx = min(indices)
                if first_idx == idx_rn:
                    sep_len = 2
                elif first_idx in (idx_esc0g, idx_esc1g):
                    sep_len = 4
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
    """Consome tokens da fila e atualiza o progresso.

    Se 'bar' for fornecido, atualiza a barra Rich (com throttle de 10Hz).
    """
    last_percent = -1
    teve_percentual = False
    bar_width = 25
    spinner = "|/-\\"
    spin_idx = 0
    last_label = ""
    last_update_time = 0.0
    throttle_interval = 0.1  # 10Hz

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

        line = _strip_ansi(line).strip()
        if not line:
            continue

        # Regex para capturar velocidade do nyuu (ex: "1.23 MB/s")
        # Útil para mostrar no label do upload.
        speed_match = re.search(r"(\d+\.?\d*\s*(?:[KMGT]?B)/s)", line, re.I)
        if speed_match:
            last_label = speed_match.group(1)

        m = _PCT_RE.search(line)
        if m:
            try:
                pct_val = float(m.group(1))
                if 0.0 <= pct_val <= 100.0:
                    last_percent = int(pct_val)
                    teve_percentual = True

                    # Tenta extrair um label útil se não for apenas lixo visual
                    label_candidate = _PCT_RE.sub("", line).strip()
                    label_candidate = _LABEL_CLEAN_RE.sub("", label_candidate)

                    # Se temos velocidade, prioriza ela ou anexa
                    current_label = label_candidate
                    if speed_match:
                        current_label = speed_match.group(1)
                    elif not current_label and last_label:
                        current_label = last_label

                    if bar:
                        now = time.time()
                        if now - last_update_time > throttle_interval or pct_val >= 100:
                            bar.update_progress(pct_val, current_label)
                            last_update_time = now
                        continue

                    # Fallback TTY (mantido)
                    sys.stdout.write(clear)
                    filled = int((pct_val / 100.0) * bar_width)
                    prog_bar = "#" * filled + "-" * (bar_width - filled)
                    prefix = f"[{prog_bar}] {pct_val:5.1f}%"
                    if current_label:
                        available = term_columns - 1 - len(prefix) - 2
                        label_trunc = current_label[:available] if available > 0 else ""
                        msg = f"{prefix}  {label_trunc}" if label_trunc else prefix
                    else:
                        msg = prefix
                    sys.stdout.write(msg[: term_columns - 1])
                    sys.stdout.flush()
                    continue
            except (ValueError, TypeError):
                pass

        if bar:
            # Se não tem porcentagem, atualiza label se parecer significativo (contém letras)
            clean_line = _LABEL_CLEAN_RE.sub("", line)

            # Filtra banners inúteis do rar e logs internos do parpar
            lower_clean = clean_line.lower()
            is_noise = any(
                x in lower_clean
                for x in [
                    "copyright (c)",
                    "trial version",
                    "evaluation copy",
                    "please register",
                    "article_size=",
                    "total=",
                    "slice=",
                    "min-slices=",
                    "max-slices=",
                ]
            )

            if (
                not is_noise
                and clean_line
                and any(c.isalpha() for c in clean_line)
                and len(clean_line) < 80
            ):
                last_label = clean_line
                now = time.time()
                if now - last_update_time > throttle_interval:
                    bar.update_progress(float(max(0, last_percent)), clean_line)
                    last_update_time = now
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
