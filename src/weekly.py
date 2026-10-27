"""Week-specific NBA schedule, lineup assignment and fantasy value calculations.

No transaction APIs; comparisons are advisory.
"""
from datetime import date, datetime, timedelta
from functools import lru_cache
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo
import json

from src.report import player_data, projected_season_fppg

SEASON_DAY_ONE = date(2026, 10, 20)
EASTERN = ZoneInfo("America/New_York")
ACTIVE_SLOTS = (0, 1, 2, 3, 4, 5, 6, 11, 11, 11)
BENCH = 12
INJURED_RESERVE = 13
INACTIVE_STATUSES = {"OUT", "SUSPENSION", "INJURY_RESERVE", "INJURED_RESERVE"}
SLOT_NAMES = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C",
              5: "G", 6: "F", 11: "UTIL", 12: "Bench", 13: "IR"}


def scoring_period(day):
    return (day - SEASON_DAY_ONE).days + 1


def current_week(today):
    start = today - timedelta(days=today.weekday())
    return [start + timedelta(days=i) for i in range(7)]


def nba_day(day):
    """NBA game states keyed by ESPN professional team ID. Fail closed on bad data."""
    url = ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
           "?dates=" + day.strftime("%Y%m%d") + "&limit=100")
    request = Request(url, headers={"User-Agent": "fantasy-basketball-assistant/0.1",
                                     "Accept": "application/json"})
    try:
        with urlopen(request, timeout=25) as res:
            data = json.loads(res.read(3_000_000))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ValueError("NBA schedule unavailable for " + day.isoformat()) from None
    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("NBA schedule returned no events list.")
    scheduled = {}
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        comp = competitions[0]
        if not isinstance(comp, dict):
            continue
        game_id = str(event.get("id"))
        if game_id in seen:
            continue
        seen.add(game_id)
        game_date = event.get("date")
        if not isinstance(game_date, str):
            continue
        when = datetime.fromisoformat(game_date.replace("Z", "+00:00")).astimezone(EASTERN).date()
        if when != day:
            continue
        state = ((event.get("status") or {}).get("type") or {}).get("state")
        if state not in ("pre", "in", "post"):
            raise ValueError("Unknown NBA game state for " + day.isoformat())
        for side in comp.get("competitors") or []:
            team_id = (side.get("team") or {}).get("id")
            if team_id is None or not str(team_id).isdigit():
                raise ValueError("Unrecognized NBA team ID in schedule.")
            tid = int(team_id)
            scheduled.setdefault(tid, []).append(state)
    return scheduled


def normalize_entry(entry):
    p = player_data(entry)
    return {
        "id": p.get("id") or entry.get("playerId"),
        "name": p.get("fullName") or "Unknown player",
        "pro_team_id": p.get("proTeamId"),
        "lineup_slot_id": entry.get("lineupSlotId"),
        "eligible_slots": p.get("eligibleSlots") or [],
        "injury_status": p.get("injuryStatus"),
        "projected_fppg": projected_season_fppg(entry),
    }


def entries_for_day(league_response, matchup_period):
    """Use ESPN's daily roster, never extrapolate one current roster to all days."""
    result = {}
    for matchup in league_response.get("schedule") or []:
        if matchup.get("matchupPeriodId") != matchup_period:
            continue
        for label in ("home", "away"):
            side = matchup.get(label)
            if not isinstance(side, dict) or not isinstance(side.get("teamId"), int):
                continue
            roster = side.get("rosterForCurrentScoringPeriod") or {}
            entries = roster.get("entries")
            if isinstance(entries, list):
                result[str(side["teamId"])] = [normalize_entry(e) for e in entries]
    return result


def game_state(player, games):
    return games.get(player.get("pro_team_id")) or games.get(str(player.get("pro_team_id"))) or []


def point_value(player, games):
    """Only project yet-unstarted, non-injured NBA player-games."""
    if player.get("injury_status") in INACTIVE_STATUSES:
        return 0.0
    value = player.get("projected_fppg")
    if not isinstance(value, (int, float)):
        return 0.0
    return float(value) * game_state(player, games).count("pre")


def current_lineup_score(entries, games):
    return round(sum(point_value(p, games) for p in entries
                     if p.get("lineup_slot_id") in ACTIVE_SLOTS), 2)


