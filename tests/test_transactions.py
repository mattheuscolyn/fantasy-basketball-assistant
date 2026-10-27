import unittest
from datetime import date, timedelta
from src.transactions import transaction_counts
from src.weekly import current_week


class TransactionTests(unittest.TestCase):
    def test_actual_additions_not_lineup_edits_or_canceled_claims(self):
        week = current_week(date(2026, 10, 27))
        source = {
            7: [
                {"id": "a", "teamId": 4, "type": "FUTURE_ROSTER",
                 "status": "EXECUTED", "scoringPeriodId": 7,
                 "items": [{"type": "LINEUP"}]},
                {"id": "b", "teamId": 4, "type": "WAIVER",
                 "status": "CANCELED", "scoringPeriodId": 7,
                 "items": [{"type": "ADD"}]},
            ],
            8: [
                {"id": "c", "teamId": 7, "type": "WAIVER",
                 "status": "EXECUTED", "scoringPeriodId": 8,
                 "items": [{"type": "ADD"}]},
                {"id": "d", "teamId": 7, "type": "WAIVER",
                 "status": "EXECUTED", "scoringPeriodId": 8,
                 "items": [{"type": "ADD"}, {"type": "DROP"}]},
                {"id": "e", "teamId": 7, "type": "WAIVER",
                 "status": "EXECUTED", "scoringPeriodId": 8,
                 "items": [{"type": "ADD"}, {"type": "DROP"}]},
                {"id": "f", "teamId": 4, "type": "WAIVER",
                 "status": "PENDING", "scoringPeriodId": 8,
                 "items": [{"type": "ADD"}]},
                {"id": "c", "teamId": 7, "type": "WAIVER",
                 "status": "EXECUTED", "scoringPeriodId": 8,
                 "items": [{"type": "ADD"}]},
            ],
        }
        def fake_fetch(views, scoring_period):
            self.assertEqual(views, ["mTransactions2"])
            return {"transactions": source[scoring_period]}
        d = transaction_counts(fake_fetch, week, date(2026, 10, 27), [4, 7])
        self.assertEqual(d["executed_additions_by_team"], {"4": 0, "7": 3})
        self.assertEqual(d["pending_claims_by_team"]["4"], 1)
        self.assertTrue(d["verified"])

    def test_incomplete_transaction_data_fails_closed(self):
        with self.assertRaises(ValueError):
            transaction_counts(
                lambda views, scoring_period: {"transactions": None},
                current_week(date(2026, 10, 27)),
                date(2026, 10, 27), [4])


if __name__ == "__main__":
    unittest.main()
