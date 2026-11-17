from typing import Annotated, Literal, Self

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.around_the_clock import ClockProgress
from app.api.features.game.domain.cricket import CricketProgress
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_options import GameProgress
from app.api.features.game.domain.game_status import is_resumable
from app.api.features.game.domain.killer import KillerProgress
from app.api.features.game.domain.personal_training import PersonalProgress
from app.api.features.game.domain.training import TrainingProgress
from app.api.features.game.dto.around_the_clock import ClockStandingDto
from app.api.features.game.dto.cricket import CricketStandingDto
from app.api.features.game.dto.dart import DartDto
from app.api.features.game.dto.game_settings import GameSettingsDto, settings_dto
from app.api.features.game.dto.killer import KillerStandingDto
from app.api.features.game.dto.personal_training import PersonalStandingDto
from app.api.features.game.dto.player import PlayerDto
from app.api.features.game.dto.setup import SetupDto
from app.api.features.game.dto.training import TrainingStandingDto
from app.api.features.game.dto.turn import TurnDto

type StandingDto = Annotated[
    CricketStandingDto
    | KillerStandingDto
    | ClockStandingDto
    | TrainingStandingDto
    | PersonalStandingDto,
    Field(discriminator="variant"),
]


def _standing(game: Game, progress: GameProgress | None) -> StandingDto | None:
    match progress:
        case CricketProgress():
            return CricketStandingDto.from_entity(game, progress)
        case KillerProgress():
            return KillerStandingDto.from_entity(game, progress)
        case ClockProgress():
            return ClockStandingDto.from_entity(game, progress)
        case TrainingProgress():
            return TrainingStandingDto.from_entity(game, progress)
        case PersonalProgress():
            return PersonalStandingDto.from_entity(game, progress)
    return None


class GameStateDto(CamelModel):
    """The authoritative game state, returned over HTTP and pushed over the socket
    after connecting and after every change.
    """

    type: Literal["game_state"] = "game_state"
    id: str
    revision: int
    settings: GameSettingsDto
    players: list[PlayerDto]
    current_player_index: int
    turns: list[TurnDto]
    shadow_darts: list[DartDto]
    darts_remaining: int
    winner_id: int | None
    # A race's places so far, best first; empty outside the race variants.
    places: list[int]
    # Who reached the goal: placed, or finished in the round under way.
    finisher_ids: list[int]
    # Who sits out a tiebreak between the players ahead of them.
    waiting_ids: list[int]
    checkout: list[str] | None
    setup: SetupDto | None
    elimination: list[str] | None
    # Where everyone stands in a variant with own rules; null for the points variants.
    standing: StandingDto | None
    evaluation_enabled: bool
    tracking_paused: bool
    win_confirmed: bool
    # Whether a game nobody wins was ended by hand.
    ended: bool
    resumable: bool

    @classmethod
    def from_entity(cls, game: Game) -> Self:
        just_reset = game.just_reset()
        eliminations = game.eliminations()
        race = game.race() if game.variant.races else None
        return cls(
            id=game.id,
            revision=game.revision,
            settings=settings_dto(game.settings),
            players=[
                PlayerDto.from_entity(
                    player,
                    game.remaining(player.id) if game.variant.counts_points else None,
                    game.average(player.id),
                    game.last_visit(player.id),
                    player.id in just_reset,
                    eliminations[player.id],
                )
                for player in game.players
            ],
            current_player_index=game.current_player_index,
            turns=[TurnDto.from_entity(turn) for turn in game.turns],
            shadow_darts=[DartDto.from_entity(dart) for dart in game.shadow_darts],
            darts_remaining=game.darts_remaining,
            winner_id=game.winner.id if game.winner is not None else None,
            places=race.places if race is not None else [],
            finisher_ids=race.finishers if race is not None else [],
            waiting_ids=race.waiting if race is not None else [],
            checkout=game.checkout,
            setup=SetupDto.from_entity(game.setup) if game.setup is not None else None,
            elimination=game.elimination,
            standing=_standing(game, game.progress),
            evaluation_enabled=game.evaluation_enabled,
            tracking_paused=game.tracking_paused,
            win_confirmed=game.win_confirmed,
            ended=game.ended,
            resumable=is_resumable(game.over, game.updated_at),
        )
