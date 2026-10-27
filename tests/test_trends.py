import unittest
from datetime import date
from scripts.build_site import _history, SEASON_DAY_ONE


def record(period, total, minutes=None):
    return {
        "seasonId": 2027, "scoringPeriodId": period,
        "statSourceId": 0, "statSplitTypeId": 5,
        "appliedTotal": total,
        "stats": {"40": minutes} if minutes is not None else {},
    }


def stub(entries_by_day):
    def mock_fetch(views, scoring_period):
        assert views == ["mRoster"]
        stats = entries_by_day.get(scoring_period, [])
        return {"teams": [{"roster": {"entries": [
            {"playerId": 33, "playerPoolEntry": {
                "player": {"id": 33, "stats": [item]}}}
            for item in stats
        ]}}]}
    return mock_fetch


class TrendsTests(unittest.TestCase):
    def test_only_actual_games_count(self):
        data = {
            1: [record(1, 34, 30)],
            2: [record(2, 0)],
            3: [record(3, 48, 35)],
            4: [record(4, 0, 12)],
        }
        result = _history(SEASON_DAY_ONE, date(2026, 10, 26), stub(data))
        self.assertEqual(result["33"], [
            {"date": "2026-10-20", "actual": 34.0},
            {"date": "2026-10-22", "actual": 48.0},
            {"date": "2026-10-23", "actual": 0.0},
        ])

    def test_missing_games_are_not_zeros(self):
        result = _history(SEASON_DAY_ONE, date(2026, 10, 26),
                          stub({4: [record(4, 0)]}))
        self.assertEqual(result, {})

    def test_other_scoring_period_ignored(self):
        result = _history(SEASON_DAY_ONE, date(2026, 10, 26),
                          stub({5: [record(4, 25, 30)]}))
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
