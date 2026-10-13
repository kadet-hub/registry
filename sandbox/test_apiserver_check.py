import json
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


# Test fixture written for these tests, not an upstream CRD. A plain = needs
# the loader of QA-12; with strategy Webhook, the v2 Widget would need the
# unreachable webhook to convert it to the storage version v1.
WIDGETS = """\
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: widgets.example.com}
spec:
  group: example.com
  names: {kind: Widget, listKind: WidgetList, plural: widgets, singular: widget}
  scope: Namespaced
  conversion:
    strategy: Webhook
    webhook:
      conversionReviewVersions: [v1]
      clientConfig: {url: "https://203.0.113.1/convert"}
  versions:
  - name: v1
    served: true
    storage: true
    schema: &schema
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              chart: {type: string}
              chartRef: {type: string}
              match:
                type: string
                enum:
                - =
                - "!="
            x-kubernetes-validations:
            - rule: has(self.chart) != has(self.chartRef)
              message: either chart or chartRef must be set
  - {name: v2, served: true, storage: false, schema: *schema}
  - {name: v1beta1, served: false, storage: false, schema: *schema}
"""

CUSTOM = """\
apiVersion: example.com/v1
kind: Widget
metadata: {name: ok, namespace: apps}
spec: {chart: podinfo, match: "="}
---
apiVersion: example.com/v2
kind: Widget
metadata: {name: converted, namespace: apps}
spec: {chartRef: podinfo}
---
apiVersion: example.com/v1
kind: Widget
metadata: {name: both}
spec: {chart: podinfo, chartRef: podinfo}
---
apiVersion: example.com/v1
kind: Widget
metadata: {name: typo}
spec: {chart: podinfo, chartz: podinfo}
---
apiVersion: example.com/v1beta1
kind: Widget
metadata: {name: old}
spec: {chart: podinfo}
---
apiVersion: example.com/v1
kind: Gadget
metadata: {name: cluster-scoped}
---
apiVersion: example.com/v1
kind: Unknown
metadata: {name: u}
---
apiVersion: other.example.org/v1
kind: Thing
metadata: {name: t1}
---
apiVersion: other.example.org/v1
kind: Thing
metadata: {name: t2}
---
apiVersion: v1
kind: ConfigMap
metadata: {name: cm}
"""


def crd(group, plural, kind, scope="Namespaced", rule="true"):
    """A test CRD with one served version v1 and one CEL rule."""
    schema = {"type": "object", "x-kubernetes-validations": [{"rule": rule}]}
    return json.dumps({
        "apiVersion": "apiextensions.k8s.io/v1", "kind": "CustomResourceDefinition", "metadata": {"name": f"{plural}.{group}"},
        "spec": {"group": group, "names": {"kind": kind, "plural": plural}, "scope": scope,
                 "versions": [{"name": "v1", "served": True, "storage": True, "schema": {"openAPIV3Schema": schema}}]},
    })


SOURCES = "".join(f"{g}: {{software: test, version: '1', source: tbd, license: Apache-2.0}}\n" for g in ("example.com", "other.example.org", "rbac.authorization.k8s.io"))


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

    def test_custom_resources_against_shipped_crds(self):
        with tree({"compiled/minimal/crs.yaml": CUSTOM}) as out, tree({
            "sources.yaml": SOURCES,
            "example.com/crds/widgets.yaml": WIDGETS,
            "example.com/crds/gadgets.json": crd("example.com", "gadgets", "Gadget", scope="Cluster"),
            "example.com/gadget_v1.json": "{}",
        }) as schemas:
            findings, lines = check(out, schemas)
        expected = [
            ("Widget both", "either chart or chartRef must be set"),
            ("Widget old", "example.com/v1beta1 Widget is not served by CRD widgets.example.com"),
            ("Widget typo", 'unknown field "spec.chartz"'),
        ]
        self.assertEqual(len(findings), len(expected), findings)
        for finding, (what, message) in zip(findings, expected):
            self.assertTrue(finding.startswith(f"QA-11: compiled/minimal/crs.yaml: {what}: "), finding)
            self.assertIn(message, finding)
        self.assertRegex(lines[0], r"^QA-10: validated against kube-apiserver v\d+\.\d+\.\d+: 1 built-in documents, 9 skipped$")
        self.assertEqual(lines[1:], [
            "QA-11: validated against 2 CRDs: 5 custom resources, 3 skipped",
            "review: QA-11: example.com/v1: no CRD, 1 documents skipped",
            "review: QA-11: other.example.org/v1: no CRD, 2 documents skipped",
        ])

    def test_crd_files_that_break_the_layout_are_findings(self):
        with tree({}) as out, tree({
            "sources.yaml": SOURCES,
            "example.com/crds/gizmos.yaml": crd("example.com", "gizmos", "Gizmo"),
            "example.com/crds/sprocket.yaml": crd("example.com", "sprockets", "Sprocket"),
            "example.com/crds/twos.yaml": crd("example.com", "twos", "Two") + "\n---\n" + crd("example.com", "ones", "One"),
            "example.com/crds/brokens.yaml": crd("example.com", "brokens", "Broken", rule="self.nope("),
            "example.com/crds/cogs.yaml": crd("example.com", "cogs", "Gizmo"),
            "example.com/crds/sub/bolts.yaml": crd("example.com", "bolts", "Bolt"),
            "other.example.org/crds/widgets.yaml": crd("example.com", "widgets", "Widget"),
            "nosource.example.com/crds/things.yaml": crd("nosource.example.com", "things", "Thing"),
            "rbac.authorization.k8s.io/crds/roles.yaml": crd("rbac.authorization.k8s.io", "roles", "Role"),
        }) as schemas:
            findings, lines = check(out, schemas)
        expected = [
            ("example.com/crds/brokens.yaml", "compilation failed"),
            # cogs and gizmos claim the same kind; the one created second is not established.
            ("example.com/crds/", "not established within 60 s: "),
            ("example.com/crds/sprocket.yaml", "not named example.com/crds/sprockets.yaml or .json"),
            ("example.com/crds/sub/bolts.yaml", "not named example.com/crds/bolts.yaml or .json"),
            ("example.com/crds/twos.yaml", "does not hold exactly one apiextensions.k8s.io/v1 CustomResourceDefinition"),
            ("nosource.example.com/crds/things.yaml", "group nosource.example.com has no entry in sources.yaml"),
            ("other.example.org/crds/widgets.yaml", "CRD of group example.com, not other.example.org"),
            ("rbac.authorization.k8s.io/crds/roles.yaml", "group rbac.authorization.k8s.io is served by kube-apiserver"),
        ]
        self.assertEqual(len(findings), len(expected), findings)
        for finding, (file, message) in zip(findings, expected):
            self.assertTrue(finding.startswith(f"QA-12: {file}"), finding)
            self.assertIn(message, finding)
        self.assertIn("is already in use", findings[1])
        self.assertEqual(lines[1:], ["QA-11: validated against 1 CRDs: 0 custom resources, 0 skipped"])

    def test_output_without_kubernetes_documents_starts_no_server(self):
        with tree({"compiled/a/main.tf.json": "{}", "compiled/a/values.yml": "replicas: 2\n"}) as out:
            self.assertEqual(check(out), ([], []))


if __name__ == "__main__":
    unittest.main()
