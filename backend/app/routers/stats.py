from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from math import isclose
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import GroupContext, require_group
from app.avatar_models import PlayerAvatar
from app.database import get_session
from app.models import Match, MatchPlayerOut, MatchRead, Player, StatsRead

router = APIRouter(prefix="/api/stats", tags=["stats"])

AMS = ZoneInfo("Europe/Amsterdam")
DAYS_NL = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
ELO_INITIAL = 1000.0
ELO_K = 32
MatchMode = Literal["all", "1v1", "2v2"]
StatsPeriod = Literal["all", "30d", "50"]


def _played_at_utc(match: Match) -> datetime:
    played_at = match.played_at
    if played_at.tzinfo is None:
        return played_at.replace(tzinfo=timezone.utc)
    return played_at.astimezone(timezone.utc)


def _match_sort_key(match: Match) -> tuple[datetime, int]:
    return (_played_at_utc(match), match.id or 0)


def _ordered_matches(matches: list[Match]) -> list[Match]:
    return sorted(matches, key=_match_sort_key)


def _filter_matches(
    matches: list[Match], mode: MatchMode, period: StatsPeriod, *, now: datetime | None = None
) -> list[Match]:
    selected = [match for match in _ordered_matches(matches) if mode == "all" or _match_type(match) == mode]
    if period == "50":
        return selected[-50:]
    if period == "30d":
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        local_date = current.astimezone(AMS).date()
        # Include today and the preceding 29 local calendar days, across DST changes.
        start = datetime.combine(local_date - timedelta(days=29), time.min, AMS)
        end = datetime.combine(local_date + timedelta(days=1), time.min, AMS)
        return [match for match in selected if start <= _played_at_utc(match) < end]
    return selected


def _compute_badges(matches: list[Match], players: list[Player]) -> dict[int, list[dict]]:
    """Permanent achievements use the complete group history, never a statistics filter."""
    badges: dict[int, dict[str, dict]] = {player.id: {} for player in players if player.id is not None}
    wins: defaultdict[int, int] = defaultdict(int)
    games: defaultdict[int, int] = defaultdict(int)
    streaks: defaultdict[int, int] = defaultdict(int)
    for match in _ordered_matches(matches):
        for entry in match.players:
            if entry.player_id not in badges:
                continue
            player_id = entry.player_id
            won = entry.side == _winner(match)
            games[player_id] += 1
            wins[player_id] += int(won)
            streaks[player_id] = streaks[player_id] + 1 if won else 0
            earned = []
            if wins[player_id] == 1 and won:
                earned.append(("first_win", "Eerste winst", "⭐", "Je eerste wedstrijd gewonnen."))
            if streaks[player_id] == 5:
                earned.append(("win_streak_5", "Vijf op rij", "🏅", "Vijf wedstrijden achter elkaar gewonnen."))
            if streaks[player_id] == 10:
                earned.append(("win_streak_10", "Tien op rij", "🏆", "Tien wedstrijden achter elkaar gewonnen."))
            if games[player_id] == 50:
                earned.append(("matches_50", "Vaste speler", "🦾", "Vijftig wedstrijden gespeeld."))
            for key, label, emoji, description in earned:
                badges[player_id].setdefault(key, {
                    "key": key, "label": label, "emoji": emoji, "description": description,
                    "earned_at": _played_at_utc(match),
                })
    return {player_id: list(earned.values()) for player_id, earned in badges.items()}


def _match_type(match: Match) -> str:
    return "1v1" if len(match.players) == 2 else "2v2"


def _winner(match: Match) -> str:
    return "orange" if match.orange_score > match.blue_score else "blue"


def _rate(wins: int, total: int) -> float | None:
    return round(wins / total * 100, 1) if total else None


def _score_for_player(match: Match, side: str) -> tuple[int, int]:
    if side == "orange":
        return match.orange_score, match.blue_score
    return match.blue_score, match.orange_score


