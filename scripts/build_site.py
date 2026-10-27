"""Build the public-safe read-only dashboard data from private ESPN league API."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.espn_client import EspnError, fetch, fetch_snapshot
from src.report import projected_season_fppg
from src.weekly import (EASTERN, SEASON_DAY_ONE, current_week, entries_for_day,
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


def _history(league_start, today, espn_fetch, player_metadata=None):
    """Historical game-level actuals from ESPN's day-scoped team roster feed.

    Query each historical scoring day, keeping ONLY stat-source 0 / split 5
    for that exact day. Missing records stay missing (not zero).
    """
    first = max(1, scoring_period(today) - HISTORY_DAYS)
    last = scoring_period(today) - 1
    history = {}
    for period_id in range(first, last + 1):
        day = league_start + timedelta(days=period_id - 1)
        # The 2026 season began Tuesday October 20. Week 1 was six days;
        # subsequent fantasy weeks follow Monday through Sunday.
        try:
            response = espn_fetch(["mRoster"], scoring_period=period_id)
        except EspnError:
            continue
        for team in response.get("teams") or []:
            for entry in (team.get("roster") or {}).get("entries") or []:
                pool = entry.get("playerPoolEntry") or {}
                player = pool.get("player") or {}
                pid = player.get("id") or entry.get("playerId")
                if pid is None:
                    continue
                game_records = [
                    s for s in (player.get("stats") or pool.get("stats") or [])
                    if s.get("seasonId") == 2027
                    and s.get("scoringPeriodId") == period_id
                    and s.get("statSourceId") == 0
                    and s.get("statSplitTypeId") == 5
                    and isinstance(s.get("appliedTotal"), (int, float))
                ]
                if not game_records:
                    continue
                record = game_records[0]
                box_stats = record.get("stats") or {}
                minutes = box_stats.get("40", box_stats.get(40))
                if record["appliedTotal"] == 0 and not (isinstance(minutes, (int, float)) and minutes > 0):
                    # ESPN emits zero-point daily records even for DNPs.
                    # Exclude them from per-game averages and trend charts.
                    continue
                # Keep the game only once per player/day, even across multiple rosters.
                history.setdefault(str(pid), {})[day.isoformat()] = float(record["appliedTotal"])
    # ESPN's historical mRoster covers only rostered players. Player cards
    # extend trend coverage to free agents, including past team transactions.
    if player_metadata:
        ids = sorted(int(pid) for pid in player_metadata if str(pid).isdigit())
        for offset in range(0, len(ids), 20):
            batch = ids[offset:offset + 20]
            try:
                response = espn_fetch(["kona_playercard"], player_filter={
                    "players": {
                        "filterIds": {"value": batch},
                        "filterStatsForTopScoringPeriodIds": {
                            "value": 75,
                            "additionalValue": ["002027", "102027"],
                        },
                    }
                })
            except EspnError:
                # Core forecasts can continue if the optional history view
                # fails. Historical trend coverage will be incomplete.
                continue
            for entry in response.get("players") or []:
                player = entry.get("player") or {}
                pid = player.get("id") or entry.get("id")
                if pid is None:
                    continue
                for s in player.get("stats") or []:
                    day = s.get("scoringPeriodId")
                    total = s.get("appliedTotal")
                    if not (s.get("seasonId") == 2027
                            and s.get("statSourceId") == 0
                            and s.get("statSplitTypeId") == 5
                            and isinstance(day, int) and 1 <= day < scoring_period(today)
                            and isinstance(total, (int, float))):
                        continue
                    raw = s.get("stats") or {}
                    # DNP zero records lack a valid appearance count.
                    if not isinstance(raw, dict) or not (
                        float(raw.get("42") or 0) > 0
                        or float(raw.get("41") or 0) > 0
                    ):
                        continue
                    when = (league_start + timedelta(days=day - 1)).isoformat()
                    history.setdefault(str(pid), {})[when] = float(total)
    return {
        pid: [{"date": when, "actual": actual}
              for when, actual in sorted(record.items())]
        for pid, record in history.items()
    }


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
        rosters = entries_for_day(response, period)
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
    history = _history(SEASON_DAY_ONE, today, espn_fetch, player_info)
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
        "nba_schedule": {d: {str(k): v for k, v in team_games.items()}
                         for d, team_games in nba_schedule.items()},
        "players": player_info,
        "history": history,
        "opportunities": opportunities,
        "limits": {
            "data_is_public_safe": True,
            "waivers_not_modeled": True,
            "streaming_requires_manual_review": True,
            "season_projection_baseline": "ESPN full-season projected FP/G",
            "historical_expected_baseline": "Current ESPN projection only; historical as-of snapshots not collected yet",
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
