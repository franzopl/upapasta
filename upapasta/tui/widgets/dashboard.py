"""
tui/widgets/dashboard.py

Painel lateral de estatísticas do catálogo de uploads.
Toggle com [D] no app principal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import work
from textual.message import Message
from textual.widgets import Static

from ..catalog_index import CatalogIndex
from ..fs_scanner import scan_directory
from ..status import UploadStatus

# ── Data ──────────────────────────────────────────────────────────────────────


@dataclass
class DashboardStats:
    uploaded_count: int = 0
    uploaded_bytes: int = 0
    sparkline: list[int] = field(default_factory=list)  # bytes/dia, 30 dias, oldest→newest
    pending_count: int = 0
    pending_bytes: int = 0
    partial_items: list[str] = field(default_factory=list)
    fs_loaded: bool = False


def compute_catalog_stats(index: CatalogIndex, days: int = 30) -> DashboardStats:
    """Computa estatísticas do catálogo (rápido, sem I/O de filesystem)."""
    # Usa data UTC para consistência com as entradas do catálogo (armazenadas em UTC)
    today = datetime.now(timezone.utc).date()
    buckets: dict[date, int] = {}
    for i in range(days):
        buckets[today - timedelta(days=i)] = 0

    for entry in index.all_entries_flat():
        d = entry.upload_date.date()
        if d in buckets:
            buckets[d] += entry.tamanho_bytes or 0

    sparkline = [buckets[today - timedelta(days=days - 1 - i)] for i in range(days)]

    return DashboardStats(
        uploaded_count=index.unique_names(),
        uploaded_bytes=index.total_bytes(),
        sparkline=sparkline,
    )


def compute_fs_stats(root_path: Path, index: CatalogIndex) -> tuple[int, int, list[str]]:
    """
    Escaneia filhos diretos de root_path.
    Returns: (pending_count, pending_bytes, partial_items)
    Roda em thread de background — não chamar diretamente na thread principal.
    """
    nodes = scan_directory(root_path, index)
    pending_count = 0
    pending_bytes = 0
    partial_items: list[str] = []

    for node in nodes:
        if node.status == UploadStatus.PENDING:
            pending_count += 1
            pending_bytes += node.size
        elif node.status == UploadStatus.PARTIAL:
            partial_items.append(node.name)

    return pending_count, pending_bytes, partial_items


def sparkline_chars(values: list[int]) -> str:
    """Converte lista de inteiros em sparkline unicode (▁▂▃▄▅▆▇█)."""
    blocks = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == 0:
        return "▁" * len(values)
    max_val = max(values)
    return "".join(blocks[int(v / max_val * (len(blocks) - 1))] for v in values)


def fmt_bytes(b: int) -> str:
    if b < 1024**3:
        return f"{b / 1024**2:.0f} MB"
    return f"{b / 1024**3:.1f} GB"


# ── Widget ────────────────────────────────────────────────────────────────────


class DashboardWidget(Static):
    """
    Painel lateral com métricas do catálogo e alertas.

    Seções:
    - Visão Geral: contagens de itens enviados / pendentes / parciais
    - Uploads (30 dias): sparkline ASCII de atividade
    - Alertas: itens com upload parcial
    """

    DEFAULT_CSS = """
    DashboardWidget {
        width: 44;
        height: 100%;
        border-left: tall $accent;
        padding: 1 1;
        background: $surface;
        display: none;
    }
    """

    class FsStatsReady(Message):
        """Postado pelo worker quando o scan de filesystem termina."""

        def __init__(
            self,
            pending_count: int,
            pending_bytes: int,
            partial_items: list[str],
        ) -> None:
            super().__init__()
            self.pending_count = pending_count
            self.pending_bytes = pending_bytes
            self.partial_items = partial_items

    def __init__(
        self,
        index: CatalogIndex,
        root_path: Path,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__("", name=name, id=id, classes=classes)
        self._index = index
        self._root_path = root_path
        self._stats = DashboardStats()

    # ── API pública ───────────────────────────────────────────────────────────

    def refresh_data(self) -> None:
        """Recomputa estatísticas do catálogo e dispara worker para stats de filesystem."""
        self._stats = compute_catalog_stats(self._index)
        self._update_display()
        self._load_fs_stats()

    # ── Worker ────────────────────────────────────────────────────────────────

    @work(thread=True)
    def _load_fs_stats(self) -> None:
        pending_count, pending_bytes, partial_items = compute_fs_stats(self._root_path, self._index)
        self.post_message(DashboardWidget.FsStatsReady(pending_count, pending_bytes, partial_items))

    def on_dashboard_widget_fs_stats_ready(self, event: FsStatsReady) -> None:
        self._stats.pending_count = event.pending_count
        self._stats.pending_bytes = event.pending_bytes
        self._stats.partial_items = event.partial_items
        self._stats.fs_loaded = True
        self._update_display()

    # ── Renderização ──────────────────────────────────────────────────────────

    def _update_display(self) -> None:
        self.update(self._build_content())

    def _build_content(self) -> Text:
        text = Text(no_wrap=False)
        s = self._stats

        # Visão Geral
        text.append(" Visão Geral\n", style="bold cyan")
        text.append(" " + "─" * 28 + "\n", style="dim")

        text.append(" Enviados:  ", style="dim")
        text.append(f"{s.uploaded_count}", style="green bold")
        text.append(" itens", style="dim")
        if s.uploaded_bytes > 0:
            text.append(f"  {fmt_bytes(s.uploaded_bytes)}", style="green dim")
        text.append("\n")

        text.append(" Pendentes: ", style="dim")
        if s.fs_loaded:
            clr = "red bold" if s.pending_count > 0 else "dim"
            text.append(f"{s.pending_count}", style=clr)
            text.append(" itens", style="dim")
            if s.pending_bytes > 0:
                text.append(f"  {fmt_bytes(s.pending_bytes)}", style="red dim")
        else:
            text.append("…", style="dim")
        text.append("\n")

        text.append(" Parciais:  ", style="dim")
        if s.fs_loaded:
            n = len(s.partial_items)
            clr = "yellow bold" if n > 0 else "dim"
            text.append(f"{n}", style=clr)
            text.append(" itens\n", style="dim")
        else:
            text.append("…\n", style="dim")

        text.append("\n")

        # Sparkline
        text.append(" Uploads — 30 dias\n", style="bold cyan")
        text.append(" " + "─" * 28 + "\n", style="dim")
        if s.sparkline:
            spark = sparkline_chars(s.sparkline)
            max_day = max(s.sparkline)
            text.append(f" {spark}\n", style="green")
            if max_day > 0:
                text.append(f" pico: {fmt_bytes(max_day)}/dia\n", style="dim")
            else:
                text.append(" (sem uploads no período)\n", style="dim")
        else:
            text.append(" (sem dados)\n", style="dim")

        text.append("\n")

        # Alertas
        if s.fs_loaded:
            text.append(" Alertas\n", style="bold cyan")
            text.append(" " + "─" * 28 + "\n", style="dim")
            if not s.partial_items:
                text.append(" Nenhum alerta ✓\n", style="green dim")
            else:
                for item in s.partial_items[:6]:
                    display = item if len(item) <= 26 else item[:23] + "…"
                    text.append(f" • {display}\n", style="yellow")
                if len(s.partial_items) > 6:
                    extra = len(s.partial_items) - 6
                    text.append(f" • …e mais {extra}\n", style="yellow dim")

        return text
