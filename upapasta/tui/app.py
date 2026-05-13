"""
tui/app.py

App principal da TUI do UpaPasta.

Requer: pip install upapasta[tui]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Tree

from .catalog_index import load_catalog
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

    # ── Composição ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        yield FileTreeWidget(
            self.root_path,
            self._index,
            id="file-tree",
        )
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = str(self.root_path)

    # ── Eventos ───────────────────────────────────────────────────────────────

    @on(Tree.NodeHighlighted)
    def _on_node_highlighted(self, event: Tree.NodeHighlighted[None]) -> None:
        file_node = event.node.data  # type: ignore[union-attr]
        self.query_one(StatusBar).update_node(file_node)  # type: ignore[arg-type]

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

    # ── Internals ────────────────────────────────────────────────────────────

    def _apply_filter(self, status: Optional[UploadStatus]) -> None:
        self._filter = status
        self.query_one(FileTreeWidget).set_filter(status)
        if status is not None:
            self.sub_title = f"{self.root_path}  —  Filtro: {status.label}"
            self.notify(f"Filtro: {status.label}", severity="information", timeout=2)
        else:
            self.sub_title = str(self.root_path)


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
