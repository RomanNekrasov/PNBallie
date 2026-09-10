from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import GroupContext, require_group
from app.avatar_models import PlayerAvatar
from app.database import get_session
from app.models import Group, Match, MatchPlayer, Player, StatsRead, User
from app.routers.stats import (
    _build_stats,
    _compute_elo,
    _compute_global_stats,
    _compute_head_to_head,
    _compute_player_stats,
    _compute_records,
    _filter_matches,
    _inject_names,
    router,
)


def player(player_id: int, name: str) -> Player:
    return Player(id=player_id, name=name)


def match(
    match_id: int,
    played_at: datetime,
    orange_score: int,
    blue_score: int,
    entries: list[tuple[int, str, str]],
) -> Match:
    result = Match(
        id=match_id,
        played_at=played_at,
        orange_score=orange_score,
        blue_score=blue_score,
    )
    result.players = [
        MatchPlayer(
            id=index,
            match_id=match_id,
            player_id=player_id,
            side=side,
            position=position,
        )
        for index, (player_id, side, position) in enumerate(entries, start=match_id * 10)
    ]
    return result


@pytest.fixture
def four_players() -> list[Player]:
    return [player(1, "Ada"), player(2, "Bo"), player(3, "Cleo"), player(4, "Daan")]


def test_player_totals_rates_goals_form_and_exact_biggest_win(four_players):
    timestamp = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    matches = [
        match(1, timestamp, 10, 4, [(1, "orange", "solo"), (2, "blue", "solo")]),
        match(2, timestamp, 8, 10, [(1, "orange", "solo"), (2, "blue", "solo")]),
        match(3, timestamp, 10, 4, [(1, "orange", "solo"), (2, "blue", "solo")]),
    ]

    stats = _compute_player_stats(list(reversed(matches)), four_players)
    ada = next(item for item in stats if item["player_id"] == 1)

    assert (ada["wins"], ada["losses"], ada["winrate"]) == (2, 1, 66.7)
    assert ada["recent_form"] == ["W", "L", "W"]
    assert ada["average_goals_for"] == 9.3
    assert ada["average_goals_against"] == 6.0
    assert ada["average_goal_difference"] == 3.3
    assert ada["biggest_victory_margin"] == 6
    assert ada["biggest_victory_score"] == "10-4"
    assert ada["longest_winstreak"] == 1


def test_global_totals_timezone_activity_and_goal_average(four_players):
    matches = [
        match(1, datetime(2026, 1, 5, 11, 30), 10, 8, [(1, "orange", "solo"), (2, "blue", "solo")]),
        match(2, datetime(2026, 1, 5, 14, tzinfo=timezone.utc), 7, 10, [
            (1, "orange", "voor"), (3, "orange", "achter"),
            (2, "blue", "voor"), (4, "blue", "achter"),
        ]),
    ]
    stats = _compute_global_stats(matches)

    assert stats["total_matches"] == 2
    assert (stats["total_1v1"], stats["total_2v2"]) == (1, 1)
    assert stats["average_goals_per_match"] == 17.5
    assert stats["average_goal_difference"] == 2.5
    assert (stats["lunch_matches"], stats["middag_matches"]) == (1, 1)
    assert stats["matches_per_day"][0] == {"day": "Maandag", "count": 2, "before_14": 1, "from_14": 1}
    assert stats["current_blue_streak"] == 1


def test_elo_is_deterministic_and_uses_shared_display_ranks(four_players):
    timestamp = datetime(2026, 1, 5, tzinfo=timezone.utc)
    matches = [
        match(2, timestamp, 10, 8, [(3, "orange", "solo"), (4, "blue", "solo")]),
        match(1, timestamp, 10, 8, [(1, "orange", "solo"), (2, "blue", "solo")]),
    ]
    leaderboard, _, _, _ = _compute_elo(matches, four_players)

    assert [(entry["name"], entry["elo_precise"], entry["rank"]) for entry in leaderboard] == [
        ("Ada", 1016.0, 1),
        ("Cleo", 1016.0, 1),
        ("Bo", 984.0, 3),
        ("Daan", 984.0, 3),
    ]