def _compute_player_stats(matches: list[Match], players: list[Player]) -> list[dict]:
    stats: dict[int, dict] = {}
    for player in players:
        if player.id is None:
            continue
        stats[player.id] = {
            "player_id": player.id,
            "name": player.name,
            "avatar_url": getattr(player, "avatar_url", None),
            "wins": 0,
            "losses": 0,
            "wins_1v1": 0,
            "losses_1v1": 0,
            "wins_2v2": 0,
            "losses_2v2": 0,
            "wins_orange": 0,
            "matches_orange": 0,
            "wins_blue": 0,
            "matches_blue": 0,
            "wins_voor": 0,
            "matches_voor": 0,
            "wins_achter": 0,
            "matches_achter": 0,
            "biggest_victory_margin": 0,
            "biggest_victory_score": None,
            "current_winstreak": 0,
            "longest_winstreak": 0,
            "current_losestreak": 0,
            "longest_losestreak": 0,
            "_goals_for": 0,
            "_goals_against": 0,
            "_ordered_results": [],
        }

    for match in _ordered_matches(matches):
        match_type = _match_type(match)
        winner = _winner(match)

        for match_player in match.players:
            player_stats = stats.get(match_player.player_id)
            if player_stats is None:
                continue

            won = match_player.side == winner
            goals_for, goals_against = _score_for_player(match, match_player.side)
            margin = goals_for - goals_against

            player_stats["wins" if won else "losses"] += 1
            player_stats[f"{'wins' if won else 'losses'}_{match_type}"] += 1
            player_stats[f"matches_{match_player.side}"] += 1
            if won:
                player_stats[f"wins_{match_player.side}"] += 1

            if match_player.position in {"voor", "achter"}:
                player_stats[f"matches_{match_player.position}"] += 1
                if won:
                    player_stats[f"wins_{match_player.position}"] += 1

            player_stats["_goals_for"] += goals_for
            player_stats["_goals_against"] += goals_against
            player_stats["_ordered_results"].append(won)

            # Ordered traversal makes an equal-margin tie resolve to the most recent match.
            if won and margin >= player_stats["biggest_victory_margin"]:
                player_stats["biggest_victory_margin"] = margin
                player_stats["biggest_victory_score"] = f"{goals_for}-{goals_against}"

    result: list[dict] = []
    for player_stats in stats.values():
        ordered_results = player_stats.pop("_ordered_results")
        goals_for = player_stats.pop("_goals_for")
        goals_against = player_stats.pop("_goals_against")
        matches_played = player_stats["wins"] + player_stats["losses"]

        current_win = longest_win = current_loss = longest_loss = 0
        for won in ordered_results:
            if won:
                current_win += 1
                current_loss = 0
                longest_win = max(longest_win, current_win)
            else:
                current_loss += 1
                current_win = 0
                longest_loss = max(longest_loss, current_loss)

        player_stats.update({
            "matches": matches_played,
            "winrate": _rate(player_stats["wins"], matches_played),
            "current_winstreak": current_win,
            "longest_winstreak": longest_win,
            "current_losestreak": current_loss,
            "longest_losestreak": longest_loss,
            "winrate_orange": _rate(player_stats["wins_orange"], player_stats["matches_orange"]),
            "winrate_blue": _rate(player_stats["wins_blue"], player_stats["matches_blue"]),
            "winrate_voor": _rate(player_stats["wins_voor"], player_stats["matches_voor"]),
            "winrate_achter": _rate(player_stats["wins_achter"], player_stats["matches_achter"]),
            "average_goals_for": round(goals_for / matches_played, 1) if matches_played else None,
            "average_goals_against": round(goals_against / matches_played, 1) if matches_played else None,
            "average_goal_difference": round((goals_for - goals_against) / matches_played, 1) if matches_played else None,
            "recent_form": ["W" if won else "L" for won in reversed(ordered_results[-5:])],
        })

        orange_rate = player_stats["winrate_orange"]
        blue_rate = player_stats["winrate_blue"]
        player_stats["color_delta"] = (
            round(orange_rate - blue_rate, 1)
            if orange_rate is not None and blue_rate is not None else None
        )
        front_rate = player_stats["winrate_voor"]
        back_rate = player_stats["winrate_achter"]
        player_stats["position_delta"] = (
            round(front_rate - back_rate, 1)
            if front_rate is not None and back_rate is not None else None
        )
        result.append(player_stats)

    result.sort(key=lambda item: (-item["wins"], item["name"].casefold(), item["player_id"]))
    return result


