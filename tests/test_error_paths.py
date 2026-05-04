"""Testes para error paths diferenciados e backend par2."""
import io
import logging
import subprocess

from upapasta.makepar import make_parity
from upapasta.orchestrator import UpaPastaOrchestrator
from upapasta.ui import setup_logging

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _orch(tmp_path, **kwargs):
    dummy = tmp_path / "input"
    dummy.mkdir(exist_ok=True)
    return UpaPastaOrchestrator(input_path=str(dummy), dry_run=False, **kwargs)


# ---------------------------------------------------------------------------
# #4 — Error handling diferenciado em run_makepar
# ---------------------------------------------------------------------------

def test_run_makepar_permission_error_returns_false(tmp_path, monkeypatch):
    target = tmp_path / "show.rar"
    target.write_bytes(b"R")

    def fake_make_parity(*args, **kwargs):
        raise PermissionError("sem acesso")

    monkeypatch.setattr("upapasta.orchestrator.make_parity", fake_make_parity)

    o = _orch(tmp_path)
    o.input_target = str(target)
    assert o.run_makepar() is False


def test_run_makepar_oserror_returns_false(tmp_path, monkeypatch):
    target = tmp_path / "show.rar"
    target.write_bytes(b"R")

    def fake_make_parity(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("upapasta.orchestrator.make_parity", fake_make_parity)

    o = _orch(tmp_path)
    o.input_target = str(target)
    assert o.run_makepar() is False


def test_run_makerar_permission_error_returns_false(tmp_path, monkeypatch):
    folder = tmp_path / "MyShow"
    folder.mkdir()

    def fake_make_rar(path, force, threads=None, **kwargs):
        raise PermissionError("sem acesso")

    monkeypatch.setattr("upapasta.orchestrator.make_rar", fake_make_rar)

    o = UpaPastaOrchestrator(input_path=str(folder), dry_run=False)
    assert o.run_makerar() is False


def test_run_makerar_oserror_returns_false(tmp_path, monkeypatch):
    folder = tmp_path / "MyShow"
    folder.mkdir()

    def fake_make_rar(path, force, threads=None, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("upapasta.orchestrator.make_rar", fake_make_rar)

    o = UpaPastaOrchestrator(input_path=str(folder), dry_run=False)
    assert o.run_makerar() is False


# ---------------------------------------------------------------------------
# #3 — Cleanup sem rar_file (só par_file)
# ---------------------------------------------------------------------------

def test_cleanup_only_par_file(tmp_path):
    par = tmp_path / "show.par2"
    vol = tmp_path / "show.vol0+1.par2"
    par.write_bytes(b"P")
    vol.write_bytes(b"V")

    o = _orch(tmp_path)
    o.rar_file = None
    o.par_file = str(par)
    o.cleanup()

    assert not par.exists()
    assert not vol.exists()


def test_cleanup_deduplication_does_not_double_delete(tmp_path):
    """Garante que a deduplicação não causa erro ao deletar o mesmo arquivo duas vezes."""
    rar = tmp_path / "show.rar"
    par = tmp_path / "show.par2"
    rar.write_bytes(b"R")
    par.write_bytes(b"P")

    o = _orch(tmp_path)
    o.rar_file = str(rar)
    o.par_file = str(par)
    o.cleanup()  # não deve lançar exceção

    assert not rar.exists()
    assert not par.exists()


# ---------------------------------------------------------------------------
# #3 — Backend par2 em make_parity
# ---------------------------------------------------------------------------

class DummyPopenPar2:
    def __init__(self, args_passed, *a, **kw):
        self.stdout = io.StringIO("creating recovery files...\n")
        self._out_par2 = None
        # par2 create -rN out.par2 file → out.par2 is args[3]
        if args_passed and len(args_passed) > 3:
            self._out_par2 = args_passed[3]

    def wait(self, timeout=None):
        if self._out_par2:
            try:
                open(self._out_par2, "w").close()
            except Exception:
                pass
        return 0

    def poll(self):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


def test_make_parity_par2_backend(monkeypatch, tmp_path):
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy")

    import upapasta.makepar as makepar_module

    monkeypatch.setattr(makepar_module, "find_par2", lambda: ("par2", "/usr/bin/par2"))
    monkeypatch.setattr(makepar_module, "find_parpar", lambda: None)
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *args, **kwargs: DummyPopenPar2(args[0] if args else None, **kwargs),
    )

    rc = make_parity(str(input_file), redundancy=10, force=True, backend="par2", profile="balanced")
    assert rc == 0
    assert (tmp_path / "video.par2").exists()


# ---------------------------------------------------------------------------
# #3 — makepar FileNotFoundError → código 4
# ---------------------------------------------------------------------------

def test_make_parity_file_not_found_returns_4(monkeypatch, tmp_path):
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy")

    import upapasta.makepar as makepar_module

    monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/fake/parpar"))
    monkeypatch.setattr(makepar_module, "find_par2", lambda: None)

    def boom(*args, **kwargs):
        raise FileNotFoundError("parpar not found")

    monkeypatch.setattr(subprocess, "Popen", boom)

    rc = make_parity(str(input_file), redundancy=10, force=True, backend="parpar", profile="balanced")
    assert rc == 4


# ---------------------------------------------------------------------------
# #6 — setup_logging com log_file
# ---------------------------------------------------------------------------

def test_setup_logging_creates_file_handler(tmp_path):
    log_path = tmp_path / "upapasta.log"
    root = logging.getLogger("upapasta")
    # limpa handlers anteriores para não poluir outros testes
    root.handlers.clear()

    setup_logging(verbose=False, log_file=str(log_path))

    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].baseFilename == str(log_path)

    # limpa para não vazar estado
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)


def test_setup_logging_no_file_handler_by_default():
    root = logging.getLogger("upapasta")
    root.handlers.clear()

    setup_logging(verbose=False)

    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0

    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
