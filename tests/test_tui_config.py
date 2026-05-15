"""
Testes do wizard de configuração visual (tui_config.py).

Testa a lógica das fábricas de abas, coleta de valores, salvamento
e fallback — sem precisar de terminal real.
"""

from __future__ import annotations

import curses
from pathlib import Path
from unittest.mock import patch

import pytest


# curses.color_pair exige initscr() — mockamos para não precisar de terminal
@pytest.fixture(autouse=True)
def _mock_curses_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curses, "color_pair", lambda n: 0)


from upapasta.tui_config import (
    ConfigWizard,
    _make_tab_avancado,
    _make_tab_notificacoes,
    _make_tab_nzb,
    _make_tab_servidor,
    _make_tab_upload,
    _make_tab_verificacao,
    run_config_wizard,
)
from upapasta.tui_widgets import (
    Button,
    CheckBox,
    CollapsibleSection,
    Dropdown,
    FormPage,
    RadioGroup,
    Slider,
    TextField,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _env(**kwargs: str) -> dict[str, str]:
    """Constrói um env dict mínimo para os testes das fábricas."""
    base: dict[str, str] = {
        "NNTP_HOST": "news.test.com",
        "NNTP_PORT": "563",
        "NNTP_SSL": "true",
        "NNTP_IGNORE_CERT": "false",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "NNTP_CONNECTIONS": "50",
        "USENET_GROUP": "alt.binaries.test",
        "ARTICLE_SIZE": "700K",
        "DEFAULT_COMPRESSOR": "",
        "CHECK_CONNECTIONS": "5",
        "CHECK_TRIES": "2",
        "CHECK_DELAY": "5s",
        "CHECK_RETRY_DELAY": "30s",
        "CHECK_POST_TRIES": "2",
        "NZB_OUT": "{filename}.nzb",
        "NZB_OVERWRITE": "true",
        "SKIP_ERRORS": "all",
        "WEBHOOK_URL": "",
        "TMDB_API_KEY": "",
        "TMDB_LANGUAGE": "pt-BR",
        "QUIET": "false",
        "LOG_TIME": "true",
        "DUMP_FAILED_POSTS": "",
        "NYUU_EXTRA_ARGS": "",
        "NFO_TEMPLATE": "",
        "EXTERNAL_NZB_DIR": "",
    }
    base.update(kwargs)
    return base


def _find_widget(page: FormPage, key: str) -> object | None:
    for w in page._widgets:
        if isinstance(w, CollapsibleSection):
            for c in w.children:
                if c.key == key:
                    return c
        elif w.key == key:
            return w
    return None


# ── Aba Servidor ──────────────────────────────────────────────────────────────


class TestTabServidor:
    def test_creates_form_page(self) -> None:
        page = _make_tab_servidor(_env())
        assert isinstance(page, FormPage)

    def test_host_field_populated(self) -> None:
        page = _make_tab_servidor(_env(NNTP_HOST="news.eweka.nl"))
        w = _find_widget(page, "NNTP_HOST")
        assert w is not None
        assert w.value == "news.eweka.nl"  # type: ignore[union-attr]

    def test_port_radio_selects_563(self) -> None:
        page = _make_tab_servidor(_env(NNTP_PORT="563"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "NNTP_PORT")
        assert rg.value == "563"

    def test_port_radio_selects_119(self) -> None:
        page = _make_tab_servidor(_env(NNTP_PORT="119"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "NNTP_PORT")
        assert rg.value == "119"

    def test_port_radio_falls_back_to_outro_for_custom(self) -> None:
        page = _make_tab_servidor(_env(NNTP_PORT="8563"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "NNTP_PORT")
        assert rg.value == "outro"

    def test_ssl_checkbox_true(self) -> None:
        page = _make_tab_servidor(_env(NNTP_SSL="true"))
        cb = next(w for w in page._widgets if isinstance(w, CheckBox) and w.key == "NNTP_SSL")
        assert cb.checked

    def test_ssl_checkbox_false(self) -> None:
        page = _make_tab_servidor(_env(NNTP_SSL="false"))
        cb = next(w for w in page._widgets if isinstance(w, CheckBox) and w.key == "NNTP_SSL")
        assert not cb.checked

    def test_connections_slider_value(self) -> None:
        page = _make_tab_servidor(_env(NNTP_CONNECTIONS="30"))
        sl = next(w for w in page._widgets if isinstance(w, Slider))
        assert sl._int_value == 30

    def test_failover_section_exists(self) -> None:
        page = _make_tab_servidor(_env())
        cs = next(
            (w for w in page._widgets if isinstance(w, CollapsibleSection)),
            None,
        )
        assert cs is not None

    def test_failover_collapsed_by_default(self) -> None:
        page = _make_tab_servidor(_env())
        cs = next(w for w in page._widgets if isinstance(w, CollapsibleSection))
        assert not cs.expanded

    def test_host_validator_rejects_url(self) -> None:
        page = _make_tab_servidor(_env())
        tf = next(w for w in page._widgets if isinstance(w, TextField) and w.key == "NNTP_HOST")
        tf._value = "https://news.eweka.nl"
        assert not tf.validate()

    def test_host_validator_accepts_hostname(self) -> None:
        page = _make_tab_servidor(_env())
        tf = next(w for w in page._widgets if isinstance(w, TextField) and w.key == "NNTP_HOST")
        tf._value = "news.eweka.nl"
        assert tf.validate()

    def test_test_button_present(self) -> None:
        page = _make_tab_servidor(_env())
        btn = next((w for w in page._widgets if isinstance(w, Button)), None)
        assert btn is not None

    def test_test_button_calls_nntp(self) -> None:
        page = _make_tab_servidor(_env())
        btn = next(w for w in page._widgets if isinstance(w, Button))
        with patch(
            "upapasta.tui_config.check_nntp_connection", return_value=(True, "ok")
        ) as mock_c:
            btn.handle_key(10)
            assert mock_c.called
        assert btn._result is not None
        ok, _ = btn._result
        assert ok

    def test_test_button_propagates_failure(self) -> None:
        page = _make_tab_servidor(_env())
        btn = next(w for w in page._widgets if isinstance(w, Button))
        with patch("upapasta.tui_config.check_nntp_connection", return_value=(False, "❌ Timeout")):
            btn.handle_key(10)
        ok, msg = btn._result  # type: ignore[misc]
        assert not ok
        assert "Timeout" in msg


# ── Aba Upload ────────────────────────────────────────────────────────────────


class TestTabUpload:
    def test_creates_form_page(self) -> None:
        assert isinstance(_make_tab_upload(_env()), FormPage)

    def test_pool_mode_detected(self) -> None:
        pool = "alt.binaries.a,alt.binaries.b"
        page = _make_tab_upload(_env(USENET_GROUP=pool))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "USENET_GROUP")
        assert rg.value == "pool"

    def test_single_mode_detected(self) -> None:
        page = _make_tab_upload(_env(USENET_GROUP="alt.binaries.boneless"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "USENET_GROUP")
        assert rg.value == "unico"

    def test_group_field_disabled_in_pool_mode(self) -> None:
        pool = "alt.binaries.a,alt.binaries.b"
        page = _make_tab_upload(_env(USENET_GROUP=pool))
        tf = next(
            (w for w in page._widgets if isinstance(w, TextField) and w.key == "USENET_GROUP"),
            None,
        )
        assert tf is not None
        assert not tf.enabled

    def test_article_size_radio_700k(self) -> None:
        page = _make_tab_upload(_env(ARTICLE_SIZE="700K"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "ARTICLE_SIZE")
        assert rg.value == "700K"

    def test_article_size_custom_fallback(self) -> None:
        page = _make_tab_upload(_env(ARTICLE_SIZE="400K"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "ARTICLE_SIZE")
        assert rg.value == "custom"

    def test_compressor_none_default(self) -> None:
        page = _make_tab_upload(_env(DEFAULT_COMPRESSOR=""))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "DEFAULT_COMPRESSOR"
        )
        assert rg.value == ""

    def test_compressor_rar(self) -> None:
        page = _make_tab_upload(_env(DEFAULT_COMPRESSOR="rar"))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "DEFAULT_COMPRESSOR"
        )
        assert rg.value == "rar"


# ── Aba Verificação ───────────────────────────────────────────────────────────


class TestTabVerificacao:
    def test_creates_form_page(self) -> None:
        assert isinstance(_make_tab_verificacao(_env()), FormPage)

    def test_check_connections_slider(self) -> None:
        page = _make_tab_verificacao(_env(CHECK_CONNECTIONS="8"))
        sl = next(w for w in page._widgets if isinstance(w, Slider))
        assert sl._int_value == 8

    def test_check_tries_radio(self) -> None:
        page = _make_tab_verificacao(_env(CHECK_TRIES="3"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "CHECK_TRIES")
        assert rg.value == "3"

    def test_delay_validator_accepts_format(self) -> None:
        page = _make_tab_verificacao(_env())
        tf = next(w for w in page._widgets if isinstance(w, TextField) and w.key == "CHECK_DELAY")
        tf._value = "30s"
        assert tf.validate()

    def test_delay_validator_rejects_garbage(self) -> None:
        page = _make_tab_verificacao(_env())
        tf = next(w for w in page._widgets if isinstance(w, TextField) and w.key == "CHECK_DELAY")
        tf._value = "abc"
        assert not tf.validate()


# ── Aba NZB ───────────────────────────────────────────────────────────────────


class TestTabNzb:
    def test_creates_form_page(self) -> None:
        assert isinstance(_make_tab_nzb(_env()), FormPage)

    def test_nzb_out_populated(self) -> None:
        page = _make_tab_nzb(_env(NZB_OUT="/mnt/{filename}.nzb"))
        tf = next(w for w in page._widgets if isinstance(w, TextField) and w.key == "NZB_OUT")
        assert tf.value == "/mnt/{filename}.nzb"

    def test_overwrite_radio_true(self) -> None:
        page = _make_tab_nzb(_env(NZB_OVERWRITE="true"))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "NZB_OVERWRITE"
        )
        assert rg.value == "true"

    def test_overwrite_radio_false(self) -> None:
        page = _make_tab_nzb(_env(NZB_OVERWRITE="false"))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "NZB_OVERWRITE"
        )
        assert rg.value == "false"

    def test_skip_errors_radio(self) -> None:
        page = _make_tab_nzb(_env(SKIP_ERRORS="none"))
        rg = next(w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "SKIP_ERRORS")
        assert rg.value == "none"

    def test_nzb_validator_rejects_empty(self) -> None:
        page = _make_tab_nzb(_env())
        tf = next(w for w in page._widgets if isinstance(w, TextField) and w.key == "NZB_OUT")
        tf._value = ""
        assert not tf.validate()


# ── Aba Notificações ──────────────────────────────────────────────────────────


class TestTabNotificacoes:
    def test_creates_form_page(self) -> None:
        assert isinstance(_make_tab_notificacoes(_env()), FormPage)

    def test_discord_detected(self) -> None:
        page = _make_tab_notificacoes(_env(WEBHOOK_URL="https://discord.com/api/webhooks/x/y"))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "_webhook_service"
        )
        assert rg.value == "discord"

    def test_slack_detected(self) -> None:
        page = _make_tab_notificacoes(_env(WEBHOOK_URL="https://hooks.slack.com/services/x"))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "_webhook_service"
        )
        assert rg.value == "slack"

    def test_off_when_empty(self) -> None:
        page = _make_tab_notificacoes(_env(WEBHOOK_URL=""))
        rg = next(
            w for w in page._widgets if isinstance(w, RadioGroup) and w.key == "_webhook_service"
        )
        assert rg.value == "off"

    def test_tmdb_language_dropdown(self) -> None:
        page = _make_tab_notificacoes(_env(TMDB_LANGUAGE="en-US"))
        dd = next(w for w in page._widgets if isinstance(w, Dropdown))
        assert dd.value == "en-US"

    def test_webhook_url_field_masked(self) -> None:
        from upapasta.tui_widgets import PasswordField

        page = _make_tab_notificacoes(_env(WEBHOOK_URL="https://discord.com/secret"))
        pf = next(
            (w for w in page._widgets if isinstance(w, PasswordField) and w.key == "WEBHOOK_URL"),
            None,
        )
        assert pf is not None
        assert pf._secret


# ── Aba Avançado ──────────────────────────────────────────────────────────────


class TestTabAvancado:
    def test_creates_form_page(self) -> None:
        assert isinstance(_make_tab_avancado(_env()), FormPage)

    def test_quiet_checkbox(self) -> None:
        page = _make_tab_avancado(_env(QUIET="true"))
        cb = next(w for w in page._widgets if isinstance(w, CheckBox) and w.key == "QUIET")
        assert cb.checked

    def test_log_time_checkbox(self) -> None:
        page = _make_tab_avancado(_env(LOG_TIME="false"))
        cb = next(w for w in page._widgets if isinstance(w, CheckBox) and w.key == "LOG_TIME")
        assert not cb.checked

    def test_nyuu_extra_args_field(self) -> None:
        page = _make_tab_avancado(_env(NYUU_EXTRA_ARGS="--queue=20"))
        tf = next(
            w for w in page._widgets if isinstance(w, TextField) and w.key == "NYUU_EXTRA_ARGS"
        )
        assert tf.value == "--queue=20"


# ── ConfigWizard ──────────────────────────────────────────────────────────────


class TestConfigWizard:
    def _wizard(self, tmp_path: Path, env: dict[str, str] | None = None) -> ConfigWizard:
        env_file = str(tmp_path / ".env")
        wiz = ConfigWizard(env_file=env_file)
        wiz._env = env or _env()
        wiz._build_pages()
        return wiz

    def test_build_pages_creates_six_tabs(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        assert len(wiz._pages) == 6

    def test_collect_all_empty_when_no_changes(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        assert wiz._collect_all() == {}

    def test_collect_all_aggregates_dirty_fields(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        # Simula mudança no campo NNTP_HOST da aba Servidor
        tf = next(
            w for w in wiz._pages[0]._widgets if isinstance(w, TextField) and w.key == "NNTP_HOST"
        )
        tf.handle_key(ord("z"))  # altera valor → dirty
        result = wiz._collect_all()
        assert "NNTP_HOST" in result

    def test_collect_all_ignores_internal_keys(self, tmp_path: Path) -> None:
        """Chaves prefixadas com _ (ex: _webhook_service) não vão para o .env."""
        wiz = self._wizard(tmp_path)
        # Força dirty no RadioGroup interno
        for w in wiz._pages[4]._widgets:
            if isinstance(w, RadioGroup) and w.key == "_webhook_service":
                w.handle_key(curses.KEY_DOWN)
        result = wiz._collect_all()
        assert "_webhook_service" not in result

    def test_do_save_writes_file(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        # Faz uma alteração para ter algo a salvar
        tf = next(
            w for w in wiz._pages[0]._widgets if isinstance(w, TextField) and w.key == "NNTP_HOST"
        )
        tf.handle_key(ord("x"))
        with patch("upapasta.tui_config._write_full_env") as mock_write:
            wiz._do_save()
            assert mock_write.called

    def test_do_save_sets_status_ok(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        tf = next(
            w for w in wiz._pages[0]._widgets if isinstance(w, TextField) and w.key == "NNTP_HOST"
        )
        tf.handle_key(ord("x"))
        with patch("upapasta.tui_config._write_full_env"):
            wiz._do_save()
        assert wiz._status_ok
        assert wiz._status  # mensagem não vazia

    def test_do_save_noop_when_no_changes(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        with patch("upapasta.tui_config._write_full_env") as mock_write:
            wiz._do_save()
            assert not mock_write.called
        assert "Nenhuma" in wiz._status

    def test_do_save_reports_validation_error(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        # Injeta host inválido
        tf = next(
            w for w in wiz._pages[0]._widgets if isinstance(w, TextField) and w.key == "NNTP_HOST"
        )
        tf._value = "https://invalido"  # altera direto para burlar cursor
        tf._original = ""  # força dirty
        with patch("upapasta.tui_config._write_full_env") as mock_write:
            wiz._do_save()
            assert not mock_write.called
        assert not wiz._status_ok

    def test_tab_navigation_via_fkey(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        assert wiz._tab_idx == 0
        wiz._handle_key(curses.KEY_F3)
        assert wiz._tab_idx == 2

    def test_q_sets_not_running(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        wiz._handle_key(ord("q"))
        assert not wiz._running

    def test_esc_sets_not_running(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        wiz._handle_key(27)
        assert not wiz._running

    def test_f10_calls_save(self, tmp_path: Path) -> None:
        wiz = self._wizard(tmp_path)
        with patch.object(wiz, "_do_save") as mock_save:
            wiz._handle_key(curses.KEY_F10)
            mock_save.assert_called_once()


# ── run_config_wizard ─────────────────────────────────────────────────────────


class TestRunConfigWizard:
    def test_falls_back_on_curses_error(self, tmp_path: Path) -> None:
        """Se curses.wrapper lançar curses.error, deve re-lançar RuntimeError."""
        with patch("upapasta.tui_config.resolve_env_file", return_value=str(tmp_path / ".env")):
            with patch("curses.wrapper", side_effect=curses.error("no tty")):
                with pytest.raises(RuntimeError, match="curses"):
                    run_config_wizard()

    def test_returns_false_when_not_saved(self, tmp_path: Path) -> None:
        """curses.wrapper retornando False → run_config_wizard retorna False."""
        with patch("upapasta.tui_config.resolve_env_file", return_value=str(tmp_path / ".env")):
            with patch("curses.wrapper", return_value=False):
                assert run_config_wizard() is False

    def test_returns_true_when_saved(self, tmp_path: Path) -> None:
        with patch("upapasta.tui_config.resolve_env_file", return_value=str(tmp_path / ".env")):
            with patch("curses.wrapper", return_value=True):
                assert run_config_wizard() is True
