import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_diff import diff


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

    def test_no_schemas_no_lines(self):
        self.assertEqual(diff({}, {}), [])


if __name__ == "__main__":
    unittest.main()
