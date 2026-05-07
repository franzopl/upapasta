"""
Testa o passthrough de --filepath-format e --parpar-args para o parpar.

Garante que make_parity injeta -f <fmt> no argv do parpar e concatena tokens
extras de parpar_extra_args após as flags próprias mas antes da lista de
arquivos.
"""

import io
import subprocess

import pytest

from upapasta import makepar as makepar_module
from upapasta.makepar import make_parity

_captured_argv: list = []


class _RecordingPopen:
    def __init__(self, args_passed=None, *args, **kwargs):
        _captured_argv.clear()
        if args_passed:
            _captured_argv.extend(args_passed)
        self.stdout = io.StringIO("done\n")
        self._argv = args_passed

    def wait(self, timeout=None):
        if self._argv and "-o" in self._argv:
            out = self._argv[self._argv.index("-o") + 1]
            open(out, "w").close()
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
        subprocess,
        "Popen",
        lambda *args, **kw: _RecordingPopen(args[0] if args else None, **kw),
    )


def test_default_filepath_format_is_common(fake_parpar, tmp_path):
    f = tmp_path / "vid.mkv"
    f.write_bytes(b"x" * 1024)
    rc = make_parity(str(f), redundancy=5, force=True, backend="parpar", threads=1)
    assert rc == 0
    assert "-f" in _captured_argv
    assert _captured_argv[_captured_argv.index("-f") + 1] == "common"


def test_filepath_format_keep_passed_through(fake_parpar, tmp_path):
    f = tmp_path / "vid.mkv"
    f.write_bytes(b"x" * 1024)
    rc = make_parity(
        str(f),
        redundancy=5,
        force=True,
        backend="parpar",
        threads=1,
        filepath_format="keep",
    )
    assert rc == 0
    assert _captured_argv[_captured_argv.index("-f") + 1] == "keep"


@pytest.mark.parametrize("fmt", ["basename", "outrel", "common"])
def test_filepath_format_choices(fake_parpar, tmp_path, fmt):
    f = tmp_path / "vid.mkv"
    f.write_bytes(b"x" * 1024)
    rc = make_parity(
        str(f),
        redundancy=5,
        force=True,
        backend="parpar",
        threads=1,
        filepath_format=fmt,
    )
    assert rc == 0
    assert _captured_argv[_captured_argv.index("-f") + 1] == fmt


def test_parpar_extra_args_tokens_injected(fake_parpar, tmp_path):
    f = tmp_path / "vid.mkv"
    f.write_bytes(b"x" * 1024)
    rc = make_parity(
        str(f),
        redundancy=5,
        force=True,
        backend="parpar",
        threads=1,
        parpar_extra_args=["--noindex", "--foo=bar"],
    )
    assert rc == 0
    assert "--noindex" in _captured_argv
    assert "--foo=bar" in _captured_argv
    # Devem aparecer antes do arquivo de input (último elemento)
    assert _captured_argv.index("--noindex") < _captured_argv.index(str(f))


def test_filepath_format_par2_backend_ignored(monkeypatch, tmp_path):
    """Backend par2 não suporta -f: a flag deve ser silenciosamente ignorada."""
    f = tmp_path / "vid.mkv"
    f.write_bytes(b"x" * 1024)
    monkeypatch.setattr(makepar_module, "find_parpar", lambda: None)
    monkeypatch.setattr(makepar_module, "find_par2", lambda: ("par2", "/bin/true"))
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kw: _RecordingPopen(args[0] if args else None, **kw),
    )
    rc = make_parity(
        str(f),
        redundancy=5,
        force=True,
        backend="par2",
        threads=1,
        filepath_format="keep",
    )
    assert rc == 0
    assert "-f" not in _captured_argv  # par2 não recebe -f
