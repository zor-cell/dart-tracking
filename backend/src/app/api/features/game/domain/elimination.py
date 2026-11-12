"""Elimination's settings: which dart may send an opponent back to zero."""

from dataclasses import dataclass
from enum import StrEnum

from app.api.features.game.domain.dart import Dart


class EliminationKill(StrEnum):
    """Which darts reset: any field, or only a double or the bullseye, as in double out."""

    ANY = "any"
    DOUBLE = "double"


@dataclass(frozen=True)
class EliminationOptions:
    kill: EliminationKill = EliminationKill.ANY


def can_kill(dart: Dart, kill: EliminationKill) -> bool:
    return kill is EliminationKill.ANY or dart.multiplier == 2
