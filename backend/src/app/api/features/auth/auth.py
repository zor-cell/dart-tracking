"""Accounts over HTTP: sessions, profile, address confirmation and password changes.
The refresh token rides in an httpOnly cookie and is rotated on every use; the
access token goes to the client in the body."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from app.api.core.services import rate_limit
from app.api.features.auth.dto.email_change import EmailChangeDto
from app.api.features.auth.dto.login import LoginDto
from app.api.features.auth.dto.password_change import PasswordChangeDto
from app.api.features.auth.dto.password_reset import PasswordResetDto
from app.api.features.auth.dto.password_reset_request import PasswordResetRequestDto
from app.api.features.auth.dto.profile import ProfileDto
from app.api.features.auth.dto.register import RegisterDto
from app.api.features.auth.dto.session import SessionDto
from app.api.features.auth.dto.user import UserDto
from app.api.features.auth.dto.verify_email import VerifyEmailDto
from app.api.features.auth.domain.user import User
from app.api.features.auth.persistence.user_repository import repository
from app.api.features.auth.services import (
    access_tokens,
    account_mails,
    one_time_tokens,
    passwords,
)
from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.auth.services.refresh_store import store as refresh_store
from app.api.features.player.persistence.player_repository import repository as players
from app.infrastructure import database, mailer
from app.infrastructure.config import get_settings

router = APIRouter(prefix="/auth", tags=["Auth"])

# Scoped to this router: no other endpoint reads the cookie, so no other request
# needs to carry it.
_COOKIE_NAME = "refresh_token"
_COOKIE_PATH = "/api/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=_COOKIE_NAME)]

# Failed sign-ins per account per window, and registrations per IP per hour.
_LOGIN_FAILURE_LIMIT, _LOGIN_FAILURE_WINDOW = 10, 15 * 60
_REGISTER_LIMIT, _REGISTER_WINDOW = 5, 60 * 60
# Mails per account, per address and per IP per hour.
_RESEND_LIMIT, _RESEND_WINDOW = 3, 60 * 60
_RESET_EMAIL_LIMIT, _RESET_IP_LIMIT, _RESET_WINDOW = 3, 10, 60 * 60


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


def _invalid_link() -> HTTPException:
    return HTTPException(status_code=400, detail="invalid or expired link")


async def _require_password(user: User, password: str) -> None:
    """403 on a wrong password, counted against the same limit as failed sign-ins.
    Not 401, so the client does not take it for an expired token."""
    await rate_limit.check("login-failures", user.email, _LOGIN_FAILURE_LIMIT)

    async with database.session_scope() as session:
        found = await repository.find_by_email(session, user.email)

    if found is None or not passwords.verify_password(password, found[1]):
        await rate_limit.count("login-failures", user.email, _LOGIN_FAILURE_WINDOW)
        raise HTTPException(status_code=403, detail="current password is wrong")
    await rate_limit.reset("login-failures", user.email)


async def _send_verification(user: User, background: BackgroundTasks) -> None:
    token = await one_time_tokens.email_verification.issue(user.id)
    background.add_task(mailer.send, account_mails.email_verification(user, token))


@router.post("/register", response_model=SessionDto, status_code=201)
async def register(
    body: RegisterDto, request: Request, response: Response, background: BackgroundTasks
) -> SessionDto:
    await rate_limit.enforce(
        "register", rate_limit.client_ip(request), _REGISTER_LIMIT, _REGISTER_WINDOW
    )
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

    await _send_verification(user, background)
    return await _begin_session(response, user)


@router.post("/login", response_model=SessionDto)
async def login(body: LoginDto, response: Response) -> SessionDto:
    identifier = body.identifier.strip()

    async with database.session_scope() as session:
        found = await repository.find_for_login(session, identifier)

    # Failures count per account, so alternating email and username gains nothing.
    limit_key = found[0].email if found is not None else identifier.lower()
    await rate_limit.check("login-failures", limit_key, _LOGIN_FAILURE_LIMIT)

    # One message for both failures, so the endpoint does not reveal which
    # accounts exist.
    if found is None or not passwords.verify_password(body.password, found[1]):
        await rate_limit.count("login-failures", limit_key, _LOGIN_FAILURE_WINDOW)
        raise HTTPException(status_code=401, detail="invalid credentials")

    await rate_limit.reset("login-failures", limit_key)
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


@router.post("/verify-email", response_model=UserDto)
async def verify_email(body: VerifyEmailDto) -> UserDto:
    redeemed = await one_time_tokens.email_verification.consume(body.token)
    if redeemed is None:
        raise _invalid_link()

    async with database.session_scope() as session:
        user = await repository.mark_email_verified(session, redeemed.user_id)

    if user is None:
        raise _invalid_link()
    return UserDto.from_entity(user)


@router.post("/verify-email/resend", status_code=204)
async def resend_verification(user: AuthenticatedUser, background: BackgroundTasks) -> None:
    if user.email_verified:
        raise HTTPException(status_code=409, detail="email already verified")
    await rate_limit.enforce("verify-resend", user.id, _RESEND_LIMIT, _RESEND_WINDOW)
    await _send_verification(user, background)


@router.post("/password-reset", status_code=204)
async def request_password_reset(
    body: PasswordResetRequestDto, request: Request, background: BackgroundTasks
) -> None:
    """Answers the same whether or not the address has an account."""
    email = body.email.strip().lower()
    await rate_limit.enforce(
        "reset-ip", rate_limit.client_ip(request), _RESET_IP_LIMIT, _RESET_WINDOW
    )
    await rate_limit.enforce("reset-email", email, _RESET_EMAIL_LIMIT, _RESET_WINDOW)

    async with database.session_scope() as session:
        found = await repository.find_by_email(session, email)

    if found is not None:
        user = found[0]
        token = await one_time_tokens.password_reset.issue(user.id)
        background.add_task(mailer.send, account_mails.password_reset(user, token))


@router.post("/password-reset/confirm", status_code=204)
async def reset_password(body: PasswordResetDto) -> None:
    """Set the new password and end every session the account had."""
    redeemed = await one_time_tokens.password_reset.consume(body.token)
    if redeemed is None:
        raise _invalid_link()

    async with database.session_scope() as session:
        changed = await repository.set_password(
            session,
            redeemed.user_id,
            passwords.hash_password(body.password),
            confirms_email=True,
        )

    if not changed:
        raise _invalid_link()
    await refresh_store.revoke_all(redeemed.user_id)


@router.get("/me", response_model=UserDto)
async def me(user: AuthenticatedUser) -> UserDto:
    return UserDto.from_entity(user)


@router.put("/me", response_model=UserDto)
async def update_profile(body: ProfileDto, user: AuthenticatedUser) -> UserDto:
    """Identification runs on the id everywhere, so both names are free to
    change. The display name is carried into the account's own address-book
    entry, which is the row the player list shows."""
    username = body.username.strip()

    async with database.session_scope() as session:
        if await repository.username_taken(session, username, user.id):
            raise HTTPException(status_code=409, detail="username already in use")
        if await players.name_taken(session, user.id, body.display_name, except_self=True):
            raise HTTPException(status_code=409, detail="display name in address book")
        updated = await repository.update_profile(
            session, user.id, username, body.display_name
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="account not found")
        await players.rename_self(session, user.id, body.display_name)

    return UserDto.from_entity(updated)


@router.put("/me/password", response_model=SessionDto)
async def change_password(
    body: PasswordChangeDto, user: AuthenticatedUser, response: Response
) -> SessionDto:
    """Replace the password and sign out every device; the caller gets a fresh session."""
    await _require_password(user, body.current_password)

    async with database.session_scope() as session:
        await repository.set_password(
            session, user.id, passwords.hash_password(body.new_password)
        )

    await refresh_store.revoke_all(user.id)
    return await _begin_session(response, user)


@router.put("/me/email", status_code=204)
async def request_email_change(
    body: EmailChangeDto, user: AuthenticatedUser, background: BackgroundTasks
) -> None:
    """Mail a link to the new address; the account keeps the old one until it is opened."""
    email = body.new_email.strip().lower()
    if email == user.email:
        raise HTTPException(status_code=409, detail="email unchanged")
    await _require_password(user, body.current_password)
    await rate_limit.enforce("email-change", user.id, _RESEND_LIMIT, _RESEND_WINDOW)

    async with database.session_scope() as session:
        if await repository.find_by_email(session, email) is not None:
            raise HTTPException(status_code=409, detail="email already in use")

    token = await one_time_tokens.email_change.issue(user.id, email)
    background.add_task(mailer.send, account_mails.email_change(user, email, token))


@router.post("/email-change/confirm", response_model=UserDto)
async def confirm_email_change(body: VerifyEmailDto) -> UserDto:
    redeemed = await one_time_tokens.email_change.consume(body.token)
    if redeemed is None or redeemed.payload is None:
        raise _invalid_link()

    try:
        async with database.session_scope() as session:
            found = await repository.find_by_email(session, redeemed.payload)
            if found is not None and found[0].id != redeemed.user_id:
                raise HTTPException(status_code=409, detail="email already in use")
            user = await repository.set_email(session, redeemed.user_id, redeemed.payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email already in use") from None

    if user is None:
        raise _invalid_link()
    return UserDto.from_entity(user)
