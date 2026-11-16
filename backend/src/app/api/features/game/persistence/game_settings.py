"""Maps a game's settings between the domain and the table of its variant."""

from collections.abc import Mapping

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.around_the_clock import ClockOptions, ClockZone
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketOptions, CricketScoring
from app.api.features.game.domain.elimination import EliminationKill, EliminationOptions
from app.api.features.game.domain.finish import FinishRules
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions, KillerZone
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.personal_training import (
    Baseline,
    PersonalFocus,
    PersonalLength,
    PersonalOptions,
    PlanBlock,
)
from app.api.features.game.domain.training import (
    TrainingGoal,
    TrainingLength,
    TrainingMinutes,
    TrainingOptions,
    TrainingRing,
)
from app.api.features.game.persistence.clock_settings import ClockSettingsTable
from app.api.features.game.persistence.cricket_settings import CricketSettingsTable
from app.api.features.game.persistence.elimination_settings import EliminationSettingsTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.killer_settings import KillerSettingsTable
from app.api.features.game.persistence.personal_settings import PersonalSettingsTable
from app.api.features.game.persistence.training_settings import TrainingSettingsTable
from app.api.features.game.persistence.x01_settings import X01SettingsTable
from app.infrastructure.database import Base

type SettingsRow = (
    X01SettingsTable
    | EliminationSettingsTable
    | CricketSettingsTable
    | KillerSettingsTable
    | ClockSettingsTable
    | TrainingSettingsTable
    | PersonalSettingsTable
)

SETTINGS_TABLES: dict[GameVariant, type[Base]] = {
    GameVariant.X01: X01SettingsTable,
    GameVariant.ELIMINATION: EliminationSettingsTable,
    GameVariant.CRICKET: CricketSettingsTable,
    GameVariant.KILLER: KillerSettingsTable,
    GameVariant.AROUND_THE_CLOCK: ClockSettingsTable,
    GameVariant.TRAINING: TrainingSettingsTable,
    GameVariant.PERSONAL: PersonalSettingsTable,
}


def settings_row(game_id: str, setup: GameSetup) -> SettingsRow:
    """The row that stores `setup` in the table of its variant."""
    finish = {"catch_up": setup.finish.catch_up, "play_on": setup.finish.play_on}
    match setup.options:
        case EliminationOptions(kill=kill):
            return EliminationSettingsTable(
                game_id=game_id, **_points(setup), kill=kill.value, **finish
            )
        case CricketOptions(scoring=scoring):
            return CricketSettingsTable(game_id=game_id, scoring=scoring.value)
        case KillerOptions(numbers=numbers, lives=lives, zone=zone):
            return KillerSettingsTable(
                game_id=game_id, numbers=list(numbers), lives=lives, zone=zone.value
            )
        case ClockOptions(zone=zone, skip=skip):
            return ClockSettingsTable(game_id=game_id, zone=zone.value, skip=skip, **finish)
        case TrainingOptions() as training:
            return TrainingSettingsTable(
                game_id=game_id,
                goal=training.goal.value,
                ring=training.ring.value,
                fields=[list(field) for field in training.fields],
                repeats=training.repeats,
                shuffle=training.shuffle,
                any_ring=training.any_ring,
                darts=training.darts,
                minutes=training.minutes,
                seed=training.seed,
            )
        case PersonalOptions() as personal:
            return PersonalSettingsTable(
                game_id=game_id,
                focus=personal.focus.value,
                length=int(personal.length),
                any_ring=personal.any_ring,
                minutes=personal.minutes,
                blocks=[
                    {"fields": [list(target) for target in block.fields], "darts": block.darts}
                    for block in personal.blocks
                ],
                baselines=[
                    {"field": list(baseline.field), "darts": baseline.darts, "hits": baseline.hits}
                    for baseline in personal.baselines
                ],
            )
    return X01SettingsTable(game_id=game_id, **_points(setup), **finish)


