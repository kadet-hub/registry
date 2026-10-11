import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_check import check
from tf_schema import compare, describe, extract

ADDRESS = "registry.terraform.io/example/cloud"
FULL = {
    "format_version": "1.0",
    "provider_schemas": {ADDRESS: {
        "provider": {"block": {
            "attributes": {"region": {"type": "string", "required": True}},
            "block_types": {"features": {"nesting_mode": "list", "min_items": 1, "max_items": 1, "block": {}}},
        }},
        "resource_schemas": {
            "cloud_net": {"block": {
                "attributes": {
                    "id": {"type": "string", "computed": True},
                    "cidr": {"type": "string", "required": True},
                    "size": {"type": "number", "optional": True},
                    "tags": {"type": ["map", "string"], "optional": True},
                    "rules": {"type": ["set", ["object", {"name": "string", "port": "number"}]], "optional": True},
                },
                "block_types": {"timeouts": {"nesting_mode": "single", "block": {"attributes": {"create": {"type": "string", "optional": True}}}}},
            }},
            "cloud_unused": {"block": {}},
        },
        "data_source_schemas": {"cloud_zone": {"block": {"attributes": {"name": {"type": "string", "required": True}}}}},
    }},
}
SOURCES = "terraform/example/cloud:\n  software: Example provider\n  version: 1.2.3\n  source: https://registry.terraform.io/providers/example/cloud/1.2.3\n"
PROVIDERS = {
    "terraform": {"required_providers": {"cloud": {"source": "example/cloud", "version": "1.2.3"}}},
    "provider": {"cloud": {"region": "eu", "features": {}}},
}
NET = {"resource": {"cloud_net": {"main": {"cidr": "10.0.0.0/16", "size": 2, "tags": {"a": "b"},
                                           "rules": [{"name": "ssh", "port": 22}], "depends_on": ["x.y"]}}},
       "data": {"cloud_zone": {"z": {"name": "a"}}}}


def run(output, sources=SOURCES, schema=FULL):
    with tempfile.TemporaryDirectory() as root:
        files = {"schemas/sources.yaml": sources, "schemas/terraform/example_cloud_1.2.3.json": json.dumps(schema)}
        files.update({f"out/{k}": json.dumps(v) for k, v in output.items()})
        for rel, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
                f.write(text)
        return check(os.path.join(root, "schemas"), os.path.join(root, "out"))


class TerraformSchema(unittest.TestCase):
    def test_valid_module_names_the_provider(self):
        findings, lines, result = run({"tf/providers.tf.json": PROVIDERS, "tf/net.tf.json": NET})
        self.assertEqual(findings, [])
        self.assertEqual(result, [{"software": "Example provider", "version": "1.2.3",
                                   "source": "https://registry.terraform.io/providers/example/cloud/1.2.3"}])
        self.assertIn("QA-8: validated against Example provider 1.2.3", lines)

    def test_each_kind_of_error_is_a_finding(self):
        bad = {"resource": {"cloud_net": {"main": {
            "id": "x", "size": "two", "colour": "red", "rules": [{"name": "ssh"}],
            "timeouts": [{"create": "1m"}, {"create": "2m"}],
        }, "other": {"cidr": "${var.cidr}", "tags": "${local.tags}"}}, "cloud_gone": {"x": {}}}}
        findings, _, _ = run({"tf/providers.tf.json": {**PROVIDERS, "provider": {"cloud": {}}}, "tf/net.tf.json": bad})
        self.assertEqual(findings, sorted([
            "QA-8: tf/net.tf.json: cloud_gone.x: type cloud_gone not in the cloud schema",
            "QA-8: tf/net.tf.json: cloud_net.main.colour: unknown argument or block",
            "QA-8: tf/net.tf.json: cloud_net.main.id: read-only attribute",
            "QA-8: tf/net.tf.json: cloud_net.main.rules[0]: missing attribute port",
            "QA-8: tf/net.tf.json: cloud_net.main.size: \"two\" is not a \"number\"",
            "QA-8: tf/net.tf.json: cloud_net.main.timeouts: at most 1 block allowed, got 2",
            "QA-8: tf/net.tf.json: cloud_net.main: missing required argument cidr",
            "QA-8: tf/providers.tf.json: provider.cloud: missing required argument region",
            "QA-8: tf/providers.tf.json: provider.cloud: missing required block features",
        ]))

    def test_unpinned_or_unknown_version_is_review(self):
        loose = {**PROVIDERS, "terraform": {"required_providers": {"cloud": {"source": "example/cloud", "version": "~> 1.2"}}}}
        findings, lines, result = run({"a/providers.tf.json": loose, "a/net.tf.json": NET})
        self.assertEqual((findings, result), ([], []))
        self.assertTrue(any(line.endswith("no exact version pin") for line in lines))
        other = {**PROVIDERS, "terraform": {"required_providers": {"cloud": {"source": "example/cloud", "version": "= 9.9.9"}}}}
        _, lines, _ = run({"a/providers.tf.json": other, "a/net.tf.json": NET})
        self.assertTrue(any("no schema for example/cloud 9.9.9" in line for line in lines))

    def test_provider_without_sources_entry_fails(self):
        findings, _, _ = run({"a/providers.tf.json": PROVIDERS, "a/net.tf.json": NET}, sources="other: {}\n")
        self.assertEqual(findings, ["QA-8: terraform/example/cloud: schema without an entry in sources.yaml"])

    def test_extract_keeps_only_the_types_used(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "out", "tf"))
            for name, doc in (("providers.tf.json", PROVIDERS), ("net.tf.json", NET)):
                with open(os.path.join(root, "out", "tf", name), "w", encoding="utf-8") as f:
                    json.dump(doc, f)
            with open(os.path.join(root, "full.json"), "w", encoding="utf-8") as f:
                json.dump(FULL, f)
            reduced = extract(os.path.join(root, "full.json"), os.path.join(root, "out"))
        schema = reduced["provider_schemas"][ADDRESS]
        self.assertEqual(sorted(schema["resource_schemas"]), ["cloud_net"])
        self.assertEqual(sorted(schema["data_source_schemas"]), ["cloud_zone"])
        self.assertIn("block", schema["provider"])


    def test_compare_finds_edited_and_invented_types(self):
        with tempfile.TemporaryDirectory() as root:
            full, ext = os.path.join(root, "full.json"), os.path.join(root, "example_cloud_1.2.3.json")
            with open(full, "w", encoding="utf-8") as f:
                json.dump(FULL, f)
            shipped = json.loads(json.dumps(FULL))
            part = shipped["provider_schemas"][ADDRESS]
            del part["resource_schemas"]["cloud_unused"]
            with open(ext, "w", encoding="utf-8") as f:
                json.dump(shipped, f)
            self.assertEqual(compare(ext, full), [])  # a subset is fine
            self.assertEqual(describe(ext), ("example/cloud", "1.2.3"))
            part["resource_schemas"]["cloud_net"]["block"]["attributes"]["extra"] = {"type": "string", "optional": True}
            part["resource_schemas"]["cloud_made_up"] = {"block": {}}
            part["provider"] = {"block": {}}
            with open(ext, "w", encoding="utf-8") as f:
                json.dump(shipped, f)
            self.assertEqual(compare(ext, full), [
                f"{ADDRESS}: provider block differs",
                f"{ADDRESS}: resource cloud_made_up does not exist in this version",
                f"{ADDRESS}: resource cloud_net differs",
            ])


if __name__ == "__main__":
    unittest.main()
