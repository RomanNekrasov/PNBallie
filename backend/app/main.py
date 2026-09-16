import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from sqlalchemy import text

from app.auth import validate_auth_configuration
from app.database import engine
from app.email_verification import validate_configuration
from app.release import worker_revision
from app.routers import auth, avatars, groups, matches, players, stats
from app.telemetry import API_SERVICE, Runtime, install_http

telemetry = Runtime(API_SERVICE, engine)


@asynccontextmanager
async def lifespan(_: FastAPI):
    telemetry.configure()
    try:
        validate_auth_configuration()
        validate_configuration()
        yield
    finally:
        telemetry.close()


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


@app.get("/api/version", include_in_schema=False)
def version(response: Response):
    response.headers["Cache-Control"] = "no-store"
    with engine.connect() as connection:
        schema = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return {"revision": os.getenv("APP_REVISION", "development"),
            "schema": schema, "worker_revision": worker_revision()}


app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(stats.router)

app.include_router(avatars.router, prefix="/api")

install_http(app, telemetry)
