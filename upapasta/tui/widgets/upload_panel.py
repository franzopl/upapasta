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
import threading
import time
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Label, ProgressBar, RichLog, Rule, Static

from ..._process import managed_popen
from ..fs_scanner import FileNode
from ..screens.confirm import UploadConfig, build_upload_cmd

_SPINNER_CHARS = "⣾⣽⣻⢿⡿⣟⣯⣷"

_PHASE_MAP = {
    "NFO": "NFO",
    "PACK": "Compactação",
    "PAR2": "PAR2",
    "OBF": "Ofuscação",
    "UPLOAD": "Upload",
    "DONE": "Concluído",
}

_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_SPEED_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kB|MB|GB)/s", re.I)
_ETA_RE = re.compile(r"(?:ETA\s*:?\s*)?(\d+:\d+(?::\d+)?)\b", re.I)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _last_cr_segment(raw: str) -> str:
    """Retorna o último segmento separado por \\r (estado final da linha de progresso)."""
    parts = raw.rstrip("\n").split("\r")
    for part in reversed(parts):
        seg = _strip_ansi(part).strip()
        if seg:
            return seg
    return ""


def _item_text(name: str, status: str) -> Text:
    """Renderiza o nome do item com ícone e estilo para cada estado."""
    t = Text(no_wrap=True, overflow="ellipsis")
    if status == "running":
        t.append("  ▶  ", style="bold yellow")
        t.append(name, style="bold")
    elif status == "done":
        t.append("  ✓  ", style="bold green")
        t.append(name, style="dim")
    elif status == "failed":
        t.append("  ✗  ", style="bold red")
        t.append(name, style="dim")
    else:  # pending
        t.append("  ○  ", style="dim")
        t.append(name, style="dim")
    return t


