from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locale"
_DOMAIN = "upapasta"


def _detect_lang() -> str:
    lang = os.environ.get("UPAPASTA_LANG", "").strip()
    if lang:
        return lang

    try:
        lc, _ = locale.getlocale()
        if lc:
            return lc
    except Exception:
        pass

    env_lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    if env_lang:
        # strip encoding suffix (e.g. "pt_BR.UTF-8" → "pt_BR")
        return env_lang.split(".")[0]

    return "en"


def _load_translation(lang: str) -> gettext.NullTranslations:
    # Try exact lang, then language prefix (e.g. "pt_BR" → "pt")
    candidates = [lang]
    if "_" in lang:
        candidates.append(lang.split("_")[0])

    for candidate in candidates:
        try:
            return gettext.translation(
                _DOMAIN,
                localedir=str(_LOCALE_DIR),
                languages=[candidate],
            )
        except FileNotFoundError:
            continue

    return gettext.NullTranslations()


_translation = _load_translation(_detect_lang())


def get_translation() -> gettext.NullTranslations:
    return _translation


def install(lang: str | None = None) -> None:
    """Reinitialise the active translation (useful for testing)."""
    global _translation
    resolved = lang if lang is not None else _detect_lang()
    _translation = _load_translation(resolved)


def _(msg: str) -> str:
    return _translation.gettext(msg)
