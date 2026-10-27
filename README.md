# Courtside · Fantasy Basketball Assistant

**Read-only mobile dashboard for the 2026–27 ESPN league (ID 394231780).** Team TayTay is the featured team, but the dashboard covers all seven teams.

## What works

- **League:** Current head-to-head matchups, byes, actual points and a projected finish calculated using season-long ESPN fantasy points per game for remaining *unstarted* NBA games.
- **Lineups:** Read the seven daily ESPN lineups for the matchup; detect eligible, higher-scoring lineup arrangements subject to the league's PG/SG/SF/PF/C/G/F and three UTIL slots.
- **Opportunities:** Simulate one hypothetical add/drop against a limited pool of ESPN free agents and show the projected remaining-week difference. Moves are never executed.
- **Trends:** Backfill recent actual game-by-game fantasy scores for rostered and available players from ESPN player cards; compare their 3-game rolling average with ESPN's *current* projected FP/G.

This project is **not affiliated with ESPN**. The ESPN fantasy API is undocumented and can change. All calculations are advisory.

## Repository architecture

- `src/espn_client.py`: authenticated GET-only ESPN fantasy API client.
- `src/weekly.py`: NBA schedule ingestion, starter eligibility and points optimization.
- `scripts/build_site.py`: private ESPN sync → allowlisted public-safe `site/data.json`.
- `site/`: static responsive HTML/CSS/JavaScript dashboard, including SVG trend charts.
- `.github/workflows/build-dashboard.yml`: runs the unit tests, builds and checks the site, uploads an expiring **private site preview**. Configured to refresh three times daily.
- `.github/workflows/espn-sync.yml`: original manual ingestion audit and one-day private snapshot artifact.

The site is a static build; visitors **never contact ESPN with your cookies**. No person can sign in to, edit, or transact within ESPN through this site.

## Required GitHub secrets

From your signed-in ESPN browser, store these in **Settings → Secrets and variables → Actions**:

- `ESPN_S2`: complete `espn_s2` cookie.
- `ESPN_SWID`: complete `SWID` cookie, including braces.

These secrets are **login session credentials**. Never paste them into the README, source, issues, Actions logs, or chat.

## Preview

Open [Build Courtside dashboard](https://github.com/mattheuscolyn/fantasy-basketball-assistant/actions/workflows/build-dashboard.yml), select the latest successful run, and download the `courtside-site-preview` artifact. It includes `index.html`, `styles.css`, `app.js`, and generated `data.json`. Serve that directory through any static HTTP server to see the interactive interface.

To use locally:

```bash
python -m http.server 8000 --directory site
```

Then visit `http://localhost:8000`. Browsers may block data fetches directly from `file://`, so use an HTTP server.

## Public GitHub Pages deployment (opt-in)

The **GitHub Free** plan generally requires a public repository for GitHub Pages. If you don't have private-repository Pages access, make the repository public only after reviewing the published fields—or publish the sanitized `site/` output in a separate public repository to keep all integration source private.

To enable Pages on this repository if eligible:

1. Open **Settings → Pages** and set **Source** to **GitHub Actions**.
2. Open **Settings → Secrets and variables → Actions → Variables** and create `ENABLE_PUBLIC_PAGES` with value `true`.
3. Start **Actions → Build Courtside dashboard → Run workflow**. Once validated, the scheduled refreshes will also deploy.
4. View the URL listed in the successful deploy job.

**Public data:** Fantasy team names/IDs, NBA player names/IDs, roster placement, projected fantasy scores, public NBA game schedules and game results, and advisory lineup/move analysis. The build rejects known sensitive fields such as cookies, emails, owner IDs and member IDs. The public payload is allowlist-constructed; full API responses and credentials are not published.

## How projections work

- ESPN matchup `totalPoints` is the actual-to-date source of truth.
- Remaining points are based on **the daily lineup currently saved in ESPN**, not on a hypothetical team of the best ten players.
- A game counts only if its NBA schedule state is **pre-game** and the player is not marked out/inactive. Live games aren't forecast further until a more accurate live-remaining method is available.
- Optimized points use a ten-slot eligible lineup (including three UTIL positions) each day; current projected total and optimized projected total are shown separately.
- Add/drop scenarios assume the new player is immediately available for **future days only**, and don't model waivers, acquisition caps, injury changes, games-played caps, or the risk of losing a dropped player. Treat as ideas requiring manual review, not orders.
- The trends page compares historical actual scoring against the **latest** ESPN season projection, not historical predictions saved before each game. DNP/zero-filled ESPN records are excluded unless a games-played flag confirms participation.

## Data reliability and security

- The backend fails rather than guessing if ESPN daily rosters are missing, an NBA schedule response is invalid, or the league's team count changes.
- Team owners, member IDs, emails, account identities, and credentials are not requested in the public dataset.
- Read-only requests only: no trade, claim, drop or lineup mutation endpoints.
- Public Pages deployment is disabled until you explicitly opt in using the repository variable.
- Refresh can lag ESPN or be delayed by scheduled GitHub Actions. A “last updated” timestamp is displayed.
- As ESPN changes, projections can be inaccurate—do not assume a calculated advantage guarantees a win.

## Tests

```bash
python -m unittest discover -s tests -v
```

Core calculations have deterministic unit tests. Scheduled builds also validate the published JSON's schema and reject forbidden fields.

## Next improvements

- Confirm acquisition/game-play limit fields with ESPN and model waivers properly.
- Widen free-agent coverage beyond the first 50 players.
- Preserve **point-in-time projection snapshots** for prospective trend analysis.
- Add lineup-lock awareness, postgame forecast calibration and personalized protected-player preferences.
