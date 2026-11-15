"""What the persistence was for: the numbers behind a player's throws."""

import asyncio
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.game.domain.around_the_clock import ClockZone
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketScoring
from app.api.features.game.domain.elimination import EliminationKill
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerZone
from app.api.features.game.domain.player_count import PlayerCount
from app.api.features.game.domain.target import Target
from app.api.features.game.domain.training import TrainingGoal, TrainingRing
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.api.features.statistics.dto.cricket_statistics import CricketStatisticsDto
from app.api.features.statistics.dto.kill_statistics import KillStatisticsDto
from app.api.features.statistics.dto.overall_statistics import OverallStatisticsDto
from app.api.features.statistics.dto.statistics_overview import StatisticsOverviewDto
from app.api.features.statistics.dto.target_statistics import TargetStatisticsDto
from app.api.features.statistics.persistence.cricket_repository import repository as cricket
from app.api.features.statistics.persistence.kill_repository import repository as kills
from app.api.features.statistics.persistence.overall_repository import repository as overall
from app.api.features.statistics.persistence.statistics_repository import repository
from app.api.features.statistics.persistence.target_repository import repository as targets
from app.infrastructure import database

router = APIRouter(prefix="/statistics", tags=["Statistics"])


def _selection(
    variant: list[GameVariant] = Query([]),
    mode: list[GameMode] = Query([]),
    checkout_mode: list[CheckoutMode] = Query([], alias="checkoutMode"),
    kill: list[EliminationKill] = Query([]),
    scoring: list[CricketScoring] = Query([]),
    killer_zone: list[KillerZone] = Query([], alias="killerZone"),
    clock_zone: list[ClockZone] = Query([], alias="clockZone"),
    training_goal: list[TrainingGoal] = Query([], alias="trainingGoal"),
    training_ring: list[TrainingRing] = Query([], alias="trainingRing"),
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
        elimination_kills=tuple(kill),
        cricket_scorings=tuple(scoring),
        killer_zones=tuple(killer_zone),
        clock_zones=tuple(clock_zone),
        training_goals=tuple(training_goal),
        training_rings=tuple(training_ring),
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

    return await asyncio.to_thread(StatisticsOverviewDto.from_overview, overview)


@router.get("/targets", response_model=TargetStatisticsDto)
async def target_statistics(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> TargetStatisticsDto:
    """The darts thrown at a named field in the selected games: Around the Clock,
    training targets, Killer's own number and the finishing doubles of x01."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        statistics = await targets.overview(session, user.id, criteria, last, compared)

    return await asyncio.to_thread(TargetStatisticsDto.from_entity, statistics)


@router.get("/kills", response_model=KillStatisticsDto)
async def kill_statistics(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> KillStatisticsDto:
    """The kills in the selected Elimination and Killer games, game by game."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        statistics = await kills.overview(session, user.id, criteria, last, compared)

    return KillStatisticsDto.from_entity(statistics)


@router.get("/cricket", response_model=CricketStatisticsDto)
async def cricket_statistics(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> CricketStatisticsDto:
    """The selected Cricket games: marks per round, distances, visits and the hit picture."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        statistics = await cricket.overview(session, user.id, criteria, last, compared)

    return await asyncio.to_thread(CricketStatisticsDto.from_entity, statistics)


@router.get("/all", response_model=OverallStatisticsDto)
async def overall_statistics(
    user: AuthenticatedUser, selection: Selection, player: Compared = None
) -> OverallStatisticsDto:
    """Every finished game of any kind in the selection, added up."""
    criteria, last = selection
    async with database.session_scope() as session:
        compared = await _compared(session, user.id, player)
        statistics = await overall.overview(session, user.id, criteria, last, compared)

    return await asyncio.to_thread(OverallStatisticsDto.from_entity, statistics)
