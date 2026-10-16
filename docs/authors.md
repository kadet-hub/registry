# Adding a generator

A generator is listed by a pull request that adds `generators/<name>.yaml`
to this repository. The gate checks the tagged source, a maintainer reviews
it, and after the merge the release workflow publishes the checked tree as
`ghcr.io/kadet-hub/<name>` and lists it on [kadet-hub.org](https://kadet-hub.org).
The fields of the manifest and the entry are defined under
[Registration](specs/registration.md#registration).

## When a generator is worth writing

A generator turns a compact block of inventory into output that would
otherwise be written by hand, many times, with the same decisions in it.
It pays off when it carries knowledge the inventory author should not have
to repeat:

- One input fans out into many resources that must agree with each other:
  a service entry that yields a Deployment, Service, ServiceAccount,
  NetworkPolicy, PodDisruptionBudget and ServiceMonitor with matching
  names, labels and ports.
- The output encodes defaults or conventions: resource requests, security
  contexts, label schemes, naming rules, which fields an operator needs
  together.
- Values have to be derived, not copied: a port list turns into container
  ports, Service ports and NetworkPolicy rules; a secret reference turns
  into an ExternalSecret and the volume that mounts it.
- The same intent must come out in several formats: a database entry that
  yields the operator's custom resource, a Grafana dashboard, alert rules
  and a runbook page.
- An upstream API is awkward to write by hand and stable enough to model:
  CRDs with deep nesting, shorthands that expand to verbose specs.

## When not

A generator that only reshapes YAML into the same YAML adds a layer
without adding knowledge. An Ansible generator is the standard example:
the inventory would hold the playbook's structure, the generator would
copy it into a playbook, and the result is the YAML the author could have
written directly, now with a second schema to learn. Signs that a
generator is the wrong tool:

- The inventory block mirrors the output field by field. Use a `jinja2` or
  `copy` input, or write the file.
- An upstream Helm chart already renders it and its values are the real
  interface. Use the `helm` input with the chart pinned; a generator that
  wraps a chart only renames its values. For what the values do not expose,
  [patch the rendered chart](#patching-a-helm-chart-instead-of-wrapping-it).
- It produces one resource with no defaults or derived values.
- The target tool has its own composition that does the job better, such
  as Kustomize overlays for per-environment patches of the same manifests.
- It would generate secrets or call out to the network at compile time.
  The gate forbids both; use Kapitan refs for secrets.
- It is specific to one project's naming and structure. Keep it in that
  project; the marketplace is for generators other projects can use with
  their own inventory.

## Designing a section

One entry, one intent. A section renders every object that belongs to one
intent and wires their references itself, so users never repeat a name to
keep two objects consistent. Contradicting keys fail the compile, naming
the entry. There is one way to express a thing; objects with their own
lifecycle or owner stay separate entries.

For example, one `rbac` entry of the `kubernetes` generator is a role with
its bindings: the ClusterRole and a RoleBinding in each listed namespace
share the entry's name, instead of a `roles` and a `role_bindings` entry
whose `roleRef` repeats it. A Kyverno policy and its PolicyException stay
apart, because exceptions are scoped and owned separately.

## Patching a Helm chart instead of wrapping it

The marketplace lists no generic `helm` generator that renders a chart
named in your inventory ([DEC-15](specs/marketplace.md#decisions)): the
gate pins and scans only the charts a manifest declares
([SEC-8](specs/gate.md#dependencies-binaries-and-charts)), so it cannot
vouch for yours. Kapitan renders a pinned chart itself, and a short kadet
step in your own project patches what the chart's values do not expose.
That is the overlay stage asked for in
[kapicorp/kapitan#527](https://github.com/kapicorp/kapitan/issues/527).
Kapitan's `kustomize` input can patch as well, but it runs the `kustomize`
binary, which the sandbox image does not carry.

A class pins the chart, renders it with the `helm` input and runs the kadet
step over the same `output_path`. Kapitan runs compile entries in order and
passes the kadet step that directory as `input_params.compile_path`.
Patches are a map keyed `<kind>/<name>`, not a list, because the inventory
merges maps across classes and targets but appends lists:

```yaml
# inventory/classes/podinfo.yml
parameters:
  podinfo:
    namespace: apps
    patches:
      Deployment/podinfo:
        spec:
          strategy:
            rollingUpdate:
              maxUnavailable: 0
  kapitan:
    dependencies:
      - type: helm
        source: https://stefanprodan.github.io/podinfo
        chart_name: podinfo
        version: 6.15.0
        output_path: charts/podinfo
    compile:
      - input_type: helm
        input_paths:
          - charts/podinfo
        output_path: podinfo
        helm_params:
          name: podinfo
          namespace: ${podinfo:namespace}
        helm_values:
          replicaCount: 2
      - input_type: kadet
        input_paths:
          - components/patch
        output_path: podinfo
        output_type: auto
        input_params:
          patches: ${podinfo:patches}
```

A target, or a class per environment, adds its own patches on top; this one
ends up with both:

```yaml
# inventory/targets/prod.yml
classes:
  - podinfo

parameters:
  kapitan:
    vars:
      target: prod
  podinfo:
    patches:
      Deployment/podinfo:
        spec:
          template:
            spec:
              terminationGracePeriodSeconds: 60
```

The kadet step reads every file the helm entry wrote, merges each patch
into the documents of that kind and name, maps recursively while lists and
other values replace, and writes the files back under their names, which
`output_type: auto` keeps. A patch that matches no document fails the
compile, so a chart upgrade that renames a resource cannot drop a patch
silently.

```python
# components/patch/__init__.py
"""Patch the documents the helm entry before this one rendered (docs/authors.md)."""

import os

import yaml
from kapitan.inputs.kadet import BaseObj, CompileError


def merge(base, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value


def main(input_params):
    root = input_params["compile_path"]
    patches = input_params.get("patches") or {}
    unmatched = set(patches)
    out = BaseObj()
    for folder, _, files in os.walk(root):
        for file in files:
            path = os.path.join(folder, file)
            with open(path, encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            for doc in docs:
                key = f"{doc.get('kind')}/{doc.get('metadata', {}).get('name')}"
                if key in patches:
                    merge(doc, patches[key])
                    unmatched.discard(key)
            out.root[os.path.relpath(path, root)] = docs
    if unmatched:
        raise CompileError(f"patches match no rendered document: {sorted(unmatched)}")
    return out
```

`kapitan compile --fetch` pulls the chart into `charts/podinfo`, pinned by
version only, without a digest or a sandbox
([Kapitan's `--fetch` is not enough](consumers.md#kapitans---fetch-is-not-enough)).
The [consumer workflow](consumers.md#workflow) pulls it outside the sandbox
and compiles without network, with this `.kapitan-sandbox.yaml`:

```yaml
index_serial: 0
hosts:
  helm: [stefanprodan.github.io]
binaries: ["helm template"]
```

These files are the sample
[`tests/consumers/pass-helm-patch`](../tests/consumers/pass-helm-patch),
which the consumer selftest compiles with the Kapitan version the gate pins
and checks for both patches in the output.

## Ideas

Generators that would be useful to many Kapitan projects, beyond rendering
one operator's resources:

- **Workload bundles**: one service entry to Deployment, Service,
  autoscaling, disruption budget, network policy and monitoring, with
  security defaults that pass admission policies.
- **Policy as code**: Kyverno or Gatekeeper policies and their exceptions
  from a short list of rules and namespaces.
- **Observability from the inventory**: Prometheus rules, Grafana dashboards
  and alert routing generated from the services and SLOs the inventory
  already lists.
- **Network intent**: NetworkPolicies, Cilium policies or Gateway API
  routes from a service dependency graph.
- **GitOps wiring**: Argo CD Applications or ApplicationSets, Flux
  Kustomizations, one per target.
- **Platform catalogs**: Backstage `catalog-info.yaml` and ownership data
  from the same inventory that deploys the service.
- **Cloud resources**: Terraform JSON for buckets, DNS records, IAM bindings
  that a workload needs, next to the Kubernetes side.
- **Pipelines**: GitLab CI or GitHub Actions workflows for each target,
  with the compile and diff steps the project uses.
- **Documentation**: runbooks, README sections and Mermaid diagrams of the
  deployed topology, generated from the values that are actually deployed.
- **Container builds**: Dockerfiles with pinned bases and labels from a
  short image description.

If you would use one of these but will not write it, [request
it](https://github.com/kadet-hub/registry/issues/new?template=generator-request.yml).

## In your repository

The quickest start is the template repository
[kadet-hub/generator-template](https://github.com/kadet-hub/generator-template):
it has the files below, a `./check` script that runs the gate's ruff
rules and sandbox compile locally, and `AGENTS.md` for coding agents.


The generator lives in a public repository on github.com or gitlab.com, in
its own directory or at the root. That directory carries:

- `kapitan-generator.yaml`, the manifest. `owners` are GitHub numeric user
  IDs (`gh api users/<login> --jq .id`). Every program the generator starts
  is declared in `binaries`, every chart it renders in `charts` with the
  sha256 of the `.tgz`; `dependencies` stays empty.
- a fixture project, the directory named in `fixtures`: an ordinary Kapitan
  project with a `minimal` target, whose compile entries load the generator
  from `lib/<name>`, where the gate places it.
- `README.md` with an inventory example in a fenced code block,
  `CHANGELOG.md` with a heading for the version (`## 1.4.0`), and `LICENSE`
  here or at the repository root. `license` in the manifest is one of
  [`policy/licenses.txt`](../policy/licenses.txt), and `LICENSE` has to
  read as that license. The catalog shows the README of the latest
  version as Markdown: raw HTML is dropped, images become links, and
  relative links point into your repository at the pinned commit.

The Python code has to pass `ruff check` with
[`policy/ruff.toml`](../policy/ruff.toml): syntax errors and pyflakes
findings, no style rules; `noqa` comments do not count.

What Kapitan passes to `main()` and does with its return value, the
inventory and naming conventions, and the gate rules for the code are
collected in the
[generator contract](https://kadet-hub.org/guides/writing-a-kapitan-generator/#generator-contract).

Tag the commit with a semver, optionally prefixed for repositories with
several generators (`v1.4.0`, `argocd-v1.4.0`).

## The pull request

```yaml
# generators/<name>.yaml
source:
  repo: https://github.com/<owner>/<repo>.git
  path: <generator dir>   # "." at the root
  tag: v1.4.0
  sha: <git rev-parse v1.4.0^{commit}>
owners: [<GitHub user ID>, ...]
```

The pull request changes only this file, is opened by one of the
manifest's owners, and lists the same owners as the manifest at `sha`. Opening it accepts the [terms of listing](../TERMS.md): you
allow the marketplace to republish the tree under its license and confirm
you have the rights to it.

The gate fetches the tree at `sha` without running it, scans it for
secrets, malware and dangerous code, and compiles the fixture project in a
gVisor sandbox without network, with decoy credentials and a syscall trace.
A program not declared in `binaries`, a read of a decoy or a network attempt
fails the gate. The gate posts its result as a comment; a maintainer reviews
the code and merges. Which checks are implemented is recorded per
requirement in the [spec](specs/marketplace.md).

A static finding that is a false positive can be excepted in the entry,
bound to the file's content:

```yaml
exceptions:
  - rule: gitleaks:generic-api-key   # rule IDs: spec SEC-14
    path: tests/consumer/inventory/classes/demo.yml
    sha256: <sha256sum of that file>
```

The exception lapses when the file changes. Malware, GuardDog, sandbox
and output findings cannot be excepted; the maintainer decides on every
exception in review.

## New versions and yanking

Renovate opens a pull request when you push a newer tag with the same
prefix; the gate and the review run again on the new commit. When a version
moves to a newer release of the software it renders for, update its
`schemas/` and `schemas/sources.yaml` in the same commit: the gate
validates each version against its own schemas, and the catalog's "Built
for" comes from them. You can also
open the bump yourself. The version must increase, and `repo` and `path`
stay fixed.

A generator that renders Terraform ships the schema of the provider
version it pins in `required_providers` instead of JSON Schemas. In the
compiled output directory, after `terraform init -backend=false`, run
`terraform providers schema -json > full.json`, then reduce it to the
types your output uses with `sandbox/tf_schema.py` from a registry
checkout:

```sh
python3 sandbox/tf_schema.py extract --full full.json --out compiled/ \
  > schemas/terraform/hashicorp_aws_6.68.0.json
```

and add an entry keyed `terraform/hashicorp/aws` to `schemas/sources.yaml`.
The gate then checks every provider block, resource and data source
against it ([QA-8](specs/gate.md#quality-gate)); regenerate the file
whenever you raise the pinned version.

A generator that renders custom resources can also ship the CRDs of
their kinds, one per file, as `schemas/<group>/crds/<plural>.yaml`: the
upstream file byte for byte when it holds only that CRD and is at most
1 MiB, otherwise `<plural>.json` with the CRD as compact JSON. The
group's `sources.yaml` entry covers them. The gate installs them in a
throwaway kube-apiserver and creates every custom resource of their kinds
with a server-side dry run, which also evaluates the CEL rules the JSON
Schemas cannot ([QA-11, QA-12](specs/gate.md#quality-gate)). Kinds
without a CRD get a review line.

To withdraw a version, add it under `yanked` with a reason. The catalog
then shows the reason instead of the inventory entry. A version that is
malicious is reported as described in [SECURITY.md](../SECURITY.md).

## Badge

Below its buttons, each generator page has a "Badge" disclosure with the
Markdown for a [shields.io](https://shields.io) badge that shows the latest
listed version and links the page:

```markdown
[![kadet-hub](https://img.shields.io/endpoint?url=https://kadet-hub.org/generators/<name>/badge.json)](https://kadet-hub.org/generators/<name>/)
```

shields.io reads `badge.json`, which every catalog build rewrites, so the
badge follows new versions without a commit in your repository. Once no
version is listed, it reads "not listed".
