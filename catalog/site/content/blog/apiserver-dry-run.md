---
title: Catch bad manifests with a server-side dry run in CI
date: 2026-10-20
topics: [ci, validation, crds, gate]
description: A copy-paste GitHub Actions job that starts etcd and kube-apiserver, installs your CRDs and dry-runs every manifest in a few seconds.
---

Most repositories that ship Kubernetes manifests, Helm charts or [CRDs](/glossary/#crd) check
them in CI with kubeconform or another JSON Schema validator. That catches
wrong types, missing required fields and, with `-strict`, unknown fields. It
does not catch everything the API server checks, and the gap shows up on the
first `kubectl apply` against a real cluster.

The API server does not need a cluster. etcd and kube-apiserver, two static
binaries, start on 127.0.0.1 in about two seconds. No kubelet, no scheduler,
no nodes, no kind, no Docker. Install the CRDs into it, send every document
with `kubectl apply --dry-run=server`, and you get the answer a cluster would
give, minus the operator's admission webhooks.

The full example, with the script, the workflow and the manifests below, is
at
[kadet-hub/examples/apiserver-dry-run](https://github.com/kadet-hub/examples/tree/main/apiserver-dry-run).

## What kubeconform passes and the server rejects

The example has seven files. Two are valid, five are broken in ways a real
cluster rejects. All 9 documents pass `kubeconform -strict` against the
Kubernetes 1.37.1 schemas plus JSON Schemas generated from the Gateway API
v1.6.3 CRDs with kubeconform's own `openapi2jsonschema.py`:

```text
Summary: 9 resources found in 7 files - Valid: 9, Invalid: 0, Errors: 0, Skipped: 0
```

kube-apiserver v1.37.1 with the same CRDs installed rejects five of them:

| Document | What is wrong | Checked by |
|---|---|---|
| HTTPRoute `web-redirect` | `RequestRedirect` filter and `backendRefs` in one rule | CEL rule in the CRD |
| HTTPRoute `web-slow` | `backendRequest: 30s` longer than `request: 10s` | CEL rule in the CRD |
| Gateway `internal` | two listeners named `http` | `listType: map` key, plus a CEL rule |
| Deployment `worker` | selector does not match the template labels | built-in validation |
| ConfigMap `Web_Settings` | name is not a lowercase RFC 1123 subdomain | built-in validation |

The messages are the ones a cluster would print:

```text
The Gateway "internal" is invalid:
* spec.listeners[1]: Duplicate value: {"name":"http"}
* spec.listeners: Invalid value: Listener name must be unique within the Gateway
The HTTPRoute "web-redirect" is invalid: spec.rules[0]: Invalid value: RequestRedirect filter must not be used together with backendRefs
The Deployment "worker" is invalid: spec.template.metadata.labels: Invalid value: {"app":"queue-worker"}: `selector` does not match template `labels`
The HTTPRoute "web-slow" is invalid: spec.rules[0].timeouts: Invalid value: backendRequest timeout cannot be longer than request timeout
```

The two HTTPRoute rules are cross-field constraints written in CEL under
`x-kubernetes-validations`. The generated JSON Schema still contains them,
but a JSON Schema validator ignores keywords it does not know. The `v1` schemas of the Gateway API standard
channel alone carry 166 of them, and many operator CRDs use them the same
way. For the [built-in kinds](/glossary/#kind), much of the server's validation lives in Go
code that the published OpenAPI schema does not describe, such as name
formats and selector matching.

## The job

```yaml
name: dry-run
on:
  pull_request:
  push:
    branches: [main]
permissions: {}
jobs:
  dry-run:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
    timeout-minutes: 10
    env:
      KUBERNETES_VERSION: v1.37.1
      KUBE_APISERVER_SHA256: de9b1b43c10143f448408b3aaf15f44fd5248b97a56301417a1fe2f1fc47a691
      KUBECTL_SHA256: 65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8
      ETCD_VERSION: v3.7.2
      ETCD_SHA256: 3a3679bc51a4ee9d30bccea1da7cd4fe62c6fc1d2ca1255068d2c53bf3026135
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - name: Install kube-apiserver, kubectl and etcd
        run: |
          mkdir -p "$RUNNER_TEMP/bin" && cd "$RUNNER_TEMP/bin"
          curl -fsSLo kube-apiserver "https://dl.k8s.io/release/$KUBERNETES_VERSION/bin/linux/amd64/kube-apiserver"
          curl -fsSLo kubectl "https://dl.k8s.io/release/$KUBERNETES_VERSION/bin/linux/amd64/kubectl"
          curl -fsSLo etcd.tgz "https://github.com/etcd-io/etcd/releases/download/$ETCD_VERSION/etcd-$ETCD_VERSION-linux-amd64.tar.gz"
          sha256sum -c <<EOF
          $KUBE_APISERVER_SHA256  kube-apiserver
          $KUBECTL_SHA256  kubectl
          $ETCD_SHA256  etcd.tgz
          EOF
          tar -xzf etcd.tgz --strip-components=1 "etcd-$ETCD_VERSION-linux-amd64/etcd"
          rm etcd.tgz
          chmod +x kube-apiserver kubectl
          echo "$RUNNER_TEMP/bin" >> "$GITHUB_PATH"
      - run: ./dry-run crds manifests
```

The checksums are the ones dl.k8s.io publishes next to each binary and the
`SHA256SUMS` of the etcd release. Kubernetes 1.37.1 names etcd 3.7.0 in its
`build/dependencies.yaml`; 3.7.2 is the newest patch of that minor. The job
needs no token, no cache and no container. For a Helm chart, add a step
that runs `helm template` into `manifests/` first.

## The script

`dry-run` is 75 lines of bash. The part that matters is how the
server is started:

```bash
kube-apiserver --etcd-servers http://127.0.0.1:2379 \
  --bind-address 127.0.0.1 --advertise-address 127.0.0.1 --secure-port 6443 \
  --endpoint-reconciler-type none --cert-dir "$tmp" \
  --token-auth-file "$tmp/tokens.csv" --authorization-mode AlwaysAllow --allow-privileged \
  --service-account-issuer https://kubernetes.default.svc \
  --service-account-key-file "$tmp/sa.key" --service-account-signing-key-file "$tmp/sa.key" \
  --service-cluster-ip-range 10.96.0.0/12 \
  --disable-admission-plugins NamespaceLifecycle,PodSecurity,ServiceAccount,Priority,RuntimeClass
```

kube-apiserver refuses to start without a service account signing key, so
the script generates a throwaway EC key with `openssl`. A random token in
`tokens.csv` as a member of `system:masters`, under `AlwaysAllow`, gives
kubectl full access; with `--cert-dir` the server writes a self-signed
certificate that kubectl then trusts with `--certificate-authority`.
Without `--allow-privileged` the server rejects every privileged
container with `Forbidden: disallowed by cluster policy`.

The disabled admission plugins look up other objects. A [dry run](/glossary/#server-side-dry-run) persists
nothing, so a Pod's namespace, service account or priority class never
exists, and these plugins would reject documents that are fine in a real
deployment. With the `ServiceAccount` plugin on, even a Pod that names no
service account fails with `serviceaccount "default" not found`.
With `NamespaceLifecycle` off, objects in the `shop` namespace are
accepted without creating it. `PodSecurity` has to go as well: for a
namespace that does not exist it answers `failed to lookup namespace
"shop"`, and in an existing namespace without labels it admits even a
privileged Pod. If your namespaces carry `pod-security.kubernetes.io`
labels, this check does not enforce them.

After `/readyz` answers, the script runs `kubectl create -f crds`, waits
with `kubectl wait --for condition=Established crd --all`, and then calls
`kubectl apply --dry-run=server -f` once per file, recording a failure
instead of stopping. kubectl's default `--validate=strict` sends
`fieldValidation=Strict`, so unknown fields are errors, not warnings. A
trap kills both processes with `SIGKILL` and removes the temporary
directory on every exit. In one run with a plain `SIGTERM`, kube-apiserver
was still waiting in its shutdown minutes after etcd had exited, which in
CI would burn the job's timeout. If either process dies during start-up,
the script stops waiting and prints the tail of both logs; without the
service account flags that takes half a second and shows kube-apiserver's
own error.

## What it costs

Measured on 2026-10-17 on a Linux workstation, six runs over the
example: kube-apiserver answered `/readyz` 2.1 to 2.5 s after the script
started, and a whole run took 5.3 to 7.7 s, median 5.7 s. In a traced
run, creating the ten Gateway API CRDs took 0.7 s, waiting for
`Established` 1.2 s, and the seven `kubectl apply` calls 1.3 s together.
The two binaries and the etcd archive are 182 MB to download. The numbers
on a GitHub-hosted runner are not measured here; kadet-hub measured 2.4 s
for a test that starts the same server and sends 13 documents on
`ubuntu-24.04`.

## What it does not catch

The dry run is a create. CEL transition rules compare with `oldSelf` and
only run on update, so a changed immutable field passes. The GatewayClass
`controllerName` is one: a dry run of a GatewayClass with any controller
name succeeds, and the server only answers `spec.controllerName: Invalid
value: "example.com/controller-b": Value is immutable` once an older
GatewayClass of the same name exists. To check that, create the previous
release's objects for real first.

Validation in an operator's admission webhook does not run, because the
operator does not run. cert-manager's webhook and Kyverno's policies need
their own tests. The
[guide on checking custom resources against their CRDs](/guides/checking-custom-resources-against-crds/)
covers CRDs with conversion webhooks and what to do when upstream
publishes no CRD file.

Unknown fields are no reason to switch: kubeconform `-strict` already
rejects a misspelled `spec.rule` with `additional properties 'rule' not
allowed`, and it checks the whole example in about 0.3 s. Keep it as the
first pass. The dry run adds the server's own rules, and with `-o yaml` it shows the object after
defaulting: the valid HTTPRoute comes back with `weight: 1`, `kind:
Service` on its backend and a `PathPrefix /` match nobody wrote.

## In kadet-hub

The kadet-hub [gate](/glossary/#gate) runs this check on every [generator](/glossary/#generator) version before it is
listed: the same pinned kube-apiserver v1.37.1 and etcd v3.7.2, the
generator's shipped CRDs, and every rendered document. [How kadet-hub
works](/guides/how-kadet-hub-works/) describes the gate as a whole.
