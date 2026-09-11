from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

from app import auth, demo
from app.models import (
    Group,
    Match,
    MatchPlayer,
    Membership,
    Player,
    StatsRead,
    User,
    as_utc,
)
from app.routers.stats import _build_stats

NOW = datetime(2026, 4, 2, 0, 5, tzinfo=timezone.utc)
PASSWORD = "fictional-demo-password"


@pytest.fixture
def demo_env(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("AUTH_APP_ORIGIN", demo.ACCEPTANCE_ORIGIN)
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", " DEMO@example.org ")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", PASSWORD)


def snapshot(engine):
    with Session(engine) as session:
        return {
            model.__tablename__: [row.model_dump() for row in session.exec(select(model)).all()]
            for model in (Group, User, Membership, Player, Match, MatchPlayer)
        }


@pytest.mark.parametrize("variable,value", [
    ("DEPLOYMENT_ENVIRONMENT", "production"),
    ("DEPLOYMENT_ENVIRONMENT", "preview"),
    ("DEPLOYMENT_ENVIRONMENT", ""),
    ("AUTH_APP_ORIGIN", "https://pnballie.nl"),
    ("AUTH_APP_ORIGIN", "https://acceptatie.pnballie.nl/"),
])
def test_seed_requires_exact_acceptance_environment(db_engine, demo_env, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    before = snapshot(db_engine)
    with pytest.raises(demo.DemoSeedError, match="requires DEPLOYMENT_ENVIRONMENT"):
        demo.seed_demo(db_engine, if_empty=True)
    assert snapshot(db_engine) == before


@pytest.mark.parametrize("variable,value", [
    ("DEMO_ADMIN_EMAIL", "not-an-email"),
    ("DEMO_ADMIN_EMAIL", ""),
    ("DEMO_ADMIN_PASSWORD", "short-value"),
    ("DEMO_ADMIN_PASSWORD", ""),
])
def test_seed_validates_credentials_without_disclosing_them(db_engine, demo_env, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    before = snapshot(db_engine)
    with pytest.raises(demo.DemoSeedError, match="Set a valid") as error:
        demo.seed_demo(db_engine)
    assert not value or value not in str(error.value)
    assert snapshot(db_engine) == before


@pytest.mark.parametrize("existing", ["user", "player", "match", "group"])
def test_seed_refuses_existing_application_data_without_changes(db_engine, demo_env, existing):
    with Session(db_engine) as session:
        group = Group(id=1, name="Existing", is_legacy=existing != "group")
        session.add(group)
        session.flush()
        if existing == "user":
            session.add(User(email="existing@example.org", display_name="Existing"))
        elif existing == "player":
            session.add(Player(name="Existing", group_id=group.id))
        elif existing == "match":
            session.add(Match(group_id=group.id, orange_score=10, blue_score=4))
        session.commit()
    before = snapshot(db_engine)
    with pytest.raises(demo.DemoSeedError, match="already contains"):
        demo.seed_demo(db_engine)
    assert snapshot(db_engine) == before


@pytest.mark.parametrize("now", [NOW, datetime(2026, 11, 1, 0, 5, tzinfo=timezone.utc)])
def test_seed_populates_real_stats_across_modes_periods_and_dst(db_engine, demo_env, now):
    with Session(db_engine) as session:
        session.add(Group(id=1, name="Bestaande competitie", is_legacy=True, created_at=NOW))
        session.commit()
    result = demo.seed_demo(db_engine, now=now)
    assert result == demo.DemoSeedResult(seeded=True, groups=1, users=1, players=8, matches=180)

    with Session(db_engine) as session:
        legacy = session.get(Group, 1)
        assert (legacy.name, legacy.is_legacy, as_utc(legacy.created_at)) == ("Bestaande competitie", True, NOW)
        user = session.exec(select(User)).one()
        assert (user.email, user.display_name) == ("demo@example.org", "Sam")
        assert auth.verify_password(PASSWORD, user.password_hash)
        membership = session.exec(select(Membership)).one()
        assert membership.user_id == user.id and membership.role == "admin"
        group = session.get(Group, membership.group_id)
        assert group.id != legacy.id and group.name == "Democompetitie" and not group.is_legacy
        players = list(session.exec(select(Player)).all())
        assert [player.name for player in players] == list(demo.PLAYER_NAMES)
        assert {player.name for player in players if player.user_id == user.id} == {"Sam"}
        assert all(player.group_id == group.id for player in players)
        matches = list(session.exec(select(Match).order_by(Match.played_at)).all())
        local_times = [as_utc(match.played_at).astimezone(demo.AMS) for match in matches]
        assert all(match.group_id == group.id for match in matches)
        assert all(as_utc(match.played_at) < now for match in matches)
        assert min(local_times).date() == now.astimezone(demo.AMS).date() - timedelta(days=120)
        assert max(local_times).date() == now.astimezone(demo.AMS).date() - timedelta(days=1)
        assert {timestamp.utcoffset() for timestamp in local_times} == {timedelta(hours=1), timedelta(hours=2)}
        assert Counter(timestamp.hour for timestamp in local_times) == {12: 90, 15: 90}
        for match in matches:
            assert max(match.orange_score, match.blue_score) == 10
            assert min(match.orange_score, match.blue_score) in range(10)
            assert len({entry.player_id for entry in match.players}) == len(match.players)
            assert Counter(entry.side for entry in match.players) == {"orange": len(match.players) // 2, "blue": len(match.players) // 2}
            expected = {"solo"} if len(match.players) == 2 else {"voor", "achter"}
            assert {entry.position for entry in match.players if entry.side == "orange"} == expected
            assert {entry.position for entry in match.players if entry.side == "blue"} == expected

        for mode in ("all", "1v1", "2v2"):
            for period in ("all", "30d", "50"):
                stats = _build_stats(matches, players, mode=mode, period=period, now=now)
                StatsRead.model_validate(stats)
                assert stats["global"]["total_matches"] > 0
                assert stats["global"]["orange_wins"] and stats["global"]["blue_wins"]
                if period == "30d":
                    assert stats["global"]["total_matches"] < 50
                if period == "50":
                    assert stats["global"]["total_matches"] == 50
                sam = next(player for player in stats["players"] if player["name"] == "Sam")
                assert "win_streak_5" in {badge["key"] for badge in sam["badges"]}
                assert sam["current_winstreak"] == 0
        stats = _build_stats(matches, players, now=now)
        assert (stats["global"]["total_1v1"], stats["global"]["total_2v2"]) == (72, 108)
        assert all(player["wins"] and player["losses"] for player in stats["players"])
        assert all(player["matches_orange"] and player["matches_blue"] for player in stats["players"])
        assert all(player["matches_voor"] and player["matches_achter"] for player in stats["players"])
        assert stats["head_to_head"]["matchups_1v1"] and stats["head_to_head"]["matchups_2v2"] and stats["head_to_head"]["duos"]


def test_cli_if_empty_skips_existing_data_but_keeps_environment_guard(db_engine, demo_env, monkeypatch, capsys):
    monkeypatch.setattr("app.database.engine", db_engine)
    assert demo.main(["--if-empty"]) == 0
    assert "8 players, 180 matches" in capsys.readouterr().out
    before = snapshot(db_engine)
    assert demo.main(["--if-empty"]) == 0
    assert "skipped" in capsys.readouterr().out
    assert snapshot(db_engine) == before
    assert demo.main([]) == 1
    assert "already contains" in capsys.readouterr().err
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "production")
    assert demo.main(["--if-empty"]) == 1
    assert "requires DEPLOYMENT_ENVIRONMENT" in capsys.readouterr().err
    assert snapshot(db_engine) == before


def test_fixed_seed_reproduces_the_same_competition(db_engine, demo_env, tmp_path):
    other = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    SQLModel.metadata.create_all(other)
    try:
        demo.seed_demo(db_engine, now=NOW)
        demo.seed_demo(other, now=NOW)
        first, second = snapshot(db_engine), snapshot(other)
        # Argon2 deliberately uses a fresh salt for each account creation.
        first["app_user"][0].pop("password_hash")
        second["app_user"][0].pop("password_hash")
        assert first == second
    finally:
        other.dispose()


def test_database_failure_rolls_back_all_seeded_rows(db_engine, demo_env):
    with Session(db_engine) as session:
        session.add(Group(name="Untouched legacy", is_legacy=True, created_at=NOW))
        session.commit()
    before = snapshot(db_engine)

    def fail_match_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO match_player"):
            raise SQLAlchemyError("Synthetic write failure")

    event.listen(db_engine, "before_cursor_execute", fail_match_insert)
    try:
        with pytest.raises(SQLAlchemyError, match="Synthetic write failure"):
            demo.seed_demo(db_engine, now=NOW)
    finally:
        event.remove(db_engine, "before_cursor_execute", fail_match_insert)
    assert snapshot(db_engine) == before
