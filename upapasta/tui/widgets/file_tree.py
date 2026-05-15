"""
tui/widgets/file_tree.py

Widget de árvore de arquivos com status de upload por cor/ícone.
Lazy loading: subdiretórios são populados apenas quando expandidos.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ..catalog_index import CatalogIndex
from ..fs_scanner import FileNode, scan_directory
from ..status import IndexerStatus, UploadStatus


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

    # Adiciona tamanho para arquivos
    if not node.is_dir and node.size > 0:
        text.append(f"  ({node.size_human})", style="dim")

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

    badge = node.indexer_status.badge
    if badge:
        style = "cyan" if node.indexer_status == IndexerStatus.SEARCHING else "green"
        text.append(badge, style=style)

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
        Binding("a", "select_all", "Sel. Todos", show=True),
        Binding("i", "invert_selection", "Inverter", show=True),
        Binding("ctrl+d", "clear_selection", "Limpar", show=True),
        Binding("left", "back", "Voltar", show=False),
        Binding("n", "download_nzb", "Baixar NZB", show=True),
    ]

    class SelectionChanged(Message):
        """Postado quando a seleção de itens muda."""

        def __init__(self, selected: list[FileNode]) -> None:
            super().__init__()
            self.selected = selected

    class IndexerStatusUpdated(Message):
        """Postado pela thread de busca quando o status de um item é atualizado."""

        def __init__(self, path: Path, status: IndexerStatus, nzb_url: str, title: str) -> None:
            super().__init__()
            self.path = path
            self.status = status
            self.nzb_url = nzb_url
            self.title = title

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
        self._toggle_node_selection(cursor, node)
        self.post_message(self.SelectionChanged(list(self._selected.values())))

    def _toggle_node_selection(self, tree_node: TreeNode[FileNode], file_node: FileNode) -> None:
        if file_node.path in self._selected:
            del self._selected[file_node.path]
            now_selected = False
        else:
            self._selected[file_node.path] = file_node
            now_selected = True
        tree_node.set_label(make_node_label(file_node, selected=now_selected, query=self._query))

    def action_select_all(self) -> None:
        """Seleciona todos os nós de arquivo visíveis."""
        count = 0
        for node in self.query("TreeNode"):
            file_node: Optional[FileNode] = node.data  # type: ignore
            if file_node and not file_node.is_dir and file_node.path not in self._selected:
                self._toggle_node_selection(node, file_node)  # type: ignore
                count += 1
        if count > 0:
            self.app.notify(f"{count} itens selecionados", severity="information", timeout=2)
            self.post_message(self.SelectionChanged(list(self._selected.values())))
        else:
            self.app.notify("Nenhum item novo para selecionar", severity="warning", timeout=2)

    def action_invert_selection(self) -> None:
        """Inverte a seleção de todos os nós de arquivo visíveis."""
        for node in self.query("TreeNode"):
            file_node: Optional[FileNode] = node.data  # type: ignore
            if file_node and not file_node.is_dir:
                self._toggle_node_selection(node, file_node)  # type: ignore
        n = len(self._selected)
        self.app.notify(f"Seleção invertida — {n} itens", severity="information", timeout=2)
        self.post_message(self.SelectionChanged(list(self._selected.values())))

    def action_clear_selection(self) -> None:
        """Remove toda a seleção."""
        if not self._selected:
            return
        self.clear_selection()
        self.app.notify("Seleção removida", severity="information", timeout=2)

    def action_back(self) -> None:
        """Sobe um nível na árvore ou recolhe pasta."""
        cursor = self.cursor_node
        if cursor is None:
            return
        if cursor.is_expanded:
            cursor.collapse()
        elif cursor.parent:
            self.select_node(cursor.parent)

    def action_download_nzb(self) -> None:
        """Baixa o NZB do item em destaque se ele foi encontrado no indexador."""
        node = self.highlighted_node()
        if node is None or node.indexer_status != IndexerStatus.FOUND:
            self.app.notify(
                "Item não encontrado no indexador. Use x para buscar primeiro.",
                severity="warning",
                timeout=3,
            )
            return
        self._do_download_nzb(node)

    @work(thread=True)
    def _do_download_nzb(self, node: FileNode) -> None:
        import os
        import re

        from ...config import load_env_file, resolve_env_file
        from ...indexer import INDEXER_NZB_DIR, build_client_from_env

        env_vars = load_env_file(resolve_env_file())
        client = build_client_from_env(env_vars)
        if client is None or not node.indexer_nzb_url:
            self.app.call_from_thread(
                self.app.notify, "Indexador não configurado.", severity="error"
            )
            return

        safe = re.sub(r'[\\/*?"<>|]', "_", (node.indexer_title or node.name)[:60])
        dest = os.path.join(INDEXER_NZB_DIR, f"{safe}.nzb")
        try:
            client.download_nzb(node.indexer_nzb_url, dest)
            self.app.call_from_thread(
                self.app.notify,
                f"NZB salvo: {dest}",
                severity="information",
                timeout=5,
            )
        except Exception as exc:
            self.app.call_from_thread(
                self.app.notify, f"Erro ao baixar NZB: {exc}", severity="error"
            )

    # ── Indexer search ────────────────────────────────────────────────────────

    @work(thread=True)
    def start_indexer_search(self) -> None:
        """
        Busca todos os arquivos visíveis no indexador em background.
        Rate limiting gerenciado pelo NewznabClient — seguro chamar sem throttle externo.
        """
        from ...config import load_env_file, resolve_env_file
        from ...indexer import build_client_from_env

        env_vars = load_env_file(resolve_env_file())
        client = build_client_from_env(env_vars)
        if client is None:
            self.app.call_from_thread(
                self.app.notify,
                "Indexador não configurado (INDEXER_URL / INDEXER_APIKEY ausentes).",
                severity="warning",
                timeout=4,
            )
            return

        nodes = self._collect_visible_file_nodes()
        if not nodes:
            return

        self.app.call_from_thread(
            self.app.notify,
            f"Buscando {len(nodes)} item(s) no indexador...",
            severity="information",
            timeout=3,
        )

        for file_node in nodes:
            # Marca como buscando
            self.post_message(
                self.IndexerStatusUpdated(file_node.path, IndexerStatus.SEARCHING, "", "")
            )
            try:
                results = client.search(file_node.name, limit=3)
            except Exception:
                results = []

            if results:
                best = results[0]
                self.post_message(
                    self.IndexerStatusUpdated(
                        file_node.path, IndexerStatus.FOUND, best.nzb_url, best.title
                    )
                )
            else:
                self.post_message(
                    self.IndexerStatusUpdated(file_node.path, IndexerStatus.NOT_FOUND, "", "")
                )

    def _collect_visible_file_nodes(self) -> list[FileNode]:
        """Coleta todos os FileNodes de arquivo visíveis na árvore."""
        result = []
        for tree_node in self.query("TreeNode"):
            fn: Optional[FileNode] = tree_node.data  # type: ignore[assignment]
            if fn and not fn.is_dir:
                result.append(fn)
        return result

    @on(IndexerStatusUpdated)
    def _on_indexer_status_updated(self, event: IndexerStatusUpdated) -> None:
        """Atualiza o FileNode e re-renderiza o label correspondente na árvore."""
        for tree_node in self.query("TreeNode"):
            fn: Optional[FileNode] = tree_node.data  # type: ignore[assignment]
            if fn and fn.path == event.path:
                fn.indexer_status = event.status
                fn.indexer_nzb_url = event.nzb_url or None
                fn.indexer_title = event.title or None
                selected = fn.path in self._selected
                tree_node.set_label(make_node_label(fn, selected=selected, query=self._query))
                break

    # ── API pública ───────────────────────────────────────────────────────────

    def select_by_pattern(self, pattern: str) -> None:
        """Seleciona itens que casam com o regex entre os nós já carregados."""
        try:
            regex = re.compile(pattern, re.I)
        except re.error as exc:
            self.app.notify(f"Regex inválido: {exc}", severity="error")
            return

        count = 0
        for node in self.query("TreeNode"):
            file_node: Optional[FileNode] = node.data  # type: ignore
            if file_node and not file_node.is_dir and regex.search(file_node.name):
                if file_node.path not in self._selected:
                    self._toggle_node_selection(node, file_node)  # type: ignore
                    count += 1

        if count > 0:
            self.app.notify(f"{count} itens selecionados", severity="information")
            self.post_message(self.SelectionChanged(list(self._selected.values())))
        else:
            self.app.notify("Nenhum item novo encontrado", severity="warning")

    def select_by_status(self, status: UploadStatus) -> None:
        """Seleciona todos os nós visíveis com o status dado."""
        count = 0
        for node in self.query("TreeNode"):
            file_node: Optional[FileNode] = node.data  # type: ignore
            if file_node and not file_node.is_dir and file_node.status == status:
                if file_node.path not in self._selected:
                    self._toggle_node_selection(node, file_node)  # type: ignore
                    count += 1

        if count > 0:
            self.app.notify(f"{count} itens selecionados", severity="information")
            self.post_message(self.SelectionChanged(list(self._selected.values())))
        else:
            self.app.notify("Nenhum item encontrado com esse status", severity="warning")

    def select_by_min_size(self, min_bytes: int) -> None:
        """Seleciona arquivos com tamanho >= min_bytes entre os nós visíveis."""
        count = 0
        for node in self.query("TreeNode"):
            file_node: Optional[FileNode] = node.data  # type: ignore
            if file_node and not file_node.is_dir and file_node.size >= min_bytes:
                if file_node.path not in self._selected:
                    self._toggle_node_selection(node, file_node)  # type: ignore
                    count += 1

        if count > 0:
            self.app.notify(f"{count} itens selecionados", severity="information")
            self.post_message(self.SelectionChanged(list(self._selected.values())))
        else:
            self.app.notify("Nenhum arquivo encontrado com esse tamanho mínimo", severity="warning")

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
        # Salva o que estava expandido
        expanded_paths = {
            n.data.path
            for n in self.query("TreeNode")
            if n.is_expanded and n.data  # type: ignore
        }
        self._loaded_paths.clear()
        self.root.remove_children()
        self._load_node(self.root, self.root_path)
        self.root.expand()

        # Re-expand recursivamente
        self._reexpand_paths(self.root, expanded_paths)

    def _reexpand_paths(self, root_node: TreeNode[FileNode], expanded_paths: set[Path]) -> None:
        for node in root_node.children:
            if node.data and node.data.path in expanded_paths:
                if node.data.path not in self._loaded_paths:
                    self._load_node(node, node.data.path)
                node.expand()
                self._reexpand_paths(node, expanded_paths)

    def highlighted_node(self) -> Optional[FileNode]:
        """Retorna o FileNode do item atualmente sob o cursor, ou None."""
        node = self.cursor_node
        if node is None:
            return None
        return node.data
