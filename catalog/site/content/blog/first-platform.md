---
title: A first platform from four kadet-hub generators
date: 2026-10-17
topics: [kapitan, generators, verification]
description: Two Kapitan targets from four verified kadet-hub generators, from an empty directory to 23 schema-valid manifests and a CI workflow.
---

This post builds a small platform from the catalog: a `dev` and a `prod`
[target](/glossary/#target) that share one [inventory](/glossary/#inventory) and render a web workload, its TLS
certificate, a Cilium network policy and the Argo CD Application that deploys
it. Four [generators](/glossary/#generator) do the rendering: [kubernetes](/generators/kubernetes/),
[cilium](/generators/cilium/), [certmanager](/generators/certmanager/) and
[argocd](/generators/argocd/). Every artifact is checked against the signed
[index](/glossary/#index) before it is used.

The finished project is in
[kadet-hub/examples](https://github.com/kadet-hub/examples/tree/main/first-platform).
Replayed from an empty directory with a cold package cache, the commands in
this post take 79 seconds: 33 for installing [Kapitan](/glossary/#kapitan), 44 for verifying and
fetching the index and the four generators, two for compiling and
validating. The
rest of your time goes into reading four generator pages and writing 107
lines of inventory, which I did not time for a person.

## Kapitan

The project pins the Kapitan version the kadet-hub sandbox uses, with uv:

```toml
[project]
name = "first-platform"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
# omegaconf 2.4.0 breaks the OmegaConf backend of Kapitan 0.36.3 (kapicorp/kapitan#1621).
dependencies = ["kapitan[omegaconf,reclass-rs]==0.36.3", "omegaconf==2.4.0.dev4"]

[tool.uv]
package = false
```

`uv sync` creates `.venv` and `uv.lock`; everything below runs through
`uv run`. You also need `gh`, `oras` and `jq`.

## Versions come from the signed index

The catalog pages show an inventory entry per generator, but the record that
the release workflow signs is the index. Each index serial is also a GitHub
release of the registry with the index and its Sigstore bundle:

```sh
gh release download index-47 --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json --owner kadet-hub \
  --cert-identity https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
jq .serial index.json   # 47
```

The [digest](/glossary/#digest) for a version is one `jq` call away, and `yanked` is `null` for
all four versions used here:

```sh
jq -r '.generators.certmanager["1.0.2"].digest' index.json
# sha256:ba7632e9e06a593fbe20e9fa6774139203d7df65992adff9db94779606888ad9
```

Then each artifact's [attestation](/glossary/#attestation), checked against the same workflow identity:

```sh
gh attestation verify \
  oci://ghcr.io/kadet-hub/certmanager@sha256:ba7632e9e06a593fbe20e9fa6774139203d7df65992adff9db94779606888ad9 \
  --owner kadet-hub \
  --cert-identity https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
```

In a terminal this ends with `✓ Verification succeeded!`. Piped or in a
script, `gh` prints nothing on success, so check the exit code or add
`--format json`. All four passed; the digests matched the catalog pages.

## Pin the generators

One [class](/glossary/#class) holds the four dependencies and one compile entry per generator,
each writing to its own directory below the target:

```yaml
# inventory/classes/generators.yml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/cilium:1.0.3@sha256:8cee8be098798642199063b8afa5e5bbf8d717b0426df280dd718d998e116635
        output_path: lib/cilium
      - type: oci
        source: ghcr.io/kadet-hub/certmanager:1.0.2@sha256:ba7632e9e06a593fbe20e9fa6774139203d7df65992adff9db94779606888ad9
        output_path: lib/certmanager
      - type: oci
        source: ghcr.io/kadet-hub/argocd:1.0.3@sha256:49804acaf225b3337a63ec95ae3ba001a98c53e342791e1c2b1b6ed3089638d4
        output_path: lib/argocd
      - type: oci
        source: ghcr.io/kadet-hub/kubernetes:1.2.0@sha256:52017626e77dd5bf7293ce465ff0c3dc7a61dae1ae8353a56a53ffebe1bfb67c
        output_path: lib/kubernetes
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/kubernetes], output_path: apps/}
      - {input_type: kadet, output_type: yml, input_paths: [lib/cilium], output_path: cilium/}
      - {input_type: kadet, output_type: yml, input_paths: [lib/certmanager], output_path: cert-manager/}
      - {input_type: kadet, output_type: yml, input_paths: [lib/argocd], output_path: argocd/}
```

The tag is for readers and Renovate; the digest decides what is fetched.

## Describe the platform

A `platform` class sets up a private CA and a Let's Encrypt ClusterIssuer
through certmanager, and an Argo CD AppProject plus an Application pointing at
the compiled apps of the target. A `shop` class describes the app:

```yaml
# inventory/classes/shop.yml (excerpt)
parameters:
  namespace: shop
  generators:
    manifest:
      default_config:
        recommended_labels: true
        security_profile: restricted
    cilium:
      network_policies:
        web:
          endpoint_selector:
            match_labels: {name: web}
          ingress:
            - fromEntities: [ingress]
              ports: [8080]
          allow_dns: true
  components:
    web:
      image: ghcr.io/stefanprodan/podinfo:6.9.2
      replicas: ${replicas}
      ports:
        http: {container_port: 8080, service_port: 80}
      healthcheck:
        readiness: {type: http, port: http, path: /readyz}
```

Each generator reads its own key: `generators.cilium`,
`generators.certmanager`, `generators.argocd`. The kubernetes generator
reads `components` and `generators.kubernetes`, and takes defaults for every
component from `generators.manifest`. The targets
only set what differs:

```yaml
# inventory/targets/prod.yml
classes: [generators, platform, shop]
parameters:
  kapitan:
    vars: {target: prod}
  env: prod
  letsencrypt: production
  hostname: shop.example.com
  replicas: 3
  components:
    web:
      pdb_min_available: 2
```

`dev` has one replica, `letsencrypt: staging` and no PDB. My first version
put `pdb_min_available: 1` in the shared class, and the kubernetes generator
warned for dev: `web: pdb_min_available 1 >= 1 replicas allows no eviction,
which blocks node drains`. That warning is why the PDB now lives in prod.

## Fetch and compile

[docs/consumers.md](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
is explicit that `kapitan compile --fetch` checks neither attestations nor
digests and runs generator code with your credentials. Locally I followed
the consumer workflow instead: pull each verified digest with `oras` and
unpack its single tar layer.

```sh
d=$(jq -r '.generators.certmanager["1.0.2"].digest' index.json)
t=$(mktemp -d); oras pull -o "$t" "ghcr.io/kadet-hub/certmanager@$d"
mkdir -p lib/certmanager && tar -xf "$t/certmanager.tar" -C lib/certmanager --no-same-owner
```

With `lib/` in place, compile without `--fetch`:

```
$ uv run kapitan compile --inventory-backend reclass-rs
Rendered inventory (0.01s): discovered 2 targets.
Compiling 2/2 targets using 2 concurrent processes: (24 CPU available)
Compiled dev (0.06s)
Compiled prod (0.06s)
Compiled 2 targets in 0.74s
```

If you try `--fetch` anyway: the `omegaconf` and `reclass-rs` extras do not
pull in the `oras` Python package, and Kapitan stops with `The 'oras' package
is required for OCI dependencies`. With `kapitan[oci]` it fetched the same
four digests and produced identical output, but still without any
verification. The generator code also runs unsandboxed in both cases; the
sandbox only exists in the CI workflow below.

## What came out

```
$ find compiled/prod -type f | sort
compiled/prod/apps/shop-namespace.yml
compiled/prod/apps/shop/web-deploy.yml
compiled/prod/apps/shop/web-scaling.yml
compiled/prod/apps/shop/web-svc.yml
compiled/prod/argocd/argocd/platform-appproject.yml
compiled/prod/argocd/argocd/shop-application.yml
compiled/prod/cert-manager/cert-manager/internal-ca-cert.yml
compiled/prod/cert-manager/internal-ca-cissuer.yml
compiled/prod/cert-manager/internal-ca-selfsigned-cissuer.yml
compiled/prod/cert-manager/letsencrypt-cissuer.yml
compiled/prod/cert-manager/shop/web-cert.yml
compiled/prod/cilium/shop/web-cnp.yml
```

Prod has 12 files with one document each: three ClusterIssuers, two
Certificates, and one each of Namespace, Deployment, Service,
PodDisruptionBudget, CiliumNetworkPolicy, AppProject and Application. Dev has
the same minus the PDB, 11 files. `diff -r compiled/dev compiled/prod` shows
only what the targets set: replicas, the PDB, the Argo CD source path, the CA
common name, the ACME server and the certificate's DNS name.

The Deployment came out with the restricted profile: `runAsNonRoot`,
`seccompProfile: RuntimeDefault`, all capabilities dropped, no service
account token. The cilium generator turned `ports: [8080]` into a
`toPorts` entry with the port as a string, which the [CRD](/glossary/#crd) requires, and
`allow_dns: true` into an egress rule to kube-dns with an L7 DNS rule.

Each generator ships the JSON Schemas it was checked against, so the output
can be validated without a cluster:

```sh
a=(); for g in kubernetes cilium certmanager argocd; do
  a+=(-schema-location "lib/$g/schemas/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"); done
kubeconform -strict -summary "${a[@]}" \
  -schema-location 'lib/kubernetes/schemas/core/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' compiled/
# Summary: 23 resources found in 23 files - Valid: 23, Invalid: 0, Errors: 0, Skipped: 0
```

A broken copy (`replicas: three`, a misspelled `fromEntities`) reported both
documents invalid, so the schemas are actually applied.

## Compile in CI

The local compile is for iterating. For anything you apply, the reusable
consumer workflow does the same steps with the checks: it verifies every
artifact against the attested index, compiles in a gVisor sandbox without
network and with decoy credentials, and checks the output for privileged
containers, `hostPath`, admin bindings and similar. Pin it by commit:

```yaml
# .github/workflows/compile.yml
on: [pull_request]
permissions: {}
jobs:
  compile:
    permissions:
      contents: read
      packages: read
      attestations: read
    uses: kadet-hub/registry/.github/workflows/consumer.yml@37d5aeaa0b5f402ca36e720e14435419ad56c4df
```

```yaml
# .kapitan-sandbox.yaml
index_serial: 47
inventory_backend: reclass-rs
hosts:
  oci: [ghcr.io]
```

`index_serial: 47` rejects any older index, and `hosts` allows OCI
dependencies from ghcr.io only. None of the four generators declares a
program to run, and the output needs no `output_capabilities`. I ran the
workflow's dependency check (`consumer/plan.py`) and its output check
locally against this project: both passed, the plan failed as expected with
`index_serial: 48`, and an added `privileged: true` was reported.

The workflow treats the repository root as the Kapitan project. To use the
example, copy the `first-platform` folder to the root of your own
repository. The [how kadet-hub works](/guides/how-kadet-hub-works/) guide
covers what the [gate](/glossary/#gate) checked before these versions were listed, and the
[supply-chain guide](/guides/supply-chain-security-for-kapitan-generators/)
what a listing does not cover.
