"""How a signed-in account wants the app to behave.

Server-owned so the choices follow the account across devices; an anonymous
session gets `DEFAULTS` and cannot change them.
"""

from dataclasses import dataclass, replace
from typing import Self


@dataclass(frozen=True)
class AppSettings:
    """Defaults are the safe reading of each switch: the fallbacks that keep a
    game playable are on, the diagnostics are off."""

    # Hand a visit over once the camera sees its darts pulled out, not only on a tap.
    advance_on_pull: bool = True
    evaluation_enabled: bool = False
    # Finishing doubles by sector (25 for bull) the checkout suggests first, in order.
    preferred_doubles: tuple[int, ...] = ()

    def without_diagnostics(self) -> Self:
        """This set with the recording switch off: what an account that is not
        an admin runs on, whatever happens to be stored for it."""
        return replace(self, evaluation_enabled=False)


DEFAULTS = AppSettings()
