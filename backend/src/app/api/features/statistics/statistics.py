"""What the persistence was for: the numbers behind a player's throws."""

from fastapi import APIRouter

from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.statistics.dto.player_statistics import PlayerStatisticsDto
from app.api.features.statistics.persistence.statistics_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("", response_model=PlayerStatisticsDto)
async def own_statistics(user: AuthenticatedUser) -> PlayerStatisticsDto:
    async with database.session_scope() as session:
        statistics = await repository.tally(session, user.id)

    return PlayerStatisticsDto.from_entity(statistics)
