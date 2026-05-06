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
import threading
import time
from datetime import datetime
from typing import Optional, cast

from .i18n import _

logger = logging.getLogger("upapasta")

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mABCDEFGHJKSTfhilmns]')
_SENSITIVE_RE = [
    (re.compile(r'(?i)(senha\s+rar:\s*)\S+'), r'\1***'),
    (re.compile(r'(?i)(NNTP_PASS=)\S+'),      r'\1***'),
    (re.compile(r'(?i)(-hp)\S+'),              r'\1***'),
]


def _sanitize(s: str) -> str:
    clean = _ANSI_RE.sub('', s)
    for pat, repl in _SENSITIVE_RE:
        clean = pat.sub(repl, clean)
    return clean


class _ThreadDispatchTeeStream(io.TextIOBase):
    """sys.stdout replacement: terminal para todos + log-file por-thread.

    Instalado uma única vez; cada thread registra seu log_fh via threading.local().
    Resolve a race-condition de --jobs N onde múltiplas threads sobrescreviam
    sys.stdout globalmente.
    """

    def __init__(self, terminal: io.TextIOBase) -> None:
        self._terminal = terminal

    def write(self, s: str) -> int:
        try:
            self._terminal.write(s)
            self._terminal.flush()
        except Exception:
            pass
        log_fh: Optional[io.TextIOWrapper] = getattr(_thread_local, 'log_fh', None)
        if log_fh:
            try:
                log_fh.write(_sanitize(s))
            except Exception:
                pass
        return len(s)

    def flush(self) -> None:
        try:
            self._terminal.flush()
        except Exception:
            pass
        log_fh: Optional[io.TextIOWrapper] = getattr(_thread_local, 'log_fh', None)
        if log_fh:
            try:
                log_fh.flush()
            except Exception:
                pass

    @property
    def encoding(self) -> str:  # type: ignore[override]
        enc = getattr(self._terminal, 'encoding', 'utf-8')
        return enc if isinstance(enc, str) else 'utf-8'

    @property
    def errors(self) -> Optional[str]:  # type: ignore[override]
        return getattr(self._terminal, 'errors', 'replace')

    def fileno(self) -> int:
        return self._terminal.fileno()

    def isatty(self) -> bool:
        return self._terminal.isatty()


# Mantido por compatibilidade interna; não usado em modo --jobs N.
class _TeeStream(io.TextIOBase):
    """Duplica escrita para stream original + arquivo de log (uso single-thread legado)."""

    def __init__(self, original: io.TextIOBase, log_fh: io.TextIOBase) -> None:
        self._original = original
        self._log = log_fh

    def write(self, s: str) -> int:
        self._original.write(s)
        self._original.flush()
        self._log.write(_sanitize(s))
        self._log.flush()
        return len(s)

    def flush(self) -> None:
        self._original.flush()
        self._log.flush()

    @property
    def encoding(self) -> str:  # type: ignore[override]
        enc = getattr(self._original, 'encoding', 'utf-8')
        return enc if isinstance(enc, str) else 'utf-8'

    def fileno(self) -> int:
        return self._original.fileno()

    def isatty(self) -> bool:
        return self._original.isatty()


# Estado global do dispatcher — inicializado após a definição da classe
_thread_local: threading.local = threading.local()
_dispatch_lock = threading.Lock()
_dispatch_stream: Optional[_ThreadDispatchTeeStream] = None


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


def setup_session_log(input_name: str, env_file: Optional[str] = None) -> tuple[str, io.TextIOWrapper]:
    """Cria arquivo de log da sessão e registra esta thread no dispatcher global.

    Thread-safe: instala _ThreadDispatchTeeStream em sys.stdout uma única vez;
    cada thread subsequente apenas registra seu próprio log_fh via threading.local().
    """
    global _dispatch_stream

    log_dir = os.path.join(os.path.dirname(env_file or os.path.expanduser("~/.config/upapasta/.env")), "logs")
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = re.sub(r'[^\w.\-]', '_', input_name)[:80]
    log_path = os.path.join(log_dir, f"{ts}_{safe_name}.log")

    log_fh = open(log_path, "w", encoding="utf-8", buffering=1)
    log_fh.write(_("# UpaPasta — log de sessão\n# Início: {start}\n# Entrada: {name}\n\n").format(
        start=datetime.now().isoformat(), name=input_name))

    # Instala o dispatcher global uma única vez (proteção com lock)
    with _dispatch_lock:
        if _dispatch_stream is None:
            terminal = cast(io.TextIOBase, sys.__stdout__ or sys.stdout)
            _dispatch_stream = _ThreadDispatchTeeStream(terminal)
            sys.stdout = _dispatch_stream

    # Registra o log file desta thread
    _thread_local.log_fh = log_fh
    return log_path, log_fh


def teardown_session_log(log_fh: Optional[io.TextIOBase], log_path: str) -> None:
    """Desregistra esta thread do dispatcher e fecha o arquivo de log."""
    if log_fh:
        log_fh.write(_("\n# Fim: {end}\n").format(end=datetime.now().isoformat()))
        log_fh.close()
    # Remove log file desta thread; futuros prints vão apenas para o terminal
    _thread_local.log_fh = None
    print(_("📄 Log salvo em: {path}").format(path=log_path))


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
        display_phase = _(phase)
        if state == "done":
            t = int(self._elapsed.get(phase, 0))
            return f"[{icon} {display_phase} {t // 60:02d}:{t % 60:02d}]"
        if state == "active":
            return f"[{icon} {display_phase}...]"
        if state in ("skipped", "error"):
            return f"[{icon} {display_phase}]"
        return f"[{icon} {display_phase}]"

    def _render(self) -> None:
        bar = "  ".join(self._fmt(p) for p in self.PHASES)
        print(f"\n{bar}")


# Mensagens para extração (i18n)
def _extract_msgs() -> None:
    _("NFO")
    _("RAR")
    _("PAR2")
    _("UPLOAD")
    _("DONE")
