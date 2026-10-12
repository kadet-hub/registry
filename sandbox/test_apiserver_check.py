import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apiserver_check import check


def tree(files):
    tmp = tempfile.TemporaryDirectory()
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(tmp.name, rel)), exist_ok=True)
        with open(os.path.join(tmp.name, rel), "w", encoding="utf-8") as f:
            f.write(text)
    return tmp


ACCEPTED = """\
apiVersion: v1
kind: Namespace
metadata: {name: kube-system}
---
apiVersion: v1
kind: ConfigMap
metadata: {name: cm, namespace: not-in-output}
data: {a: b}
---
apiVersion: v1
kind: Pod
metadata: {name: pod, namespace: apps}
spec:
  serviceAccountName: not-in-output
  priorityClassName: not-in-output
  runtimeClassName: not-in-output
  containers: [{name: c, image: busybox, securityContext: {privileged: true}}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: all}
rules: [{apiGroups: ["*"], resources: ["*"], verbs: ["*"]}]
---
apiVersion: example.com/v1
kind: Widget
metadata: {name: w}
---
apiVersion: v1alpha1
kind: HostnameConfig
hostname: talos-machine-config
---
apiVersion: v1
kind: Config
clusters: []
"""

REJECTED = """\
apiVersion: v1
kind: Service
metadata: {name: noports}
spec: {selector: {app: x}}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: emptyprobe}
spec:
  selector: {matchLabels: {app: x}}
  template:
    metadata: {labels: {app: x}}
    spec:
      containers: [{name: c, image: busybox, livenessProbe: {}}]
---
apiVersion: v1
kind: Secret
metadata: {name: plain}
data: {key: not base64!}
---
apiVersion: v1
kind: ConfigMap
metadata: {name: typo, labelz: {}}
---
apiVersion: batch/v1beta1
kind: CronJob
metadata: {name: removed}
"""


class ApiserverCheck(unittest.TestCase):
    def test_server_rejections_are_findings(self):
        with tree({"compiled/minimal/ok.yaml": ACCEPTED, "compiled/minimal/bad.yaml": REJECTED}) as out:
            findings, lines = check(out)
        expected = [
            ("ConfigMap typo", 'unknown field "metadata.labelz"'),
            ("CronJob removed", "batch/v1beta1 CronJob is not served by kube-apiserver"),
            ("Deployment emptyprobe", "livenessProbe: Required value"),
            ("Secret plain", "illegal base64 data"),
            ("Service noports", "spec.ports: Required value"),
        ]
        self.assertEqual(len(findings), len(expected), findings)
        for finding, (what, message) in zip(findings, expected):
            self.assertTrue(finding.startswith(f"QA-10: compiled/minimal/bad.yaml: {what}: "), finding)
            self.assertIn(message, finding)
        self.assertRegex(lines[0], r"^QA-10: validated against kube-apiserver v\d+\.\d+\.\d+: 8 built-in documents, 3 skipped$")

    def test_output_without_kubernetes_documents_starts_no_server(self):
        with tree({"compiled/a/main.tf.json": "{}", "compiled/a/values.yml": "replicas: 2\n"}) as out:
            self.assertEqual(check(out), ([], []))


if __name__ == "__main__":
    unittest.main()
