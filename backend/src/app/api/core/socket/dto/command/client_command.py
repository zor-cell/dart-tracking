from typing import Annotated

from pydantic import Field

from app.api.core.socket.dto.command.set_role import SetRoleDto

ClientCommand = Annotated[
    SetRoleDto,
    Field(discriminator="type"),
]