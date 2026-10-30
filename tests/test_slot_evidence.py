import unittest
from src.decision_audit import evaluate_sequence


def player(pid, name, value, team, slots, lineup=12):
    return {
        "id": pid, "name": name, "projected_fppg": value,
        "pro_team_id": team, "eligible_slots": slots,
        "lineup_slot_id": lineup, "injury_status": "ACTIVE",
        "availability_status": "FREEAGENT",
    }


class AssignedSlotEvidenceTests(unittest.TestCase):
    def test_two_new_players_receive_distinct_legal_positions(self):
        original = [player(1, "Old guard", 10, 1, [0, 12], 0),
                    player(2, "Old center", 10, 2, [4, 12], 4)]
        free_agents = [player(3, "New guard", 35, 3, [0, 11, 12]),
                       player(4, "New center", 32, 4, [4, 11, 12])]
        moves = [
            {"day": "2026-10-30", "drop_id": 1, "add_id": 3},
            {"day": "2026-10-30", "drop_id": 2, "add_id": 4},
        ]
        result = evaluate_sequence(
            moves, {"2026-10-30": original},
            {"2026-10-30": {1: ["pre"], 2: ["pre"], 3: ["pre"], 4: ["pre"]}},
            free_agents)
        starters = result["daily_evidence"][0]["newly_acquired_starters"]
        self.assertEqual(len(starters), 2)
        self.assertEqual(result["gain_vs_optimized"], 47.0)
        self.assertIn(starters[0]["assigned_slot"], ("PG", "UTIL"))
        self.assertIn(starters[1]["assigned_slot"], ("C", "UTIL"))
        self.assertEqual(len(set((s["assigned_slot"] for s in starters))), 2)

    def test_locked_util_slots_cannot_be_reused(self):
        active = [
            player(1, "Locked 1", 40, 1, [11, 12], 11),
            player(2, "Locked 2", 40, 2, [11, 12], 11),
            player(3, "Locked 3", 40, 3, [11, 12], 11),
            player(4, "Expendable", 5, 4, [0, 12], 0),
        ]
        added = [player(5, "UTIL-only pickup", 35, 5, [11, 12])]
        result = evaluate_sequence(
            [{"day": "2026-10-30", "drop_id": 4, "add_id": 5}],
            {"2026-10-30": active},
            {"2026-10-30": {1: ["in"], 2: ["in"], 3: ["in"],
                             4: ["pre"], 5: ["pre"]}}, added)
        self.assertEqual(result["gain_vs_optimized"], -5)
        self.assertFalse(result["daily_evidence"][0]["newly_acquired_starters"])


if __name__ == "__main__":
    unittest.main()
