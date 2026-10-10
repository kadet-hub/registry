import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from index import build
from tree import read_dir, read_tar, tree_id, write_tar

GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"]}


def git_tree(path):
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"]):
        subprocess.run(cmd, cwd=path, check=True, env=GIT_ENV)
    return subprocess.run(["git", "write-tree"], cwd=path, check=True, env=GIT_ENV,
                          capture_output=True, text=True).stdout.strip()


def make_tree(path, executable=False):
    files = {"kapitan-generator.yaml": "name: x\n", "lib/b.py": "b = 1\n", "lib-a.py": "a\n", "lib/sub/c.j2": "{{ x }}\n"}
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(path, rel)), exist_ok=True)
        with open(os.path.join(path, rel), "w") as f:
            f.write(text)
    if executable:
        os.chmod(os.path.join(path, "lib/b.py"), 0o755)


class Tree(unittest.TestCase):
    def test_tar_is_reproducible_and_matches_git(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            make_tree(src)
            files = read_dir(src)
            write_tar(files, os.path.join(d, "a.tar"))
            write_tar(dict(reversed(list(files.items()))), os.path.join(d, "b.tar"))
            with open(os.path.join(d, "a.tar"), "rb") as a, open(os.path.join(d, "b.tar"), "rb") as b:
                self.assertEqual(a.read(), b.read())
            expected = git_tree(src)
            self.assertEqual(tree_id(files), expected)
            self.assertEqual(tree_id(read_tar(os.path.join(d, "a.tar"))), expected)

    def test_executable_source_fails_the_tree_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            make_tree(src, executable=True)
            write_tar(read_dir(src), os.path.join(d, "a.tar"))
            self.assertNotEqual(tree_id(read_tar(os.path.join(d, "a.tar"))), git_tree(src))


NOW, LATER = "2026-10-09T00:00:00Z", "2026-10-10T00:00:00Z"


def version(name, v, digest="sha256:" + "a" * 64):
    return {"digest": digest, "meta": {"name": name, "version": v, "tree": "t", "license": "MIT"}}


class Index(unittest.TestCase):
    def test_yanked_and_removed(self):
        index = build([version("gen", "1.0.0"), version("gen", "1.1.0"), version("old", "0.1.0")],
                      {"gen": {"yanked": {"1.0.0": "broken"}}}, None, NOW)
        gens = index["generators"]
        self.assertEqual(index["serial"], 1)
        self.assertEqual(gens["gen"]["1.0.0"]["yanked"], "broken")
        self.assertIsNone(gens["gen"]["1.1.0"]["yanked"])
        self.assertEqual(gens["old"]["0.1.0"]["yanked"], "entry removed")
        self.assertEqual(gens["gen"]["1.1.0"]["digest"], "sha256:" + "a" * 64)
        self.assertEqual(gens["gen"]["1.1.0"]["advisories"], [])

    def test_serial_increases_only_on_change(self):
        entries = {"gen": {}}
        first = build([version("gen", "1.0.0")], entries, None, NOW)
        self.assertIsNone(build([version("gen", "1.0.0")], entries, first, LATER))
        second = build([version("gen", "1.0.0")], {"gen": {"yanked": {"1.0.0": "x"}}}, first, LATER)
        self.assertEqual(second["serial"], 2)

    def test_published_is_kept_from_the_previous_index(self):
        first = build([version("gen", "1.0.0")], {"gen": {}}, None, NOW)
        second = build([version("gen", "1.0.0"), version("gen", "1.1.0")], {"gen": {}}, first, LATER)
        self.assertEqual(second["generators"]["gen"]["1.0.0"]["published"], NOW)
        self.assertEqual(second["generators"]["gen"]["1.1.0"]["published"], LATER)

    def test_deleted_yanked_version_stays_with_its_advisory(self):
        entries = {"gen": {"yanked": {"1.0.0": "malicious"}, "advisories": {"1.0.0": ["GHSA-2345-6789-cfgh"]}}}
        first = build([version("gen", "1.0.0"), version("gen", "1.1.0")], entries, None, NOW)
        self.assertEqual(first["generators"]["gen"]["1.0.0"]["advisories"], ["GHSA-2345-6789-cfgh"])
        second = build([version("gen", "1.1.0")], entries, first, LATER)
        self.assertIsNone(second)
        kept = build([version("gen", "1.1.0")], {"gen": {"yanked": {"1.0.0": "malicious, see advisory"},
                                                         "advisories": entries["gen"]["advisories"]}}, first, LATER)
        record = kept["generators"]["gen"]["1.0.0"]
        self.assertEqual((record["digest"], record["yanked"], record["advisories"], record["published"]),
                         ("sha256:" + "a" * 64, "malicious, see advisory", ["GHSA-2345-6789-cfgh"], NOW))

    def test_deleted_version_that_is_not_yanked_is_dropped(self):
        first = build([version("gen", "1.0.0")], {"gen": {}}, None, NOW)
        self.assertEqual(build([], {"gen": {}}, first, LATER)["generators"], {})


if __name__ == "__main__":
    unittest.main()
