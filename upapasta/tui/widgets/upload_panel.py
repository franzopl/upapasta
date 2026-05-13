"""
tui/widgets/upload_panel.py

Painel de progresso de upload em tempo real.

Executa o pipeline upapasta em um subprocess por item, capturando stdout linha
a linha. Comunica progresso via mensagens Textual (thread-safe). Suporta
cancelamento limpo via proc.terminate() → SIGTERM → SIGKILL.
"""

from __future__ import annotations

import re
import subprocess
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import ProgressBar, RichLog, Static

from ..fs_scanner import FileNode
from ..screens.confirm import UploadConfig, build_upload_cmd

# Padrões para detectar a fase atual a partir das linhas de saída
_PHASE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"NFO|mediainfo|ffprobe", re.I), "NFO"),
    (re.compile(r"PAR2|parpar", re.I), "PAR2"),
    (re.compile(r"[Uu]pload|nyuu"), "Upload"),
    (re.compile(r"NZB|pós-processamento", re.I), "NZB"),
    (re.compile(r"limpeza|cleanup", re.I), "Limpeza"),
]

_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class UploadPanel(Vertical):
    """
    Painel de progresso de upload: cabeçalho + barra de fase + log scrollável.

    Inicia o upload automaticamente ao ser montado. Posta UploadPanel.Finished
    quando todos os itens são processados (ou o upload é cancelado).
    """

    # ── Mensagens (thread-safe via post_message) ───────────────────────────────

    class _Header(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class _Phase(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    class _Progress(Message):
        def __init__(self, pct: float) -> None:
            super().__init__()
            self.pct = pct

    class _LogLine(Message):
        def __init__(self, line: str, style: str = "") -> None:
            super().__init__()
            self.line = line
            self.style = style

    class Finished(Message):
        """Postado quando todos os itens terminaram (sucesso ou cancelamento)."""

        def __init__(self, success: bool) -> None:
            super().__init__()
            self.success = success

    # ── CSS ───────────────────────────────────────────────────────────────────

    DEFAULT_CSS = """
    UploadPanel {
        padding: 1 1 0 1;
    }

    #up-header {
        color: $text;
        text-style: bold;
        margin-bottom: 0;
    }

    #up-phase {
        color: $accent;
        margin-bottom: 0;
    }

    #up-bar {
        margin-bottom: 1;
    }

    #up-log {
        height: 1fr;
        border: tall $panel;
    }
    """

    def __init__(
        self,
        items: list[FileNode],
        config: UploadConfig,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._items = items
        self._config = config
        self._proc: Optional[subprocess.Popen[str]] = None
        self._cancelled = False

    def compose(self) -> ComposeResult:
        yield Static("", id="up-header")
        yield Static("Preparando...", id="up-phase")
        yield ProgressBar(total=100.0, show_eta=False, id="up-bar")
        yield RichLog(id="up-log", markup=False, highlight=False, auto_scroll=True)

    def on_mount(self) -> None:
        self._run_all()

    # ── Cancelamento ──────────────────────────────────────────────────────────

    def cancel(self) -> None:
        """Sinaliza cancelamento e envia SIGTERM ao subprocess ativo."""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

    # ── Worker (thread) ───────────────────────────────────────────────────────

    @work(thread=True)
    def _run_all(self) -> None:
        success = True
        for i, item in enumerate(self._items, 1):
            header = f"Enviando {i}/{len(self._items)}: {item.name}"
            self.post_message(self._Header(header))
            ok = self._run_one(item)
            if not ok:
                success = False
                if self._cancelled:
                    break
        self.post_message(self.Finished(success))

    def _run_one(self, item: FileNode) -> bool:
        cmd = build_upload_cmd(item, self._config)
        self.post_message(self._LogLine(f"$ {' '.join(cmd)}", style="dim"))
        self.post_message(self._Phase("Iniciando"))
        self.post_message(self._Progress(0.0))

        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ) as proc:
                self._proc = proc
                assert proc.stdout is not None
                for raw in proc.stdout:
                    if self._cancelled:
                        proc.terminate()
                        break
                    line = _strip_ansi(raw.rstrip())
                    if line:
                        self.post_message(self._LogLine(line))
                        self._detect_phase(line)
                        self._detect_progress(line)
                rc = proc.wait()
        except OSError as exc:
            self.post_message(self._LogLine(f"Erro ao iniciar processo: {exc}", style="bold red"))
            return False
        finally:
            self._proc = None

        if self._cancelled:
            self.post_message(self._LogLine("Upload cancelado pelo usuário.", style="yellow"))
            return False

        if rc != 0:
            self.post_message(
                self._LogLine(f"Processo encerrou com código {rc}.", style="bold red")
            )
            return False

        self.post_message(self._Phase("Concluído"))
        self.post_message(self._Progress(100.0))
        return True

    def _detect_phase(self, line: str) -> None:
        for pattern, name in _PHASE_PATTERNS:
            if pattern.search(line):
                self.post_message(self._Phase(name))
                break

    def _detect_progress(self, line: str) -> None:
        m = _PCT_RE.search(line)
        if m:
            self.post_message(self._Progress(min(100.0, float(m.group(1)))))

    # ── Handlers de mensagem ──────────────────────────────────────────────────

    def on_upload_panel__header(self, event: _Header) -> None:
        self.query_one("#up-header", Static).update(event.text)

    def on_upload_panel__phase(self, event: _Phase) -> None:
        self.query_one("#up-phase", Static).update(f"Fase: {event.name}")

    def on_upload_panel__progress(self, event: _Progress) -> None:
        self.query_one("#up-bar", ProgressBar).update(progress=event.pct)

    def on_upload_panel__log_line(self, event: _LogLine) -> None:
        log = self.query_one("#up-log", RichLog)
        if event.style:
            log.write(Text(event.line, style=event.style))
        else:
            log.write(event.line)
