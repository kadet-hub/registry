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

Every key of `out.root` becomes one output file. Keep to the
[import allowlist](https://github.com/kadet-hub/registry/blob/main/policy/imports.txt):
no subprocesses, no network, no `eval`. Make the output deterministic.

## 4. Ship the schemas of what you emit

Put the JSON Schema of every kind you render under `schemas/` and name its
upstream source in `schemas/sources.yaml`. The gate validates your output
against them and the catalog shows "Built for" from them. When you move to
a newer upstream release, update the schemas in the same commit.

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
