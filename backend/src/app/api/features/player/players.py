"""The address book: the people this account has played with. Scoped to the
caller on purpose — a global player search would be a user-enumeration endpoint."""

from fastapi import APIRouter, HTTPException, Query

from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.player.dto.player_identity import PlayerIdentityDto
from app.api.features.player.dto.player_name import PlayerNameDto
from app.api.features.player.persistence.player_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/players", tags=["Player"])


def _name_taken() -> HTTPException:
    return HTTPException(status_code=409, detail="name already in address book")


@router.get("", response_model=list[PlayerIdentityDto])
async def search_players(
    user: AuthenticatedUser,
    q: str = Query("", max_length=64),
    limit: int = Query(20, ge=1, le=500),
) -> list[PlayerIdentityDto]:
    async with database.session_scope() as session:
        identities = await repository.search(session, user.id, q.strip(), limit)

    return [PlayerIdentityDto.from_entity(identity, user.id) for identity in identities]


@router.post("", response_model=PlayerIdentityDto, status_code=201)
async def create_player(body: PlayerNameDto, user: AuthenticatedUser) -> PlayerIdentityDto:
    async with database.session_scope() as session:
        if await repository.name_taken(session, user.id, body.name):
            raise _name_taken()
        identity = await repository.create(session, body.name, owner_user_id=user.id)

    return PlayerIdentityDto.from_entity(identity, user.id)


@router.put("/{player_id}", response_model=PlayerIdentityDto)
async def rename_player(
    player_id: str, body: PlayerNameDto, user: AuthenticatedUser
) -> PlayerIdentityDto:
    async with database.session_scope() as session:
        if await repository.name_taken(session, user.id, body.name, except_id=player_id):
            raise _name_taken()
        identity = await repository.rename(session, user.id, player_id, body.name)

    if identity is None:
        raise HTTPException(status_code=404, detail="player not found")
    return PlayerIdentityDto.from_entity(identity, user.id)


@router.delete("/{player_id}", status_code=204)
async def remove_player(player_id: str, user: AuthenticatedUser) -> None:
    async with database.session_scope() as session:
        removed = await repository.release(session, user.id, player_id)

    if not removed:
        raise HTTPException(status_code=404, detail="player not found")
