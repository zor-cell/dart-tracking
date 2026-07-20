from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.features.game import games
from app.api.features.tracking import tracking

app = FastAPI(
    title="Dart Tracking API",
    description="Backend for automatic dart-tracking",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(tracking.router)
api_router.include_router(games.router)

app.include_router(api_router)