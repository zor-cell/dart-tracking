"""The language the frontend serves a request's browser in, by the same rule as nginx."""

from fastapi import Request

from app.api.features.settings.domain.language import Language

# Set by the frontend's language switch, sent along with every request.
_COOKIE = "lang"


def request_language(request: Request) -> Language:
    """The switch's cookie, else German for a browser that asks for it first, else English."""
    try:
        return Language(request.cookies.get(_COOKIE, ""))
    except ValueError:
        pass
    accepted = request.headers.get("accept-language", "").strip().lower()
    return Language.DE if accepted.startswith("de") else Language.EN
