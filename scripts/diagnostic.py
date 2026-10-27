"""Public-safe field-level audit of league transaction and live-scoring behavior.

Never serialize API replies, owner/member objects, token values, or player details.
"""
import json
from pathlib import Path
from src.espn_client import fetch
from src.weekly import scoring_period, EASTERN
from datetime import datetime


ALLOWED_SETTING_VALUES = {
    "acquisitionLimit", "matchupAcquisitionLimit", "acquisitionType",
    "waiverHours", "waiverProcessDays", "waiverProcessTime",
    "waiverOrderReset", "waiverSystem", "waiverBudget",
    "playerAddSystem", "freeAgentBudget", "matchupAcquisitionLimit",
    "matchupLimitPerScoringPeriod", "waiverProcessHour", "transactionLockingEnabled",
    "prohibitTransactionSet", "lineupLockType",
}


def scalar_config(value):
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items()
            if k in ALLOWED_SETTING_VALUES and type(v) in (int, str, bool, float)}


def side_probe(side):
    if not isinstance(side, dict):
        return {}
    entries = ((side.get("rosterForCurrentScoringPeriod") or {}).get("entries") or [])
    totals = {}
    for k in ("totalPoints", "totalProjectedPointsLive", "totalPointsLive"):
        if type(side.get(k)) in (int, float):
            totals[k] = side[k]
    if entries:
        totals["entry_count"] = len(entries)
        totals["scoring_field_presence"] = sorted(
            k for k in (entries[0].get("playerPoolEntry") or {})
            if k in {"appliedStatTotal", "appliedStats", "player", "stats",
                     "appliedStatTotalLive"})
        totals["applied_stat_total_examples"] = [
            float((e.get("playerPoolEntry") or {}).get("appliedStatTotal"))
            for e in entries[:3]
            if type((e.get("playerPoolEntry") or {}).get("appliedStatTotal")) in (int, float)
        ]
    return totals


def main():
    league = fetch(["mStatus", "mSettings", "mMatchupScore"])
    status = league.get("status") or {}
    settings = league.get("settings") or {}
    current = status.get("currentMatchupPeriod")
    today = datetime.now(EASTERN).date()
    day = scoring_period(today)
    out = {
        "date": today.isoformat(),
        "period": current,
        "scoring_period": day,
        "settings": {
            "acquisition": scalar_config(settings.get("acquisitionSettings")),
            "roster": scalar_config(settings.get("rosterSettings")),
            "general": scalar_config(settings),
            "schedule": scalar_config(settings.get("scheduleSettings")),
        },
        "acquisition_keys": sorted((settings.get("acquisitionSettings") or {}).keys()),
        "status_keys": sorted(status.keys()),
        "team_transaction_keys": [],
        "team_transaction_counts": [],
        "views": {},
    }
    team_view = fetch(["mTeam"])
    teams = team_view.get("teams") or []
    out["team_transaction_keys"] = sorted({
        k for team in teams for k in team
        if ("acquis" in k.lower() or "transact" in k.lower() or "waiv" in k.lower())
    })
    out["team_transaction_counts"] = [
        {"team_id": t.get("id"), "counter": {
            str(k): v for k, v in (t.get("transactionCounter") or {}).items()
            if type(v) in (int, float)
        }} for t in teams if t.get("id") is not None
    ]
    for title, views in (
        ("matchup", ["mMatchupScore"]),
        ("boxscore", ["mBoxscore"]),
        ("live", ["mLiveScoring"]),
        ("combined", ["mMatchupScore", "mBoxscore", "mLiveScoring"]),
    ):
        try:
            result = fetch(views, scoring_period=day, matchup_period=current)
            match = next((m for m in result.get("schedule") or []
                          if m.get("matchupPeriodId") == current), {})
            out["views"][title] = {
                "schedule_count": len(result.get("schedule") or []),
                "match_keys": sorted(match.keys()),
                "home": side_probe(match.get("home")),
                "away": side_probe(match.get("away")),
            }
        except Exception as error:
            out["views"][title] = {"error_type": type(error).__name__}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/schema-diagnostic.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
