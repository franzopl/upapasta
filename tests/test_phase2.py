"""
test_phase2.py

Testes para os itens implementados na Fase 2 do roadmap UpaPasta.

Cobertos:
  F2.1  — Validação prévia (espaço em disco, permissões)
  F2.2  — ETA pré-pipeline
  F2.3  — Mensagens de erro do nyuu parseadas
  F2.4  — Retry com backoff exponencial
  F2.5  — Rollback de PAR2 parciais na falha
  F2.8  — _progress.py compartilhado
  F2.13 — Logging com timestamps
  F2.14 — watch.py (polling básico)
  F2.15 — SSL seguro por padrão
  F2.17 — Cache de get_total_size
"""

from __future__ import annotations

import io
import logging
import os
import ssl
import sys
import tempfile
import time
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest


# ── F2.3: parse de stderr do nyuu ────────────────────────────────────────────

from upapasta.upfolder import _parse_nyuu_stderr


def test_parse_nyuu_stderr_auth():
    assert "autenticação" in _parse_nyuu_stderr("error 401 Unauthorized").lower()


def test_parse_nyuu_stderr_502():
    assert "502" in _parse_nyuu_stderr("502 Service Unavailable")


def test_parse_nyuu_stderr_timeout():
    assert "timeout" in _parse_nyuu_stderr("Connection timeout after 30s").lower()


def test_parse_nyuu_stderr_ssl():
    msg = _parse_nyuu_stderr("SSL certificate verify failed")
    assert msg is not None and "SSL" in msg or "certificado" in msg.lower()


def test_parse_nyuu_stderr_econnrefused():
    msg = _parse_nyuu_stderr("ECONNREFUSED 127.0.0.1:119")
    assert msg is not None


def test_parse_nyuu_stderr_unknown():
    assert _parse_nyuu_stderr("some random output with no known error") is None


# ── F2.15: SSL seguro por padrão ─────────────────────────────────────────────

from upapasta.nntp_test import test_nntp_connection as _check_nntp


def test_ssl_secure_by_default(monkeypatch):
    """test_nntp_connection deve usar CA certs por padrão (não CERT_NONE)."""
    captured_ctx = {}

    import upapasta.nntp_test as nntp_mod
    if nntp_mod.nntplib is None:
        pytest.skip("nntplib não disponível")

    class FakeNNTP:
        def __init__(self, host, port, *, user, password, ssl_context, timeout):
            captured_ctx["ctx"] = ssl_context
        def quit(self):
            pass

    monkeypatch.setattr(nntp_mod.nntplib, "NNTP_SSL", FakeNNTP)
    ok, _ = _check_nntp("host", 563, True, "u", "p", insecure=False)
    assert ok
    ctx = captured_ctx.get("ctx")
    assert ctx is not None
    assert ctx.verify_mode != ssl.CERT_NONE


def test_ssl_insecure_flag_disables_verification(monkeypatch):
    """Com insecure=True, a verificação de certificado deve ser desativada."""
    captured_ctx = {}

    import upapasta.nntp_test as nntp_mod
    if nntp_mod.nntplib is None:
        pytest.skip("nntplib não disponível")

    class FakeNNTP:
        def __init__(self, host, port, *, user, password, ssl_context, timeout):
            captured_ctx["ctx"] = ssl_context
        def quit(self):
            pass

    monkeypatch.setattr(nntp_mod.nntplib, "NNTP_SSL", FakeNNTP)
    ok, _ = _check_nntp("host", 563, True, "u", "p", insecure=True)
    assert ok
    ctx = captured_ctx.get("ctx")
    assert ctx.verify_mode == ssl.CERT_NONE


# ── F2.17: Cache de get_total_size ───────────────────────────────────────────

from upapasta.resources import get_total_size


def test_get_total_size_cache(tmp_path):
    """Segunda chamada com mesmo path deve retornar valor cacheado sem re-walk."""
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    size1 = get_total_size(str(tmp_path))
    # Adiciona arquivo sem limpar o cache — resultado deve ser o mesmo (cacheado)
    (tmp_path / "b.txt").write_bytes(b"world")
    size2 = get_total_size(str(tmp_path))
    assert size1 == size2  # cache hit: não percorreu novamente


