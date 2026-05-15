"""
tui/status.py

Enum de status de upload para uso na TUI.
"""

from __future__ import annotations

from enum import Enum


class UploadStatus(Enum):
    UPLOADED = "uploaded"
    PARTIAL = "partial"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IGNORED = "ignored"
    EXTERNAL = "external"

    @property
    def icon(self) -> str:
        return _ICONS[self.value]

    @property
    def color(self) -> str:
        return _COLORS[self.value]

    @property
    def label(self) -> str:
        return _LABELS[self.value]


_ICONS: dict[str, str] = {
    "uploaded": "✅",
    "partial": "🔶",
    "pending": "❌",
    "in_progress": "⏳",
    "ignored": "—",
    "external": "🌐",
}

_COLORS: dict[str, str] = {
    "uploaded": "green",
    "partial": "yellow",
    "pending": "red",
    "in_progress": "cyan",
    "ignored": "dim",
    "external": "blue",
}

_LABELS: dict[str, str] = {
    "uploaded": "Enviado",
    "partial": "Parcial",
    "pending": "Pendente",
    "in_progress": "Enviando",
    "ignored": "Ignorado",
    "external": "Externo",
}


class IndexerStatus(Enum):
    """Status da busca no indexador Newznab para um item da TUI."""

    UNKNOWN = "unknown"  # ainda não buscado
    SEARCHING = "searching"  # busca em andamento
    FOUND = "found"  # encontrado no indexador
    NOT_FOUND = "not_found"  # buscado, não encontrado

    @property
    def badge(self) -> str:
        return _INDEXER_BADGES[self.value]


_INDEXER_BADGES: dict[str, str] = {
    "unknown": "",
    "searching": " 🔍",
    "found": " 📥",
    "not_found": "",
}
