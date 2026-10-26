import unittest
from datetime import date
from src.weekly import (
    ACTIVE_SLOTS, best_lineup, current_week, lineup_alert,
    normalize_entry, scoring_period, point_value, evaluate_add_drops,
)


def player(id, score, eligible, slot, team=16, injury="ACTIVE"):
    return {
        "id": id, "name": "Player " + str(id), "pro_team_id": team,
        "lineup_slot_id": slot, "eligible_slots": eligible,
        "injury_status": injury, "projected_fppg": score,
    }


class WeeklyOptimizerTests(unittest.TestCase):
    def test_season_anchor(self):
        self.assertEqual(scoring_period(date(2026, 10, 26)), 7)
        self.assertEqual(current_week(date(2026, 10, 29))[0], date(2026, 10, 26))

    def test_only_unstarted_games_count(self):
        p = player(1, 38, [0, 11, 12], 0)
        self.assertEqual(point_value(p, {16: ["pre"]}), 38)
        self.assertEqual(point_value(p, {16: ["post"]}), 0)
        self.assertEqual(point_value(p, {16: ["in"]}), 0)
        self.assertEqual(point_value(p, {16: ["pre", "pre"]}), 76)
        p["injury_status"] = "OUT"
        self.assertEqual(point_value(p, {16: ["pre"]}), 0)

    def test_position_eligible_bench_swap(self):
        players = [
            player(1, 20, [0, 11, 12], 0),
            player(2, 42, [0, 11, 12], 12),
        ]
        optimized, picks = best_lineup(players, {16: ["pre"]})
        self.assertEqual(optimized, 62)
        self.assertEqual({p["player_id"] for p in picks}, {1, 2})

    def test_restricted_cannot_take_wrong_position(self):
        a = player(1, 30, [4, 12], 12)
        b = player(2, 40, [4, 12], 4)
        score, chosen = best_lineup([a, b], {16: ["pre"]})
        self.assertEqual(score, 40)
        self.assertEqual(chosen[0]["player_id"], 2)

    def test_eligible_lineup_alert(self):
        players = [
            player(1, 10, [0, 11, 12], 0),
            player(2, 30, [0, 11, 12], 12),
        ]
        alert = lineup_alert(players, {16: ["pre"]})
        self.assertEqual(alert["potential_gain"], 30)
        self.assertEqual(alert["bench_to_start"], ["Player 2"])

    def test_no_game_no_lineup_alert(self):
        players = [
            player(1, 30, [0, 11, 12], 0),
            player(2, 50, [0, 11, 12], 12),
        ]
        self.assertEqual(lineup_alert(players, {})["potential_gain"], 0)

    def test_acquisition_in_future_only(self):
        today = date(2026, 10, 26)
        tomorrow = "2026-10-27"
        roster = [player(1, 10, [0, 11, 12], 0)]
        agents = [player(2, 30, [0, 11, 12], 12)]
        moves = evaluate_add_drops({tomorrow: roster}, {tomorrow: {16: ["pre"]}}, agents, today)
        self.assertEqual(moves[0]["projected_gain"], 20.0)

    def test_ir_is_excluded(self):
        players = [player(1, 70, [0, 11, 13], 13)]
        self.assertEqual(best_lineup(players, {16: ["pre"]})[0], 0.0)


if __name__ == "__main__":
    unittest.main()
