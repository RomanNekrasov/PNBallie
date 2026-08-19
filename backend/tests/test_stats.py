from datetime import datetime, timezone

import pytest

from app.models import Match, MatchPlayer, Player
from app.routers.stats import (
    _compute_elo,
    _compute_global_stats,
    _compute_head_to_head,
    _compute_player_stats,
    _compute_records,
    _inject_names,
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
    assert (stats["lunch_matches"], stats["middag_matches"]) == (1, 1)
    assert stats["matches_per_day"][0] == {"day": "Maandag", "count": 2}
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


def test_empty_statistics_are_safe(four_players):
    player_stats = _compute_player_stats([], four_players)
    global_stats = _compute_global_stats([])
    leaderboard, _, _, _ = _compute_elo([], four_players)
    head_to_head = _compute_head_to_head([])

    assert all(player["matches"] == 0 and player["recent_form"] == [] for player in player_stats)
    assert global_stats["total_matches"] == 0
    assert global_stats["average_goals_per_match"] is None
    assert leaderboard == []
    assert head_to_head == {"matchups": [], "matchups_1v1": [], "matchups_2v2": [], "duos": []}
