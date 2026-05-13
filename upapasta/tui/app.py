"""
tui/app.py

App principal da TUI do UpaPasta.

Requer: pip install upapasta[tui]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, Tree

from .catalog_index import load_catalog
from .screens.confirm import ConfirmScreen
from .screens.upload_progress import UploadProgressScreen
from .status import UploadStatus
from .widgets.file_tree import FileTreeWidget
from .widgets.status_bar import StatusBar


class UpaPastaApp(App[None]):
    """Gerenciador visual de uploads Usenet."""

    TITLE = "UpaPasta"
    SUB_TITLE = "Gerenciador de Uploads Usenet"

    BINDINGS = [
        Binding("q", "quit", "Sair", priority=True),
        Binding("r", "refresh", "Atualizar"),
        Binding("u", "upload", "Upload", show=True),
        Binding("1", "filter_pending", "Pendentes", show=True),
        Binding("2", "filter_uploaded", "Enviados", show=True),
        Binding("3", "filter_partial", "Parciais", show=True),
        Binding("0", "filter_all", "Todos", show=True),
    ]

    CSS = """
    Screen {
        background: $surface;
    }

    FileTreeWidget {
        width: 100%;
        height: 1fr;
        scrollbar-gutter: stable;
    }

    #search-input {
        dock: bottom;
        height: 3;
        margin: 0;
        border: tall $accent;
        display: none;
    }

    StatusBar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $panel-darken-1;
        color: $text-muted;
    }

    Footer {
        background: $panel;
    }
    """

    def __init__(self, root_path: Path) -> None:
        super().__init__()
        self.root_path = root_path
        self._index = load_catalog()
        self._filter: Optional[UploadStatus] = None
        self._selection_count: int = 0

    # ── Composição ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        yield FileTreeWidget(
            self.root_path,
            self._index,
            id="file-tree",
        )
        yield Input(placeholder="Buscar... (Enter ou Esc para fechar)", id="search-input")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = str(self.root_path)

    # ── Eventos ───────────────────────────────────────────────────────────────

    @on(Tree.NodeHighlighted)
    def _on_node_highlighted(self, event: Tree.NodeHighlighted[None]) -> None:
        file_node = event.node.data  # type: ignore[union-attr]
        self.query_one(StatusBar).update_node(file_node)  # type: ignore[arg-type]

    @on(Input.Changed, "#search-input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self.query_one(FileTreeWidget).set_search(event.value)

    @on(Input.Submitted, "#search-input")
    def _on_search_submitted(self, event: Input.Submitted) -> None:
        self._hide_search()

    @on(FileTreeWidget.SelectionChanged)
    def _on_selection_changed(self, event: FileTreeWidget.SelectionChanged) -> None:
        self._selection_count = len(event.selected)
        self._update_subtitle()

    def on_key(self, event: events.Key) -> None:
        search = self.query_one("#search-input", Input)
        if event.key == "slash" and not search.display:
            search.display = True
            search.focus()
            event.stop()
        elif event.key == "escape" and search.display:
            self._hide_search()
            event.stop()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self.query_one(FileTreeWidget).reload()
        self.notify("Catálogo recarregado", severity="information", timeout=2)

    def action_filter_pending(self) -> None:
        self._apply_filter(UploadStatus.PENDING)

    def action_filter_uploaded(self) -> None:
        self._apply_filter(UploadStatus.UPLOADED)

    def action_filter_partial(self) -> None:
        self._apply_filter(UploadStatus.PARTIAL)

    def action_filter_all(self) -> None:
        self._apply_filter(None)

    def action_upload(self) -> None:
        items = self.query_one(FileTreeWidget).selected_nodes()
        if not items:
            self.notify("Selecione ao menos um item com Space", severity="warning", timeout=3)
            return
        self._run_upload_flow(items)

    @work
    async def _run_upload_flow(self, items: list) -> None:
        config = await self.push_screen_wait(ConfirmScreen(items))
        if config is None:
            return
        await self.push_screen_wait(UploadProgressScreen(items, config))
        tree = self.query_one(FileTreeWidget)
        tree.clear_selection()
        tree.reload()

    # ── Internals ────────────────────────────────────────────────────────────

    def _apply_filter(self, status: Optional[UploadStatus]) -> None:
        self._filter = status
        self.query_one(FileTreeWidget).set_filter(status)
        self._update_subtitle()
        if status is not None:
            self.notify(f"Filtro: {status.label}", severity="information", timeout=2)

    def _hide_search(self) -> None:
        search = self.query_one("#search-input", Input)
        search.display = False
        search.clear()
        tree = self.query_one(FileTreeWidget)
        tree.set_search("")
        tree.focus()

    def _update_subtitle(self) -> None:
        parts: list[str] = [str(self.root_path)]
        if self._filter is not None:
            parts.append(f"Filtro: {self._filter.label}")
        if self._selection_count > 0:
            s = "s" if self._selection_count != 1 else ""
            parts.append(f"{self._selection_count} selecionado{s}")
        self.sub_title = "  —  ".join(parts)


# ── Entry points ─────────────────────────────────────────────────────────────


def run_tui(root_path: Optional[Path] = None) -> None:
    """Inicia a TUI no diretório fornecido (padrão: cwd)."""
    if root_path is None:
        root_path = Path.cwd()
    root_path = root_path.resolve()
    if not root_path.is_dir():
        print(f"❌ Não é um diretório: {root_path}", file=sys.stderr)
        sys.exit(1)
    UpaPastaApp(root_path=root_path).run()


def run_tui_cli() -> None:
    """Entry point standalone: upapasta-tui [caminho]"""
    args = sys.argv[1:]
    root_path = Path(args[0]).resolve() if args else Path.cwd()
    run_tui(root_path=root_path)
