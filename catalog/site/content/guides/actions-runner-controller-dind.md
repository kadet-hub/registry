---
title: Actions Runner Controller dind image from your own registry
date: 2026-10-21
topics: [helm, kustomize, kapitan, ci]
description: "GitHub Actions Runner Controller dind image from a mirror or air-gapped registry: gha-runner-scale-set patched with Kustomize or Kapitan, tested on kind."
---

With `containerMode.type: dind`, the gha-runner-scale-set chart of
actions-runner-controller (ARC) adds a Docker daemon to every runner pod.
The chart fixes that container's image as `docker:dind`, which the kubelet
pulls from Docker Hub, and the current release, 0.15.0 from 1 October 2026,
has no value to change it. This post replaces the image on the rendered
manifests, first with Kustomize over `helm template`, then with
[Kapitan](/glossary/#kapitan)'s [mutate](/generators/mutate/)
[generator](/glossary/#generator), for a pull-through mirror and for a
registry inside an air-gapped network.

Each patch was rendered from the 0.15.0 chart with Helm 4.3.1, Kustomize
5.8.3, and Kapitan 0.36.3 with mutate 0.1.0, and applied to a kind cluster
on Kubernetes 1.37.0. The guide [Patch a Helm chart](/guides/patch-helm-chart/)
compares Helm post-renderers, Kustomize, Flux and Argo CD as places for such
a patch.

## The dind image in gha-runner-scale-set {#arc-dind-image}

[actions/actions-runner-controller#3997](https://github.com/actions/actions-runner-controller/issues/3997),
opened in March 2025 and at 28 thumbs up, asks for a way to pull the dind
image from your own registry instead of Docker Hub, whose pull limits for
unauthenticated users it cites. Pull request #3851, which made the image
configurable, was closed unmerged in August 2025. Closing the related #4219,
the ARC maintainer nikola-jokic
[wrote](https://github.com/actions/actions-runner-controller/pull/4219#issuecomment-3236359120)
that "we don't want to create a patch that will simply modify the dind
image" and pointed to the way the chart's `values.yaml` documents: leave
`containerMode` empty and write the whole runner pod spec into `template`
yourself. That spec is two init containers, the runner container and three
volumes, which you then keep in step with the chart.

In 0.15.0 the image is a literal in
[`_helpers.tpl`](https://github.com/actions/actions-runner-controller/blob/gha-runner-scale-set-0.15.0/charts/gha-runner-scale-set/templates/_helpers.tpl#L263-L264):

```yaml
{{- define "gha-runner-scale-set.dind-container" -}}
image: docker:dind
```

The chart `gha-runner-scale-set-experimental`, published next to it as
0.15.0, has the value `runner.dind.container.image`, and renders a mirror
image with it. Its release notes say experimental charts "are not supported
for production workloads and may be modified or republished without
notice."

### Where the chart puts dind

[`autoscalingrunnerset.yaml`](https://github.com/actions/actions-runner-controller/blob/gha-runner-scale-set-0.15.0/charts/gha-runner-scale-set/templates/autoscalingrunnerset.yaml#L265)
tests `ge (.Capabilities.KubeVersion.Minor | int) 29`. From Kubernetes 1.29,
which turned on [sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
by default, dind is the second init container, with `restartPolicy: Always`
and a startup probe that runs `docker info`, so the runner container starts
once dockerd answers. Below 1.29 dind is the second entry in `containers`.

`helm template` has no cluster to read the version from and uses its
built-in default, v1.37.0 for Helm 4.3.1. For an older cluster, pass
`--kube-version`. A patch has to look for dind in the list the chart
rendered for that version.

### Kustomize over helm template

The values select dind mode and pin the runner image by tag and
[digest](/glossary/#digest); the chart uses the image of the container named
`runner` for the init container that copies the runner's externals, too.
`controllerServiceAccount` names the ServiceAccount of a controller
installed as release `arc` in `arc-systems`. Without it the chart looks up
the controller Deployment in the cluster, and `helm template`, which has
none, fails with `No gha-rs-controller deployment found`.

```yaml
githubConfigUrl: https://github.com/example-org
githubConfigSecret: arc-github
controllerServiceAccount:
  namespace: arc-systems
  name: arc-gha-rs-controller
containerMode:
  type: dind
template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:2.338.0@sha256:4ffadc0002b2581327e06101fc8c06cd189232baf79fe561fac9caeb76f5e807
        command: ["/home/runner/run.sh"]
```

Render the chart and build the patch over the output:

```bash
helm template arc-runners oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
  --version 0.15.0 --namespace arc-runners -f values.yaml --kube-version 1.37.0 > helm.yaml
kustomize build .
```

with this `kustomization.yaml` next to `helm.yaml`:

```yaml
resources:
  - helm.yaml
images:
  - name: docker
    newName: mirror.gcr.io/library/docker
    newTag: 29.9.1-dind
    digest: sha256:3e5756e2b6dad6a5f1f5deacf0a19f9eaa2581b76ae092b2d4a118162e1d4d4e
```

Kustomize's `images` transformer looks for `containers` and
`initContainers` at any depth of any object, so it finds dind in the
AutoscalingRunnerSet, a custom resource, in both layouts. The test
rendered the chart for 1.37.0 and for 1.28.0, and in both outputs the
dind image was the only field of the AutoscalingRunnerSet that changed. A strategic merge patch is no
alternative here: Kustomize has no schema for the AutoscalingRunnerSet and
replaces the whole `initContainers` list, so a patch that names only dind
and its image leaves a list with that one entry, without
`init-dind-externals` and without dind's arguments and `privileged`.

### Kapitan's mutate

A [class](/glossary/#class) pins the chart by version and by the digest of
its OCI artifact, renders it with the same values file and passes the
Kubernetes version to Helm:

```yaml
parameters:
  kube_version: 1.37.0
  kapitan:
    dependencies:
      - type: helm
        source: oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set@sha256:bdfdad17cf8e45ae064c73ed6764f0c75d4bf71a6e2912e6363a43d6dfc787de
        chart_name: gha-runner-scale-set
        version: 0.15.0
        output_path: charts/gha-runner-scale-set
    compile:
      - input_type: helm
        input_paths: [charts/gha-runner-scale-set]
        output_path: gha-runner-scale-set
        helm_values_files: [values.yaml]
        helm_params:
          name: arc-runners
          namespace: arc-runners
          kube_version: ${kube_version}
```

mutate's `images` action covers Pods and the Pod templates of workload
kinds, not custom resources, so the mutation is a JSON Patch:

```yaml
parameters:
  mutations:
    dind-image:
      match: {apiVersion: actions.github.com/v1alpha1, kind: AutoscalingRunnerSet, name: arc-runners}
      json6902:
        - {op: test, path: /spec/template/spec/initContainers/1/name, value: dind}
        - op: replace
          path: /spec/template/spec/initContainers/1/image
          value: mirror.gcr.io/library/docker:29.9.1-dind@sha256:3e5756e2b6dad6a5f1f5deacf0a19f9eaa2581b76ae092b2d4a118162e1d4d4e
```

`test` fails the compile unless the second init container is dind, and
`replace` sets its image. The [target](/glossary/#target) adds mutate as a
second compile entry on the chart's `output_path`, as the guide shows. For a
cluster below 1.29 the class below sets the Kubernetes version and patches
`containers` instead:

```yaml
parameters:
  kube_version: 1.28.0
  mutations:
    dind-image:
      match: {apiVersion: actions.github.com/v1alpha1, kind: AutoscalingRunnerSet, name: arc-runners}
      json6902:
        - {op: test, path: /spec/template/spec/containers/1/name, value: dind}
        - op: replace
          path: /spec/template/spec/containers/1/image
          value: mirror.gcr.io/library/docker:29.9.1-dind@sha256:3e5756e2b6dad6a5f1f5deacf0a19f9eaa2581b76ae092b2d4a118162e1d4d4e
```

Both mutated renders produced the same AutoscalingRunnerSet as Kustomize.
The first mutation on a render for 1.28.0, where dind is not an init container,
stops the compile:

```text
mutate: mutation dind-image: gha-runner-scale-set/templates/autoscalingrunnerset.yaml: json6902 path '/spec/template/spec/initContainers/1/name' does not exist
```

Kapitan's helm compile entry also accepts a `kube_version` key of its own,
not the one under `helm_params`. Kapitan 0.36.3
[passes it to Helm](https://github.com/kapicorp/kapitan/blob/v0.36.3/kapitan/inputs/helm.py#L63-L64)
as `--api-versions`, which leaves `.Capabilities.KubeVersion` at Helm's
default: with `kube_version: 1.28.0` on the entry, dind was still rendered
as an init container.

### On kind

The kind cluster got the four CRDs of the controller chart
gha-runner-scale-set-controller 0.15.0 and the mutated output of the
scale-set chart. The API server accepted both Kustomize outputs and the
mutated 1.28.0 output in a server-side dry run, and stored the
AutoscalingRunnerSet with these init containers (name, image,
`restartPolicy`):

```text
init-dind-externals	ghcr.io/actions/actions-runner:2.338.0@sha256:4ffadc0002b2581327e06101fc8c06cd189232baf79fe561fac9caeb76f5e807
dind	mirror.gcr.io/library/docker:29.9.1-dind@sha256:3e5756e2b6dad6a5f1f5deacf0a19f9eaa2581b76ae092b2d4a118162e1d4d4e	Always
```

The controller creates runner pods only for a scale set registered with
GitHub, so the test built a Pod from the stored `spec.template` and
replaced the runner's command with `docker version` followed by a sleep.
The Pod became Ready. The kubelet reported the dind image as pulled from
the mirror, with the digest of the patch:

```text
dind	mirror.gcr.io/library/docker@sha256:3e5756e2b6dad6a5f1f5deacf0a19f9eaa2581b76ae092b2d4a118162e1d4d4e	started=true
```

and the runner container, which started after dind's startup probe, printed
the daemon's version:

```text
server 29.9.1
```

### Air-gapped registry

`mirror.gcr.io` serves Google's cached copies of Docker Hub images, and for
this tag it returned the same index digest as Docker Hub. In a network
without that access, copy the image into your registry by digest:

```bash
oras cp -r mirror.gcr.io/library/docker:29.9.1-dind@sha256:3e5756e2b6dad6a5f1f5deacf0a19f9eaa2581b76ae092b2d4a118162e1d4d4e \
  registry.example.internal/library/docker:29.9.1-dind
```

`oras cp` copies the image index with every platform, so the copy has the
same digest, `sha256:3e5756e2…`, and the patch needs only the new registry
in `newName`, or in the mutation's `value`. In the test, oras 1.3.5 copied
the index to a local registry, which then served it with that digest and
the platforms `linux/amd64`, `linux/arm64v8`, `linux/armv6` and
`linux/armv7`.
