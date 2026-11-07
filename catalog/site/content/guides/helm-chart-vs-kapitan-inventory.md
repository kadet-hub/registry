---
title: "Writing a Helm chart vs Kapitan: three popular charts rebuilt"
date: 2026-10-23
topics: [helm, kapitan, generators, comparison]
description: "Writing a Helm chart vs a Kapitan inventory, measured on metrics-server, cert-manager and kube-prometheus-stack: equal objects and behaviour on kind."
---

If you install a third-party chart, keep the chart. Its values are the
interface its maintainers support, and for what they do not expose you can
[patch the rendered output](/guides/patch-helm-chart/). This post is about
the other side: the people who write and maintain a chart. What would they
maintain if the same objects came from a [Kapitan](/glossary/#kapitan)
[inventory](/glossary/#inventory) and a [generator](/glossary/#generator)
instead of templates?

To find out, three of the most starred charts on Artifact Hub were rebuilt
as one Kapitan project on the omegaconf backend: metrics-server, cert-manager
and kube-prometheus-stack. The project and the script that compares them
are in
[kadet-hub/examples/chart-vs-kapitan](https://github.com/kadet-hub/examples/tree/main/chart-vs-kapitan),
and CI runs the comparison on every change.

## How the two sides are compared

"Looks the same" is not enough, so the check asks the API server. Both
renderings go through `kubectl apply --dry-run=server` on a kind cluster,
which applies the defaults Kubernetes adds on its own. Then names, labels,
selectors and list order are normalized, because the generator names
objects by its own convention. What remains has to be equal.

RBAC is compared by what it grants, not by how it is written:
`kubectl auth can-i --list` for every ServiceAccount of the chart, and for
a user bound only to the built-in `view` role, where aggregated
ClusterRoles land. Finally each side is installed on its own fresh cluster
and has to work: `kubectl top nodes` for metrics-server, a Certificate
issued by a self-signed ClusterIssuer for cert-manager. For
kube-prometheus-stack the comparison is what both installs do, described
in [its section](#kube-prometheus-stack-alternative).

## Results

| | metrics-server 3.14.0 | cert-manager v1.21.2 | kube-prometheus-stack 92.11.0 |
|---|---|---|---|
| Objects | equal (4 outside RBAC) | equal (17 outside RBAC, CRDs included) | 114 vs 126, compared by behaviour |
| Permissions | equal | equal | not compared, see below |
| Works on kind | `kubectl top nodes` | Certificate `Ready` | same scrape jobs and health, same rules, Grafana dashboards |
| Chart templates | 761 lines | 15,803 lines | 24,928 lines with subcharts |
| Chart `values.yaml` | 248 lines | 1,758 lines | 9,920 lines with subcharts |
| Kapitan inventory | 63 lines | 161 lines | 406 lines, plus 101 of Jsonnet |

The chart's numbers are what its authors maintain. The inventory's numbers
are what you would maintain instead; the code that turns them into objects
is the kadet-hub [kubernetes](/generators/kubernetes/) and
[prometheus-operator](/generators/prometheus-operator/) generators,
versioned, signed and maintained once for every project that uses them.
Someone who only installs a chart writes far less: 2 lines of values for
metrics-server on kind, 4 for cert-manager. That is the comparison the
first paragraph of this post sets aside.

## metrics-server {#metrics-server}

metrics-server is a Deployment, a Service, an APIService and RBAC. The
inventory declares the port once, and the generator derives the container
port, the Service port, the Service's `appProtocol` from the port name and
the APIService that points at the Service:

```yaml
components:
  metrics-server:
    ports:
      https:
        container_port: 10250
        service_port: 443
    service:
      type: ClusterIP
    api_service: {group: metrics.k8s.io, version: v1beta1, insecure_skip_tls_verify: true}
    cluster_role:
      rules:
        - {apiGroups: [""], resources: [nodes/metrics], verbs: [get]}
        - {apiGroups: [""], resources: [pods, nodes, namespaces, configmaps], verbs: [get, list, watch]}
```

`cluster_role` on the component creates the ClusterRole and binds it to
the component's own ServiceAccount, so no name is written twice. Two
differences remain by design. RBAC objects cannot be named
`system:metrics-server`, because the generator also writes the name as a
label value, where colons are not allowed. And probes need
`timeout_seconds: 1` to match the chart, because the generator defaults to
5 seconds where Kubernetes defaults to 1.

## cert-manager {#cert-manager}

cert-manager has three Deployments, two webhook configurations, six CRDs
and 13 ClusterRoles. The inventory has one `cluster_role` per component
instead of 13: the controller's nine roles become one list of 37 rules,
and `can-i` shows the same permissions. Shared pod settings, such as the
security context, the metrics port and the `POD_NAMESPACE` variable, are
written once in `generators.manifest.default_config`. Leader election
Roles in `kube-system` sit on their component with `role.namespace`. The
CRDs are cert-manager's release file, pinned by sha256, not part of either
count.

The webhooks only state what is specific to them:

```yaml
webhook_annotations:
  cert-manager.io/inject-ca-from-secret: cert-manager/cert-manager-webhook-ca
webhooks:
  - name: webhook.cert-manager.io
    rules: [{apiGroups: [cert-manager.io], apiVersions: [v1], operations: [CREATE], resources: [certificaterequests]}]
    timeoutSeconds: 30
    clientConfig: {service: {path: /mutate}}
```

The Service, `admissionReviewVersions: [v1]` and `sideEffects: None` come
from the generator. One behavioural difference is intended: the generator
keeps a webhook out of its own namespace, so it cannot block the pods that
serve it. The chart's mutating webhook does not. The startupapicheck Job is
switched off on the chart side, because it is a Helm hook and Kapitan has
no hooks.

## kube-prometheus-stack {#kube-prometheus-stack-alternative}

kube-prometheus-stack installs the Prometheus Operator, kube-state-metrics,
node-exporter, Grafana with its dashboard sidecars, a Prometheus and an
Alertmanager, 13 ServiceMonitors, 35 PrometheusRules and about 30 dashboard
ConfigMaps. Most of its rules and dashboards are not written by hand:
a sync script generates them from kube-prometheus and kubernetes-mixin,
which are [Jsonnet](https://jsonnet.org/). Kapitan compiles Jsonnet
natively, so the Kapitan side builds them from the same upstream commits
the chart's sync uses, pinned in a `jsonnetfile.lock.json`. The workloads
come from the kubernetes generator, Prometheus, Alertmanager and the
ServiceMonitors from the prometheus-operator generator, and the Services
for the pods the operator and the cluster run from the kubernetes
generator's `services` section.

Object for object comparison stops making sense here, so each side is
installed on its own cluster and asked what it does:

- Prometheus scrapes the same 13 jobs with the same health on both sides.
  Four are down on both, because kind binds kube-controller-manager,
  kube-scheduler, etcd and kube-proxy metrics to localhost.
- Prometheus loads the same 205 rule names.
- Alertmanager is ready, and Grafana is healthy with the same two
  datasources and 29 dashboards.

34 of the chart's 35 rule groups and all 29 dashboards come out equal. The
35th, `k8s.rules.container_resource`, is left over from an older sync:
the pinned sources produce the same eight recording rules split into four
groups, which the chart ships but switches off. Permissions are not
compared for this chart, because the prometheus-operator generator's
Prometheus RBAC differs from the chart's by one verb and one path.

For the comparison both sides switch off the operator's admission webhooks
and the TLS that goes with them, because the chart creates their
certificates with Helm hooks.

## What the comparison changed

Rebuilding the charts showed values the inventory had to repeat because
the generator could not derive them. Each became a default in the
kubernetes generator, overridable where it can be wrong:

| Version | Change |
|---|---|
| 1.3.0 | `appProtocol` on Service ports |
| 1.4.0 | `appProtocol` from the port name; a component's webhooks point at its Service and default `admissionReviewVersions` and `sideEffects`; `role.namespace` for leader election Roles; cert-manager's CA injection annotations |
| 1.5.0 | `api_service` on a component |
| 1.6.0 | Services for pods no component renders, such as Prometheus and the control-plane pods; `external_name` |

## Where the chart stays ahead

A chart is the one artifact every Kubernetes tool consumes. Helm hooks run
Jobs at install time, such as cert-manager's startupapicheck or
kube-prometheus-stack's certificate generator, which an inventory replaces
with something else, like a Job you apply first. And a chart's users
expect `helm install` with a values file, not a Kapitan project. The
inventory pays off for the people who maintain the chart's logic, for
platform teams that run the same apps in many clusters, and wherever one
value has to reach several objects: the port that is also the Service
port, the probe port and the APIService port.
