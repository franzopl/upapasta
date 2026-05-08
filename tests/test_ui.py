"""Testes para upapasta/ui.py — PhaseBar, _TeeStream, format_time."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from upapasta.ui import PhaseBar, _TeeStream, format_time

# ---------------------------------------------------------------------------
# format_time
# ---------------------------------------------------------------------------


def test_format_time_zero():
    assert format_time(0) == "00:00:00"


def test_format_time_negative():
    assert format_time(-5) == "00:00:00"


def test_format_time_seconds_only():
    assert format_time(45) == "00:00:45"


def test_format_time_minutes_and_seconds():
    assert format_time(125) == "00:02:05"


def test_format_time_hours():
    assert format_time(3661) == "01:01:01"


# ---------------------------------------------------------------------------
# _TeeStream — duplicação e strip de ANSI
# ---------------------------------------------------------------------------


def _make_tee() -> tuple[_TeeStream, io.StringIO, io.StringIO]:
    terminal = io.StringIO()
    logfile = io.StringIO()
    tee = _TeeStream(terminal, logfile)
    return tee, terminal, logfile


def test_tee_escreve_nos_dois_streams():
    tee, terminal, logfile = _make_tee()
    tee.write("olá\n")
    assert terminal.getvalue() == "olá\n"
    assert logfile.getvalue() == "olá\n"


def test_tee_retorna_len_do_input():
    tee, _, _ = _make_tee()
    n = tee.write("abc")
    assert n == 3


def test_tee_strip_ansi_no_log():
    tee, terminal, logfile = _make_tee()
    tee.write("\x1b[32mVerde\x1b[0m")
    assert terminal.getvalue() == "\x1b[32mVerde\x1b[0m"
    assert logfile.getvalue() == "Verde"


def test_tee_strip_ansi_movimento_cursor():
    tee, terminal, logfile = _make_tee()
    tee.write("\x1b[1A\x1b[2K texto")
    assert "\x1b[" not in logfile.getvalue()
    assert " texto" in logfile.getvalue()


def test_tee_mascara_senha_rar():
    tee, _, logfile = _make_tee()
    tee.write("senha rar: supersecreta\n")
    assert "supersecreta" not in logfile.getvalue()
    assert "***" in logfile.getvalue()


def test_tee_mascara_nntp_pass():
    tee, _, logfile = _make_tee()
    tee.write("NNTP_PASS=minhasenha123\n")
    assert "minhasenha123" not in logfile.getvalue()
    assert "***" in logfile.getvalue()


def test_tee_mascara_flag_hp():
    tee, _, logfile = _make_tee()
    tee.write("rar a -hpSENHA_SECRETA arquivo.rar\n")
    assert "SENHA_SECRETA" not in logfile.getvalue()
    assert "-hp***" in logfile.getvalue()


def test_tee_nao_mascara_terminal():
    tee, terminal, _ = _make_tee()
    tee.write("NNTP_PASS=abc123\n")
    assert "abc123" in terminal.getvalue()


def test_tee_flush_propaga():
    terminal = io.StringIO()
    logfile = io.StringIO()
    tee = _TeeStream(terminal, logfile)
    tee.flush()  # não deve lançar exceção


def test_tee_encoding_herda_do_original():
    # Usa mock para simular stream com encoding definido (ex: arquivo aberto em latin-1)
    terminal = MagicMock(spec=io.TextIOBase)
    terminal.encoding = "latin-1"
    logfile = io.StringIO()
    tee = _TeeStream(terminal, logfile)
    assert tee.encoding == "latin-1"


def test_tee_encoding_fallback_utf8():
    # Quando o stream não tem encoding (getattr retorna None/ausente), usa utf-8
    terminal = MagicMock(spec=io.RawIOBase)  # sem atributo encoding
    del terminal.encoding
    logfile = io.StringIO()
    tee = _TeeStream(terminal, logfile)
    assert tee.encoding == "utf-8"


# ---------------------------------------------------------------------------
# PhaseBar — lifecycle completo
# ---------------------------------------------------------------------------


def test_phasebar_estado_inicial_pending():
    bar = PhaseBar()
    for phase in PhaseBar.PHASES:
        assert bar._state[phase] == "pending"


def test_phasebar_start_muda_estado_para_active():
    bar = PhaseBar()
    bar.start("NFO")
    assert bar._state["NFO"] == "active"


def test_phasebar_done_muda_estado_para_done():
    bar = PhaseBar()
    with patch("upapasta.ui.time") as mock_time:
        mock_time.time.return_value = 0.0
        bar.start("NFO")
        mock_time.time.return_value = 5.0
        bar.done("NFO")
    assert bar._state["NFO"] == "done"
    assert bar._elapsed["NFO"] == pytest.approx(5.0)


def test_phasebar_skip_muda_estado():
    bar = PhaseBar()
    bar.skip("RAR")
    assert bar._state["RAR"] == "skipped"


def test_phasebar_error_muda_estado():
    bar = PhaseBar()
    with patch("upapasta.ui.time") as mock_time:
        mock_time.time.return_value = 0.0
        bar.start("PAR2")
        mock_time.time.return_value = 3.0
        bar.error("PAR2")
    assert bar._state["PAR2"] == "error"


def test_phasebar_render_group_contem_todas_as_fases():
    bar = PhaseBar()
    # Mock do tradutor _ para retornar a própria string
    with patch("upapasta.ui._", side_effect=lambda x: x):
        group = bar._render_group()
        # O group contém a tabela de fases. Vamos verificar se as fases estão lá.
        # Como o Rich renderiza para objetos complexos, vamos converter para texto simples para teste
        from rich.console import Console

        console = Console(width=100)
        with console.capture() as capture:
            console.print(group)
        output = capture.get()
        for phase in PhaseBar.PHASES:
            assert phase in output


def test_phasebar_update_progress_cria_task():
    bar = PhaseBar()
    bar.update_progress(50.0, "Testando")
    assert bar.active_task is not None
    task = bar.progress.tasks[0]
    assert task.completed == 50.0
    assert task.description == "Testando"


def test_phasebar_done_remove_task():
    bar = PhaseBar()
    bar.update_progress(100.0)
    assert bar.active_task is not None
    bar.done("RAR")
    assert bar.active_task is None
    assert len(bar.progress.tasks) == 0


def test_phasebar_done_sem_start_nao_quebra():
    bar = PhaseBar()
    bar.done("DONE")  # nunca chamou start("DONE")
    assert bar._state["DONE"] == "done"
    assert "DONE" not in bar._elapsed


def test_phasebar_metadata_render():
    meta = {"size": 10.5, "obfuscate": True, "password": "secret_pwd"}
    bar = PhaseBar(metadata=meta)
    with patch("upapasta.ui._", side_effect=lambda x: x):
        group = bar._render_group()
        from rich.console import Console

        console = Console(width=100)
        with console.capture() as capture:
            console.print(group)
        output = capture.get()
        assert "10.5 GB" in output
        assert "ON" in output
        assert "secret_pwd" in output


def test_phasebar_log_rotation():
    bar = PhaseBar()
    bar._max_logs = 2
    bar.log("msg1")
    bar.log("msg2")
    bar.log("msg3")
    assert len(bar._logs) == 2
    assert bar._logs == ["msg2", "msg3"]