def test_head_to_head_separates_1v1_2v2_and_duo_results(four_players):
    matches = [
        match(1, datetime(2026, 1, 1), 10, 5, [(1, "orange", "solo"), (2, "blue", "solo")]),
        match(2, datetime(2026, 1, 2), 6, 10, [
            (1, "orange", "voor"), (3, "orange", "achter"),
            (2, "blue", "voor"), (4, "blue", "achter"),
        ]),
    ]
    head_to_head = _compute_head_to_head(matches)
    _inject_names(head_to_head, four_players)

    pair_1v1 = head_to_head["matchups_1v1"][0]
    pair_2v2 = next(item for item in head_to_head["matchups_2v2"] if item["player1_id"] == 1 and item["player2_id"] == 2)
    combined = next(item for item in head_to_head["matchups"] if item["player1_id"] == 1 and item["player2_id"] == 2)

    assert (pair_1v1["player1_wins"], pair_1v1["player2_wins"], pair_1v1["total"]) == (1, 0, 1)
    assert (pair_2v2["player1_wins"], pair_2v2["player2_wins"], pair_2v2["total"]) == (0, 1, 1)
    assert (combined["player1_wins"], combined["player2_wins"], combined["total"]) == (1, 1, 2)
    assert any(duo["player1_id"] == 2 and duo["player2_id"] == 4 and duo["wins"] == 1 for duo in head_to_head["duos"])


def test_awards_include_aggregate_ties_and_use_latest_single_match(four_players):
    matches = [
        match(1, datetime(2026, 1, 1), 10, 2, [(1, "orange", "solo"), (2, "blue", "solo")]),
        match(2, datetime(2026, 1, 2), 2, 10, [(1, "orange", "solo"), (2, "blue", "solo")]),
    ]
    player_stats = _compute_player_stats(matches, four_players)
    head_to_head = _compute_head_to_head(matches)
    _inject_names(head_to_head, four_players)
    records = _compute_records(matches, player_stats, head_to_head, four_players)

    iron = next(record for record in records if record["key"] == "ijzeren_man")
    biggest = next(record for record in records if record["key"] == "grootste_afstraffing")
    assert iron["value"] == "Ada & Bo"
    assert biggest["value"] == "Bo"
    assert biggest["detail"] == "10-2"
    assert not any(record["key"] == "hoogste_score" for record in records)


def test_empty_statistics_are_safe(four_players):
    player_stats = _compute_player_stats([], four_players)
    global_stats = _compute_global_stats([])
    leaderboard, _, _, _ = _compute_elo([], four_players)
    head_to_head = _compute_head_to_head([])

    assert all(player["matches"] == 0 and player["recent_form"] == [] for player in player_stats)
    assert global_stats["total_matches"] == 0
    assert global_stats["average_goals_per_match"] is None
    assert global_stats["average_goal_difference"] is None
    assert leaderboard == []
    assert head_to_head == {"matchups": [], "matchups_1v1": [], "matchups_2v2": [], "duos": []}


@pytest.mark.parametrize("day,utc_boundary", [(datetime(2026, 1, 5), 13), (datetime(2026, 7, 6), 12)])
def test_activity_boundary_uses_amsterdam_winter_and_summer_time(day, utc_boundary):
    entries = [(1, "orange", "solo"), (2, "blue", "solo")]
    boundary = day.replace(hour=utc_boundary, tzinfo=timezone.utc)
    stats = _compute_global_stats([
        match(1, boundary - timedelta(seconds=1), 10, 3, entries),
        match(2, boundary, 10, 5, entries),
    ])
    assert stats["lunch_matches"] == stats["middag_matches"] == 1
    assert stats["matches_per_day"][0] == {"day": "Maandag", "count": 2, "before_14": 1, "from_14": 1}


