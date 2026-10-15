import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tempfile

from schema_diff import diff, sources


class SchemaDiff(unittest.TestCase):
    def test_versions_before_and_after(self):
        old = {"keda.sh": {"software": "KEDA", "version": "2.21.0"}, "core": {"software": "Kubernetes", "version": "1.35"}}
        new = {"keda.sh": {"software": "KEDA", "version": "2.22.0"}, "core": {"software": "Kubernetes", "version": "1.35"},
               "apps": {"software": "Kubernetes", "version": "1.35"}}
        self.assertEqual(diff(old, new), [
            "QA-7: schemas apps: none -> Kubernetes 1.35",
            "QA-7: schemas core: Kubernetes 1.35 -> Kubernetes 1.35 (unchanged)",
            "QA-7: schemas keda.sh: KEDA 2.21.0 -> KEDA 2.22.0",
        ])

    def test_terraform_providers_are_qa8(self):
        new = {"terraform/hashicorp/aws": {"software": "hashicorp/aws", "version": "6.68.0"}}
        self.assertEqual(diff({}, new), ["QA-8: schemas terraform/hashicorp/aws: none -> hashicorp/aws 6.68.0"])

    def test_no_schemas_no_lines(self):
        self.assertEqual(diff({}, {}), [])

    def test_malformed_files_have_no_sources(self):  # GI-14
        for manifest, src in ((b"- schemas\n", b"core: {}\n"), (b"schemas: s\n", b"- core\n"), (b"schemas: s\n", b"core: \xff\n")):
            with tempfile.TemporaryDirectory() as tree:
                os.makedirs(os.path.join(tree, "s"))
                for rel, data in (("kapitan-generator.yaml", manifest), ("s/sources.yaml", src)):
                    with open(os.path.join(tree, rel), "wb") as f:
                        f.write(data)
                self.assertEqual(sources(tree), {})


if __name__ == "__main__":
    unittest.main()
