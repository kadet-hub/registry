---
title: "Kustomize delete resource: Kyverno PDBs and ESO webhooks"
date: 2026-10-24
topics: [helm, kustomize, kapitan]
description: "Kustomize patch delete resource on a rendered Helm chart, and the same with Kapitan's mutate: Kyverno's forced PDBs and External Secrets' webhooks, on kind."
---

Some Helm charts render an object you need to own yourself and offer no
value to leave it out. This post covers two such cases from open issues:
the Kyverno chart creates a PodDisruptionBudget for every controller that
runs more than one replica, and the External Secrets chart renders its two
ValidatingWebhookConfigurations whenever it renders the webhook. In both,
the object is deleted from the rendered manifests, first with a Kustomize
patch over `helm template`, then with [Kapitan](/glossary/#kapitan)'s
[mutate](/generators/mutate/) [generator](/glossary/#generator).

Each patch was rendered from the chart version named in its section with
Helm 4.3.1, Kustomize 5.8.3, and Kapitan 0.36.3 with mutate 0.1.0, and the
result was installed on a kind cluster on Kubernetes 1.37.0. The guide
[Patch a Helm chart](/guides/patch-helm-chart/) compares the places such a
patch can live.

## Kyverno Helm chart: PodDisruptionBudgets with more than one replica {#kyverno-pdb}

[kyverno/kyverno#11469](https://github.com/kyverno/kyverno/issues/11469),
opened in October 2024, reports that the chart's PodDisruptionBudgets cannot
be turned off. The reporter wants to supply PDBs of their own instead. The
maintainer realshuting
[asked](https://github.com/kyverno/kyverno/issues/11469#issuecomment-2437149508)
the authors of the change that introduced the behaviour whether there was a
reason to keep PDBs on for more than one replica, and the question is
unanswered. In chart 3.9.2, published to the chart repository and to
ghcr.io on 21 October 2026, the PDB template of each of the four
controllers has the same condition, here from
[`admission-controller/poddisruptionbudget.yaml`](https://github.com/kyverno/kyverno/blob/kyverno-chart-3.9.2/charts/kyverno/templates/admission-controller/poddisruptionbudget.yaml#L1):

```yaml
{{- if or .Values.admissionController.podDisruptionBudget.enabled (gt (int .Values.admissionController.replicas) 1) -}}
```

`podDisruptionBudget.enabled: false` is the default, and with more than one
replica the `or` ignores it. The chart's `values.yaml` says so: "Will
always be enabled if replicas > 1. This non-declarative behavior should
ideally be avoided, but changing it now would be breaking." With these
values the chart rendered four PDBs, and the same four with
`podDisruptionBudget.enabled=false` set for every controller:

```yaml
admissionController:
  replicas: 3
backgroundController:
  replicas: 2
cleanupController:
  replicas: 2
reportsController:
  replicas: 2
```

All four carry the label `app.kubernetes.io/part-of: kyverno`. Its value is
the chart's fullname, so it follows the release name: release `policy`
gives `policy-kyverno`.

### Kustomize over helm template

```bash
helm template kyverno oci://ghcr.io/kyverno/charts/kyverno --version 3.9.2 \
  --namespace kyverno -f kyverno-values.yaml > helm.yaml
kustomize build .
```

with this `kustomization.yaml` next to `helm.yaml`:

```yaml
resources:
  - helm.yaml
patches:
  - target:
      kind: PodDisruptionBudget
      labelSelector: app.kubernetes.io/part-of=kyverno
    patch: |-
      $patch: delete
      apiVersion: policy/v1
      kind: PodDisruptionBudget
      metadata:
        name: ignored
```

With a `target`, Kustomize applies the patch to every object the selector
matches, here the four PDBs, and the `metadata.name` in the patch is
required but not used. The output was the render without the four PDBs and
otherwise unchanged. A selector that matches nothing is not an error: over
a render for release `policy`, the build passed and kept all four PDBs.

### Kapitan's mutate

The [class](/glossary/#class) pins the chart by version and by the
[digest](/glossary/#digest) of its OCI artifact, and reads the same values
file:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: helm
        source: oci://ghcr.io/kyverno/charts/kyverno@sha256:83054f30148c3cfc001087c1f5772eda7c7224e9b74b7f0e70c39c9cafe009d1
        chart_name: kyverno
        version: 3.9.2
        output_path: charts/kyverno
    compile:
      - input_type: helm
        input_paths: [charts/kyverno]
        output_path: kyverno
        helm_values_files: [kyverno-values.yaml]
        helm_params:
          name: kyverno
          namespace: kyverno
```

The mutation deletes the PDBs by label and states how many it expects:

```yaml
parameters:
  mutations:
    no-pdbs:
      match: {apiVersion: policy/v1, kind: PodDisruptionBudget, labels: {app.kubernetes.io/part-of: kyverno}}
      delete: true
      expects: 4
```

The [target](/glossary/#target) adds mutate as a second compile entry on
the chart's `output_path`, as the guide shows. Each PDB file became a
single comment line, and the rest of the render was unchanged. With the
class changed to release `policy`, the compile stops:

```text
mutate: mutation no-pdbs: expects 4, matched 0
```

### Helm hooks in the rendered output

`helm template` also renders the chart's hooks: a post-upgrade Job
`kyverno-migrate-resources` with its ServiceAccount, ClusterRole and
ClusterRoleBinding, and the pre-delete Jobs `kyverno-scale-to-zero` and
`kyverno-rm-webhooks`. `helm install` runs each of them only at its hook.
`kubectl apply` of the whole output runs them at once, and on kind the
Job `kyverno-scale-to-zero` left every controller at zero replicas:

```text
kyverno-admission-controller    0/0     0            0           5s
kyverno-background-controller   0/0     0            0           5s
```

The test therefore applied every object except those with a
`helm.sh/hook` annotation, as `helm install` would. A tool that maps Helm
hooks to its own, as Argo CD does, needs no such filter.

### On kind

The four controllers, with three admission controller replicas and two of
each other, all reported Available, and the namespace held no
PodDisruptionBudget. The Kustomize output, without hooks, passed a
server-side dry run. To check that Kyverno still enforces policies, the
test added a ValidatingPolicy that requires the label `team` on ConfigMaps
in the namespace `demo`. A ConfigMap without it was refused:

```text
error: failed to create configmap: admission webhook "vpol.validate.kyverno.svc-fail" denied the request: Policy require-team-label failed: label team is required
```

## External Secrets Helm chart: the ValidatingWebhookConfigurations {#external-secrets-webhooks}

[external-secrets/external-secrets#6961](https://github.com/external-secrets/external-secrets/issues/6961),
opened in September 2026, asks for a value that leaves the two
ValidatingWebhookConfigurations out of the chart while it still deploys the
webhook. The reporter applies cluster-scoped objects from a separate chart
and wants the configurations to come from there, with the
external-secrets chart used as published. The maintainers asked for the
use case. alekc
[called it](https://github.com/external-secrets/external-secrets/issues/6961#issuecomment-5868041712)
"a very niche usecase which would be best suited by a custom helm chart for
your org" and wrote that such a toggle "would mean allowing users to deploy
a broken (unless they take separate steps outside of the helm chart)
deployment of eso". evrardj-roche closed the pull request with the toggle
"temporarily until we have clarified the multi-tenant story" and pointed
to the multi-namespace design in #7023.

In chart 2.13.0, the release of 16 October 2026,
[`validatingwebhook.yaml`](https://github.com/external-secrets/external-secrets/blob/helm-chart-2.13.0/deploy/charts/external-secrets/templates/validatingwebhook.yaml#L1-L5)
renders `secretstore-validate` and `externalsecret-validate` under the same
condition as the webhook itself:

```yaml
{{- if .Values.webhook.create }}
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: secretstore-validate
```

`webhook.create=false` removes the configurations and also the webhook's
Deployment, Service, Secret and ServiceAccount. The configurations have
`failurePolicy: Fail` and no `caBundle`. cert-controller adds it, and its
[ClusterRole](https://github.com/external-secrets/external-secrets/blob/helm-chart-2.13.0/deploy/charts/external-secrets/templates/cert-controller-rbac.yaml#L38-L47)
allows it to update only these two names:

```yaml
  - apiGroups:
    - "admissionregistration.k8s.io"
    resources:
    - "validatingwebhookconfigurations"
    resourceNames:
    - "secretstore-validate"
    - "externalsecret-validate"
    verbs:
    - "update"
    - "patch"
```

### Kustomize over helm template

```bash
helm template external-secrets oci://ghcr.io/external-secrets/charts/external-secrets \
  --version 2.13.0 --namespace external-secrets > helm.yaml
kustomize build .
```

with this `kustomization.yaml`:

```yaml
resources:
  - helm.yaml
patches:
  - target:
      kind: ValidatingWebhookConfiguration
      labelSelector: external-secrets.io/component=webhook
    patch: |-
      $patch: delete
      apiVersion: admissionregistration.k8s.io/v1
      kind: ValidatingWebhookConfiguration
      metadata:
        name: ignored
```

The label `external-secrets.io/component: webhook` is also on the webhook's
Service and Secret, so the target names the kind as well. The output
was the render without the two configurations and otherwise unchanged.

### Kapitan's mutate

The class pins chart 2.13.0 by OCI digest like the Kyverno one, and the
mutation expects exactly the two configurations:

```yaml
parameters:
  mutations:
    no-validating-webhooks:
      match: {apiVersion: admissionregistration.k8s.io/v1, kind: ValidatingWebhookConfiguration, labels: {external-secrets.io/component: webhook}}
      delete: true
      expects: 2
```

### On kind

Without the configurations, the controller and the webhook Deployments
became Available, and cert-controller did not become Ready. Its readiness
probe kept failing with HTTP status 500:

```text
external-secrets-cert-controller-56d7b45fc5-btm8q ready=false restarts=0
```

With no webhook registered, a SecretStore whose fake
provider has an empty key was accepted. The test then applied the two
configurations as the plain render has them, names and labels included,
standing in for the separate chart. cert-controller injected the CA and
became Ready:

```text
secretstore-validate caBundle bytes: 1196
externalsecret-validate caBundle bytes: 1196
```

A valid SecretStore passed the webhook, which added its warning about the
fake provider, and the one with the empty key was now refused:

```text
Error from server (Forbidden): error when creating "eso-store-invalid.yaml": admission webhook "validate.secretstore.external-secrets.io" denied the request: key must be set in data 0
```

The deletion is half of the change the issue asks for. The other chart has
to apply both configurations with these names, or cert-controller cannot
update them and stays unready.
