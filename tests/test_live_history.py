import tempfile
import unittest
from datetime import date
from src.live import credited_points, remaining_fraction, active_in_progress_projection
from src.transaction_rules import transaction_settings
from src.projection_history import save_snapshot, load, attach_game_projections


class LiveAndArchiveTests(unittest.TestCase):
    def test_live_totals_have_priority_even_if_lower(self):
        self.assertEqual(credited_points({"totalPoints": 110, "totalPointsLive": 106}),
                         (106.0, "live"))
        self.assertEqual(credited_points({"totalPoints": 80}), (80.0, "settled"))

    def test_regulation_clock_and_overtime(self):
        self.assertAlmostEqual(remaining_fraction("in", 2, "06:00"), 0.625)
        self.assertEqual(remaining_fraction("in", 5, "04:00"), None)
        self.assertEqual(remaining_fraction("in", 3, None), None)
        self.assertEqual(remaining_fraction("pre", 0, ""), 1.0)

    def test_no_double_count_credited_live_points(self):
        p = {"id": 1, "lineup_slot_id": 0, "pro_team_id": 16,
             "projected_fppg": 40, "injury_status": "ACTIVE"}
        future, started = active_in_progress_projection([p], {
            "16": {"state": "in", "remaining_fraction": 0.25}})
        self.assertEqual((future, started), (10.0, 1))
        missing, count = active_in_progress_projection([p], {
            "16": {"state": "in", "remaining_fraction": None}})
        self.assertEqual((missing, count), (None, 1))

    def test_exact_daily_espn_transaction_rule(self):
        s = {"acquisitionSettings": {
            "acquisitionType": "WAIVERS_TRADITIONAL",
            "matchupLimitPerScoringPeriod": True,
            "matchupAcquisitionLimit": 1.0,
            "waiverHours": 24,
            "acquisitionLimit": -1,
        }}
        policy = transaction_settings(s, days_in_matchup=7)
        self.assertEqual(policy["per_scoring_period"], 1)
        self.assertEqual(policy["maximum_matchup_additions"], 7)
        self.assertIsNone(policy["season_limit"])
        self.assertFalse(policy["daily_usage_known"])

    def test_only_projections_saved_before_tipoff_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            players = {"123": {"projected_fppg": 31, "pro_team_id": 16},
                       "ignore": {"projected_fppg": 30, "pro_team_id": 2}}
            times = {"2026-10-27": {"16": "2026-10-27T23:30:00Z"}}
            save_snapshot(tmp, players, times, "2026-10-27T17:00:00Z")
            players["123"]["projected_fppg"] = 40
            save_snapshot(tmp, players, times, "2026-10-28T02:00:00Z")
            hist = {"123": [{"date": "2026-10-27", "actual": 50},
                            {"date": "2026-10-26", "actual": 48}]}
            out = attach_game_projections(hist, load(tmp))
            self.assertEqual(out["123"][0]["expected_at_game"], 31)
            self.assertEqual(out["123"][1]["expected_at_game"], None)
            self.assertEqual(len(load(tmp)), 2)
            with self.assertRaises(FileExistsError):
                save_snapshot(tmp, players, times, "2026-10-27T17:00:00Z")


if __name__ == "__main__":
    unittest.main()