def _points(setup: GameSetup) -> dict[str, int | str]:
    if setup.mode is None or setup.checkout_mode is None:
        raise ValueError(f"{setup.variant} needs a mode and a checkout")
    return {"start_score": int(setup.mode), "checkout_mode": setup.checkout_mode.value}


def setup_of(row: SettingsRow) -> GameSetup:
    """The settings one row of a variant's table holds."""
    match row:
        case X01SettingsTable():
            return GameSetup(
                GameVariant.X01,
                GameMode(row.start_score),
                CheckoutMode(row.checkout_mode),
                None,
                FinishRules(catch_up=row.catch_up, play_on=row.play_on),
            )
        case EliminationSettingsTable():
            return GameSetup(
                GameVariant.ELIMINATION,
                GameMode(row.start_score),
                CheckoutMode(row.checkout_mode),
                EliminationOptions(kill=EliminationKill(row.kill)),
                FinishRules(catch_up=row.catch_up, play_on=row.play_on),
            )
        case CricketSettingsTable():
            options = CricketOptions(scoring=CricketScoring(row.scoring))
            return GameSetup(GameVariant.CRICKET, None, None, options)
        case KillerSettingsTable():
            return GameSetup(
                GameVariant.KILLER,
                None,
                None,
                KillerOptions(
                    numbers=tuple(row.numbers), lives=row.lives, zone=KillerZone(row.zone)
                ),
            )
        case ClockSettingsTable():
            return GameSetup(
                GameVariant.AROUND_THE_CLOCK,
                None,
                None,
                ClockOptions(zone=ClockZone(row.zone), skip=row.skip),
                FinishRules(catch_up=row.catch_up, play_on=row.play_on),
            )
        case TrainingSettingsTable():
            return GameSetup(
                GameVariant.TRAINING,
                None,
                None,
                TrainingOptions(
                    goal=TrainingGoal(row.goal),
                    ring=TrainingRing(row.ring),
                    fields=tuple((value, multiplier) for value, multiplier in row.fields),
                    repeats=row.repeats,
                    shuffle=row.shuffle,
                    any_ring=row.any_ring,
                    darts=None if row.darts is None else TrainingLength(row.darts),
                    minutes=None if row.minutes is None else TrainingMinutes(row.minutes),
                    seed=row.seed,
                ),
            )
        case PersonalSettingsTable():
            return GameSetup(
                GameVariant.PERSONAL,
                None,
                None,
                PersonalOptions(
                    focus=PersonalFocus(row.focus),
                    length=PersonalLength(row.length),
                    any_ring=row.any_ring,
                    minutes=None if row.minutes is None else TrainingMinutes(row.minutes),
                    blocks=tuple(
                        PlanBlock(tuple((v, m) for v, m in block["fields"]), block["darts"])
                        for block in row.blocks
                    ),
                    baselines=tuple(
                        Baseline(
                            (baseline["field"][0], baseline["field"][1]),
                            baseline["darts"],
                            baseline["hits"],
                        )
                        for baseline in row.baselines
                    ),
                ),
            )


def start_score() -> ColumnElement[int | None]:
    """A points game's starting score, for a query on `games`; NULL for the other variants."""
    return func.coalesce(
        *(
            select(table.start_score)
            .where(table.game_id == GameTable.id)
            .correlate(GameTable)
            .scalar_subquery()
            for table in (X01SettingsTable, EliminationSettingsTable)
        )
    )


async def load_setups(
    session: AsyncSession, variants: Mapping[str, GameVariant]
) -> dict[str, GameSetup]:
    """The settings of the games in `variants`, one query per variant among them."""
    setups: dict[str, GameSetup] = {}
    for variant in set(variants.values()):
        table = SETTINGS_TABLES[variant]
        ids = [game_id for game_id, played in variants.items() if played is variant]
        rows = (await session.execute(select(table).where(table.game_id.in_(ids)))).scalars()
        setups.update({row.game_id: setup_of(row) for row in rows})
    return setups
