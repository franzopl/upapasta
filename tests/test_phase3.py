"""
test_phase3.py

Testes para os itens implementados na Fase 3 do roadmap UpaPasta.

Cobertos:
  F3.3  — Webhooks nativos (Discord / Slack / Telegram / genérico)
  F3.7  — upapasta --stats (histórico agregado)
  F3.11 — profiles.py separado de config.py
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

from upapasta._webhook import _build_payload, send_webhook

# ── F3.11 — profiles.py ──────────────────────────────────────────────────────

class TestProfilesModule:
    def test_profiles_importable(self):
        from upapasta.profiles import PROFILES
        assert "fast" in PROFILES
        assert "balanced" in PROFILES
        assert "safe" in PROFILES

    def test_profiles_keys(self):
        from upapasta.profiles import PROFILES
        for name, cfg in PROFILES.items():
            assert "redundancy" in cfg, f"perfil '{name}' sem 'redundancy'"

    def test_config_reexports_profiles(self):
        from upapasta.config import PROFILES as cfg_profiles
        from upapasta.profiles import PROFILES as prof_profiles
        assert cfg_profiles is prof_profiles


# ── F3.7 — --stats ───────────────────────────────────────────────────────────

class TestStats:
    def test_print_stats_empty(self, tmp_path, monkeypatch):
        from upapasta.catalog import print_stats
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        # diretório de config não existe → sem histórico
        out = StringIO()
        with patch("builtins.print", side_effect=lambda *a, **kw: out.write(" ".join(str(x) for x in a) + "\n")):
            print_stats()
        assert "Nenhum upload" in out.getvalue() or "vazio" in out.getvalue().lower()

    def test_print_stats_with_records(self, tmp_path, monkeypatch):
        from upapasta.catalog import print_stats

        cfg_dir = tmp_path / ".config" / "upapasta"
        cfg_dir.mkdir(parents=True)
        history = cfg_dir / "history.jsonl"
        records = [
            {
                "nome_original": "Filme.mkv",
                "categoria": "Movie",
                "tamanho_bytes": 2 * 1024 ** 3,
                "grupo_usenet": "alt.binaries.test",
                "data_upload": "2026-04-15T10:00:00",
                "duracao_upload_s": 120.0,
            },
            {
                "nome_original": "Serie.S01E01.mkv",
                "categoria": "TV",
                "tamanho_bytes": 1 * 1024 ** 3,
                "grupo_usenet": "alt.binaries.test",
                "data_upload": "2026-05-01T12:00:00",
                "duracao_upload_s": 60.0,
            },
        ]
        with open(history, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        lines: list[str] = []
        with patch("builtins.print", side_effect=lambda *a, **kw: lines.append(" ".join(str(x) for x in a))):
            print_stats()

        output = "\n".join(lines)
        assert "2" in output          # 2 uploads
        assert "Movie" in output
        assert "TV" in output
        assert "3.00 GB" in output    # total


# ── F3.3 — Webhooks ──────────────────────────────────────────────────────────

class TestBuildPayload:
    def test_discord_uses_content_key(self):
        payload = _build_payload(
            "https://discord.com/api/webhooks/123/abc",
            "Filme.mkv", 1024 ** 3, "alt.binaries.test", "Movie",
        )
        assert "content" in payload
        assert "Filme.mkv" in payload["content"]

    def test_slack_uses_text_key(self):
        payload = _build_payload(
            "https://hooks.slack.com/services/T000/B000/xxx",
            "Serie.S01E01.mkv", None, None, "TV",
        )
        assert "text" in payload
        assert "Serie.S01E01.mkv" in payload["text"]

    def test_telegram_uses_text_key(self):
        payload = _build_payload(
            "https://api.telegram.org/bot123:TOKEN/sendMessage?chat_id=-100",
            "Arquivo.rar", 500 * 1024 ** 2, None, None,
        )
        assert "text" in payload

    def test_generic_payload_fields(self):
        payload = _build_payload(
            "https://meuservidor.local/hook",
            "Release.mkv", 2 * 1024 ** 3, "alt.binaries.x", "Generic",
        )
        assert payload["nome"] == "Release.mkv"
        assert payload["tamanho_bytes"] == 2 * 1024 ** 3
        assert payload["grupo"] == "alt.binaries.x"
        assert "message" in payload

    def test_without_size_shows_question_mark(self):
        payload = _build_payload(
            "https://discord.com/api/webhooks/1/x",
            "Arquivo.nfo", None, None, None,
        )
        assert "?" in payload["content"]

    def test_categoria_included_in_message(self):
        payload = _build_payload(
            "https://discord.com/api/webhooks/1/x",
            "Filme.mkv", 1024 ** 3, None, "Movie",
        )
        assert "Movie" in payload["content"]


class TestSendWebhook:
    def test_send_success(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            send_webhook(
                "https://discord.com/api/webhooks/1/x",
                "Filme.mkv",
                tamanho_bytes=1024 ** 3,
                grupo="alt.binaries.test",
                categoria="Movie",
            )
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.get_header("Content-type") == "application/json"

    def test_send_http_error_does_not_raise(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            url="https://x.com", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )):
            send_webhook("https://x.com/hook", "Arquivo.mkv")  # não deve lançar

    def test_send_network_error_does_not_raise(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            send_webhook("https://x.com/hook", "Arquivo.mkv")  # não deve lançar

    def test_payload_is_valid_json(self):
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            m = MagicMock()
            m.__enter__ = lambda s: s
            m.__exit__ = MagicMock(return_value=False)
            return m

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            send_webhook(
                "https://hooks.slack.com/services/x",
                "Release.mkv",
                tamanho_bytes=500 * 1024 ** 2,
            )

        assert captured
        parsed = json.loads(captured[0].decode())
        assert "text" in parsed

# ── F3.1 — Múltiplas entradas posicionais ───────────────────────────────────

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestMultiInput:
    """Testa suporte a múltiplos inputs posicionais (F3.1)."""

    def _make_args(self, inputs: list[str], jobs: int = 1) -> argparse.Namespace:
        return argparse.Namespace(
            inputs=inputs,
            rar=False, password=None, obfuscate=False, strong_obfuscate=False,
            each=False, season=False, watch=False, jobs=jobs,
            skip_rar_deprecated=False,
        )

    # ── parse_args aceita múltiplos inputs ──────────────────────────────────

    def test_parse_args_multiplos_inputs(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["upapasta", "a.mkv", "b.mkv", "c.mkv"])
        from upapasta.cli import parse_args
        args = parse_args()
        assert args.inputs == ["a.mkv", "b.mkv", "c.mkv"]

    def test_parse_args_input_unico(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["upapasta", "Pasta/"])
        from upapasta.cli import parse_args
        args = parse_args()
        assert args.inputs == ["Pasta/"]

    def test_parse_args_sem_inputs(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["upapasta"])
        from upapasta.cli import parse_args
        args = parse_args()
        assert args.inputs == []

    def test_parse_args_jobs(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["upapasta", str(tmp_path), "--jobs", "4"])
        from upapasta.cli import parse_args
        args = parse_args()
        assert args.jobs == 4

    # ── _validate_flags com múltiplos inputs ────────────────────────────────

    def test_validate_flags_normaliza_input(self, tmp_path):
        from upapasta.cli import _validate_flags
        args = self._make_args([str(tmp_path), str(tmp_path)])
        _validate_flags(args)
        # args.input deve ser o primeiro elemento da lista
        assert args.input == str(tmp_path)

    def test_validate_each_rejeita_multiplos_inputs(self, tmp_path):
        from upapasta.cli import _validate_flags
        args = self._make_args([str(tmp_path), str(tmp_path)], jobs=1)
        args.each = True
        result = _validate_flags(args)
        assert result is False

    def test_validate_watch_rejeita_multiplos_inputs(self, tmp_path):
        from upapasta.cli import _validate_flags
        args = self._make_args([str(tmp_path), str(tmp_path)], jobs=1)
        args.watch = True
        result = _validate_flags(args)
        assert result is False

    def test_validate_jobs_invalido(self):
        from upapasta.cli import _validate_flags
        args = self._make_args(["/tmp/a"], jobs=0)
        result = _validate_flags(args)
        assert result is False

    # ── _run_multi_input sequencial ──────────────────────────────────────────

    def test_run_multi_input_sequencial(self, tmp_path):
        from upapasta.main import _run_multi_input

        resultados: list[int] = [0, 0, 0]
        chamados: list[str] = []

        def fake_run_single(args, item_path, env_file):
            chamados.append(item_path)
            return 0

        args = self._make_args([], jobs=1)

        with patch("upapasta.main._run_single_input", side_effect=fake_run_single):
            rc = _run_multi_input(
                args,
                ["/tmp/a", "/tmp/b", "/tmp/c"],
                ".env",
                jobs=1,
            )

        assert rc == 0
        assert chamados == ["/tmp/a", "/tmp/b", "/tmp/c"]

    def test_run_multi_input_reporta_falhas(self):
        from upapasta.main import _run_multi_input

        respostas = [0, 1, 0]
        idx = [0]

        def fake_run_single(args, item_path, env_file):
            rc = respostas[idx[0]]
            idx[0] += 1
            return rc

        args = self._make_args([], jobs=1)

        with patch("upapasta.main._run_single_input", side_effect=fake_run_single):
            rc = _run_multi_input(
                args,
                ["/tmp/a", "/tmp/b", "/tmp/c"],
                ".env",
                jobs=1,
            )

        assert rc == 1

    def test_run_multi_input_paralelo(self):
        from upapasta.main import _run_multi_input
        import threading

        chamados: list[str] = []
        lock = threading.Lock()

        def fake_run_single(args, item_path, env_file):
            with lock:
                chamados.append(item_path)
            return 0

        args = self._make_args([], jobs=2)

        with patch("upapasta.main._run_single_input", side_effect=fake_run_single):
            rc = _run_multi_input(
                args,
                ["/tmp/a", "/tmp/b"],
                ".env",
                jobs=2,
            )

        assert rc == 0
        assert sorted(chamados) == ["/tmp/a", "/tmp/b"]
