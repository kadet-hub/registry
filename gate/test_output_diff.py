import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class OutputDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old, self.new = os.path.join(self.tmp.name, "old"), os.path.join(self.tmp.name, "new")
        write(self.old, "compiled/t/a.yml", "kind: ConfigMap\n")
        write(self.old, "compiled/t/z.yml", "kind: Service\nport: 80\n")
        write(self.new, "compiled/t/a.yml", "kind: ConfigMap\n")
        write(self.new, "compiled/t/z.yml", "kind: Service\nport: 8080\n")
        write(self.new, "compiled/t/ds.yml", "kind: DaemonSet\nhostPath: /\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_diff(self, log="", extra=()):
        logfile, full = os.path.join(self.tmp.name, "log"), os.path.join(self.tmp.name, "output.diff")
        write(self.tmp.name, "log", log)
        out = subprocess.run([sys.executable, os.path.join(HERE, "output_diff.py"), "--old", self.old, "--new", self.new,
                              "--compile-log", logfile, "--full", full, *extra], capture_output=True, text=True, check=True).stdout
        with open(full, encoding="utf-8") as f:
            return out, f.read()

    def test_size_in_files_and_hunks(self):
        out, full = self.run_diff()
        self.assertIn("2 files, 2 hunks", out.splitlines()[0])
        self.assertNotIn("a.yml", full)
        self.assertLess(full.index("b/compiled/t/ds.yml"), full.index("b/compiled/t/z.yml"))

    def test_sec12_matches_first(self):
        out, full = self.run_diff('SEC-12: declared host-path: compiled/t/z.yml: ["x"]\n')
        self.assertIn("SEC-12 matches first: compiled/t/z.yml", out)
        self.assertLess(full.index("b/compiled/t/z.yml"), full.index("b/compiled/t/ds.yml"))

    def test_report_is_cut_and_full_diff_kept(self):
        write(self.new, "compiled/t/big.yml", "".join(f"line {i} {'x' * 300}\n" for i in range(400)))
        out, full = self.run_diff()
        self.assertLessEqual(len(out.splitlines()), 153)
        self.assertIn("[cut]", out)
        self.assertIn("more lines in output.diff", out)
        self.assertIn("line 399", full)

    def test_summary_and_cut_for_the_release(self):  # PUB-9
        write(self.new, "compiled/t/big.yml", "".join(f"é {i}\n" for i in range(400)))
        summary = os.path.join(self.tmp.name, "summary.json")
        self.run_diff(extra=("--max-bytes", "1000", "--json", summary))
        with open(os.path.join(self.tmp.name, "output.diff"), "rb") as f:
            data = f.read()
        with open(summary, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"files": 3, "hunks": 3, "sha256": hashlib.sha256(data).hexdigest()})
        self.assertLessEqual(len(data), 1000)
        kept, mark = data.decode().rsplit("\n", 2)[0], data.decode().splitlines()[-1]
        self.assertEqual(mark, "... output diff truncated at 1000 bytes")
        self.assertRegex(kept, r"\n\+é \d+$")  # whole lines only


    def test_recipe_before_and_after(self):  # REC-10
        digest = "sha256:" + "a" * 64
        old = {"source": ["Source: `oci://ghcr.io/x/valkey:0.11.0@sha256:1`"], "level": ["Level: `deploys`"],
               "pins": [f"ghcr.io/kadet-hub/kubernetes:1.8.0@{digest}"], "included": ["valkey"],
               "recipes": {"valkey": {"rule": "REC-16", "version": "1.0.0", "digest": digest}}}
        new = {**old, "source": ["Source: `oci://ghcr.io/x/valkey:0.12.0@sha256:2`"],
               "pins": [f"ghcr.io/kadet-hub/kubernetes:1.9.0@{digest}"], "included": ["valkey", "postgresql"],
               "recipes": {"valkey": {"rule": "REC-16", "version": "1.1.0", "digest": digest}}}
        for name, data in (("old.json", old), ("new.json", new)):
            write(self.tmp.name, name, json.dumps(data))
        write(self.tmp.name, "old.log", "## Static checks\nSEC-12: unparsed output compiled/t/x (*)\n")
        log = "SEC-12: admission-webhook: compiled/t/z.yml: ValidatingWebhookConfiguration x\n"
        out, _ = self.run_diff(log, ("--recipe", os.path.join(self.tmp.name, "old.json"), os.path.join(self.tmp.name, "new.json"),
                                     "--old-compile-log", os.path.join(self.tmp.name, "old.log")))
        section = out[out.index("### Before and after (REC-10)\n"):].splitlines()[1:]
        self.assertEqual(section, [
            "chart or manifest source:", "- Source: `oci://ghcr.io/x/valkey:0.11.0@sha256:1`",
            "+ Source: `oci://ghcr.io/x/valkey:0.12.0@sha256:2`",
            "level:", "  Level: `deploys`",
            "generator pins:", f"- ghcr.io/kadet-hub/kubernetes:1.8.0@{digest}", f"+ ghcr.io/kadet-hub/kubernetes:1.9.0@{digest}",
            "included recipes:", f"- valkey 1.0.0 {digest}", f"+ valkey 1.1.0 {digest}", "+ postgresql, no published version",
            "SEC-12 matches:", "+ SEC-12: admission-webhook: compiled/t/z.yml: ValidatingWebhookConfiguration x"])
        self.assertNotIn("Before and after", self.run_diff(log)[0])
        out, _ = self.run_diff("", ("--recipe", os.path.join(self.tmp.name, "old.json"), os.path.join(self.tmp.name, "old.json"),
                                    "--old-compile-log", os.path.join(self.tmp.name, "old.log")))
        self.assertIn("SEC-12 matches:\n  none", out)

if __name__ == "__main__":
    unittest.main()
