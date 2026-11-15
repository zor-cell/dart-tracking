"""Every table module in one place, so importing this completes `Base.metadata` for
Alembic and the app. Add a line whenever a feature gains a table.
"""

from app.api.features.auth.persistence import user  # noqa: F401
from app.api.features.evaluation.persistence import game_event  # noqa: F401
from app.api.features.game.persistence import (  # noqa: F401
    clock_settings,
    cricket_settings,
    dart,
    elimination_settings,
    game,
    game_hide,
    game_player,
    killer_settings,
    training_settings,
    turn,
    x01_settings,
)
from app.api.features.player.persistence import player  # noqa: F401
from app.api.features.settings.persistence import user_settings  # noqa: F401
