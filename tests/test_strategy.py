import unittest
from datetime import date, timedelta
from src.outlook import generate_outlook, matchup_for_team, evaluate_season_signal
from src.streaming import streaming_options


def p(pid, points, team=1, slot=11, status=None):
    return {"id": pid, "name": "P" + str(pid), "projected_fppg": points,
            "pro_team_id": team, "lineup_slot_id": slot,
            "eligible_slots": [11, 12], "injury_status": "ACTIVE",
            "availability_status": status}


class SeasonPlanningTests(unittest.TestCase):
    def test_three_week_matchups_and_ranks(self):
        start = date(2026, 10, 26)
        rosters = {"1": [p(1, 40)], "2": [p(2, 30, team=2)]}
        schedule = {}
        for day in range(7, 21):
            d = (start + timedelta(days=day)).isoformat()
            schedule[d] = {1: ["pre"], 2: ["pre"]}
        current = [{"home_team_id": 1, "away_team_id": 2,
                    "home_projected": 230, "away_projected": 240}]
        future = [(1, 3, [{"home_team_id": 1, "away_team_id": 2}]),
                  (2, 4, [{"home_team_id": 2, "away_team_id": 1}])]
        result = generate_outlook(start, 2, current, future, rosters, schedule)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["teams"]["1"]["projected_points"], 280)
        self.assertEqual(result[1]["teams"]["1"]["league_rank"], 1)
        self.assertEqual(matchup_for_team(result[2], 1), 2)
        signal = evaluate_season_signal(result, 1)
        self.assertEqual(signal["recommendation"], "Consider safe streaming")
        self.assertEqual(signal["observed_performance"]["status"], "Not enough evidence")

    def test_two_step_stream_can_fill_different_days(self):
        today = date(2026, 10, 27)
        wed, thu, fri = "2026-10-28", "2026-10-29", "2026-10-30"
        base = p(1, 10, team=1)
        first = p(2, 40, team=2, status="FREEAGENT")
        second = p(3, 40, team=3, status="FREEAGENT")
        lineups = {d: [base] for d in (wed, thu, fri)}
        nba = {wed: {1: ["pre"], 2: ["pre"]},
               thu: {1: ["pre"], 3: ["pre"]},
               fri: {1: ["pre"], 3: ["pre"]}}
        moves = streaming_options(lineups, nba, [first, second], today,
                                  acquisition_remaining=2)
        two = [x for x in moves if x["acquisitions"] == 2
               and x["moves"][0]["add_id"] == 2
               and x["moves"][1]["add_id"] == 3]
        self.assertTrue(two)
        self.assertEqual(two[0]["this_week_gain"], 90)
        self.assertEqual(two[0]["moves"][1]["day"], thu)

    def test_no_acquisitions_means_no_streaming_plan(self):
        today = date(2026, 10, 27)
        self.assertEqual(streaming_options(
            {"2026-10-28": [p(1, 10)]},
            {"2026-10-28": {1: ["pre"]}},
            [p(2, 40, status="FREEAGENT")], today,
            acquisition_remaining=0), [])


if __name__ == "__main__":
    unittest.main()