def _compute_global_stats(matches: list[Match]) -> dict:
    ordered_matches = _ordered_matches(matches)
    counts: defaultdict[str, int] = defaultdict(int)
    day_counts: defaultdict[int, int] = defaultdict(int)
    before_14: defaultdict[int, int] = defaultdict(int)
    from_14: defaultdict[int, int] = defaultdict(int)
    total_goals = 0
    total_difference = 0

    for match in ordered_matches:
        winner = _winner(match)
        match_type = _match_type(match)
        counts[f"{winner}_wins"] += 1
        counts[f"{winner}_wins_{match_type}"] += 1
        counts[f"total_{match_type}"] += 1
        total_goals += match.orange_score + match.blue_score
        total_difference += abs(match.orange_score - match.blue_score)

        amsterdam_time = _played_at_utc(match).astimezone(AMS)
        counts["lunch_matches" if amsterdam_time.hour < 14 else "middag_matches"] += 1
        day_counts[amsterdam_time.weekday()] += 1
        (before_14 if amsterdam_time.hour < 14 else from_14)[amsterdam_time.weekday()] += 1

    current_streak = {"orange": 0, "blue": 0}
    longest_streak = {"orange": 0, "blue": 0}
    for match in ordered_matches:
        winner = _winner(match)
        loser = "blue" if winner == "orange" else "orange"
        current_streak[winner] += 1
        current_streak[loser] = 0
        longest_streak[winner] = max(longest_streak[winner], current_streak[winner])

    total_matches = len(ordered_matches)
    return {
        "total_matches": total_matches,
        "total_1v1": counts["total_1v1"],
        "total_2v2": counts["total_2v2"],
        "average_goals_per_match": round(total_goals / total_matches, 1) if total_matches else None,
        "average_goal_difference": round(total_difference / total_matches, 1) if total_matches else None,
        "orange_wins": counts["orange_wins"],
        "blue_wins": counts["blue_wins"],
        "orange_wins_1v1": counts["orange_wins_1v1"],
        "blue_wins_1v1": counts["blue_wins_1v1"],
        "orange_wins_2v2": counts["orange_wins_2v2"],
        "blue_wins_2v2": counts["blue_wins_2v2"],
        "current_orange_streak": current_streak["orange"],
        "longest_orange_streak": longest_streak["orange"],
        "current_blue_streak": current_streak["blue"],
        "longest_blue_streak": longest_streak["blue"],
        "lunch_matches": counts["lunch_matches"],
        "middag_matches": counts["middag_matches"],
        "matches_per_day": [
            {
                "day": DAYS_NL[index], "count": day_counts[index],
                "before_14": before_14[index], "from_14": from_14[index],
            }
            for index in range(7)
        ],
    }


def _compute_elo(
    matches: list[Match], players: list[Player]
) -> tuple[list[dict], dict[int, int], dict[int, float], dict[int, int]]:
    elo = {player.id: ELO_INITIAL for player in players if player.id is not None}
    names = {player.id: player.name for player in players if player.id is not None}
    avatars = {player.id: getattr(player, "avatar_url", None) for player in players}
    wins: defaultdict[int, int] = defaultdict(int)
    losses: defaultdict[int, int] = defaultdict(int)
    results: defaultdict[int, list[str]] = defaultdict(list)

    for match in _ordered_matches(matches):
        winner = _winner(match)
        teams = {
            side: [mp.player_id for mp in match.players if mp.side == side and mp.player_id in elo]
            for side in ("orange", "blue")
        }
        if not teams["orange"] or not teams["blue"]:
            continue

        average = {
            side: sum(elo[player_id] for player_id in player_ids) / len(player_ids)
            for side, player_ids in teams.items()
        }
        expected_orange = 1 / (1 + 10 ** ((average["blue"] - average["orange"]) / 400))

        for side, expected in (("orange", expected_orange), ("blue", 1 - expected_orange)):
            score = 1.0 if side == winner else 0.0
            for player_id in teams[side]:
                elo[player_id] += ELO_K * (score - expected)
                wins[player_id] += int(score)
                losses[player_id] += int(1 - score)
                results[player_id].append("W" if score else "L")

    elo_int = {player_id: round(value) for player_id, value in elo.items()}
    elo_precise = {player_id: round(value, 1) for player_id, value in elo.items()}
    leaderboard = [
        {
            "player_id": player_id,
            "name": names[player_id],
            "avatar_url": avatars[player_id],
            "elo": elo_int[player_id],
            "elo_precise": elo_precise[player_id],
            "wins": wins[player_id],
            "losses": losses[player_id],
            "winrate": _rate(wins[player_id], wins[player_id] + losses[player_id]) or 0.0,
            "recent_form": list(reversed(results[player_id][-5:])),
        }
        for player_id in elo
        if wins[player_id] + losses[player_id] > 0
    ]
    leaderboard.sort(
        key=lambda item: (-item["elo_precise"], item["name"].casefold(), item["player_id"])
    )

    rank_map: dict[int, int] = {}
    previous_elo: float | None = None
    previous_rank = 0
    for index, entry in enumerate(leaderboard, start=1):
        rank = previous_rank if entry["elo_precise"] == previous_elo else index
        entry["rank"] = rank
        rank_map[entry["player_id"]] = rank
        previous_elo = entry["elo_precise"]
        previous_rank = rank

    return leaderboard, elo_int, elo_precise, rank_map


