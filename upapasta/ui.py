"""
ui.py

Componentes de interface de usuário (barra de progresso) e sistema de logging/sessão.
Utiliza a biblioteca 'rich' para uma interface de terminal (TUI) moderna e robusta.
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
from typing import Any, Optional, cast

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from .i18n import _

logger = logging.getLogger("upapasta")

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mABCDEFGHJKSTfhilmns]")
_SENSITIVE_RE = [
    (re.compile(r"(?i)(senha\s+rar:\s*)\S+"), r"\1***"),
    (re.compile(r"(?i)(NNTP_PASS=)\S+"), r"\1***"),
    (re.compile(r"(?i)(-hp)\S+"), r"\1***"),
]


def _sanitize(s: str) -> str:
    clean = _ANSI_RE.sub("", s)
    for pat, repl in _SENSITIVE_RE:
        clean = pat.sub(repl, clean)
    return clean


class _ThreadDispatchTeeStream(io.TextIOBase):
    """sys.stdout replacement: terminal para todos + log-file por-thread."""

    def __init__(self, terminal: io.TextIOBase) -> None:
        self._terminal = terminal

    def write(self, s: str) -> int:
        try:
            self._terminal.write(s)
            self._terminal.flush()
        except Exception:
            pass

        log_fh: Optional[io.TextIOWrapper] = getattr(_thread_local, "log_fh", None)
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
        log_fh: Optional[io.TextIOWrapper] = getattr(_thread_local, "log_fh", None)
        if log_fh:
            try:
                log_fh.flush()
            except Exception:
                pass

    @property
    def encoding(self) -> str:  # type: ignore[override]
        enc = getattr(self._terminal, "encoding", "utf-8")
        return enc if isinstance(enc, str) else "utf-8"

    @property
    def errors(self) -> Optional[str]:  # type: ignore[override]
        return getattr(self._terminal, "errors", "replace")

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
        enc = getattr(self._original, "encoding", "utf-8")
        return enc if isinstance(enc, str) else "utf-8"

    def fileno(self) -> int:
        return self._original.fileno()

    def isatty(self) -> bool:
        return self._original.isatty()


# Estado global do dispatcher
_thread_local: threading.local = threading.local()
_dispatch_lock = threading.Lock()
_dispatch_stream: Optional[_ThreadDispatchTeeStream] = None


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setLevel(level)
    fmt = "%(asctime)s %(levelname)s %(message)s" if verbose else "%(levelname)s %(message)s"
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))
    root = logging.getLogger("upapasta")
    root.setLevel(level)
    root.addHandler(handler)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
        )
        root.addHandler(fh)


def setup_session_log(
    input_name: str, env_file: Optional[str] = None
) -> tuple[str, io.TextIOWrapper]:
    global _dispatch_stream
    log_dir = os.path.join(
        os.path.dirname(env_file or os.path.expanduser("~/.config/upapasta/.env")), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = re.sub(r"[^\w.\-]", "_", input_name)[:80]
    log_path = os.path.join(log_dir, f"{ts}_{safe_name}.log")
    log_fh = open(log_path, "w", encoding="utf-8", buffering=1)
    log_fh.write(
        _("# UpaPasta — log de sessão\n# Início: {start}\n# Entrada: {name}\n\n").format(
            start=datetime.now().isoformat(), name=input_name
        )
    )
    with _dispatch_lock:
        if _dispatch_stream is None:
            terminal = cast(io.TextIOBase, sys.__stdout__ or sys.stdout)
            _dispatch_stream = _ThreadDispatchTeeStream(terminal)
            sys.stdout = _dispatch_stream
    _thread_local.log_fh = log_fh
    return log_path, log_fh


def teardown_session_log(log_fh: Optional[io.TextIOBase], log_path: str) -> None:
    if log_fh:
        log_fh.write(_("\n# Fim: {end}\n").format(end=datetime.now().isoformat()))
        log_fh.close()
    _thread_local.log_fh = None
    print(_("📄 Log salvo em: {path}").format(path=log_path))


def format_time(seconds: int) -> str:
    if seconds < 0:
        return "00:00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class PhaseBar:
    """Interface unificada (TUI) usando Rich.

    Gerencia o layout com fases e barra de progresso ativa.
    """

    PHASES = ("NFO", "PACK", "PAR2", "OBF", "UPLOAD", "DONE")
    _ICONS = {
        "pending": "[grey50]⬜[/]",
        "active": "[bold cyan]▶ [/]",
        "done": "[bold green]✅[/]",
        "skipped": "[grey50]⏭ [/]",
        "error": "[bold red]❌[/]",
    }

    def __init__(
        self,
        console: Optional[Console] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.console = console or Console()
        self._state: dict[str, str] = {p: "pending" for p in self.PHASES}
        self._elapsed: dict[str, float] = {}
        self._start_time: dict[str, float] = {}
        self.metadata = metadata or {}
        self._logs: list[str] = []
        self._max_logs = 3

        # Progresso rico
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, pulse_style="bright_blue"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            expand=True,
            console=self.console,
        )
        self.active_task: Optional[Any] = None
        self._live: Optional[Live] = None

    def __enter__(self) -> PhaseBar:
        _thread_local.bar_active = True
        self._porcelain = os.environ.get("UPAPASTA_PORCELAIN") == "1"
        if not self._porcelain:
            self._live = Live(self._render_group(), console=self.console, refresh_per_second=10)
            self._live.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._live:
            self._live.stop()
        _thread_local.bar_active = False

    def log(self, message: str) -> None:
        """Adiciona uma mensagem curta ao log do dashboard."""
        if getattr(self, "_porcelain", False):
            return
        self._logs.append(message)
        if len(self._logs) > self._max_logs:
            self._logs.pop(0)
        self._update_live()

    def start(self, phase: str) -> None:
        self._state[phase] = "active"
        self._start_time[phase] = time.time()
        if getattr(self, "_porcelain", False):
            print(f"@@PHASE:{phase}@@", flush=True)
            return
        self._update_live()

    def done(self, phase: str) -> None:
        if phase in self._start_time:
            self._elapsed[phase] = time.time() - self._start_time[phase]
        self._state[phase] = "done"
        if self.active_task is not None:
            self.progress.remove_task(self.active_task)
            self.active_task = None
        self._update_live()

    def skip(self, phase: str) -> None:
        self._state[phase] = "skipped"
        self._update_live()

    def skip_all(self) -> None:
        for phase in self.PHASES:
            if self._state[phase] == "pending":
                self._state[phase] = "skipped"
        self._update_live()

    def error(self, phase: str) -> None:
        if phase in self._start_time:
            self._elapsed[phase] = time.time() - self._start_time[phase]
        self._state[phase] = "error"
        self._update_live()

    def update_progress(self, percentage: float, description: str = "") -> None:
        """Atualiza a barra de progresso da fase ativa."""
        if getattr(self, "_porcelain", False):
            return
        if self.active_task is None:
            self.active_task = self.progress.add_task(description or _("Processando..."), total=100)
        self.progress.update(self.active_task, completed=percentage, description=description)
        self._update_live()

    def _update_live(self) -> None:
        if self._live:
            self._live.update(self._render_group())

    def _render_group(self) -> Group:
        renderables: list[Any] = []

        # Header de Metadados (opcional)
        if self.metadata:
            meta_table = Table.grid(padding=(0, 1))
            meta_table.add_column(style="bold magenta")
            meta_table.add_column()

            if "size" in self.metadata:
                meta_table.add_row(_("Tamanho:"), f"{self.metadata['size']} GB")
            if "obfuscate" in self.metadata:
                status = "[green]ON[/]" if self.metadata["obfuscate"] else "[grey50]OFF[/]"
                meta_table.add_row(_("Ofuscação:"), status)
            if "password" in self.metadata and self.metadata["password"]:
                pwd = self.metadata["password"]
                meta_table.add_row(_("Senha RAR:"), f"[bold yellow][ {pwd} ][/]")

            renderables.append(meta_table)
            renderables.append("")

        # Tabela de Fases
        table = Table.grid(padding=(0, 2))
        table.add_column(justify="left")

        for i, p in enumerate(self.PHASES, 1):
            state = self._state[p]
            icon = self._ICONS.get(state, "⬜")
            display_name = _(p)
            step_prefix = f"[dim][{i}/{len(self.PHASES)}][/] "

            if state == "done":
                t = int(self._elapsed.get(p, 0))
                table.add_row(
                    f"{icon} {step_prefix}[bold green]{display_name}[/] [dim]({t // 60:02d}:{t % 60:02d})[/]"
                )
            elif state == "active":
                table.add_row(f"{icon} {step_prefix}[bold cyan]{display_name}...[/]")
            elif state == "error":
                table.add_row(f"{icon} {step_prefix}[bold red]{display_name}[/]")
            else:
                table.add_row(f"{icon} {step_prefix}[grey50]{display_name}[/]")

        renderables.append(table)

        # Barra de Progresso Ativa
        if self.active_task is not None:
            renderables.append("")
            renderables.append(self.progress)

        # Logs Recentes
        if self._logs:
            renderables.append("")
            for log_msg in self._logs:
                renderables.append(f"[dim]  • {log_msg}[/]")

        return Group(*renderables)

    def _render(self) -> None:
        """Mantido para compatibilidade, mas agora usa Live."""
        pass


# Mensagens para extração (i18n)
def _extract_msgs() -> None:
    _("NFO")
    _("RAR")
    _("PAR2")
    _("UPLOAD")
    _("DONE")
    _("Processando...")
