"""
Pasta com subpastas + --skip-rar deve passar ao parpar a árvore inteira
recursivamente, e make_parity deve sinalizar -f common no argv.
"""
import io
import subprocess

import pytest

from upapasta import makepar as makepar_module
from upapasta.makepar import make_parity


_captured: list = []


class _Pop:
    def __init__(self, argv=None, *a, **kw):
        _captured.clear()
        if argv:
            _captured.extend(argv)
        self.stdout = io.StringIO("ok\n")
        self._argv = argv

    def wait(self, timeout=None):
        if self._argv and "-o" in self._argv:
            open(self._argv[self._argv.index("-o") + 1], "w").close()
        return 0

    def poll(self):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


@pytest.fixture
def fake_parpar(monkeypatch):
    monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **kw: _Pop(a[0] if a else None, **kw),
    )


def _build_nested_tree(root):
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "c.bin").write_bytes(b"c" * 2048)
    (root / "a" / "d.bin").write_bytes(b"d" * 2048)
    (root / "e.bin").write_bytes(b"e" * 2048)


def test_make_parity_walks_full_tree_for_folder(fake_parpar, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _build_nested_tree(root)

    rc = make_parity(str(root), redundancy=5, force=True, backend="parpar", threads=1)
    assert rc == 0

    # Todos os 3 arquivos da árvore devem estar no argv passado ao parpar
    leaf_paths = [str(root / "a" / "b" / "c.bin"),
                  str(root / "a" / "d.bin"),
                  str(root / "e.bin")]
    for p in leaf_paths:
        assert p in _captured, f"{p} ausente do argv: {_captured}"


def test_filepath_format_common_present_for_nested(fake_parpar, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _build_nested_tree(root)

    rc = make_parity(str(root), redundancy=5, force=True, backend="parpar", threads=1)
    assert rc == 0
    assert "-f" in _captured
    assert _captured[_captured.index("-f") + 1] == "common"
