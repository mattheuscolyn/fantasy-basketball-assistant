"""One-time allowlisted API shape inspection. No credentials or member identities in output."""
import json
from pathlib import Path
from src.espn_client import fetch

def side_shape(side):
    roster=side.get("rosterForCurrentScoringPeriod") or {}
    entries=roster.get("entries") or []
    first=entries[0] if entries else {}
    player=first.get("playerPoolEntry") or {}
    return {
        "keys": list(side.keys()),
        "team_id": side.get("teamId"),
        "total_points":side.get("totalPoints"),
        "projected_live":side.get("totalProjectedPointsLive"),
        "entry_count":len(entries),
        "entry_keys": list(first.keys()),
        "entry_sample":{"player_id":first.get("playerId"),"lineup_slot":first.get("lineupSlotId"),
                        "pool_keys":list(player.keys()),"applied_stat_total":player.get("appliedStatTotal")},
    }

def main():
    basics=fetch(["mStatus","mSettings","mMatchupScore"])
    status=basics.get("status") or {}
    settings=basics.get("settings") or {}
    season=settings.get("scheduleSettings") or {}
    matchups=basics.get("schedule") or []
    current=status.get("currentMatchupPeriod") or 2
    scoring=status.get("currentScoringPeriod") or 6
    if isinstance(scoring,dict): scoring=scoring.get("id")
    if isinstance(current,dict): current=current.get("id")
    if not isinstance(current,int):current=2
    if not isinstance(scoring,int):scoring=6
    box=fetch(["mBoxscore"],scoring_period=scoring,matchup_period=current)
    pro=fetch(["proTeamSchedules_wl"])
    pro_sched=pro.get("proTeamSchedules")
    if isinstance(pro_sched,dict):
        pro_shapes={str(k): {"kind":type(v).__name__, "keys":list(v.keys())[:15] if isinstance(v,dict) else [],
                             "sample":str(v)[:250] } for k,v in list(pro_sched.items())[:2]}
    elif isinstance(pro_sched,list):
        pro_shapes={"items":[{"keys":list(v.keys()) if isinstance(v,dict) else [],
                              "sample":str(v)[:250]}for v in pro_sched[:3]]}
    else:
        pro_shapes={"kind":type(pro_sched).__name__}

    day=fetch(["mRoster"],scoring_period=scoring)
    old=fetch(["mRoster"],scoring_period=6)
    def roster_stat_probe(record):
        teams=record.get("teams") or []
        out=[]
        for t in teams[:1]:
            for e in ((t.get("roster") or {}).get("entries") or [])[:3]:
                player=(e.get("playerPoolEntry") or {}).get("player") or {}
                stats=player.get("stats") or (e.get("playerPoolEntry") or {}).get("stats") or []
                out.append({"player_id":player.get("id"),
                            "stat_probes":[{"period":s.get("scoringPeriodId"),
                                            "split":s.get("statSplitTypeId"),
                                            "source":s.get("statSourceId"),
                                            "points":s.get("appliedTotal")}for s in stats[:12]]})
        return out

    samples=box.get("schedule") or []
    out={
       "pro_schedule_keys":list(pro.keys()),
       "pro_schedule_shape":pro_shapes,
       "status_keys":list(status.keys()),
       "status_safe":{k:v for k,v in status.items() if k in (
           "currentMatchupPeriod","currentScoringPeriod","latestScoringPeriod",
           "firstScoringPeriod","finalScoringPeriod")},
       "settings_schedule_keys":list(season.keys()),
       "matchup_periods":season.get("matchupPeriods"),
       "matchup_period_count":len(season.get("matchupPeriods") or {}),
       "scoring_periods_by_matchup":season.get("matchupPeriods"),
       "matchup_sample":[{"id":m.get("id"),"period":m.get("matchupPeriodId"),
                          "home":side_shape(m.get("home") or {}),"away":side_shape(m.get("away") or {})}
                         for m in matchups if m.get("matchupPeriodId")==current][:4],
       "box_keys":list(box.keys()),
       "box_schedule_length":len(samples),
       "box_sample":[{"id":m.get("id"),"period":m.get("matchupPeriodId"),
                      "home":side_shape(m.get("home") or {}),"away":side_shape(m.get("away") or {})}
                     for m in samples[:4]],
       "day_team_count":len(day.get("teams") or []),
       "daily_stat_probe":roster_stat_probe(old),
       "day_sample":[{"id":t.get("id"),"entries":[{"id":e.get("playerId"),
                "slot":e.get("lineupSlotId")}for e in (t.get("roster")or{}).get("entries",[])][:20]}
                    for t in (day.get("teams")or[])[:2]],
       "periods": {"current":current,"scoring":scoring},
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/inspect.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    print("Saved allowlisted API shape inspection to private artifact.")

if __name__=="__main__":
    main()
