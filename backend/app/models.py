from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel


class PlayerBase(SQLModel):
    name: str = Field(index=True, unique=True)


class Player(PlayerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlayerCreate(PlayerBase):
    pass


class PlayerRead(PlayerBase):
    id: int
    created_at: datetime


# --- Match ---


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    orange_score: int = Field(ge=0, le=10)
    blue_score: int = Field(ge=0, le=10)
    played_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    players: list["MatchPlayer"] = Relationship(back_populates="match")


class MatchPlayer(SQLModel, table=True):
    __tablename__ = "match_player"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    side: str  # "orange" | "blue"
    position: str  # "voor" | "achter" | "solo"

    match: Optional[Match] = Relationship(back_populates="players")


# --- API schemas ---


class MatchPlayerIn(BaseModel):
    player_id: int
    side: str  # "orange" | "blue"
    position: str  # "voor" | "achter" | "solo"


class MatchCreate(BaseModel):
    orange_score: int
    blue_score: int
    players: list[MatchPlayerIn]


class MatchPlayerOut(BaseModel):
    player_id: int
    side: str
    position: str


class MatchRead(BaseModel):
    id: int
    orange_score: int
    blue_score: int
    played_at: datetime
    players: list[MatchPlayerOut]
