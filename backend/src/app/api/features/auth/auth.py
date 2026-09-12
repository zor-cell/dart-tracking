"""Accounts over HTTP: register, sign in, refresh, sign out.

The refresh token rides in an httpOnly cookie and is rotated on every use; the
access token goes to the client in the body (docs/feature/done/persistenz.md §6)."""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response

from app.api.features.auth.dto.login import LoginDto
from app.api.features.auth.dto.register import RegisterDto
from app.api.features.auth.dto.session import SessionDto
from app.api.features.auth.dto.user import UserDto
from app.api.features.auth.domain.user import User
from app.api.features.auth.persistence.user_repository import repository
from app.api.features.auth.services import access_tokens, passwords
from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.auth.services.refresh_store import store as refresh_store
from app.api.features.player.persistence.player_repository import repository as players
from app.infrastructure import database
from app.infrastructure.config import get_settings

router = APIRouter(prefix="/auth", tags=["Auth"])

# Scoped to this router: no other endpoint reads the cookie, so no other request
# needs to carry it.
_COOKIE_NAME = "refresh_token"
_COOKIE_PATH = "/api/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=_COOKIE_NAME)]


def _expired_session() -> HTTPException:
    """401 that also clears the cookie. Headers set on an injected `Response`
    are dropped when the handler raises, so the erasure travels on the error."""
    eraser = Response()
    eraser.delete_cookie(_COOKIE_NAME, path=_COOKIE_PATH)
    return HTTPException(
        status_code=401,
        detail="session expired",
        headers={"set-cookie": eraser.headers["set-cookie"]},
    )


async def _begin_session(response: Response, user: User) -> SessionDto:
    """Hand out a fresh pair: the access token in the body, the refresh token in
    the cookie."""
    settings = get_settings()
    refresh_token = await refresh_store.issue(user.id)
    response.set_cookie(
        _COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    access_token, expires_in = access_tokens.issue(user.id)
    return SessionDto(
        access_token=access_token, expires_in=expires_in, user=UserDto.from_entity(user)
    )


@router.post("/register", response_model=SessionDto, status_code=201)
async def register(body: RegisterDto, response: Response) -> SessionDto:
    email = body.email.strip().lower()
    username = body.username.strip()
    display_name = body.display_name

    async with database.session_scope() as session:
        taken = await repository.taken(session, email, username)
        if taken is not None:
            raise HTTPException(status_code=409, detail=f"{taken} already in use")
        user = await repository.create(
            session,
            email,
            username,
            display_name,
            passwords.hash_password(body.password),
        )
        # The account's own entry in its address book, so the first game can be
        # set up without typing one's own name (§4.1).
        await players.create(
            session, display_name, owner_user_id=user.id, user_id=user.id
        )

    return await _begin_session(response, user)


@router.post("/login", response_model=SessionDto)
async def login(body: LoginDto, response: Response) -> SessionDto:
    async with database.session_scope() as session:
        found = await repository.find_by_email(session, body.email.strip().lower())

    # One message for both failures, so the endpoint does not reveal which
    # addresses have an account.
    if found is None or not passwords.verify_password(body.password, found[1]):
        raise HTTPException(status_code=401, detail="invalid email or password")

    return await _begin_session(response, found[0])


@router.post("/refresh", response_model=SessionDto)
async def refresh(response: Response, refresh_token: RefreshCookie = None) -> SessionDto:
    """Trade the cookie for a new pair. Redeeming it deletes it, so the token
    that arrives here is spent whether or not the call succeeds."""
    user_id = None if refresh_token is None else await refresh_store.consume(refresh_token)
    if user_id is None:
        raise _expired_session()

    async with database.session_scope() as session:
        user = await repository.get(session, user_id)

    if user is None:
        raise _expired_session()

    return await _begin_session(response, user)


@router.post("/logout", status_code=204)
async def logout(response: Response, refresh_token: RefreshCookie = None) -> None:
    """Ends the session on the server as well: the access token still runs out
    its few minutes, but nothing can be refreshed from it."""
    if refresh_token is not None:
        await refresh_store.revoke(refresh_token)
    response.delete_cookie(_COOKIE_NAME, path=_COOKIE_PATH)


@router.get("/me", response_model=UserDto)
async def me(user: AuthenticatedUser) -> UserDto:
    return UserDto.from_entity(user)
