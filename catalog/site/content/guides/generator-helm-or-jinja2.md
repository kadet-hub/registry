---
title: Kapitan generator vs Helm chart vs Kustomize
layout: prose
description: Choosing between a Kapitan kadet generator, the helm input, jinja2 templates and Kustomize, with concrete cases for each and the trade-offs.
---

Kapitan offers several inputs for the same goal, files rendered from the
inventory. They differ in where the knowledge lives.

| You have | Use | Why |
|---|---|---|
| An upstream chart whose values are the real interface | `helm` input, chart pinned | The chart owner maintains the logic; a generator around it only renames values |
| A file that mirrors the inventory almost 1:1 | `jinja2` or `copy` | A template is shorter than code and readers see the output shape |
| One entry that must become several consistent resources | kadet generator | Names, labels, ports and references are derived once, in code, and tested |
| The same manifests with per-environment patches | Kustomize, or classes in the inventory | Overlays express "the same, except"; a generator would hide the base |
| A format with structure YAML templating gets wrong (JSON dashboards, Terraform JSON) | kadet generator | Building data structures avoids quoting and indentation errors |

## Signs you picked the wrong one

- Your jinja2 template has loops over loops and `{% if %}` on every field:
  the logic wants to be code; a generator is easier to test.
- Your generator's inventory block has the same keys as its output: it
  adds a second schema to learn without adding knowledge. Ansible
  playbooks are the classic case; they are YAML already.
- You wrap a chart in a generator to set five values: use the `helm` input
  and keep `helm_values` in the inventory.

## Mixing them

One target can use all of them: the `helm` input for the operator's chart,
a generator for the custom resources you configure through it, and jinja2
for a README. Generators on kadet-hub are fetched like any other OCI
dependency, so they combine with the rest of your compile entries.

More in the author guide: [When not](https://github.com/kadet-hub/registry/blob/main/docs/authors.md#when-not).
