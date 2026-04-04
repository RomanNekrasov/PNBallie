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


def _compute_elo(matches: list[Match], players: list[Player]) -> tuple[list[dict], dict[int, int]]:
    """Compute Elo ratings from match history. Returns (leaderboard, elo_map)."""
    K = 32
    elo: dict[int, float] = {p.id: 1000.0 for p in players}
    name_map = {p.id: p.name for p in players}
    wins_map: dict[int, int] = defaultdict(int)
    losses_map: dict[int, int] = defaultdict(int)

    for m in sorted(matches, key=lambda x: x.played_at):
        winner = _winner(m)
        orange_pids = [mp.player_id for mp in m.players if mp.side == "orange"]
        blue_pids = [mp.player_id for mp in m.players if mp.side == "blue"]

        if not orange_pids or not blue_pids:
            continue

        orange_elo = sum(elo.get(pid, 1000) for pid in orange_pids) / len(orange_pids)
        blue_elo = sum(elo.get(pid, 1000) for pid in blue_pids) / len(blue_pids)

        expected_orange = 1 / (1 + 10 ** ((blue_elo - orange_elo) / 400))
        expected_blue = 1 - expected_orange

        orange_score = 1.0 if winner == "orange" else 0.0
        blue_score = 1.0 - orange_score

        for pid in orange_pids:
            elo[pid] += K * (orange_score - expected_orange)
            if winner == "orange":
                wins_map[pid] += 1
            else:
                losses_map[pid] += 1

        for pid in blue_pids:
            elo[pid] += K * (blue_score - expected_blue)
            if winner == "blue":
                wins_map[pid] += 1
            else:
                losses_map[pid] += 1

    elo_int = {pid: round(e) for pid, e in elo.items()}
    leaderboard = sorted(
        [
            {
                "player_id": pid,
                "name": name_map[pid],
                "elo": elo_int[pid],
                "wins": wins_map.get(pid, 0),
                "losses": losses_map.get(pid, 0),
            }
            for pid in elo_int
            if wins_map.get(pid, 0) + losses_map.get(pid, 0) > 0
        ],
        key=lambda x: x["elo"],
        reverse=True,
    )
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard, elo_int


