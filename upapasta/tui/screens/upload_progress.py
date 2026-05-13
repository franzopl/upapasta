"""
tui/screens/upload_progress.py

Tela dedicada ao progresso de upload. Exibe o UploadPanel em tela cheia.
Retorna True se todos os uploads concluíram com sucesso, False caso contrário.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from ..fs_scanner import FileNode
from ..screens.confirm import UploadConfig
from ..widgets.upload_panel import UploadPanel


class UploadProgressScreen(Screen[bool]):
    """Tela de progresso de upload. dismiss(True) em sucesso, dismiss(False) em falha/cancelamento."""

    BINDINGS = [
        Binding("escape", "request_cancel", "Cancelar upload"),
    ]

    def __init__(self, items: list[FileNode], config: UploadConfig) -> None:
        super().__init__()
        self._items = items
        self._config = config

    def compose(self) -> ComposeResult:
        yield Header()
        yield UploadPanel(self._items, self._config, id="upload-panel")
        yield Footer()

    def on_mount(self) -> None:
        count = len(self._items)
        self.title = "UpaPasta — Upload em Progresso"
        s = "ns" if count != 1 else ""
        self.sub_title = f"{count} item{s} na fila"

    def on_upload_panel_finished(self, event: UploadPanel.Finished) -> None:
        if event.success:
            self.app.notify("Upload concluído com sucesso!", severity="information", timeout=4)
        else:
            self.app.notify("Upload falhou ou foi cancelado.", severity="error", timeout=4)
        self.dismiss(event.success)

    def action_request_cancel(self) -> None:
        self.query_one("#upload-panel", UploadPanel).cancel()
        self.app.notify("Cancelando...", severity="warning", timeout=2)
