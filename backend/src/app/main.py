from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, darts

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

app.include_router(health.router)
app.include_router(darts.router)