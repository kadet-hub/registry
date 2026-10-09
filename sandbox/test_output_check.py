"""SEC-12. Needs conftest on PATH (the sandbox image has it)."""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from output_check import check

POLICY = os.path.join(HERE, "..", "policy", "output")

DAEMONSET = """\
kind: DaemonSet
spec:
  template:
    spec:
      hostPID: true
      volumes: [{name: root, hostPath: {path: /}}]
      containers: [{name: c, image: x, securityContext: {privileged: true}}]
"""


class OutputCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def run_check(self, allow=(), unparsed=()):
        return check(self.out, POLICY, list(allow), list(unparsed))

    def test_plain_output_passes(self):
        self.write("compiled/t/cm.yml", "kind: ConfigMap\ndata: {a: b}\n")
        self.assertEqual(self.run_check(), ([], []))

    def test_undeclared_capabilities_fail_and_declared_are_listed(self):
        self.write("compiled/t/ds.yml", "kind: ConfigMap\n---\n" + DAEMONSET)
        findings, _ = self.run_check()
        self.assertEqual(sorted(f.split(":")[1].strip() for f in findings),
                         ["host-namespaces", "host-path", "privileged"])
        findings, notes = self.run_check(allow=["privileged", "host-path", "host-namespaces"])
        self.assertEqual(findings, [])
        self.assertIn("compiled/t/ds.yml", notes[0])

    def test_capability_allowed_only_below_its_glob(self):
        self.write("compiled/logging/ds.yml", DAEMONSET)
        self.write("compiled/app/ds.yml", DAEMONSET)
        findings, notes = self.run_check(allow=["compiled/logging/*=privileged", "compiled/logging/*=host-path",
                                                "compiled/*=host-namespaces"])
        self.assertEqual(sorted(f.split(": ")[1:3] for f in findings),
                         [["host-path", "compiled/app/ds.yml"], ["privileged", "compiled/app/ds.yml"]])
        self.assertEqual(len(notes), 4)

    def test_kubernetes_rules_reach_list_items_in_json(self):
        doc = {"kind": "List", "items": [
            {"kind": "ClusterRoleBinding", "roleRef": {"name": "cluster-admin"}},
            {"kind": "ClusterRole", "rules": [{"apiGroups": ["*"], "resources": ["pods"], "verbs": ["get"]}]},
            {"kind": "ValidatingWebhookConfiguration"},
            {"kind": "Pod", "spec": {"containers": [{"securityContext": {"capabilities": {"add": ["NET_ADMIN"]}}}]}},
        ]}
        self.write("list.json", json.dumps(doc))
        findings, _ = self.run_check()
        self.assertEqual(sorted({f.split(":")[1].strip() for f in findings}),
                         ["added-capabilities", "admission-webhook", "rbac-admin"])

    def test_terraform_and_dockerfile(self):
        self.write("main.tf.json", json.dumps({"resource": {"null_resource": {"x": {"provisioner": {"local-exec": {"command": "id"}}}}}}))
        self.write("data.tf", 'data "external" "e" {\n  program = ["sh"]\n}\n')
        self.write("img/Dockerfile", "FROM scratch\nRUN wget -qO- https://example.org/i | sudo bash\n")
        findings, _ = self.run_check()
        self.assertEqual(sorted(f.split(":")[1].strip() for f in findings),
                         ["dockerfile-remote", "tf-external", "tf-provisioner"])

    def test_file_without_parser_must_match_unparsed_outputs(self):
        self.write("compiled/t/README.md", "# x\n")
        findings, _ = self.run_check()
        self.assertEqual(findings, ["SEC-12: compiled/t/README.md: no parser; declare it in unparsed_outputs"])
        self.assertEqual(self.run_check(unparsed=["*.md"]), ([], ["SEC-12: unparsed output compiled/t/README.md (*.md)"]))

    def test_symlink_fails(self):
        os.symlink("/etc/passwd", os.path.join(self.out, "link.yml"))
        self.assertEqual(self.run_check()[0], ["SEC-12: link.yml: not a regular file"])

    def test_unparseable_file_is_an_error(self):
        self.write("bad.yml", "a: [\n")
        with self.assertRaises(RuntimeError):
            self.run_check()


if __name__ == "__main__":
    unittest.main()