def test_activity_uses_local_day_instead_of_utc_day():
    stats = _compute_global_stats([
        match(1, datetime(2026, 7, 5, 23), 10, 6, [(1, "orange", "solo"), (2, "blue", "solo")]),
    ])
    assert stats["matches_per_day"][0]["count"] == 1
    assert stats["matches_per_day"][6]["count"] == 0


@pytest.mark.parametrize("mode,expected", [("all", 2), ("1v1", 1), ("2v2", 1)])
def test_mode_filter_applies_to_all_statistics_and_recent_matches(four_players, mode, expected):
    history = [
        match(1, datetime(2026, 1, 1), 10, 5, [(1, "orange", "solo"), (2, "blue", "solo")]),
        match(2, datetime(2026, 1, 2), 6, 10, [
            (1, "orange", "voor"), (3, "orange", "achter"),
            (2, "blue", "voor"), (4, "blue", "achter"),
        ]),
    ]
    data = _build_stats(history, four_players, mode=mode)
    assert data["global"]["total_matches"] == expected
    assert data["players"][0]["matches"] == expected
    assert len(data["recent_matches"]) == expected
    assert data["head_to_head"]["matchups"][0]["total"] == expected
    ada_rank = next(entry for entry in data["leaderboard"] if entry["player_id"] == 1)
    assert ada_rank["wins"] + ada_rank["losses"] == expected
    assert data["records"][0]["detail"] == f"{expected} wedstrijden"
    assert data["filters"] == {"mode": mode, "period": "all"}
    if mode == "1v1":
        assert data["head_to_head"]["duos"] == []
        assert data["global"]["blue_wins"] == 0
    if mode == "2v2":
        assert data["head_to_head"]["matchups_1v1"] == []
        assert data["global"]["orange_wins"] == 0


@pytest.mark.parametrize("now,start_utc,end_utc", [
    # Starts before the spring transition; uses midnight CET even though now is CEST.
    (datetime(2026, 4, 5, 10, tzinfo=timezone.utc), datetime(2026, 3, 6, 23), datetime(2026, 4, 5, 22)),
    # Starts before the autumn transition; uses midnight CEST even though now is CET.
    (datetime(2026, 11, 5, 10, tzinfo=timezone.utc), datetime(2026, 10, 6, 22), datetime(2026, 11, 5, 23)),
])
def test_last_30_calendar_days_crosses_dst_with_precise_inclusive_start_exclusive_end(now, start_utc, end_utc):
    entries = [(1, "orange", "solo"), (2, "blue", "solo")]
    history = [
        match(1, start_utc - timedelta(seconds=1), 10, 3, entries),
        match(2, start_utc, 10, 3, entries),
        match(3, end_utc - timedelta(seconds=1), 10, 3, entries),
        match(4, end_utc, 10, 3, entries),
    ]
    assert [item.id for item in _filter_matches(history, "all", "30d", now=now)] == [2, 3]


def test_last_50_is_after_mode_filter_and_timestamp_ties_are_deterministic():
    entries = [(1, "orange", "solo"), (2, "blue", "solo")]
    timestamp = datetime(2026, 1, 1)
    history = [match(index, timestamp, 10, 4, entries) for index in range(1, 56)]
    history += [match(100, timestamp + timedelta(days=1), 10, 2, [
        (1, "orange", "voor"), (3, "orange", "achter"), (2, "blue", "voor"), (4, "blue", "achter"),
    ])]
    assert [item.id for item in _filter_matches(list(reversed(history)), "1v1", "50")] == list(range(6, 56))


