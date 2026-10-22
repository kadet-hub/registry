---
title: Validate Kubernetes custom resources against their CRDs
layout: prose
description: Why JSON Schema checks miss rejected custom resources, how a throwaway kube-apiserver dry run catches them, and what to do when upstream ships no CRD YAML.
lastmod: 2026-10-19
---

A rendered manifest can be valid YAML, match the JSON Schema of its [kind](/glossary/#kind)
and still be rejected by the cluster. For built-in kinds that gap is small.
For [custom resources](/glossary/#crd) it is wide, because a CustomResourceDefinition carries
more than a schema.

## What a JSON Schema check misses

Tools such as kubeconform validate each document against a JSON Schema
extracted from the CRD's `openAPIV3Schema`. That catches wrong types,
missing required fields and, in strict mode, unknown fields. It does not
evaluate:

- CEL rules in `x-kubernetes-validations`, which operators use for
  cross-field constraints;
- which versions the CRD serves, so a manifest in a version that was
  dropped still passes against an old schema file;
- the API server's own checks, such as name formats and immutable fields.

Flux shows the first case. A `helm.toolkit.fluxcd.io/v2` HelmRelease must
set either `chart` or `chartRef`. Both fields are optional in the schema,
so a release that sets both passes every JSON Schema check. The API server
answers `spec: Invalid value: either chart or chartRef must be set`.

## A throwaway API server

The check that sees what the cluster sees is the cluster's API server.
It does not need a cluster: etcd and kube-apiserver alone, on loopback,
with their state in a temporary directory, start in a few seconds. No
kubelet, no scheduler, no network.

The procedure:

1. Install the CRDs and wait until each is `Established` and the server
   lists its versions.
2. Create the namespaces the output uses.
3. `POST` every document with `dryRun=All&fieldValidation=Strict`. Nothing
   is persisted; `Strict` turns unknown fields into errors instead of
   warnings.

Two details matter. Admission plugins that look objects up, such as
`ServiceAccount`, `Priority` and `RuntimeClass`, reject documents that
refer to objects the same output would create, so they are switched off.
And a CRD with a conversion webhook has no webhook to call; the [dry run](/glossary/#server-side-dry-run)
still converts to the storage version, so the check installs it with
conversion `None`.

On a laptop, [envtest](https://book.kubebuilder.io/reference/envtest)
binaries or a [kind](https://kind.sigs.k8s.io/) cluster give the same
answer with `kubectl apply --dry-run=server -f compiled/`.

## How kadet-hub runs it

The [gate](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate)
validates every listed version in three layers: the JSON Schemas the
[generator](/glossary/#generator) ships (QA-7), a dry run of built-in kinds (QA-10), and a dry run
of every custom resource whose CRD the generator ships (QA-11). The CRDs
live in `schemas/<group>/crds/<plural>.yaml`, one per file, as the
upstream file byte for byte, or as compact JSON when the upstream file
holds several CRDs or exceeds 1 MiB (QA-12). The
[weekly upstream update](https://github.com/kadet-hub/generators/blob/main/docs/specs/upstream.md)
regenerates them at each new release and only proposes files it can
reproduce byte for byte at the current one.

In the first run, 23 generators shipped 147 CRDs, and all 304 custom
resources their fixtures render were accepted. Adding the CRDs cost a
few seconds per check.

## When upstream publishes no CRD YAML

Some operators create their CRDs at runtime and never publish them as
files. KubeVirt v1.9.1 ships one CRD in its release assets,
`kubevirts.kubevirt.io`; the other 19, VirtualMachine among them, are
built by virt-operator from Go code. CDI v1.66.1 is the same with
`cdis.cdi.kubevirt.io` and eleven runtime CRDs such as DataVolume.
Linkerd's CRDs exist only as Helm templates.

Offline validation has nothing to load for these kinds: no JSON Schema
check, no server dry run, no GitOps diff against the schema. kadet-hub
asked both projects to publish the CRDs as release assets
([kubevirt/kubevirt#19429](https://github.com/kubevirt/kubevirt/issues/19429),
[kubevirt/containerized-data-importer#4316](https://github.com/kubevirt/containerized-data-importer/issues/4316)).
Until then the gate validates what it can and prints a review line per
`apiVersion` it could not check, so a reviewer reads those documents
instead of trusting a green result.

If you maintain an operator: publish every CRD your operator installs as
plain YAML with each release, at a stable path. It costs one build step
and lets every downstream tool validate against your real API.
