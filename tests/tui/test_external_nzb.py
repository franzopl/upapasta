"""
Testes para detecção de NZB externo e de senha (tui/external_nzb.py),
e para a integração próprio + externo no scanner de filesystem.
"""

from __future__ import annotations

import json
from pathlib import Path

from upapasta.tui.catalog_index import CatalogIndex
from upapasta.tui.external_nzb import ExternalNzbIndex, nzb_has_password
from upapasta.tui.fs_scanner import scan_single
from upapasta.tui.status import UploadStatus

# ── Helpers ───────────────────────────────────────────────────────────────────

_FILE_BLOCK = (
    '<file poster="p" date="1" subject="s">'
    "<groups><group>a.b.c</group></groups>"
    '<segments><segment bytes="1" number="1">id</segment></segments>'
    "</file>"
)


def _write_nzb(path: Path, *, password: str | None = None, head: bool = True) -> None:
    """Grava um .nzb mínimo. password=None e head=True → head sem senha."""
    head_xml = ""
    if head:
        meta = f'<meta type="password">{password}</meta>' if password is not None else ""
        head_xml = f"<head>{meta}</head>"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nzb xmlns="http://www.newznab.com/DTD/2003/nzb">'
        f"{head_xml}{_FILE_BLOCK}</nzb>",
        encoding="utf-8",
    )


