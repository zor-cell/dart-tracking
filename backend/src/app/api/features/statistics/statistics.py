"""What the persistence was for: the numbers behind a player's throws."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.api.features.statistics.dto.player_statistics import PlayerStatisticsDto
from app.api.features.statistics.dto.trend_point import TrendPointDto
from app.api.features.statistics.persistence.statistics_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/statistics", tags=["Statistics"])


def _selection(
    variant: GameVariant | None = None,
    mode: GameMode | None = None,
    checkout_mode: CheckoutMode | None = Query(None, alias="checkoutMode"),
    opponent: UUID | None = None,
    min_players: int | None = Query(None, ge=1, alias="minPlayers"),
    max_players: int | None = Query(None, ge=1, alias="maxPlayers"),
    since: datetime | None = None,
    until: datetime | None = None,
    last: int | None = Query(None, ge=1, le=1000),
) -> tuple[GameFilter, int | None]:
    """The games the filters select, each left out leaving them open, and how many of
    the most recent ones that count to keep."""
    criteria = GameFilter(
        variant=variant,
        mode=mode,
        checkout_mode=checkout_mode,
        opponent_id=str(opponent) if opponent else None,
        min_players=min_players,
        max_players=max_players,
        since=since,
        until=until,
    )
    return criteria, last


Selection = Annotated[tuple[GameFilter, int | None], Depends(_selection)]
# An entry of the account's address book whose figures are read instead of its own.
Compared = Annotated[UUID | None, Query(alias="player")]


async def _compared(
    session: AsyncSession, user_id: str, player: UUID | None
) -> PlayerIdentity | None:
    """The address book entry `player` names, a 404 if the account has none such."""
    if player is None:
        return None
    found = (await players.owned(session, [str(player)], user_id)).get(str(player))
    if found is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return found


@router.get("", response_model=PlayerStatisticsDto)
async def own_statistics(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> PlayerStatisticsDto:
    """The account's legs in the selected games, or the compared player's, in one tally."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        statistics = await repository.tally(session, user.id, criteria, last, compared)

    return PlayerStatisticsDto.from_entity(statistics)


@router.get("/trend", response_model=list[TrendPointDto])
async def own_trend(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> list[TrendPointDto]:
    """The same games one by one, oldest first, for how the figures move."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        points = await repository.trend(session, user.id, criteria, last, compared)

    return [TrendPointDto.from_entity(point) for point in points]
