"""Fetch the private ESPN league and show a safe-to-share workflow status."""
import os
import sys

from src.espn_client import EspnError, fetch_snapshot
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
        print("ESPN private league sync succeeded. View the Actions run Summary to see the report.")
        return 0
    except (EspnError, ValueError) as error:
        print("ESPN sync failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
