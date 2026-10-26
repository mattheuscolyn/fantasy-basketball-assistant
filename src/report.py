"""Conservative report from ESPN's actual league data, without forecast claims."""
from datetime import datetime, timezone
from html import escape

STAT_NAMES = {
    0: "Points (PTS)", 1: "Blocks (BLK)", 2: "Steals (STL)",
    3: "Assists (AST)", 4: "Offensive rebounds", 5: "Defensive rebounds",
    6: "Rebounds (REB)", 11: "Turnovers (TO)", 13: "Field goals made (FGM)",
    14: "Field goals attempted (FGA)", 15: "Free throws made (FTM)",
    16: "Free throws attempted (FTA)", 17: "Three-pointers made (3PM)",
}


def safe(value):
    """Escape user-controlled names in GitHub-flavored Markdown."""
    return escape(str(value if value is not None else ""), quote=True).replace("|", r"\|").replace("\n", " ")


def player_data(entry):
    pool = entry.get("playerPoolEntry") or {}
    player = entry.get("player") or pool.get("player") or {}
    return player if isinstance(player, dict) else {}


def actual_season_fppg(entry, season=2027):
    """Return explicit ESPN current-season actual average; never impute."""
    player = player_data(entry)
    pool = entry.get("playerPoolEntry") or {}
    stats = player.get("stats") or pool.get("stats") or []
    for stat in stats:
        if (
            stat.get("seasonId") == season
            and stat.get("scoringPeriodId") == 0
            and stat.get("statSourceId", stat.get("statTypeId")) == 0
            and stat.get("statSplitTypeId", 0) == 0
            and isinstance(stat.get("appliedAverage"), (int, float))
        ):
            return float(stat["appliedAverage"])
    return None


def scoring_weights(settings):
    weights = {}
    items = (settings.get("scoringSettings") or {}).get("scoringItems") or []
    for item in items:
        if "statId" not in item or "points" not in item:
            continue
        key = int(item["statId"])
        if key in weights:
            raise ValueError("ESPN returned duplicated stat ID in scoring rules.")
        weights[key] = float(item["points"])
    return weights


def calculate_points(stats, weights):
    """Compute points from raw ESPN stat IDs and league weights."""
    return sum(float(stats.get(str(k), stats.get(k, 0))) * v
               for k, v in weights.items())


def render(snapshot):
    settings = snapshot["settings"]
    teams = snapshot["teams"]
    agents = snapshot["free_agents"]
    scoring = settings.get("scoringSettings") or {}
    weights = scoring_weights(settings)
    expected_size = settings.get("size")
    result = [
        "# ESPN Fantasy Basketball — private league connection report",
        "",
        "_Retrieved " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + ". Read-only: no transactions performed._",
        "",
        "**League:** " + safe(settings.get("name", "Unknown")) + "  ",
        "**Teams:** " + str(len(teams)) + " (ESPN league setting: " + safe(expected_size) + ")  ",
        "**Season:** 2026–27 (ESPN season 2027)  ",
        "**Scoring type:** " + safe(scoring.get("scoringType", "Unknown")) + "  ",
        "**Available/waiver players loaded:** " + str(len(agents)) + " (ESPN top 50 by rostered percentage)",
        "",
        "## Scoring rules from ESPN",
        "| ESPN statistic | Points per event |",
        "|---|---:|",
    ]
    for stat_id, points in sorted(weights.items()):
        result.append("| " + safe(STAT_NAMES.get(stat_id, "Unmapped stat ID " + str(stat_id))) + " | " + format(points, "g") + " |")
    if not weights:
        result.append("| No scoring rules returned | — |")
    overrides = [str(item.get("statId")) for item in scoring.get("scoringItems", []) if item.get("pointsOverrides")]
    if overrides:
        result += ["", "**Warning:** ESPN returned scoring overrides for statistic IDs " + ", ".join(overrides) + ". Base scoring weights alone may not cover these exceptions."]
    result += ["", "## Current team rosters", "Lineup slot IDs are left as ESPN returns them; position labels will be validated separately."]
    for team in sorted(teams, key=lambda t: t.get("id", 0)):
        roster = (team.get("roster") or {}).get("entries") or []
        team_name = team.get("name") or (str(team.get("location", "")) + " " + str(team.get("nickname", ""))).strip() or "Unnamed team"
        result += [
            "",
            "### " + safe(team_name) + " (ESPN team " + safe(team.get("id")) + ")",
            "| Player | Slot ID | Injury/status | Actual season FP/G |",
            "|---|---:|---|---:|",
        ]
        for item in roster:
            player = player_data(item)
            value = actual_season_fppg(item)
            result.append("| " + safe(player.get("fullName", "Player ID " + str(item.get("playerId", "?")))) +
                          " | " + safe(item.get("lineupSlotId")) +
                          " | " + safe(player.get("injuryStatus", "Unknown")) +
                          " | " + (format(value, ".1f") if value is not None else "—") + " |")
        if not roster:
            result.append("| No player entries returned | — | — | — |")
    result += [
        "",
        "## Available/waiver players",
        "Sorted by ESPN rostered percentage, **not** by projected value.",
        "| Player | Rostered % | Injury/status | Actual season FP/G |",
        "|---|---:|---|---:|",
    ]
    for entry in agents:
        player = player_data(entry)
        ownership = entry.get("ownership") or (entry.get("playerPoolEntry") or {}).get("ownership") or player.get("ownership") or {}
        owned = ownership.get("percentOwned")
        value = actual_season_fppg(entry)
        result.append("| " + safe(player.get("fullName", "Unknown")) +
                      " | " + (format(float(owned), ".1f") + "%" if isinstance(owned, (int, float)) else "—") +
                      " | " + safe(player.get("injuryStatus", "Unknown")) +
                      " | " + (format(value, ".1f") if value is not None else "—") + " |")
    if not agents:
        result.append("| No available players returned | — | — | — |")
    checks = {
        "Expected seven teams": len(teams) == expected_size == 7,
        "Every team has at least one roster entry": all(bool((t.get("roster") or {}).get("entries")) for t in teams),
        "Scoring rules present": bool(weights),
        "Player pool present": bool(agents),
    }
    result += ["", "## Data-quality checks"]
    for check, passed in checks.items():
        result.append("- " + ("PASS" if passed else "CHECK") + ": " + check)
    result += [
        "",
        "> This first run verifies data ingestion. It does not yet make projection, trade, or add/drop claims.",
        "> No private league data are committed to source control; the report appears in the private GitHub Actions run summary.",
    ]
    return "\n".join(result) + "\n", checks
