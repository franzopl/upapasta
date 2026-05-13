"""
Testes para geração de labels da árvore TUI.
Não requer textual instalado — testa apenas a lógica de formatação.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")

from rich.text import Text

from upapasta.tui.catalog_index import CatalogIndex
from upapasta.tui.fs_scanner import scan_single
from upapasta.tui.status import UploadStatus
from upapasta.tui.widgets.file_tree import make_node_label
from upapasta.tui.widgets.status_bar import _render

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_catalog(tmp_path: Path, names: list[str]) -> CatalogIndex:
    f = tmp_path / "history.jsonl"
    with f.open("w") as fh:
        for name in names:
            record = {
                "nome_original": name,
                "data_upload": "2025-06-15T10:00:00+00:00",
                "tamanho_bytes": 1024 * 1024 * 500,
                "caminho_nzb": None,
                "grupo_usenet": "alt.binaries.test",
                "categoria": "Movie",
            }
            fh.write(json.dumps(record) + "\n")
    idx = CatalogIndex(f)
    idx.load()
    return idx


def _empty_catalog(tmp_path: Path) -> CatalogIndex:
    return _make_catalog(tmp_path, [])


# ── Testes: make_node_label ────────────────────────────────────────────────────


def test_label_is_text_instance(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node)
    assert isinstance(label, Text)


def test_label_contains_filename(tmp_path: Path) -> None:
    f = tmp_path / "Breaking.Bad.S01.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node)
    assert "Breaking.Bad.S01.mkv" in label.plain


def test_label_contains_status_icon_pending(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node)
    assert UploadStatus.PENDING.icon in label.plain


def test_label_contains_status_icon_uploaded(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _make_catalog(tmp_path, ["movie.mkv"])
    node = scan_single(f, idx)
    label = make_node_label(node)
    assert UploadStatus.UPLOADED.icon in label.plain


def test_label_contains_upload_date_when_uploaded(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _make_catalog(tmp_path, ["movie.mkv"])
    node = scan_single(f, idx)
    label = make_node_label(node)
    assert "2025-06-15" in label.plain


def test_label_no_upload_date_when_pending(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node)
    assert "2025" not in label.plain


def test_label_dir_shows_folder_icon(tmp_path: Path) -> None:
    d = tmp_path / "Series"
    d.mkdir()
    idx = _empty_catalog(tmp_path)
    node = scan_single(d, idx)
    label = make_node_label(node)
    assert "📁" in label.plain


def test_label_partial_shows_count(tmp_path: Path) -> None:
    d = tmp_path / "Course"
    d.mkdir()
    (d / "lesson01").mkdir()
    (d / "lesson02").mkdir()
    (d / "lesson03").mkdir()
    idx = _make_catalog(tmp_path, ["lesson01"])
    node = scan_single(d, idx)
    assert node.status == UploadStatus.PARTIAL
    label = make_node_label(node)
    assert "1/3" in label.plain


def test_label_partial_shows_percentage(tmp_path: Path) -> None:
    d = tmp_path / "Course"
    d.mkdir()
    for i in range(4):
        (d / f"lesson{i:02d}").mkdir()
    idx = _make_catalog(tmp_path, ["lesson00", "lesson01"])
    node = scan_single(d, idx)
    assert node.status == UploadStatus.PARTIAL
    label = make_node_label(node)
    assert "50%" in label.plain


# ── Testes: _render (status bar) ──────────────────────────────────────────────


def test_render_none_shows_hint() -> None:
    text = _render(None)
    assert isinstance(text, Text)
    assert len(text.plain) > 0


def test_render_uploaded_shows_date(tmp_path: Path) -> None:
    f = tmp_path / "film.mkv"
    f.touch()
    idx = _make_catalog(tmp_path, ["film.mkv"])
    node = scan_single(f, idx)
    text = _render(node)
    assert "2025-06-15" in text.plain


def test_render_shows_filename(tmp_path: Path) -> None:
    f = tmp_path / "Dune.Part.Two.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    text = _render(node)
    assert "Dune.Part.Two.mkv" in text.plain


def test_render_shows_size(tmp_path: Path) -> None:
    f = tmp_path / "file.mkv"
    f.write_bytes(b"x" * 2048)
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    text = _render(node)
    # size_human deve aparecer (ex: "2.0 KB")
    assert "KB" in text.plain or "B" in text.plain


def test_render_partial_shows_subdir_count(tmp_path: Path) -> None:
    d = tmp_path / "BigCourse"
    d.mkdir()
    for i in range(5):
        (d / f"mod{i:02d}").mkdir()
    idx = _make_catalog(tmp_path, ["mod00", "mod01", "mod02"])
    node = scan_single(d, idx)
    assert node.status == UploadStatus.PARTIAL
    text = _render(node)
    assert "3/5" in text.plain


# ── Testes: make_node_label — selected ───────────────────────────────────────


def test_label_selected_shows_indicator(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node, selected=True)
    assert "◉" in label.plain


def test_label_unselected_no_indicator(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node, selected=False)
    assert "◉" not in label.plain


# ── Testes: make_node_label — query/highlight ─────────────────────────────────


def test_label_query_match_preserves_name(tmp_path: Path) -> None:
    f = tmp_path / "Breaking.Bad.S01.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node, query="Breaking")
    assert "Breaking.Bad.S01.mkv" in label.plain


def test_label_query_no_match_shows_full_name(tmp_path: Path) -> None:
    f = tmp_path / "Dune.2021.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label = make_node_label(node, query="Breaking")
    assert "Dune.2021.mkv" in label.plain


def test_label_query_case_insensitive(tmp_path: Path) -> None:
    f = tmp_path / "Breaking.Bad.S01.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    # Tanto com minúsculas quanto maiúsculas o nome aparece completo
    label_lower = make_node_label(node, query="breaking")
    label_upper = make_node_label(node, query="BREAKING")
    assert "Breaking.Bad.S01.mkv" in label_lower.plain
    assert "Breaking.Bad.S01.mkv" in label_upper.plain


def test_label_empty_query_no_highlight(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    label_with = make_node_label(node, query="")
    label_without = make_node_label(node)
    assert label_with.plain == label_without.plain


# ── Testes: FileTreeWidget — multi-select e busca ─────────────────────────────


def test_file_tree_initial_selection_empty(tmp_path: Path) -> None:
    from upapasta.tui.widgets.file_tree import FileTreeWidget

    idx = _empty_catalog(tmp_path)
    widget = FileTreeWidget(tmp_path, idx)
    assert widget.selected_nodes() == []
    assert widget._selected == {}


def test_file_tree_initial_query_empty(tmp_path: Path) -> None:
    from upapasta.tui.widgets.file_tree import FileTreeWidget

    idx = _empty_catalog(tmp_path)
    widget = FileTreeWidget(tmp_path, idx)
    assert widget._query == ""


def test_file_tree_set_search_updates_query(tmp_path: Path) -> None:
    from unittest.mock import patch

    from upapasta.tui.widgets.file_tree import FileTreeWidget

    idx = _empty_catalog(tmp_path)
    widget = FileTreeWidget(tmp_path, idx)
    with patch.object(widget, "_reload_root"):
        widget.set_search("breaking")
    assert widget._query == "breaking"


def test_status_bar_hint_contains_space() -> None:
    text = _render(None)
    assert "Space" in text.plain


def test_status_bar_hint_contains_search() -> None:
    text = _render(None)
    assert "/" in text.plain or "Buscar" in text.plain
