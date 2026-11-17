"""The data export's JSON files, one model per file in the archive."""

from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.auth.dto.user import UserDto
from app.api.features.evaluation.domain.game_event import GameEvent, GameEventKind
from app.api.features.export.domain.account_export import (
    AccountExport,
    ExportedDart,
    ExportedGame,
    ExportedSeat,
    ExportedTurn,
)
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.dto.game_settings import GameSettingsDto, settings_dto
from app.api.features.player.dto.player_identity import PlayerIdentityDto
from app.api.features.settings.dto.app_settings import AppSettingsDto
from app.api.features.settings.dto.filter_usage import FilterUseDto


class AccountFileDto(CamelModel):
    exported_at: datetime
    user: UserDto
    settings: AppSettingsDto
    filter_usage: list[FilterUseDto]
    players: list[PlayerIdentityDto]

    @classmethod
    def from_entity(cls, export: AccountExport, exported_at: datetime) -> Self:
        return cls(
            exported_at=exported_at,
            user=UserDto.from_entity(export.user),
            settings=AppSettingsDto.from_entity(export.settings),
            filter_usage=[FilterUseDto.from_entity(use) for use in export.filter_usage],
            players=[
                PlayerIdentityDto.from_entity(player, export.user.id) for player in export.players
            ],
        )


class ExportedDartDto(CamelModel):
    value: int
    multiplier: int
    # [x, y] in board millimetres, or None for a dart entered by hand.
    position: list[float] | None
    # Whether the position was moved into the field a correction booked.
    snapped: bool
    thrown_at: datetime | None
    target_value: int | None
    target_multiplier: int | None

    @classmethod
    def from_entity(cls, exported: ExportedDart) -> Self:
        dart, target = exported.dart, exported.target
        return cls(
            value=dart.value,
            multiplier=dart.multiplier,
            position=list(dart.position) if dart.position is not None else None,
            snapped=dart.snapped,
            thrown_at=dart.thrown_at,
            target_value=target.value if target else None,
            target_multiplier=target.multiplier if target else None,
        )


class ExportedTurnDto(CamelModel):
    player_index: int
    busted: bool
    ended_at: datetime | None
    darts: list[ExportedDartDto]

    @classmethod
    def from_entity(cls, turn: ExportedTurn) -> Self:
        return cls(
            player_index=turn.player_index,
            busted=turn.busted,
            ended_at=turn.ended_at,
            darts=[ExportedDartDto.from_entity(dart) for dart in turn.darts],
        )


class ExportedSeatDto(CamelModel):
    player_id: str
    name: str
    is_me: bool

    @classmethod
    def from_entity(cls, seat: ExportedSeat) -> Self:
        return cls(player_id=seat.player_id, name=seat.name, is_me=seat.is_me)


class ExportedEventDto(CamelModel):
    kind: GameEventKind
    created_at: datetime | None
    turn_index: int
    player_index: int
    accepted: bool
    camera_armed: bool
    value: int | None
    multiplier: int | None
    position: list[float] | None
    dart_index: int | None
    target_index: int | None
    failure: str | None
    metrics: dict[str, float] | None
    tracker_version: int | None

    @classmethod
    def from_entity(cls, event: GameEvent) -> Self:
        return cls(
            kind=event.kind,
            created_at=event.created_at,
            turn_index=event.turn_index,
            player_index=event.player_index,
            accepted=event.accepted,
            camera_armed=event.camera_armed,
            value=event.value,
            multiplier=event.multiplier,
            position=list(event.position) if event.position is not None else None,
            dart_index=event.dart_index,
            target_index=event.target_index,
            failure=event.failure,
            metrics=event.metrics,
            tracker_version=event.tracker_version,
        )


class ExportedGameDto(CamelModel):
    id: str
    settings: GameSettingsDto
    status: GameStatus
    hidden: bool
    owned: bool
    evaluation_enabled: bool
    created_at: datetime
    finished_at: datetime | None
    players: list[ExportedSeatDto]
    turns: list[ExportedTurnDto]
    events: list[ExportedEventDto]

    @classmethod
    def from_entity(cls, game: ExportedGame) -> Self:
        return cls(
            id=game.id,
            settings=settings_dto(game.setup),
            status=game.status,
            hidden=game.hidden,
            owned=game.owned,
            evaluation_enabled=game.evaluation_enabled,
            created_at=game.created_at,
            finished_at=game.finished_at,
            players=[ExportedSeatDto.from_entity(seat) for seat in game.seats],
            turns=[ExportedTurnDto.from_entity(turn) for turn in game.turns],
            events=[ExportedEventDto.from_entity(event) for event in game.events],
        )


class GamesFileDto(CamelModel):
    games: list[ExportedGameDto]

    @classmethod
    def from_entity(cls, export: AccountExport) -> Self:
        return cls(games=[ExportedGameDto.from_entity(game) for game in export.games])
