---
title: Supply-chain security for Kapitan generators
layout: prose
description: Why a third-party Kapitan generator runs with your credentials at compile time, what kadet-hub checks before listing one, and how to consume generators safely.
---

A [generator](/glossary/#generator) is code. When [Kapitan](/glossary/#kapitan) compiles, it imports the generator's
Python with your environment: your cloud credentials, your kubeconfig,
network access. A malicious or compromised generator can read them during
an ordinary `kapitan compile`, before any output is reviewed.

## What can go wrong

- **Credential theft at compile time**: the code reads `~/.aws`, `~/.kube`
  or environment tokens and sends them out.
- **Poisoned output**: the generator emits a privileged pod, a host path
  mount or a Terraform provisioner that runs on apply.
- **Moving targets**: a tag is re-pointed, so the same reference fetches
  different code tomorrow.
- **CI-aware payloads**: the code behaves only when it detects CI, or only
  outside the scanner's sandbox.

## What kadet-hub does before listing a version

Secret, malware and code scans of the tree; a compile of the fixture
project in a gVisor sandbox without network, with decoy credentials and a
trace of every program it starts; a check that the output uses only the
capabilities the manifest declares; a second compile with CI variables set;
schema validation; a maintainer's review. The published artifact is the
scanned tree, attested by the release workflow and pinned by [digest](/glossary/#digest); each
[attestation](/glossary/#attestation) is in Sigstore's public transparency log.

These checks find known patterns; they do not prove a generator harmless.
Code that acts only on values from your own [inventory](/glossary/#inventory) stays inert in the
[gate](/glossary/#gate). [What a listing covers](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#what-a-listing-covers)
lists the limits.

## How to consume safely

1. **Pin by digest**, never by tag: `ghcr.io/kadet-hub/<name>@sha256:...`.
2. **Verify the attestation** (`gh attestation verify`, command on each
   generator page) and set `index_serial` so a [rolled-back index](/glossary/#index) is refused.
3. **Compile in a sandbox**, not on a workstation with production
   credentials: the [consumer workflow](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#workflow)
   runs Kapitan in the same gVisor sandbox and checks the output.
4. **Review the compiled output** before you apply it, especially on a
   version bump.

Kapitan's own `--fetch` checks neither attestations nor digests and runs
the code with your environment, so it is not enough on its own.
