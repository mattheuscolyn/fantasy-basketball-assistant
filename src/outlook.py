"""Three-week matchup context and future schedule outlook."""
from datetime import timedelta
from src.weekly import best_lineup, current_week, point_value


def matchups_for_period(response, period):
    games = []
    for match in response.get("schedule") or []:
        if match.get("matchupPeriodId") != period:
            continue
        home = (match.get("home") or {}).get("teamId")
        away = (match.get("away") or {}).get("teamId")
        if not isinstance(home, int):
            continue
        games.append({"home_team_id": home, "away_team_id": away})
    return games


def forecast_future_week(start, teams, nba_by_day):
    """Use today's actual roster, optimize each future day by eligible slots.

    Does not assume saved future lineups, future roster moves or injury returns.
    """
    forecast = {}
    for tid, entries in teams.items():
        total = 0.0
        starts = 0
        schedule_games = 0
        for delta in range(7):
            day = (start + timedelta(days=delta)).isoformat()
            games = nba_by_day[day]
            score, assignments = best_lineup(entries, games)
            total += score
            starts += len(assignments)
            schedule_games += sum(1 for p in entries
                                  if point_value(p, games) > 0 and
                                  p.get("lineup_slot_id") != 13)
        forecast[str(tid)] = {
            "projected_points": round(total, 1),
            "usable_starts": starts,
            "potential_player_games": schedule_games,
            "points_per_start": round(total / starts, 1) if starts else None,
        }
    return forecast


def generate_outlook(current_week_start, matchup_period, current, week_futures,
                     team_entries, nba_by_day):
    """Return rankings, matchup context, future opponent and schedule effects."""
    team_ids = {str(t) for t in team_entries}
    weeks = [{
        "week_start": current_week_start.isoformat(),
        "matchup_period": matchup_period,
        "label": "This week",
        "teams": {},
        "matchups": [{
            "home_team_id": m["home_team_id"],
            "away_team_id": m["away_team_id"]
        } for m in current],
        "forecast_type": "saved ESPN lineup + credited matchup score",
    }]
    for m in current:
        for label in ("home", "away"):
            tid = m.get(label + "_team_id")
            if tid is None:
                continue
            weeks[0]["teams"][str(tid)] = {
                "projected_points": m.get(label + "_projected"),
                "projection_incomplete": m.get("projection_incomplete", False),
            }
    for ahead, period, pairings in week_futures:
        start = current_week_start + timedelta(days=7 * ahead)
        week_data = forecast_future_week(start, team_entries, nba_by_day)
        if not pairings:
            raise ValueError("ESPN did not confirm future matchup pairings.")
        listed = {str(x) for m in pairings for x in (m["home_team_id"], m["away_team_id"])
                  if x is not None}
        if listed != team_ids:
            raise ValueError("Future ESPN matchups omit or duplicate teams.")
        weeks.append({
            "week_start": start.isoformat(), "matchup_period": period,
            "label": "Next week" if ahead == 1 else "In two weeks",
            "teams": week_data, "matchups": pairings,
            "forecast_type": "optimized existing roster; no predicted acquisitions",
        })
    for week in weeks:
        ranked = sorted(((float(v["projected_points"]), k)
                         for k, v in week["teams"].items()
                         if isinstance(v.get("projected_points"), (float, int))),
                        reverse=True)
        for n, (_, tid) in enumerate(ranked, 1):
            week["teams"][tid]["league_rank"] = n
        week["ranked_count"] = len(ranked)
    # Compare future schedules only against that team's own 2-week baseline.
    # This is a schedule-strength indicator, not a claim of good/bad luck.
    for tid in team_ids:
        projected = [week["teams"][tid].get("projected_points") for week in weeks[1:]]
        future_mean = sum(projected) / len(projected)
        for week in weeks[1:]:
            week["teams"][tid]["relative_to_own_future_average"] = round(
                week["teams"][tid]["projected_points"] - future_mean, 1)
    return weeks


def matchup_for_team(week, team_id):
    tid = int(team_id)
    for m in week["matchups"]:
        if m["home_team_id"] == tid:
            return m["away_team_id"]
        if m["away_team_id"] == tid:
            return m["home_team_id"]
    return None


def evaluate_season_signal(weeks, team_id, observed=None):
    """Qualitative diagnosis; never infer luck from a single projected total."""
    this = weeks[0]
    own = this["teams"].get(str(team_id), {})
    opp_id = matchup_for_team(this, team_id)
    opponent = this["teams"].get(str(opp_id), {}) if opp_id else {}
    own_total = own.get("projected_points")
    opp_total = opponent.get("projected_points")
    enough = isinstance(own_total, (int, float)) and isinstance(opp_total, (int, float))
    margin = round(own_total - opp_total, 1) if enough else None
    own_future = [w["teams"][str(team_id)]["projected_points"] for w in weeks[1:]]
    near_average = round(sum(own_future) / len(own_future), 1)
    next_week = weeks[1]
    next_opp = matchup_for_team(next_week, team_id)
    next_margin = (round(next_week["teams"][str(team_id)]["projected_points"] -
                         next_week["teams"][str(next_opp)]["projected_points"], 1)
                   if next_opp is not None else None)
    # No calibrated win probability or arbitrary luck score.
    # A large deficit cannot by itself justify a costly irreversible drop.
    if not enough:
        decision = "Review data"
        reason = "The current matchup projection is incomplete."
    elif margin >= 0:
        decision = "Protect the lead"
        reason = "You are projected ahead; focus on free lineup fixes."
    elif margin < -100 and (next_margin is None or next_margin > margin):
        decision = "Preserve the roster"
        reason = "A large projected deficit makes risky short-term drops unattractive."
    else:
        decision = "Consider safe streaming"
        reason = "Look for extra usable games without dropping players you value long-term."
    matched = (observed or {}).get("matched_games", 0)
    performance = {
        "matched_games": matched,
        "status": "Not enough evidence" if matched < 5 else "Historical comparison available",
        "actual_vs_pregame": (observed or {}).get("actual_minus_expected")
            if matched >= 5 else None,
    }
    return {
        "recommendation": decision, "reason": reason,
        "current_margin": margin,
        "next_week_margin": next_margin,
        "team_future_weekly_average": near_average,
        "opponent_id": opp_id, "next_opponent_id": next_opp,
        "observed_performance": performance,
        "caveats": ["Future weeks use current rosters, ESPN season projections and optimized eligibility.",
                    "NBA schedules, injuries and opponent rosters may change.",
                    "A projected difficult matchup does not prove player performance luck."],
    }
