"""Who says the announcer's phrases: a language and one of its voices."""

from dataclasses import dataclass
from enum import StrEnum

from app.api.core.domain.language import Language


class Voice(StrEnum):
    """Each language offers two voices; the first speaks unless the account picks the other."""

    FIRST = "first"
    SECOND = "second"


@dataclass(frozen=True)
class Speaker:
    language: Language
    voice: Voice = Voice.FIRST
