from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.elimination import EliminationKill, EliminationOptions


class EliminationOptionsDto(CamelModel):
    kill: EliminationKill = EliminationKill.ANY

    def to_entity(self) -> EliminationOptions:
        return EliminationOptions(kill=self.kill)
