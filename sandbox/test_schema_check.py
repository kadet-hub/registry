import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_check import check

CM = {"type": "object", "required": ["data"], "properties": {"data": {"type": "object", "additionalProperties": {"type": "string"}}}}
SOURCES = "core:\n  software: Kubernetes\n  version: '1.35'\n  source: https://example.org/k8s\n"


def tree(files):
    tmp = tempfile.TemporaryDirectory()
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(tmp.name, rel)), exist_ok=True)
        with open(os.path.join(tmp.name, rel), "w", encoding="utf-8") as f:
            f.write(text if isinstance(text, str) else json.dumps(text))
    return tmp


class SchemaCheck(unittest.TestCase):
    def run_check(self, output, sources=SOURCES, schemas=None):
        files = {"schemas/core/configmap_v1.json": CM, **(schemas or {})}
        if sources is not None:
            files["schemas/sources.yaml"] = sources
        files.update({f"out/{k}": v for k, v in output.items()})
        with tree(files) as root:
            return check(os.path.join(root, "schemas"), os.path.join(root, "out"))

    def test_valid_output_names_the_software(self):
        findings, lines, result = self.run_check({"a/cm.yml": "apiVersion: v1\nkind: ConfigMap\ndata: {a: b}\n"})
        self.assertEqual(findings, [])
        self.assertEqual(result, [{"software": "Kubernetes", "version": "1.35", "source": "https://example.org/k8s"}])
        self.assertIn("QA-7: validated against Kubernetes 1.35", lines)

    def test_invalid_output_fails(self):
        findings, _, _ = self.run_check({"a/cm.yml": "apiVersion: v1\nkind: ConfigMap\ndata: {a: 1}\n"})
        self.assertEqual(findings, ["QA-7: a/cm.yml: ConfigMap data/a: 1 is not of type 'string'"])

    def test_unicode_property_pattern(self):
        log = {"type": "object", "properties": {"value": {"type": "string", "pattern": "^\\PC*$"}}}
        schemas = {"schemas/core/configmap_v1.json": dict(CM, properties=dict(CM["properties"], log=log))}
        ok = "apiVersion: v1\nkind: ConfigMap\ndata: {}\nlog: {value: audit}\n"
        bad = "apiVersion: v1\nkind: ConfigMap\ndata: {}\nlog: {value: \"a\\x07\"}\n"
        self.assertEqual(self.run_check({"a/cm.yml": ok}, schemas=schemas)[0], [])
        findings = self.run_check({"a/cm.yml": bad}, schemas=schemas)[0]
        self.assertEqual(len(findings), 1)
        self.assertIn("QA-7: a/cm.yml: ConfigMap log/value: ", findings[0])

    def test_group_version_entry_takes_precedence(self):
        talos = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
        sources = SOURCES + "core/v1alpha1:\n  software: Talos\n  version: 1.14.2\n  source: https://example.org/talos\n"
        output = {"a/cm.yml": "apiVersion: v1\nkind: ConfigMap\ndata: {}\n---\napiVersion: v1alpha1\nkind: HostnameConfig\nname: n1\n"}
        findings, lines, result = self.run_check(output, sources=sources, schemas={"schemas/core/hostnameconfig_v1alpha1.json": talos})
        self.assertEqual(findings, [])
        self.assertEqual([r["software"] for r in result], ["Kubernetes", "Talos"])
        self.assertIn("QA-7: validated against Talos 1.14.2", lines)

    def test_kind_without_schema_is_review(self):
        findings, lines, result = self.run_check({"a/s.yml": "apiVersion: apps/v1\nkind: Deployment\n---\napiVersion: apps/v1\nkind: Deployment\n"})
        self.assertEqual((findings, result), ([], []))
        self.assertEqual(lines, ["review: a/s.yml: no schema for apps/v1 Deployment"])

    def test_group_without_source_entry_fails(self):
        findings, _, _ = self.run_check({"a/cm.yml": "apiVersion: v1\nkind: ConfigMap\ndata: {}\n"}, sources="other: {}\n")
        self.assertEqual(findings, ["QA-7: core: schemas without an entry in sources.yaml"])
        findings, _, _ = self.run_check({}, sources=None)
        self.assertEqual(findings, ["QA-7: schemas/sources.yaml is missing or not YAML"])

    def test_sources_not_a_mapping_or_not_utf8_fails(self):  # GI-14
        findings, _, _ = self.run_check({}, sources="- core\n")
        self.assertEqual(findings, ["QA-7: schemas/sources.yaml is missing or not YAML"])
        with tree({"out/x": ""}) as root:
            os.makedirs(os.path.join(root, "schemas"))
            with open(os.path.join(root, "schemas", "sources.yaml"), "wb") as f:
                f.write(b"core: \xff\n")
            findings, _, _ = check(os.path.join(root, "schemas"), os.path.join(root, "out"))
        self.assertEqual(findings, ["QA-7: schemas/sources.yaml is missing or not YAML"])


if __name__ == "__main__":
    unittest.main()
