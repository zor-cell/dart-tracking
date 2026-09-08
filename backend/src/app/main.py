from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.core.socket import socket
from app.api.features.auth import auth
from app.api.features.evaluation import evaluation
from app.api.features.game import games
from app.api.features.player import players
# Aliased: `settings` is already the process configuration below.
from app.api.features.settings import settings as user_settings
from app.api.features.statistics import statistics
from app.infrastructure import database, redis_client
from app.infrastructure.config import get_settings
from app.infrastructure.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Hold the database and Redis connections for the lifetime of the app."""
    configure_logging()
    database.init(settings.database_url)
    redis_client.init(settings.redis_url)
    yield
    await redis_client.close()
    await database.close()


app = FastAPI(
    title="Dart Tracking API",
    description="Backend for automatic dart-tracking",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(socket.router)
api_router.include_router(games.router)
api_router.include_router(auth.router)
api_router.include_router(players.router)
api_router.include_router(evaluation.router)
api_router.include_router(statistics.router)
api_router.include_router(user_settings.router)

app.include_router(api_router)