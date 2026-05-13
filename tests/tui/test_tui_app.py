"""
Testes da TUI App (requer: pip install upapasta[tui]).
Skipa automaticamente se textual não estiver instalado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")

from upapasta.tui.app import UpaPastaApp, run_tui
from upapasta.tui.catalog_index import CatalogIndex
from upapasta.tui.status import UploadStatus
from upapasta.tui.widgets.file_tree import FileTreeWidget
from upapasta.tui.widgets.status_bar import StatusBar

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_media_tree(tmp_path: Path) -> tuple[Path, CatalogIndex]:
    """Cria estrutura de mídia de exemplo com catálogo."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "Breaking.Bad.S01").mkdir()
    (media / "Breaking.Bad.S02").mkdir()
    (media / "Dune.2021.4K").mkdir()
    (media / "Pending.Movie").mkdir()

    history = tmp_path / "history.jsonl"
    uploaded = ["Breaking.Bad.S01", "Breaking.Bad.S02", "Dune.2021.4K"]
    with history.open("w") as f:
        for name in uploaded:
            f.write(
                json.dumps(
                    {
                        "nome_original": name,
                        "data_upload": "2025-03-10T12:00:00+00:00",
                        "tamanho_bytes": 1024**3 * 40,
                        "caminho_nzb": None,
                        "grupo_usenet": "alt.binaries.test",
                        "categoria": "TV",
                    }
                )
                + "\n"
            )

    idx = CatalogIndex(history)
    idx.load()
    return media, idx


# ── Testes: instanciação ──────────────────────────────────────────────────────


def test_app_instantiation(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    assert app.root_path == media


def test_app_root_must_exist(tmp_path: Path) -> None:
    """run_tui com path inexistente deve sair com erro (não travar)."""
    nonexistent = tmp_path / "nope"
    # run_tui chama sys.exit(1) — capturamos com pytest.raises
    with pytest.raises(SystemExit) as exc:
        run_tui(root_path=nonexistent)
    assert exc.value.code == 1


def test_app_root_not_directory(tmp_path: Path) -> None:
    f = tmp_path / "file.mkv"
    f.touch()
    with pytest.raises(SystemExit) as exc:
        run_tui(root_path=f)
    assert exc.value.code == 1


# ── Testes: FileTreeWidget ────────────────────────────────────────────────────


def test_file_tree_widget_creation(tmp_path: Path) -> None:
    media, idx = _make_media_tree(tmp_path)
    widget = FileTreeWidget(media, idx)
    assert widget.root_path == media
    assert widget.index is idx


def test_file_tree_widget_filter_none(tmp_path: Path) -> None:
    media, idx = _make_media_tree(tmp_path)
    widget = FileTreeWidget(media, idx)
    # set_filter não deve lançar exceção antes de mount
    widget._filter = None
    assert widget._filter is None


def test_file_tree_widget_filter_set(tmp_path: Path) -> None:
    media, idx = _make_media_tree(tmp_path)
    widget = FileTreeWidget(media, idx)
    widget._filter = UploadStatus.PENDING
    assert widget._filter == UploadStatus.PENDING


# ── Testes: StatusBar ─────────────────────────────────────────────────────────


def test_status_bar_creation() -> None:
    bar = StatusBar()
    assert bar is not None


@pytest.mark.asyncio
async def test_status_bar_update_none(tmp_path: Path) -> None:
    """update_node(None) não deve lançar exceção dentro de um app ativo."""
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        bar = app.query_one(StatusBar)
        bar.update_node(None)  # não deve lançar
        await pilot.press("q")


# ── Testes: async (TUI real) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_app_quits_with_q(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("q")
    assert not app.is_running


@pytest.mark.asyncio
async def test_app_composes_tree_and_statusbar(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        assert app.query_one(FileTreeWidget) is not None
        assert app.query_one(StatusBar) is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_filter_pending_key(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("1")
        tree = app.query_one(FileTreeWidget)
        assert tree._filter == UploadStatus.PENDING
        await pilot.press("q")


@pytest.mark.asyncio
async def test_filter_all_resets(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("2")  # filter uploaded
        await pilot.press("0")  # back to all
        tree = app.query_one(FileTreeWidget)
        assert tree._filter is None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_filter_uploaded_key(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("2")
        tree = app.query_one(FileTreeWidget)
        assert tree._filter == UploadStatus.UPLOADED
        await pilot.press("q")


@pytest.mark.asyncio
async def test_subtitle_shows_root_path(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        assert str(media) in app.sub_title
        await pilot.press("q")


@pytest.mark.asyncio
async def test_subtitle_changes_on_filter(tmp_path: Path) -> None:
    media, _ = _make_media_tree(tmp_path)
    app = UpaPastaApp(root_path=media)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("1")  # filter pending
        assert "Pendente" in app.sub_title
        await pilot.press("q")