def _compute_head_to_head(matches: list[Match]) -> dict:
    """Compute head-to-head matchups and duo stats."""
    # Matchups: pairs on opposite teams
    matchup_wins: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {"p1": 0, "p2": 0, "total": 0})
    # Duos: pairs on same team
    duo_stats: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {"wins": 0, "total": 0})

    name_map: dict[int, str] = {}

    for m in matches:
        orange_pids = []
        blue_pids = []
        for mp in m.players:
            name_map[mp.player_id] = ""  # filled below
            if mp.side == "orange":
                orange_pids.append(mp.player_id)
            else:
                blue_pids.append(mp.player_id)

        winner = _winner(m)

        # Matchups: every orange vs every blue player
        for o_pid in orange_pids:
            for b_pid in blue_pids:
                key = (min(o_pid, b_pid), max(o_pid, b_pid))
                matchup_wins[key]["total"] += 1
                if winner == "orange":
                    if o_pid == key[0]:
                        matchup_wins[key]["p1"] += 1
                    else:
                        matchup_wins[key]["p2"] += 1
                else:
                    if b_pid == key[0]:
                        matchup_wins[key]["p1"] += 1
                    else:
                        matchup_wins[key]["p2"] += 1

        # Duos: teammates in 2v2
        for team_pids, side in [(orange_pids, "orange"), (blue_pids, "blue")]:
            if len(team_pids) == 2:
                key = (min(team_pids), max(team_pids))
                duo_stats[key]["total"] += 1
                if winner == side:
                    duo_stats[key]["wins"] += 1

    # Resolve names
    # We need to get names from match players
    for m in matches:
        for mp in m.players:
            if hasattr(mp, "player") and mp.player:
                name_map[mp.player_id] = mp.player.name

    # If names not available via relationship, we'll pass them in
    # For now, build result with IDs and names will be injected

    matchups = []
    for (p1, p2), data in sorted(matchup_wins.items(), key=lambda x: x[1]["total"], reverse=True):
        matchups.append({
            "player1_id": p1,
            "player2_id": p2,
            "player1_wins": data["p1"],
            "player2_wins": data["p2"],
            "total": data["total"],
        })

    duos = []
    for (p1, p2), data in sorted(duo_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        winrate = round(data["wins"] / data["total"] * 100, 1) if data["total"] else 0
        duos.append({
            "player1_id": p1,
            "player2_id": p2,
            "wins": data["wins"],
            "total": data["total"],
            "winrate": winrate,
        })

    return {"matchups": matchups, "duos": duos}


def _inject_names(h2h: dict, players: list[Player]) -> None:
    """Inject player names into head-to-head data."""
    name_map = {p.id: p.name for p in players}
    for item in h2h["matchups"]:
        item["player1_name"] = name_map.get(item["player1_id"], "?")
        item["player2_name"] = name_map.get(item["player2_id"], "?")
    for item in h2h["duos"]:
        item["player1_name"] = name_map.get(item["player1_id"], "?")
        item["player2_name"] = name_map.get(item["player2_id"], "?")


def _compute_records(
    matches: list[Match],
    player_stats: list[dict],
    h2h: dict,
    players: list[Player],
) -> list[dict]:
    """Compute fun/novelty records."""
    records = []
    name_map = {p.id: p.name for p in players}

    if not player_stats:
        return records

    # IJzeren Man — most matches played
    most_matches = max(player_stats, key=lambda p: p["wins"] + p["losses"])
    total_m = most_matches["wins"] + most_matches["losses"]
    if total_m > 0:
        records.append({
            "key": "ijzeren_man",
            "label": "IJzeren Man",
            "emoji": "\U0001F9BE",
            "description": "Meeste wedstrijden gespeeld",
            "value": most_matches["name"],
            "detail": f"{total_m} wedstrijden",
        })

    # Dominant — highest winrate (min 10 matches)
    eligible = [p for p in player_stats if p["wins"] + p["losses"] >= 10]
    if eligible:
        best = max(eligible, key=lambda p: p["wins"] / (p["wins"] + p["losses"]))
        wr = round(best["wins"] / (best["wins"] + best["losses"]) * 100, 1)
        records.append({
            "key": "dominant",
            "label": "Dominant",
            "emoji": "\U0001F451",
            "description": "Hoogste winrate (min. 10 wedstrijden)",
            "value": best["name"],
            "detail": f"{wr}%",
        })

    # Koningspaar — best duo (min 5 games)
    eligible_duos = [d for d in h2h["duos"] if d["total"] >= 5]
    if eligible_duos:
        best_duo = max(eligible_duos, key=lambda d: d["winrate"])
        records.append({
            "key": "koningspaar",
            "label": "Koningspaar",
            "emoji": "\U0001F91D",
            "description": "Beste duo (min. 5 wedstrijden samen)",
            "value": f"{best_duo['player1_name']} & {best_duo['player2_name']}",
            "detail": f"{best_duo['winrate']}% ({best_duo['wins']}/{best_duo['total']})",
        })

    # Rivalen — most games against each other
    if h2h["matchups"]:
        rivals = h2h["matchups"][0]  # already sorted by total desc
        records.append({
            "key": "rivalen",
            "label": "Rivalen",
            "emoji": "\u2694\uFE0F",
            "description": "Meeste duels tegen elkaar",
            "value": f"{rivals['player1_name']} vs {rivals['player2_name']}",
            "detail": f"{rivals['total']} wedstrijden ({rivals['player1_wins']}-{rivals['player2_wins']})",
        })

    # Op Dreef — longest current win streak
    if player_stats:
        best_streak = max(player_stats, key=lambda p: p["current_winstreak"])
        if best_streak["current_winstreak"] > 0:
            records.append({
                "key": "op_dreef",
                "label": "Op Dreef",
                "emoji": "\U0001F525",
                "description": "Langste actieve winstreak",
                "value": best_streak["name"],
                "detail": f"{best_streak['current_winstreak']} op rij",
            })

    # Langste Reeks Ooit — all-time longest win streak
    if player_stats:
        longest = max(player_stats, key=lambda p: p["longest_winstreak"])
        if longest["longest_winstreak"] > 0:
            records.append({
                "key": "langste_reeks",
                "label": "Langste Reeks Ooit",
                "emoji": "\U0001F3C6",
                "description": "Langste winstreak aller tijden",
                "value": longest["name"],
                "detail": f"{longest['longest_winstreak']} op rij",
            })

    # Muurvast — lowest avg goals conceded (min 10 matches)
    # Doelpuntenmachine — highest avg goals scored (min 10 matches)
    goals_data: dict[int, dict] = defaultdict(lambda: {"conceded": 0, "scored": 0, "matches": 0})
    for m in matches:
        for mp in m.players:
            pid = mp.player_id
            goals_data[pid]["matches"] += 1
            if mp.side == "orange":
                goals_data[pid]["scored"] += m.orange_score
                goals_data[pid]["conceded"] += m.blue_score
            else:
                goals_data[pid]["scored"] += m.blue_score
                goals_data[pid]["conceded"] += m.orange_score

    eligible_goals = {pid: d for pid, d in goals_data.items() if d["matches"] >= 10}
    if eligible_goals:
        best_def = min(eligible_goals.items(), key=lambda x: x[1]["conceded"] / x[1]["matches"])
        avg_conc = round(best_def[1]["conceded"] / best_def[1]["matches"], 1)
        records.append({
            "key": "muurvast",
            "label": "Muurvast",
            "emoji": "\U0001F9F1",
            "description": "Minste goals tegen per wedstrijd (min. 10)",
            "value": name_map.get(best_def[0], "?"),
            "detail": f"{avg_conc} gem. tegen",
        })

        best_att = max(eligible_goals.items(), key=lambda x: x[1]["scored"] / x[1]["matches"])
        avg_scored = round(best_att[1]["scored"] / best_att[1]["matches"], 1)
        records.append({
            "key": "doelpuntenmachine",
            "label": "Doelpuntenmachine",
            "emoji": "\U0001F4A5",
            "description": "Meeste goals voor per wedstrijd (min. 10)",
            "value": name_map.get(best_att[0], "?"),
            "detail": f"{avg_scored} gem. voor",
        })

    # Grootste Afstraffing — biggest score difference in a single match
    if matches:
        biggest = max(matches, key=lambda m: abs(m.orange_score - m.blue_score))
        margin = abs(biggest.orange_score - biggest.blue_score)
        if margin > 0:
            winner_side = _winner(biggest)
            winner_names = [
                name_map.get(mp.player_id, "?")
                for mp in biggest.players
                if mp.side == winner_side
            ]
            records.append({
                "key": "grootste_afstraffing",
                "label": "Grootste Afstraffing",
                "emoji": "\U0001F480",
                "description": "Grootste verschil in één wedstrijd",
                "value": " & ".join(winner_names) if winner_names else "?",
                "detail": f"{biggest.orange_score}-{biggest.blue_score}",
            })

    # Hoogste Score — match with most total goals
    if matches:
        highest = max(matches, key=lambda m: m.orange_score + m.blue_score)
        total_goals = highest.orange_score + highest.blue_score
        if total_goals > 0:
            all_names = [name_map.get(mp.player_id, "?") for mp in highest.players]
            records.append({
                "key": "hoogste_score",
                "label": "Hoogste Score",
                "emoji": "\U0001F3AF",
                "description": "Meeste goals in één wedstrijd",
                "value": f"{highest.orange_score}-{highest.blue_score}",
                "detail": f"{total_goals} goals totaal",
            })

    return records


@router.get("")
def get_stats(session: Session = Depends(get_session)):
    matches = list(session.exec(select(Match)).all())
    players = list(session.exec(select(Player)).all())

    player_stats = _compute_player_stats(matches, players)
    global_stats = _compute_global_stats(matches)
    leaderboard, elo_map = _compute_elo(matches, players)
    h2h = _compute_head_to_head(matches)
    _inject_names(h2h, players)
    records = _compute_records(matches, player_stats, h2h, players)

    # Inject Elo into player stats
    for ps in player_stats:
        ps["elo"] = elo_map.get(ps["player_id"], 1000)

    return {
        "players": player_stats,
        "global": global_stats,
        "leaderboard": leaderboard,
        "head_to_head": h2h,
        "records": records,
    }
