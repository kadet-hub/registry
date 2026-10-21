---
title: "kube-prometheus-stack default Grafana dashboards, one by one"
date: 2026-10-21
topics: [helm, kustomize, kapitan, monitoring]
description: "kube-prometheus-stack dashboards: which values switch removes which default Grafana dashboard, and how to drop single ones with Kustomize or Kapitan."
---

kube-prometheus-stack 92.11.0, the release of 20 October 2026, renders 29
Grafana dashboards by default, each as a ConfigMap that Grafana's sidecar
loads. `grafana.defaultDashboardsEnabled` turns all of them off at once,
and the switches for scraped components remove some of them along with
the scraping. No value turns off a single dashboard. This post shows which
dashboard depends on which switch and removes single dashboards from the
rendered manifests, first with Kustomize over `helm template`, then with
[Kapitan](/glossary/#kapitan)'s [mutate](/generators/mutate/)
[generator](/glossary/#generator).

Each patch was rendered from the 92.11.0 chart with Helm 4.3.1, Kustomize
5.8.3, and Kapitan 0.36.3 with mutate 0.1.0, and the result was installed
on a kind cluster on Kubernetes 1.37.0. The guide
[Patch a Helm chart](/guides/patch-helm-chart/) compares the places such a
patch can live.

## Disable single default dashboards {#disable-default-dashboards}

[prometheus-community/helm-charts#3763](https://github.com/prometheus-community/helm-charts/issues/3763),
opened in September 2023 and at 23 thumbs up, asks for a switch per default
dashboard. The reporter's workaround, overwriting the ConfigMaps by hand,
lasts until the next deploy. The one maintainer reply, from jkroepke in
October 2025, is "just open a PR to solve this." Pull request #7015, opened
in June 2026, adds a map `grafana.defaultDashboardsDisabled`. It has no
review and conflicts with the current chart.

Every dashboard template starts with the same condition, here from
[`grafana-overview.yaml`](https://github.com/prometheus-community/helm-charts/blob/kube-prometheus-stack-92.11.0/charts/kube-prometheus-stack/templates/grafana/dashboards-1.14/grafana-overview.yaml#L7-L12):

```yaml
{{- if and (or .Values.grafana.enabled .Values.grafana.forceDeployDashboards) (semverCompare ">=1.14.0-0" $kubeTargetVersion) (semverCompare "<9.9.9-9" $kubeTargetVersion) .Values.grafana.defaultDashboardsEnabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  namespace: {{ template "kube-prometheus-stack-grafana.namespace" . }}
  name: {{ printf "%s-%s" (include "kube-prometheus-stack.fullname" $) "grafana-overview" | trunc 63 | trimSuffix "-" }}
```

Some templates add a component switch to that condition. Sixteen add
nothing, so `defaultDashboardsEnabled` is their only switch:
cluster-total, grafana-overview, the eight k8s-resources dashboards from
cluster to workloads-namespace, namespace-by-pod, namespace-by-workload,
persistentvolumesusage, pod-total, prometheus and workload-total.

### Which dashboard hangs on which switch

Setting a component's `enabled` to false removes its dashboard and also
what the chart renders to monitor that component. Rendered with each
switch set to false in turn, compared with the default render:

| Switch set to false | Dashboard ConfigMaps removed | Also removed |
|---|---|---|
| `kubeApiServer.enabled` | apiserver | ServiceMonitor, 4 PrometheusRules |
| `kubeControllerManager.enabled` | controller-manager | Service, ServiceMonitor, 1 PrometheusRule |
| `kubeScheduler.enabled` | scheduler | Service, ServiceMonitor, 2 PrometheusRules |
| `kubeEtcd.enabled` | etcd | Service, ServiceMonitor, 1 PrometheusRule |
| `kubeProxy.enabled` | proxy | Service, ServiceMonitor, 1 PrometheusRule |
| `coreDns.enabled` | k8s-coredns | Service, ServiceMonitor |
| `kubelet.enabled` | kubelet | ServiceMonitor, PrometheusRule kubelet.rules |
| `nodeExporter.enabled` | node-cluster-rsrc-use, node-rsrc-use, nodes, nodes-aix, nodes-darwin | the node-exporter DaemonSet, Service, ServiceAccount and ServiceMonitor |
| `alertmanager.enabled` | alertmanager-overview | Alertmanager, its Secret, Service, ServiceAccount and ServiceMonitor |

Where a component is not scraped at all, as the control plane of many
managed clusters, the switch removes the dashboard together with the
monitoring objects that have nothing to scrape. To keep scraping and
alerting for a component and drop only its dashboard, or to drop one of
the sixteen dashboards without a switch, delete the ConfigMap from the
rendered output.
`nodeExporter.forceDeployDashboards` and
`alertmanager.forceDeployDashboards` keep the dashboards of a disabled
node-exporter or Alertmanager, and `nodeExporter.operatingSystems.aix.enabled`
and `.darwin.enabled` remove only nodes-aix and nodes-darwin.

### Dashboard names

A dashboard ConfigMap is named `<fullname>-<dashboard>`, cut to 63
characters. The chart's `kube-prometheus-stack.fullname` starts from the
release name when that contains `kube-prometheus-stack`, and from
`<release>-kube-prometheus-stack` otherwise, and cuts either to 26
characters. Release `kube-prometheus-stack` therefore names a dashboard
`kube-prometheus-stack-grafana-overview`, and release `monitoring`, whose
`monitoring-kube-prometheus-stack` is cut to `monitoring-kube-prometheus`,
names it `monitoring-kube-prometheus-grafana-overview`. The 63-character
cut never applies to the default dashboards: the longest name, for a
fullname of the full 26 characters, has 60.

### Kustomize over helm template

For release `monitoring` in namespace `monitoring`:

```bash
helm template monitoring oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --version 92.11.0 --namespace monitoring --skip-tests > helm.yaml
kustomize build .
```

`--skip-tests` leaves out the Grafana subchart's test Pod, as Kapitan's
`helm` input does by default.

with this `kustomization.yaml` next to `helm.yaml`, which deletes the
dashboards Grafana Overview and Kubernetes / Compute Resources /
Multi-Cluster:

```yaml
resources:
  - helm.yaml
patches:
  - patch: |-
      $patch: delete
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: monitoring-kube-prometheus-grafana-overview
        namespace: monitoring
  - patch: |-
      $patch: delete
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: monitoring-kube-prometheus-k8s-resources-multicluster
        namespace: monitoring
```

A strategic merge patch with `$patch: delete` removes the object it names.
Kustomize's output kept every other object of the render; it only dropped
`metadata.annotations` where the chart renders it empty or null. Over a
render for release `kube-prometheus-stack`, where the names differ, the
build fails instead of passing without effect:

```text
Error: no resource matches strategic merge patch "ConfigMap.v1.[noGrp]/monitoring-kube-prometheus-grafana-overview.monitoring": no matches for Id ConfigMap.v1.[noGrp]/monitoring-kube-prometheus-grafana-overview.monitoring; failed to find unique target for patch ConfigMap.v1.[noGrp]/monitoring-kube-prometheus-grafana-overview.monitoring
```

### Kapitan's mutate

The [class](/glossary/#class) pins the chart by version and by the
[digest](/glossary/#digest) of its OCI artifact, and renders it as release
`monitoring`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: helm
        source: oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack@sha256:5b9b0215085f00f61c0fb2aa01ec402609d91c0a6a91bc84ca85cce2ed69e635
        chart_name: kube-prometheus-stack
        version: 92.11.0
        output_path: charts/kube-prometheus-stack
    compile:
      - input_type: helm
        input_paths: [charts/kube-prometheus-stack]
        output_path: kube-prometheus-stack
        helm_params:
          name: monitoring
          namespace: monitoring
```

The mutations delete the same two ConfigMaps:

```yaml
parameters:
  mutations:
    no-grafana-overview-dashboard:
      match: {apiVersion: v1, kind: ConfigMap, name: monitoring-kube-prometheus-grafana-overview}
      delete: true
    no-multicluster-dashboard:
      match: {apiVersion: v1, kind: ConfigMap, name: monitoring-kube-prometheus-k8s-resources-multicluster}
      delete: true
```

The [target](/glossary/#target) adds mutate as a second compile entry on
the chart's `output_path`, as the guide shows. Each dashboard template is
a file of its own, so both files become a single comment line:

```text
kube-prometheus-stack/templates/grafana/dashboards-1.14/grafana-overview.yaml: # all objects removed by mutation no-grafana-overview-dashboard
kube-prometheus-stack/templates/grafana/dashboards-1.14/k8s-resources-multicluster.yaml: # all objects removed by mutation no-multicluster-dashboard
```

The mutated render lost exactly the two ConfigMaps compared with the plain
one, and kept the same 27 dashboards as the Kustomize output. With the
class changed to release `kube-prometheus-stack`, the compile stops:

```text
mutate: mutation no-grafana-overview-dashboard: expects 1+, matched 0
```

### On kind

The mutated output went to a kind cluster on Kubernetes 1.37.0, the CRDs
first and everything with a server-side apply. Grafana, the operator,
kube-state-metrics, Prometheus, Alertmanager and node-exporter all became
ready, and the Kustomize output passed a server-side dry run against the
same cluster. The cluster held 27 dashboard ConfigMaps. Grafana's search
API listed 27 dashboards, with the same titles as those ConfigMaps:

```text
Grafana lists 27 dashboards, the mutated render has 27
neither removed dashboard is listed: ["Grafana Overview","Kubernetes / Compute Resources /  Multi-Cluster"]
```

The ServiceMonitor `monitoring-kube-prometheus-kube-controller-manager`
stayed in place, so the controller manager is still scraped, without its
dashboard.

### With the Grafana Operator

With `grafana.operator.dashboardsConfigMapRefEnabled: true` and
`grafana.operator.matchLabels` set, the chart also renders a
`GrafanaDashboard` per dashboard, with the same name as its ConfigMap and
a `configMapRef` to it. The patches above delete only the ConfigMaps and
would leave two GrafanaDashboards that reference ConfigMaps that no longer
exist. With the operator, the Kustomize patch deletes both kinds:

```yaml
resources:
  - helm.yaml
patches:
  - patch: |-
      $patch: delete
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: monitoring-kube-prometheus-grafana-overview
        namespace: monitoring
  - patch: |-
      $patch: delete
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: monitoring-kube-prometheus-k8s-resources-multicluster
        namespace: monitoring
  - patch: |-
      $patch: delete
      apiVersion: grafana.integreatly.org/v1beta1
      kind: GrafanaDashboard
      metadata:
        name: monitoring-kube-prometheus-grafana-overview
        namespace: monitoring
  - patch: |-
      $patch: delete
      apiVersion: grafana.integreatly.org/v1beta1
      kind: GrafanaDashboard
      metadata:
        name: monitoring-kube-prometheus-k8s-resources-multicluster
        namespace: monitoring
```

and each mutation matches every kind by name and expects two objects:

```yaml
parameters:
  mutations:
    no-grafana-overview-dashboard:
      match: {kind: "*", name: monitoring-kube-prometheus-grafana-overview}
      delete: true
      expects: 2
    no-multicluster-dashboard:
      match: {kind: "*", name: monitoring-kube-prometheus-k8s-resources-multicluster}
      delete: true
      expects: 2
```

Rendered with those two values, both removed exactly the two ConfigMaps
and the two GrafanaDashboards, and no remaining GrafanaDashboard refers to
a missing ConfigMap. The Grafana Operator itself was not installed, so
this variant is tested on the rendered output only.
