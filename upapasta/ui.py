"""
ui.py

Componentes de interface de usuário (barra de progresso) e sistema de logging/sessão.
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Optional, cast

logger = logging.getLogger("upapasta")


class _TeeStream(io.TextIOBase):
    """Duplica escrita para stream original + arquivo de log."""

    def __init__(self, original: io.TextIOBase, log_fh: io.TextIOBase) -> None:
        self._original = original
        self._log = log_fh

    def write(self, s: str) -> int:
        self._original.write(s)
        self._original.flush()
        clean = re.sub(r'\x1b\[[0-9;]*[mABCDEFGHJKSTfhilmns]', '', s)
        # Mascara valores sensíveis antes de gravar no log em disco
        clean = re.sub(r'(?i)(senha\s+rar:\s*)\S+', r'\1***', clean)
        clean = re.sub(r'(?i)(NNTP_PASS=)\S+', r'\1***', clean)
        clean = re.sub(r'(?i)(-hp)\S+', r'\1***', clean)
        self._log.write(clean)
        self._log.flush()
        return len(s)

    def flush(self) -> None:
        self._original.flush()
        self._log.flush()

    @property
    def encoding(self) -> str:  # type: ignore[override]
        enc = getattr(self._original, 'encoding', 'utf-8')
        return enc if isinstance(enc, str) else 'utf-8'

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return self._original.isatty()


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setLevel(level)
    # Timestamps no terminal apenas em verbose — mantém output limpo no modo padrão
    fmt = "%(asctime)s %(levelname)s %(message)s" if verbose else "%(levelname)s %(message)s"
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))
    root = logging.getLogger("upapasta")
    root.setLevel(level)
    root.addHandler(handler)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
        root.addHandler(fh)


def setup_session_log(input_name: str, env_file: Optional[str] = None) -> tuple:
    """
    Cria arquivo de log da sessão em ~/.config/upapasta/logs/.
    Redireciona stdout para TeeStream que grava simultaneamente no terminal e no log.
    Retorna (caminho_do_log, file_handle) para fechar ao final.
    """
    log_dir = os.path.join(os.path.dirname(env_file or os.path.expanduser("~/.config/upapasta/.env")), "logs")
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Sanitiza nome para uso em arquivo
    safe_name = re.sub(r'[^\w.\-]', '_', input_name)[:80]
    log_path = os.path.join(log_dir, f"{ts}_{safe_name}.log")

    log_fh = open(log_path, "w", encoding="utf-8", buffering=1)
    log_fh.write(f"# UpaPasta — log de sessão\n# Início: {datetime.now().isoformat()}\n# Entrada: {input_name}\n\n")

    original_stdout = sys.__stdout__
    if original_stdout is None:
        original_stdout = sys.stdout  # type: ignore[assignment]
    tee_stream = _TeeStream(original_stdout, log_fh)  # type: ignore[arg-type]
    sys.stdout = tee_stream
    return log_path, log_fh


def teardown_session_log(log_fh: Optional[io.TextIOBase], log_path: str) -> None:
    """Restaura stdout e fecha o arquivo de log."""
    original = sys.__stdout__ or sys.stdout
    sys.stdout = cast(io.TextIOWrapper, original)
    if log_fh:
        log_fh.write(f"\n# Fim: {datetime.now().isoformat()}\n")
        log_fh.close()
    print(f"📄 Log salvo em: {log_path}")


def format_time(seconds: int) -> str:
    """Formata segundos como HH:MM:SS."""
    if seconds < 0:
        return "00:00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class PhaseBar:
    """Barra de progresso compacta com 5 fases: NFO → RAR → PAR2 → UPLOAD → DONE.

    Imprime uma linha de status sempre que uma fase muda de estado.
    Compatível com saída de subprocessos — não usa posicionamento de cursor.
    """

    PHASES = ("NFO", "RAR", "PAR2", "UPLOAD", "DONE")
    _ICONS = {"pending": "⬜", "active": "▶ ", "done": "✅", "skipped": "⏭ ", "error": "❌"}

    def __init__(self) -> None:
        self._state: dict[str, str] = {p: "pending" for p in self.PHASES}
        self._elapsed: dict[str, float] = {}
        self._start: dict[str, float] = {}

    def start(self, phase: str) -> None:
        self._state[phase] = "active"
        self._start[phase] = time.time()
        self._render()

    def done(self, phase: str) -> None:
        if phase in self._start:
            self._elapsed[phase] = time.time() - self._start[phase]
        self._state[phase] = "done"
        self._render()

    def skip(self, phase: str) -> None:
        self._state[phase] = "skipped"

    def error(self, phase: str) -> None:
        if phase in self._start:
            self._elapsed[phase] = time.time() - self._start[phase]
        self._state[phase] = "error"
        self._render()

    def _fmt(self, phase: str) -> str:
        state = self._state[phase]
        icon = self._ICONS.get(state, "⬜")
        if state == "done":
            t = int(self._elapsed.get(phase, 0))
            return f"[{icon} {phase} {t // 60:02d}:{t % 60:02d}]"
        if state == "active":
            return f"[{icon} {phase}...]"
        if state in ("skipped", "error"):
            return f"[{icon} {phase}]"
        return f"[{icon} {phase}]"

    def _render(self) -> None:
        bar = "  ".join(self._fmt(p) for p in self.PHASES)
        print(f"\n{bar}")
