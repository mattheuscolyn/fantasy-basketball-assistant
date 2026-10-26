import unittest
from src.report import (
    calculate_points, projected_season_fppg, projection_audit,
    scoring_weights, safe, render
)

WEIGHTS = {0: 1, 1: 4, 2: 4, 3: 2, 6: 1, 11: -2,
           13: 2, 14: -1, 15: 1, 16: -1, 17: 1}


def projection(total=30):
    return {
        "seasonId": 2027,
        "scoringPeriodId": 0,
        "statSourceId": 1,
        "statSplitTypeId": 0,
        "appliedAverage": total,
        "appliedTotal": total,
        "stats": {"0": total},
    }


class TestScoring(unittest.TestCase):
    def test_two_point_shot(self):
        self.assertEqual(calculate_points({"0": 2, "13": 1, "14": 1}, WEIGHTS), 3)

    def test_three_point_shot(self):
        self.assertEqual(calculate_points({"0": 3, "13": 1, "14": 1, "17": 1}, WEIGHTS), 5)

    def test_free_throw(self):
        self.assertEqual(calculate_points({"0": 1, "15": 1, "16": 1}, WEIGHTS), 1)

    def test_configured_weights(self):
        rules = {"scoringSettings": {"scoringItems": [
            {"statId": key, "points": value} for key, value in WEIGHTS.items()
        ]}}
        self.assertEqual(scoring_weights(rules), WEIGHTS)

    def test_table_escaping(self):
        self.assertEqual(safe("A|B"), r"A\|B")

    def test_espn_projection_source_and_totals(self):
        entry = {"player": {
            "fullName": "Test Player",
            "stats": [projection(33.5)],
        }}
        self.assertEqual(projected_season_fppg(entry), 33.5)
        present, checked, failures = projection_audit([entry], {0: 1})
        self.assertEqual((present, checked, failures), (1, 1, []))

    def test_bad_projection_is_detected(self):
        entry = {"player": {"fullName": "Wrong Points", "stats": [projection(33.5)]}}
        present, checked, failures = projection_audit([entry], {0: 2})
        self.assertEqual((present, checked, failures), (1, 1, ["Wrong Points"]))

    def test_report_fixture(self):
        settings = {
            "name": "Test", "size": 7,
            "scoringSettings": {
                "scoringType": "H2H_POINTS",
                "scoringItems": [{"statId": 0, "points": 1}],
            },
        }
        teams = [
            {"id": i, "name": "Team " + str(i), "roster": {"entries": [
                {"playerId": i, "lineupSlotId": 0, "playerPoolEntry": {
                    "player": {
                        "fullName": "Player " + str(i),
                        "injuryStatus": "ACTIVE",
                        "stats": [projection()],
                    },
                }},
            ]}}
            for i in range(1, 8)
        ]
        agents = [{
            "player": {
                "fullName": "Example Agent",
                "injuryStatus": "ACTIVE",
                "stats": [projection(34)],
            },
            "ownership": {"percentOwned": 50.0},
        }]
        markdown, checks = render({
            "settings": settings, "teams": teams, "free_agents": agents,
        })
        self.assertTrue(all(checks.values()))
        self.assertIn("Example Agent", markdown)
        self.assertIn("Team 7", markdown)
        self.assertIn("Healthy available players", markdown)


if __name__ == "__main__":
    unittest.main()
