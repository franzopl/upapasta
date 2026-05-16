"""
tui/screens/upload_progress.py

Tela dedicada ao progresso de upload. Exibe o UploadPanel em tela cheia.
Retorna True se todos os uploads concluíram com sucesso, False caso contrário.
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from ..fs_scanner import FileNode
from ..screens.confirm import UploadConfig
from ..screens.nzb_viewer import NzbViewerScreen
from ..widgets.upload_panel import UploadPanel


class UploadProgressScreen(Screen[bool]):
    """Tela de progresso de upload. dismiss(True) em sucesso, dismiss(False) em falha/cancelamento."""

    BINDINGS = [
        Binding("escape", "request_cancel", "Cancelar / Voltar"),
        Binding("p", "toggle_pause", "Pausar / Retomar", show=True),
        Binding("enter", "confirm_finish", "Concluir", show=False),
        Binding("n", "view_nzb", "Ver NZB", show=False),
    ]

    def __init__(self, items: list[FileNode], config: UploadConfig) -> None:
        super().__init__()
        self._items = items
        self._config = config
        self._finished = False
        self._success = False
        self._last_nzb: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield UploadPanel(self._items, self._config, id="upload-panel")
        yield Footer()

    def on_mount(self) -> None:
        count = len(self._items)
        self.title = "UpaPasta — Upload em Progresso"
        s = "ns" if count != 1 else ""
        self.sub_title = f"{count} item{s} na fila"

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """
        Controla a visibilidade dinâmica das bindings no Footer.

        'confirm_finish' e 'view_nzb' só aparecem após o término do upload —
        evita mutar a lista de classe BINDINGS (que vazaria entre instâncias).
        """
        if action == "confirm_finish":
            return True if self._finished else None
        if action == "view_nzb":
            return True if (self._finished and self._last_nzb) else None
        return True

    def on_upload_panel_nzb_generated(self, event: UploadPanel.NzbGenerated) -> None:
        self._last_nzb = event.path

    def on_upload_panel_finished(self, event: UploadPanel.Finished) -> None:
        self._finished = True
        self._success = event.success
        if event.last_nzb:
            self._last_nzb = event.last_nzb

        if event.success:
            nzb_hint = "  [N] Ver NZB" if self._last_nzb else ""
            self.app.notify(f"Upload concluído!{nzb_hint}", severity="information", timeout=5)
        else:
            self.app.notify("Upload encerrado com alertas.", severity="warning", timeout=4)

        # Reavalia check_action: Footer passa a exibir [Enter] Voltar e [N] Ver NZB
        self.refresh_bindings()

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

    def action_view_nzb(self) -> None:
        if self._last_nzb:
            self.app.push_screen(NzbViewerScreen(self._last_nzb))

    def action_confirm_finish(self) -> None:
        if self._finished:
            self.dismiss(self._success)
