"""
tui/widgets/dashboard.py

Painel lateral de estatísticas do catálogo de uploads.
Toggle com [D] no app principal. Teclas [ / ] para ajustar timeframe do sparkline.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from ..catalog_index import CatalogEntry, CatalogIndex
from ..fs_scanner import scan_directory
from ..status import UploadStatus

# ── Data ──────────────────────────────────────────────────────────────────────

_TIMEFRAMES = [7, 14, 30, 90]


@dataclass
class DashboardStats:
    # Catálogo
    uploaded_count: int = 0
    uploaded_bytes: int = 0
    sparkline: list[int] = field(default_factory=list)
    avg_bytes: int = 0
    uploads_this_week: int = 0
    uploads_last_week: int = 0
    recent_uploads: list[CatalogEntry] = field(default_factory=list)
    top_groups: list[tuple[str, int]] = field(default_factory=list)
    top_categories: list[tuple[str, int]] = field(default_factory=list)
    # Filesystem (background)
    pending_count: int = 0
    pending_bytes: int = 0
    partial_items: list[str] = field(default_factory=list)
    fs_loaded: bool = False


def compute_catalog_stats(index: CatalogIndex, days: int = 30) -> DashboardStats:
    today = datetime.now(timezone.utc).date()

    buckets: dict[date, int] = {today - timedelta(days=i): 0 for i in range(days)}

    all_entries = index.all_entries_flat()

    week_start = today - timedelta(days=7)
    prev_week_start = today - timedelta(days=14)

    uploads_this = 0
    uploads_last = 0
    group_counter: Counter[str] = Counter()
    cat_counter: Counter[str] = Counter()
    size_list: list[int] = []

    for entry in all_entries:
        d = entry.upload_date.date()
        if d in buckets:
            buckets[d] += entry.tamanho_bytes or 0
        if d >= week_start:
            uploads_this += 1
        elif d >= prev_week_start:
            uploads_last += 1
        if entry.grupo_usenet:
            group_counter[entry.grupo_usenet] += 1
        if entry.categoria:
            cat_counter[entry.categoria] += 1
        if entry.tamanho_bytes:
            size_list.append(entry.tamanho_bytes)

    sparkline = [buckets[today - timedelta(days=days - 1 - i)] for i in range(days)]

    # Últimos 5 uploads únicos por data decrescente
    seen: set[str] = set()
    recent: list[CatalogEntry] = []
    for entry in sorted(all_entries, key=lambda e: e.upload_date, reverse=True):
        key = entry.nome_original.lower()
        if key not in seen:
            seen.add(key)
            recent.append(entry)
        if len(recent) >= 5:
            break

    avg_bytes = int(sum(size_list) / len(size_list)) if size_list else 0

    return DashboardStats(
        uploaded_count=index.unique_names(),
        uploaded_bytes=index.total_bytes(),
        sparkline=sparkline,
        avg_bytes=avg_bytes,
        uploads_this_week=uploads_this,
        uploads_last_week=uploads_last,
        recent_uploads=recent,
        top_groups=group_counter.most_common(3),
        top_categories=cat_counter.most_common(3),
    )


def compute_fs_stats(root_path: Path, index: CatalogIndex) -> tuple[int, int, list[str]]:
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
    blocks = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == 0:
        return "▁" * len(values)
    max_val = max(values)
    return "".join(blocks[int(v / max_val * (len(blocks) - 1))] for v in values)


def fmt_bytes(b: int) -> str:
    if b >= 1024**4:
        return f"{b / 1024**4:.1f} TB"
    if b >= 1024**3:
        return f"{b / 1024**3:.1f} GB"
    return f"{b / 1024**2:.0f} MB"


def _relative_date(dt: datetime) -> str:
    """Retorna string relativa como 'hoje', 'ontem', '3 dias atrás', '2 sem.'."""
    today = datetime.now(timezone.utc).date()
    delta = (today - dt.date()).days
    if delta == 0:
        return "hoje"
    if delta == 1:
        return "ontem"
    if delta < 7:
        return f"{delta}d atrás"
    if delta < 30:
        weeks = delta // 7
        return f"{weeks}sem atrás"
    months = delta // 30
    return f"{months}m atrás"


# ── Widget ────────────────────────────────────────────────────────────────────


class DashboardWidget(Static):
    """
    Painel lateral com métricas do catálogo.

    Seções:
    - Visão Geral: contagens e bytes totais
    - Esta semana vs semana anterior
    - Recentes: últimos 5 uploads
    - Atividade: sparkline ajustável com [ / ]
    - Top Grupos e Categorias
    - Alertas: itens parciais
    """

    BINDINGS = [
        Binding("[", "prev_timeframe", "Período ←", show=True),
        Binding("]", "next_timeframe", "Período →", show=True),
    ]

    DEFAULT_CSS = """
    DashboardWidget {
        width: 46;
        height: 100%;
        border-left: tall $accent;
        padding: 1 1;
        background: $surface;
        display: none;
        overflow-y: auto;
    }
    """

    class FsStatsReady(Message):
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
        self._tf_idx: int = 2  # default: 30 dias

    @property
    def _days(self) -> int:
        return _TIMEFRAMES[self._tf_idx]

    # ── API pública ───────────────────────────────────────────────────────────

    def refresh_data(self) -> None:
        self._stats = compute_catalog_stats(self._index, self._days)
        self._update_display()
        self._load_fs_stats()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_prev_timeframe(self) -> None:
        if self._tf_idx > 0:
            self._tf_idx -= 1
            self.refresh_data()

    def action_next_timeframe(self) -> None:
        if self._tf_idx < len(_TIMEFRAMES) - 1:
            self._tf_idx += 1
            self.refresh_data()

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

    def _sep(self, text: Text, title: str = "") -> None:
        w = 36
        if title:
            pad = (w - len(title) - 2) // 2
            line = "─" * pad + f" {title} " + "─" * (w - pad - len(title) - 2)
        else:
            line = "─" * w
        text.append(f" {line}\n", style="dim")

    def _build_content(self) -> Text:
        text = Text(no_wrap=False)
        s = self._stats

        # ── Visão Geral ────────────────────────────────────────────────────
        text.append(" VISÃO GERAL\n", style="bold cyan")
        self._sep(text)

        text.append(" Enviados   ", style="dim")
        text.append(f"{s.uploaded_count}", style="bold green")
        text.append(" itens", style="dim")
        if s.uploaded_bytes > 0:
            text.append(f"  ({fmt_bytes(s.uploaded_bytes)})", style="green dim")
        text.append("\n")

        text.append(" Pendentes  ", style="dim")
        if s.fs_loaded:
            clr = "bold red" if s.pending_count > 0 else "dim"
            text.append(f"{s.pending_count}", style=clr)
            text.append(" itens", style="dim")
            if s.pending_bytes > 0:
                text.append(f"  ({fmt_bytes(s.pending_bytes)})", style="red dim")
        else:
            text.append("…", style="dim")
        text.append("\n")

        text.append(" Parciais   ", style="dim")
        if s.fs_loaded:
            n = len(s.partial_items)
            text.append(f"{n}", style="bold yellow" if n > 0 else "dim")
            text.append(" itens\n", style="dim")
        else:
            text.append("…\n", style="dim")

        if s.avg_bytes > 0:
            text.append(" Média/item ", style="dim")
            text.append(f"{fmt_bytes(s.avg_bytes)}\n", style="bold")

        text.append("\n")

        # ── Esta semana vs anterior ────────────────────────────────────────
        text.append(" ESTA SEMANA\n", style="bold cyan")
        self._sep(text)
        text.append(" Esta sem.  ", style="dim")
        text.append(f"{s.uploads_this_week}", style="bold green")
        text.append(" uploads\n", style="dim")
        text.append(" Sem. ant.  ", style="dim")
        text.append(f"{s.uploads_last_week}", style="bold")
        text.append(" uploads", style="dim")
        if s.uploads_last_week > 0 and s.uploads_this_week != s.uploads_last_week:
            diff = s.uploads_this_week - s.uploads_last_week
            if diff > 0:
                text.append(f"  ↑+{diff}", style="green bold")
            else:
                text.append(f"  ↓{diff}", style="red bold")
        text.append("\n\n")

        # ── Recentes ──────────────────────────────────────────────────────
        text.append(" RECENTES\n", style="bold cyan")
        self._sep(text)
        if not s.recent_uploads:
            text.append(" (sem histórico)\n", style="dim")
        else:
            for entry in s.recent_uploads:
                rel = _relative_date(entry.upload_date)
                name = entry.nome_original
                max_name = 26
                display_name = name if len(name) <= max_name else name[: max_name - 1] + "…"
                text.append(f" {display_name}", style="default")
                # padding
                pad = max_name - len(display_name)
                text.append(" " * pad)
                text.append(f" {rel}\n", style="dim")
        text.append("\n")

        # ── Sparkline ─────────────────────────────────────────────────────
        text.append(f" ATIVIDADE — {self._days} DIAS", style="bold cyan")
        text.append("  [/] ajustar\n", style="dim")
        self._sep(text)
        if s.sparkline:
            spark = sparkline_chars(s.sparkline)
            max_day = max(s.sparkline)
            total_period = sum(s.sparkline)
            active_days = sum(1 for v in s.sparkline if v > 0)
            text.append(f" {spark}\n", style="green")
            if max_day > 0:
                text.append(f" pico: {fmt_bytes(max_day)}/dia", style="dim")
                text.append(f"  total: {fmt_bytes(total_period)}\n", style="dim")
                text.append(f" {active_days}/{self._days} dias ativos\n", style="dim")
            else:
                text.append(" (sem uploads no período)\n", style="dim")
        else:
            text.append(" (sem dados)\n", style="dim")
        text.append("\n")

        # ── Top Grupos ────────────────────────────────────────────────────
        if s.top_groups:
            text.append(" TOP GRUPOS\n", style="bold cyan")
            self._sep(text)
            for grp, cnt in s.top_groups:
                display = grp if len(grp) <= 30 else grp[:27] + "…"
                text.append(f" {display}", style="default")
                text.append(f"  {cnt}×\n", style="dim")
            text.append("\n")

        # ── Top Categorias ────────────────────────────────────────────────
        if s.top_categories:
            text.append(" TOP CATEGORIAS\n", style="bold cyan")
            self._sep(text)
            for cat, cnt in s.top_categories:
                display = cat if len(cat) <= 30 else cat[:27] + "…"
                text.append(f" {display}", style="default")
                text.append(f"  {cnt}×\n", style="dim")
            text.append("\n")

        # ── Alertas ───────────────────────────────────────────────────────
        text.append(" ALERTAS\n", style="bold cyan")
        self._sep(text)
        if not s.fs_loaded:
            text.append(" Carregando…\n", style="dim")
        elif not s.partial_items:
            text.append(" Nenhum alerta ✓\n", style="green dim")
        else:
            for item in s.partial_items[:8]:
                display = item if len(item) <= 34 else item[:31] + "…"
                text.append(f" ⚠ {display}\n", style="yellow")
            if len(s.partial_items) > 8:
                extra = len(s.partial_items) - 8
                text.append(f" … e mais {extra}\n", style="yellow dim")

        return text
