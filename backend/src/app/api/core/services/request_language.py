"""The language the frontend serves a request's browser in, by the same rule as nginx."""

from contextvars import ContextVar

from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.core.domain.language import Language

# Set by the frontend's language switch, sent along with every request.
_COOKIE = "lang"

# The language of the request or socket being handled.
current_language: ContextVar[Language] = ContextVar("current_language", default=Language.DE)


def request_language(connection: HTTPConnection) -> Language:
    """The switch's cookie, else German for a browser that asks for it first, else English."""
    try:
        return Language(connection.cookies.get(_COOKIE, ""))
    except ValueError:
        pass
    accepted = connection.headers.get("accept-language", "").strip().lower()
    return Language.DE if accepted.startswith("de") else Language.EN


class LanguageMiddleware:
    """Sets `current_language` for each request and socket connection."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        token = current_language.set(request_language(HTTPConnection(scope)))
        try:
            await self.app(scope, receive, send)
        finally:
            current_language.reset(token)
