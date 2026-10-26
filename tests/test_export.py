import json
import unittest

from src.export import serialize_snapshot


class ExportTests(unittest.TestCase):
    def test_export_is_allowlisted_and_no_sensitive_identity_metadata(self):
        player = {
            "id": 12345,
            "fullName": "Example Player",
            "proTeamId": 10,
            "injuryStatus": "ACTIVE",
            "eligibleSlots": [0, 1],
            "stats": [],
            "owners": ["private-member-email@example.com"],
            "espn_s2": "DONT_EXPORT_THIS_COOKIE",
        }
        data = {
            "settings": {
                "name": "Fam league", "size": 7,
                "scoringSettings": {"scoringItems": [{"statId": 0, "points": 1}]},
                "member": {"email": "private-member-email@example.com"},
                "rosterSettings": {"lineupSlotCounts": {"0": 1}},
                "acquisitionSettings": {"acquisitionLimit": 7},
            },
            "teams": [{
                "id": 1, "name": "First team",
                "owners": ["private-member-email@example.com"],
                "roster": {"entries": [{
                    "playerId": 12345, "lineupSlotId": 0,
                    "playerPoolEntry": {"player": player},
                }]},
            }],
            "free_agents": [{"player": player, "ownership": {"percentOwned": 30}}],
        }
        payload = serialize_snapshot(data)
        parsed = json.loads(payload)
        self.assertEqual(parsed["league"]["id"], 394231780)
        self.assertEqual(parsed["teams"][0]["roster"][0]["player"]["name"], "Example Player")
        self.assertEqual(parsed["available_players"][0]["espn_player_id"], 12345)
        self.assertNotIn("DONT_EXPORT_THIS_COOKIE", payload)
        self.assertNotIn("private-member-email@example.com", payload)
        self.assertNotIn("owners", payload)


if __name__ == "__main__":
    unittest.main()
