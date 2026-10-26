import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "release"))
from tree import read_dir, tree_id  # noqa: E402


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

    def test_recipe_reads_only_its_tests_files(self):  # REC-4
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            files = {"demo/init.yml": "classes: []\n", "demo/vendor/crds.yaml": "kind: CRD\n", "demo/tests/target.yml": "t\n",
                     "demo/tests/values.yaml": "v\n", "demo/tests/smoke": "#!/bin/sh\n", "demo/tests/kind.yaml": "k\n",
                     "other/init.yml": "classes: []\n", "other/tests/target.yml": "t\n", "docs/README.md": "d\n", "check/lint.py": "x = 1\n",
                     "docs/sub/tests/target.yml": "t\n"}
            for rel, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
                with open(os.path.join(repo, rel), "w") as f:
                    f.write(text)
            os.chmod(os.path.join(repo, "demo/tests/smoke"), 0o755)
            env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"]}
            for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "t"]):
                subprocess.run(cmd, cwd=repo, check=True, env=env)
            sha = run("git", "rev-parse", "HEAD", cwd=repo)
            out = os.path.join(d, "out")
            fetch = [sys.executable, os.path.join(HERE, "fetch_tree.py"), "--git-dir", os.path.join(repo, ".git"), "--rev", sha]
            subprocess.run([*fetch, "--recipe", "demo", "--out", out], check=True)
            written = sorted(os.path.relpath(os.path.join(r, f), out) for r, _, fs in os.walk(out) for f in fs)
            self.assertEqual(written, ["demo/init.yml", "demo/tests/smoke", "demo/tests/target.yml", "demo/tests/values.yaml",
                                       "demo/vendor/crds.yaml", "other/init.yml"])
            self.assertEqual(os.path.getsize(os.path.join(out, "demo/tests/smoke")), 0)
            self.assertFalse(os.stat(os.path.join(out, "demo/tests/smoke")).st_mode & 0o111)
            r = subprocess.run([*fetch, "--recipe", "missing", "--out", os.path.join(d, "o")], capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 1)
            # REC-4, REC-8: --targets reads tests/target.yml of the named recipes and nothing else.
            targets = os.path.join(d, "targets")
            subprocess.run([*fetch, "--targets", "other", "demo", "--out", targets], check=True)
            written = sorted(os.path.relpath(os.path.join(r, f), targets) for r, _, fs in os.walk(targets) for f in fs)
            self.assertEqual(written, ["demo/tests/target.yml", "other/tests/target.yml"])
            for names in (["docs"], ["other", "missing"], ["../demo"], ["demo/tests"], ["docs/sub"]):
                r = subprocess.run([*fetch, "--targets", *names, "--out", os.path.join(d, "t")], capture_output=True, text=True, check=False)
                self.assertEqual(r.returncode, 1, names)
            self.assertFalse(os.path.exists(os.path.join(d, "t")))

    def test_recipe_tree_without_tests(self):  # REC-16
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            files = {"demo/init.yml": "classes: [recipes.other]\n", "demo/tests/target.yml": "t\n", "other/init.yml": "classes: []\n",
                     "other/README.md": "# other\n", "other/vendor/crds.yaml": "kind: CRD\n", "other/tests/target.yml": "t\n"}
            for rel, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
                with open(os.path.join(repo, rel), "w") as f:
                    f.write(text)
            env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"]}
            for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "t"]):
                subprocess.run(cmd, cwd=repo, check=True, env=env)
            sha = run("git", "rev-parse", "HEAD", cwd=repo)
            # REC-11: the tree git mktree writes for the listing of sha:other without its tests entry.
            listing = run("git", "ls-tree", f"{sha}:other", cwd=repo).splitlines()
            shipped = subprocess.run(["git", "mktree"], cwd=repo, check=True, capture_output=True, text=True,
                                     input="".join(f"{ln}\n" for ln in listing if not ln.endswith("\ttests"))).stdout.strip()
            out = os.path.join(d, "out")
            subprocess.run([sys.executable, os.path.join(HERE, "fetch_tree.py"), "--git-dir", os.path.join(repo, ".git"),
                            "--rev", sha, "--recipe", "demo", "--out", out], check=True)
            self.assertEqual(tree_id(read_dir(os.path.join(out, "other"))), shipped)
            self.assertNotEqual(shipped, run("git", "rev-parse", f"{sha}:other", cwd=repo))

    def test_missing_path_fails(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_tree.py"), "--git-dir", os.path.join(d, ".git"),
                                "--rev", "0" * 40, "--path", "x", "--out", os.path.join(d, "o")], capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