def _add_matchup_result(bucket: dict, first_id: int, second_id: int, winner_id: int) -> None:
    key = (min(first_id, second_id), max(first_id, second_id))
    data = bucket[key]
    data["total"] += 1
    data["p1" if winner_id == key[0] else "p2"] += 1


def _serialize_matchups(bucket: dict) -> list[dict]:
    return [
        {
            "player1_id": player1_id,
            "player2_id": player2_id,
            "player1_wins": data["p1"],
            "player2_wins": data["p2"],
            "total": data["total"],
        }
        for (player1_id, player2_id), data in sorted(
            bucket.items(), key=lambda item: (-item[1]["total"], item[0])
        )
    ]


def _compute_head_to_head(matches: list[Match]) -> dict:
    new_matchup_bucket = lambda: defaultdict(lambda: {"p1": 0, "p2": 0, "total": 0})
    all_matchups = new_matchup_bucket()
    matchups_1v1 = new_matchup_bucket()
    matchups_2v2 = new_matchup_bucket()
    duo_stats = defaultdict(lambda: {"wins": 0, "total": 0})

    for match in _ordered_matches(matches):
        winner = _winner(match)
        match_type = _match_type(match)
        teams = {
            side: [mp.player_id for mp in match.players if mp.side == side]
            for side in ("orange", "blue")
        }
        matchup_bucket = matchups_1v1 if match_type == "1v1" else matchups_2v2

        for orange_id in teams["orange"]:
            for blue_id in teams["blue"]:
                winner_id = orange_id if winner == "orange" else blue_id
                _add_matchup_result(all_matchups, orange_id, blue_id, winner_id)
                _add_matchup_result(matchup_bucket, orange_id, blue_id, winner_id)

        if match_type == "2v2":
            for side, player_ids in teams.items():
                if len(player_ids) != 2:
                    continue  # Older versions allowed an incomplete team.
                key = tuple(sorted(player_ids))
                duo_stats[key]["total"] += 1
                duo_stats[key]["wins"] += int(side == winner)

    duos = [
        {
            "player1_id": player1_id,
            "player2_id": player2_id,
            "wins": data["wins"],
            "total": data["total"],
            "winrate": _rate(data["wins"], data["total"]) or 0.0,
        }
        for (player1_id, player2_id), data in sorted(
            duo_stats.items(), key=lambda item: (-item[1]["total"], item[0])
        )
    ]
    return {
        "matchups": _serialize_matchups(all_matchups),
        "matchups_1v1": _serialize_matchups(matchups_1v1),
        "matchups_2v2": _serialize_matchups(matchups_2v2),
        "duos": duos,
    }


def _inject_names(head_to_head: dict, players: list[Player]) -> None:
    names = {player.id: player.name for player in players}
    for group in ("matchups", "matchups_1v1", "matchups_2v2", "duos"):
        for item in head_to_head[group]:
            item["player1_name"] = names.get(item["player1_id"], "?")
            item["player2_name"] = names.get(item["player2_id"], "?")


