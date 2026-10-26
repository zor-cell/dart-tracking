"""What the persistence was for: the numbers behind a player's throws."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.statistics.dto.player_statistics import PlayerStatisticsDto
from app.api.features.statistics.persistence.statistics_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("", response_model=PlayerStatisticsDto)
async def own_statistics(
    user: AuthenticatedUser,
    mode: GameMode | None = None,
    checkout_mode: CheckoutMode | None = Query(None, alias="checkoutMode"),
    opponent: UUID | None = None,
    min_players: int | None = Query(None, ge=1, alias="minPlayers"),
    max_players: int | None = Query(None, ge=1, alias="maxPlayers"),
    since: datetime | None = None,
    until: datetime | None = None,
) -> PlayerStatisticsDto:
    """The account's legs in the games the filters select; each left out leaves them open."""
    criteria = GameFilter(
        mode=mode,
        checkout_mode=checkout_mode,
        opponent_id=str(opponent) if opponent else None,
        min_players=min_players,
        max_players=max_players,
        since=since,
        until=until,
    )
    async with database.session_scope() as session:
        statistics = await repository.tally(session, user.id, criteria)

    return PlayerStatisticsDto.from_entity(statistics)
