"""Counterfactual lineup evidence for streaming choices.

All scenarios are advisory. Every reported gain is recomputed from eligible
daily starters against the same optimized no-transaction baseline.
"""
from datetime import date
from itertools import combinations
from src.weekly import best_lineup, current_lineup_score, point_value


def evaluate_sequence(moves, daily_rosters, nba_schedule, free_agents,
                      current_roster=None, future_schedule=None):
    """Replay planned acquisitions and record every affected daily lineup."""
    pool = {str(p["id"]): p for p in free_agents if p.get("id") is not None}
    days = sorted(daily_rosters)
    active_added = {}
    removed_ids = set()
    evidence = []
    totals = {"saved": 0.0, "optimized": 0.0, "scenario": 0.0}
    moves_by_day = {}
    for move in moves:
        moves_by_day.setdefault(move["day"], []).append(move)
    for day in days:
        original = daily_rosters[day]
        games = nba_schedule[day]
        for move in moves_by_day.get(day, []):
            drop_id = str(move["drop_id"])
            add_id = str(move["add_id"])
            if add_id not in pool:
                raise ValueError("Proposed acquisition no longer in free-agent pool.")
            if drop_id in active_added:
                del active_added[drop_id]
            else:
                removed_ids.add(drop_id)
            active_added[add_id] = dict(pool[add_id], lineup_slot_id=12)
        simulated = ([p for p in original if str(p.get("id")) not in removed_ids]
                     + list(active_added.values()))
        actual_saved = current_lineup_score(original, games)
        optimal, baseline_picks = best_lineup(original, games)
        updated, updated_picks = best_lineup(simulated, games)
        ids = {str(p["id"]): p for p in simulated if p.get("id") is not None}
        starters = []
        for item in updated_picks:
            p = ids.get(str(item["player_id"]))
            if p:
                starters.append({
                    "player": p["name"],
                    "id": p["id"],
                    "projected_points": round(point_value(p, games), 1),
                    "acquired": str(p["id"]) in active_added,
                })
        gained = round(updated - optimal, 1)
        total = {
            "date": day,
            "saved_lineup_fp": round(actual_saved, 1),
            "optimized_no_move_fp": round(optimal, 1),
            "scenario_fp": round(updated, 1),
            "extra_fp": gained,
            "baseline_usable_starts": len(baseline_picks),
            "scenario_usable_starts": len(updated_picks),
            "scenario_starters": sorted(starters, key=lambda p: -p["projected_points"]),
            "newly_acquired_starters": [p for p in starters if p["acquired"]],
        }
        evidence.append(total)
        totals["saved"] += actual_saved
        totals["optimized"] += optimal
        totals["scenario"] += updated
    output = {
        "daily_evidence": evidence,
        "remaining_saved_points": round(totals["saved"], 1),
        "remaining_optimized_no_moves": round(totals["optimized"], 1),
        "remaining_scenario_points": round(totals["scenario"], 1),
        "gain_vs_optimized": round(totals["scenario"]-totals["optimized"], 1),
        "free_lineup_gain": round(totals["optimized"]-totals["saved"], 1),
    }
    if current_roster is not None and future_schedule is not None:
        updated_roster = [p for p in current_roster
                          if str(p.get("id")) not in removed_ids]
        updated_roster.extend(active_added.values())
        by_week = {}
        for day, games in future_schedule.items():
            baseline, _ = best_lineup(current_roster, games)
            scenario, _ = best_lineup(updated_roster, games)
            monday = date.fromisoformat(day)
            monday = monday.fromordinal(monday.toordinal()-monday.weekday())
            key = monday.isoformat()
            by_week[key] = round(by_week.get(key, 0) + scenario - baseline, 2)
        output["future_week_deltas"] = {k: round(v, 1) for k, v in sorted(by_week.items())}
        output["next_two_weeks_delta"] = round(sum(by_week.values()), 1)
    return output


def _convert_plan(plan, first_day):
    return [{
        "day": move["day"],
        "drop_id": (plan["drop_id"] if i == 0 else plan["moves"][i-1]["add_id"]),
        "add_id": move["add_id"],
        "drop": move["drop"],
        "add": move["add"],
    } for i, move in enumerate(plan["moves"])]


