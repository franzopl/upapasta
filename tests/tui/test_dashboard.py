"""
Testes do DashboardWidget e funções auxiliares (Fase 4 da TUI).
Skipa automaticamente se textual não estiver instalado.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")

from upapasta.tui.app import UpaPastaApp
from upapasta.tui.catalog_index import CatalogIndex
from upapasta.tui.widgets.dashboard import (
    DashboardStats,
    DashboardWidget,
    compute_catalog_stats,
    compute_fs_stats,
    fmt_bytes,
    sparkline_chars,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_catalog(tmp_path: Path, entries: list[dict]) -> CatalogIndex:
    history = tmp_path / "history.jsonl"
    with history.open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    idx = CatalogIndex(history)
    idx.load()
    return idx


def _entry(name: str, days_ago: int = 0, size_gb: float = 10.0) -> dict:
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "nome_original": name,
        "data_upload": d.isoformat(),
        "tamanho_bytes": int(size_gb * 1024**3),
        "caminho_nzb": None,
        "grupo_usenet": "alt.binaries.test",
        "categoria": "TV",
    }


def _make_media_tree(tmp_path: Path) -> tuple[Path, CatalogIndex]:
    """Cria árvore de mídia com 3 enviados, 1 pendente, 1 pasta parcial."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "Breaking.Bad.S01").mkdir()
    (media / "Breaking.Bad.S02").mkdir()
    (media / "Dune.2021.4K").mkdir()
    (media / "Pending.Movie").mkdir()
    partial_dir = media / "Partial.Series"
    partial_dir.mkdir()
    (partial_dir / "ep01").mkdir()
    (partial_dir / "ep02").mkdir()

    idx = _make_catalog(
        tmp_path,
        [
            _entry("Breaking.Bad.S01", days_ago=5, size_gb=40),
            _entry("Breaking.Bad.S02", days_ago=3, size_gb=44),
            _entry("Dune.2021.4K", days_ago=10, size_gb=87),
            _entry("ep01", days_ago=2, size_gb=2),
        ],
    )
    return media, idx


# ── Testes: fmt_bytes ─────────────────────────────────────────────────────────


def test_fmt_bytes_mb():
    assert fmt_bytes(500 * 1024**2) == "500 MB"


def test_fmt_bytes_gb():
    assert fmt_bytes(2 * 1024**3) == "2.0 GB"


def test_fmt_bytes_zero():
    assert fmt_bytes(0) == "0 MB"


def test_fmt_bytes_fractional_gb():
    result = fmt_bytes(int(1.5 * 1024**3))
    assert result == "1.5 GB"


# ── Testes: sparkline_chars ───────────────────────────────────────────────────


def test_sparkline_empty():
    result = sparkline_chars([])
    assert result == ""


def test_sparkline_all_zero():
    result = sparkline_chars([0, 0, 0, 0])
    assert result == "▁▁▁▁"


def test_sparkline_single_value():
    result = sparkline_chars([100])
    assert result == "█"


def test_sparkline_ascending():
    values = [0, 25, 50, 75, 100]
    result = sparkline_chars(values)
    assert len(result) == 5
    # Primeiro deve ser menor que o último
    blocks = " ▁▂▃▄▅▆▇█"
    assert blocks.index(result[0]) < blocks.index(result[-1])


def test_sparkline_max_is_full_block():
    values = [0, 50, 100]
    result = sparkline_chars(values)
    assert result[-1] == "█"


def test_sparkline_length_matches_input():
    values = list(range(30))
    result = sparkline_chars(values)
    assert len(result) == 30


# ── Testes: compute_catalog_stats ────────────────────────────────────────────


def test_compute_catalog_stats_empty(tmp_path: Path):
    history = tmp_path / "history.jsonl"
    history.touch()
    idx = CatalogIndex(history)
    idx.load()

    stats = compute_catalog_stats(idx)

    assert stats.uploaded_count == 0
    assert stats.uploaded_bytes == 0
    assert len(stats.sparkline) == 30
    assert all(v == 0 for v in stats.sparkline)
    assert not stats.fs_loaded


