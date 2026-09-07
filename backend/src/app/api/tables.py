"""Every table module in one place, so importing this completes `Base.metadata`.

Two consumers need the full set: Alembic, whose autogenerate reads anything
missing here as a dropped table, and the running app, where an unregistered
table leaves a foreign key pointing at nothing (`NoReferencedTableError` on the
first flush). Add a line here whenever a feature gains a table.
"""

from app.api.features.auth.persistence import user  # noqa: F401
from app.api.features.evaluation.persistence import tracking_event  # noqa: F401
from app.api.features.game.persistence import dart, game, game_player, turn  # noqa: F401
from app.api.features.player.persistence import player  # noqa: F401
from app.api.features.settings.persistence import user_settings  # noqa: F401
