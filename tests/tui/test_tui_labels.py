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
