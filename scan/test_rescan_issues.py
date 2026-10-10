import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rescan_issues import issues

ROWS = [
    ("rescan", "demo", "1.2.0", "gitleaks: aws-access-token: settings.yml:3"),
    ("rescan", "demo", "1.2.0", "gitleaks: aws-access-token: other.yml:1"),
    ("rescan", "demo", "1.2.0", "gitleaks: github-pat: a.py:9"),
    ("rescan", "demo", "1.2.0", "tree: symlink passwd"),
    ("rescan", "demo", "1.2.0", "tree: executable run.sh"),
    ("drift", "demo", "v1.2.0", "tag v1.2.0 resolves to nothing, the entry pins " + "a" * 40),
]


class Issues(unittest.TestCase):
    def test_one_issue_per_rule(self):
        titles = [i["title"] for i in issues(ROWS, "https://run")]
        self.assertEqual(titles, [
            "rescan: demo 1.2.0: gitleaks: aws-access-token",
            "rescan: demo 1.2.0: gitleaks: github-pat",
            "rescan: demo 1.2.0: tree",
            "tag drift: demo v1.2.0",
        ])
        self.assertIn("settings.yml:3\ngitleaks: aws-access-token: other.yml:1", issues(ROWS, "u")[0]["body"])

    def test_finding_text_cannot_leave_the_fence(self):
        evil = "tree: symlink ````\n@someone [x](https://evil) " + chr(0x202E)
        body = issues([("rescan", "demo", "1.0.0", evil)], "u")[0]["body"]
        fence = body.split("\n")[2]
        self.assertGreater(len(fence), 4)
        self.assertTrue(fence.strip("`") == "")
        self.assertEqual(body.count(fence), 2)
        self.assertNotIn(chr(0x202E), body)

    def test_title_keeps_safe_characters_only(self):
        title = issues([("rescan", "demo", "1.0.0", "semgrep: x\"`@<b>: a.py:1")], "u")[0]["title"]
        self.assertEqual(title, "rescan: demo 1.0.0: semgrep: x????b?")


if __name__ == "__main__":
    unittest.main()
