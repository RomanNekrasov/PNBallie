from collections import defaultdict
from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Match, MatchPlayer, Player

router = APIRouter(prefix="/api/stats", tags=["stats"])

AMS = ZoneInfo("Europe/Amsterdam")
DAYS_NL = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]


def _match_type(m: Match) -> str:
    return "1v1" if len(m.players) == 2 else "2v2"


def _winner(m: Match) -> str:
    return "orange" if m.orange_score > m.blue_score else "blue"


def _compute_player_stats(matches: list[Match], players: list[Player]) -> list[dict]:
    player_map = {p.id: p.name for p in players}
    stats: dict[int, dict] = {}

    for pid, name in player_map.items():
        stats[pid] = {
            "player_id": pid,
            "name": name,
            "wins": 0, "losses": 0,
            "wins_1v1": 0, "losses_1v1": 0,
            "wins_2v2": 0, "losses_2v2": 0,
            "wins_orange": 0, "matches_orange": 0,
            "wins_blue": 0, "matches_blue": 0,
            "wins_voor": 0, "matches_voor": 0,
            "wins_achter": 0, "matches_achter": 0,
            "biggest_victory_margin": 0,
            "current_winstreak": 0,
            "longest_winstreak": 0,
            "current_losestreak": 0,
            "longest_losestreak": 0,
            "_ordered_results": [],
        }

    for m in sorted(matches, key=lambda x: x.played_at):
        mt = _match_type(m)
        winner = _winner(m)
        margin = abs(m.orange_score - m.blue_score)

        for mp in m.players:
            pid = mp.player_id
            if pid not in stats:
                continue
            s = stats[pid]
            won = mp.side == winner

            if won:
                s["wins"] += 1
            else:
                s["losses"] += 1

            if mt == "1v1":
                if won:
                    s["wins_1v1"] += 1
                else:
                    s["losses_1v1"] += 1
            else:
                if won:
                    s["wins_2v2"] += 1
                else:
                    s["losses_2v2"] += 1

            if mp.side == "orange":
                s["matches_orange"] += 1
                if won:
                    s["wins_orange"] += 1
            else:
                s["matches_blue"] += 1
                if won:
                    s["wins_blue"] += 1

            # "solo" counts as neither voor nor achter for position stats
            if mp.position == "voor":
                s["matches_voor"] += 1
                if won:
                    s["wins_voor"] += 1
            elif mp.position == "achter":
                s["matches_achter"] += 1
                if won:
                    s["wins_achter"] += 1

            if won and margin > s["biggest_victory_margin"]:
                s["biggest_victory_margin"] = margin

            s["_ordered_results"].append(won)

    result = []
    for s in stats.values():
        results = s.pop("_ordered_results")
        cur_win = 0
        max_win = 0
        cur_lose = 0
        max_lose = 0
        for won in results:
            if won:
                cur_win += 1
                cur_lose = 0
                if cur_win > max_win:
                    max_win = cur_win
            else:
                cur_lose += 1
                cur_win = 0
                if cur_lose > max_lose:
                    max_lose = cur_lose
        s["current_winstreak"] = cur_win
        s["longest_winstreak"] = max_win
        s["current_losestreak"] = cur_lose
        s["longest_losestreak"] = max_lose

        total_orange = s["matches_orange"]
        total_blue = s["matches_blue"]
        s["winrate_orange"] = round(s["wins_orange"] / total_orange * 100, 1) if total_orange else None
        s["winrate_blue"] = round(s["wins_blue"] / total_blue * 100, 1) if total_blue else None
        s["winrate_voor"] = round(s["wins_voor"] / s["matches_voor"] * 100, 1) if s["matches_voor"] else None
        s["winrate_achter"] = round(s["wins_achter"] / s["matches_achter"] * 100, 1) if s["matches_achter"] else None

        if s["winrate_orange"] is not None and s["winrate_blue"] is not None:
            s["color_delta"] = round(s["winrate_orange"] - s["winrate_blue"], 1)
        else:
            s["color_delta"] = None

        if s["winrate_voor"] is not None and s["winrate_achter"] is not None:
            s["position_delta"] = round(s["winrate_voor"] - s["winrate_achter"], 1)
        else:
            s["position_delta"] = None

        result.append(s)

    result.sort(key=lambda x: x["wins"], reverse=True)
    return result


def _compute_global_stats(matches: list[Match]) -> dict:
    total = len(matches)
    orange_wins = 0
    blue_wins = 0
    orange_wins_1v1 = 0
    blue_wins_1v1 = 0
    orange_wins_2v2 = 0
    blue_wins_2v2 = 0
    lunch_matches = 0
    middag_matches = 0
    day_counts: dict[int, int] = defaultdict(int)

    sorted_matches = sorted(matches, key=lambda x: x.played_at)

    for m in sorted_matches:
        winner = _winner(m)
        mt = _match_type(m)

        if winner == "orange":
            orange_wins += 1
            if mt == "1v1":
                orange_wins_1v1 += 1
            else:
                orange_wins_2v2 += 1
        else:
            blue_wins += 1
            if mt == "1v1":
                blue_wins_1v1 += 1
            else:
                blue_wins_2v2 += 1

        if m.played_at.tzinfo is None:
            ams_time = m.played_at.replace(tzinfo=timezone.utc).astimezone(AMS)
        else:
            ams_time = m.played_at.astimezone(AMS)

        if ams_time.hour < 14:
            lunch_matches += 1
        else:
            middag_matches += 1

        day_counts[ams_time.weekday()] += 1

    # Color streaks
    cur_orange = 0
    max_orange = 0
    cur_blue = 0
    max_blue = 0
    for m in sorted_matches:
        if _winner(m) == "orange":
            cur_orange += 1
            cur_blue = 0
            if cur_orange > max_orange:
                max_orange = cur_orange
        else:
            cur_blue += 1
            cur_orange = 0
            if cur_blue > max_blue:
                max_blue = cur_blue

    matches_per_day = [
        {"day": DAYS_NL[i], "count": day_counts.get(i, 0)}
        for i in range(7)
    ]

    return {
        "total_matches": total,
        "orange_wins": orange_wins,
        "blue_wins": blue_wins,
        "orange_wins_1v1": orange_wins_1v1,
        "blue_wins_1v1": blue_wins_1v1,
        "orange_wins_2v2": orange_wins_2v2,
        "blue_wins_2v2": blue_wins_2v2,
        "current_orange_streak": cur_orange,
        "longest_orange_streak": max_orange,
        "current_blue_streak": cur_blue,
        "longest_blue_streak": max_blue,
        "lunch_matches": lunch_matches,
        "middag_matches": middag_matches,
        "matches_per_day": matches_per_day,
    }


@router.get("")
def get_stats(session: Session = Depends(get_session)):
    matches = list(session.exec(select(Match)).all())
    players = list(session.exec(select(Player)).all())
    return {
        "players": _compute_player_stats(matches, players),
        "global": _compute_global_stats(matches),
    }
