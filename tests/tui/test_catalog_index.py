"""Testes para upapasta.tui.catalog_index."""

from __future__ import annotations

import json
from pathlib import Path

from upapasta.tui.catalog_index import CatalogIndex, _parse_date

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _write_jsonl(path: Path, records: list[dict]) -> None:  # type: ignore[type-arg]
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_record(
    name: str,
    date: str = "2025-01-15T10:00:00+00:00",
    size: int = 1024,
    nzb: str | None = None,
) -> dict:  # type: ignore[type-arg]
    return {
        "nome_original": name,
        "data_upload": date,
        "tamanho_bytes": size,
        "caminho_nzb": nzb,
        "grupo_usenet": "alt.binaries.test",
        "categoria": "Movie",
    }


# ── Testes: load ──────────────────────────────────────────────────────────────


def test_load_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    f.write_text("")
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 0
    assert idx.total_entries() == 0


def test_load_nonexistent_file(tmp_path: Path) -> None:
    idx = CatalogIndex(tmp_path / "nope.jsonl")
    idx.load()
    assert idx.unique_names() == 0


def test_load_single_entry(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Breaking.Bad.S01")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 1
    assert idx.has("Breaking.Bad.S01")


def test_load_multiple_entries(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(
        f,
        [
            _make_record("Movie.A"),
            _make_record("Movie.B"),
            _make_record("Series.S01"),
        ],
    )
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 3


def test_load_skips_invalid_json_lines(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    with f.open("w") as fh:
        fh.write(json.dumps(_make_record("Valid.Movie")) + "\n")
        fh.write("THIS IS NOT JSON\n")
        fh.write(json.dumps(_make_record("Another.Movie")) + "\n")
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 2
    assert idx.has("Valid.Movie")
    assert idx.has("Another.Movie")


def test_load_skips_entries_without_name(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    with f.open("w") as fh:
        fh.write(json.dumps({"data_upload": "2025-01-01T00:00:00+00:00"}) + "\n")
        fh.write(json.dumps(_make_record("Good.Entry")) + "\n")
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 1
    assert idx.has("Good.Entry")


def test_load_skips_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    with f.open("w") as fh:
        fh.write("\n")
        fh.write(json.dumps(_make_record("Movie.X")) + "\n")
        fh.write("\n\n")
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 1


# ── Testes: lookup ────────────────────────────────────────────────────────────


def test_lookup_existing(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Dune.2021")])
    idx = CatalogIndex(f)
    idx.load()
    entry = idx.lookup("Dune.2021")
    assert entry is not None
    assert entry.nome_original == "Dune.2021"


def test_lookup_nonexistent_returns_none(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Dune.2021")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.lookup("NotInCatalog") is None


def test_lookup_case_insensitive(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Breaking.Bad.S01")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.lookup("breaking.bad.s01") is not None
    assert idx.lookup("BREAKING.BAD.S01") is not None
    assert idx.lookup("Breaking.Bad.S01") is not None


def test_lookup_returns_most_recent_entry(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(
        f,
        [
            _make_record("Series.S01", date="2025-01-01T00:00:00+00:00", size=100),
            _make_record("Series.S01", date="2025-06-15T00:00:00+00:00", size=200),
            _make_record("Series.S01", date="2025-03-01T00:00:00+00:00", size=150),
        ],
    )
    idx = CatalogIndex(f)
    idx.load()
    entry = idx.lookup("Series.S01")
    assert entry is not None
    assert entry.tamanho_bytes == 200  # a entrada mais recente


def test_lookup_all_returns_sorted_descending(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(
        f,
        [
            _make_record("Series.S01", date="2025-01-01T00:00:00+00:00"),
            _make_record("Series.S01", date="2025-06-01T00:00:00+00:00"),
        ],
    )
    idx = CatalogIndex(f)
    idx.load()
    entries = idx.lookup_all("Series.S01")
    assert len(entries) == 2
    assert entries[0].upload_date > entries[1].upload_date


# ── Testes: has ───────────────────────────────────────────────────────────────


def test_has_existing(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Movie.X")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.has("Movie.X") is True


def test_has_nonexistent(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Movie.X")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.has("Movie.Y") is False


def test_has_case_insensitive(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Movie.X")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.has("movie.x") is True
    assert idx.has("MOVIE.X") is True


# ── Testes: reload incremental ────────────────────────────────────────────────


def test_no_reload_when_file_unchanged(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Movie.A")])
    idx = CatalogIndex(f)
    idx.load()
    first_index_id = id(idx._index)
    idx.load()  # segunda chamada — arquivo não mudou
    assert id(idx._index) == first_index_id  # mesmo objeto, não recarregou


def test_reload_when_file_grows(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Movie.A")])
    idx = CatalogIndex(f)
    idx.load()
    assert idx.unique_names() == 1

    # Adiciona nova entrada
    with f.open("a") as fh:
        fh.write(json.dumps(_make_record("Movie.B")) + "\n")

    idx.load()
    assert idx.unique_names() == 2
    assert idx.has("Movie.B")


# ── Testes: métricas ──────────────────────────────────────────────────────────


def test_total_entries_counts_duplicates(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(
        f,
        [
            _make_record("Same.Name"),
            _make_record("Same.Name"),
            _make_record("Other.Name"),
        ],
    )
    idx = CatalogIndex(f)
    idx.load()
    assert idx.total_entries() == 3
    assert idx.unique_names() == 2


def test_total_bytes_sums_most_recent(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(
        f,
        [
            _make_record("Movie.A", size=1000),
            _make_record("Movie.B", size=2000),
        ],
    )
    idx = CatalogIndex(f)
    idx.load()
    assert idx.total_bytes() == 3000


def test_all_names_returns_lowercase(tmp_path: Path) -> None:
    f = tmp_path / "history.jsonl"
    _write_jsonl(f, [_make_record("Breaking.Bad.S01")])
    idx = CatalogIndex(f)
    idx.load()
    names = idx.all_names()
    assert "breaking.bad.s01" in names


# ── Testes: _parse_date ───────────────────────────────────────────────────────


def test_parse_date_iso_with_offset() -> None:
    dt = _parse_date("2025-01-15T10:30:00+00:00")
    assert dt.year == 2025
    assert dt.month == 1
    assert dt.day == 15


def test_parse_date_z_suffix() -> None:
    dt = _parse_date("2025-06-01T00:00:00Z")
    assert dt.year == 2025


def test_parse_date_invalid_returns_epoch() -> None:
    dt = _parse_date("not-a-date")
    assert dt.year == 1970


def test_parse_date_empty_returns_epoch() -> None:
    dt = _parse_date("")
    assert dt.year == 1970


def test_parse_date_none_returns_epoch() -> None:
    dt = _parse_date(None)  # type: ignore[arg-type]
    assert dt.year == 1970
