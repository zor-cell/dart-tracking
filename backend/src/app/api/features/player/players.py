"""The address book: the people this account has played with. Scoped to the
caller on purpose — a global player search would be a user-enumeration endpoint."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.services import rate_limit
from app.api.features.auth.domain.user import User
from app.api.features.auth.persistence.user_repository import repository as users
from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.player.domain.invitation import Invitation, InvitationPreview
from app.api.features.player.domain.player_filter import PlayerFilter
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.domain.reciprocal_link import ReciprocalLink
from app.api.features.player.dto.invitation import InvitationDto
from app.api.features.player.dto.invitation_acceptance import InvitationAcceptanceDto
from app.api.features.player.dto.invite_link import InviteLinkDto
from app.api.features.player.dto.player_identity import PlayerIdentityDto
from app.api.features.player.dto.player_link import PlayerLinkDto
from app.api.features.player.dto.player_name import PlayerNameDto
from app.api.features.player.dto.player_page import PlayerPageDto
from app.api.features.player.persistence.player_repository import repository
from app.api.features.player.services import invitations
from app.infrastructure import database

router = APIRouter(prefix="/players", tags=["Player"])

# Invitations opened or accepted per account per hour.
_INVITATION_LIMIT, _INVITATION_WINDOW = 30, 60 * 60


def _name_taken() -> HTTPException:
    return HTTPException(status_code=409, detail="name already in address book")


def _invitation_gone() -> HTTPException:
    return HTTPException(status_code=404, detail="invitation not found")


def _already_linked() -> HTTPException:
    return HTTPException(status_code=409, detail="already linked in this address book")


async def _open_invitation(
    session: AsyncSession, token: str, user: User
) -> tuple[PlayerIdentity, User]:
    """The entry an invitation links and who sent it; an error if it cannot be
    accepted by `user`."""
    await rate_limit.enforce("player-invitation", user.id, _INVITATION_LIMIT, _INVITATION_WINDOW)
    invitation = await invitations.peek(token)
    if invitation is None:
        raise _invitation_gone()
    if invitation.owner_user_id == user.id:
        raise HTTPException(status_code=400, detail="own invitation")

    identity = await repository.invitable(session, invitation.owner_user_id, invitation.player_id)
    inviter = await users.get(session, invitation.owner_user_id)
    if identity is None or inviter is None:
        raise _invitation_gone()
    if await repository.linked_to(session, inviter.id, user.id) is not None:
        raise _already_linked()
    return identity, inviter


@router.get("", response_model=list[PlayerIdentityDto])
async def search_players(
    user: AuthenticatedUser,
    q: str = Query("", max_length=64),
    limit: int = Query(20, ge=1, le=500),
) -> list[PlayerIdentityDto]:
    async with database.session_scope() as session:
        identities = await repository.search(session, user.id, q.strip(), limit)

    return [PlayerIdentityDto.from_entity(identity, user.id) for identity in identities]


@router.get("/page", response_model=PlayerPageDto)
async def list_players(
    user: AuthenticatedUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=64),
    linked: bool | None = None,
) -> PlayerPageDto:
    """The address book one page at a time."""
    criteria = PlayerFilter(query=q.strip() or None, linked=linked)
    async with database.session_scope() as session:
        identities = await repository.page(
            session, user.id, limit=limit, offset=offset, criteria=criteria
        )
        total = await repository.count(session, user.id, criteria)

    return PlayerPageDto(
        items=[PlayerIdentityDto.from_entity(identity, user.id) for identity in identities],
        total=total,
    )


@router.get("/links", response_model=list[PlayerLinkDto])
async def list_links(user: AuthenticatedUser) -> list[PlayerLinkDto]:
    """Where this account is linked in someone else's address book."""
    async with database.session_scope() as session:
        links = await repository.links_of(session, user.id)

    return [PlayerLinkDto.from_entity(link) for link in links]


@router.delete("/links/{player_id}", status_code=204)
async def leave_link(
    player_id: str,
    user: AuthenticatedUser,
    keep_history: bool = Query(False, alias="keepHistory"),
) -> None:
    async with database.session_scope() as session:
        left = await repository.leave(session, user.id, player_id, keep_history=keep_history)

    if not left:
        raise HTTPException(status_code=404, detail="link not found")


@router.get("/invitations/{token}", response_model=InvitationDto)
async def preview_invitation(token: str, user: AuthenticatedUser) -> InvitationDto:
    async with database.session_scope() as session:
        identity, inviter = await _open_invitation(session, token, user)
        reciprocal, _ = await repository.reciprocal(
            session, user.id, inviter.id, inviter.display_name
        )
        game_count = await repository.game_count(session, identity.id)

    return InvitationDto.from_entity(
        InvitationPreview(
            inviter_name=inviter.display_name,
            player_name=identity.display_name,
            game_count=game_count,
            reciprocal=reciprocal,
        )
    )


@router.post("/invitations/{token}", status_code=204)
async def accept_invitation(
    token: str, body: InvitationAcceptanceDto, user: AuthenticatedUser
) -> None:
    try:
        async with database.session_scope() as session:
            identity, inviter = await _open_invitation(session, token, user)
            if not await repository.link(session, inviter.id, identity.id, user.id):
                raise _invitation_gone()

            if body.reciprocal:
                reciprocal, existing_id = await repository.reciprocal(
                    session, user.id, inviter.id, inviter.display_name
                )
                if reciprocal is ReciprocalLink.CREATE:
                    await repository.create(
                        session, inviter.display_name, owner_user_id=user.id, user_id=inviter.id
                    )
                elif reciprocal is ReciprocalLink.LINK and existing_id is not None:
                    await repository.link(session, user.id, existing_id, inviter.id)
    except IntegrityError:
        raise _already_linked() from None

    await invitations.consume(token)


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


@router.post("/{player_id}/invitation", response_model=InviteLinkDto, status_code=201)
async def invite_player(player_id: str, user: AuthenticatedUser) -> InviteLinkDto:
    """A link that lets the person behind an entry link it to their account."""
    async with database.session_scope() as session:
        identity = await repository.invitable(session, user.id, player_id)

    if identity is None:
        raise HTTPException(status_code=404, detail="player not found or already linked")
    token, expires_at = await invitations.issue(
        Invitation(player_id=identity.id, owner_user_id=user.id)
    )
    return InviteLinkDto(token=token, expires_at=expires_at)


@router.delete("/{player_id}/link", response_model=PlayerIdentityDto)
async def unlink_player(player_id: str, user: AuthenticatedUser) -> PlayerIdentityDto:
    """The entry that stands in the address book afterwards; a new one if the
    linked account keeps the games played so far."""
    async with database.session_scope() as session:
        identity = await repository.unlink(session, user.id, player_id)

    if identity is None:
        raise HTTPException(status_code=404, detail="linked player not found")
    return PlayerIdentityDto.from_entity(identity, user.id)


@router.delete("/{player_id}", status_code=204)
async def remove_player(player_id: str, user: AuthenticatedUser) -> None:
    async with database.session_scope() as session:
        removed = await repository.release(session, user.id, player_id)

    if not removed:
        raise HTTPException(status_code=404, detail="player not found")
