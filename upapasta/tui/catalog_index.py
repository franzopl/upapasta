"""
tui/catalog_index.py

Índice em memória do history.jsonl, keyed por nome de arquivo/pasta.

O catálogo armazena apenas o nome do item (input_path.name), não o path completo.
O lookup é case-insensitive e retorna sempre a entrada mais recente para cada nome.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .external_nzb import ExternalNzbIndex


@dataclass(frozen=True)
class CatalogEntry:
    nome_original: str
    upload_date: datetime
    tamanho_bytes: Optional[int]
    caminho_nzb: Optional[str]
    grupo_usenet: Optional[str]
    categoria: Optional[str]
    is_external: bool = False


class CatalogIndex:
    """
    Índice em memória do history.jsonl e de diretórios de NZBs externos.

    Lookup por nome é O(1). Reload incremental: só relê o arquivo
    se o tamanho em bytes mudou desde a última leitura.
    """

    def __init__(self, history_path: Path, external_nzb_paths: Optional[list[Path]] = None) -> None:
        self._path = history_path
        self._index: dict[str, list[CatalogEntry]] = {}
        self._loaded_size: int = -1
        self._external_idx = ExternalNzbIndex(external_nzb_paths or [])

    # ── Carregamento ─────────────────────────────────────────────────────────

    def load(self) -> None:
        """Carrega ou recarrega o catálogo. Idempotente se o arquivo não mudou."""
        self._external_idx.scan()

        if not self._path.exists():
            self._index = {}
            self._loaded_size = 0
            return

        current_size = self._path.stat().st_size
        if current_size == self._loaded_size:
            return

        index: dict[str, list[CatalogEntry]] = {}

        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                name = record.get("nome_original")
                if not name or not isinstance(name, str):
                    continue

                entry = CatalogEntry(
                    nome_original=name,
                    upload_date=_parse_date(record.get("data_upload", "")),
                    tamanho_bytes=record.get("tamanho_bytes"),
                    caminho_nzb=record.get("caminho_nzb"),
                    grupo_usenet=record.get("grupo_usenet"),
                    categoria=record.get("categoria"),
                )

                key = name.lower()
                if key not in index:
                    index[key] = []
                index[key].append(entry)

        for entries in index.values():
            entries.sort(key=lambda e: e.upload_date, reverse=True)

        self._index = index
        self._loaded_size = current_size

    # ── Consulta ─────────────────────────────────────────────────────────────

    def lookup(self, name: str) -> Optional[CatalogEntry]:
        """Retorna a entrada mais recente para o nome, ou uma entrada virtual externa."""
        entries = self._index.get(name.lower())
        if entries:
            return entries[0]

        if self._external_idx.is_present(name):
            # Cria entrada virtual
            return CatalogEntry(
                nome_original=name,
                upload_date=datetime(1970, 1, 1, tzinfo=timezone.utc),
                tamanho_bytes=None,
                caminho_nzb=None,
                grupo_usenet=None,
                categoria=None,
                is_external=True,
            )

        return None

    def lookup_all(self, name: str) -> list[CatalogEntry]:
        """Retorna todas as entradas para o nome, ordenadas por data decrescente."""
        entries = list(self._index.get(name.lower(), []))
        if not entries and self._external_idx.is_present(name):
            return [self.lookup(name)]  # type: ignore
        return entries

    def has(self, name: str) -> bool:
        return name.lower() in self._index or self._external_idx.is_present(name)

    def all_names(self) -> set[str]:
        """Retorna o conjunto de nomes normalizados (lowercase) no índice."""
        return set(self._index.keys())

    # ── Métricas ──────────────────────────────────────────────────────────────

    def total_entries(self) -> int:
        """Número total de entradas no catálogo (incluindo duplicatas por nome)."""
        return sum(len(v) for v in self._index.values())

    def unique_names(self) -> int:
        """Número de nomes únicos no catálogo."""
        return len(self._index)

    def total_bytes(self) -> int:
        """Soma de tamanho_bytes de todas as entradas mais recentes por nome."""
        total = 0
        for entries in self._index.values():
            b = entries[0].tamanho_bytes
            if b is not None:
                total += b
        return total

    def all_entries_flat(self) -> list[CatalogEntry]:
        """Retorna todas as entradas do catálogo (todas as versões) em lista plana."""
        result: list[CatalogEntry] = []
        for entries in self._index.values():
            result.extend(entries)
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_date(value: object) -> datetime:
    """Parse de data ISO com fallback para epoch zero em caso de erro."""
    epoch_zero = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return epoch_zero
    # Python 3.9 fromisoformat não suporta sufixo 'Z'
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return epoch_zero


def load_catalog(
    history_path: Optional[Path] = None, external_nzb_paths: Optional[list[Path]] = None
) -> CatalogIndex:
    """Cria e carrega um CatalogIndex do path padrão ou do path fornecido."""
    if history_path is None:
        from ..config import CONFIG_DIR

        history_path = Path(CONFIG_DIR) / "history.jsonl"
    idx = CatalogIndex(history_path, external_nzb_paths=external_nzb_paths)
    idx.load()
    return idx
