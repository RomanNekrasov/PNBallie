"""Seed the isolated acceptance database once with fictional competition data.

Run after Alembic migrations with ``python -m app.demo``. Credentials come
only from DEMO_ADMIN_EMAIL and DEMO_ADMIN_PASSWORD, never command arguments.
"""

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Sequence
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app import auth
from app.models import (
    Group,
    Match,
    MatchPlayer,
    Membership,
    Player,
    User,
    as_utc,
    utc_now,
)
from app.routers.auth import Registration

ACCEPTANCE_ORIGIN = "https://acceptatie.pnballie.nl"
PLAYER_NAMES = ("Sam", "Noor", "Mila", "Finn", "Bo", "Alex", "Robin", "Jules")
MATCH_COUNT = 180
AMS = ZoneInfo("Europe/Amsterdam")


class DemoSeedError(RuntimeError):
    """A safe, credential-free explanation of why the seed was refused."""


@dataclass(frozen=True)
class DemoSeedResult:
    seeded: bool
    groups: int = 0
    users: int = 0
    players: int = 0
    matches: int = 0


def _configuration() -> Registration:
    if (
        os.getenv("DEPLOYMENT_ENVIRONMENT") != "staging"
        or os.getenv("AUTH_APP_ORIGIN") != ACCEPTANCE_ORIGIN
    ):
        raise DemoSeedError(
            "Demo seeding requires DEPLOYMENT_ENVIRONMENT=staging and "
            "AUTH_APP_ORIGIN=https://acceptatie.pnballie.nl."
        )
    try:
        return Registration(
            email=os.getenv("DEMO_ADMIN_EMAIL", ""),
            password=os.getenv("DEMO_ADMIN_PASSWORD", ""),
            display_name=PLAYER_NAMES[0],
        )
    except ValidationError:
        # Pydantic's default exception includes input values, including passwords.
        raise DemoSeedError(
            "Set a valid DEMO_ADMIN_EMAIL and DEMO_ADMIN_PASSWORD of 12–1024 characters."
        ) from None


def _timestamps(now: datetime, rng: random.Random) -> list[datetime]:
    first_day = now.astimezone(AMS).date() - timedelta(days=120)
    timestamps = []
    for index in range(MATCH_COUNT):
        # End yesterday, so even a midnight deployment cannot produce future games.
        local_day = first_day + timedelta(days=index * 119 // (MATCH_COUNT - 1))
        local_time = time(12 if index % 2 == 0 else 15, rng.randrange(60))
        timestamps.append(datetime.combine(local_day, local_time, AMS).astimezone(timezone.utc))
    return sorted(timestamps)


def _matches(players: list[Player], group_id: int, now: datetime) -> list[Match]:
    rng = random.Random(20260911)
    timestamps = _timestamps(now, rng)
    remaining_modes = [1] * 66 + [2] * 108
    rng.shuffle(remaining_modes)
    team_sizes = [1] * 6 + remaining_modes
    matches = []
    for index, (played_at, team_size) in enumerate(zip(timestamps, team_sizes, strict=True)):
        if index < 6:
            # Sam earns a permanent five-win badge, then loses the active streak.
            participants = [players[0], players[1 + index % (len(players) - 1)]]
            if index % 2:
                participants.reverse()
        elif index == MATCH_COUNT - 1:
            participants = [players[0], *rng.sample(players[1:], team_size * 2 - 1)]
        else:
            participants = rng.sample(players, team_size * 2)
        orange = participants[:team_size]
        blue = participants[team_size:]
        orange_wins = rng.choice((True, False))
        if index < 6:
            orange_wins = (players[0] in orange) == (index < 5)
        elif index == MATCH_COUNT - 1:
            orange_wins = False  # Historical badges stay visible without a current flame.
        losing_score = rng.randrange(10)
        match = Match(
            group_id=group_id,
            played_at=played_at,
            orange_score=10 if orange_wins else losing_score,
            blue_score=losing_score if orange_wins else 10,
        )
        positions = ("solo",) if team_size == 1 else ("voor", "achter")
        match.players = [
            MatchPlayer(player_id=player.id, side=side, position=position)
            for side, team in (("orange", orange), ("blue", blue))
            for player, position in zip(team, positions, strict=True)
        ]
        matches.append(match)
    return matches


def seed_demo(engine: Engine, *, now: datetime | None = None, if_empty: bool = False) -> DemoSeedResult:
    """Seed atomically; an empty legacy group created by migrations is preserved."""
    config = _configuration()
    timestamp = as_utc(now or utc_now())
    created_at = timestamp - timedelta(days=121)
    with Session(engine) as session, session.begin():
        if engine.dialect.name == "sqlite":
            # Acquire the write lock before checking emptiness. Another writer
            # cannot register an account between this check and the first insert.
            session.exec(text("BEGIN IMMEDIATE"))
        occupied = any(
            session.exec(select(model.id).limit(1)).first() is not None
            for model in (User, Player, Match)
        ) or session.exec(select(Group.id).where(Group.is_legacy == False).limit(1)).first() is not None  # noqa: E712
        if occupied:
            if if_empty:
                return DemoSeedResult(seeded=False)
            raise DemoSeedError("Demo seeding refused: database already contains application data.")

        group = Group(name="Democompetitie", created_at=created_at)
        user = User(
            email=config.email,
            display_name=config.display_name,
            password_hash=auth.password_hash(config.password),
            created_at=created_at,
        )
        session.add_all([group, user])
        session.flush()
        session.add(Membership(group_id=group.id, user_id=user.id, role="admin", created_at=created_at))
        players = [
            Player(
                name=name, group_id=group.id,
                user_id=user.id if index == 0 else None,
                created_at=created_at,
            )
            for index, name in enumerate(PLAYER_NAMES)
        ]
        session.add_all(players)
        session.flush()
        session.add_all(_matches(players, group.id, timestamp))
    return DemoSeedResult(seeded=True, groups=1, users=1, players=len(PLAYER_NAMES), matches=MATCH_COUNT)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--if-empty", action="store_true", help="Skip an occupied acceptance database without changing it.")
    args = parser.parse_args(argv)
    from app.database import engine

    try:
        result = seed_demo(engine, if_empty=args.if_empty)
    except DemoSeedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Demo seeding failed; no demo data was committed. Check database migrations and connectivity.", file=sys.stderr)
        return 1
    if result.seeded:
        print(f"Demo created: {result.groups} group, {result.users} admin, {result.players} players, {result.matches} matches.")
    else:
        print("Demo seeding skipped: database already contains application data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
