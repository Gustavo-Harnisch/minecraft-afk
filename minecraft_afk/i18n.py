"""Catálogos gettext compartidos por la GUI y los mensajes de los scripts."""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path


DOMAIN = "minecraft-afk"
LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"
SUPPORTED_LANGUAGES = frozenset({"auto", "es", "en"})
_catalog: gettext.NullTranslations = gettext.NullTranslations()


def resolve_language(preference: str) -> str:
    if preference in {"es", "en"}:
        return preference
    # LANGUAGE permits a preference list, e.g. pt_BR:en_GB:es.
    system_language = (
        os.environ.get("LANGUAGE")
        or os.environ.get("LC_ALL")
        or os.environ.get("LC_MESSAGES")
        or os.environ.get("LANG")
        or locale.getlocale()[0]
        or "es"
    )
    for candidate in system_language.split(":"):
        language = candidate.lower().replace("-", "_").split("_")[0].split(".")[0]
        if language in {"es", "en"}:
            return language
    return "es"


def set_language(preference: str) -> str:
    """Load a bundled catalog; Spanish source strings are the fallback."""
    global _catalog
    language = resolve_language(preference)
    _catalog = gettext.translation(
        DOMAIN, localedir=str(LOCALE_DIR), languages=[language], fallback=True
    )
    return language


def _(message: str) -> str:
    return _catalog.gettext(message)


def N_(message: str) -> str:
    """Mark stored labels for extraction; translate them only when displayed."""
    return message