def _joined_names(names: list[str]) -> str:
    ordered = sorted(set(names), key=str.casefold)
    if len(ordered) <= 1:
        return ordered[0] if ordered else "?"
    return f"{', '.join(ordered[:-1])} & {ordered[-1]}"


def _best_players(player_stats: list[dict], score) -> tuple[list[dict], float] | tuple[list, None]:
    if not player_stats:
        return [], None
    best_score = max(score(player) for player in player_stats)
    return [player for player in player_stats if isclose(score(player), best_score)], best_score


def _compute_records(
    matches: list[Match], player_stats: list[dict], head_to_head: dict, players: list[Player]
) -> list[dict]:
    records: list[dict] = []
    names = {player.id: player.name for player in players}
    active_players = [player for player in player_stats if player["matches"] > 0]
    if not active_players:
        return records

    leaders, total_matches = _best_players(active_players, lambda player: player["matches"])
    records.append({
        "key": "ijzeren_man",
        "label": "IJzeren Man",
        "emoji": "🦾",
        "description": "Meeste wedstrijden gespeeld",
        "value": _joined_names([player["name"] for player in leaders]),
        "detail": f"{int(total_matches)} wedstrijden",
    })

    eligible = [player for player in active_players if player["matches"] >= 10]
    if eligible:
        leaders, best_rate = _best_players(eligible, lambda player: player["wins"] / player["matches"])
        records.append({
            "key": "dominant",
            "label": "Dominant",
            "emoji": "👑",
            "description": "Hoogste winrate (min. 10 wedstrijden)",
            "value": _joined_names([player["name"] for player in leaders]),
            "detail": f"{best_rate * 100:.1f}%",
        })

    eligible_duos = [duo for duo in head_to_head["duos"] if duo["total"] >= 5]
    if eligible_duos:
        best_rate = max(duo["winrate"] for duo in eligible_duos)
        leaders = [duo for duo in eligible_duos if isclose(duo["winrate"], best_rate)]
        records.append({
            "key": "koningspaar",
            "label": "Koningspaar",
            "emoji": "🤝",
            "description": "Beste duo (min. 5 wedstrijden samen)",
            "value": " / ".join(
                f"{duo['player1_name']} & {duo['player2_name']}" for duo in leaders
            ),
            "detail": f"{best_rate:.1f}%",
        })

    if head_to_head["matchups"]:
        most_games = max(matchup["total"] for matchup in head_to_head["matchups"])
        leaders = [matchup for matchup in head_to_head["matchups"] if matchup["total"] == most_games]
        records.append({
            "key": "rivalen",
            "label": "Rivalen",
            "emoji": "⚔️",
            "description": "Meeste duels tegen elkaar",
            "value": " / ".join(
                f"{matchup['player1_name']} vs {matchup['player2_name']}" for matchup in leaders
            ),
            "detail": f"{most_games} wedstrijden",
        })

    leaders, current_streak = _best_players(active_players, lambda player: player["current_winstreak"])
    if current_streak:
        records.append({
            "key": "op_dreef",
            "label": "Op Dreef",
            "emoji": "🔥",
            "description": "Langste actieve winstreak",
            "value": _joined_names([player["name"] for player in leaders]),
            "detail": f"{int(current_streak)} op rij",
        })

    leaders, longest_streak = _best_players(active_players, lambda player: player["longest_winstreak"])
    if longest_streak:
        records.append({
            "key": "langste_reeks",
            "label": "Langste Reeks",
            "emoji": "🏆",
            "description": "Langste winstreak binnen de selectie",
            "value": _joined_names([player["name"] for player in leaders]),
            "detail": f"{int(longest_streak)} op rij",
        })

    goal_eligible = [player for player in active_players if player["matches"] >= 10]
    if goal_eligible:
        lowest_against = min(player["average_goals_against"] for player in goal_eligible)
        leaders = [
            player for player in goal_eligible
            if isclose(player["average_goals_against"], lowest_against)
        ]
        records.append({
            "key": "muurvast",
            "label": "Muurvast",
            "emoji": "🧱",
            "description": "Minste goals tegen per wedstrijd (min. 10)",
            "value": _joined_names([player["name"] for player in leaders]),
            "detail": f"{lowest_against:.1f} gem. tegen",
        })

        highest_for = max(player["average_goals_for"] for player in goal_eligible)
        leaders = [
            player for player in goal_eligible
            if isclose(player["average_goals_for"], highest_for)
        ]
        records.append({
            "key": "doelpuntenmachine",
            "label": "Doelpuntenmachine",
            "emoji": "💥",
            "description": "Meeste goals voor per wedstrijd (min. 10)",
            "value": _joined_names([player["name"] for player in leaders]),
            "detail": f"{highest_for:.1f} gem. voor",
        })

    ordered_matches = _ordered_matches(matches)
    if ordered_matches:
        biggest = max(
            ordered_matches,
            key=lambda match: (abs(match.orange_score - match.blue_score), _match_sort_key(match)),
        )
        winner = _winner(biggest)
        winner_names = [
            names.get(match_player.player_id, "?")
            for match_player in biggest.players if match_player.side == winner
        ]
        winner_score, loser_score = _score_for_player(biggest, winner)
        records.append({
            "key": "grootste_afstraffing",
            "label": "Grootste Afstraffing",
            "emoji": "💀",
            "description": "Grootste verschil in één wedstrijd",
            "value": _joined_names(winner_names),
            "detail": f"{winner_score}-{loser_score}",
        })

    return records


