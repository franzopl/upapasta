"""Tests for upapasta.i18n — locale detection and gettext fallback."""
from __future__ import annotations

import locale
from unittest.mock import patch

import pytest


class TestDetectLang:
    def test_upapasta_lang_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPAPASTA_LANG", "pt_BR")
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        from upapasta.i18n import _detect_lang
        assert _detect_lang() == "pt_BR"

    def test_lang_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UPAPASTA_LANG", raising=False)
        monkeypatch.setenv("LANG", "pt_BR.UTF-8")
        with patch("locale.getlocale", return_value=(None, None)):
            from upapasta.i18n import _detect_lang
            assert _detect_lang() == "pt_BR"

    def test_no_env_defaults_to_en(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UPAPASTA_LANG", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        with patch("locale.getlocale", return_value=(None, None)):
            from upapasta.i18n import _detect_lang
            assert _detect_lang() == "en"


class TestFallbackToNullTranslations:
    def test_missing_mo_returns_null_translations(self) -> None:
        import gettext
        from upapasta.i18n import _load_translation

        t = _load_translation("zz_ZZ")  # non-existent locale
        assert isinstance(t, gettext.NullTranslations)

    def test_null_translations_returns_original_string(self) -> None:
        from upapasta.i18n import _load_translation

        t = _load_translation("zz_ZZ")
        assert t.gettext("Hello") == "Hello"


class TestInstallAndTranslate:
    def test_install_en_and_translate(self) -> None:
        from upapasta import i18n

        i18n.install("en")
        # English .mo exists — gettext returns the original string unchanged
        result = i18n._("Upload complete")
        assert result == "Upload complete"

    def test_install_unknown_lang_falls_back(self) -> None:
        from upapasta import i18n

        i18n.install("xx_XX")
        # NullTranslations: passthrough
        assert i18n._("test string") == "test string"

    def test_underscore_function_callable(self) -> None:
        from upapasta.i18n import _

        assert callable(_)
        assert _("hello") == "hello"
