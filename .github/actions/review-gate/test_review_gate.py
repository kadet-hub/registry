import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import review_gate


class Decide(unittest.TestCase):  # AGT-11
    def test_fixtures(self):
        with open(os.path.join(HERE, "fixtures.json")) as f:
            cases = json.load(f)
        for case in cases:
            with self.subTest(case["name"]):
                reasons = review_gate.decide(case["author"], case["head"], case["reviews"], lambda login, write=case["write"]: login in write)
                self.assertEqual(not reasons, case["pass"], reasons)

    def test_write_access_asked_only_for_change_requests(self):
        asked = []
        reviews = [
            {"user": {"login": "neat-bot"}, "state": "APPROVED", "commit_id": "a"},
            {"user": {"login": "Moep90"}, "state": "APPROVED", "commit_id": "a"},
            {"user": {"login": "drive-by"}, "state": "CHANGES_REQUESTED", "commit_id": "a"},
        ]
        review_gate.decide("kadet-hub-agent[bot]", "a", reviews, lambda login: asked.append(login) or False)
        self.assertEqual(asked, ["drive-by"])

    def test_review_of_a_deleted_account(self):
        reviews = [
            {"user": None, "state": "CHANGES_REQUESTED", "commit_id": "a"},
            {"user": {"login": "neat-bot"}, "state": "APPROVED", "commit_id": "a"},
        ]
        self.assertEqual(review_gate.decide("kadet-hub-agent[bot]", "a", reviews, lambda login: True), [])


if __name__ == "__main__":
    unittest.main()
