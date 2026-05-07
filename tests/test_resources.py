"""Testes para upapasta/resources.py."""

from __future__ import annotations

from unittest.mock import mock_open, patch

import pytest

from upapasta.resources import (
    calculate_optimal_resources,
    get_mem_available_mb,
    get_total_size,
)

# ---------------------------------------------------------------------------
# get_mem_available_mb
# ---------------------------------------------------------------------------

PROC_MEMINFO_SAMPLE = """\
MemTotal:       16384000 kB
MemFree:         2048000 kB
MemAvailable:    8192000 kB
Buffers:          512000 kB
"""


def test_get_mem_available_mb_parses_proc_meminfo():
    with patch("builtins.open", mock_open(read_data=PROC_MEMINFO_SAMPLE)):
        result = get_mem_available_mb()
    assert result == 8000  # 8192000 kB // 1024


def test_get_mem_available_mb_fallback_on_ioerror():
    with patch("builtins.open", side_effect=OSError("sem /proc")):
        result = get_mem_available_mb()
    assert result == 2048


def test_get_mem_available_mb_fallback_on_bad_format():
    # /proc/meminfo sem linha MemAvailable
    broken = "MemTotal: 16384000 kB\nMemFree: 2048000 kB\n"
    with patch("builtins.open", mock_open(read_data=broken)):
        result = get_mem_available_mb()
    assert result == 2048


# ---------------------------------------------------------------------------
# get_total_size
# ---------------------------------------------------------------------------


def test_get_total_size_file(tmp_path):
    f = tmp_path / "arquivo.bin"
    f.write_bytes(b"x" * 1000)
    assert get_total_size(str(f)) == 1000


def test_get_total_size_directory(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 500)
    (tmp_path / "b.bin").write_bytes(b"x" * 300)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.bin").write_bytes(b"x" * 200)
    assert get_total_size(str(tmp_path)) == 1000


def test_get_total_size_ignores_symlinks(tmp_path):
    real = tmp_path / "real.bin"
    real.write_bytes(b"x" * 400)
    link = tmp_path / "link.bin"
    link.symlink_to(real)
    # Symlink não é contado; apenas o arquivo real
    assert get_total_size(str(tmp_path)) == 400


def test_get_total_size_empty_directory(tmp_path):
    assert get_total_size(str(tmp_path)) == 0


# ---------------------------------------------------------------------------
# calculate_optimal_resources — overrides manuais
# ---------------------------------------------------------------------------


def _calc(size_bytes: int, **kw):
    with patch("upapasta.resources.get_mem_available_mb", return_value=8192):
        with patch("os.cpu_count", return_value=8):
            return calculate_optimal_resources(size_bytes, **kw)


def test_user_threads_override():
    result = _calc(1 * 1024**3, user_threads=3)
    assert result["threads"] == 3
    assert result["par_threads"] == 3


def test_user_threads_clamped_to_one():
    result = _calc(1 * 1024**3, user_threads=0)
    assert result["threads"] == 1
    assert result["par_threads"] == 1


def test_user_memory_override():
    result = _calc(1 * 1024**3, user_memory_mb=1024)
    assert result["max_memory_mb"] == 1024


def test_user_memory_clamped_to_256():
    result = _calc(1 * 1024**3, user_memory_mb=10)
    assert result["max_memory_mb"] == 256


# ---------------------------------------------------------------------------
# calculate_optimal_resources — faixas de tamanho
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "size_gb, expected_conservative",
    [
        (1, False),
        (50, False),
        (100, False),
        (201, True),
    ],
)
def test_conservative_mode_by_size(size_gb, expected_conservative):
    result = _calc(size_gb * 1024**3)
    assert result["conservative_mode"] is expected_conservative


def test_conservative_mode_by_low_memory():
    with patch("upapasta.resources.get_mem_available_mb", return_value=2048):
        with patch("os.cpu_count", return_value=8):
            result = calculate_optimal_resources(1 * 1024**3)
    assert result["conservative_mode"] is True


def test_total_gb_rounded():
    result = _calc(int(1.5 * 1024**3))
    assert result["total_gb"] == pytest.approx(1.5, rel=0.01)


# ---------------------------------------------------------------------------
# calculate_optimal_resources — limites de memória
# ---------------------------------------------------------------------------


def test_memory_cap_at_8192():
    # mem_avail muito alto não deve ultrapassar o cap de 8 GB
    with patch("upapasta.resources.get_mem_available_mb", return_value=32768):
        with patch("os.cpu_count", return_value=8):
            result = calculate_optimal_resources(1 * 1024**3)
    assert result["max_memory_mb"] <= 8192


def test_memory_minimum_512():
    # mem_avail muito baixo → mínimo de 512 MB
    with patch("upapasta.resources.get_mem_available_mb", return_value=512):
        with patch("os.cpu_count", return_value=2):
            result = calculate_optimal_resources(1 * 1024**3)
    assert result["max_memory_mb"] >= 512


# ---------------------------------------------------------------------------
# calculate_optimal_resources — estrutura do retorno
# ---------------------------------------------------------------------------


def test_return_keys():
    result = _calc(1 * 1024**3)
    assert set(result.keys()) == {
        "threads",
        "par_threads",
        "max_memory_mb",
        "conservative_mode",
        "total_gb",
    }


def test_threads_at_least_one():
    result = _calc(1 * 1024**3)
    assert result["threads"] >= 1
    assert result["par_threads"] >= 1
