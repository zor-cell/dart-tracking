"""The address book: the people this account has played with. Scoped to the
caller on purpose — a global player search would be a user-enumeration endpoint
(docs/feature/persistenz.md §4.3)."""

from fastapi import APIRouter, Query

from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.player.dto.player_identity import PlayerIdentityDto
from app.api.features.player.persistence.player_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/players", tags=["Player"])


@router.get("", response_model=list[PlayerIdentityDto])
async def search_players(
    user: AuthenticatedUser, q: str = Query("", max_length=64)
) -> list[PlayerIdentityDto]:
    async with database.session_scope() as session:
        identities = await repository.search(session, user.id, q.strip())

    return [PlayerIdentityDto.from_entity(identity, user.id) for identity in identities]
