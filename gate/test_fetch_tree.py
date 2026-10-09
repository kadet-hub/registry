import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args, cwd):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class FetchTree(unittest.TestCase):
    def test_writes_tree_and_reports_links(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            os.makedirs(os.path.join(repo, "gen", "sub"))
            with open(os.path.join(repo, "gen", "a.py"), "w") as f:
                f.write("x = 1\n")
            with open(os.path.join(repo, "gen", "sub", "run.sh"), "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(os.path.join(repo, "gen", "sub", "run.sh"), 0o755)
            with open(os.path.join(repo, "gen", ".gitattributes"), "w") as f:
                f.write("* export-subst\n")
            os.symlink("/etc/passwd", os.path.join(repo, "gen", "link"))
            env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"]}
            for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "t"]):
                subprocess.run(cmd, cwd=repo, check=True, env=env)
            sha = run("git", "rev-parse", "HEAD", cwd=repo)
            out = os.path.join(d, "out")
            r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_tree.py"), "--git-dir", os.path.join(repo, ".git"),
                                "--rev", sha, "--path", "gen", "--out", out], capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 1)
            self.assertIn("tree: symlink link", r.stdout)
            self.assertFalse(os.path.lexists(os.path.join(out, "link")))
            with open(os.path.join(out, "a.py")) as f:
                self.assertEqual(f.read(), "x = 1\n")
            self.assertTrue(os.stat(os.path.join(out, "sub", "run.sh")).st_mode & 0o111)
            self.assertTrue(os.path.exists(os.path.join(out, ".gitattributes")))

    def test_missing_path_fails(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_tree.py"), "--git-dir", os.path.join(d, ".git"),
                                "--rev", "0" * 40, "--path", "x", "--out", os.path.join(d, "o")], capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
