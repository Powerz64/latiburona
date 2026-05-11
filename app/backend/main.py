from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.config import get_cors_origins
from app.backend.db import SessionLocal, init_db
from app.backend.routers.analytics import router as analytics_router
from app.backend.routers.auth import router as auth_router
from app.backend.routers.canchas import router as canchas_router
from app.backend.routers.dashboard import router as dashboard_router
from app.backend.routers.reservations import router as reservations_router
from app.backend.routers.tournaments import router as tournaments_router
from app.backend.services.auth_service import ensure_default_admin_user


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as session:
        ensure_default_admin_user(session)
    yield


app = FastAPI(title="LaTiburona API", lifespan=lifespan)
cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(analytics_router)
app.include_router(dashboard_router)
app.include_router(reservations_router)
app.include_router(canchas_router)
app.include_router(tournaments_router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "latiburona-api"}