def _write_history(path: Path, name: str, *, senha: str | None = None) -> None:
    record = {
        "nome_original": name,
        "data_upload": "2025-06-15T10:00:00+00:00",
        "tamanho_bytes": 1024,
        "caminho_nzb": None,
        "grupo_usenet": "a.b.c",
        "categoria": "Movie",
        "senha_rar": senha,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# ── nzb_has_password ──────────────────────────────────────────────────────────


def test_nzb_with_password_detected(tmp_path: Path) -> None:
    nzb = tmp_path / "x.nzb"
    _write_nzb(nzb, password="segredo123")
    assert nzb_has_password(nzb) is True


def test_nzb_without_password(tmp_path: Path) -> None:
    nzb = tmp_path / "x.nzb"
    _write_nzb(nzb)
    assert nzb_has_password(nzb) is False


def test_nzb_empty_password_is_false(tmp_path: Path) -> None:
    nzb = tmp_path / "x.nzb"
    _write_nzb(nzb, password="")
    assert nzb_has_password(nzb) is False


def test_nzb_no_head_is_false(tmp_path: Path) -> None:
    nzb = tmp_path / "x.nzb"
    _write_nzb(nzb, head=False)
    assert nzb_has_password(nzb) is False


def test_nzb_password_string_after_file_ignored(tmp_path: Path) -> None:
    """type="password" fora do <head> (ex.: dentro de um subject) não conta."""
    nzb = tmp_path / "x.nzb"
    nzb.write_text(
        '<?xml version="1.0"?><nzb xmlns="x"><head></head>'
        '<file poster="p" date="1" subject="meta type=&quot;password&quot;">'
        "<groups><group>g</group></groups>"
        '<segments><segment bytes="1" number="1">id</segment></segments></file></nzb>',
        encoding="utf-8",
    )
    assert nzb_has_password(nzb) is False


def test_nzb_missing_file_returns_false(tmp_path: Path) -> None:
    assert nzb_has_password(tmp_path / "inexistente.nzb") is False


def test_nzb_single_quotes_attribute(tmp_path: Path) -> None:
    nzb = tmp_path / "x.nzb"
    nzb.write_text(
        "<nzb xmlns='x'><head><meta type='password'>pw</meta></head>" + _FILE_BLOCK + "</nzb>",
        encoding="utf-8",
    )
    assert nzb_has_password(nzb) is True


# ── ExternalNzbIndex ──────────────────────────────────────────────────────────


def test_external_index_lookup_by_full_name(tmp_path: Path) -> None:
    _write_nzb(tmp_path / "Filme.mkv.nzb")
    idx = ExternalNzbIndex([tmp_path])
    idx.scan()
    info = idx.lookup("Filme.mkv")
    assert info is not None
    assert info.has_password is False


def test_external_index_lookup_by_stem(tmp_path: Path) -> None:
    """'Filme.nzb' deve casar tanto 'Filme' quanto 'Filme.mkv' (via stem)."""
    _write_nzb(tmp_path / "Filme.nzb")
    idx = ExternalNzbIndex([tmp_path])
    idx.scan()
    assert idx.is_present("Filme") is True
    assert idx.is_present("Filme.mkv") is True


def test_external_index_password_flag(tmp_path: Path) -> None:
    _write_nzb(tmp_path / "ComSenha.mkv.nzb", password="abc")
    idx = ExternalNzbIndex([tmp_path])
    idx.scan()
    info = idx.lookup("ComSenha.mkv")
    assert info is not None and info.has_password is True


def test_external_index_absent(tmp_path: Path) -> None:
    idx = ExternalNzbIndex([tmp_path])
    idx.scan()
    assert idx.lookup("qualquer") is None
    assert idx.is_present("qualquer") is False


def test_external_index_rescan_uses_cache(tmp_path: Path) -> None:
    """Re-scan de arquivo inalterado mantém o resultado de senha."""
    nzb = tmp_path / "Filme.mkv.nzb"
    _write_nzb(nzb, password="x")
    idx = ExternalNzbIndex([tmp_path])
    idx.scan()
    idx.scan()
    info = idx.lookup("Filme.mkv")
    assert info is not None and info.has_password is True


# ── Integração: NZB próprio + externo no scanner ──────────────────────────────


def test_node_has_both_own_and_external(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    target = src / "movie.mkv"
    target.touch()

    history = tmp_path / "history.jsonl"
    _write_history(history, "movie.mkv")

    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    _write_nzb(ext_dir / "movie.mkv.nzb")

    index = CatalogIndex(history, external_nzb_paths=[ext_dir])
    index.load()
    node = scan_single(target, index)

    assert node.has_own_nzb is True
    assert node.has_external_nzb is True
    assert node.status == UploadStatus.UPLOADED


def test_node_own_with_password_external_without(tmp_path: Path) -> None:
    """1 upload (próprio) com senha, backup externo sem senha."""
    src = tmp_path / "src"
    src.mkdir()
    target = src / "movie.mkv"
    target.touch()

    history = tmp_path / "history.jsonl"
    _write_history(history, "movie.mkv", senha="rarpass")

    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    _write_nzb(ext_dir / "movie.mkv.nzb")  # sem senha

    index = CatalogIndex(history, external_nzb_paths=[ext_dir])
    index.load()
    node = scan_single(target, index)

    assert node.own_has_password is True
    assert node.external_has_password is False
    assert node.password_protected is True


def test_node_external_with_password_own_without(tmp_path: Path) -> None:
    """Backup externo com senha, upload próprio sem senha."""
    src = tmp_path / "src"
    src.mkdir()
    target = src / "movie.mkv"
    target.touch()

    history = tmp_path / "history.jsonl"
    _write_history(history, "movie.mkv", senha=None)

    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    _write_nzb(ext_dir / "movie.mkv.nzb", password="indexpass")

    index = CatalogIndex(history, external_nzb_paths=[ext_dir])
    index.load()
    node = scan_single(target, index)

    assert node.own_has_password is False
    assert node.external_has_password is True


def test_node_external_only(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    target = src / "movie.mkv"
    target.touch()

    history = tmp_path / "history.jsonl"
    history.touch()

    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    _write_nzb(ext_dir / "movie.mkv.nzb")

    index = CatalogIndex(history, external_nzb_paths=[ext_dir])
    index.load()
    node = scan_single(target, index)

    assert node.has_own_nzb is False
    assert node.has_external_nzb is True
    assert node.status == UploadStatus.EXTERNAL
