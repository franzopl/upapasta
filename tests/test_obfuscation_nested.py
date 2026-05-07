"""
obfuscate_and_par em pasta com 3 níveis de subpastas:
  - apenas o nome do diretório raiz é renomeado
  - subpastas e arquivos internos preservam nomes
  - reversão em KeyboardInterrupt restaura nome do root
"""

import io
import os
import subprocess

import pytest

from upapasta import makepar as makepar_module
from upapasta.makepar import obfuscate_and_par


def _mktree(root):
    (root / "10. A" / "1. X").mkdir(parents=True)
    (root / "10. A" / "1. X" / "aula.mp4").write_bytes(b"a" * 1024)
    (root / "10. A" / "leia.txt").write_text("ok")
    (root / "11. B").mkdir()
    (root / "11. B" / "doc.pdf").write_bytes(b"p" * 1024)


class _OkPopen:
    def __init__(self, argv=None, *a, **kw):
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


class _RaisingPopen(_OkPopen):
    def wait(self, timeout=None):
        raise KeyboardInterrupt


@pytest.fixture
def fake_parpar(monkeypatch):
    monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))


def test_obfuscation_only_renames_root(fake_parpar, monkeypatch, tmp_path):
    root = tmp_path / "Release [2025]"
    root.mkdir()
    _mktree(root)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **kw: _OkPopen(a[0] if a else None, **kw),
    )

    rc, new_path, mapping, _linked = obfuscate_and_par(
        str(root),
        redundancy=5,
        force=True,
        backend="parpar",
        threads=1,
    )
    assert rc == 0
    assert new_path is not None and os.path.isdir(new_path)

    # Subpastas e arquivos originais preservados dentro do root ofuscado
    assert os.path.join(new_path, "10. A", "1. X", "aula.mp4")
    assert os.path.exists(os.path.join(new_path, "10. A", "1. X", "aula.mp4"))
    assert os.path.exists(os.path.join(new_path, "10. A", "leia.txt"))
    assert os.path.exists(os.path.join(new_path, "11. B", "doc.pdf"))
    # Mapa contém o root original
    assert "Release [2025]" in mapping.values()


def test_obfuscation_reverts_on_keyboard_interrupt(fake_parpar, monkeypatch, tmp_path):
    root = tmp_path / "Release [2025]"
    root.mkdir()
    _mktree(root)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **kw: _RaisingPopen(a[0] if a else None, **kw),
    )

    with pytest.raises(KeyboardInterrupt):
        obfuscate_and_par(
            str(root),
            redundancy=5,
            force=True,
            backend="parpar",
            threads=1,
        )

    # Root original deve ter voltado
    assert root.exists() and root.is_dir()
    assert (root / "10. A" / "1. X" / "aula.mp4").exists()