def best_lineup(entries, games, *, exclude_ids=()):
    """Maximum projected value, honoring individual eligibility and distinct active slots.

    DP uses 10-bit mask (ten slots) and processes at most 15 eligible players.
    Slots with the same role are retained individually for capacity constraints.
    """
    forbidden = set(exclude_ids)
    locked_slots = []
    eligible = []
    for p in entries:
        if p.get("id") in forbidden or p.get("lineup_slot_id") == INJURED_RESERVE:
            continue
        state = game_state(p, games)
        # An active player whose NBA game started has an immovable lineup
        # slot. Never reuse it for a theoretical bench-to-starter swap.
        if p.get("lineup_slot_id") in ACTIVE_SLOTS and (
                "in" in state or "post" in state):
            locked_slots.append(p["lineup_slot_id"])
        else:
            eligible.append(p)
    if len(eligible) > 18:
        raise ValueError("Unexpectedly large ESPN roster; cannot safely optimize.")
    @lru_cache(None)
    def solve(i, mask):
        if i == len(eligible):
            return (0.0, ())
        best = solve(i + 1, mask)
        p = eligible[i]
        gain = point_value(p, games)
        if gain <= 0:
            return best
        for j, slot in enumerate(ACTIVE_SLOTS):
            if not ((mask >> j) & 1) and slot in p.get("eligible_slots", []):
                remaining, picks = solve(i + 1, mask | (1 << j))
                candidate = (gain + remaining, ((p["id"], slot),) + picks)
                if candidate[0] > best[0] + 0.001:
                    best = candidate
        return best
    used = 0
    for locked_slot in locked_slots:
        for j, slot in enumerate(ACTIVE_SLOTS):
            if slot == locked_slot and not (used >> j) & 1:
                used |= 1 << j
                break
        else:
            raise ValueError("More locked players than available lineup slots.")
    value, assignment = solve(0, used)
    return round(value, 2), [{"player_id": pid, "slot_id": slot}
                              for pid, slot in assignment]


def lineup_alert(entries, games):
    baseline = current_lineup_score(entries, games)
    optimized, picks = best_lineup(entries, games)
    baseline_active = {p["id"] for p in entries
                       if p.get("lineup_slot_id") in ACTIVE_SLOTS
                       and point_value(p, games) > 0}
    optimized_active = {p["player_id"] for p in picks}
    names = {p["id"]: p["name"] for p in entries}
    return {
        "current_projected_remaining": baseline,
        "best_projected_remaining": optimized,
        "potential_gain": round(max(0, optimized - baseline), 2),
        "bench_to_start": [names[x] for x in optimized_active - baseline_active if x in names],
        "start_to_bench": [names[x] for x in baseline_active - optimized_active if x in names],
    }


def evaluate_add_drops(daily_lineups, nba_schedule, available, today):
    """Single-acquisition what-if, with a conservative droppable-player filter.

    Does not account for waivers, acquired-player timing or future NBA injuries.
    It is an opportunity list only; no orders are placed.
    """
    days = [d for d in sorted(daily_lineups) if date.fromisoformat(d) > today]
    if not days:
        return []
    current = daily_lineups[days[0]]
    ranked = sorted((p for p in current if isinstance(p.get("projected_fppg"), (int, float))
                     and p.get("lineup_slot_id") != INJURED_RESERVE),
                    key=lambda p: p["projected_fppg"])
    candidates_drop = ranked[:4]
    before = sum(best_lineup(daily_lineups[d], nba_schedule[d])[0] for d in days)
    suggestions = []
    for drop in candidates_drop:
        for addition in available:
            if addition.get("injury_status") in INACTIVE_STATUSES:
                continue
            if not isinstance(addition.get("projected_fppg"), (int, float)):
                continue
            new_player = dict(addition, lineup_slot_id=BENCH)
            after = 0
            for day in days:
                entries = [p for p in daily_lineups[day] if p["id"] != drop["id"]]
                after += best_lineup(entries + [new_player], nba_schedule[day])[0]
            gain = round(after - before, 1)
            if gain >= 5:
                suggestions.append({
                    "drop": drop["name"], "add": addition["name"],
                    "projected_gain": gain, "risk": "Dropped player may be permanently lost",
                    "note": "Assumes immediate acquisition and no waiver delay; confirmation required.",
                })
    return sorted(suggestions, key=lambda x: x["projected_gain"], reverse=True)[:12]