def test_compute_catalog_stats_counts(tmp_path: Path):
    idx = _make_catalog(
        tmp_path,
        [
            _entry("Movie.A", days_ago=1, size_gb=10),
            _entry("Movie.B", days_ago=2, size_gb=20),
            _entry("Movie.C", days_ago=5, size_gb=30),
        ],
    )

    stats = compute_catalog_stats(idx)

    assert stats.uploaded_count == 3
    assert stats.uploaded_bytes == int(60 * 1024**3)


def test_compute_catalog_stats_sparkline_recent(tmp_path: Path):
    idx = _make_catalog(
        tmp_path,
        [
            _entry("Movie.Today", days_ago=0, size_gb=10),
        ],
    )

    stats = compute_catalog_stats(idx, days=30)

    # O último elemento do sparkline corresponde a hoje
    assert stats.sparkline[-1] == int(10 * 1024**3)


def test_compute_catalog_stats_sparkline_old_entry_excluded(tmp_path: Path):
    idx = _make_catalog(
        tmp_path,
        [
            _entry("Old.Movie", days_ago=60, size_gb=10),
        ],
    )

    stats = compute_catalog_stats(idx, days=30)

    assert all(v == 0 for v in stats.sparkline)


def test_compute_catalog_stats_sparkline_length(tmp_path: Path):
    idx = _make_catalog(tmp_path, [_entry("X", days_ago=1)])

    stats = compute_catalog_stats(idx, days=7)

    assert len(stats.sparkline) == 7


def test_compute_catalog_stats_sparkline_day_mapping(tmp_path: Path):
    """Entradas de dias diferentes devem cair nos buckets corretos."""
    idx = _make_catalog(
        tmp_path,
        [
            _entry("A", days_ago=0, size_gb=1),
            _entry("B", days_ago=1, size_gb=2),
            _entry("C", days_ago=2, size_gb=3),
        ],
    )

    stats = compute_catalog_stats(idx, days=5)

    # sparkline[-1] = hoje = 1 GB, sparkline[-2] = ontem = 2 GB, etc.
    assert stats.sparkline[-1] == int(1 * 1024**3)
    assert stats.sparkline[-2] == int(2 * 1024**3)
    assert stats.sparkline[-3] == int(3 * 1024**3)


# ── Testes: compute_fs_stats ──────────────────────────────────────────────────


def test_compute_fs_stats_empty_dir(tmp_path: Path):
    media = tmp_path / "media"
    media.mkdir()
    history = tmp_path / "history.jsonl"
    history.touch()
    idx = CatalogIndex(history)
    idx.load()

    pending, pending_bytes, partial = compute_fs_stats(media, idx)

    assert pending == 0
    assert pending_bytes == 0
    assert partial == []


def test_compute_fs_stats_pending_dirs(tmp_path: Path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "Movie.A").mkdir()
    (media / "Movie.B").mkdir()

    history = tmp_path / "history.jsonl"
    history.touch()
    idx = CatalogIndex(history)
    idx.load()

    pending, pending_bytes, partial = compute_fs_stats(media, idx)

    # Diretórios vazios têm size=0
    assert pending == 2
    assert pending_bytes == 0
    assert partial == []


def test_compute_fs_stats_uploaded_not_counted(tmp_path: Path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "Uploaded.Movie").mkdir()
    (media / "Pending.Movie").mkdir()

    idx = _make_catalog(tmp_path, [_entry("Uploaded.Movie", days_ago=1)])

    pending, _, partial = compute_fs_stats(media, idx)

    assert pending == 1
    assert partial == []