@router.get("", response_model=StatsRead, response_model_by_alias=True)
def get_stats(
    mode: MatchMode = "all",
    period: StatsPeriod = "all",
    session: Session = Depends(get_session),
    group: GroupContext = Depends(require_group),
):
    history = list(session.exec(select(Match).where(Match.group_id == group.id)).all())
    players = list(session.exec(select(Player).where(Player.group_id == group.id)).all())
    result = _build_stats(history, players, mode, period)
    # Fetch only metadata; PNG blobs can be large and do not belong in the stats query.
    avatar_versions = session.exec(
        select(PlayerAvatar.player_id, PlayerAvatar.version).where(PlayerAvatar.group_id == group.id)
    ).all()
    avatars = {player_id: f"/api/avatars/players/{player_id}.png?v={version}" for player_id, version in avatar_versions}
    for bucket in (result["players"], result["leaderboard"]):
        for player in bucket:
            player["avatar_url"] = avatars.get(player["player_id"])
    return result


def _build_stats(
    history: list[Match], players: list[Player], mode: MatchMode = "all", period: StatsPeriod = "all",
    *, now: datetime | None = None,
) -> dict:
    matches = _filter_matches(history, mode, period, now=now)

    player_stats = _compute_player_stats(matches, players)
    global_stats = _compute_global_stats(matches)
    leaderboard, elo_map, precise_elo_map, rank_map = _compute_elo(matches, players)
    head_to_head = _compute_head_to_head(matches)
    _inject_names(head_to_head, players)

    for player in player_stats:
        player_id = player["player_id"]
        player["elo"] = elo_map.get(player_id, round(ELO_INITIAL))
        player["elo_precise"] = precise_elo_map.get(player_id, ELO_INITIAL)
        player["rank"] = rank_map.get(player_id)

    records = _compute_records(matches, player_stats, head_to_head, players)
    badges = _compute_badges(history, players)
    lifetime_stats = {player["player_id"]: player for player in _compute_player_stats(history, players)}
    for player in player_stats:
        player["badges"] = badges[player["player_id"]]
        # Current flames must describe the actual streak, even when looking at older/subset results.
        for field in ("current_winstreak", "longest_winstreak", "current_losestreak", "longest_losestreak"):
            player[field] = lifetime_stats[player["player_id"]][field]
    return {
        "filters": {"mode": mode, "period": period},
        "players": player_stats,
        "global": global_stats,
        "leaderboard": leaderboard,
        "head_to_head": head_to_head,
        "records": records,
        "recent_matches": [
            MatchRead(
                id=match.id, orange_score=match.orange_score, blue_score=match.blue_score,
                played_at=_played_at_utc(match),
                players=[MatchPlayerOut.model_validate(entry, from_attributes=True) for entry in match.players],
            ) for match in reversed(matches[-5:])
        ],
    }
