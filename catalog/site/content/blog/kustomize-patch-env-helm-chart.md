---
title: Kustomize patch env variable with valueFrom in a Helm chart
date: 2026-10-25
topics: [helm, kustomize, kapitan]
description: "Kustomize patch environment variable with valueFrom into Helm chart containers by name, and the same with Kapitan's mutate: KEDA HTTP add-on and Crossplane."
---

Many charts take extra environment variables as a map of names to values
and render each entry as `name` and `value`. A variable that comes from a
Secret, a ConfigMap or the downward API needs `valueFrom`, which such a map
cannot express. This post adds those entries to the rendered Deployments
instead, merged into the container by its name, first with a Kustomize
strategic merge patch over `helm template`, then with
[Kapitan](/glossary/#kapitan)'s [mutate](/generators/mutate/)
[generator](/glossary/#generator). The two cases come from open issues
against the KEDA HTTP add-on chart and the Crossplane chart.

Each patch was rendered from the chart version named in its section with
Helm 4.3.1, Kustomize 5.8.3, and Kapitan 0.36.3 with mutate 0.1.0, and the
result was installed on a kind cluster on Kubernetes 1.37.0. Both charts
come from HTTP chart repositories, and each downloaded package matched the
sha256 its repository's `index.yaml` lists. The guide
[Patch a Helm chart](/guides/patch-helm-chart/) compares the places such a
patch can live.

## KEDA HTTP add-on chart: env with valueFrom {#keda-http-add-on-env}

[kedacore/charts#761](https://github.com/kedacore/charts/issues/761) asked
in June 2025 for extra environment variables on the HTTP add-on's
interceptor, scaler and operator. Pull request #777, merged in October
2025, added `extraEnvs` to each, as a map of names to values. In July
2026 a commenter
[pointed out](https://github.com/kedacore/charts/issues/761#issuecomment-4871143127)
that a map cannot set variables from ConfigMaps, Secrets or the downward
API, gave `HOST_IP` from `status.hostIP` as the example, and proposed an
`env` list. Nobody has replied. Chart 0.16.0 renders the map in
[`interceptor/deployment.yaml`](https://github.com/kedacore/charts/blob/1acc1efb02bbe7d425e796ee527ae07714675b48/http-add-on/templates/interceptor/deployment.yaml#L124-L126):

```yaml
        {{- range $key, $value := .Values.interceptor.extraEnvs }}
        - name: {{ $key }}
          value: {{ $value | quote }}
```

Given the commenter's entry as a map, the chart quotes the map as a
string, and the container gets that text as the value:

```text
keda-add-ons-http: the value as an env entry: [{'name': 'HOST_IP', 'value': 'map[valueFrom:map[fieldRef:map[fieldPath:status.hostIP]]]'}]
```

KEDA's core chart 2.21.0 has an `env` list for the operator, the metrics
adapter and the webhooks. The add-on chart has none.

### Kustomize over helm template

```bash
helm template http-add-on keda-add-ons-http --repo https://kedacore.github.io/charts \
  --version 0.16.0 --namespace keda > helm.yaml
kustomize build .
```

with this `kustomization.yaml` next to `helm.yaml`:

```yaml
resources:
  - helm.yaml
patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: keda-add-ons-http-interceptor
        namespace: keda
      spec:
        template:
          spec:
            containers:
              - name: keda-add-ons-http-interceptor
                env:
                  - name: HOST_IP
                    valueFrom:
                      fieldRef:
                        fieldPath: status.hostIP
```

Kustomize knows the schema of a Deployment, so the strategic merge finds the
container by `name` and the entry by its `name` within `env`, and keeps the
chart's other entries. It puts the new entry first in the list. Apart from
that entry, and from fields whose value is null, which Kustomize drops, the
output equalled the plain render.

### Kapitan's mutate

The [class](/glossary/#class) pins the chart by version:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: helm
        source: https://kedacore.github.io/charts
        chart_name: keda-add-ons-http
        version: 0.16.0
        output_path: charts/keda-add-ons-http
    compile:
      - input_type: helm
        input_paths: [charts/keda-add-ons-http]
        output_path: keda-add-ons-http
        helm_params:
          name: http-add-on
          namespace: keda
```

`merge` alone would replace the `containers` list with the one entry of the
patch. `merge_lists` merges `containers` and `env` by `name` instead, at any
depth:

```yaml
parameters:
  mutations:
    interceptor-host-ip:
      match: {apiVersion: apps/v1, kind: Deployment, name: keda-add-ons-http-interceptor}
      merge_lists: {containers: name, env: name}
      merge:
        spec:
          template:
            spec:
              containers:
                - name: keda-add-ons-http-interceptor
                  env:
                    - name: HOST_IP
                      valueFrom:
                        fieldRef: {fieldPath: status.hostIP}
```

The [target](/glossary/#target) adds mutate as a second compile entry on
the chart's `output_path`, as the guide shows. mutate appends the entry at
the end of `env`, and nothing else in the render changed.

### On kind

The add-on needs KEDA itself, so the test installed KEDA's chart 2.21.0
first. All six Deployments became Available, the interceptor Pod became
Ready, and the live Pod carries the entry, with the `apiVersion` the API
server fills in:

```text
{"name":"HOST_IP","valueFrom":{"fieldRef":{"apiVersion":"v1","fieldPath":"status.hostIP"}}}
```

The Kustomize output passed a server-side dry run against the same
cluster.

## Crossplane Helm chart: env from a Secret {#crossplane-env-secret}

[crossplane/crossplane#7792](https://github.com/crossplane/crossplane/issues/7792),
opened in September 2026, needs `HTTP_PROXY` for every Crossplane pod from a
corporate egress proxy whose URL carries a password. `extraEnvVarsCrossplane`
takes literals only, so the password ends up in plain text in the values
repository, which the reporter's scanner flags. Another user offered to
implement `valueFrom` support. No pull request or maintainer reply exists
yet. Chart 2.4.2 renders the map in
[`deployment.yaml`](https://github.com/crossplane/crossplane/blob/v2.4.2/cluster/charts/crossplane/templates/deployment.yaml#L222-L224):

```yaml
        {{- range $key, $value := .Values.extraEnvVarsCrossplane }}
          - name: {{ $key | replace "." "_" }}
            value: {{ $value | quote }}
```

With the issue's entry as a map, the chart renders it as a string like
the KEDA chart does:

```text
crossplane: the value as an env entry: [{'name': 'HTTP_PROXY', 'value': 'map[valueFrom:map[secretKeyRef:map[key:url name:http-proxy]]]'}]
```

### Kustomize over helm template

```bash
helm template crossplane crossplane --repo https://charts.crossplane.io/stable \
  --version 2.4.2 --namespace crossplane-system > helm.yaml
kustomize build .
```

with this `kustomization.yaml`:

```yaml
resources:
  - helm.yaml
patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: crossplane
        namespace: crossplane-system
      spec:
        template:
          spec:
            containers:
              - name: crossplane
                env:
                  - name: HTTP_PROXY
                    valueFrom:
                      secretKeyRef:
                        name: http-proxy
                        key: url
```

The Deployments `crossplane` and `crossplane-rbac-manager` both name their
container `crossplane`, so the patch selects the Deployment by name. As
with the KEDA chart, the entry went first and nothing else changed.

### Kapitan's mutate

The class pins chart 2.4.2 like the KEDA one, and the mutation has the same
shape:

```yaml
parameters:
  mutations:
    crossplane-http-proxy:
      match: {apiVersion: apps/v1, kind: Deployment, name: crossplane}
      merge_lists: {containers: name, env: name}
      merge:
        spec:
          template:
            spec:
              containers:
                - name: crossplane
                  env:
                    - name: HTTP_PROXY
                      valueFrom:
                        secretKeyRef: {name: http-proxy, key: url}
```

### On kind

The Secret `http-proxy` did not exist when the mutated output was applied,
so the kubelet could not start the container:

```text
secret "http-proxy" not found
```

Once the Secret existed, with an `http://` URL as `url`, both Deployments
became Available, and the live Pod carries the reference:

```text
{"name":"HTTP_PROXY","valueFrom":{"secretKeyRef":{"key":"url","name":"http-proxy"}}}
```

The proxy in the Secret does not exist, and Crossplane still reached the
API server: Go programs use `HTTP_PROXY` for `http://` URLs only, and the
API server is reached over HTTPS. The Kustomize output passed a
server-side dry run.

## When the container name does not match

Both tools merge by the name they are given and add a new list entry when
no container has it. With the KEDA patch changed to the name
`interceptor`, the mutate compile and the Kustomize build both passed, and
each Deployment then had a second container with nothing but a name and
`env`. The API server refused both, mutate's output, where the extra
container comes second, and Kustomize's, where it comes first:

```text
The Deployment "keda-add-ons-http-interceptor" is invalid: spec.template.spec.containers[1].image: Required value
The Deployment "keda-add-ons-http-interceptor" is invalid: spec.template.spec.containers[0].image: Required value
```

mutate's `expects` counts the matched documents, here the one Deployment,
so it does not catch a container name that a chart release changes. A
server-side dry run in CI does.
