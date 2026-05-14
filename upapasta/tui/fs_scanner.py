"""
tui/fs_scanner.py

Scanner de filesystem que cruza entradas com o CatalogIndex para determinar
o status de upload de cada arquivo/pasta.

Matching por nome: o catálogo armazena apenas input_path.name, então a comparação
é feita pelo nome do item, não pelo path completo. Isso é uma limitação do catálogo
atual — dois itens com o mesmo nome em paths diferentes serão tratados como idênticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .catalog_index import CatalogEntry, CatalogIndex
from .status import UploadStatus


@dataclass
class FileNode:
    path: Path
    is_dir: bool
    size: int
    status: UploadStatus
    upload_entry: Optional[CatalogEntry] = field(default=None)
    child_total: int = 0
    child_uploaded: int = 0

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def upload_date(self) -> Optional[datetime]:
        return self.upload_entry.upload_date if self.upload_entry else None

    @property
    def nzb_path(self) -> Optional[Path]:
        if self.upload_entry and self.upload_entry.caminho_nzb:
            p = Path(self.upload_entry.caminho_nzb)
            return p if p.exists() else None
        return None

    @property
    def size_human(self) -> str:
        """Tamanho formatado de forma legível."""
        return _fmt_size(self.size)


def scan_directory(root: Path, index: CatalogIndex) -> list[FileNode]:
    """
    Escaneia os filhos imediatos de root e retorna uma lista de FileNode.

    Ordem: diretórios primeiro, depois arquivos, ambos em ordem alfabética
    case-insensitive.

    Não é recursivo — expansão de subdiretórios é feita sob demanda pela TUI.
    """
    if not root.is_dir():
        raise ValueError(f"Não é um diretório: {root}")

    try:
        raw_entries = list(root.iterdir())
    except PermissionError:
        return []

    nodes: list[FileNode] = []
    for entry in raw_entries:
        try:
            node = _build_node(entry, index)
        except OSError:
            continue
        nodes.append(node)

    nodes.sort(key=lambda n: (not n.is_dir, n.name.lower()))
    return nodes


def scan_single(path: Path, index: CatalogIndex) -> FileNode:
    """Cria um FileNode para um único path (arquivo ou diretório)."""
    return _build_node(path, index)


# ── Internals ─────────────────────────────────────────────────────────────────


def _build_node(path: Path, index: CatalogIndex) -> FileNode:
    if path.is_dir():
        return _build_dir_node(path, index)
    return _build_file_node(path, index)


def _build_file_node(path: Path, index: CatalogIndex) -> FileNode:
    entry = index.lookup(path.name)
    if entry:
        status = UploadStatus.EXTERNAL if entry.is_external else UploadStatus.UPLOADED
    else:
        status = UploadStatus.PENDING

    return FileNode(
        path=path,
        is_dir=False,
        size=_safe_size(path),
        status=status,
        upload_entry=entry,
    )


def _build_dir_node(path: Path, index: CatalogIndex) -> FileNode:
    entry = index.lookup(path.name)
    if entry:
        status = UploadStatus.EXTERNAL if entry.is_external else UploadStatus.UPLOADED
        return FileNode(
            path=path,
            is_dir=True,
            size=0,
            status=status,
            upload_entry=entry,
        )

    # Diretório não está no catálogo: verifica filhos diretos para status PARTIAL
    child_total, child_uploaded = _count_children(path, index)

    if child_total == 0 or child_uploaded == 0:
        status = UploadStatus.PENDING
    elif child_uploaded == child_total:
        status = UploadStatus.UPLOADED
    else:
        status = UploadStatus.PARTIAL

    return FileNode(
        path=path,
        is_dir=True,
        size=0,
        status=status,
        upload_entry=None,
        child_total=child_total,
        child_uploaded=child_uploaded,
    )


def _count_children(path: Path, index: CatalogIndex) -> tuple[int, int]:
    """Conta (total, uploaded) de filhos diretos de path."""
    try:
        children = list(path.iterdir())
    except PermissionError:
        return 0, 0

    total = len(children)
    uploaded = sum(1 for c in children if index.has(c.name))
    return total, uploaded


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size / 1024:.1f} KB"
    if size < 1024**3:
        return f"{size / 1024**2:.1f} MB"
    return f"{size / 1024**3:.2f} GB"
