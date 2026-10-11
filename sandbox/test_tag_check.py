import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tag_check import check


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


if __name__ == "__main__":
    unittest.main()
