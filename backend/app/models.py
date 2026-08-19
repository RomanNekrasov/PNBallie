from datetime import datetime, timezone
from typing import Literal, Optional

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


# --- Statistics API schemas ---


class DayCount(BaseModel):
    day: str
    count: int


class PlayerStatsRead(BaseModel):
    player_id: int
    name: str
    elo: int
    elo_precise: float
    rank: int | None
    matches: int
    wins: int
    losses: int
    winrate: float | None
    wins_1v1: int
    losses_1v1: int
    wins_2v2: int
    losses_2v2: int
    wins_orange: int
    matches_orange: int
    wins_blue: int
    matches_blue: int
    wins_voor: int
    matches_voor: int
    wins_achter: int
    matches_achter: int
    winrate_orange: float | None
    winrate_blue: float | None
    winrate_voor: float | None
    winrate_achter: float | None
    color_delta: float | None
    position_delta: float | None
    average_goals_for: float | None
    average_goals_against: float | None
    average_goal_difference: float | None
    recent_form: list[Literal["W", "L"]]
    biggest_victory_margin: int
    biggest_victory_score: str | None
    current_winstreak: int
    longest_winstreak: int
    current_losestreak: int
    longest_losestreak: int


class GlobalStatsRead(BaseModel):
    total_matches: int
    total_1v1: int
    total_2v2: int
    average_goals_per_match: float | None
    orange_wins: int
    blue_wins: int
    orange_wins_1v1: int
    blue_wins_1v1: int
    orange_wins_2v2: int
    blue_wins_2v2: int
    current_orange_streak: int
    longest_orange_streak: int
    current_blue_streak: int
    longest_blue_streak: int
    lunch_matches: int
    middag_matches: int
    matches_per_day: list[DayCount]


class LeaderboardEntryRead(BaseModel):
    player_id: int
    name: str
    elo: int
    elo_precise: float
    rank: int
    wins: int
    losses: int
    winrate: float
    recent_form: list[Literal["W", "L"]]


class HeadToHeadMatchupRead(BaseModel):
    player1_id: int
    player1_name: str
    player2_id: int
    player2_name: str
    player1_wins: int
    player2_wins: int
    total: int


class DuoStatRead(BaseModel):
    player1_id: int
    player1_name: str
    player2_id: int
    player2_name: str
    wins: int
    total: int
    winrate: float


class HeadToHeadRead(BaseModel):
    # `matchups` remains the combined legacy view.
    matchups: list[HeadToHeadMatchupRead]
    matchups_1v1: list[HeadToHeadMatchupRead]
    matchups_2v2: list[HeadToHeadMatchupRead]
    duos: list[DuoStatRead]


class RecordItemRead(BaseModel):
    key: str
    label: str
    emoji: str
    description: str
    value: str
    detail: str


class StatsRead(BaseModel):
    players: list[PlayerStatsRead]
    global_: GlobalStatsRead = Field(alias="global")
    leaderboard: list[LeaderboardEntryRead]
    head_to_head: HeadToHeadRead
    records: list[RecordItemRead]

    model_config = {"populate_by_name": True}
