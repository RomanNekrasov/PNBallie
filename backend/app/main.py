import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text

from app.auth import require_entra_token, validate_auth_configuration
from app.database import engine
from app.routers import matches, players, stats


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("APP_ENV", "development").lower() == "production":
        validate_auth_configuration()
    yield


app = FastAPI(title="PNBallie", lifespan=lifespan)


@app.get("/health/live", include_in_schema=False)
def live():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    return {"status": "ok"}


auth_dependencies = [Depends(require_entra_token)]
app.include_router(players.router, dependencies=auth_dependencies)
app.include_router(matches.router, dependencies=auth_dependencies)
app.include_router(stats.router, dependencies=auth_dependencies)
