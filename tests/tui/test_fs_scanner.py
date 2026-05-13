"""Testes para upapasta.tui.fs_scanner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from upapasta.tui.catalog_index import CatalogIndex
from upapasta.tui.fs_scanner import _fmt_size, scan_directory, scan_single
from upapasta.tui.status import UploadStatus

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_catalog(tmp_path: Path, names: list[str]) -> CatalogIndex:
    f = tmp_path / "history.jsonl"
    with f.open("w") as fh:
        for name in names:
            record = {
                "nome_original": name,
                "data_upload": "2025-01-15T10:00:00+00:00",
                "tamanho_bytes": 1024 * 1024 * 100,
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


# ── Testes: arquivo ───────────────────────────────────────────────────────────


def test_file_uploaded(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.write_bytes(b"x" * 100)
    idx = _make_catalog(tmp_path, ["movie.mkv"])
    node = scan_single(f, idx)
    assert node.status == UploadStatus.UPLOADED
    assert node.is_dir is False
    assert node.upload_entry is not None


def test_file_pending(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.write_bytes(b"x" * 100)
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    assert node.status == UploadStatus.PENDING
    assert node.upload_entry is None


def test_file_size_is_set(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_bytes(b"x" * 512)
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    assert node.size == 512


def test_file_name_property(tmp_path: Path) -> None:
    f = tmp_path / "Breaking.Bad.S01.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    assert node.name == "Breaking.Bad.S01.mkv"


def test_file_upload_date_when_uploaded(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _make_catalog(tmp_path, ["movie.mkv"])
    node = scan_single(f, idx)
    assert node.upload_date is not None
    assert node.upload_date.year == 2025


def test_file_upload_date_when_pending(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(f, idx)
    assert node.upload_date is None


# ── Testes: diretório ─────────────────────────────────────────────────────────


def test_dir_uploaded_when_in_catalog(tmp_path: Path) -> None:
    d = tmp_path / "Breaking.Bad.S01"
    d.mkdir()
    (d / "ep01.mkv").touch()
    idx = _make_catalog(tmp_path, ["Breaking.Bad.S01"])
    node = scan_single(d, idx)
    assert node.status == UploadStatus.UPLOADED
    assert node.is_dir is True


def test_dir_pending_when_no_children_uploaded(tmp_path: Path) -> None:
    d = tmp_path / "New.Series"
    d.mkdir()
    (d / "ep01.mkv").touch()
    (d / "ep02.mkv").touch()
    idx = _empty_catalog(tmp_path)
    node = scan_single(d, idx)
    assert node.status == UploadStatus.PENDING


def test_dir_partial_when_some_children_uploaded(tmp_path: Path) -> None:
    d = tmp_path / "Course.Python"
    d.mkdir()
    (d / "lesson01").mkdir()
    (d / "lesson02").mkdir()
    (d / "lesson03").mkdir()
    idx = _make_catalog(tmp_path, ["lesson01", "lesson02"])
    node = scan_single(d, idx)
    assert node.status == UploadStatus.PARTIAL
    assert node.child_total == 3
    assert node.child_uploaded == 2


def test_dir_uploaded_when_all_children_uploaded(tmp_path: Path) -> None:
    d = tmp_path / "Complete.Series"
    d.mkdir()
    (d / "S01").mkdir()
    (d / "S02").mkdir()
    idx = _make_catalog(tmp_path, ["S01", "S02"])
    node = scan_single(d, idx)
    assert node.status == UploadStatus.UPLOADED


def test_empty_dir_is_pending(tmp_path: Path) -> None:
    d = tmp_path / "Empty.Folder"
    d.mkdir()
    idx = _empty_catalog(tmp_path)
    node = scan_single(d, idx)
    assert node.status == UploadStatus.PENDING


def test_dir_size_is_zero_lazy(tmp_path: Path) -> None:
    d = tmp_path / "Big.Folder"
    d.mkdir()
    (d / "huge.file").write_bytes(b"x" * 1000)
    idx = _empty_catalog(tmp_path)
    node = scan_single(d, idx)
    assert node.size == 0  # lazy — não calculado no scan


# ── Testes: scan_directory ────────────────────────────────────────────────────


def test_scan_directory_returns_immediate_children(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "Movie.A").mkdir()
    (media / "Movie.B").mkdir()
    (media / "file.txt").touch()

    # Subpasta não deve aparecer como filho de media via scan
    sub = media / "Movie.A" / "deep"
    sub.mkdir()

    idx = _empty_catalog(tmp_path)
    nodes = scan_directory(media, idx)
    names = [n.name for n in nodes]
    assert "Movie.A" in names
    assert "Movie.B" in names
    assert "file.txt" in names
    assert "deep" not in names


def test_scan_directory_dirs_first(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "z_file.txt").touch()
    (media / "a_file.mkv").touch()
    (media / "M.Folder").mkdir()
    (media / "A.Folder").mkdir()

    idx = _empty_catalog(tmp_path)
    nodes = scan_directory(media, idx)

    dir_nodes = [n for n in nodes if n.is_dir]
    file_nodes = [n for n in nodes if not n.is_dir]

    # Todos os dirs vêm antes dos arquivos
    assert nodes.index(dir_nodes[-1]) < nodes.index(file_nodes[0])


def test_scan_directory_sorted_alphabetically(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "Z.Movie").mkdir()
    (media / "A.Movie").mkdir()
    (media / "M.Movie").mkdir()

    idx = _empty_catalog(tmp_path)
    nodes = scan_directory(media, idx)
    names = [n.name for n in nodes]
    assert names == ["A.Movie", "M.Movie", "Z.Movie"]


def test_scan_directory_status_assigned(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "Uploaded.Movie").mkdir()
    (media / "Pending.Movie").mkdir()

    idx = _make_catalog(tmp_path, ["Uploaded.Movie"])
    nodes = scan_directory(media, idx)

    node_map = {n.name: n for n in nodes}
    assert node_map["Uploaded.Movie"].status == UploadStatus.UPLOADED
    assert node_map["Pending.Movie"].status == UploadStatus.PENDING


def test_scan_directory_raises_on_file(tmp_path: Path) -> None:
    f = tmp_path / "not_a_dir.txt"
    f.touch()
    idx = _empty_catalog(tmp_path)
    with pytest.raises(ValueError, match="Não é um diretório"):
        scan_directory(f, idx)


def test_scan_directory_empty(tmp_path: Path) -> None:
    d = tmp_path / "empty"
    d.mkdir()
    idx = _empty_catalog(tmp_path)
    nodes = scan_directory(d, idx)
    assert nodes == []


def test_scan_directory_case_insensitive_match(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "Breaking.Bad.S01").mkdir()

    # Catálogo com nome em caixa diferente
    idx = _make_catalog(tmp_path, ["breaking.bad.s01"])
    nodes = scan_directory(media, idx)
    assert nodes[0].status == UploadStatus.UPLOADED


def test_scan_directory_nzb_path_none_when_no_nzb(tmp_path: Path) -> None:
    f = tmp_path / "movie.mkv"
    f.touch()
    idx = _make_catalog(tmp_path, ["movie.mkv"])
    node = scan_single(f, idx)
    # caminho_nzb é None no fixture — deve retornar None
    assert node.nzb_path is None


# ── Testes: _fmt_size ─────────────────────────────────────────────────────────


def test_fmt_size_bytes() -> None:
    assert _fmt_size(512) == "512 B"


def test_fmt_size_kilobytes() -> None:
    result = _fmt_size(2048)
    assert "KB" in result


def test_fmt_size_megabytes() -> None:
    result = _fmt_size(5 * 1024 * 1024)
    assert "MB" in result


def test_fmt_size_gigabytes() -> None:
    result = _fmt_size(2 * 1024**3)
    assert "GB" in result


def test_fmt_size_zero() -> None:
    assert _fmt_size(0) == "0 B"
