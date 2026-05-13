"""
tui/widgets/file_tree.py

Widget de árvore de arquivos com status de upload por cor/ícone.
Lazy loading: subdiretórios são populados apenas quando expandidos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ..catalog_index import CatalogIndex
from ..fs_scanner import FileNode, scan_directory
from ..status import UploadStatus


def make_node_label(
    node: FileNode,
    *,
    selected: bool = False,
    query: str = "",
) -> Text:
    """Gera o label Rich de um FileNode para exibição na árvore."""
    text = Text(no_wrap=True, overflow="ellipsis")

    if selected:
        text.append("◉ ", style="bold cyan")

    text.append(node.status.icon + " ", style=node.status.color)
    if node.is_dir:
        text.append("📁 ")

    name = node.name
    name_style = "bold" if node.is_dir else "default"

    if query and (match_start := name.lower().find(query.lower())) != -1:
        match_end = match_start + len(query)
        if match_start > 0:
            text.append(name[:match_start], style=name_style)
        text.append(name[match_start:match_end], style="bold yellow reverse")
        if match_end < len(name):
            text.append(name[match_end:], style=name_style)
    else:
        text.append(name, style=name_style)

    if node.upload_date:
        text.append(
            f"  [{node.upload_date.strftime('%Y-%m-%d')}]",
            style="dim",
        )

    if node.status == UploadStatus.PARTIAL and node.child_total > 0:
        pct = int(100 * node.child_uploaded / node.child_total)
        text.append(
            f"  {node.child_uploaded}/{node.child_total} ({pct}%)",
            style="yellow dim",
        )

    return text


class FileTreeWidget(Tree[FileNode]):
    """
    Árvore de arquivos com indicadores visuais de status de upload.

    Lazy loading: ao expandir um diretório pela primeira vez, seus filhos
    são carregados via scan_directory + CatalogIndex. Re-expansões subsequentes
    não re-escaneiam (a menos que reload() seja chamado).
    """

    BINDINGS = [
        Binding("space", "toggle_select", "Selecionar", show=True, priority=True),
    ]

    class SelectionChanged(Message):
        """Postado quando a seleção de itens muda."""

        def __init__(self, selected: list[FileNode]) -> None:
            super().__init__()
            self.selected = selected

    def __init__(
        self,
        root_path: Path,
        index: CatalogIndex,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(
            Text.from_markup(f"📁 [bold]{root_path.name}[/bold]"),
            name=name,
            id=id,
            classes=classes,
        )
        self.root_path = root_path
        self.index = index
        self._filter: Optional[UploadStatus] = None
        self._query: str = ""
        self._loaded_paths: set[Path] = set()
        self._selected: dict[Path, FileNode] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.index.load()
        self._load_node(self.root, self.root_path)
        self.root.expand()

    # ── Carga de nós ──────────────────────────────────────────────────────────

    def _load_node(self, node: TreeNode[FileNode], path: Path) -> None:
        node.remove_children()
        children = scan_directory(path, self.index)
        query_lower = self._query.lower()
        for child in children:
            if self._filter is not None and not child.is_dir and child.status != self._filter:
                continue
            if query_lower and not child.is_dir and query_lower not in child.name.lower():
                continue
            selected = child.path in self._selected
            label = make_node_label(child, selected=selected, query=self._query)
            if child.is_dir:
                node.add(label, data=child, allow_expand=True)
            else:
                node.add_leaf(label, data=child)
        self._loaded_paths.add(path)

    @on(Tree.NodeExpanded)
    def _on_expanded(self, event: Tree.NodeExpanded[FileNode]) -> None:
        file_node = event.node.data
        if file_node is None or not file_node.is_dir:
            return
        # Lazy load: só escaneia na primeira expansão
        if file_node.path not in self._loaded_paths:
            self._load_node(event.node, file_node.path)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_select(self) -> None:
        """Alterna seleção do item sob o cursor."""
        cursor = self.cursor_node
        if cursor is None or cursor.data is None:
            return
        node: FileNode = cursor.data
        if node.path in self._selected:
            del self._selected[node.path]
            now_selected = False
        else:
            self._selected[node.path] = node
            now_selected = True
        cursor.set_label(make_node_label(node, selected=now_selected, query=self._query))
        self.post_message(self.SelectionChanged(list(self._selected.values())))

    # ── API pública ───────────────────────────────────────────────────────────

    def set_filter(self, status: Optional[UploadStatus]) -> None:
        self._filter = status
        self._reload_root()

    def set_search(self, query: str) -> None:
        self._query = query
        self._reload_root()

    def reload(self) -> None:
        self.index.load()
        self._reload_root()

    def selected_nodes(self) -> list[FileNode]:
        return list(self._selected.values())

    def clear_selection(self) -> None:
        self._selected.clear()
        self._reload_root()
        self.post_message(self.SelectionChanged([]))

    def _reload_root(self) -> None:
        self._loaded_paths.clear()
        self._load_node(self.root, self.root_path)
        self.root.expand()

    def highlighted_node(self) -> Optional[FileNode]:
        """Retorna o FileNode do item atualmente sob o cursor, ou None."""
        node = self.cursor_node
        if node is None:
            return None
        return node.data
