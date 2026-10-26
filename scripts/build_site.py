"""Build the public-safe read-only dashboard data from private ESPN league API."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.espn_client import EspnError, fetch, fetch_snapshot
from src.report import projected_season_fppg
from src.weekly import (EASTERN, INACTIVE_STATUSES, current_week, entries_for_day,
                        evaluate_add_drops, lineup_alert, nba_day, normalize_entry,
                        point_value, scoring_period)

MY_TEAM_ID = 4
HISTORY_DAYS = 21


def _normalize_matchups(schedule, period):
    result = []
    for item in schedule:
        if item.get("matchupPeriodId") != period:
            continue
        home = item.get("home") or {}
        away = item.get("away") or {}
        if home.get("teamId") is None:
            continue
        result.append({
            "id": item.get("id"),
            "home_team_id": home["teamId"],
            "away_team_id": away.get("teamId"),
            "home_actual": float(home.get("totalPoints") or 0),
            "away_actual": float(away.get("totalPoints") or 0),
            "bye": away.get("teamId") is None,
        })
    return result


def _daily_actual(entry, period):
    pool = entry.get("playerPoolEntry") or {}
    player = pool.get("player") or entry.get("player") or {}
    candidates = [
        s for s in player.get("stats") or []
        if s.get("seasonId") == 2027
        and s.get("scoringPeriodId") == period
        and s.get("statSourceId") == 0
        and isinstance(s.get("appliedTotal"), (int, float))
    ]
    if not candidates:
        return None
    # ESPN's split_type 5 = the game-specific daily record, if available.
    chosen = next((s for s in candidates if s.get("statSplitTypeId") == 5), candidates[0])
    return float(chosen["appliedTotal"])


def _history(league_start, today, metadata):
    """Re-query recent scoring periods; don't backfill projections with today's values."""
    first = max(1, scoring_period(today) - HISTORY_DAYS)
    last = scoring_period(today) - 1
    history = {}
    if last < first:
        return history
    for period_id in range(first, last + 1):
        day = league_start + timedelta(days=period_id - 1)
        matchup_period = 1 + ((day - (league_start - timedelta(days=1))).days // 7)
        # Season begins on a Tuesday; matchup periods after week 1 begin Monday.
        if matchup_period < 1:
            continue
        try:
            response = fetch(["mBoxscore"], scoring_period=period_id,
                             matchup_period=matchup_period)
        except EspnError:
            continue
        for match in response.get("schedule") or []:
            if match.get("matchupPeriodId") != matchup_period:
                continue
            for side_name in ("home", "away"):
                side = match.get(side_name) or {}
                entries = ((side.get("rosterForCurrentScoringPeriod") or {})
                           .get("entries") or [])
                for entry in entries:
                    info = ((entry.get("playerPoolEntry") or {}).get("player") or {})
                    pid = info.get("id") or entry.get("playerId")
                    if pid is None:
                        continue
                    applied = _daily_actual(entry, period_id)
                    if applied is None:
                        continue
                    item = history.setdefault(str(pid), {})
                    item[day.isoformat()] = applied
    return {key: [{"date": date_key, "actual": val}
                  for date_key, val in sorted(value.items())]
            for key, value in history.items()}


def build_data(today=None, *, nba_fetch=nba_day, espn_fetch=fetch, snapshot_fetch=fetch_snapshot):
    today = today or datetime.now(EASTERN).date()
    week = current_week(today)
    league = espn_fetch(["mStatus", "mMatchupScore", "mSettings"])
    status = league.get("status") or {}
    period = status.get("currentMatchupPeriod")
    if not isinstance(period, int):
        raise ValueError("Could not determine current matchup period from ESPN.")
    if not (week[0] <= today <= week[-1]):
        raise ValueError("Invalid current matchup week.")
    schedule = _normalize_matchups(league.get("schedule") or [], period)
    if not schedule:
        raise ValueError("ESPN returned no matchups for the active period.")

    snapshot = snapshot_fetch()
    teams = {str(t["id"]): {
        "id": t["id"], "name": (t.get("name") or
                               (str(t.get("location") or "") + " " +
                                str(t.get("nickname") or "")).strip()),
    } for t in snapshot["teams"]}
    if len(teams) != 7:
        raise ValueError("League team count doesn't match expected seven.")

    metadata = {}
    for team in snapshot["teams"]:
        for e in (team.get("roster") or {}).get("entries") or []:
            item = normalize_entry(e)
            if item["id"] is not None:
                metadata[item["id"]] = item

    nba_schedule = {}
    daily = {}
    for day in week:
        key = day.isoformat()
        nba_schedule[key] = nba_fetch(day)
        # Earlier days are already included in matchup actual points; we only
        # need their rosters for history collection.
        if day < today:
            continue
        response = espn_fetch(["mBoxscore"], scoring_period=scoring_period(day),
                              matchup_period=period)
        rosters = entries_for_day(response)
        if set(rosters) != set(teams):
            raise ValueError("Incomplete daily ESPN rosters for " + key
                             + "; refusing to publish fabricated lineups.")
        for roster in rosters.values():
            for p in roster:
                info = metadata.get(p["id"], {})
                for field in ("name", "eligible_slots", "pro_team_id",
                              "projected_fppg", "injury_status"):
                    if p.get(field) in (None, [], "Unknown player"):
                        p[field] = info.get(field)
        daily[key] = rosters

    week_team = {}
    for tid in teams:
        daily_by_team = {d: value[tid] for d, value in daily.items()}
        alerts = []
        baseline = 0
        ideal = 0
        for day, entries in daily_by_team.items():
            issue = lineup_alert(entries, nba_schedule[day])
            baseline += issue["current_projected_remaining"]
            ideal += issue["best_projected_remaining"]
            if issue["potential_gain"] >= 0.5:
                alerts.append({"date": day, **issue})
        week_team[tid] = {
            "remaining_expected": round(baseline, 1),
            "remaining_optimized": round(ideal, 1),
            "alerts": alerts,
        }

    output_matchups = []
    for pair in schedule:
        home = str(pair["home_team_id"])
        away = str(pair["away_team_id"]) if pair["away_team_id"] is not None else None
        home_projected = round(pair["home_actual"] + week_team[home]["remaining_expected"], 1)
        away_projected = (round(pair["away_actual"] + week_team[away]["remaining_expected"], 1)
                          if away is not None else None)
        output_matchups.append({
            **pair, "home_projected": home_projected, "away_projected": away_projected,
            "home_optimized_projected": round(
                pair["home_actual"] + week_team[home]["remaining_optimized"], 1),
            "away_optimized_projected": round(
                pair["away_actual"] + week_team[away]["remaining_optimized"], 1)
            if away is not None else None,
        })

    free_agents = [normalize_entry(a) for a in snapshot["free_agents"]]
    next_days = {d: daily[d][str(MY_TEAM_ID)] for d in daily}
    opportunities = evaluate_add_drops(next_days, nba_schedule, free_agents, today)
    player_info = {}
    for p in free_agents:
        if p["id"] is not None:
            player_info[str(p["id"])] = {k: v for k, v in p.items() if k != "lineup_slot_id"}
    for player in metadata.values():
        player_info[str(player["id"])] = {k: v for k, v in player.items() if k != "lineup_slot_id"}

    # Include current-week ESPN histories where ESPN explicitly returns daily actuals.
    history = _history(__import__("src.weekly", fromlist=["SEASON_DAY_ONE"]).SEASON_DAY_ONE,
                       today, player_info)
    return {
        "schema_version": 2,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "snapshot_date_eastern": today.isoformat(),
        "week_start": week[0].isoformat(),
        "week_end": week[-1].isoformat(),
        "matchup_period": period,
        "my_team_id": MY_TEAM_ID,
        "teams": list(teams.values()),
        "matchups": output_matchups,
        "team_analysis": week_team,
        "daily_lineups": daily,
        "players": player_info,
        "history": history,
        "opportunities": opportunities,
        "limits": {
            "data_is_public_safe": True,
            "waivers_not_modeled": True,
            "streaming_requires_manual_review": True,
            "season_projection_baseline": "ESPN full-season projected FP/G",
            "historical_expected_baseline": "Current projection; not historical as-of-game",
            "today_in_progress_games": "Live games excluded from remaining projections",
            "free_agents_checked": len(free_agents),
        },
    }


def main():
    payload = build_data()
    out = Path("site/data.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print("Dashboard built for week " + payload["week_start"] + " to " + payload["week_end"]
          + ": " + str(len(payload["matchups"])) + " matchups; "
          + str(len(payload["history"])) + " players with game history.")


if __name__ == "__main__":
    main()
