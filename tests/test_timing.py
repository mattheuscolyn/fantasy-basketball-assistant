import unittest
from src.decision_audit import improve_first_drop_timing


def player(pid,name,score,team,slot,eligible=None):
    return {"id":pid,"name":name,"projected_fppg":score,"pro_team_id":team,
            "lineup_slot_id":slot,"eligible_slots":eligible or [11,12],
            "injury_status":"ACTIVE","availability_status":"FREEAGENT"}


class TimingTests(unittest.TestCase):
    def test_keep_friday_starter_and_drop_before_saturday(self):
        powell=player(1,"Powell",36,1,11)
        bench=player(2,"Bench",10,4,12)
        ayo=player(3,"Ayo",30,2,12)
        grayson=player(4,"Grayson",27,3,12)
        friday="2026-10-30"
        saturday="2026-10-31"
        rosters={friday:[powell,bench],saturday:[powell,bench]}
        games={friday:{1:["pre"],2:["pre"]},
               saturday:{2:["pre"],3:["pre"]}}
        moves=[{"day":friday,"drop_id":1,"add_id":3,"drop":"Powell","add":"Ayo"},
               {"day":friday,"drop_id":2,"add_id":4,"drop":"Bench","add":"Grayson"}]
        revised,evidence=improve_first_drop_timing(moves,rosters,games,[ayo,grayson])
        self.assertEqual(next(x["day"] for x in revised if x["drop_id"]==1),saturday)
        self.assertEqual(evidence["daily_evidence"][0]["extra_fp"],0)
        self.assertEqual(evidence["daily_evidence"][1]["extra_fp"],57)
        self.assertEqual(evidence["gain_vs_optimized"],57)


if __name__=="__main__":
    unittest.main()
