---
title: "Patch a Helm chart: post-renderers, Kustomize and Kapitan"
layout: prose
description: "Patch a Helm chart without forking it: Helm post-renderers, Kustomize, Flux and Argo CD compared with Kapitan's mutate generator, checked on kind."
---

A Helm chart exposes what its templates read from `values.yaml`. A field
the chart does not template, an image pinned by digest instead of a tag, an
annotation on every Service, or an object you do not want deployed at all
leaves two choices: fork the chart and carry the change through every
upgrade, or patch the rendered manifests. This guide compares where such a
patch can live, then shows [Kapitan](/glossary/#kapitan)'s
[mutate](/generators/mutate/) [generator](/glossary/#generator) patching
podinfo's chart. The code is
[`helm-mutate`](https://github.com/kadet-hub/examples/tree/main/helm-mutate)
in kadet-hub/examples, and a CI job fails unless every patch below is in
the output and the result deploys with `kubectl apply`, Argo CD and Flux.

## Helm post-renderers

A post-renderer receives the manifests Helm rendered and returns the ones
Helm installs, for `install`, `upgrade` and `template`
([post rendering](https://helm.sh/docs/topics/advanced/#post-rendering)).
Helm itself does not patch anything: the post-renderer is a program you
write or install, often a wrapper around `kustomize`.

Helm 4 changed how it is called. `--post-renderer` now takes the name of a
plugin of type `postrenderer/v1`, not a path to an executable
([Helm 4 overview](https://helm.sh/docs/overview/),
[migrating plugins](https://helm.sh/docs/plugins/migrate/)). Helm 4.3.0
rejects a script path with `plugin: {Name:./pr.sh Type:postrenderer/v1} not
found`, so a Helm 3 pipeline that passed a script needs it packaged as a
plugin with a `plugin.yaml` and installed with `helm plugin install` on
every machine that renders the release. Helm 4 also sends chart hooks to the
post-renderer together with the templates by default, which Helm 3 never
did. Helm's documentation adds that everyone who changes a release has to
use the same post-renderer.

## Kustomize with helmCharts

Kustomize's `helmCharts` field runs `helm` as a subprocess to inflate a
chart, and the result goes through Kustomize's `patches` and `images`
transformers like any other resource. `kustomize build` refuses the field
without `--enable-helm`. Kustomize's own example advises against it in
production and recommends keeping a locally inflated copy of the chart
instead
([chart example](https://github.com/kubernetes-sigs/kustomize/blob/kustomize/v5.8.3/examples/chart.md)).

A Kustomize patch also does not say how many objects it expects to change.
With the Kustomize built into kubectl 1.37.1 (v5.8.1), a JSON patch whose
`target` selects a Deployment that does not exist builds without an error
and changes nothing; a strategic merge patch that names a missing object
fails with `no resource matches strategic merge patch`. A chart upgrade
that renames an object therefore drops a `target` patch silently.

## Flux and Argo CD

Flux's HelmRelease takes `spec.postRenderers`, a list of Kustomize `patches`
and `images` that helm-controller applies in order and stores with the
release
([HelmRelease](https://github.com/fluxcd/helm-controller/blob/v1.6.5/docs/spec/v2/helmreleases.md#post-renderers)).
No plugin is needed, but the patch runs inside the cluster: the patched
manifests exist in the Helm release, not in a file you review before the
merge.

Argo CD renders Helm charts natively and Kustomize directories natively, but
not a Kustomize directory that inflates a chart: `--enable-helm` is not part
of its Kustomize options. Either `kustomize.buildOptions: --enable-helm` in
`argocd-cm` turns it on for every Kustomize application, or a config
management plugin does the rendering
([Kustomizing Helm charts](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/user-guide/kustomize.md#kustomizing-helm-charts)).
An Application can also carry inline `kustomize.patches`.

All four keep the chart unforked. They differ in where the patch runs and
where its result can be read: on the machine that runs Helm or Kustomize,
or only inside the cluster.

## Patching at compile time with mutate

Kapitan renders a chart with its `helm` input, which runs `helm template`
and writes the manifests as files. The mutate generator is a second compile
entry on the same `output_path` that rewrites those files in place, so the
patched manifests are plain YAML in `compiled/`, readable in a pull request
and deployable by any tool that applies files.

The example's [class](/glossary/#class) pins the chart through Kapitan's
`helm` dependency and renders it:

```yaml
# inventory/classes/podinfo.yml
parameters:
  kapitan:
    dependencies:
      - type: helm
        source: oci://ghcr.io/stefanprodan/charts/podinfo@sha256:ff3d3e14728f75476ed4d43c14f80d52d81d36bc16906843463d464c6146f0d8
        chart_name: podinfo
        version: 6.15.0
        output_path: charts/podinfo
    compile:
      - input_type: helm
        input_paths: [charts/podinfo]
        output_path: podinfo
        helm_params:
          name: podinfo
          namespace: podinfo
          skip_tests: false
```

Kapitan's `helm` dependency has no digest field of its own; it hands the
source and version to `helm pull`, and Helm 4.3.0 fails with `chart
reference digest mismatch` when the tag points to another
[digest](/glossary/#digest). Kapitan passes `--skip-tests` by default;
`skip_tests: false` renders the chart's three helm test Pods so the example
has objects to delete.

The [target](/glossary/#target) adds mutate, pinned by version and digest
like every kadet-hub generator, and the mutations, a map keyed by id:

```yaml
# inventory/targets/podinfo.yml
parameters:
  kapitan:
    compile:
      - input_type: kadet
        input_paths: [lib/mutate]
        output_path: podinfo
        output_type: plain
        input_params:
          mutations: ${mutations}
  mutations:
    pin-image:
      match: {kind: Deployment, name: podinfo}
      images:
        ghcr.io/stefanprodan/podinfo:
          digest: sha256:ec73780a8425f59ea49f5bc8cdff0d598805a224fbaa1f86c67a244f250fa9da
    harden:
      match: {kind: Deployment, name: podinfo}
      merge_lists: {containers: name}
      merge:
        spec:
          template:
            spec:
              containers:
                - name: podinfo
                  securityContext:
                    allowPrivilegeEscalation: false
                    capabilities: {drop: [ALL]}
                    readOnlyRootFilesystem: true
                    runAsNonRoot: true
                    runAsUser: 65534
                    seccompProfile: {type: RuntimeDefault}
                  resources:
                    limits: {memory: 64Mi}
    service-owner:
      match: {kind: Service}
      merge:
        metadata:
          annotations:
            example.com/owner: platform
    replicas:
      match: {kind: Deployment, name: podinfo}
      json6902:
        - {op: test, path: /spec/replicas, value: 1}
        - {op: replace, path: /spec/replicas, value: 2}
    no-test-pods:
      match: {kind: Pod, labels: {app.kubernetes.io/name: podinfo}}
      delete: true
```

`output_type: plain` is required: with the default `yaml` Kapitan would
write `deployment.yaml.yaml` next to the unpatched original, and mutate
fails the compile instead. Because mutations are a map, another class or a
target adds its own or overrides one by id; a list in the
[inventory](/glossary/#inventory) would be appended to.

### What each action does

`match` compares `apiVersion`, `kind`, `name`, `namespace` and `labels`
exactly, all of them at once. `kind: "*"` matches every kind and keeps the
other keys in force. A document without `metadata.namespace` does not match
a `namespace` key, which matters for charts that leave the namespace to
`helm --namespace`. The test Pods' names end in five random characters, so
`no-test-pods` matches them by kind and label.

`merge` is a JSON Merge Patch (RFC 7386): maps merge, `null` removes a key,
lists replace. A merge of `containers` alone would replace the chart's
container list with the one container in the patch. `merge_lists:
{containers: name}` merges the list by the `name` key instead, so `harden`
adds `securityContext` and a memory limit to the container named `podinfo`
and keeps its command, probes, env and the chart's resource requests.

`json6902` applies JSON Patch (RFC 6902) operations in order. The `test` in
`replicas` fails the compile if the chart's default stops being one replica,
instead of overwriting a value the chart maintainers changed on purpose.
`images` follows Kustomize's `images` semantics on the containers and init
containers of Pods and Pod templates; `digest` drops the tag. `delete`
removes the matched documents. Mutations run in sorted id order, deletes
after everything else.

Every mutation expects to change at least one document unless it sets
`expects` to `"0+"` or an exact count. The check adds a mutation for a
Deployment named `podinfo-frontend` to a copy of the inventory and expects
the compile to fail with:

```
mutate: mutation renamed: expects 1+, matched 0
```

That is the failure a chart upgrade that renames an object produces, where
a Kustomize `target` patch would apply to nothing.

### The output

The check renders the chart once without mutate (target `helm`) and diffs
it against the mutated target, with both sides loaded and dumped again with
sorted keys:

```diff
 spec:
-  replicas: 1
+  replicas: 2
...
-        image: ghcr.io/stefanprodan/podinfo:6.15.0
+        image: ghcr.io/stefanprodan/podinfo@sha256:ec73780a8425f59ea49f5bc8cdff0d598805a224fbaa1f86c67a244f250fa9da
...
         resources:
+          limits:
+            memory: 64Mi
           requests:
             cpu: 1m
             memory: 16Mi
+        securityContext:
+          allowPrivilegeEscalation: false
...
 metadata:
+  annotations:
+    example.com/owner: platform
```

A file whose documents were all deleted becomes a single comment line, so
Kapitan overwrites the chart's file instead of leaving it in place:

```yaml
# podinfo/templates/tests/service.yaml
# all objects removed by mutation no-test-pods
```

mutate writes only the files a mutation changed or emptied; the others keep
the bytes Helm wrote. A rewritten file keeps its key order but loses Helm's
`# Source:` comments and its list indentation, which is why the check sorts
both sides before the diff.

## Deploying the result

The check deploys the mutated directory, comment-only files included, to a
kind cluster on Kubernetes 1.37.0 three times, one tool per cluster. The
`podinfo` namespace enforces restricted Pod Security, which admits podinfo's
Pods only with `harden`: the chart sets no `securityContext` by default, and
the image's user is the name `app`, so `runAsNonRoot` needs a numeric
`runAsUser` to be verifiable. In each run Chainsaw asserts two available
replicas, the pinned image, the Service annotation and that no helm test
Pod exists.

- `kubectl apply -R -f` created `deployment.apps/podinfo` and
  `service/podinfo` and nothing for the three comment-only files.
- Argo CD 3.5.5, with the directory as a source and `recurse: true`,
  reported the Application `Synced` and `Healthy` at the pushed commit, with
  two resources, the Service and the Deployment, and no conditions.
- Flux 2.9.6 reported the Kustomization `Ready` at the pushed commit, with
  the Service and the Deployment in its inventory. The directory has no
  `kustomization.yaml`, so kustomize-controller generates one from every
  `.yaml` file that decodes as Kubernetes YAML
  ([`scanManifests`](https://github.com/fluxcd/pkg/blob/kustomize/v1.35.7/kustomize/kustomize_generator.go#L572-L632));
  a comment decodes to zero objects and adds none.

Both tools read the commit from a Git server inside the cluster, set up as
in the [Argo CD vs Flux guide](/guides/argocd-vs-flux/).

## Limits

mutate has no strategic merge patch, no regular expressions on the rendered
text and no templating, and it cannot move objects between files or rename
them. With Kapitan's `--cache`, the compile result is keyed on the
inventory, the input parameters and the target's `helm` dependencies, not on
the files mutate reads; a chart vendored without a `helm` dependency can
change without invalidating the cache. The example pins the chart through a
`helm` dependency.

Kapitan's `helm` input runs `helm template`, so there is no Helm release:
`helm ls` shows nothing, and chart hooks are rendered as ordinary manifests
that carry their `helm.sh/hook` annotations. Where a release,
`helm rollback` and hooks matter, a Flux
HelmRelease with `postRenderers` keeps them, and a Helm 4 post-renderer
plugin does for `helm install`.

The digest pin fixes the chart's bytes, not their origin: the check does
not verify the cosign or Notation signatures that podinfo publishes for the
chart, because Kapitan's `helm` dependency has no place for it. The
[supply-chain guide](/guides/supply-chain-security-for-kapitan-generators/)
covers how kadet-hub generators themselves are verified, by
[attestation](/glossary/#attestation) against the signed
[index](/glossary/#index).
