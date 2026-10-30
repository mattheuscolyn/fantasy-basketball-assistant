import unittest
from src.decision_audit import evaluate_sequence, evidence_for_plans


def p(n, score, team, slot=11, free=False):
    return {"id": n, "name": "Player " + str(n),
            "projected_fppg": score, "pro_team_id": team,
            "eligible_slots": [11, 12], "lineup_slot_id": slot,
            "injury_status": "ACTIVE",
            "availability_status": "FREEAGENT" if free else None}


class DecisionAuditTests(unittest.TestCase):
    def test_daily_replay_accounts_for_new_starts(self):
        original = [p(1, 10, 1)]
        fa = [p(2, 30, 2, free=True), p(3, 40, 3, free=True)]
        rosters = {"2026-10-30": original, "2026-10-31": original}
        games = {
            "2026-10-30": {1: ["pre"], 2: ["pre"]},
            "2026-10-31": {1: ["pre"], 3: ["pre"]},
        }
        moves = [
            {"day": "2026-10-30", "drop_id": 1, "add_id": 2},
            {"day": "2026-10-31", "drop_id": 2, "add_id": 3},
        ]
        audit = evaluate_sequence(moves, rosters, games, fa)
        self.assertEqual(audit["remaining_optimized_no_moves"], 20)
        self.assertEqual(audit["remaining_scenario_points"], 70)
        self.assertEqual(audit["gain_vs_optimized"], 50)
        self.assertEqual(audit["daily_evidence"][0]["extra_fp"], 20)
        self.assertEqual(audit["daily_evidence"][1]["extra_fp"], 30)
        self.assertEqual(audit["daily_evidence"][1]["newly_acquired_starters"][0]["player"], "Player 3")

    def test_missing_free_agent_fails(self):
        with self.assertRaises(ValueError):
            evaluate_sequence(
                [{"day": "2026-10-30", "drop_id": 1, "add_id": 999}],
                {"2026-10-30": [p(1, 10, 1)]},
                {"2026-10-30": {1: ["pre"]}}, [])

    def test_scenario_projection_does_not_double_count_free_lineup_fixes(self):
        a, b = p(1, 10, 1, slot=12), p(2, 20, 2, slot=11)
        one = p(3, 30, 3, free=True)
        rosters = {"2026-10-30": [a, b]}
        games = {"2026-10-30": {1: ["pre"], 2: ["pre"], 3: ["pre"]}}
        plans = [{"drop_id": 2, "drop": "Player 2",
                  "moves": [{"day": "2026-10-30", "add_id": 3,
                             "add": "Player 3", "drop": "Player 2"}],
                  "acquisitions": 1}]
        # Current saved +20, optimized no move +30,
        # scenario +40 => +10 free lineup +10 streaming.
        evidence = evidence_for_plans(plans, rosters, games, [one],
                                      [a, b], {}, opponent_projected=150,
                                      user_projected=100)
        self.assertEqual(evidence[0]["free_lineup_gain"], 10)
        self.assertEqual(evidence[0]["gain_vs_optimized"], 10)
        self.assertEqual(evidence[0]["scenario_final"], 120)
        self.assertEqual(evidence[0]["scenario_margin"], -30)
        self.assertFalse(evidence[0]["closes_projected_gap"])


if __name__ == "__main__":
    unittest.main()
