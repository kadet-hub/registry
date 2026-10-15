import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tag_check import check, kinds


def tree(files):
    tmp = tempfile.TemporaryDirectory()
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(tmp.name, rel)), exist_ok=True)
        with open(os.path.join(tmp.name, rel), "w", encoding="utf-8") as f:
            f.write(text)
    return tmp


class TagCheck(unittest.TestCase):
    def test_verifiable_tags_need_evidence(self):
        with tree({"compiled/minimal/cm.yml": "apiVersion: v1\nkind: ConfigMap\n"}) as out:
            findings, lines = check({"tags": ["kubernetes", "terraform", "helm"]}, out)
        self.assertEqual(findings, ["QA-6: tag terraform: no *.tf.json or *.tf file in the compiled output",
                                    "QA-6: tag helm: no chart in the manifest and no helm template in binaries"])
        self.assertIn("QA-6: tag kubernetes: compiled/minimal/cm.yml", lines)

    def test_evidence_from_output_and_manifest(self):
        with tree({"compiled/a/main.tf.json": "{}", "compiled/a/list.json": '{"items": [], "apiVersion": "v1", "kind": "List"}'}) as out:
            findings, _ = check({"tags": ["terraform", "kubernetes", "helm"], "binaries": ["helm template"]}, out)
            self.assertEqual(findings, [])
            findings, _ = check({"tags": ["helm"], "charts": [{"name": "podinfo"}]}, out)
            self.assertEqual(findings, [])

    def test_documents_without_kind_are_no_evidence(self):
        with tree({"compiled/a/values.yml": "apiVersion: v1\nreplicas: 2\n", "compiled/a/bad.yml": ": [\n"}) as out:
            findings, _ = check({"tags": ["kubernetes"]}, out)
        self.assertEqual(len(findings), 1)

    def test_purpose_tags_go_to_review_and_missing_tags_are_suggested(self):
        with tree({"compiled/minimal/cm.yaml": "---\napiVersion: v1\nkind: ConfigMap\n"}) as out:
            findings, lines = check({"tags": ["security"]}, out)
        self.assertEqual(findings, [])
        self.assertIn("review: tag security: check it against /tags/#security", lines)
        self.assertIn("review: tag kubernetes is not set, but the generator shows it: compiled/minimal/cm.yaml", lines)

    def test_kinds_of_the_output(self):  # PUB-10
        with tree({"compiled/minimal/a.yml": "apiVersion: v1\nkind: ConfigMap\n---\napiVersion: gateway.networking.k8s.io/v1\nkind: HTTPRoute\n",
                   "compiled/complete/a.yml": "apiVersion: v1\nkind: ConfigMap\n",
                   "compiled/complete/list.json": '{"items": [], "apiVersion": "v1", "kind": "List"}',
                   "compiled/complete/items.yaml": "- apiVersion: apps/v1\n  kind: Deployment\n",
                   "compiled/talos/bond.yaml": "apiVersion: v1alpha1\nkind: BondConfig\n",
                   "compiled/complete/values.yml": "apiVersion: v1\nreplicas: 2\n", "compiled/complete/bad.yml": ": [\n",
                   "compiled/complete/main.tf.json": '{"resource": {"aws_s3_bucket": {}}}'}) as out:
            expected = [{"group": "", "version": "v1", "kind": "ConfigMap"}, {"group": "", "version": "v1", "kind": "List"},
                        {"group": "", "version": "v1alpha1", "kind": "BondConfig"}, {"group": "apps", "version": "v1", "kind": "Deployment"},
                        {"group": "gateway.networking.k8s.io", "version": "v1", "kind": "HTTPRoute"}]
            self.assertEqual(kinds(out), expected)
            result = os.path.join(out, "kinds.json")
            with open(os.path.join(out, "manifest.yaml"), "w", encoding="utf-8") as f:
                f.write("tags: [kubernetes]\n")
            p = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_check.py"),
                                "--manifest", os.path.join(out, "manifest.yaml"), "--out", os.path.join(out, "compiled"), "--kinds", result],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout)
            with open(result, encoding="utf-8") as f:
                self.assertEqual(json.load(f), expected)


if __name__ == "__main__":
    unittest.main()
