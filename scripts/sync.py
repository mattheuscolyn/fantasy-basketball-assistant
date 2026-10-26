"""Fetch private ESPN league, render report, and export an allowlisted artifact."""
import os
import sys
from pathlib import Path

from src.espn_client import EspnError, fetch_snapshot
from src.export import serialize_snapshot
from src.report import render


def main():
    try:
        snapshot = fetch_snapshot()
        markdown, checks = render(snapshot)
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file:
            with open(summary_file, "a", encoding="utf-8") as stream:
                stream.write(markdown)
        else:
            print(markdown)
        if not all(checks.values()):
            print("ESPN connection succeeded, but one or more validation checks need attention.", file=sys.stderr)
            return 1
        # Export only the limited, allowlisted data. Never output raw ESPN JSON.
        artifact = Path("reports/private-league-snapshot.json")
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(serialize_snapshot(snapshot), encoding="utf-8")
        print("ESPN private league sync succeeded. Sanitized snapshot created for private Actions artifact.")
        return 0
    except (EspnError, ValueError, TypeError) as error:
        print("ESPN sync failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
