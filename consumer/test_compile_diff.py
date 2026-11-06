import os
import re
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compile_diff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class Diff(unittest.TestCase):  # CD-3
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base, self.head, self.out = (os.path.join(self.tmp.name, n) for n in ("base", "head", "out"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_diff(self, glob="*"):
        n = compile_diff.diff(self.base, self.head, self.out, glob)
        diffs = {}
        for f in sorted(os.listdir(self.out)):
            if f.endswith(".diff"):
                with open(os.path.join(self.out, f)) as fh:
                    diffs[f[:-5]] = fh.read()
        return n, diffs

    def test_marker_without_changes(self):  # CD-10
        write(f"{self.base}/dev/a.yml", b"same\n")
        write(f"{self.head}/dev/a.yml", b"same\n")
        self.assertEqual(compile_diff.diff(self.base, self.head, self.out, "*"), 0)
        self.assertEqual(os.listdir(self.out), ["compile-diff.txt"])

    def test_changed_added_removed_and_unchanged(self):
        write(f"{self.base}/dev/apps/web.yml", b"kind: Deployment\nspec:\n  replicas: 1\n")
        write(f"{self.head}/dev/apps/web.yml", b"kind: Deployment\nspec:\n  replicas: 2\n")
        write(f"{self.base}/dev/apps/old.yml", b"a: 1\n")
        write(f"{self.head}/dev/apps/new.yml", b"b: 2\n")
        write(f"{self.base}/prod/apps/web.yml", b"same\n")
        write(f"{self.head}/prod/apps/web.yml", b"same\n")
        n, diffs = self.run_diff()
        self.assertEqual(n, 1)
        self.assertEqual(list(diffs), ["dev"])
        d = diffs["dev"]
        self.assertIn("--- a/dev/apps/web.yml\n+++ b/dev/apps/web.yml\n", d)
        self.assertIn("\n-  replicas: 1\n+  replicas: 2\n", d)
        self.assertIn("--- /dev/null\n+++ b/dev/apps/new.yml\n@@ -0,0 +1 @@\n+b: 2\n", d)
        self.assertIn("--- a/dev/apps/old.yml\n+++ /dev/null\n", d)
        self.assertEqual(compile_diff.file_list(d), ["A dev/apps/new.yml", "D dev/apps/old.yml", "M dev/apps/web.yml"])

    def test_ref_hash_change_is_a_diff(self):
        write(f"{self.base}/dev/secret.yml", b"password: ?{gpg:db/password:3f2a8c1e}\n")
        write(f"{self.head}/dev/secret.yml", b"password: ?{gpg:db/password:9b0d7e44}\n")
        _, diffs = self.run_diff()
        self.assertIn("+password: ?{gpg:db/password:9b0d7e44}\n", diffs["dev"])

    def test_glob_filters_targets(self):
        for t in ("dev", "prod"):
            write(f"{self.head}/{t}/x.yml", b"x\n")
        n, diffs = self.run_diff("pro*")
        self.assertEqual((n, list(diffs)), (1, ["prod"]))

    def test_binary_and_missing_newline(self):
        write(f"{self.base}/dev/blob", b"\0\1")
        write(f"{self.head}/dev/blob", b"\0\2")
        write(f"{self.base}/dev/a.txt", b"x")
        write(f"{self.head}/dev/a.txt", b"x\n")
        _, diffs = self.run_diff()
        self.assertIn("+++ b/dev/blob\nBinary files differ\n", diffs["dev"])
        self.assertIn("-x\n\\ No newline at end of file\n+x\n", diffs["dev"])

    def test_symlink_is_not_followed(self):
        secret = os.path.join(self.tmp.name, "secret")
        write(secret, b"host secret\n")
        os.makedirs(f"{self.head}/dev")
        os.symlink(secret, f"{self.head}/dev/link")
        _, diffs = self.run_diff()
        self.assertNotIn("host secret", diffs["dev"])
        self.assertIn(f"+symlink to {secret}\n", diffs["dev"])


class Render(unittest.TestCase):  # CD-7, CD-9, CD-11
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        write(os.path.join(self.dir, "compile-diff.txt"), b"0 targets changed\n")

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, conclusion="success"):
        return compile_diff.render(self.dir, conclusion, "3f0c2a1" + "0" * 33, "https://github.com/o/r/actions/runs/1")

    def diff(self, target, text):
        write(os.path.join(self.dir, target + ".diff"), text.encode())

    def test_summary_details_and_files(self):
        self.diff("dev", "diff --git a/dev/w.yml b/dev/w.yml\n--- a/dev/w.yml\n+++ b/dev/w.yml\n@@ -1 +1 @@\n-  replicas: 1\n+  replicas: 2\n")
        body = self.render()
        self.assertTrue(body.startswith(compile_diff.MARKER + "\n**compile diff: 1 target changed, 1 file** at `3f0c2a1`."))
        self.assertIn("<details><summary>dev: 1 file</summary>\n\n```diff\nM dev/w.yml\n\n", body)
        self.assertIn("+  replicas: 2\n```\n", body)

    def test_hostile_artifact_stays_text(self):
        text = "+@someone <img src=x> [x](https://example.org) \u202eevil\u202c ü\n+``````\n+</details>\n"
        self.diff("x<b>y", text)
        write(os.path.join(self.dir, "notes.md"), b"**injected**")
        os.symlink("/etc/passwd", os.path.join(self.dir, "link.diff"))
        body = self.render()
        self.assertNotIn("injected", body)
        self.assertNotIn("root:", body)
        self.assertIn("<summary>x?b?y: 0 files</summary>", body)
        self.assertTrue(body.isascii())
        self.assertIn(" ?evil? ?", body)
        fence = re.search(r"\n(`+)diff\n", body).group(1)
        self.assertEqual(len(fence), 7)
        inside = body.split(fence + "diff\n", 1)[1].split("\n" + fence + "\n", 1)[0]
        self.assertIn("</details>", inside)
        self.assertIn("@someone", inside)

    def test_limit_with_one_large_target(self):
        lines = "".join(f"+line {i} " + "x" * 80 + "\n" for i in range(5000))
        self.diff("dev", "diff --git a/dev/a b/dev/a\n--- /dev/null\n+++ b/dev/a\n" + lines)
        body = self.render()
        self.assertLessEqual(len(body), compile_diff.LIMIT)
        self.assertGreater(len(body), compile_diff.LIMIT - 1000)
        self.assertRegex(body, r"Cut after \d+ of 5005 lines; the artifact holds the full diff\.")
        self.assertIn("A dev/a\n", body)

    def test_limit_with_many_targets(self):
        for i in range(400):
            self.diff(f"t{i:03}", "diff --git a/f b/f\n--- a/f\n+++ b/f\n" + "+" + "y" * 500 + "\n")
        body = self.render()
        self.assertLessEqual(len(body), compile_diff.LIMIT)
        self.assertIn("**compile diff: 400 targets changed, 400 files**", body)
        self.assertRegex(body, r"\d+ more targets changed; see the artifact\.")

    def test_small_target_leaves_room_to_a_large_one(self):
        self.diff("a", "diff --git a/a/f b/a/f\n--- a/a/f\n+++ b/a/f\n" + "+z\n" * 40000)
        self.diff("b", "diff --git a/b/f b/b/f\n--- a/b/f\n+++ b/b/f\n+small\n")
        body = self.render()
        self.assertLessEqual(len(body), compile_diff.LIMIT)
        self.assertGreater(len(body), compile_diff.LIMIT - 1000)
        self.assertLess(body.index("<summary>a:"), body.index("<summary>b:"))
        self.assertIn("+small\n", body)

    def test_no_change_and_failed_run(self):
        self.assertIn("**compile diff: no change** in `compiled/` at `3f0c2a1`", self.render())
        self.diff("dev", "+x\n")
        failed = self.render("failure")
        self.assertIn("**compile diff: no result** at `3f0c2a1`: the compile [run](https://github.com/o/r/actions/runs/1) ended with failure.", failed)
        self.assertNotIn("+x", failed)

    def exit_code(self, conclusion="success"):
        with open(os.devnull, "w") as null, unittest.mock.patch("sys.stdout", null), self.assertRaises(SystemExit) as e:
            compile_diff.main(["compile_diff.py", "render", self.dir, conclusion, "0" * 40, "https://github.com/o/r/actions/runs/1"])
        return e.exception.code

    def test_missing_marker(self):
        self.assertEqual(self.exit_code(), 0)
        os.remove(os.path.join(self.dir, "compile-diff.txt"))
        self.diff("dev", "+x\n")
        body = self.render()
        self.assertIn("**compile diff: no result** at `3f0c2a1`: the artifact `compile-diff` of the [run]", body)
        self.assertIn("is missing or could not be downloaded", body)
        self.assertNotIn("no change", body)
        self.assertNotIn("+x", body)
        self.assertEqual(self.exit_code(), 1)
        self.assertEqual(self.exit_code("failure"), 0)


class NoReveal(unittest.TestCase):  # CD-2
    def test_no_reveal_in_the_compile_path(self):
        for path in ("consumer/run", "sandbox/run", ".github/actions/compile-diff/action.yml"):
            with open(os.path.join(ROOT, path)) as f:
                self.assertNotIn("--reveal", f.read(), path)


if __name__ == "__main__":
    unittest.main()
