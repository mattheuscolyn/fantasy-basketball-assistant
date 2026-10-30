# Courtside · Fantasy Basketball Assistant

**Read-only mobile dashboard for the 2026–27 ESPN league (ID 394231780).** Team TayTay is the featured team, but the dashboard covers all seven teams.

## What works

- **League:** Current head-to-head matchups, byes, actual points and a projected finish calculated using season-long ESPN fantasy points per game for remaining *unstarted* NBA games.
- **Lineups:** Read the seven daily ESPN lineups for the matchup; detect eligible, higher-scoring lineup arrangements subject to the league's PG/SG/SF/PF/C/G/F and three UTIL slots.
- **Opportunities:** Simulate one hypothetical add/drop against a limited pool of ESPN free agents and show the projected remaining-week difference. Moves are never executed.
- **Trends:** Backfill recent actual game-by-game fantasy scores for rostered and available players from historical day-scoped ESPN rosters; compare their 3-game rolling average with ESPN's *current* projected FP/G.

This project is **not affiliated with ESPN**. The ESPN fantasy API is undocumented and can change. All calculations are advisory.

## Repository architecture

- `src/espn_client.py`: authenticated GET-only ESPN fantasy API client.
- `src/weekly.py`: NBA schedule ingestion, starter eligibility and points optimization.
- `scripts/build_site.py`: private ESPN sync → allowlisted public-safe `site/data.json`.
- `site/`: static responsive HTML/CSS/JavaScript dashboard, including SVG trend charts.
- `.github/workflows/build-dashboard.yml`: runs the unit tests, builds and checks the site, uploads an expiring **private site preview**. Configured to refresh three times daily.
- `.github/workflows/espn-sync.yml`: original manual ingestion audit and one-day private snapshot artifact.

The free-agent discovery list currently includes up to 150 available/waiver players, sorted by ESPN rostered percentage. The site is a static build; visitors **never contact ESPN with your cookies**. No person can sign in to, edit, or transact within ESPN through this site.

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
- Add/drop scenarios account for the ESPN **seven-acquisition matchup cap**, completed acquisitions, free-agent versus waiver status, and a conservative waiver-processing availability date. They intentionally do not predict waiver priority, acquisition success, intra-day clearance, injury changes, or the risk of permanently losing dropped players. Treat them as advisory estimates.
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

## October 2026: live scoring, acquisitions and projection history

**Live matchup estimate:** The dashboard credits ESPN's `totalPointsLive` (falling back to `totalPoints`). When NBA games are already underway, it estimates only the unplayed fraction of regulation time using ESPN projected FP/G, without adding another full-game projection. That extra amount is an approximation, not a prediction from actual pace. Missing NBA clock data suppress affected projections. Started lineup positions are locked in the optimizer.

**Acquisition policy:** The league's ESPN settings specify `matchupLimitPerScoringPeriod=true` and `matchupAcquisitionLimit=1`, which scale the **matchup-wide acquisition cap** by the number of scoring periods (usually **seven acquisitions across a seven-day matchup**). They do **not** mean one acquisition per day. Verified ESPN transaction history shows several completed additions in a single scoring period. There is no season-long acquisition cap. Traditional waivers have a 24-hour period, and ESPN controls their processing times; free agents can be added immediately. The dashboard now counts actual executed `ADD` transactions for each team in the current matchup and shows remaining acquisitions, plus pending requests. ESPN also provides `FREEAGENT`/`WAIVERS` status and a process timestamp for waiver players. The simulation waits until the day *after* a waiver clears before crediting games, to avoid promising intra-day availability. Claim success still depends on waiver priority, and you should verify moves in ESPN.

**Point-in-time trends:** Every successful scheduled dashboard build records a timestamped, allowlisted snapshot to the `projection-history` branch. Records contain only numeric per-player projections, ESPN NBA team IDs, and public NBA game tipoff times. The trend chart compares actual points to the **latest observed ESPN projection saved strictly before that game's tipoff**. When historical observations don't exist (including games before tracking started), the pregame expected value stays blank. We do not substitute a current projection for an older one.

Scheduled builds are serialized, so they don't overwrite each other's archive records. Snapshots are retained in Git history, not in temporary Actions artifacts or raw ESPN API files.

**Important:** The live remainder and future add/drop simulations remain estimates. We haven't incorporated per-player real-time scoring pace, verified same-day transaction usage, or detailed waiver-claim execution yet.

## Strategy: three-week decision dashboard

The **Strategy** tab is the default landing page. It compares this week's projected matchup with your next two actual ESPN opponents and their projected lineups. This week uses earned/live ESPN scores plus points from the saved daily lineup; future weeks use **current rosters optimally assigned to eligible daily slots**. No future acquisitions, injury returns, or lineup locks are assumed.

A league-wide ranking shows whether your opponent is especially tough. The app treats observed player overperformance separately: it only compares actual results against **historically saved, pre-tipoff** ESPN projections and explicitly says when observations are insufficient. A tough schedule or projected league-leading opponent is **not** evidence of luck.

The **Protected players** controls are saved in local browser storage only, never to ESPN or GitHub. By default the ten highest-projected rostered players plus any projected at least 35 FP/G are protected. Edit this list to reflect your own risk tolerance.

The **Streaming scenarios** panel simulates one- and two-acquisition sequences across the remaining week using free agents, positional constraints and the verified matchup acquisition allowance. It also estimates the next two weeks' points if the final acquisition is retained; this value is hidden when an injured dropped player's recovery makes it unreliable. Conservative mode omits uncertain or negative three-week scenarios, and neither mode ever recommends dropping a protected player. Aggressive mode does not override a user's explicit protection.

**Limitations:** This is a candidate generator, not a complete game-theoretic optimizer. It does not predict waiver competition, trades, future injuries, shifts in playing time, probability of winning, or future free-agent availability. Streamers are assumed acquired in time to play beginning on the indicated following day. A move must be carried out manually in ESPN.

## Evidence-first decision review (October 29)

The Strategy tab now includes a **scenario comparison** that recomputes counterfactual lineups and displays:

- A hold-roster baseline, projected final matchup margin, and remaining roster acquisition allowance (including pending claims).
- Day-by-day counts of usable starters for Team TayTay and its current opponent.
- Saved ESPN lineup versus optimized existing lineup versus simulated acquired-player lineup, with exact projected points gained by scoring day.
- The exact suggested add/drop sequence, newly acquired starters who produce each day's gains, and estimated separate effects on the following two matchups.
- Conditional conservative versus aggressive routes, protected-player controls, and explicit injury/availability/future-value uncertainty.
- A prominent note when even the strongest allowed plan still projects a loss.

The plan generator searches a bounded set of one- and two-roster-slot streams (up to four acquisitions in a combined sequence). It is **not an exhaustive proof** that all possible legal transactions have been considered. The dataset represents an ESPN point-in-time snapshot; a plan can cease to be available minutes later. The user must verify each transaction, roster lock, injury and pending claim directly in ESPN before acting. No transactions are made by Courtside. Longer-term permanent-loss risk cannot be reduced to the next two weeks' projection.

## Next improvements

- Improve exact intra-day eligibility and player/game lock checks for newly processed waivers; compare prospective forecasts with outcomes.
- Expand and paginate free-agent coverage beyond the initial 150-player ESPN request.
- Preserve **point-in-time projection snapshots** for prospective trend analysis.
- Add lineup-lock awareness, postgame forecast calibration and personalized protected-player preferences.
