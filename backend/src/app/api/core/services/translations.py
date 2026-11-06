"""Texts the backend sends to people, one JSON file per language under `core/locale/`."""

import json
from functools import cache
from pathlib import Path

from app.api.core.domain.language import Language
from app.api.core.services.request_language import current_language

_LOCALE = Path(__file__).parent.parent / "locale"


@cache
def texts(language: Language) -> dict[str, str]:
    """All texts of `language`, keyed like `mail.reset.title`."""
    return json.loads((_LOCALE / f"{language.value}.json").read_text(encoding="utf-8"))


def translate(key: str, language: Language | None = None, **params: object) -> str:
    """The text under `key` with its `{placeholders}` filled; the current request's
    language unless one is given. An unknown key is a KeyError."""
    return texts(language or current_language.get())[key].format(**params)