def evidence_for_plans(plans, daily_rosters, nba_schedule, agents,
                       current_roster, future_schedule, opponent_projected,
                       user_projected, max_acquisitions=None):
    """Explain individual plans plus compatible pairs of independent streams."""
    pool = [p for p in agents if p.get("id") is not None]
    enriched = []
    for plan in plans:
        moves = _convert_plan(plan, next(iter(daily_rosters)))
        if max_acquisitions is not None and len(moves) > max_acquisitions:
            continue
        audit = evaluate_sequence(moves, daily_rosters, nba_schedule, pool,
                                  current_roster, future_schedule)
        item = dict(plan)
        item.update(audit)
        item["move_ids"] = moves
        item["scenario_final"] = round(user_projected + audit["free_lineup_gain"] + audit["gain_vs_optimized"], 1)
        item["scenario_margin"] = round(item["scenario_final"]-opponent_projected, 1)
        item["closes_projected_gap"] = item["scenario_margin"] >= 0
        item["drop_ids"] = [plan["drop_id"]]
        enriched.append(item)
    # Limit the combinatorial search to best alternatives for each original drop.
    grouped = {}
    for plan in enriched:
        grouped.setdefault(str(plan["drop_id"]), []).append(plan)
    candidates = []
    for group in grouped.values():
        best_double = sorted((p for p in group if p["acquisitions"] == 2),
                             key=lambda p:p["gain_vs_optimized"], reverse=True)[:1]
        best_single = sorted((p for p in group if p["acquisitions"] == 1),
                             key=lambda p:p["gain_vs_optimized"], reverse=True)[:1]
        candidates.extend(best_double+best_single)
    combined = []
    for a, b in combinations(candidates, 2):
        if a["drop_id"] == b["drop_id"]:
            continue
        occupied = {str(m["add_id"]) for m in a["move_ids"]}
        occupied2 = {str(m["add_id"]) for m in b["move_ids"]}
        if occupied & occupied2:
            continue
        moves = sorted(a["move_ids"] + b["move_ids"],
                       key=lambda m:(m["day"],str(m["drop_id"])))
        if max_acquisitions is not None and len(moves) > max_acquisitions:
            continue
        audit = evaluate_sequence(moves, daily_rosters, nba_schedule, pool,
                                  current_roster, future_schedule)
        if audit["gain_vs_optimized"] <= max(
                a["gain_vs_optimized"], b["gain_vs_optimized"])+1:
            continue
        output = {
            "moves": [{k: m[k] for k in ("day","drop","add","add_id")}
                      for m in moves],
            "move_ids": moves,
            "drop_ids": [a["drop_id"],b["drop_id"]],
            "drop": a["drop"]+" + "+b["drop"],
            "acquisitions": len(moves),
            "risk": "Two original roster players may be permanently lost",
            "availability_note": "Immediate-availability and future-roster scenario only; confirm every transaction.",
        }
        output.update(audit)
        output["this_week_gain"] = audit["gain_vs_optimized"]
        output["three_week_net_points"] = round(
            audit["gain_vs_optimized"]+audit.get("next_two_weeks_delta",0),1)
        output["scenario_final"] = round(user_projected + audit["free_lineup_gain"] + audit["gain_vs_optimized"], 1)
        output["scenario_margin"] = round(output["scenario_final"]-opponent_projected,1)
        output["closes_projected_gap"] = output["scenario_margin"]>=0
        combined.append(output)
    # Diverse drop sets, avoid 20 near-identical recommendations.
    by_roster_drop = {}
    for p in sorted(enriched+combined,
                    key=lambda x:(x["scenario_margin"],
                                  x.get("next_two_weeks_delta") or -1e9),
                    reverse=True):
        key = tuple(sorted(str(x) for x in p["drop_ids"]))
        by_roster_drop.setdefault(key, [])
        if len(by_roster_drop[key]) < 5:
            by_roster_drop[key].append(p)
    result = [p for group in by_roster_drop.values() for p in group]
    for p in result:
        p["verified_availability"] = False
        p["assumption"] = ("All suggested players must still be free agents and "
                            "eligible before each game's roster lock. No ESPN "
                            "transaction or future availability is guaranteed.")
        p["future_uncertainty"] = (
            "Future-week projection holds current NBA injury statuses fixed and "
            "does not forecast a dropped player's recovery.")
        p["scenario_type"] = "two-roster-spot" if len(p["drop_ids"]) == 2 else "one-roster-spot"
    return sorted(result, key=lambda p:p["scenario_margin"], reverse=True)[:40]
