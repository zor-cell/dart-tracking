"""The names an account made through Google starts with."""

import re

_NOT_ALLOWED = re.compile(r"[^A-Za-z0-9_.-]+")


def username_base(email: str) -> str:
    """The part of the address before the `@`, cut to the characters and length a username allows."""
    local = _NOT_ALLOWED.sub("", email.split("@", 1)[0])[:32]
    return local if len(local) >= 3 else f"{local}player"


def display_name_for(name: str | None, email: str) -> str:
    """The name on the Google account, else the part of the address before the `@`."""
    return (name or email.split("@", 1)[0])[:64]
