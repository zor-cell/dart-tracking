"""How a signed-in account wants the app to behave; anonymous sessions get
`DEFAULTS`.
"""

from dataclasses import dataclass

from app.api.core.domain.language import Language
from app.api.features.announcement.domain.speaker import Voice


@dataclass(frozen=True)
class AppSettings:
    """Defaults are the safe reading of each switch: the fallbacks that keep a
    game playable are on."""

    # Hand a visit over once the camera sees its darts pulled out, not only on a tap.
    advance_on_pull: bool = True
    # Keep the camera frames of the games this account sets up; off until it agrees.
    evaluation_enabled: bool = False
    # None until the account picks one; the browser's own language applies meanwhile.
    language: Language | None = None
    # Finishing doubles by sector (25 for bull) the checkout suggests first, in order.
    preferred_doubles: tuple[int, ...] = ()
    # None speaks in the language the announcing device shows the app in.
    announcer_language: Language | None = None
    announcer_voice: Voice = Voice.FIRST


DEFAULTS = AppSettings()
