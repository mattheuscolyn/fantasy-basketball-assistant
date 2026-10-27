"""Versioned ESPN projections captured before real NBA games."""
import json
from datetime import datetime, timezone
from pathlib import Path


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("UTC timestamp required")
    return value.astimezone(timezone.utc)


def save_snapshot(directory, players, game_times, captured_at=None):
    now = utc(captured_at or datetime.now(timezone.utc))
    rows = {}
    for pid, player in players.items():
        value, team = player.get("projected_fppg"), player.get("pro_team_id")
        if str(pid).isdigit() and type(value) in (int, float) and str(team).isdigit():
            rows[str(pid)] = {"ppg": round(value, 3), "team": int(team)}
    times = {}
    for day, teams in game_times.items():
        times[str(day)] = {str(tid): utc(t).isoformat().replace("+00:00", "Z")
                           for tid, t in teams.items() if str(tid).isdigit()}
    out = {"version": 1,
           "captured_at_utc": now.isoformat().replace("+00:00", "Z"),
           "players": rows, "tipoffs": times}
    path = Path(directory) / (now.strftime("%Y-%m-%dT%H-%M-%S-%fZ") + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(out, stream, separators=(",", ":"), allow_nan=False)
    return path


def load(directory):
    result = []
    for path in sorted(Path(directory).glob("*.json"))[-1500:]:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if d["version"] == 1 and isinstance(d["players"], dict):
                result.append((utc(d["captured_at_utc"]), d))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return sorted(result)


def attach_game_projections(history, snapshots):
    for pid, games in history.items():
        for game in games:
            selected = None
            for at, snapshot in snapshots:
                p = snapshot["players"].get(str(pid))
                if not p:
                    continue
                start = snapshot.get("tipoffs", {}).get(game["date"], {}).get(str(p["team"]))
                if not start or at >= utc(start):
                    continue
                if selected is None or at > selected[0]:
                    selected = (at, p["ppg"])
            game["expected_at_game"] = selected[1] if selected else None
            game["expected_recorded_at_utc"] = (
                selected[0].isoformat().replace("+00:00", "Z") if selected else None)
    return history
