"""
tui/widgets/status_bar.py

Barra inferior com detalhes do item selecionado na árvore.
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from ..fs_scanner import FileNode
from ..status import UploadStatus


class StatusBar(Static):
    """Exibe detalhes (path, tamanho, data de upload, NZB) do item em foco."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0 1;
        background: $panel-darken-1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__("", name=name, id=id, classes=classes)

    # ── API pública ───────────────────────────────────────────────────────────

    def update_node(self, node: Optional[FileNode]) -> None:
        """Atualiza o conteúdo da barra para o FileNode fornecido."""
        self.update(_render(node))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _render(node: Optional[FileNode]) -> Text:
    if node is None:
        return Text(
            " ↑↓ Navegar  Enter Expandir  Space Selecionar  / Buscar  p Padrão  1/2/3 Filtrar  r Atualizar  q Sair"
        )

    text = Text(no_wrap=True)
    text.append(f" {node.status.icon} ", style=node.status.color)
    text.append(node.name, style="bold" if node.is_dir else "default")

    if node.size > 0:
        text.append(f"  {node.size_human}", style="dim")

    if node.upload_date:
        text.append(
            f"  Enviado: {node.upload_date.strftime('%Y-%m-%d %H:%M')}",
            style="green dim",
        )
        if node.upload_entry:
            if node.upload_entry.grupo_usenet:
                text.append(f"  [{node.upload_entry.grupo_usenet}]", style="cyan dim")
            if node.upload_entry.categoria:
                text.append(f"  ({node.upload_entry.categoria})", style="magenta dim")

    if node.nzb_path is not None:
        text.append("  NZB ✓", style="green dim")

    if node.status == UploadStatus.PARTIAL and node.child_total > 0:
        pct = int(100 * node.child_uploaded / node.child_total)
        text.append(
            f"  {node.child_uploaded}/{node.child_total} itens ({pct}%)",
            style="yellow dim",
        )

    # Path completo no final para distinção
    text.append(f"  ({node.path})", style="dim")

    return text
