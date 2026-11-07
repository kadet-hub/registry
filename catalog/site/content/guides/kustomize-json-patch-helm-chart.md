---
title: "Kustomize JSON patch add: fields a Helm chart does not template"
date: 2026-10-21
lastmod: 2026-10-22
topics: [helm, kustomize, kapitan]
description: "Kustomize JSON patch add and Kapitan's mutate for fields charts lack: appProtocol, trafficDistribution, topologySpreadConstraints, annotations, hostNetwork."
---

A chart can only set the fields its templates write. When a Kubernetes
field you need is missing from them, the value you add to `values.yaml`
is silently ignored, unless the chart has a values schema that rejects it.
This post sets nine such fields from open issues on the rendered manifests,
first with a Kustomize patch over `helm template`, then with
[Kapitan](/glossary/#kapitan)'s [mutate](/generators/mutate/)
[generator](/glossary/#generator). Most of them are RFC 6902 JSON Patch
operations, and mutate's `json6902` takes the same operations as
Kustomize, so the two versions of each patch read almost the same.

Each patch was rendered from the chart version named in its section with
Helm 4.3.1, Kustomize 5.8.3, and Kapitan 0.36.3 with mutate 0.1.0. In every
case the Kustomize output and the mutate output set the same value and
changed nothing else in the render. The mutate output was installed on
kind clusters on Kubernetes 1.37.0 with three worker nodes, and each
Kustomize output's patched object passed a server-side dry run there.
Charts from HTTP
repositories matched the sha256 their `index.yaml` lists. The guide
[Patch a Helm chart](/guides/patch-helm-chart/) compares the places such a
patch can live.

The [class](/glossary/#class) for each chart pins its version, like this
one for Vault, and the [target](/glossary/#target) adds mutate as a second
compile entry on the chart's `output_path`, as the guide shows:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: helm
        source: https://helm.releases.hashicorp.com
        chart_name: vault
        version: 0.34.1
        output_path: charts/vault
    compile:
      - input_type: helm
        input_paths: [charts/vault]
        output_path: vault
        helm_values_files: [values/vault.yaml]
        helm_params:
          name: vault
          namespace: vault
```

## Vault Helm chart: Service appProtocol {#vault-service-appprotocol}

[hashicorp/vault-helm#1108](https://github.com/hashicorp/vault-helm/issues/1108),
opened in April 2025 and at 9 thumbs up, asks for `appProtocol: https` on
the Vault Service. Without it, Gateway API implementations such as GKE's
Gateway controller talk plain HTTP to a Vault that serves HTTPS, according
to the issue and the GKE documentation it links. No maintainer has
replied. Chart 0.34.1, released on 13 August 2026, writes the ports in
[`server-service.yaml`](https://github.com/hashicorp/vault-helm/blob/v0.34.1/templates/server-service.yaml#L45-L54)
without it:

```yaml
  ports:
    - name: {{ include "vault.scheme" . }}
      port: {{ .Values.server.service.port }}
      targetPort: {{ .Values.server.service.targetPort }}
      {{- if and (.Values.server.service.nodePort) (eq (.Values.server.service.type | toString) "NodePort") }}
      nodePort: {{ .Values.server.service.nodePort }}
      {{- end }}
    - name: https-internal
      port: 8201
      targetPort: 8201
```

The port takes its name from the scheme, `https` once `global.tlsDisable`
is false, which this values file sets:

```yaml
global:
  tlsDisable: false
```

```yaml
resources:
  - helm.yaml
patches:
  - target:
      kind: Service
      name: vault
    patch: |-
      - op: test
        path: /spec/ports/0/name
        value: https
      - op: add
        path: /spec/ports/0/appProtocol
        value: https
```

```yaml
parameters:
  mutations:
    vault-app-protocol:
      match: {apiVersion: v1, kind: Service, name: vault}
      json6902:
        - {op: test, path: /spec/ports/0/name, value: https}
        - {op: add, path: /spec/ports/0/appProtocol, value: https}
```

`test` makes both patches refuse to mark a plain HTTP port as `https`. With
the chart's default `tlsDisable: true` the first port is named `http`, and
both stopped:

```text
Error: testing value /spec/ports/0/name failed: test failed
mutate: mutation vault-app-protocol: vault/templates/server-service.yaml: json6902 test of '/spec/ports/0/name' failed
```

The Kustomize target `name: vault` matched the Service `vault` only, not
`vault-internal` or `vault-agent-injector-svc`. The test applied the
chart's Services to kind, without the Vault server, and the stored Service
carries the field:

```text
https 8200 appProtocol=https
```

## CloudNativePG cluster chart: topologySpreadConstraints {#cloudnative-pg-topology-spread-constraints}

[cloudnative-pg/charts#817](https://github.com/cloudnative-pg/charts/issues/817),
opened in February 2026, asks for `topologySpreadConstraints` on the
Cluster that the `cluster` chart renders. The CloudNativePG operator
supports the field, but the chart's
[`cluster.yaml`](https://github.com/cloudnative-pg/charts/blob/cluster-v0.9.0/charts/cluster/templates/cluster.yaml#L42-L45)
only templates `affinity`. Pull request #818, opened the same day, adds
it. It has had no review and now conflicts with the chart's main branch.
In its thread, a user pointed out that the label `cnpg.io/cluster` alone
also matches pooler and Job pods, and suggested adding
`cnpg.io/podRole: instance` to the selector.

On node-local storage that selector has a catch. CloudNativePG creates
each instance's volume through an initdb or join Job, whose pod gets the
instance's constraints but not the label `cnpg.io/podRole`, so the
constraint does not count it. kind's `local-path` volumes are bound to the
node of the first pod that mounts them. In a run with that selector, the
join Job of the third instance landed on the node of the second, the
volume followed it, and the third instance stayed Pending:

```text
0/4 nodes are available: 1 node(s) didn't match pod topology spread constraints, 1 node(s) had untolerated taint(s), 2 node(s) didn't match PersistentVolume's node affinity. preemption: 0/4 nodes are available: 1 No preemption victims found for incoming pod, 3 Preemption is not helpful for scheduling.
```

A selector that counts the Job pods too and leaves out only poolers spread
all three instances. Until a chart release has the value, chart 0.9.0
takes this patch:

```yaml
resources:
  - helm.yaml
patches:
  - target:
      group: postgresql.cnpg.io
      kind: Cluster
      name: pg-cluster
    patch: |-
      - op: add
        path: /spec/topologySpreadConstraints
        value:
          - maxSkew: 1
            topologyKey: kubernetes.io/hostname
            whenUnsatisfiable: DoNotSchedule
            labelSelector:
              matchLabels:
                cnpg.io/cluster: pg-cluster
              matchExpressions:
                - key: cnpg.io/podRole
                  operator: NotIn
                  values: [pooler]
```

```yaml
parameters:
  mutations:
    cluster-topology-spread:
      match: {apiVersion: postgresql.cnpg.io/v1, kind: Cluster, name: pg-cluster}
      json6902:
        - op: add
          path: /spec/topologySpreadConstraints
          value:
            - maxSkew: 1
              topologyKey: kubernetes.io/hostname
              whenUnsatisfiable: DoNotSchedule
              labelSelector:
                matchLabels:
                  cnpg.io/cluster: pg-cluster
                matchExpressions:
                  - key: cnpg.io/podRole
                    operator: NotIn
                    values: [pooler]
```

With operator chart 0.29.1 on the cluster and the release named `pg`, the
Cluster `pg-cluster` became Ready on a fresh cluster. Its three instance
pods carry the constraint and run on three different workers:

```text
pg-cluster-1 node=set-fields-worker2 ready=true spread=kubernetes.io/hostname
pg-cluster-2 node=set-fields-worker ready=true spread=kubernetes.io/hostname
pg-cluster-3 node=set-fields-worker3 ready=true spread=kubernetes.io/hostname
```

## Harbor Helm chart: annotations on the core Deployment {#harbor-core-deployment-annotations}

[goharbor/harbor-helm#2221](https://github.com/goharbor/harbor-helm/issues/2221),
opened in August 2025, asks for annotations and labels on the components'
Deployments, beyond the pod annotations the chart takes. One commenter
needs an annotation on `harbor-core` for Reloader. A collaborator
suggested a Helm hook, which the reporter cannot use with Argo CD. Three
pull requests for the values were closed unmerged by the stale bot. In chart
1.19.4, released on 16 October 2026,
[`core-dpl.yaml`](https://github.com/goharbor/harbor-helm/blob/v1.19.4/templates/core/core-dpl.yaml#L3-L9)
writes no annotations into the Deployment's metadata, and
`core.podAnnotations`, whose comment in `values.yaml` reads "Additional
deployment annotations", goes to the pod template only:

```yaml
metadata:
  name: {{ template "harbor.core" . }}
  namespace: {{ .Release.Namespace | quote }}
  labels:
{{ include "harbor.labels" . | indent 4 }}
    component: core
    app.kubernetes.io/component: core
```

An annotation is a key in a map, which a strategic merge patch and
mutate's `merge` add without touching other keys:

```yaml
resources:
  - helm.yaml
patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: harbor-core
        namespace: harbor
        annotations:
          reloader.stakater.com/auto: "true"
```

```yaml
parameters:
  mutations:
    harbor-core-annotations:
      match: {apiVersion: apps/v1, kind: Deployment, name: harbor-core}
      merge:
        metadata:
          annotations:
            reloader.stakater.com/auto: "true"
```

Harbor generates secrets on every render, so two renders differ in their
Secrets and in the Deployments' checksum annotations. The comparison of
the renders left those out. On kind, every Harbor Deployment became
Available, and the stored `harbor-core` carries the annotation:

```text
harbor-core annotations: {"deployment.kubernetes.io/revision":"1","reloader.stakater.com/auto":"true"}
```

## ECK operator chart: ServiceMonitor labels and interval {#eck-operator-servicemonitor}

[elastic/cloud-on-k8s#7717](https://github.com/elastic/cloud-on-k8s/issues/7717),
opened in April 2024, asks for labels and the interval on the operator's
ServiceMonitor, because a Prometheus from kube-prometheus-stack selects
ServiceMonitors by its `release` label. A commenter confirmed in August
2026 that 3.5.0 ignores `serviceMonitor.labels` and keeps a second
ServiceMonitor by hand. The chart has no values schema, so the key is
silently dropped. In 3.5.0, released on 4 August 2026,
[`service-monitor.yaml`](https://github.com/elastic/cloud-on-k8s/blob/v3.5.0/deploy/eck-operator/templates/service-monitor.yaml#L1-L20)
renders the ServiceMonitor only with metrics in secure mode, with the
chart's own labels and a fixed interval:

```yaml
{{- if and .Values.config.metrics.secureMode.enabled .Values.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "eck-operator.fullname" . }}
  namespace: {{ ternary .Values.serviceMonitor.namespace .Release.Namespace (not (and (.Values.serviceMonitor) (empty .Values.serviceMonitor.namespace))) }}
  labels: {{- include "eck-operator.labels" . | nindent 4 }}
spec:
  namespaceSelector:
    matchNames:
      - {{ .Release.Namespace }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "eck-operator.name" . }}-metrics-service
      app.kubernetes.io/instance: {{ .Release.Name }}
  endpoints:
  - port: https
    path: /metrics
    scheme: https
    interval: 30s
```

These values turn the metrics endpoint and secure mode on:

```yaml
config:
  metrics:
    port: "8080"
    secureMode:
      enabled: true
```

```yaml
resources:
  - helm.yaml
patches:
  - target:
      group: monitoring.coreos.com
      kind: ServiceMonitor
      name: elastic-operator
    patch: |-
      - op: add
        path: /metadata/labels/release
        value: kube-prometheus-stack
      - op: test
        path: /spec/endpoints/0/interval
        value: 30s
      - op: replace
        path: /spec/endpoints/0/interval
        value: 60s
```

```yaml
parameters:
  mutations:
    eck-servicemonitor:
      match: {apiVersion: monitoring.coreos.com/v1, kind: ServiceMonitor, name: elastic-operator}
      json6902:
        - {op: add, path: /metadata/labels/release, value: kube-prometheus-stack}
        - {op: test, path: /spec/endpoints/0/interval, value: 30s}
        - {op: replace, path: /spec/endpoints/0/interval, value: 60s}
```

`add` on `/metadata/labels/release` adds one key to the existing labels.
The `test` of `30s` stops the patch if a release changes the interval. On
kind, with the ServiceMonitor CRD of kube-prometheus-stack 92.11.0, the
operator became ready and the stored ServiceMonitor has both values:

```text
release=kube-prometheus-stack interval=60s
```

## Temporal Helm chart: Service trafficDistribution {#temporal-service-trafficdistribution}

[temporalio/helm-charts#897](https://github.com/temporalio/helm-charts/issues/897),
opened in April 2026, asks for `spec.trafficDistribution` on the server
Services, at least the frontend. Its author sets the field today with a
separate server-side apply after each install. No maintainer has replied.
Chart 1.7.0, released on 12 September 2026, writes `type`, `ports` and
`selector` in
[`server-service.yaml`](https://github.com/temporalio/helm-charts/blob/temporal-1.7.0/charts/temporal/templates/server-service.yaml#L15-L40)
and has no values schema, so `server.frontend.service.trafficDistribution`
is ignored. The chart needs a database to render, and this values file
names one that the test never contacted:

```yaml
server:
  config:
    persistence:
      datastores:
        default:
          sql:
            pluginName: postgres12
            databaseName: temporal
            connectAddr: db.example.internal:5432
        visibility:
          sql:
            pluginName: postgres12
            databaseName: temporal_visibility
            connectAddr: db.example.internal:5432
```

```yaml
resources:
  - helm.yaml
patches:
  - target:
      kind: Service
      name: temporal-frontend
    patch: |-
      - op: add
        path: /spec/trafficDistribution
        value: PreferSameZone
```

```yaml
parameters:
  mutations:
    temporal-traffic-distribution:
      match: {apiVersion: v1, kind: Service, name: temporal-frontend}
      json6902:
        - {op: add, path: /spec/trafficDistribution, value: PreferSameZone}
```

`PreferClose`, the value in the issue, is the older name for
`PreferSameZone`, and the Kubernetes documentation
[lists it as deprecated](https://kubernetes.io/docs/reference/networking/virtual-ips/#traffic-distribution).
The field is generally available since Kubernetes 1.33. The value
`PreferSameZone` is enabled by default from 1.34, so a 1.33 cluster needs
`PreferClose`. Without a database the Temporal servers cannot start, so
the test applied the chart's Services only, and the API server stored the
field:

```text
temporal-frontend trafficDistribution: PreferSameZone
```

## MetalLB Helm chart: the speaker without host networking {#metallb-speaker-hostnetwork}

[metallb/metallb#3005](https://github.com/metallb/metallb/issues/3005),
opened in April 2026, asks for `hostNetwork: false` on the speaker
DaemonSet. The reporter runs FRR on every node next to MetalLB, and FRR
does not accept iBGP peering with an address in its own network
namespace, so the speaker has to run in the pod network and peer with the
node's FRR. Another user peers the speakers with Calico the same way. The
maintainers asked for the use case. Pull request #3099 adds a
`speaker.hostNetwork` value, and on it the maintainer fedepaol
[wrote](https://github.com/metallb/metallb/pull/3099#issuecomment-5583454159)
"I think it makes sense to document this, mentioning that l2 won't be
able to work." It is not merged. Chart 0.16.1 hard-codes the field in
[`speaker.yaml`](https://github.com/metallb/metallb/blob/v0.16.1/charts/metallb/templates/speaker.yaml#L172):

```yaml
      hostNetwork: true
```

By default the chart runs BGP in a separate frr-k8s DaemonSet, which keeps
host networking whatever the speaker does. The test therefore uses
MetalLB's native mode, in which the speaker itself speaks BGP:

```yaml
frrk8s:
  enabled: false
speaker:
  frr:
    enabled: false
```

Flipping `hostNetwork` alone is not enough in 0.16.1. The speaker serves
its health endpoint on `127.0.0.1` inside its own network namespace
([`speaker/main.go`](https://github.com/metallb/metallb/blob/v0.16.1/speaker/main.go#L247)),
and the chart's probes ask for `127.0.0.1`, which the kubelet resolves in
the node's network namespace. With only the field changed, no speaker
became ready on kind, and every probe was refused:

```text
Readiness probe failed: Get "http://127.0.0.1:17472/readyz": dial tcp 127.0.0.1:17472: connect: connection refused
Liveness probe failed: Get "http://127.0.0.1:17472/healthz": dial tcp 127.0.0.1:17472: connect: connection refused
```

Pull request #3099 changes the field only, so it would leave the same
probes in place. The patch below also removes both probes. The speaker
then has no health check, and the kubelet restarts it only when the
process exits:

```yaml
resources:
  - helm.yaml
patches:
  - target:
      kind: DaemonSet
      name: metallb-speaker
    patch: |-
      - op: test
        path: /spec/template/spec/hostNetwork
        value: true
      - op: replace
        path: /spec/template/spec/hostNetwork
        value: false
      - op: test
        path: /spec/template/spec/containers/0/name
        value: speaker
      - op: remove
        path: /spec/template/spec/containers/0/livenessProbe
      - op: remove
        path: /spec/template/spec/containers/0/readinessProbe
```

```yaml
parameters:
  mutations:
    metallb-speaker-pod-network:
      match: {apiVersion: apps/v1, kind: DaemonSet, name: metallb-speaker}
      json6902:
        - {op: test, path: /spec/template/spec/hostNetwork, value: true}
        - {op: replace, path: /spec/template/spec/hostNetwork, value: false}
        - {op: test, path: /spec/template/spec/containers/0/name, value: speaker}
        - {op: remove, path: /spec/template/spec/containers/0/livenessProbe}
        - {op: remove, path: /spec/template/spec/containers/0/readinessProbe}
```

On kind, a speaker ran on each of the four nodes with its own pod IP.
Without a readiness probe, ready means that the container runs:

```text
metallb-speaker-6nsjd hostNetwork=false pod IP is the node IP: no ready=true restarts=0
metallb-speaker-6rr28 hostNetwork=false pod IP is the node IP: no ready=true restarts=0
metallb-speaker-8z7rr hostNetwork=false pod IP is the node IP: no ready=true restarts=0
metallb-speaker-hc622 hostNetwork=false pod IP is the node IP: no ready=true restarts=0
```

L2 mode answers ARP requests for the service address on the node's
interface, which a speaker in the pod network does not have. With an L2
pool from the kind network and an nginx LoadBalancer Service, the test
compared both settings from the host:

```text
speaker in the pod network: the LoadBalancer address from the host: not reachable
speaker in the host network (plain chart): the LoadBalancer address from the host: reachable
```

The test did not set up a BGP peer, so it shows that the speakers run in
the pod network, not that they announce routes over BGP from there.

## Consul Helm chart: tolerations on the hook Jobs {#consul-hook-job-tolerations}

[hashicorp/consul-k8s#4469](https://github.com/hashicorp/consul-k8s/issues/4469),
opened in January 2025 and at 7 thumbs up, asks for tolerations and a
nodeSelector on the Job that generates the gossip encryption key. When
every node carries a taint, that Job and tls-init stay Pending, and the
thread names a third Job, tls-init-cleanup. The workaround offered there is
to `helm pull` the chart and edit its templates, which a commenter who
installs from HashiCorp's repository cannot do. Pull request #4625, opened
in June 2025, adds the values and has had no review. In chart 2.0.4,
released on 11 September 2026, none of the three Jobs sets either field in
its pod spec, and 2.1.0-rc2 does not either. All three are Helm hooks, as
[`tls-init-job.yaml`](https://github.com/hashicorp/consul-k8s/blob/v2.0.4/charts/consul/templates/tls-init-job.yaml#L20-L23)
shows for tls-init:

```yaml
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "1"
    "helm.sh/hook-delete-policy":  hook-succeeded,before-hook-creation
```

The gossip key Job runs at the same hooks, tls-init-cleanup at
`pre-delete`. These values turn on TLS and the gossip key, and
`global.name` gives the Jobs the names from the issue:

```yaml
global:
  name: consul
  tls:
    enabled: true
  gossipEncryption:
    autoGenerate: true
```

The test tainted and labelled all three workers with
`example.com/purpose=infra` and set the chart's own tolerations and
nodeSelector values for the server, the connect injector and the webhook
cert manager. `global.acls.tolerations` reaches the
`consul-gateway-resources` Job, which a commenter also mentions, and the
two gateway cleanup Jobs, even with ACLs off. Those three have no
nodeSelector value. With the plain chart, both pre-install Jobs stayed
Pending:

```text
consul-tls-init-fh7nh: 0/4 nodes are available: 4 node(s) had untolerated taint(s). preemption: 0/4 nodes are available: 4 Preemption is not helpful for scheduling.
```

The three Jobs carry `app: consul` whatever the release is called, and
`component` with their own name, so one Kustomize target with a set-based
selector matches all three:

```yaml
resources:
  - helm.yaml
patches:
  - target:
      group: batch
      kind: Job
      labelSelector: app=consul,component in (tls-init,tls-init-cleanup,gossip-encryption-autogenerate)
    patch: |-
      - op: add
        path: /spec/template/spec/tolerations
        value:
          - key: example.com/purpose
            operator: Equal
            value: infra
            effect: NoSchedule
      - op: add
        path: /spec/template/spec/nodeSelector
        value:
          example.com/purpose: infra
```

mutate's `match` takes one value per key, so each Job gets a mutation of
its own, and the three share the operations through an inventory key:

```yaml
parameters:
  hook_scheduling:
    - op: add
      path: /spec/template/spec/tolerations
      value:
        - {key: example.com/purpose, operator: Equal, value: infra, effect: NoSchedule}
    - op: add
      path: /spec/template/spec/nodeSelector
      value:
        example.com/purpose: infra
  mutations:
    consul-tls-init:
      match: {apiVersion: batch/v1, kind: Job, labels: {app: consul, component: tls-init}}
      json6902: ${hook_scheduling}
    consul-tls-init-cleanup:
      match: {apiVersion: batch/v1, kind: Job, labels: {app: consul, component: tls-init-cleanup}}
      json6902: ${hook_scheduling}
    consul-gossip-encryption-autogenerate:
      match: {apiVersion: batch/v1, kind: Job, labels: {app: consul, component: gossip-encryption-autogenerate}}
      json6902: ${hook_scheduling}
```

Without a cluster to ask, `helm template` renders the chart's two
PodDisruptionBudgets as `policy/v1beta1`, which Kubernetes 1.25 removed,
and the first server-side dry run refused them. Both renders therefore
pass `--api-versions policy/v1/PodDisruptionBudget`, which Kapitan takes as
`api_versions` in `helm_params`.

### Helm hooks with the patched Jobs

`kubectl apply` of the whole render would also start tls-init-cleanup,
which deletes the Secrets `consul-ca-cert`, `consul-ca-key` and
`consul-server-cert`. The test applied the mutate output in the order of
`helm install`: the pre-install hooks, the templates, then the
post-install Job. The server and the connect injector became ready. The
pre-delete hooks, applied last as `helm uninstall` would run them, removed
the three Secrets. Every Job completed on a tainted worker:

```text
consul-tls-init node=cac-consul-worker2 taint=example.com/purpose=infra:NoSchedule complete=True
consul-gossip-encryption-autogenerate node=cac-consul-worker taint=example.com/purpose=infra:NoSchedule complete=True
consul-tls-init-cleanup node=cac-consul-worker2 taint=example.com/purpose=infra:NoSchedule complete=True
```

For `helm install` itself, Helm 4 passes hooks to the post-renderer
together with the templates. Helm 3 never did. With Helm 3.22.1 and the
same Kustomize patch as a post-renderer script, `helm template` printed
the three Jobs without the fields. A Helm 4 post-renderer is a plugin, and
this one runs the Kustomize patch from the directory it is given:

```yaml
name: kustomize-pr
version: 0.1.0
type: postrenderer/v1
apiVersion: v1
runtime: subprocess
runtimeConfig:
  platformCommand:
    - command: "${HELM_PLUGIN_DIR}/kustomize.sh"
```

```bash
#!/usr/bin/env bash
# stdin: Helm's render, hooks included. $1: the directory with kustomization.yaml.
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp "$1/kustomization.yaml" "$tmp/"
cat > "$tmp/helm.yaml"
kustomize build "$tmp"
```

```bash
helm plugin install ./kustomize-pr
helm install consul consul --repo https://helm.releases.hashicorp.com --version 2.0.4 \
  -n consul -f consul-values.yaml --post-renderer kustomize-pr --post-renderer-args "$PWD" --wait
```

The plugin's output equalled the Kustomize build. With Helm 4.3.1 on kind,
the release installed, and `helm uninstall` ran tls-init-cleanup, each Job
on a tainted worker:

```text
Successfully assigned consul/consul-gossip-encryption-autogenerate-jdm6k to cac-consul-worker
Successfully assigned consul/consul-tls-init-qt7ql to cac-consul-worker3
Successfully assigned consul/consul-tls-init-cleanup-wkt87 to cac-consul-worker
```

## APISIX ingress controller chart: pod labels {#apisix-ingress-controller-pod-labels}

[apache/apisix-helm-chart#978](https://github.com/apache/apisix-helm-chart/issues/978),
opened in June 2026 and at 11 thumbs up, asks for a `podLabels` value in
the apisix-ingress-controller chart, so that the controller's pods can
carry labels for observability, scheduling or policies. Nobody has
commented. The apisix chart in the same repository got `podLabels` through
pull request #965, merged on 30 September 2026. The controller chart takes
`deployment.podAnnotations`, but in 1.4.0, released on 17 September 2026,
[`deployment.yaml`](https://github.com/apache/apisix-helm-chart/blob/apisix-ingress-controller-1.4.0/charts/apisix-ingress-controller/templates/deployment.yaml#L42-L43)
gives the pod template the selector labels only:

```yaml
      labels:
        {{- include "apisix-ingress-controller-manager.selectorLabels" . | nindent 8 }}
```

The chart's `labelsOverride` replaces these selector labels, so a label
set there also lands in the Deployment's `spec.selector` and in the
selectors of both Services. Over the installed chart, the API server
refused the change:

```text
The Deployment "apisix-ingress-controller" is invalid: spec.selector: Invalid value: {"matchLabels":{"app.kubernetes.io/instance":"apisix-ingress-controller","app.kubernetes.io/name":"apisix-ingress-controller","team":"platform"}}: field is immutable
```

`add` on a path below the pod template's labels sets one label there and
leaves the selector alone:

```yaml
resources:
  - helm.yaml
patches:
  - target:
      group: apps
      kind: Deployment
      name: apisix-ingress-controller
    patch: |-
      - op: add
        path: /spec/template/metadata/labels/team
        value: platform
```

```yaml
parameters:
  mutations:
    apisix-pod-labels:
      match: {apiVersion: apps/v1, kind: Deployment, name: apisix-ingress-controller}
      json6902:
        - {op: add, path: /spec/template/metadata/labels/team, value: platform}
```

A key with a slash such as `example.com/team` goes into the path as
`example.com~1team`, and both tools then set the label `example.com/team`.
The chart generates its webhook certificate on every render, so the
comparison of the renders left out that Secret and the webhook
configuration's `caBundle`. `helm template` renders the chart's CRDs only
with `--include-crds`, which Kapitan's helm input passes by default. On
kind, the controller became ready, and its pod carries the label:

```text
apisix-ingress-controller-85b5bb8fb4-9m4kc labels: {"app.kubernetes.io/instance":"apisix-ingress-controller","app.kubernetes.io/name":"apisix-ingress-controller","pod-template-hash":"85b5bb8fb4","team":"platform"}
```

## Cilium Helm chart: ipFamilyPolicy on cilium-ingress {#cilium-ingress-ipfamilypolicy}

[cilium/cilium#27003](https://github.com/cilium/cilium/issues/27003),
opened in July 2023, asks for `ipFamilyPolicy` and `ipFamilies` on the
Service of Cilium's ingress controller. Without them the Service gets the
cluster's primary family only, so on a dual-stack cluster the Ingresses
answer on IPv4 or on IPv6, not on both. The maintainer youngnick wrote in
July 2023 that LB Service customisation was planned for that cycle, and
pinned the issue in December 2023. Chart 1.20.3, released on 15 October
2026,
[renders the Service](https://github.com/cilium/cilium/blob/v1.20.3/install/kubernetes/cilium/templates/cilium-ingress-service.yaml#L21-L51)
with its ports, type, `loadBalancerClass`,
`allocateLoadBalancerNodePorts`, `loadBalancerIP` and
`externalTrafficPolicy`, and 1.21.0-pre.3 renders the same. The chart has
this Service in shared mode only. In dedicated mode the operator creates a
Service per Ingress, which a patch of the chart does not reach.

The ingress controller needs Cilium's kube-proxy replacement, so the test
ran Cilium as the CNI of a dual-stack kind cluster without kube-proxy:

```yaml
kubeProxyReplacement: true
k8sServiceHost: cac-cilium-control-plane
k8sServicePort: 6443
ipam:
  mode: kubernetes
ipv6:
  enabled: true
ingressController:
  enabled: true
  loadbalancerMode: shared
```

```yaml
resources:
  - helm.yaml
patches:
  - target:
      kind: Service
      name: cilium-ingress
    patch: |-
      - op: add
        path: /spec/ipFamilyPolicy
        value: RequireDualStack
      - op: add
        path: /spec/ipFamilies
        value: [IPv4, IPv6]
```

```yaml
parameters:
  mutations:
    cilium-ingress-dual-stack:
      match: {apiVersion: v1, kind: Service, name: cilium-ingress}
      json6902:
        - {op: add, path: /spec/ipFamilyPolicy, value: RequireDualStack}
        - {op: add, path: /spec/ipFamilies, value: [IPv4, IPv6]}
```

The chart generates the Hubble certificates on every render, so the
comparison of the renders left out those Secrets. The plain chart gave the
Service one IPv4 cluster IP. The mutate output, applied over it, changed
the existing Service in place, and 60 seconds later the operator had not
reverted it:

```text
ipFamilyPolicy=SingleStack ipFamilies=["IPv4"] clusterIPs=["10.96.179.251"] loadBalancer=198.51.100.0
ipFamilyPolicy=RequireDualStack ipFamilies=["IPv4","IPv6"] clusterIPs=["10.96.179.251","fd00:10:96::b12c"] loadBalancer=198.51.100.0 2001:db8::
```

LB-IPAM had a pool with one block of each family from the documentation
ranges and gave the Service an address of each. An Ingress for an echo
backend then answered on all four addresses from a node, with `curl` in
the node's network namespace:

```text
10.96.179.251 from node: 200, from pod: 000
fd00:10:96::b12c from node: 200, from pod: 200
198.51.100.0 from node: 200, from pod: 000
2001:db8:: from node: 200, from pod: 200
```

From a pod, requests over IPv4 timed out on this test host, with the plain
chart as well and on an IPv4-only kind cluster too. The patch does not
cause it, and the test does not cover that path.

`ipFamilies` with both families needs a dual-stack cluster, whatever the
policy. On an IPv4-only kind cluster the server-side dry run refused the
patched Service:

```text
* spec.ipFamilyPolicy: Invalid value: "RequireDualStack": this cluster is not configured for dual-stack services
* spec.ipFamilies[1]: Invalid value: "IPv6": not configured on this cluster
```

With `PreferDualStack` it still refused `ipFamilies[1]`. `PreferDualStack`
without `ipFamilies` passed there and got IPv4 only.
