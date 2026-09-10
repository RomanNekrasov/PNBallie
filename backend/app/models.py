from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite stores naïve timestamps; application timestamps have always been UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_user_oidc"),)
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=254)
    display_name: str = Field(max_length=80)
    password_hash: str | None = None
    oidc_issuer: str | None = None
    oidc_subject: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class LoginSession(SQLModel, table=True):
    __tablename__ = "login_session"
    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    csrf_token: str
    expires_at: datetime


class AuthThrottle(SQLModel, table=True):
    __tablename__ = "auth_throttle"
    key: str = Field(primary_key=True)
    window_start: datetime
    attempts: int = 0


class OIDCLogin(SQLModel, table=True):
    __tablename__ = "oidc_login"
    state_hash: str = Field(primary_key=True)
    nonce: str
    verifier: str
    next_path: str = "/"
    expires_at: datetime


class Group(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=80)
    is_legacy: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class Membership(SQLModel, table=True):
    group_id: int = Field(foreign_key="group.id", primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", primary_key=True)
    role: str = "member"
    created_at: datetime = Field(default_factory=utc_now)


class Invite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    code_hash: str = Field(unique=True, index=True)
    created_by: int = Field(foreign_key="app_user.id")
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    max_uses: int | None = None
    uses: int = 0
    revoked: bool = False


class PlayerBase(SQLModel):
    name: str = Field(max_length=80)


class Player(PlayerBase, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_player_group_name"),
        UniqueConstraint("group_id", "user_id", name="uq_player_group_user"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(default=1, foreign_key="group.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="app_user.id", index=True)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class PlayerCreate(PlayerBase):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value


class PlayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None
    user_id: int | None = None


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PlayerRead(PlayerBase):
    # Read historical names as stored, even if they predate input limits.
    name: str
    id: int
    group_id: int
    user_id: int | None
    is_active: bool
    created_at: datetime
    avatar_url: str | None = None

    _utc_created = field_validator("created_at")(as_utc)


# --- Match ---


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(default=1, foreign_key="group.id", index=True)
    orange_score: int = Field(ge=0, le=10)
    blue_score: int = Field(ge=0, le=10)
    played_at: datetime = Field(default_factory=utc_now)

    players: list["MatchPlayer"] = Relationship(back_populates="match")


class MatchPlayer(SQLModel, table=True):
    __tablename__ = "match_player"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    side: str
    position: str

    match: Optional[Match] = Relationship(back_populates="players")


# --- API schemas ---


class MatchPlayerIn(BaseModel):
    player_id: int
    side: str
    position: str


class MatchCreate(BaseModel):
    orange_score: int = Field(ge=0, le=10)
    blue_score: int = Field(ge=0, le=10)
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

    _utc_played = field_validator("played_at")(as_utc)


# --- Statistics API schemas ---


class DayCount(BaseModel):
    day: str
    count: int
    before_14: int
    from_14: int


class PlayerBadgeRead(BaseModel):
    key: str
    label: str
    emoji: str
    description: str
    earned_at: datetime


class StatsFiltersRead(BaseModel):
    mode: Literal["all", "1v1", "2v2"]
    period: Literal["all", "30d", "50"]


class PlayerStatsRead(BaseModel):
    player_id: int
    name: str
    avatar_url: str | None = None
    badges: list[PlayerBadgeRead]
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
    average_goal_difference: float | None
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
    avatar_url: str | None = None
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
    filters: StatsFiltersRead
    players: list[PlayerStatsRead]
    global_: GlobalStatsRead = Field(alias="global")
    leaderboard: list[LeaderboardEntryRead]
    head_to_head: HeadToHeadRead
    records: list[RecordItemRead]
    recent_matches: list[MatchRead]

    model_config = {"populate_by_name": True}
