"""The plan of a personal training, drawn from the account's latest aimed darts."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.personal_training import (
    PLAN_FIELDS,
    PROBE_FIELDS,
    Baseline,
    PersonalFocus,
    PersonalLength,
    PersonalOptions,
    plan_blocks,
    planned_target,
)
from app.api.features.statistics.domain.target_statistics import TargetStatistics
from app.api.features.statistics.domain.weakness import Weakness, weaknesses
from app.api.features.statistics.persistence.target_repository import (
    repository as targets,
)

# Latest games with aimed darts the plan reads.
PLAN_GAMES = 50


@dataclass(frozen=True)
class PersonalPlan:
    games: int
    darts: int
    # The planned fields' records, in plan order; fields with a thin record come last.
    fields: tuple[Weakness, ...]
    options: PersonalOptions


async def personal_plan(
    session: AsyncSession, user_id: str, focus: PersonalFocus, length: PersonalLength
) -> PersonalPlan:
    statistics = await targets.overview(session, user_id, last=PLAN_GAMES)
    return build_plan(statistics, focus, length)


async def personal_plans(session: AsyncSession, user_id: str) -> list[PersonalPlan]:
    """The plan of every focus and length, focus by focus."""
    statistics = await targets.overview(session, user_id, last=PLAN_GAMES)
    return [build_plan(statistics, focus, length) for focus in PersonalFocus for length in PersonalLength]


def build_plan(
    statistics: TargetStatistics, focus: PersonalFocus, length: PersonalLength
) -> PersonalPlan:
    """The weakest telling fields, filled up with the most played ones still thin."""
    probes = [planned_target(probe) for probe in PROBE_FIELDS[focus]]
    ranked = weaknesses(statistics, focus.rings, probes)
    chosen = [weak for weak in ranked if weak.telling][:PLAN_FIELDS]
    thin = {weak.target: weak for weak in ranked if not weak.telling}
    chosen += [thin[probe] for probe in probes if probe in thin][: PLAN_FIELDS - len(chosen)]
    fields = [(weak.target.value, weak.target.multiplier or 1) for weak in chosen]
    options = PersonalOptions(
        focus=focus,
        length=length,
        blocks=plan_blocks(fields, length),
        baselines=tuple(
            Baseline(field, weak.darts, weak.hits)
            for field, weak in zip(fields, chosen, strict=True)
        ),
    )
    return PersonalPlan(len(statistics.games), statistics.totals.darts, tuple(chosen), options)
