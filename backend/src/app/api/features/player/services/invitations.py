"""Invitation links that let the person behind an address-book entry link it to
their account; one live link per entry."""

from datetime import UTC, datetime, timedelta

from app.api.core.services.one_time_tokens import OneTimeTokens
from app.api.features.player.domain.invitation import Invitation

# Long enough for a link sent by messenger to be opened a few days later.
_tokens = OneTimeTokens("player:invitation", timedelta(days=7))


async def issue(invitation: Invitation) -> tuple[str, datetime]:
    """A fresh token for the entry and the moment it expires."""
    token = await _tokens.issue(invitation.player_id, invitation.owner_user_id)
    return token, datetime.now(UTC) + _tokens.ttl


async def peek(token: str) -> Invitation | None:
    redeemed = await _tokens.peek(token)
    if redeemed is None or redeemed.payload is None:
        return None
    return Invitation(player_id=redeemed.subject, owner_user_id=redeemed.payload)


async def consume(token: str) -> None:
    await _tokens.consume(token)
