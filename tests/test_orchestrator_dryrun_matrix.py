"""
Matriz parametrizada de cenarios para make_parity, cobrindo combinacoes
relevantes de tipo de entrada, backend e formato de path.

Foco: garantir que o argv passado ao binario externo reflete as escolhas
do usuario em todos os cenarios suportados, e que paths de pastas
aninhadas sao percorridos integralmente.
"""

import io
import subprocess

import pytest

from upapasta import makepar as makepar_module
from upapasta.makepar import make_parity

_argv: list = []


class _RecPopen:
    def __init__(self, argv=None, *a, **kw):
        _argv.clear()
        if argv:
            _argv.extend(argv)
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
def fake_bins(monkeypatch):
    monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))
    monkeypatch.setattr(makepar_module, "find_par2", lambda: ("par2", "/bin/true"))
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **kw: _RecPopen(a[0] if a else None, **kw),
    )


def _mk_single(tmp):
    f = tmp / "movie.mkv"
    f.write_bytes(b"x" * 4096)
    return f


def _mk_flat(tmp):
    d = tmp / "flat"
    d.mkdir()
    (d / "a.bin").write_bytes(b"a" * 2048)
    (d / "b.bin").write_bytes(b"b" * 2048)
    return d


def _mk_nested(tmp):
    d = tmp / "nested"
    (d / "s1" / "deep").mkdir(parents=True)
    (d / "s1" / "deep" / "x.bin").write_bytes(b"x" * 2048)
    (d / "s2").mkdir()
    (d / "s2" / "y.bin").write_bytes(b"y" * 2048)
    (d / "z.bin").write_bytes(b"z" * 2048)
    return d


@pytest.mark.parametrize("entry_kind", ["single", "flat", "nested"])
@pytest.mark.parametrize("backend", ["parpar", "par2"])
@pytest.mark.parametrize("filepath_format", ["common", "keep", "basename", "outrel"])
def test_make_parity_argv_matrix(fake_bins, tmp_path, entry_kind, backend, filepath_format):
    if entry_kind == "single":
        target = _mk_single(tmp_path)
        expected_inputs = {str(target)}
    elif entry_kind == "flat":
        target = _mk_flat(tmp_path)
        expected_inputs = {str(target / "a.bin"), str(target / "b.bin")}
    else:
        target = _mk_nested(tmp_path)
        expected_inputs = {
            str(target / "s1" / "deep" / "x.bin"),
            str(target / "s2" / "y.bin"),
            str(target / "z.bin"),
        }

    rc = make_parity(
        str(target),
        redundancy=5,
        force=True,
        backend=backend,
        threads=1,
        filepath_format=filepath_format,
    )
    assert rc == 0

    # Inputs sempre presentes, indep. de backend/format
    for inp in expected_inputs:
        assert inp in _argv, f"{inp} ausente para {entry_kind}/{backend}/{filepath_format}"

    # -f so aparece com parpar
    if backend == "parpar":
        assert "-f" in _argv
        assert _argv[_argv.index("-f") + 1] == filepath_format
    else:
        assert "-f" not in _argv


@pytest.mark.parametrize(
    "extra",
    [
        None,
        [],
        ["--noindex"],
        ["--foo=bar", "--baz"],
    ],
)
def test_parpar_extra_args_matrix(fake_bins, tmp_path, extra):
    f = _mk_single(tmp_path)
    rc = make_parity(
        str(f),
        redundancy=5,
        force=True,
        backend="parpar",
        threads=1,
        parpar_extra_args=extra,
    )
    assert rc == 0
    if extra:
        for tok in extra:
            assert tok in _argv
            # tokens devem vir antes do arquivo de input
            assert _argv.index(tok) < _argv.index(str(f))


def test_normalize_revert_roundtrip(tmp_path):
    """Smoke: normalize_extensionless e revert_extensionless sao inversos."""
    from upapasta.orchestrator import normalize_extensionless, revert_extensionless

    root = tmp_path / "tree"
    (root / "sub").mkdir(parents=True)
    (root / "README").write_text("a")
    (root / "sub" / "DATA").write_text("b")
    (root / "video.mkv").write_text("c")

    snapshot_before = sorted(p.name for p in root.rglob("*") if p.is_file())
    mapping = normalize_extensionless(str(root))
    revert_extensionless(mapping)
    snapshot_after = sorted(p.name for p in root.rglob("*") if p.is_file())

    assert snapshot_before == snapshot_after
