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
from app.api.features.game.domain.player_count import PlayerCount
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.api.features.statistics.dto.statistics_overview import StatisticsOverviewDto
from app.api.features.statistics.persistence.statistics_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/statistics", tags=["Statistics"])


def _selection(
    variant: list[GameVariant] = Query([]),
    mode: list[GameMode] = Query([]),
    checkout_mode: list[CheckoutMode] = Query([], alias="checkoutMode"),
    opponent: list[UUID] = Query([]),
    players: list[PlayerCount] = Query([]),
    since: datetime | None = None,
    until: datetime | None = None,
    last: int | None = Query(None, ge=1, le=1000),
) -> tuple[GameFilter, int | None]:
    """The games the filters select, any value of a repeated one, each left out leaving
    them open, and how many of the most recent ones that count to keep."""
    criteria = GameFilter(
        variants=tuple(variant),
        modes=tuple(mode),
        checkout_modes=tuple(checkout_mode),
        opponent_ids=tuple(str(id) for id in opponent),
        player_counts=tuple(players),
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


@router.get("", response_model=StatisticsOverviewDto)
async def own_statistics(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> StatisticsOverviewDto:
    """The account's legs in the selected games, or the compared player's, in one tally
    and game by game."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        overview = await repository.overview(session, user.id, criteria, last, compared)

    return StatisticsOverviewDto.from_overview(overview)
