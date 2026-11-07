---
title: cert-manager Helm chart initContainers and trust-manager issuer
date: 2026-10-20
topics: [helm, kapitan, generators]
description: "Helm chart initContainers for cert-manager and a trust-manager webhook certificate from your own ClusterIssuer, patched by Kapitan and tested on kind."
---

Two requests against the cert-manager project's Helm charts have no value
to set in the current releases, cert-manager v1.21.2 and trust-manager
v0.25.0: init containers on the cert-manager controller, and a
trust-manager webhook certificate signed by an issuer you manage instead
of the self-signed one the chart creates. Both can be fixed on the rendered
manifests without forking the chart. This post does it with
[Kapitan](/glossary/#kapitan)'s [mutate](/generators/mutate/)
[generator](/glossary/#generator), one section per issue.

The code is
[`cert-manager-mutate`](https://github.com/kadet-hub/examples/tree/main/cert-manager-mutate)
in kadet-hub/examples. Its CI job renders both charts, fails unless every
patch below is in the output, deploys the result to a kind cluster and
checks it with Chainsaw. The guide
[Patch a Helm chart](/guides/patch-helm-chart/) compares this approach
with Helm post-renderers, Kustomize and Flux's `postRenderers`.

## Rendering and patching

Each chart is pinned by version and by the [digest](/glossary/#digest) of
its OCI artifact in a [class](/glossary/#class) and rendered with Kapitan's
`helm` input. Both charts take tag and digest for every image in their
values, so no patch is needed for that. A [target](/glossary/#target) adds
mutate as a second compile entry on the same `output_path`, which rewrites
the rendered files in place:

```yaml
# inventory/targets/trust-manager.yml
parameters:
  kapitan:
    compile:
      - input_type: kadet
        input_paths: [lib/mutate]
        output_path: trust-manager
        output_type: plain
        input_params:
          mutations: ${mutations}
```

Every mutation has to match at least one object. A chart release that
renames or drops a patched object fails the compile instead of shipping
without the patch.

## cert-manager Helm chart: initContainers {#cert-manager-initcontainers}

[cert-manager/cert-manager#6071](https://github.com/cert-manager/cert-manager/issues/6071)
asks for a value that adds init containers to the controller Deployment.
The maintainer inteon
[answered](https://github.com/cert-manager/cert-manager/issues/6071#issuecomment-1591217593)
in June 2023 that "we don't want to parameterise all fields in our Helm
chart. Instead, you should use a Helm postprocessing step to add these init
containers." The stale bot closed the issue in November 2023. The v1.21.2
chart has `extraContainers`, which adds containers next to the controller,
and still no value for init containers.

The mutation adds the list with a JSON Patch:

```yaml
# inventory/targets/cert-manager.yml
parameters:
  mutations:
    init-containers:
      match: {apiVersion: apps/v1, kind: Deployment, name: cert-manager}
      json6902:
        - op: add
          path: /spec/template/spec/initContainers
          value:
            - name: init
              image: docker.io/library/busybox:1.38.0@sha256:fd7dc98638c8e305f4dc34e979f1c0fdfdcaeb0fbf8fcff77ae834b6da3d7e6e
              command: [echo, init container added by mutate]
              securityContext:
                allowPrivilegeEscalation: false
                capabilities: {drop: [ALL]}
                readOnlyRootFilesystem: true
                runAsUser: 65534
```

`match` compares apiVersion, kind and name exactly, so the webhook and
cainjector Deployments stay as rendered. `add` creates `initContainers`
because the chart renders none. On a Deployment that already has the list,
`add` would replace it. The path `/spec/template/spec/initContainers/-`
appends to an existing list instead, and fails the compile on today's
chart:

```text
mutate: mutation init-containers: cert-manager/templates/deployment.yaml: json6902 path '/spec/template/spec/initContainers/-' does not exist
```

The chart's pod sets `runAsNonRoot: true`, and busybox runs as root.
Without `runAsUser` the controller never starts:

```text
NAME                            READY   STATUS                            RESTARTS   AGE
cert-manager-559884b95-ndzkb    0/1     Init:CreateContainerConfigError   0          15s
```

```text
CreateContainerConfigError: container has runAsNonRoot and image will run as root (pod: "cert-manager-559884b95-ndzkb_cert-manager(39b2da2d-cb31-49e3-873b-d94083bfb131)", container: init)
```

The check diffs the mutated render against the plain one, both loaded and
dumped with sorted keys:

```diff
@@ -72,6 +72,19 @@
             - ALL
           readOnlyRootFilesystem: true
       enableServiceLinks: false
+      initContainers:
+      - command:
+        - echo
+        - init container added by mutate
+        image: docker.io/library/busybox:1.38.0@sha256:fd7dc98638c8e305f4dc34e979f1c0fdfdcaeb0fbf8fcff77ae834b6da3d7e6e
+        name: init
+        securityContext:
+          allowPrivilegeEscalation: false
+          capabilities:
+            drop:
+            - ALL
+          readOnlyRootFilesystem: true
+          runAsUser: 65534
       nodeSelector:
         kubernetes.io/os: linux
       securityContext:
```

On the kind cluster, Chainsaw waits for the controller pod to be Ready with
the init container `init` terminated with reason `Completed` and exit code
0, and reads its log:

```text
init container added by mutate
```

## trust-manager Helm chart: a custom issuer for the webhook {#trust-manager-custom-issuer}

[cert-manager/trust-manager#778](https://github.com/cert-manager/trust-manager/issues/778),
opened in October 2025, asks to sign the webhook certificate with an issuer
or cluster issuer managed outside the chart, for clusters whose rules a
self-signed issuer does not meet. No maintainer has replied; the bot
marked it stale in April 2026 and rotten in July 2026.

Whenever `app.webhook.tls.helmCert.enabled` is false, the default, the
chart's
[`certificate.yaml`](https://github.com/cert-manager/trust-manager/blob/v0.25.0/deploy/charts/trust-manager/templates/certificate.yaml)
renders a selfSigned Issuer and the webhook Certificate that uses it
(excerpt):

```yaml
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: {{ include "trust-manager.name" . }}
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: {{ include "trust-manager.name" . }}
spec:
  issuerRef:
    name: {{ include "trust-manager.name" . }}
    kind: Issuer
    group: cert-manager.io
```

The other setting, `helmCert.enabled: true`, has Helm generate the
certificate with a validity of 10 years, which the chart's values file
advises against in production. Two mutations replace the issuer:

```yaml
# inventory/targets/trust-manager.yml
parameters:
  mutations:
    no-selfsigned-issuer:
      match: {apiVersion: cert-manager.io/v1, kind: Issuer, name: trust-manager}
      delete: true
    webhook-issuer:
      match: {apiVersion: cert-manager.io/v1, kind: Certificate, name: trust-manager}
      merge:
        spec:
          issuerRef:
            name: internal-ca
            kind: ClusterIssuer
```

`merge` is a JSON Merge Patch, so `group: cert-manager.io` stays.
The rendered diff:

```diff
@@ -15,8 +15,8 @@
   - trust-manager.cert-manager.svc
   issuerRef:
     group: cert-manager.io
-    kind: Issuer
-    name: trust-manager
+    kind: ClusterIssuer
+    name: internal-ca
   privateKey:
     rotationPolicy: Always
   revisionHistoryLimit: 1
@@ -24,17 +24,3 @@
   secretTemplate:
     annotations:
       cert-manager.io/allow-direct-injection: 'true'
----
-apiVersion: cert-manager.io/v1
-kind: Issuer
-metadata:
-  labels:
-    app.kubernetes.io/instance: trust-manager
-    app.kubernetes.io/managed-by: Helm
-    app.kubernetes.io/name: trust-manager
-    app.kubernetes.io/version: v0.25.0
-    helm.sh/chart: trust-manager-v0.25.0
-  name: trust-manager
-  namespace: cert-manager
-spec:
-  selfSigned: {}
```

The ClusterIssuer `internal-ca` is not part of either chart. In the example,
[`internal-ca.yaml`](https://github.com/kadet-hub/examples/blob/main/cert-manager-mutate/internal-ca.yaml)
creates it: a selfSigned ClusterIssuer issues a CA certificate into the
`cert-manager` namespace, and a CA ClusterIssuer signs with that key. A
ClusterIssuer backed by your own PKI takes its place in the same `issuerRef`.

With approver-policy installed, `app.webhook.tls.approverPolicy.enabled:
true` also renders a CertificateRequestPolicy whose `selector.issuerRef`
names the Issuer `trust-manager`; that selector needs the same change. The
example does not install approver-policy and does not test it.

trust-manager v0.25.0 annotates its ValidatingWebhookConfiguration with
`cert-manager.io/inject-ca-from-secret: cert-manager/trust-manager-tls`, so
cainjector copies the `ca.crt` of the webhook's Secret into the caBundle.
With a CA issuer, that `ca.crt` is the CA's certificate. On the kind
cluster, Chainsaw asserts that the Certificate `trust-manager` is Ready with
the new `issuerRef` and that no Issuer `trust-manager` exists. A script
then verifies the webhook certificate against the CA and compares
fingerprints. From the
[CI job](https://github.com/kadet-hub/examples/actions/runs/39376093578/job/118474459710)
of the pull request that added the example:

```text
/tmp/tmp.1y1xcx7s6B/tls.crt: OK
subject=CN = trust-manager.cert-manager.svc
issuer=CN = internal-ca
internal-ca: sha256 Fingerprint=EE:31:AC:56:63:EC:89:CB:E6:3F:C4:4F:BB:4D:00:8B:66:56:43:5D:9A:23:BE:FC:B7:B2:A5:10:64:91:B0:75
Secret trust-manager-tls ca.crt: sha256 Fingerprint=EE:31:AC:56:63:EC:89:CB:E6:3F:C4:4F:BB:4D:00:8B:66:56:43:5D:9A:23:BE:FC:B7:B2:A5:10:64:91:B0:75
ValidatingWebhookConfiguration trust-manager caBundle: sha256 Fingerprint=EE:31:AC:56:63:EC:89:CB:E6:3F:C4:4F:BB:4D:00:8B:66:56:43:5D:9A:23:BE:FC:B7:B2:A5:10:64:91:B0:75
ConfigMap default/internal-ca: sha256 Fingerprint=EE:31:AC:56:63:EC:89:CB:E6:3F:C4:4F:BB:4D:00:8B:66:56:43:5D:9A:23:BE:FC:B7:B2:A5:10:64:91:B0:75
```

The Bundle `internal-ca` in
[`bundle.yaml`](https://github.com/kadet-hub/examples/blob/main/cert-manager-mutate/bundle.yaml)
copies the CA into a ConfigMap in every namespace. It is created through
trust-manager's webhook, so the API server accepted the webhook's
certificate before the Bundle reported `Synced`. In a local run with the
Certificate pointed back at the chart's Issuer, the same verification
fails:

```text
error 18 at 0 depth lookup: self-signed certificate
error /tmp/tmp.iCcWKSE67P/tls.crt: verification failed
```

If the chart stops rendering the two objects, the compile fails instead
of leaving the patches without effect. With `helmCert.enabled: true` the
chart renders neither the Issuer nor the Certificate, and Kapitan stops
with:

```text
kadet_component_mutate.mutations.MutationError: mutate: mutation webhook-issuer: expects 1+, matched 0
Error compiling trust-manager: Could not load Kadet module: mutate
```

## Installing the result

`check` applies cert-manager first, server-side because three of its CRDs
exceed the annotation size of a client-side apply, and waits until its
Deployments are available. cert-manager's webhook then still refused
connections for a few seconds; in one local run the apply of
`internal-ca.yaml` failed three times with `connect: connection refused`
before it went through. Every apply is therefore repeated for up to a
minute. trust-manager and the Bundle follow. In the CI job above the
check took 96 seconds: 25 to verify mutate and compile, 65 for the kind
cluster and the installs, and 6 for Chainsaw.

Kapitan's `helm` input runs `helm template`, so there is no Helm release,
and hooks would be applied as ordinary objects. The cert-manager class
leaves out `startupapicheck`, a hook Job that waits for the webhook during
`helm install`. Where releases and
`helm rollback` matter, the
[guide](/guides/patch-helm-chart/#flux-and-argo-cd) covers Flux's
`postRenderers`, which keep them.

To run it yourself:

```bash
git clone https://github.com/kadet-hub/examples
cd examples
cert-manager-mutate/check
```

It needs gh (authenticated), jq, oras, uv, helm, kind, kubectl, chainsaw,
openssl and Docker.
