"""One-time schema validation for current matchup and daily lineups.
Never writes ESPN's raw response or cookies to artifact.
"""
import json
from pathlib import Path
from src.espn_client import fetch


def keys(value):
    return sorted(value.keys()) if isinstance(value, dict) else []


def main():
    league = fetch(["mStatus", "mSettings", "mMatchupScore"])
    status = league.get("status") or {}
    settings = league.get("settings") or {}
    sched_settings = settings.get("scheduleSettings") or {}
    matchups = league.get("schedule") or []
    period = status.get("currentMatchupPeriod")
    scoring = status.get("currentScoringPeriod")
    date_map = sched_settings.get("matchupPeriods") or {}
    if not isinstance(period, int):
        raise ValueError("No current ESPN matchup period; do not guess.")
    # Probe a known scoring period from the prior private league snapshot if status omits the field.
    if not isinstance(scoring, int):
        scoring = 6
    limited = {
        "status_fields": keys(status),
        "status_scalar_fields": {k: v for k, v in status.items() if isinstance(v, (str, int, float, bool))},
        "current_period": period,
        "current_scoring": scoring,
        "schedule_settings_fields": keys(sched_settings),
        "matchup_periods_current": date_map.get(str(period)),
        "matchup_periods_sample": {str(k): v for k, v in list(date_map.items())[:3]},
        "matchup_samples": [
            {"period": m.get("matchupPeriodId"), "id": m.get("id"),
             "home": (m.get("home") or {}).get("teamId"),
             "away": (m.get("away") or {}).get("teamId")}
            for m in matchups if m.get("matchupPeriodId") == period
        ][:7],
        "daily": [],
    }
    selected = [scoring, scoring + 1]
    for day in selected:
        try:
            result = fetch(["mBoxscore", "mMatchupScore"], scoring_period=day, matchup_period=period)
            matches = [m for m in result.get("schedule", [])
                       if m.get("matchupPeriodId") == period]
            match = matches[0] if matches else {}
            sides = {}
            for side in ["home", "away"]:
                team = match.get(side) or {}
                entries = (team.get("rosterForCurrentScoringPeriod") or {}).get("entries") or []
                sample = entries[0] if entries else {}
                pool = sample.get("playerPoolEntry") or {}
                sides[side] = {
                    "side_fields": keys(team),
                    "roster_fields": keys(team.get("rosterForCurrentScoringPeriod")),
                    "entry_count": len(entries),
                    "slot_distribution": {
                        str(slot): sum(x.get("lineupSlotId") == slot for x in entries)
                        for slot in set(x.get("lineupSlotId") for x in entries)
                    },
                    "example_entry_fields": keys(sample),
                    "example_pool_fields": keys(pool),
                    "example_stat_labels": [
                        {"season": s.get("seasonId"), "period": s.get("scoringPeriodId"),
                         "source": s.get("statSourceId"), "split": s.get("statSplitTypeId"),
                         "applied_total": s.get("appliedTotal"),
                         "applied_average": s.get("appliedAverage")}
                        for s in (pool.get("player") or {}).get("stats", [])[:8]
                    ],
                }
            limited["daily"].append({"day": day, "matchup_count": len(matches),
                                     "sample_matchup_fields": keys(match), "sides": sides})
        except Exception as error:
            limited["daily"].append({"day": day, "error_class": type(error).__name__})
    # Probe player cards for verified game-by-game fantasy scoring history.
    try:
        cards = fetch(["kona_playercard"], player_filter={
            "players": {
                "filterIds": {"value": [3112335, 4431678]},
                "filterStatsForTopScoringPeriodIds": {
                    "value": 35, "additionalValue": ["002027", "102027"]
                },
            }
        })
        rows = cards.get("players") or []
        limited["player_card_probe"] = {
            "player_count": len(rows),
            "outer_keys": keys(rows[0]) if rows else [],
            "stat_records": [{
                "source": v.get("statSourceId"),
                "split": v.get("statSplitTypeId"),
                "period": v.get("scoringPeriodId"),
                "season": v.get("seasonId"),
                "applied_total": v.get("appliedTotal")
            } for v in (((rows[0].get("player") or {}).get("stats") or [])[:45])]
            if rows else [],
        }
    except Exception as error:
        limited["player_card_probe"] = {"error_class": type(error).__name__}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/schema-diagnostic.json").write_text(json.dumps(limited, indent=2))


if __name__ == "__main__":
    main()