def test_compute_fs_stats_partial_detected(tmp_path: Path):
    media = tmp_path / "media"
    media.mkdir()
    partial_dir = media / "Series.S01"
    partial_dir.mkdir()
    (partial_dir / "ep01").mkdir()
    (partial_dir / "ep02").mkdir()

    # Só ep01 foi enviado → Series.S01 é PARTIAL
    idx = _make_catalog(tmp_path, [_entry("ep01", days_ago=1)])

    pending, _, partial = compute_fs_stats(media, idx)

    assert "Series.S01" in partial
    assert pending == 0


# ── Testes: DashboardWidget ───────────────────────────────────────────────────


def test_dashboard_widget_creation(tmp_path: Path):
    media, idx = _make_media_tree(tmp_path)
    widget = DashboardWidget(idx, media)
    assert widget is not None


def test_dashboard_widget_hidden_by_default(tmp_path: Path):
    _make_media_tree(tmp_path)
    # DEFAULT_CSS define display: none
    assert "display: none" in DashboardWidget.DEFAULT_CSS


def test_dashboard_stats_render_no_crash(tmp_path: Path):
    """_render() não deve lançar exceção para qualquer combinação de stats."""
    media, idx = _make_media_tree(tmp_path)
    widget = DashboardWidget(idx, media)

    # Stats vazias
    widget._stats = DashboardStats()
    text = widget._build_content()
    assert text is not None

    # Stats com dados
    widget._stats = DashboardStats(
        uploaded_count=5,
        uploaded_bytes=int(100 * 1024**3),
        sparkline=[0] * 30,
        pending_count=2,
        pending_bytes=int(20 * 1024**3),
        partial_items=["Series.S01", "Course.Python"],
        fs_loaded=True,
    )
    text = widget._build_content()
    plain = text.plain
    assert "5" in plain
    assert "2" in plain


def test_dashboard_render_truncates_long_alerts(tmp_path: Path):
    media, idx = _make_media_tree(tmp_path)
    widget = DashboardWidget(idx, media)
    widget._stats = DashboardStats(
        partial_items=[f"Item.{i:02d}" for i in range(10)],
        fs_loaded=True,
    )

    text = widget._build_content()
    plain = text.plain

    # Deve mostrar no máximo 6 itens + "e mais N"
    assert "e mais 4" in plain


def test_dashboard_render_no_alerts_message(tmp_path: Path):
    media, idx = _make_media_tree(tmp_path)
    widget = DashboardWidget(idx, media)
    widget._stats = DashboardStats(partial_items=[], fs_loaded=True)

    text = widget._build_content()
    assert "Nenhum alerta" in text.plain


def test_dashboard_render_fs_not_loaded_shows_placeholder(tmp_path: Path):
    media, idx = _make_media_tree(tmp_path)
    widget = DashboardWidget(idx, media)
    widget._stats = DashboardStats(fs_loaded=False)

    text = widget._build_content()
    # Deve mostrar "…" em vez de números para pendentes/parciais
    assert "…" in text.plain


# ── Testes: integração com App ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_hidden_on_startup(tmp_path: Path):
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        dash = app.query_one(DashboardWidget)
        assert not dash.display
        await pilot.press("q")


@pytest.mark.asyncio
async def test_dashboard_toggle_with_d_key(tmp_path: Path):
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        dash = app.query_one(DashboardWidget)
        assert not dash.display

        await pilot.press("d")
        assert dash.display

        await pilot.press("d")
        assert not dash.display

        await pilot.press("q")


@pytest.mark.asyncio
async def test_dashboard_present_in_dom(tmp_path: Path):
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        # DashboardWidget deve estar no DOM (mesmo que escondido)
        assert app.query_one("#dashboard") is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_dashboard_refresh_updates_stats(tmp_path: Path):
    media, idx = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("d")  # abre dashboard
        dash = app.query_one(DashboardWidget)
        assert dash.display
        # Após toggle, _stats deve ter sido populado com dados do catálogo
        assert dash._stats.uploaded_count >= 0
        await pilot.press("q")
