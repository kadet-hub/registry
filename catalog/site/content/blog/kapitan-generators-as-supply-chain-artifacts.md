---
title: Kapitan generators as supply-chain artifacts
date: 2026-10-17
topics: [supply chain, gate, kapitan]
description: Why kadet-hub gate-checks Kapitan generators before listing them, what the sandboxed compile and API server dry runs caught, and how to use them.
---

Kapitan's kadet generators are Python packages that turn an inventory into
Kubernetes manifests, Terraform JSON or anything else. They are also code
that runs on your machine and in CI with access to your inventory and
secrets. In most projects they get copied between repositories and run
without review.

[kadet-hub](/) is a community catalog that treats them
like any other dependency you would want to pin and verify. It lists 35
generators today, among them Argo CD, cert-manager, Cilium, CloudNativePG,
Crossplane, External Secrets, Flux, KEDA, Kyverno, the Prometheus operator,
Velero and Terraform generators for AWS, AzureRM, Google Cloud and Open
Telekom Cloud.

## What a version goes through

Before a version is listed, a gate runs on the pull request that registers
it:

- secret, malware and code scans of the source;
- a compile of the generator's fixture targets in a gVisor sandbox without
  network, on every inventory backend it declares, once more with
  Kapitan's compile cache, which must produce identical output;
- validation of the rendered output against the JSON Schemas the
  generator ships;
- a server-side dry run of every built-in document, and of every custom
  resource whose CRD the generator ships, against a throwaway
  kube-apiserver.

A maintainer reviews the result. The version is then published to
`ghcr.io/kadet-hub/<name>` as an OCI artifact with a Sigstore signature,
an SBOM and a transparency log entry, and you pin it by digest in your
inventory.

## What the gate caught

The dry runs were added after schema validation alone let real bugs
through. Some examples from the generators now listed:

- probes rendered as empty objects (`startupProbe: {}`), which the API
  server rejects and a JSON Schema accepts;
- a Flux HelmRelease with both `chart` and `chartRef`, which violates a
  CEL rule in the CRD that no JSON Schema check evaluates;
- a generator whose submodule cached the inventory of the first target it
  was imported for, so the output depended on the order in which Kapitan
  compiled targets. The cache comparison showed it as a namespace that
  differed between two runs of the same commit.

The CRD dry run has its own write-up:
[Checking custom resources against their CRDs](/guides/checking-custom-resources-against-crds/).
It also covers operators that create their CRDs at runtime and publish
no YAML, such as KubeVirt and CDI, which leaves nothing to validate
against offline.

## Consuming and writing generators

The [consumer guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
shows how to pull a generator with Kapitan's `oci` dependency type and
verify it. `kapitan compile --fetch` checks neither signatures nor
digests, so a reusable GitHub workflow does the verification and compiles
your inventory in the same sandbox.

To write one, start from the
[generator template](https://github.com/kadet-hub/generator-template). Its
`./check` script runs the gate's scans and the sandboxed compile locally,
and [Writing a Kapitan generator](/guides/writing-a-kapitan-generator/)
documents the contract Kapitan gives a generator.

kadet-hub is a community project and is not affiliated with or endorsed by
the Kapitan project or kapicorp. Generator requests and feedback are
welcome as [issues](https://github.com/kadet-hub/registry/issues).
