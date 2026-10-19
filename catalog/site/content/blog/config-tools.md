---
title: cdk8s vs Tanka vs Kapitan for Kubernetes config
date: 2026-11-24
topics: [kapitan, helm, comparison, jsonnet]
description: "Kubernetes configuration management tools: one app built with Tanka, cdk8s and Kapitan to identical manifests, with size, speed, type safety and GitOps."
---

Pick cdk8s if your team writes TypeScript and wants the compiler to reject a
bad value before anything renders. Pick Tanka if you want a small, fast,
Kubernetes-only toolchain and accept Jsonnet as the language. Pick [Kapitan](/glossary/#kapitan) if
one [inventory](/glossary/#inventory) has to drive Kubernetes and Terraform and you would rather keep
values in YAML than maintain template code. All three rendered the same app to
identical manifests and passed the derived-value test that Helm and Kustomize
failed in the [companion post](/blog/same-app/).

The [example](https://github.com/kadet-hub/examples/tree/main/config-tools)
builds the app with each tool, and `./check` exits 0 only when the normalized
manifests match per environment. Versions, commands and raw output behind
every number are in its `NOTES.md`.

## The app and the check

The spec is the companion's: namespace `shop`, apps `web` and `api` with a
Deployment, Service and ConfigMap each, restricted Pod Security, dev and prod,
PodDisruptionBudgets in prod only, and an api ConfigMap entry `web_url` built
from the web Service port.

- Tanka 0.39.4, jsonnet-bundler 0.6.0, k8s-libsonnet 1.36.
- cdk8s 2.70.111 in TypeScript 5.9.3, using the generated low-level `Kube*`
  classes for Kubernetes 1.36.
- Kapitan 0.36.3 with the kadet-hub [kubernetes generator](/generators/kubernetes/)
  1.2.0 pinned by [digest](/glossary/#digest), as in the companion minus `endpoints.json`.

`check` sorts objects and keys and drops one label,
`app.kubernetes.io/managed-by`, which only the Kapitan generator sets and
which names the tool. Nothing else is ignored. Changing one replica count in a
copy makes it exit 1.

```console
$ ./check
dev: tanka = kapitan (6 objects)
dev: cdk8s = kapitan (6 objects)
prod: tanka = kapitan (8 objects)
prod: cdk8s = kapitan (8 objects)
```

## How much you write

Hand-written files only; lock files, fetched libraries and generated code are
listed separately.

| | web only | both apps | fetched or generated |
|---|---|---|---|
| Tanka | 8 files, 138 lines | 8 files, 167 lines | k8s-libsonnet, 30037 lines |
| cdk8s | 5 files, 148 lines | 5 files, 159 lines | `imports/k8s.ts`, 41214 lines, committed |
| Kapitan | 5 files, 65 lines | 6 files, 101 lines | generator, 4166 lines Python |

For the Helm vs Kustomize vs Jsonnet comparison: Helm needed 156 lines and
Kustomize 299 for both apps in the companion.

The gap is about who owns the template. Tanka and cdk8s ship building blocks,
not an opinion on what a Deployment looks like, so the example carries its
own: `lib/shop/app.libsonnet` (58 lines) and `app.ts` (87 lines). Both spell
out fields Kubernetes would default, such as probe thresholds and
`defaultMode: 420`, to match the generator. In Kapitan the template is the
generator, maintained elsewhere and pinned by digest.

cdk8s has an opinionated layer too, [cdk8s+](https://cdk8s.io/docs/latest/plus/).
An 11-line `cdk8s-plus-36` program for the web Deployment produced a
`cdk8s.io/metadata.addr` selector, 1000m/512Mi requests, 1500m/2048Mi limits,
a read-only root filesystem and a TCP startup probe. Reasonable defaults, but
not the spec's, so the example stays on the low-level classes.

## Adding the second app

| | files changed | lines added | lines removed |
|---|---|---|---|
| Tanka | 3 | 29 | 0 |
| cdk8s | 1 | 16 | 5 |
| Kapitan | 3 | 38 | 2 |

All three reuse their template, so `api` is configuration only. cdk8s is
smallest partly through layout: its per-environment values are one object
literal per line, the Jsonnet and YAML files use one line per field. Helm needed 25 lines here and Kustomize 149.

## A value derived from another

All three compute `web_url` from the web Service port. In a copy I changed
only that port to 8081 in each tool. `check` still passed, and all three
rendered `web_url: http://web.shop.svc:8081`. In the same test Helm and
Kustomize rendered the stale `:80` without an error. For Tanka vs Helm and
cdk8s vs Helm this is the main difference: a language lets one value reference
another, separate Helm values files cannot.

The mechanisms differ. Jsonnet binds `$._config` late, so an environment that
overrides the web port also changes the api URL. In cdk8s it is an ordinary
variable, so the dependency follows your code structure. Kapitan [interpolates](/glossary/#interpolation)
`${...}` across the whole inventory, so any [class](/glossary/#class) or [target](/glossary/#target) can reference any
value in another file.

## Typos and type safety

I misspelled `pdb_min_available` as `pdb_min_availabe` in the prod web values
of each tool:

| | result |
|---|---|
| Tanka | renders, exit 0, web PodDisruptionBudget missing |
| cdk8s | synth fails: `error TS2561: ... 'pdbMinAvailabe' does not exist in type 'Sizing'. Did you mean to write 'pdbMinAvailable'?` |
| Kapitan | compiles, exit 0, `web-scaling.yaml` missing |

cdk8s catches it because the example declares an interface for its values,
and the generated imports type every Kubernetes field for the editor. Jsonnet
has no types: reading a missing field fails, adding a misspelled one does not,
unless you write `assert`s. [jsonnet-language-server](https://github.com/grafana/jsonnet-language-server)
adds completion. Kapitan's inventory is YAML, and neither Kapitan nor the
generator rejected the unknown key. An [output diff](/glossary/#output-diff) in CI, like `check`, caught
it in all three.

## Toolchain and speed

Install is one run with cold caches and depends on the network. Node.js 26 and
Python 3.13 were already present and are not counted. Render covers both
environments, five warm runs.

| | install | on disk | render |
|---|---|---|---|
| Tanka | 12.1 s for `tk` and `jb`, 3.4 s `jb install` | 29 MB + 7.3 MB | 0.10 to 0.11 s |
| cdk8s | 4.2 s `npm ci`, 173 packages | 95 MB | 3.46 to 3.59 s |
| Kapitan | 63.1 s `uv run`, 89 packages; 13.3 s generator verify and pull | 285 MB + 6.2 MB | 1.61 to 1.67 s |

Tanka is two static Go binaries and by far the fastest. Much of the cdk8s
time is ts-node type-checking the 41214-line import file: transpile-only, the
same synth took 2.27 to 2.36 s. Kapitan reports 0.68 s for the compile, the
rest is `uv run` and Python startup. Its install is large because the base
package depends on cloud SDKs for its secret backends:
`google-api-python-client` alone is 112 of the 267 MB installed.

## Reuse and packages

Tanka libraries are Git repositories that
[jsonnet-bundler](https://github.com/jsonnet-bundler/jsonnet-bundler) pulls
and locks by commit, with no central registry. jsonnet-bundler had no commits in the
last 12 months and its latest release, v0.6.0, dates from August 2024.

cdk8s uses npm or the package manager of its other languages, and
[Construct Hub](https://constructs.dev/) indexes published constructs.

The kadet-hub [catalog](/) lists 36 Kapitan generators, each an [OCI artifact](/glossary/#oci-artifact)
with a [build attestation](/glossary/#attestation). The registry is young: created on 2026-10-08, one
human committer so far.

All three consume Helm charts: Tanka through
[`tanka-util`](https://tanka.dev/helm/), cdk8s through `cdk8s import helm:`
and its `Helm` construct, Kapitan through its `helm` input type.

## Kapitan and Jsonnet

Kapitan has a `jsonnet` input type, so the choice is less exclusive than it
looks. I pointed a Kapitan target at the unchanged Tanka library and the
vendored k8s-libsonnet, with an 11-line `main.jsonnet` that reads the prod
values from the inventory. After the same normalization the output matched
`tk show environments/prod`, all 8 objects. A team with a Jsonnet codebase
can keep it and add inventory, [refs](/glossary/#ref) and non-Kubernetes outputs, giving up
`tk diff` and `tk apply` against a cluster.

## Output beyond Kubernetes

Tanka and cdk8s render Kubernetes objects. Plain Jsonnet can emit
Terraform's [JSON syntax](https://developer.hashicorp.com/terraform/language/syntax/json),
outside Tanka. CDKTF, the Terraform counterpart of cdk8s, was
[archived on 10 December 2025](https://github.com/hashicorp/terraform-cdk)
with no further updates. Kapitan compiles any output from one inventory, and
kadet-hub lists Terraform generators for AWS, AzureRM, Google Cloud and Open
Telekom Cloud, all at 0.1.x.

## GitOps

Argo CD renders Helm, Kustomize and plain
[Jsonnet](https://argo-cd.readthedocs.io/en/stable/user-guide/jsonnet/)
directories natively, Flux renders Helm and Kustomize. None of the three tools
is native to either. A Tanka environment does not fit Argo CD's Jsonnet support:
`tk eval` returns nested objects (`apps.web.deployment`) that Tanka flattens,
and the namespace comes from `spec.json`.

The usual routes are an Argo CD
[config management plugin](https://argo-cd.readthedocs.io/en/stable/operator-manual/config-management-plugins/)
that runs the tool in the repo server, or rendering in CI and committing the
YAML or pushing it with
[`flux push artifact`](https://fluxcd.io/flux/cmd/flux_push_artifact/). Tanka
has `tk export` for that, and Kapitan always writes files. cdk8s has one more
option: `cdk8s synth --format helm` writes a chart with `Chart.yaml` and
templates, which both Argo CD and Flux deploy natively.

## Project activity

Read-only GitHub API on 2026-10-17, window from 2025-10-17. Human commits
exclude bot and automation accounts.

| repository | stars | commits | human commits (authors) | releases | latest |
|---|---|---|---|---|---|
| grafana/tanka | 2690 | 500 | 41 (14) | 17 | v0.39.4, 2026-10-08 |
| cdk8s-team/cdk8s | 4859 | 499 | 7 (4) | 0 | umbrella repo |
| cdk8s-team/cdk8s-core | 87 | 578 | 0 | 90 | v2.70.111, 2026-10-12 |
| cdk8s-team/cdk8s-cli | 41 | 479 | 8 (4) | 125 | v2.207.67, 2026-10-13 |
| cdk8s-team/cdk8s-plus | 163 | 635 | 8 (6) | 330 | cdk8s-plus-37 v2.0.0, 2026-10-16 |
| kapicorp/kapitan | 1931 | 135 | 93 (11) | 6 | v0.36.3, 2026-07-03 |
| kadet-hub/registry | 1 | 716 | 711 (1) | 5 | index-47, 2026-10-16 |

441 of Tanka's 500 commits are Renovate updates. All 578 cdk8s-core commits
were automated dependency upgrades; its frequent releases carry those.
Kapitan releases less often and has the most human commits of the three tools.

## Running it

You need `tk` and `jb`, Node.js with npm, and uv, plus oras and a logged-in
gh for the first generator fetch:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/config-tools
$ ./check
```

The first run installs dependencies from the lock files and verifies the
generator's attestation before pulling it by digest; the
[companion post](/blog/same-app/) covers what that fetch does not check.
