"""Testes para upapasta/ui.py — PhaseBar, _TeeStream, format_time."""
from __future__ import annotations

import io
import sys
from unittest.mock import patch

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
    from unittest.mock import MagicMock
    terminal = MagicMock(spec=io.TextIOBase)
    terminal.encoding = "latin-1"
    logfile = io.StringIO()
    tee = _TeeStream(terminal, logfile)
    assert tee.encoding == "latin-1"


def test_tee_encoding_fallback_utf8():
    # Quando o stream não tem encoding (getattr retorna None/ausente), usa utf-8
    from unittest.mock import MagicMock
    terminal = MagicMock(spec=io.RawIOBase)  # sem atributo encoding
    del terminal.encoding
    logfile = io.StringIO()
    tee = _TeeStream(terminal, logfile)
    assert tee.encoding == "utf-8"


# ---------------------------------------------------------------------------
# PhaseBar — lifecycle completo
# ---------------------------------------------------------------------------


def _capture_renders(bar: PhaseBar, actions) -> list[str]:
    """Executa ações e captura todas as linhas impressas por _render."""
    prints: list[str] = []
    original_print = print

    def fake_print(*args, **kwargs):
        prints.append(args[0] if args else "")

    with patch("upapasta.ui.print", side_effect=fake_print):
        for action, phase in actions:
            getattr(bar, action)(phase)
    return prints


def test_phasebar_estado_inicial_pending():
    bar = PhaseBar()
    for phase in PhaseBar.PHASES:
        assert bar._state[phase] == "pending"


def test_phasebar_start_muda_estado_para_active():
    bar = PhaseBar()
    with patch("upapasta.ui.print"):
        bar.start("NFO")
    assert bar._state["NFO"] == "active"


def test_phasebar_done_muda_estado_para_done():
    bar = PhaseBar()
    with patch("upapasta.ui.print"), patch("upapasta.ui.time") as mock_time:
        mock_time.time.return_value = 0.0
        bar.start("NFO")
        mock_time.time.return_value = 5.0
        bar.done("NFO")
    assert bar._state["NFO"] == "done"
    assert bar._elapsed["NFO"] == pytest.approx(5.0)


def test_phasebar_skip_nao_renderiza():
    bar = PhaseBar()
    renders = _capture_renders(bar, [("skip", "RAR")])
    assert bar._state["RAR"] == "skipped"
    assert renders == []


def test_phasebar_error_muda_estado():
    bar = PhaseBar()
    with patch("upapasta.ui.print"), patch("upapasta.ui.time") as mock_time:
        mock_time.time.return_value = 0.0
        bar.start("PAR2")
        mock_time.time.return_value = 3.0
        bar.error("PAR2")
    assert bar._state["PAR2"] == "error"


def test_phasebar_render_contem_todas_as_fases():
    bar = PhaseBar()
    prints: list[str] = []

    def fake_print(*args, **kwargs):
        prints.append(args[0] if args else "")

    with patch("upapasta.ui.print", side_effect=fake_print):
        bar.start("NFO")

    assert prints
    line = prints[-1]
    for phase in PhaseBar.PHASES:
        assert phase in line


def test_phasebar_fmt_active_contem_reticencias():
    bar = PhaseBar()
    bar._state["UPLOAD"] = "active"
    resultado = bar._fmt("UPLOAD")
    assert "..." in resultado


def test_phasebar_fmt_done_contem_tempo():
    bar = PhaseBar()
    bar._state["NFO"] = "done"
    bar._elapsed["NFO"] = 90.0  # 1m30s
    resultado = bar._fmt("NFO")
    assert "01:30" in resultado


def test_phasebar_fmt_skipped_usa_icone():
    bar = PhaseBar()
    bar._state["RAR"] = "skipped"
    resultado = bar._fmt("RAR")
    assert PhaseBar._ICONS["skipped"] in resultado


def test_phasebar_fmt_error_usa_icone():
    bar = PhaseBar()
    bar._state["PAR2"] = "error"
    resultado = bar._fmt("PAR2")
    assert PhaseBar._ICONS["error"] in resultado


def test_phasebar_done_sem_start_nao_quebra():
    bar = PhaseBar()
    with patch("upapasta.ui.print"):
        bar.done("DONE")  # nunca chamou start("DONE")
    assert bar._state["DONE"] == "done"
    assert "DONE" not in bar._elapsed
