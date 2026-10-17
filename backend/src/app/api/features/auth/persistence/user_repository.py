"""Reads and writes accounts."""

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.auth.domain.user import User
from app.api.features.auth.domain.user_role import UserRole
from app.api.features.auth.persistence.user import UserTable


def _to_domain(row: UserTable) -> User:
    return User(
        id=row.id,
        email=row.email,
        username=row.username,
        display_name=row.display_name,
        created_at=row.created_at,
        role=UserRole(row.role),
        email_verified=row.email_verified_at is not None,
    )


class UserRepository:
    async def create(
        self,
        session: AsyncSession,
        email: str,
        username: str,
        display_name: str,
        password_hash: str,
    ) -> User:
        row = UserTable(
            email=email,
            username=username,
            display_name=display_name,
            password_hash=password_hash,
        )
        session.add(row)
        # Both the id (uuidv7) and created_at come from the server, so the row
        # has to be read back before it can be mapped.
        await session.flush()
        await session.refresh(row)
        return _to_domain(row)

    async def get(self, session: AsyncSession, user_id: str) -> User | None:
        """A token from an older signing key can carry a subject that is not a
        uuid at all; that is a miss, not a crash."""
        try:
            row = await session.get(UserTable, user_id)
        except ValueError:
            return None
        return None if row is None else _to_domain(row)

    async def find_by_email(
        self, session: AsyncSession, email: str
    ) -> tuple[User, str] | None:
        """The account plus its password hash — the one place the hash leaves
        the persistence layer, for the login check."""
        row = (
            await session.execute(select(UserTable).where(UserTable.email == email))
        ).scalar_one_or_none()
        return None if row is None else (_to_domain(row), row.password_hash)

    async def update_profile(
        self, session: AsyncSession, user_id: str, username: str, display_name: str
    ) -> User | None:
        """Both names at once, so a rename is one write and one transaction."""
        row = await session.get(UserTable, user_id)
        if row is None:
            return None
        row.username = username
        row.display_name = display_name
        await session.flush()
        return _to_domain(row)

    async def mark_email_verified(self, session: AsyncSession, user_id: str) -> User | None:
        """Stamp the address as confirmed; an earlier confirmation keeps its time."""
        row = await session.get(UserTable, user_id)
        if row is None:
            return None
        if row.email_verified_at is None:
            row.email_verified_at = func.now()
            await session.flush()
            await session.refresh(row)
        return _to_domain(row)

    async def set_email(self, session: AsyncSession, user_id: str, email: str) -> User | None:
        """Switch to an address confirmed by a mailed link, so it counts as verified."""
        row = await session.get(UserTable, user_id)
        if row is None:
            return None
        row.email = email
        row.email_verified_at = func.now()
        await session.flush()
        await session.refresh(row)
        return _to_domain(row)

    async def set_password(
        self,
        session: AsyncSession,
        user_id: str,
        password_hash: str,
        *,
        confirms_email: bool = False,
    ) -> bool:
        """Replace the hash; with `confirms_email` the address counts as confirmed too."""
        values: dict[str, object] = {"password_hash": password_hash}
        if confirms_email:
            values["email_verified_at"] = func.coalesce(UserTable.email_verified_at, func.now())
        result = await session.execute(
            update(UserTable).where(UserTable.id == user_id).values(**values)
        )
        return result.rowcount > 0

    async def taken(self, session: AsyncSession, email: str, username: str) -> str | None:
        """Which of the two is already in use, for a message that names the
        field. The unique constraints stay the actual guarantee."""
        row = (
            await session.execute(
                select(UserTable.email, UserTable.username).where(
                    or_(
                        UserTable.email == email,
                        func.lower(UserTable.username) == username.lower(),
                    )
                )
            )
        ).first()
        if row is None:
            return None
        return "email" if row.email == email else "username"

    async def username_taken(
        self, session: AsyncSession, username: str, excluding_user_id: str
    ) -> bool:
        """For a rename, where the account's own handle is not a collision."""
        row = (
            await session.execute(
                select(UserTable.id).where(
                    func.lower(UserTable.username) == username.lower(),
                    UserTable.id != excluding_user_id,
                )
            )
        ).first()
        return row is not None


repository = UserRepository()
