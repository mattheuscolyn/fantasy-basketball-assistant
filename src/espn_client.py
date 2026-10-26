"""Read-only ESPN Fantasy Basketball private league connector."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST = "https://lm-api-reads.fantasy.espn.com"
LEAGUE_ID = 394231780
SEASON = 2027


class EspnError(Exception):
    """Safe-to-log connection error; never includes response bodies or cookies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise EspnError("Unexpected ESPN redirect; credentials were not forwarded.")


def fetch(views, *, player_filter=None):
    s2, swid = os.getenv("ESPN_S2"), os.getenv("ESPN_SWID")
    if not s2 or not swid:
        raise EspnError("Missing ESPN_S2 or ESPN_SWID repository secret.")
    if not (swid.startswith("{") and swid.endswith("}")):
        raise EspnError("ESPN_SWID must include its surrounding curly braces.")
    base = f"{HOST}/apis/v3/games/fba/seasons/{SEASON}/segments/0/leagues/{LEAGUE_ID}"
    query = urlencode([("view", view) for view in views])
    headers = {
        "Accept": "application/json",
        "User-Agent": "fantasy-basketball-assistant/0.1",
        "Referer": "https://fantasy.espn.com/",
        "Cookie": f"espn_s2={s2}; SWID={swid}",
    }
    if player_filter is not None:
        headers["X-Fantasy-Filter"] = json.dumps(player_filter, separators=(",", ":"))
    request = Request(f"{base}?{query}", headers=headers, method="GET")
    opener = build_opener(NoRedirect)
    for attempt in range(3):
        try:
            with opener.open(request, timeout=30) as response:
                if "json" not in response.headers.get("Content-Type", "").lower():
                    raise EspnError("ESPN returned a non-JSON response.")
                data = response.read(12_000_001)
                if len(data) > 12_000_000:
                    raise EspnError("ESPN response exceeded the safety limit.")
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise EspnError("ESPN returned an unexpected response structure.")
                return result
        except HTTPError as error:
            if error.code in (401, 403):
                raise EspnError(f"ESPN denied access (HTTP {error.code}). Check the cookies and league membership.") from None
            if error.code == 404:
                raise EspnError("League not found (HTTP 404); check ID and season.") from None
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise EspnError(f"ESPN request failed (HTTP {error.code}).") from None
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise EspnError("Could not connect to ESPN after three attempts.") from None
        except json.JSONDecodeError:
            raise EspnError("ESPN returned invalid JSON.") from None
        time.sleep(2 ** attempt)
    raise EspnError("ESPN request failed.")


def fetch_snapshot():
    league = fetch(["mSettings", "mTeam", "mRoster"])
    if league.get("id") != LEAGUE_ID or league.get("seasonId") != SEASON:
        raise EspnError("ESPN returned a different league or season.")
    settings, teams = league.get("settings"), league.get("teams")
    if not isinstance(settings, dict) or not isinstance(teams, list):
        raise EspnError("ESPN returned no league settings or teams.")
    if not teams or any(not isinstance(t.get("roster", {}).get("entries"), list) for t in teams):
        raise EspnError("ESPN returned incomplete rosters.")
    free_agents = fetch(["kona_player_info"], player_filter={
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
            "limit": 50,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }).get("players")
    if not isinstance(free_agents, list):
        raise EspnError("ESPN returned no usable player pool.")
    return {"settings": settings, "teams": teams, "free_agents": free_agents}
