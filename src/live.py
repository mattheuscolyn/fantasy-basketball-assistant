"""Read-only NBA in-progress scoring and conservative remaining-game estimates.

Credit ESPN's live matchup totals exactly once; estimate only the portion of
an ongoing NBA game that has not yet been played. These are not win odds.
"""
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import json
import re

EASTERN = ZoneInfo("America/New_York")
CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def remaining_fraction(state, period, clock):
    """Fraction of regulation time remaining; not a fantasy scoring guarantee."""
    if state == "pre":
        return 1.0
    if state == "post":
        return 0.0
    if state != "in" or not isinstance(period, int) or period < 1:
        return None
    if period >= 5:
        # Overtime is unpredictable; mark unquantifiable rather than invent minutes.
        return None
    m = CLOCK_RE.fullmatch(str(clock or ""))
    if not m:
        return None
    mins, secs = map(int, m.groups())
    if mins > 12 or secs > 59:
        return None
    return max(0.0, min(1.0, ((4 - period) * 12 + mins + secs / 60) / 48))


def live_game_details(day):
    """Only scheduled events for the NBA Eastern calendar day; team IDs are public."""
    url = ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
           "?dates=" + day.strftime("%Y%m%d") + "&limit=100")
    req = Request(url, headers={"User-Agent": "courtside-readonly/0.2",
                                "Accept": "application/json"})
    try:
        with urlopen(req, timeout=25) as stream:
            data = json.loads(stream.read(3_000_000))
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        raise ValueError("Live NBA game details unavailable.") from None
    if not isinstance(data.get("events"), list):
        raise ValueError("NBA scoreboard did not return events.")
    teams = {}
    for event in data["events"]:
        competition = (event.get("competitions") or [{}])[0]
        game_time = event.get("date")
        if not game_time:
            continue
        instant = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
        if instant.astimezone(EASTERN).date() != day:
            continue
        status = event.get("status") or {}
        state = (status.get("type") or {}).get("state")
        if state not in ("pre", "in", "post"):
            raise ValueError("Unknown NBA state.")
        remaining = remaining_fraction(state, status.get("period"), status.get("displayClock"))
        for opponent in competition.get("competitors") or []:
            id_string = str((opponent.get("team") or {}).get("id") or "")
            if not id_string.isdigit():
                raise ValueError("NBA game missing team ID.")
            teams[id_string] = {
                "state": state,
                "remaining_fraction": remaining,
                "tipoff_utc": instant.isoformat().replace("+00:00", "Z"),
            }
    return teams


def active_in_progress_projection(roster, day_games):
    """Projected future points for already-started players in saved active slots.

    Do not use this value for lineup-change optimization: games already started
    are locked. Returns None if necessary game-clock data are unavailable.
    """
    from src.weekly import ACTIVE_SLOTS, INACTIVE_STATUSES
    total = 0.0
    started = 0
    for player in roster:
        if player.get("lineup_slot_id") not in ACTIVE_SLOTS:
            continue
        game = day_games.get(str(player.get("pro_team_id"))) or {}
        if game.get("state") != "in":
            continue
        started += 1
        fraction = game.get("remaining_fraction")
        projection = player.get("projected_fppg")
        if fraction is None or not isinstance(projection, (int, float)):
            return None, started
        # Do not ignore previously selected player just because injury status
        # changed midgame. Partial points remain in ESPN's matchup total.
        total += max(0, float(projection)) * fraction
    return round(total, 2), started


def credited_points(side):
    """ESPN's live value takes precedence, including legitimate negative deltas."""
    if not isinstance(side, dict):
        return (0.0, "missing")
    for key, label in (("totalPointsLive", "live"), ("totalPoints", "settled")):
        value = side.get(key)
        if type(value) in (int, float):
            return float(value), label
    return (0.0, "missing")
