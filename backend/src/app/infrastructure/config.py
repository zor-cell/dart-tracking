"""Runtime configuration, read from the environment or the repository's `.env`.

Credentials have no defaults on purpose: nothing reaches the repository, and a
missing `.env` fails loudly instead of silently using a guessable account.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# One `.env` at the repository root, shared with docker compose. Absent inside
# the container, where the values arrive as environment variables.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Hosts and ports default to what compose.dev.yaml publishes, so a locally
    run backend reaches the containers unconfigured. Republishing on other ports
    means changing them here too."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 10022

    redis_host: str = "localhost"
    redis_port: int = 10023
    redis_db: int = 0
    redis_password: str | None = None

    cors_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]

    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False

    # Deploy build number the image was built from; unset in a local run.
    app_build: int | None = None

    @field_validator("app_build", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        credentials = f":{quote_plus(self.redis_password)}@" if self.redis_password else ""
        return f"redis://{credentials}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
