"""Password hashing. Argon2id via pwdlib, with its recommended parameters, off the event loop."""

import asyncio

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(_hasher.verify, password, password_hash)
