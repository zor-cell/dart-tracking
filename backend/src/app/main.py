from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.core.socket import socket
from app.api.features.game import games
from app.infrastructure import database, redis_client
from app.infrastructure.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Hold the database and Redis connections for the lifetime of the app."""
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

app.include_router(api_router)