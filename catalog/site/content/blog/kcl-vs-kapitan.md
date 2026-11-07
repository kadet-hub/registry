---
title: "KCL vs Kapitan: typed schemas and locked modules on one app"
date: 2026-11-14
topics: [kapitan, comparison, validation, supply chain]
description: "KCL for Kubernetes and a Kapitan inventory render one app to identical manifests. Also tested: a misspelled value and a wrong checksum in kcl.mod.lock."
---

[KCL](https://www.kcl-lang.io/) is a configuration language with types.
A schema declares the attributes a value may have, and `kcl run` stops on
a value that does not fit. Code is shared as KCL modules, which `kcl.mod`
names by version and which kcl downloads from an OCI registry. The `k8s`
module carries schemas for the kinds of the Kubernetes API.
[Kapitan](/glossary/#kapitan) reads YAML from an
[inventory](/glossary/#inventory) and passes it to a
[generator](/glossary/#generator), here the kadet-hub
[kubernetes](/generators/kubernetes/) generator, pinned by
[digest](/glossary/#digest).

The
[example](https://github.com/kadet-hub/examples/tree/main/kcl-vs-kapitan)
renders the app of the [Helm vs Kustomize vs Kapitan guide](/guides/same-app/)
with both tools. Its `check` fails unless the manifests match for each
environment. It also tests a misspelled value on both sides and what kcl
does with the checksum in `kcl.mod.lock`. CI runs `check` on every change
and once a week. The [Timoni vs Kapitan post](/blog/timoni-vs-kapitan/)
does the same with CUE.

## The app and the check

Namespace `shop`, apps `web` and `api` with a Deployment, a Service and a
ConfigMap each, the restricted Pod Security profile, environments dev and
prod, PodDisruptionBudgets in prod only. The api's ConfigMap carries
`web_url`, built from the web Service's port.

- kcl 0.13.3 with the `k8s` module 1.36 from `ghcr.io/kcl-lang/k8s`.
- Kapitan 0.36.3 with the kubernetes generator 1.14.0 and the inventory of
  the [cdk8s vs Tanka vs Kapitan guide](/guides/config-tools/).

`check` sorts the objects and their keys and drops one label,
`app.kubernetes.io/managed-by`, which only the generator sets. Nothing
else is dropped:

```console
$ ./check
downloading 'kcl-lang/k8s:1.36' from 'ghcr.io/kcl-lang/k8s:1.36'
dev: kcl = kapitan (6 objects)
prod: kcl = kapitan (8 objects)
kcl: replica rejected (Cannot add member 'replica' to schema 'App')
kapitan: replica compiled, web gets replicas: 1
downloading 'kcl-lang/k8s:1.36' from 'ghcr.io/kcl-lang/k8s:1.36'
kcl: ran prod with a wrong checksum in kcl.mod.lock
```

## Schema and values

`kcl/app/app.k` declares the schema of one app and a function that turns
an `App` into its objects:

```python
schema App:
    """The values of one app. A schema is closed: an attribute it does not declare is an error."""
    name: str
    namespace: str
    image: str
    replicas: int = 1
    port: Port
    readinessPath: str
    resources: corev1.ResourceRequirements
    config: Config
    # A PodDisruptionBudget is rendered only when this is set.
    pdbMinAvailable?: int

    check:
        replicas > 0
        pdbMinAvailable > 0 if pdbMinAvailable != Undefined
```

`Port` and `Config` are two small schemas of their own, `resources` uses
the `ResourceRequirements` schema of the `k8s` module, and the `check`
block holds rules beyond the types. The function builds each object from
the module's schemas, `appsv1.Deployment` for the Deployment.

`kcl/shop.k` declares `web` and `api` with the values both environments
share and prints their objects as one YAML stream. `prod.k` and `dev.k`
declare the same two names with the values of one environment, and
`kcl run shop.k prod.k` merges them:

```python
# shop.k
api: app.App {
    name = "api"
    namespace = "shop"
    port = {container = 9090, service = 80}
    readinessPath = "/healthz"
    config.mount = "/etc/api"
    config.data.web_url = "http://web.${web.namespace}.svc:${web.port.service}"
}

# prod.k
api: app.App {
    image = "ghcr.io/example/api:1.9.1"
    replicas = 2
    resources = {
        requests = {cpu = "500m", memory = "512Mi"}
        limits.memory = "1Gi"
    }
    config.data.log_level = "info"
    pdbMinAvailable = 1
}
```

`web_url` refers to `web`, so it follows the web Service's port, as the
[interpolation](/glossary/#interpolation)
`${components:web:ports:http:service_port}` does in the inventory. The
split into shared and per-environment files mirrors the inventory's
[classes](/glossary/#class) and [targets](/glossary/#target).

Hand-written files, without the lock file, the `k8s` module and the
generator:

| | files | lines |
|---|---|---|
| KCL (`app/app.k`, `shop.k`, `dev.k`, `prod.k`, `kcl.mod`) | 5 | 163 |
| Kapitan inventory and `.kapitan` | 6 | 99 |

Of the 163 lines, 95 are `app.k`: the schema and the function that
spells out the fields the generator writes, such as the probe thresholds
and `defaultMode: 420`. On the Kapitan side that code is the generator,
4529 lines of Python without its tests, maintained in kadet-hub. The
`k8s` module that kcl downloads holds 757 KCL files with 28,089 lines.

## A misspelled value

`check` replaces `replicas = 3` with `replica = 3` for web in prod. kcl
stops at the line in `prod.k`:

```text
error[E2L23]: CompileError
 --> /tmp/tmp.…/kcl-typo/prod.k:5:5
  |
5 |     replica = 3
  |     ^ Cannot add member 'replica' to schema 'App', did you mean '["replicas"]'?
```

`App` has no attribute `replica`, and a schema accepts no attribute it
does not declare.

Kapitan compiles the same change, `replica: 3` in its prod target, and
exits 0. The generator does not know `replica`, ignores it and renders web
with `replicas: 1`. It logs one warning, because the PodDisruptionBudget
of 2 then allows no eviction:

```text
web: pdb_min_available 2 >= 1 replicas allows no eviction, which blocks node drains
```

The warning comes from the generator's rule for the budget, not from a
check of the key. Kapitan 0.36.3 and the generator 1.14.0 accept a key they
do not know.

## Modules and their checksums

`kcl.mod` names the `k8s` module by version, and `kcl.mod.lock` records
where kcl found it and a checksum of its files:

```toml
[dependencies]
  [dependencies.k8s]
    name = "k8s"
    full_name = "k8s_1.36"
    version = "1.36"
    sum = "ezvFFbGACf8NvdIIqNh4QklNRE6cJANLnfBmPfN47yc="
    reg = "ghcr.io"
    repo = "kcl-lang/k8s"
    oci_tag = "1.36"
```

kcl pulls the module by the tag `1.36`. `check` copies the project,
replaces `sum` with a wrong value and runs prod with an empty module
directory. kcl downloads the module and renders the same manifests as
before. The lock file records the checksum, but kcl 0.13.3 does not
compare it. kpm 0.13.2, the library kcl uses for modules, checks a
dependency's sum only behind the feature gate `SupportModCheck`, which is
off by default. In a run by hand with
`KPM_FEATURE_GATES=SupportModCheck=true`, `kcl run` rendered with the
wrong sum as well.

On the Kapitan side, `inventory/classes/common.yml` pins the generator by
version and digest:

```yaml
source: ghcr.io/kadet-hub/kubernetes:1.14.0@sha256:787129e1eaed6b9bc868fe4c4aec58d40de6a89fc3cc08424a4cb5822b855080
```

Kapitan 0.36.3 does not check that digest or a signature when it fetches
dependencies either. `check` does both outside Kapitan: `gh attestation
verify` shows that the kadet-hub release workflow built the artifact,
`oras pull` fetches it by digest, and Kapitan compiles without `--fetch`.

## What the example leaves out

The images are placeholders, so nothing is deployed. The example does not
publish its own KCL module with `kcl mod push`, and it uses only kcl's
YAML output. It renders Kubernetes objects only, so Kapitan's other
outputs from the same inventory, such as Terraform, are not compared.

## Running it

You need kcl and uv, plus oras and a logged-in gh for the generator:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/kcl-vs-kapitan
$ ./check
```
