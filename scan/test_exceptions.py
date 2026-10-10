import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exceptions import apply, key

TOKEN = b'KEY = "AKIA..."\n'
SHA = hashlib.sha256(TOKEN).hexdigest()


class Exceptions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tree = self.tmp.name
        with open(os.path.join(self.tree, "keys.py"), "wb") as f:
            f.write(TOKEN)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rule_ids(self):
        self.assertEqual(key("gitleaks: aws-access-token: keys.py:1"), ("gitleaks:aws-access-token", "keys.py"))
        self.assertEqual(key("semgrep: dynamic-code: a/b.py:7"), ("semgrep:dynamic-code", "a/b.py"))
        self.assertEqual(key("imports: x.py:2: import socket"), ("imports", "x.py"))
        self.assertEqual(key("template: t.j2: {{ x.__class__ }}"), ("template", "t.j2"))
        self.assertEqual(key("ruff: x.py:1:5: F821 Undefined name `y`"), ("ruff:F821", "x.py"))
        self.assertEqual(key("tree: executable run.sh"), ("tree:executable", "run.sh"))
        self.assertEqual(key("tree: banned file .gitattributes"), ("tree:banned", ".gitattributes"))
        self.assertEqual(key("tree: big.bin above 1 MiB"), ("tree:large", "big.bin"))
        for line in ("clamav: eicar.txt: Eicar-Signature FOUND", "guarddog: exec-base64: 1", "tree: symlink passwd",
                     "semgrep: error: Timeout: a.py", "gitleaks: error 2", "SEC-12: privileged: out.yml: []"):
            self.assertIsNone(key(line), line)

    def test_matching_exception_excepts_and_lists_it_first(self):
        lines = ["review: semgrep: getattr: a.py:3", "gitleaks: aws-access-token: keys.py:1"]
        out, failed = apply(lines, self.tree, [{"rule": "gitleaks:aws-access-token", "path": "keys.py", "sha256": SHA}], 1)
        self.assertFalse(failed)
        self.assertEqual(out[0], "excepted: gitleaks: aws-access-token: keys.py:1 (SEC-14)")

    def test_changed_file_lapses_the_exception(self):
        out, failed = apply(["gitleaks: aws-access-token: keys.py:1"], self.tree,
                            [{"rule": "gitleaks:aws-access-token", "path": "keys.py", "sha256": "0" * 64}], 1)
        self.assertTrue(failed)
        self.assertIn("lapsed", out[0])

    def test_other_rule_or_path_is_not_excepted(self):
        ex = [{"rule": "gitleaks:aws-access-token", "path": "keys.py", "sha256": SHA}]
        for line in ("gitleaks: github-pat: keys.py:1", "clamav: keys.py: X FOUND"):
            out, failed = apply([line], self.tree, ex, 1)
            self.assertTrue(failed, line)
            self.assertIn("warning: exception gitleaks:aws-access-token keys.py matched no finding", out)

    def test_symlink_and_escape_are_never_excepted(self):
        os.symlink(os.path.join(self.tree, "keys.py"), os.path.join(self.tree, "link.py"))
        for path in ("link.py", "../" + os.path.basename(self.tree) + "/keys.py"):
            _, failed = apply([f"gitleaks: aws-access-token: {path}:1"], self.tree,
                              [{"rule": "gitleaks:aws-access-token", "path": path, "sha256": SHA}], 1)
            self.assertTrue(failed, path)

    def test_failed_scan_without_findings_fails(self):
        self.assertTrue(apply([], self.tree, [], 1)[1])
        self.assertFalse(apply(["review: guarddog: x: 1"], self.tree, [], 0)[1])


if __name__ == "__main__":
    unittest.main()
