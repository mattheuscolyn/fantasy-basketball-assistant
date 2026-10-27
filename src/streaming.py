"""Conservative two-step fantasy streaming simulations across remaining days."""
from datetime import date, timedelta
from src.weekly import best_lineup, INACTIVE_STATUSES, INJURED_RESERVE


def streaming_options(daily_lineups, nba_schedule, free_agents, today,
                      future_schedule=None, current_roster=None,
                      acquisition_remaining=None):
    """Enumerate at most two free-agent moves, never executing transactions.

    Models the first acquisition as usable tomorrow. A second acquisition
    replaces the first streamable free agent on a later day. Future roster
    loss is estimated separately across the next two matchup weeks.
    """
    days = [d for d in sorted(daily_lineups) if date.fromisoformat(d) > today]
    if not days or acquisition_remaining == 0:
        return []
    roster = daily_lineups[days[0]]
    drop_pool = sorted(
        (p for p in roster if p.get("lineup_slot_id") != INJURED_RESERVE
         and isinstance(p.get("projected_fppg"), (int, float))),
        key=lambda p: p["projected_fppg"])[:5]
    candidates = [
        p for p in free_agents
        if p.get("availability_status") == "FREEAGENT"
        and p.get("injury_status") not in INACTIVE_STATUSES
        and isinstance(p.get("projected_fppg"), (int, float))
        and p.get("id") is not None
    ]
    # Favor useful remaining games rather than season-long FP/G alone.
    candidates.sort(
        key=lambda p: sum(
            p["projected_fppg"] *
            (nba_schedule[d].get(p.get("pro_team_id")) or
             nba_schedule[d].get(str(p.get("pro_team_id"))) or []).count("pre")
            for d in days),
        reverse=True)
    candidates = candidates[:16]
    if not candidates or not drop_pool:
        return []
    baseline = {}
    for d in days:
        baseline[d] = best_lineup(daily_lineups[d], nba_schedule[d])[0]
    baseline_sum = sum(baseline.values())
    scores = {}
    for dropped in drop_pool:
        for added in candidates:
            key = (str(dropped["id"]), str(added["id"]))
            scores[key] = {}
            for d in days:
                replacement = dict(added, lineup_slot_id=12)
                lineup = [p for p in daily_lineups[d] if p["id"] != dropped["id"]]
                scores[key][d] = best_lineup(lineup + [replacement], nba_schedule[d])[0]
    future_cost = {}
    if current_roster and future_schedule:
        base = sum(best_lineup(current_roster, games)[0]
                   for games in future_schedule.values())
        for dropped in drop_pool:
            for added in candidates:
                new = [p for p in current_roster if p["id"] != dropped["id"]]
                new.append(dict(added, lineup_slot_id=12))
                projected = sum(best_lineup(new, games)[0]
                                for games in future_schedule.values())
                future_cost[(str(dropped["id"]), str(added["id"]))] = (
                    None if dropped.get("injury_status") in
                    (INACTIVE_STATUSES | {"DAY_TO_DAY", "QUESTIONABLE"})
                    else round(projected - base, 1))

    options = []
    for dropped in drop_pool:
        for first in candidates:
            key1 = (str(dropped["id"]), str(first["id"]))
            after_first = [scores[key1][d] for d in days]
            gain = round(sum(after_first) - baseline_sum, 1)
            if gain >= 5:
                options.append({
                    "drop_id": dropped["id"], "drop": dropped["name"],
                    "moves": [{"day": days[0], "add_id": first["id"],
                               "add": first["name"], "drop": dropped["name"]}],
                    "this_week_gain": gain, "acquisitions": 1,
                    "next_two_weeks_delta": future_cost.get(key1),
                    "risk": "Player dropped from original roster could be claimed",
                })
            if acquisition_remaining is not None and acquisition_remaining < 2:
                continue
            for second in candidates:
                if second["id"] == first["id"]:
                    continue
                key2 = (str(dropped["id"]), str(second["id"]))
                # Each second date is strictly after the first becomes usable.
                for switch in range(1, len(days)):
                    total = sum(after_first[:switch]) + sum(
                        scores[key2][d] for d in days[switch:])
                    gain = round(total - baseline_sum, 1)
                    if gain < 10:
                        continue
                    options.append({
                        "drop_id": dropped["id"], "drop": dropped["name"],
                        "moves": [
                            {"day": days[0], "add_id": first["id"],
                             "add": first["name"], "drop": dropped["name"]},
                            {"day": days[switch], "add_id": second["id"],
                             "add": second["name"], "drop": first["name"]},
                        ],
                        "this_week_gain": gain, "acquisitions": 2,
                        "next_two_weeks_delta": future_cost.get(key2),
                        "risk": "Original roster player could be permanently lost; second streamer may be claimed first",
                    })
    # A future cost cannot be ignored even if the short-term gain is larger.
    # This heuristic is a ranking convenience, NOT calibrated expected wins.
    for option in options:
        future = option["next_two_weeks_delta"]
        option["three_week_net_points"] = (
            round(option["this_week_gain"] + future, 1)
            if future is not None else None)
        option["ranking_score"] = round(
            option["this_week_gain"] + min(0, future or 0) * 0.75
            - 6 * option["acquisitions"], 1)
        option["availability_note"] = (
            "Assumes free agents stay available, acquired before each listed "
            "day's games; verify processing and lock times in ESPN.")
    options.sort(key=lambda o: (o["ranking_score"], o["this_week_gain"]), reverse=True)
    # Preserve alternative original roster drops and at least one single-move
    # option per player. Otherwise every displayed scenario can sacrifice the
    # same injured-but-valuable player.
    result = []
    for dropped in drop_pool:
        group = [p for p in options if p["drop_id"] == dropped["id"]]
        singles = [p for p in group if p["acquisitions"] == 1]
        selected = group[:5]
        if singles and all(p["acquisitions"] == 2 for p in selected):
            selected.append(singles[0])
        result.extend(selected)
    return sorted(result, key=lambda p: p["ranking_score"], reverse=True)
