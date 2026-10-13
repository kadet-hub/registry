---
title: Writing a Kapitan generator
layout: prose
description: How to write a reusable Kapitan kadet generator, test it in a sandbox like the kadet-hub gate does, and publish it as an attested OCI artifact.
---

A Kapitan generator is a kadet module: Python that reads a block of
inventory parameters and returns the files Kapitan writes. One generator
replaces the same hand-written manifests in every target that needs them.

## 1. Check that a generator is the right tool

A generator pays off when one inventory entry fans out into several
resources that must agree, when it carries defaults or conventions, or when
values have to be derived rather than copied. If your inventory would
mirror the output field by field, a `jinja2` or `helm` input is simpler.
The author guide lists the cases in
[When a generator is worth writing](https://github.com/kadet-hub/registry/blob/main/docs/authors.md#when-a-generator-is-worth-writing).

## 2. Start from the template

Use [kadet-hub/generator-template](https://github.com/kadet-hub/generator-template)
("Use this template" on GitHub). Its `example/` directory already has the
manifest, a fixture project with the required `minimal` target, a README
with an inventory example, a changelog and a schema. Rename it to your
generator's name.

## 3. Write `main()`

```python
from kapitan.inputs.kadet import BaseObj, inventory

def main(input_params=None):
    config = inventory().parameters.get("generators", {}).get("example", {})
    out = BaseObj()
    for name, spec in config.get("configmaps", {}).items():
        out.root[f"{name}-cm"] = {"apiVersion": "v1", "kind": "ConfigMap",
                                  "metadata": {"name": name}, "data": dict(spec.get("data", {}))}
    return out
```

What `main()` receives and returns, and the rules the gate applies to it,
are in the [generator contract](#generator-contract) below.

## 4. Ship the schemas of what you emit

Put the JSON Schema of every kind you render under `schemas/` and name its
upstream source in `schemas/sources.yaml`; the contract says
[what the gate and the catalog do with them](#schemas-and-built-for). When
you move to a newer upstream release, update the schemas in the same
commit.

## 5. Check locally, then publish

`./check example` runs the gate's code rules and compiles your fixtures in
the sandbox image without network, with the tag and schema checks. Then tag
the commit (`example-v0.1.0`) and open the entry pull request described in
[Adding a generator](https://github.com/kadet-hub/registry/blob/main/docs/authors.md#the-pull-request).
The gate adds secret, malware and code scans and a traced compile in
gVisor; a maintainer reviews the code; the release publishes it attested
and pinned by digest.

Working with a coding agent: point it at the template's
[AGENTS.md](https://github.com/kadet-hub/generator-template/blob/main/AGENTS.md).

## Generator contract

This section states what Kapitan 0.36, the version the gate pins, and the
kadet-hub gate expect from a generator; each gate rule links the
requirement that defines it.

### Files

A generator is a directory with `__init__.py`; modules next to it are
imported relatively (`from .base import ...`). To be listed, the directory
also carries the manifest, a fixture project, `README.md`, `CHANGELOG.md`
and a license, as described in
[In your repository](https://github.com/kadet-hub/registry/blob/main/docs/authors.md#in-your-repository).

### Wiring a target

A target fetches the generator into `lib/` and points a kadet compile entry
at it; the settings live in the inventory:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/example@sha256:<digest>
        output_path: lib/example
    compile:
      - input_type: kadet
        input_paths:
          - lib/example
        output_path: manifests
        input_params: {}        # optional, passed to main()
  generators:
    example:
      configmaps:
        settings:
          data:
            LOG_LEVEL: info
```

[Using marketplace generators](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
covers the digest, its verification and the sandboxed compile.

### What `main()` receives

For each path in `input_paths`, Kapitan imports its `__init__.py` and calls
`main(input_params)`, or `main()` when it takes no argument; a `main()` with
more than one parameter fails the compile. `input_params` is a copy of the
entry's `input_params` as the inventory renders them, plus `compile_path`,
the directory the entry writes to, unless the entry sets it. No key is
required. Use it to select what one entry renders, as grafana's
`function: generate_manifests` does, and keep the settings in the
inventory.

The inventory comes from `kapitan.inputs.kadet`: `inventory()` returns the
current target's, with attribute access (`inventory().parameters.generators`),
`inventory_global()` every target's, keyed by name, and `topics()` the
targets that publish a topic, which argocd uses for one Application per
target.

An exception in `main()` fails the target with
`Could not load Kadet module: <directory>` and your exception as the cause,
so its message should name the inventory key at fault.

### What `main()` returns

A `BaseObj` or `BaseModel`. Every key of its `root` is one file below the
entry's `output_path`, and a `/` in the key creates a directory. The
entry's `output_type` sets format and extension: `yaml` by default, so the
key `settings-cm` from step 3 becomes `manifests/settings-cm.yaml`; `auto`
keeps a `.yaml`, `.yml`, `.json` or `.toml` extension given in the key. A
list value is written as a multi-document YAML file. A fixture target that
writes no file fails the gate
([CMP-1](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#compile-gate)).

### Inventory key and file names

These are the conventions of
[kadet-hub/generators](https://github.com/kadet-hub/generators); the gate
checks none of them, and each README's inventory example shows what its
generator reads.

- Settings live under `parameters.generators.<name>`, one map per kind
  keyed by resource name, as `generators.example.configmaps.settings`
  above. external-secrets, opentelemetry-operator and prometheus-operator
  write the key with `_` (`external_secrets`); kubernetes reads
  `parameters.components` and `generators.manifest`.
- The namespace comes from the resource entry, then
  `generators.<name>.namespace`, then `parameters.namespace`, then
  `default`.
- A namespaced resource is written to `<namespace>/<name>-<kind suffix>`,
  a cluster-scoped one to `<name>-<kind suffix>`.

### Defaults, `spec` and flat keys

Resource entries accept `namespace`, `labels`, `annotations` and a `spec`
map that passes through to the resource's `spec`, next to flat keys and
shorthands for the fields the generator models. Precedence, lowest first:
generator defaults, `spec`, flat keys and shorthands. A flat key that
overrides a field also set in `spec` wins and logs:

```text
Flat key '<key>' overrides spec passthrough '<field>' for resource '<name>'
```

A README says where its generator differs, for example when a flat key
replaces a whole `spec` field instead of merging into it.

### Gate rules

- Imports: only the
  [import allowlist](https://github.com/kadet-hub/registry/blob/main/policy/imports.txt),
  checked on the syntax tree, with `subprocess` only for a declared
  program, and no `eval`, `exec` or process functions of `os`
  ([SEC-3](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#static-checks)).
- Programs: only those declared in `binaries` and allowed with their
  subcommand in
  [`policy/binaries.txt`](https://github.com/kadet-hub/registry/blob/main/policy/binaries.txt),
  such as `helm template`, enforced on the syscall trace
  ([SEC-7](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#dependencies-binaries-and-charts),
  [SEC-10](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection)).
  A chart the generator renders is declared in `charts` with its sha256
  and scanned like the code
  ([SEC-8](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#dependencies-binaries-and-charts)).
- Network and secrets: the fixture compile runs without network and with
  decoy credentials; a connection attempt, a read of a decoy or a decoy
  value in the output fails it
  ([SEC-9 to SEC-11](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection)).
  Secrets reach the output as Kapitan refs (`?{...}`) from the inventory.
- Determinism: a second compile with `CI`, `GITHUB_ACTIONS` and `GITLAB_CI`
  set must write identical output
  ([CMP-2](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#compile-gate)),
  so no timestamps, random values or environment lookups.
- Output: every file is parsed by its extension and policy-checked.
  Privileged pods, host paths, cluster-admin RBAC and the other
  capabilities of
  [SEC-12](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection)
  are declared in `output_capabilities`, files without a parser, such as
  `*.md`, in `unparsed_outputs`.

### Schemas and "Built for"

`schemas/` holds the JSON Schema of every emitted kind as
`<group>/<kind>_<version>.json`, with the kind in lower case and `core` for
the core group, and `schemas/sources.yaml` names each group's software,
version and pinned upstream source. The gate validates every compiled
document of a group it has schemas for
([QA-7](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate));
a Terraform generator ships a reduced provider schema instead
([QA-8](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate),
[how](https://github.com/kadet-hub/registry/blob/main/docs/authors.md#new-versions-and-yanking)).
The catalog's "Built for" lists the software and version of each schema
group the output was validated against
([CAT-15](https://github.com/kadet-hub/registry/blob/main/docs/specs/catalog.md#catalog)),
so it follows the schemas, not the README.
