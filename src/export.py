"""Export an allowlisted ESPN snapshot without credentials or ESPN account identities.

The output is a private GitHub Actions artifact, NOT a committed file.
"""
import json
from datetime import datetime, timezone

from src.report import actual_season_fppg, player_data, scoring_weights


def _player(entry):
    info = player_data(entry)
    owned = (entry.get("ownership")
             or (entry.get("playerPoolEntry") or {}).get("ownership")
             or info.get("ownership")
             or {})
    player_id = (info.get("id") or entry.get("playerId")
                 or (entry.get("playerPoolEntry") or {}).get("id"))
    stats = info.get("stats") or (entry.get("playerPoolEntry") or {}).get("stats") or []
    estimates = []
    for stat in stats:
        if not isinstance(stat, dict) or stat.get("seasonId") != 2027:
            continue
        # Only explicitly named numeric values, not raw API responses.
        record = {
            "scoring_period_id": stat.get("scoringPeriodId"),
            "stat_source_id": stat.get("statSourceId", stat.get("statTypeId")),
            "split_type_id": stat.get("statSplitTypeId"),
            "applied_total": stat.get("appliedTotal"),
            "applied_average": stat.get("appliedAverage"),
        }
        # Restrict raw data to known stat keys; avoid accidental user metadata.
        raw = stat.get("stats")
        if isinstance(raw, dict):
            record["stats"] = {
                str(k): v for k, v in raw.items()
                if str(k).isdigit() and isinstance(v, (int, float))
            }
        estimates.append(record)
        if len(estimates) >= 24:
            break
    return {
        "espn_player_id": player_id,
        "name": info.get("fullName"),
        "pro_team_id": info.get("proTeamId"),
        "eligible_slots": info.get("eligibleSlots") or [],
        "injury_status": info.get("injuryStatus"),
        "actual_season_fppg": actual_season_fppg(entry),
        "rostered_percent": owned.get("percentOwned"),
        "season_stats": estimates,
    }


def sanitized_snapshot(data):
    settings = data["settings"]
    weights = scoring_weights(settings)
    roster_settings = settings.get("rosterSettings") or {}
    acquisition = settings.get("acquisitionSettings") or {}
    teams = []
    for team in data["teams"]:
        roster = []
        for entry in (team.get("roster") or {}).get("entries") or []:
            roster.append({
                "lineup_slot_id": entry.get("lineupSlotId"),
                "player": _player(entry),
            })
        teams.append({
            "team_id": team.get("id"),
            "team_name": (team.get("name") or
                          (str(team.get("location") or "") + " " +
                           str(team.get("nickname") or "")).strip()),
            "roster": roster,
        })
    return {
        "schema_version": 1,
        "synced_at_utc": datetime.now(timezone.utc).isoformat(),
        "league": {
            "id": 394231780,
            "season": 2027,
            "name": settings.get("name"),
            "team_count": settings.get("size"),
            "scoring_weights_by_stat_id": {str(k): v for k, v in weights.items()},
            "roster_settings": {
                "lineup_slot_counts": roster_settings.get("lineupSlotCounts"),
                "position_limits": roster_settings.get("positionLimits"),
            },
            "acquisition_rules": {
                "acquisition_limit": acquisition.get("acquisitionLimit"),
                "acquisition_type": acquisition.get("acquisitionType"),
                "waiver_hours": acquisition.get("waiverHours"),
            },
        },
        "teams": teams,
        "available_players": [_player(entry) for entry in data["free_agents"]],
        "notes": [
            "Credentials, cookies, account emails, and team owner identities are excluded.",
            "ESPN's stat source and period IDs are preserved; applied points are not independent projections.",
            "Available pool is limited to the top 50 returned by ESPN in this version.",
        ],
    }


def serialize_snapshot(data):
    return json.dumps(sanitized_snapshot(data), indent=2, sort_keys=True,
                      ensure_ascii=False, allow_nan=False) + "\n"