class UploadPanel(Vertical):
    """
    Painel de progresso de upload: spinner + fase + barra + lista de itens + log.

    Inicia o upload automaticamente ao ser montado. Posta UploadPanel.Finished
    quando todos os itens são processados (ou o upload é cancelado).
    """

    # ── Mensagens (thread-safe via post_message) ───────────────────────────────

    class _ItemUpdate(Message):
        """Atualiza o status visual de um item na fila."""

        def __init__(self, index: int, status: str) -> None:
            super().__init__()
            self.index = index
            self.status = status  # "running" | "done" | "failed"

    class _Phase(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    class _Progress(Message):
        def __init__(self, pct: float) -> None:
            super().__init__()
            self.pct = pct

    class _SpeedETA(Message):
        def __init__(self, speed: str, eta: str) -> None:
            super().__init__()
            self.speed = speed
            self.eta = eta

    class _LogLine(Message):
        def __init__(self, line: str, style: str = "") -> None:
            super().__init__()
            self.line = line
            self.style = style

    class _PauseToggled(Message):
        def __init__(self, paused: bool) -> None:
            super().__init__()
            self.paused = paused

    class _QueueETA(Message):
        def __init__(self, eta_str: str) -> None:
            super().__init__()
            self.eta_str = eta_str

    class NzbGenerated(Message):
        """Postado quando um NZB é gerado (detectado via token @@NZB:)."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    class Finished(Message):
        """Postado quando todos os itens terminaram (sucesso ou cancelamento)."""

        def __init__(self, success: bool, last_nzb: Optional[str] = None) -> None:
            super().__init__()
            self.success = success
            self.last_nzb = last_nzb

    # ── CSS ───────────────────────────────────────────────────────────────────

    DEFAULT_CSS = """
    UploadPanel {
        padding: 1 1 0 1;
    }

    #up-status-row {
        height: 1;
        margin-bottom: 0;
    }

    #up-spinner {
        width: 2;
        color: $accent;
        text-style: bold;
    }

    #up-phase {
        width: 1fr;
        color: $accent;
    }

    #up-speed {
        width: auto;
        color: $warning;
        margin-right: 2;
    }

    #up-eta {
        width: auto;
        color: $text-muted;
        margin-right: 2;
    }

    #up-counter {
        width: auto;
        color: $text-muted;
    }

    #up-queue-eta {
        width: auto;
        color: $success;
        margin-right: 2;
    }

    #up-pause-indicator {
        width: auto;
        color: $warning;
        text-style: bold;
        display: none;
    }

    .progress-label {
        color: $text-muted;
        margin-top: 1;
    }

    #up-bar, #up-overall-bar {
        margin-top: 0;
        margin-bottom: 0;
    }

    #up-overall-bar > .bar--bar {
        color: $success;
    }

    #up-overall-bar > .bar--complete {
        color: $success;
    }

    #up-queue {
        height: 1fr;
        min-height: 8;
        border: tall $panel;
        margin-top: 1;
        padding: 0 1;
        overflow-y: scroll;
        background: $surface;
    }

    #up-log {
        height: 10;
        border: tall $panel;
        margin-top: 1;
        display: none;
    }

    #up-summary {
        padding: 1 2;
        border: thick $success;
        background: $surface;
        margin: 1 0;
        display: none;
    }

    .summary-title {
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }

    .help-text {
        color: $text-muted;
        text-align: center;
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
        self._paused = False
        self._resume_event = threading.Event()
        self._resume_event.set()  # não pausado por padrão
        self._current_phase = "Preparando"
        self._item_start: float = 0.0
        self._got_progress = False
        self._tick_count = 0
        self._done_count = 0
        self._current_speed = ""
        self._current_eta = ""
        # para ETA total da fila
        self._item_durations: list[float] = []
        self._current_item_start: float = 0.0
        self._last_nzb: Optional[str] = None

    def compose(self) -> ComposeResult:
        n = len(self._items)
        with Horizontal(id="up-status-row"):
            yield Static(_SPINNER_CHARS[0], id="up-spinner")
            yield Static("Preparando...", id="up-phase")
            yield Static("", id="up-speed")
            yield Static("", id="up-eta")
            yield Static("", id="up-queue-eta")
            yield Static("⏸ PAUSADO", id="up-pause-indicator")
            yield Static(f"0 / {n}", id="up-counter")

        yield Static("Progresso do Item:", classes="progress-label")
        yield ProgressBar(total=None, show_eta=False, id="up-bar")

        yield Static("Progresso Total:", classes="progress-label")
        yield ProgressBar(total=n, show_eta=False, id="up-overall-bar")

        if self._items:
            yield Rule()
            with Vertical(id="up-queue"):
                for i, item in enumerate(self._items):
                    yield Static(_item_text(item.name, "pending"), id=f"up-item-{i}")

        with Vertical(id="up-summary"):
            yield Label("Resumo do Upload", classes="summary-title")
            yield Static("", id="summary-text")
            yield Rule()
            yield Static("Pressione \\[Enter] ou \\[Esc] para voltar", classes="help-text")

        yield Rule()
        yield RichLog(id="up-log", markup=False, highlight=False, auto_scroll=True)

    def on_mount(self) -> None:
        self._item_start = time.monotonic()
        self.set_interval(0.5, self._tick_elapsed)
        self._run_all()

    def _tick_elapsed(self) -> None:
        """Atualiza spinner e elapsed a cada 0.5 s."""
        self._tick_count += 1
        spin = _SPINNER_CHARS[self._tick_count % len(_SPINNER_CHARS)]
        self.query_one("#up-spinner", Static).update(spin)
        elapsed = time.monotonic() - self._item_start
        mins, secs = divmod(int(elapsed), 60)
        self.query_one("#up-phase", Static).update(
            f"{self._current_phase}  —  {mins:02d}:{secs:02d}"
        )

    # ── Cancelamento e Pausa ─────────────────────────────────────────────────

    def cancel(self) -> None:
        """Sinaliza cancelamento e envia SIGTERM ao subprocess ativo."""
        self._cancelled = True
        self._resume_event.set()  # desbloqueia o worker se estiver pausado
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def toggle_pause(self) -> None:
        """Alterna pausa entre itens da fila."""
        if self._paused:
            self._paused = False
            self._resume_event.set()
        else:
            self._paused = True
            self._resume_event.clear()
        self.post_message(self._PauseToggled(self._paused))

    # ── Worker (thread) ───────────────────────────────────────────────────────

    @work(thread=True)
    def _run_all(self) -> None:
        success = True
        for idx, item in enumerate(self._items):
            # Aguarda se estiver pausado (sem bloquear cancelamento)
            self._resume_event.wait()
            if self._cancelled:
                break

            self._current_item_start = time.monotonic()
            self.post_message(self._ItemUpdate(idx, "running"))
            self.post_message(self._Phase("Iniciando"))
            ok = self._run_one(item)

            elapsed = time.monotonic() - self._current_item_start
            if ok:
                self._item_durations.append(elapsed)
                self.post_message(self._ItemUpdate(idx, "done"))
                self._post_queue_eta(idx + 1)
            else:
                self.post_message(self._ItemUpdate(idx, "failed"))
                success = False
                if self._cancelled:
                    break
        self.post_message(self.Finished(success, self._last_nzb))

    def _post_queue_eta(self, completed: int) -> None:
        """Calcula e posta ETA restante para a fila toda."""
        remaining = len(self._items) - completed
        if remaining <= 0 or not self._item_durations:
            self.post_message(self._QueueETA(""))
            return
        avg = sum(self._item_durations) / len(self._item_durations)
        total_secs = int(avg * remaining)
        mins, secs = divmod(total_secs, 60)
        hrs, mins = divmod(mins, 60)
        if hrs:
            eta_str = f"fila ~{hrs}h{mins:02d}m"
        else:
            eta_str = f"fila ~{mins}m{secs:02d}s"
        self.post_message(self._QueueETA(eta_str))

    def _run_one(self, item: FileNode) -> bool:
        cmd = build_upload_cmd(item, self._config)
        self.post_message(self._LogLine(f"$ {' '.join(cmd)}", style="dim"))
        self.post_message(self._Progress(0.0))

        try:
            import os

            env = os.environ.copy()
            env["UPAPASTA_PORCELAIN"] = "1"

            # managed_popen garante escalada SIGTERM→SIGKILL em qualquer saída
            # (cancelamento, exceção, fim de fila) — sem deixar processo zumbi.
            with managed_popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,  # Line buffered
                env=env,
            ) as proc:
                self._proc = proc
                assert proc.stdout is not None

                buffer = ""
                while True:
                    if self._cancelled:
                        proc.terminate()
                        break

                    char = proc.stdout.read(1)
                    if not char:
                        break

                    if char in ("\r", "\n"):
                        if buffer:
                            line = _strip_ansi(buffer).strip()
                            if line:
                                self.post_message(self._LogLine(line))
                                self._detect_phase(line)
                                self._detect_progress(line)
                                self._detect_speed_eta(line)
                        buffer = ""
                    else:
                        buffer += char
                        # Se o buffer ficar muito grande sem \r ou \n, força flush
                        if len(buffer) > 512:
                            self.post_message(self._LogLine(_strip_ansi(buffer)))
                            buffer = ""

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
        if line.startswith("@@NZB:"):
            nzb_path = line[len("@@NZB:") :].strip()
            if nzb_path:
                self._last_nzb = nzb_path
                self.post_message(self.NzbGenerated(nzb_path))
            return

        if line.startswith("@@PHASE:"):
            try:
                phase_code = line.split("@@")[1].split(":")[1]
                display_name = _PHASE_MAP.get(phase_code, phase_code)
                self.post_message(self._Phase(display_name))
            except IndexError:
                pass
            return

        # Fallback para limpeza
        if "limpeza" in line.lower() or "cleanup" in line.lower():
            self.post_message(self._Phase("Limpeza"))

    def _detect_progress(self, line: str) -> None:
        if "margem" in line.lower() or "ramdisk" in line.lower():
            return
        m = _PCT_RE.search(line)
        if m:
            self.post_message(self._Progress(min(100.0, float(m.group(1)))))

    def _detect_speed_eta(self, line: str) -> None:
        m_speed = _SPEED_RE.search(line)
        m_eta = _ETA_RE.search(line)
        if m_speed or m_eta:
            speed = m_speed.group(0) if m_speed else self._current_speed
            eta = m_eta.group(1) if m_eta else self._current_eta
            self.post_message(self._SpeedETA(speed, eta))

    # ── Handlers de mensagem ──────────────────────────────────────────────────

    def on_upload_panel__item_update(self, event: _ItemUpdate) -> None:
        item = self._items[event.index]
        widget = self.query_one(f"#up-item-{event.index}", Static)
        widget.update(_item_text(item.name, event.status))

        if event.status == "running":
            widget.scroll_visible()
            # Reinicia timer e barra para o novo item
            self._item_start = time.monotonic()
            self._current_phase = "Iniciando"
            self._current_speed = ""
            self._current_eta = ""
            self._got_progress = False
            self.query_one("#up-bar", ProgressBar).update(total=None, progress=0)
            self.query_one("#up-speed", Static).update("")
            self.query_one("#up-eta", Static).update("")
        elif event.status in ("done", "failed"):
            if event.status == "done":
                self._done_count += 1
            n = len(self._items)
            self.query_one("#up-counter", Static).update(f"{self._done_count} / {n}")
            self.query_one("#up-overall-bar", ProgressBar).update(progress=self._done_count)

    def on_upload_panel__phase(self, event: _Phase) -> None:
        self._current_phase = event.name
        # O timer (_tick_elapsed) atualiza o widget #up-phase

    def on_upload_panel__speed_eta(self, event: _SpeedETA) -> None:
        self._current_speed = event.speed
        self._current_eta = event.eta
        self.query_one("#up-speed", Static).update(f"⚡ {event.speed}")
        self.query_one("#up-eta", Static).update(f"⌛ {event.eta}")

    def on_upload_panel__progress(self, event: _Progress) -> None:
        bar = self.query_one("#up-bar", ProgressBar)
        if not self._got_progress:
            # Primeira porcentagem: troca para barra determinada
            self._got_progress = True
            bar.update(total=100.0, progress=event.pct)
        else:
            bar.update(progress=event.pct)

    def on_upload_panel__pause_toggled(self, event: _PauseToggled) -> None:
        indicator = self.query_one("#up-pause-indicator", Static)
        indicator.display = event.paused
        if event.paused:
            self._current_phase = "⏸ Pausado"
        else:
            self._current_phase = "Retomando..."

    def on_upload_panel__queue_eta(self, event: _QueueETA) -> None:
        self.query_one("#up-queue-eta", Static).update(event.eta_str)

    def on_upload_panel__log_line(self, event: _LogLine) -> None:
        log = self.query_one("#up-log", RichLog)
        if event.style:
            log.write(Text(event.line, style=event.style))
        else:
            log.write(event.line)

    def on_upload_panel_finished(self, event: Finished) -> None:
        """Exibe o resumo final antes de permitir a saída."""
        self.query_one("#up-bar", ProgressBar).display = False
        self.query_one("#up-overall-bar", ProgressBar).display = False
        self.query_one("#up-status-row").display = False
        self.query_one("#up-queue").display = False
        for label in self.query(".progress-label"):
            label.display = False

        n = len(self._items)
        success_count = self._done_count
        fail_count = n - success_count

        summary = f"Total de itens: {n}\n"
        summary += f"Sucessos: [bold green]{success_count}[/]\n"
        if fail_count > 0:
            summary += f"Falhas/Cancelados: [bold red]{fail_count}[/]\n"

        # Mostra o log de forma reduzida para contexto final
        log = self.query_one("#up-log")
        log.styles.height = 10
        log.display = True

        summary_widget = self.query_one("#up-summary")
        summary_widget.display = True
        self.query_one("#summary-text", Static).update(Text.from_markup(summary))
