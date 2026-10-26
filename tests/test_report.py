import unittest
from src.report import calculate_points, scoring_weights, safe, render

WEIGHTS = {0: 1, 1: 4, 2: 4, 3: 2, 6: 1, 11: -2, 13: 2, 14: -1, 15: 1, 16: -1, 17: 1}


class TestScoring(unittest.TestCase):
    def test_two_point_shot(self):
        self.assertEqual(calculate_points({"0": 2, "13": 1, "14": 1}, WEIGHTS), 3)

    def test_three_point_shot(self):
        self.assertEqual(calculate_points({"0": 3, "13": 1, "14": 1, "17": 1}, WEIGHTS), 5)

    def test_free_throw(self):
        self.assertEqual(calculate_points({"0": 1, "15": 1, "16": 1}, WEIGHTS), 1)

    def test_configured_weights(self):
        rules = {"scoringSettings": {"scoringItems": [{"statId": key, "points": value} for key, value in WEIGHTS.items()]}}
        self.assertEqual(scoring_weights(rules), WEIGHTS)

    def test_table_escaping(self):
        self.assertEqual(safe("A|B"), r"A\|B")

    def test_report_fixture(self):
        settings = {"name": "Test", "size": 7, "scoringSettings": {"scoringType": "H2H_POINTS", "scoringItems": [{"statId": 0, "points": 1}]}}
        teams = [{"id": i, "name": "Team " + str(i), "roster": {"entries": [{"playerId": i, "lineupSlotId": 0, "playerPoolEntry": {"player": {"fullName": "Player " + str(i)}}}]}} for i in range(1, 8)]
        agents = [{"player": {"fullName": "Example Agent"}, "ownership": {"percentOwned": 50.0}}]
        md, checks = render({"settings": settings, "teams": teams, "free_agents": agents})
        self.assertTrue(all(checks.values()))
        self.assertIn("Example Agent", md)
        self.assertIn("Team 7", md)


if __name__ == "__main__":
    unittest.main()
