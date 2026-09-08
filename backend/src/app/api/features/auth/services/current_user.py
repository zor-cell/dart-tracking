"""Who is calling, if anyone. Auth is optional by design, so there are three
dependencies: `CurrentUser` may be None, `AuthenticatedUser` answers 401,
`AdminUser` answers 403 (docs/feature/done/persistenz.md §6)."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.features.auth.domain.user import User
from app.api.features.auth.persistence.user_repository import repository
from app.api.features.auth.services import access_tokens
from app.infrastructure import database

_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_scheme)],
) -> User | None:
    """No token means anonymous; one that does not hold up is an error. Falling
    back to anonymous on an expired token would silently drop attribution — the
    401 is what makes the client refresh and repeat the call."""
    if credentials is None:
        return None

    user_id = access_tokens.read_subject(credentials.credentials)
    if user_id is None:
        raise _unauthorized("invalid or expired token")

    async with database.session_scope() as session:
        user = await repository.get(session, user_id)

    if user is None:
        raise _unauthorized("account no longer exists")
    return user


async def _required_user(user: Annotated[User | None, Depends(_optional_user)]) -> User:
    if user is None:
        raise _unauthorized("authentication required")
    return user


async def _required_admin(user: Annotated[User, Depends(_required_user)]) -> User:
    """403 rather than 404: the caller is known, the route is not theirs."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


CurrentUser = Annotated[User | None, Depends(_optional_user)]
AuthenticatedUser = Annotated[User, Depends(_required_user)]
AdminUser = Annotated[User, Depends(_required_admin)]