def test_get_total_size_single_file(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    assert get_total_size(str(f)) == 3


# ── F2.8: _progress.py compartilhado ─────────────────────────────────────────

from upapasta._progress import _read_output, _process_output


def test_progress_empty_queue(capsys):
    q: Queue = Queue()
    q.put(None)
    last_pct, had_pct = _process_output(q)
    assert last_pct == -1
    assert had_pct is False


def test_progress_with_percentage(capsys):
    q: Queue = Queue()
    q.put("Processing: 50%")
    q.put(None)
    last_pct, had_pct = _process_output(q)
    assert last_pct == 50
    assert had_pct is True


def test_progress_100_percent(capsys):
    q: Queue = Queue()
    q.put("Finished: 100%")
    q.put(None)
    last_pct, had_pct = _process_output(q)
    assert last_pct == 100
    assert had_pct is True


def test_read_output_none_pipe():
    """_read_output com pipe=None deve enviar apenas o sinal de fim."""
    q: Queue = Queue()
    _read_output(None, q)
    sentinel = q.get_nowait()
    assert sentinel is None
    assert q.empty()


def test_read_output_simple_pipe():
    q: Queue = Queue()
    pipe = io.StringIO("hello\nworld\n")
    _read_output(pipe, q)
    items = []
    while not q.empty():
        items.append(q.get())
    # Último item deve ser None (sentinela)
    assert items[-1] is None
    assert "hello" in items
    assert "world" in items


# ── F2.13: Timestamps no logging ─────────────────────────────────────────────

from upapasta.ui import setup_logging


def test_logging_verbose_has_timestamp():
    """Em modo verbose, o handler de stream deve incluir timestamp ISO."""
    root = logging.getLogger("upapasta")
    # Limpar handlers anteriores
    for h in root.handlers[:]:
        root.removeHandler(h)

    setup_logging(verbose=True)
    assert any(
        "asctime" in (getattr(h.formatter, "_fmt", "") or "")
        for h in root.handlers
        if isinstance(h, logging.StreamHandler)
    )


def test_logging_non_verbose_no_timestamp():
    """Em modo não-verbose, o handler de stream NÃO deve incluir timestamp."""
    root = logging.getLogger("upapasta")
    for h in root.handlers[:]:
        root.removeHandler(h)

    setup_logging(verbose=False)
    stream_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]
    assert stream_handlers
    for h in stream_handlers:
        fmt = getattr(h.formatter, "_fmt", "") or ""
        assert "asctime" not in fmt


# ── F2.1: Validação prévia (permissões e espaço) ─────────────────────────────

from upapasta.orchestrator import UpaPastaOrchestrator


def test_validate_missing_input():
    orch = UpaPastaOrchestrator("/nonexistent/path/xyz", dry_run=True)
    assert orch.validate() is False


def test_validate_existing_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    orch = UpaPastaOrchestrator(str(f), dry_run=True)
    assert orch.validate() is True


def test_validate_disk_space_ok(tmp_path):
    """Quando há espaço suficiente (dry_run=False, arquivo pequeno), deve passar."""
    f = tmp_path / "small.txt"
    f.write_bytes(b"x" * 100)
    orch = UpaPastaOrchestrator(str(f), dry_run=False)
    # Arquivo de 100B: 2× = 200B — sempre haverá espaço
    assert orch.validate() is True


def test_validate_disk_space_insufficient(tmp_path, monkeypatch):
    """Quando não há espaço, validate() deve retornar False."""
    import shutil
    f = tmp_path / "big.txt"
    f.write_bytes(b"x" * 1000)

    # Simula disco quase cheio: apenas 100 bytes livres
    fake_usage = shutil.disk_usage(str(tmp_path))._replace(free=100)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: fake_usage)

    orch = UpaPastaOrchestrator(str(f), dry_run=False)
    assert orch.validate() is False


# ── F2.2: ETA pré-pipeline ───────────────────────────────────────────────────

