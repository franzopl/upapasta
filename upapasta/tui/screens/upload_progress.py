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
        Binding("escape", "request_cancel", "Cancelar / Voltar"),
        Binding("p", "toggle_pause", "Pausar / Retomar", show=True),
        Binding("enter", "confirm_finish", "Concluir", show=False),
    ]

    def __init__(self, items: list[FileNode], config: UploadConfig) -> None:
        super().__init__()
        self._items = items
        self._config = config
        self._finished = False
        self._success = False

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
        self._finished = True
        self._success = event.success
        if event.success:
            self.app.notify("Upload concluído!", severity="information", timeout=4)
        else:
            self.app.notify("Upload encerrado com alertas.", severity="warning", timeout=4)

        # Habilita tecla Enter para fechar
        footer = self.query_one(Footer)
        self.BINDINGS.append(Binding("enter", "confirm_finish", "Voltar"))
        footer.refresh()

    def action_toggle_pause(self) -> None:
        if self._finished:
            return
        panel = self.query_one("#upload-panel", UploadPanel)
        panel.toggle_pause()
        if panel._paused:
            self.app.notify("Upload pausado. [P] para retomar.", severity="warning", timeout=3)
        else:
            self.app.notify("Upload retomado.", severity="information", timeout=2)

    def action_request_cancel(self) -> None:
        if self._finished:
            self.dismiss(self._success)
            return

        self.query_one("#upload-panel", UploadPanel).cancel()
        self.app.notify("Cancelando...", severity="warning", timeout=2)

    def action_confirm_finish(self) -> None:
        if self._finished:
            self.dismiss(self._success)
