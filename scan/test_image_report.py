import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
D = "@sha256:" + "a" * 64
# Fake trivy: logs each call, fails on a reference with "missing", reports two results otherwise.
TRIVY = """import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] == "version":
    print(json.dumps({"Version": "0.76.1", "VulnerabilityDB": {"UpdatedAt": "2026-10-29T07:17:11.934066875Z"}}))
elif "--download-db-only" in sys.argv:
    pass
elif "missing" in sys.argv[-1]:
    sys.exit("2026-10-29T04:30:00Z\\tFATAL\\tMANIFEST_UNKNOWN: manifest unknown")
elif "denied" in sys.argv[-1]:
    sys.exit("2026-10-29T04:30:00Z\\tFATAL\\tTOOMANYREQUESTS: rate limit")
else:
    v = lambda i, s: {"VulnerabilityID": i, "Severity": s, "PkgName": "openssl", "InstalledVersion": "3.0.1", "Title": "dropped"}
    print(json.dumps({"Metadata": {"RepoDigests": [sys.argv[-1].partition(":")[0] + "@sha256:" + "b" * 64]}, "Results": [{"Target": "os", "Vulnerabilities": [v("CVE-1", "HIGH"), dict(v("CVE-2", "LOW"), FixedVersion="3.0.2")]},
                                  {"Target": "go", "Vulnerabilities": [v("CVE-1", "HIGH")]}, {"Target": "none"}]}))
"""


class ImageReport(unittest.TestCase):
    """SEC-19: one scan per image, every vulnerability of every result, the digest scanned, errors recorded."""

    def test_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "bin"))
            fake = os.path.join(tmp, "bin", "trivy")
            with open(fake, "w", encoding="utf-8") as f:
                f.write(f"#!{sys.executable}\n" + TRIVY)
            os.chmod(fake, 0o755)
            images, out, log = (os.path.join(tmp, n) for n in ("images.tsv", "out.json", "log"))
            with open(images, "w", encoding="utf-8") as f:
                f.write(f"generators/kubevirt\t1.3.2\tghcr.io/a/b:1{D} quay.io/missing:1 quay.io/denied:1{D}\n"
                        f"recipes/cnpg\t1.0.1\tghcr.io/a/b:1{D}\n"
                        f"recipes/cnpg\tmain@{'c' * 40}\tghcr.io/a/b:1{D} registry.example/tagged:2\n"
                        "generators/talos\t1.2.0\t\n")
            env = dict(os.environ, PATH=os.path.join(tmp, "bin") + os.pathsep + os.environ["PATH"], FAKE_LOG=log)
            subprocess.run([sys.executable, "-I", os.path.join(HERE, "image_report.py"), images, out], env=env, check=True)
            with open(out, encoding="utf-8") as f:
                report = json.load(f)
            with open(log, encoding="utf-8") as f:
                calls = f.read().splitlines()
        self.assertEqual(report["pages"], {"generators/kubevirt": {"1.3.2": [f"ghcr.io/a/b:1{D}", "quay.io/missing:1", f"quay.io/denied:1{D}"]},
                                           "recipes/cnpg": {"1.0.1": [f"ghcr.io/a/b:1{D}"], f"main@{'c' * 40}": [f"ghcr.io/a/b:1{D}", "registry.example/tagged:2"]},
                                           "generators/talos": {"1.2.0": []}})
        self.assertEqual((report["trivy"], report["db"]), ("0.76.1", "2026-10-29T07:17:11Z"))
        self.assertRegex(report["scanned"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        row = {"id": "CVE-1", "severity": "HIGH", "package": "openssl", "installed": "3.0.1", "fixed": ""}
        rows = [row, dict(row, id="CVE-2", severity="LOW", fixed="3.0.2"), row]
        self.assertEqual(report["images"], {
            f"ghcr.io/a/b:1{D}": {"digest": "sha256:" + "b" * 64, "vulnerabilities": rows},
            "registry.example/tagged:2": {"digest": "sha256:" + "b" * 64, "vulnerabilities": rows},  # the tag's digest at scan time
            "quay.io/missing:1": {"error": "2026-10-29T04:30:00Z\tFATAL\tMANIFEST_UNKNOWN: manifest unknown", "missing": True},
            f"quay.io/denied:1{D}": {"error": "2026-10-29T04:30:00Z\tFATAL\tTOOMANYREQUESTS: rate limit", "missing": False}})
        self.assertEqual(calls[0], "image --quiet --download-db-only")  # one database for every image
        self.assertEqual(sum(c.endswith(f"ghcr.io/a/b:1{D}") for c in calls), 1)
        self.assertIn(f"image --quiet --skip-db-update --scanners vuln --image-src remote --timeout 15m --format json ghcr.io/a/b:1{D}", calls)


if __name__ == "__main__":
    unittest.main()