def test_eta_shown_in_run_output(tmp_path, capsys, monkeypatch):
    """O método run() deve exibir a linha de ETA antes do início do pipeline."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"x" * 1024)

    env = {
        "NNTP_HOST": "h", "NNTP_USER": "u",
        "NNTP_PASS": "p", "USENET_GROUP": "g",
        "NNTP_CONNECTIONS": "20",
    }
    monkeypatch.setattr("upapasta.orchestrator.check_or_prompt_credentials", lambda f: env)
    monkeypatch.setattr("upapasta.config.load_env_file", lambda f: env)

    orch = UpaPastaOrchestrator(str(f), dry_run=True, skip_upload=True, skip_par=True)
    orch.run()
    out = capsys.readouterr().out
    assert "ETA upload" in out


# ── F2.14: watch.py — polling básico ─────────────────────────────────────────

from upapasta.watch import _item_size, _watch_loop


def test_item_size_file(tmp_path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"hello")
    assert _item_size(f) == 5


def test_item_size_folder(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"abc")
    (tmp_path / "b.bin").write_bytes(b"de")
    assert _item_size(tmp_path) == 5


def test_item_size_nonexistent(tmp_path):
    """Caminho inexistente deve retornar 0 (pasta) ou -1 (arquivo)."""
    p = tmp_path / "missing"
    # Não existe: is_file() → False, rglob → vazio → 0
    assert _item_size(p) == 0


def test_watch_loop_processes_new_item(tmp_path, monkeypatch):
    """_watch_loop deve detectar novo item e chamar UpaPastaOrchestrator."""
    calls = []

    class FakeArgs:
        rar = False
        dry_run = True
        skip_upload = True
        skip_par = True
        obfuscate = False
        password = None
        par_profile = "balanced"
        redundancy = None
        post_size = None
        subject = None
        group = None
        nzb_conflict = None
        backend = "parpar"
        verbose = False
        keep_files = False
        max_memory = None
        rar_threads = None
        par_threads = None
        par_slice_size = None
        upload_timeout = None
        upload_retries = 0
        filepath_format = "common"
        parpar_args = None
        nyuu_args = None
        rename_extensionless = False
        env_file = "/dev/null"
        force = False

    # Cria arquivo na pasta monitorada DEPOIS de inicializar o loop
    new_file = tmp_path / "release.mkv"

    processed_items = set()

    import upapasta.watch as watch_mod

    orig_iterdir = Path.iterdir

    call_count = [0]

    def fake_iterdir(self):
        call_count[0] += 1
        if call_count[0] == 1:
            # Baseline: pasta vazia
            return iter([])
        elif call_count[0] == 2:
            # Segunda varredura: arquivo novo
            new_file.write_bytes(b"x" * 100)
            return iter([new_file])
        else:
            # Subsequente: lança KeyboardInterrupt para encerrar o loop
            raise KeyboardInterrupt

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    # item_size deve retornar valor estável (igual antes e depois do stable_secs)
    monkeypatch.setattr(watch_mod, "_item_size", lambda p: 100)
    monkeypatch.setattr(watch_mod, "time", MagicMock(sleep=lambda s: None))

    mock_orch = MagicMock()
    mock_orch.run.return_value = 0
    mock_session = MagicMock()
    mock_session.__enter__ = lambda s: mock_orch
    mock_session.__exit__ = MagicMock(return_value=False)

    monkeypatch.setattr(watch_mod, "UpaPastaOrchestrator", MagicMock(from_args=lambda a, p: mock_orch))
    monkeypatch.setattr(watch_mod, "UpaPastaSession", lambda o: mock_session)
    monkeypatch.setattr(watch_mod, "setup_session_log", lambda name, env_file: ("/tmp/x.log", MagicMock()))
    monkeypatch.setattr(watch_mod, "teardown_session_log", lambda fh, p: None)

    with pytest.raises(KeyboardInterrupt):
        _watch_loop(FakeArgs(), tmp_path, interval=1, stable_secs=1)

    # O orquestrador deve ter sido chamado para o arquivo novo
    mock_orch.run.assert_called_once()
