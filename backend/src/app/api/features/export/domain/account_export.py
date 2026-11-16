"""Everything an account holds, as its data export hands it out."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.auth.domain.user import User
from app.api.features.evaluation.domain.game_event import GameEvent
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.target import Target
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.settings.domain.app_settings import AppSettings
from app.api.features.settings.domain.filter_use import FilterUse


@dataclass(frozen=True)
class ExportedDart:
    dart: Dart
    target: Target | None = None


@dataclass(frozen=True)
class ExportedTurn:
    player_index: int
    busted: bool
    ended_at: datetime | None
    darts: tuple[ExportedDart, ...]


@dataclass(frozen=True)
class ExportedSeat:
    player_id: str
    name: str
    is_me: bool


@dataclass(frozen=True)
class ExportedGame:
    id: str
    setup: GameSetup
    status: GameStatus
    hidden: bool
    owned: bool
    evaluation_enabled: bool
    created_at: datetime
    finished_at: datetime | None
    seats: tuple[ExportedSeat, ...]
    turns: tuple[ExportedTurn, ...]
    # The tracker's log, kept for the games this account set up.
    events: tuple[GameEvent, ...] = ()


@dataclass(frozen=True)
class AccountExport:
    user: User
    settings: AppSettings
    filter_usage: tuple[FilterUse, ...]
    players: tuple[PlayerIdentity, ...]
    games: tuple[ExportedGame, ...]

    @property
    def recorded_game_ids(self) -> list[str]:
        """The games whose camera frames may belong in the export: test runs this account set up."""
        return [game.id for game in self.games if game.owned and game.evaluation_enabled]
