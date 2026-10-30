import unittest
from src.decision_audit import evidence_for_plans


def player(pid, name, points, team, status="ACTIVE", free=False):
    return {"id": pid, "name": name, "projected_fppg": points,
            "pro_team_id": team, "eligible_slots": [11, 12],
            "lineup_slot_id": 11 if not free else 12,
            "injury_status": status,
            "availability_status": "FREEAGENT" if free else None}


class RiskEvidenceTests(unittest.TestCase):
    def test_injured_acquisition_cannot_claim_certain_future_benefit(self):
        base = player(1, "Keep", 10, 1)
        target = player(2, "Injury Flag", 35, 2, "DAY_TO_DAY", free=True)
        day = "2026-10-30"
        plan = {"drop_id": 1, "drop": "Keep", "acquisitions": 1,
                "moves": [{"day": day, "drop": "Keep",
                           "add": "Injury Flag", "add_id": 2}]}
        actual = evidence_for_plans(
            [plan], {day: [base]}, {day: {1: ["pre"], 2: ["pre"]}},
            [target], [base], {"2026-11-02": {1: ["pre"], 2: ["pre"]}},
            opponent_projected=120, user_projected=100)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["gain_vs_optimized"], 25)
        self.assertTrue(actual[0]["acquisition_risk"])
        self.assertIsNone(actual[0]["next_two_weeks_delta"])
        self.assertIsNone(actual[0]["three_week_net_points"])


if __name__ == "__main__":
    unittest.main()
