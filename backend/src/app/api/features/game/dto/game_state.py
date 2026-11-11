from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.around_the_clock import ClockOptions, ClockProgress
from app.api.features.game.domain.cricket import CricketOptions, CricketProgress
from app.api.features.game.domain.killer import KillerOptions, KillerProgress
from app.api.features.game.dto.around_the_clock import ClockStateDto
from app.api.features.game.dto.cricket import CricketStateDto
from app.api.features.game.dto.dart import DartDto
from app.api.features.game.dto.killer import KillerStateDto
from app.api.features.game.dto.player import PlayerDto
from app.api.features.game.dto.setup import SetupDto
from app.api.features.game.dto.turn import TurnDto
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import is_resumable
from app.api.features.game.domain.game_variant import GameVariant


class GameStateDto(CamelModel):
    """The authoritative game state: both the answer to an HTTP call and the
    message pushed over the socket, so it looks the same however it arrived.

    Pushed right after connecting (a joining or reconnecting device is then in
    sync) and after every change any device makes.
    """

    type: Literal["game_state"] = "game_state"
    id: str
    revision: int
    # The points variants' starting score and finish; null for the others.
    mode: GameMode | None
    variant: GameVariant
    checkout_mode: CheckoutMode | None
    players: list[PlayerDto]
    current_player_index: int
    turns: list[TurnDto]
    shadow_darts: list[DartDto]
    darts_remaining: int
    can_undo: bool
    winner_id: int | None
    checkout: list[str] | None
    setup: SetupDto | None
    elimination: list[str] | None
    # The standing of the variant that is played; null for the others.
    cricket: CricketStateDto | None
    killer: KillerStateDto | None
    around_the_clock: ClockStateDto | None
    evaluation_enabled: bool
    tracking_paused: bool
    win_confirmed: bool
    resumable: bool

    @classmethod
    def from_entity(cls, game: Game) -> Self:
        just_reset = game.just_reset()
        eliminations = game.eliminations()
        progress = game.progress
        options = game.options
        return cls(
            id=game.id,
            revision=game.revision,
            mode=game.mode,
            variant=game.variant,
            checkout_mode=game.checkout_mode,
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
            can_undo=game.can_undo,
            winner_id=game.winner.id if game.winner is not None else None,
            checkout=game.checkout,
            setup=SetupDto.from_entity(game.setup) if game.setup is not None else None,
            elimination=game.elimination,
            cricket=(
                CricketStateDto.from_entity(game, options, progress)
                if isinstance(options, CricketOptions) and isinstance(progress, CricketProgress)
                else None
            ),
            killer=(
                KillerStateDto.from_entity(game, options, progress)
                if isinstance(options, KillerOptions) and isinstance(progress, KillerProgress)
                else None
            ),
            around_the_clock=(
                ClockStateDto.from_entity(game, options, progress)
                if isinstance(options, ClockOptions) and isinstance(progress, ClockProgress)
                else None
            ),
            evaluation_enabled=game.evaluation_enabled,
            tracking_paused=game.tracking_paused,
            win_confirmed=game.win_confirmed,
            resumable=is_resumable(game.winner is not None, game.updated_at),
        )