def test_badges_survive_lost_streak_mode_and_period_filters(four_players):
    entries = [(1, "orange", "solo"), (2, "blue", "solo")]
    history = [match(index, datetime(2026, 1, index), 10, 4, entries) for index in range(1, 6)]
    history += [match(6, datetime(2026, 8, 2), 4, 10, [
        (1, "orange", "voor"), (3, "orange", "achter"), (2, "blue", "voor"), (4, "blue", "achter"),
    ])]
    for mode, period in [("all", "all"), ("2v2", "30d"), ("1v1", "30d"), ("all", "50")]:
        data = _build_stats(history, four_players, mode, period, now=datetime(2026, 8, 10, tzinfo=timezone.utc))
        ada = next(player for player in data["players"] if player["player_id"] == 1)
        badge = next(badge for badge in ada["badges"] if badge["key"] == "win_streak_5")
        assert badge["earned_at"] == datetime(2026, 1, 5, tzinfo=timezone.utc)
        assert ada["current_winstreak"] == 0
        assert ada["longest_winstreak"] == 5
        if mode == "1v1":
            assert ada["matches"] == 0


def test_badge_first_award_date_is_not_replaced_by_later_streak(four_players):
    entries = [(1, "orange", "solo"), (2, "blue", "solo")]
    history = [match(index, datetime(2026, 1, index), 10, 4, entries) for index in range(1, 6)]
    history += [match(6, datetime(2026, 1, 6), 3, 10, entries)]
    history += [match(index, datetime(2026, 1, index), 10, 4, entries) for index in range(7, 12)]
    ada = _build_stats(history, four_players)["players"][0]
    badges = [badge for badge in ada["badges"] if badge["key"] == "win_streak_5"]
    assert len(badges) == 1
    assert badges[0]["earned_at"] == datetime(2026, 1, 5, tzinfo=timezone.utc)


def test_stats_serializes_naive_sqlite_time_as_utc_z(four_players):
    history = [match(1, datetime(2026, 1, 1, 12), 10, 3, [(1, "orange", "solo"), (2, "blue", "solo")])]
    data = StatsRead.model_validate(_build_stats(history, four_players)).model_dump(mode="json", by_alias=True)
    assert data["recent_matches"][0]["played_at"] == "2026-01-01T12:00:00Z"
    assert data["players"][0]["badges"][0]["earned_at"] == "2026-01-01T12:00:00Z"


def test_stats_endpoint_scopes_every_payload_to_selected_group():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(router)
    user = User(id=1, email="stats@example.test", display_name="Stats")
    group = GroupContext(id=1, role="member", user=user)
    with Session(engine) as session:
        session.add_all([Group(id=1, name="Ours"), Group(id=2, name="Other")])
        session.add_all([
            Player(id=1, name="Ada", group_id=1), Player(id=2, name="Bo", group_id=1, is_active=False),
            Player(id=3, name="Secret", group_id=2), Player(id=4, name="Private", group_id=2),
        ])
        first = match(1, datetime(2026, 1, 1), 10, 4, [(1, "orange", "solo"), (2, "blue", "solo")])
        other = match(2, datetime(2026, 1, 2), 10, 3, [(3, "orange", "solo"), (4, "blue", "solo")])
        other.group_id = 2
        session.add_all([first, other])
        session.add_all([
            PlayerAvatar(player_id=1, group_id=1, version="ours", png=b"our png"),
            PlayerAvatar(player_id=3, group_id=2, version="theirs", png=b"their png"),
        ])
        session.commit()
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[require_group] = lambda: group
        client = TestClient(app)
        response = client.get("/api/stats?mode=1v1&period=50")
        assert response.status_code == 200
        data = response.json()
        assert data["global"]["total_matches"] == 1
        assert {player["player_id"] for player in data["players"]} == {1, 2}
        assert [match["id"] for match in data["recent_matches"]] == [1]
        assert "Secret" not in response.text and "Private" not in response.text
        assert data["players"][0]["avatar_url"] == "/api/avatars/players/1.png?v=ours"
        assert data["leaderboard"][0]["avatar_url"] == "/api/avatars/players/1.png?v=ours"
        assert "theirs" not in response.text
        assert client.get("/api/stats?mode=3v3").status_code == 422
        assert client.get("/api/stats?period=invalid").status_code == 422
    engine.dispose()
