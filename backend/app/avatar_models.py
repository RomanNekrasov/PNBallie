"""Durable avatar jobs and private, group-scoped PNGs.

The source photograph is retained only while a job can still be processed.
No user-supplied filename or filesystem path is ever persisted.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, Session, SQLModel, select


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AvatarJob(SQLModel, table=True):
    __tablename__ = "avatar_job"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    # A unique nullable slot makes concurrent duplicate submissions impossible.
    # Released after success, cancellation or terminal failure.
    active_player_id: int | None = Field(default=None, unique=True)
    provider: str
    # Only W3C trace context; never user IDs, baggage, headers or request data.
    traceparent: str | None = Field(default=None, max_length=55)
    cloud_consent: bool = False
    status: str = Field(default="queued", index=True)
    attempts: int = 0
    source_png: bytes | None = Field(default=None, sa_column=Column(LargeBinary))
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    available_at: datetime = Field(default_factory=utcnow, index=True)
    lease_token: str | None = None
    leased_until: datetime | None = Field(default=None, index=True)


class PlayerAvatar(SQLModel, table=True):
    __tablename__ = "player_avatar"

    player_id: int = Field(foreign_key="player.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    version: str
    png: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    updated_at: datetime = Field(default_factory=utcnow)


def avatar_url(session: Session, player_id: int) -> str | None:
    version = session.exec(select(PlayerAvatar.version).where(PlayerAvatar.player_id == player_id)).first()
    if version is None:
        return None
    return f"/api/avatars/players/{player_id}.png?v={version}"


class AvatarJobRead(BaseModel):
    id: str
    player_id: int
    provider: Literal["local", "openai"]
    status: Literal["queued", "processing", "succeeded", "failed", "cancelled"]
    attempts: int
    error: str | None
    created_at: datetime
    updated_at: datetime
    avatar_url: str | None = None


def read_job(job: AvatarJob, session: Session) -> AvatarJobRead:
    return AvatarJobRead(
        id=job.id,
        player_id=job.player_id,
        provider=job.provider,
        status=job.status,
        attempts=job.attempts,
        error=job.error,
        created_at=job.created_at.replace(tzinfo=timezone.utc),
        updated_at=job.updated_at.replace(tzinfo=timezone.utc),
        avatar_url=avatar_url(session, job.player_id),
    )
