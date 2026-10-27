import unittest
from datetime import date
from scripts.build_site import _history


def record(period, total, played=True):
    return {
        "seasonId": 2027, "scoringPeriodId": period,
        "statSourceId": 0, "statSplitTypeId": 5,
        "appliedTotal": total,
        "stats": {"42": 1, "41": 1} if played else {},
    }


class TrendsTests(unittest.TestCase):
    def test_actual_player_games_only(self):
        def mock_fetch(views, player_filter):
            self.assertEqual(views, ["kona_playercard"])
            self.assertIn(33, player_filter["players"]["filterIds"]["value"])
            return {"players": [{"id": 33, "player": {"id": 33, "stats": [
                record(1, 34), record(2, 0, played=False),
                record(3, 48),
                {"seasonId": 2027, "scoringPeriodId": 0,
                 "statSourceId": 1, "statSplitTypeId": 0,
                 "appliedTotal": 3200},
                record(4, 45),
            ]}}]}
        actual = _history(date(2026, 10, 26), {"33": {}}, espn_fetch=mock_fetch)
        self.assertEqual(actual["33"], [
            {"date": "2026-10-20", "actual": 34.0},
            {"date": "2026-10-22", "actual": 48.0},
            {"date": "2026-10-23", "actual": 45.0},
        ])

    def test_empty_player_history_is_not_backfilled_with_zeros(self):
        fake = lambda views, player_filter: {
            "players": [{"id": 33, "player": {"id": 33, "stats": [record(4, 0, False)]}}]
        }
        self.assertEqual(_history(date(2026, 10, 26), {"33": {}}, espn_fetch=fake), {})


if __name__ == "__main__":
    unittest.main()
