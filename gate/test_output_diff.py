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

    def run_diff(self, log=""):
        logfile, full = os.path.join(self.tmp.name, "log"), os.path.join(self.tmp.name, "output.diff")
        write(self.tmp.name, "log", log)
        out = subprocess.run([sys.executable, os.path.join(HERE, "output_diff.py"), "--old", self.old, "--new", self.new,
                              "--compile-log", logfile, "--full", full], capture_output=True, text=True, check=True).stdout
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


if __name__ == "__main__":
    unittest.main()
