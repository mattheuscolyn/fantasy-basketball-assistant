# Fantasy Basketball Assistant

A private, **read-only** ESPN Fantasy Basketball integration for the 2026–27 **2026-7 fam league** (league ID **394231780**, seven teams, head-to-head points).

## What's implemented

A manually triggered GitHub Actions sync that:
- Authenticates to the private league with credentials stored in GitHub Actions secrets.
- Reads ESPN's scoring rules, current seven team rosters, and player injury statuses.
- Requests the top 50 free agents or waiver players by ESPN rostered percentage.
- Writes a scoring audit, roster inventory, and available-player report to the **private GitHub Actions run Summary**.
- Checks that data are actually present, rather than silently claiming a successful empty import.

This is an ingestion audit, **not** yet a projection model or an add/drop recommendation engine. It makes **read-only GET requests** and will never make roster transactions. It does not schedule itself.

## First run

1. In the repository, visit **Settings → Secrets and variables → Actions**.
2. Add repository secret `ESPN_S2` with your complete ESPN `espn_s2` browser cookie.
3. Add repository secret `ESPN_SWID` with your complete ESPN `SWID` browser cookie (including the surrounding curly braces).
4. Visit **Actions → ESPN private league read-only sync → Run workflow** on branch `main`.
5. Open the completed run and read the **Summary**. A failed data-quality check will mark the workflow as unsuccessful.

Session cookies grant access to your ESPN account. Never paste them into chat, a commit, an issue, or logs. If they expire, replace the two secrets with fresh values. If they leak, sign out of ESPN sessions / rotate credentials.

The connection uses ESPN's unofficial API. ESPN can modify or block its endpoints without notice, so the first run needs validation. If a run fails, share the **non-sensitive error text** only, not the raw API response, request headers, or cookies.

## Local test

Python 3.12 and its standard library are enough:

```bash
python -m unittest discover -s tests -v
# If credentials are already in the local environment:
python -m scripts.sync
```

The workflow output is restricted to viewers of this private repository, but still includes league members' rosters and should be treated as private. The program does not commit or upload snapshots to source control.

## After the first successful report

1. Confirm all seven team rosters and the exact scoring formula against ESPN.
2. Identify your team and audit lineup slots, acquisition/waiver rules, and matchup calendar.
3. Add schedule- and injury-aware projections, with safeguards against double-counting.
4. Test add/drop and lineup optimization by measuring subsequent actual performance.
5. Optionally schedule monitoring, keeping transactions manual until you choose otherwise.
