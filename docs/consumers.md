# Using marketplace generators

A marketplace generator is an OCI artifact `ghcr.io/kadet-hub/<name>`. You
pin it by digest in your inventory and compile with the reusable consumer
workflow, which verifies what it fetches and runs Kapitan in the gVisor
sandbox the gate uses.

## Kapitan's `--fetch` is not enough

Kapitan 0.36.3 checks neither attestations nor digests when it fetches
dependencies, and runs generator code with your environment, your
credentials and network access. `kapitan compile --fetch` therefore gives no
integrity check and no sandbox. Use the workflow below, or perform its steps
yourself.

## Inventory

Take name and digest from the index (see Verifying by hand):

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/<name>@sha256:<digest>
        output_path: lib/<name>
```

## Workflow

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
    uses: kadet-hub/registry/.github/workflows/consumer.yml@<commit sha>
```

Pin the workflow by commit SHA; the scripts and the sandbox image it uses
belong to that commit. The compiled output is uploaded as the artifact
`compiled`. Review it before you apply it.

The workflow reads the policy `.kapitan-sandbox.yaml` at the repository root
(schema: [`policy/consumer.schema.json`](../policy/consumer.schema.json)):

```yaml
index_serial: 12              # lowest index serial you accept
inventory_backend: omegaconf  # optional; default reclass
hosts:                        # dependency hosts you allow, per type
  oci: [ghcr.io]
  helm: [charts.example.org]
  git: [github.com]
  https: []
binaries: ["helm template"]   # programs your own inputs run
output_capabilities:          # output you accept, per path below the output dir
  "compiled/logging/*": [host-path]
```

It then:

1. runs `kapitan inventory` in the sandbox, because the inventory backend
   imports `inventory/resolvers.py`;
2. rejects dependencies the policy does not allow, and those without a pin:
   OCI without digest, helm without exact version, git without commit SHA;
3. fetches the dependencies outside the sandbox and verifies every
   marketplace artifact: attestation from the marketplace release workflow,
   listed under its name in an attested index, not yanked, charts with the
   digest the index records;
4. compiles in the sandbox without network, with decoy credentials and a
   syscall trace that fails on any program not declared by the generators or
   your policy;
5. checks the output against the marketplace's output rules (privileged
   containers, `hostPath`, `cluster-admin` bindings, admission webhooks,
   Terraform provisioners and others; the list is under SEC-12 in the
   [spec](specs/marketplace.md#sandbox-and-runtime-detection)) and fails on
   a match that `output_capabilities` does not accept for its path. `*`
   in a glob also matches `/`. Files the rules cannot parse are listed, not
   judged.

`.git` and `.kapitan` are not passed to Kapitan. Missing refs must exist
before the workflow runs; it compiles without `--reveal` and without ref
backend credentials.

When the index serial is higher than `index_serial`, the workflow passes and
reports it; raise `index_serial` in a reviewed commit. A lower serial fails,
so an old index cannot be replayed to you.

## GitLab CI

```yaml
# .gitlab-ci.yml
include:
  - remote: https://raw.githubusercontent.com/kadet-hub/registry/<commit sha>/sandbox/gitlab-ci.yml
    inputs:
      ref: <commit sha>
```

The job `kadet-hub-compile` runs the same steps against a `docker:dind`
service and uploads the artifact `compiled`. Set a CI variable `GH_TOKEN`,
masked, holding a GitHub token without permissions; `gh attestation
verify` needs it. GitLab-hosted runners cannot run gVisor, so the syscall
trace is missing there: undeclared programs and reads of the decoy
credentials are not detected, and `/out` is not `noexec`. Network
isolation, the read-only root, decoy values in the output and the output
rules still apply.

## Verifying by hand

```sh
digest=$(oras resolve ghcr.io/kadet-hub/index:latest)
gh attestation verify "oci://ghcr.io/kadet-hub/index@$digest" --owner kadet-hub \
  --cert-identity https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
oras pull -o index "ghcr.io/kadet-hub/index@$digest"
jq '.serial, .generators["<name>"]' index/index.json

gh attestation verify "oci://ghcr.io/kadet-hub/<name>@sha256:<digest>" --owner kadet-hub \
  --cert-identity https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
```

Tags such as `1.2.0` are a convenience; organization owners can move them.
Only the digest, checked against the attested index, identifies what the
gate scanned.

## What a listing covers

A listed version passed the gate: secret, malware and code scans of the
generator tree, a fixture compile in the gVisor sandbox with a syscall trace
and decoy credentials, and a maintainer's review. The artifact contains
exactly the scanned tree, and its attestation ties the digest to the
marketplace release workflow on `main`.

A listing does not show that the generator is harmless in your project. The
[threat model](specs/marketplace.md#threat-model) and the
[residual risks](specs/marketplace.md#residual-risk) describe the limits; the
ones that matter most when you consume:

- Code that acts only on values from your inventory, or only when it does
  not detect the gate's sandbox, stays inert in the gate. The consumer
  sandbox bounds what it can reach, not what it writes into your output.
- Output can be harmful in your cluster or account while being valid, and
  within the capabilities a generator declares. Review the compiled output.
- One maintainer account controls the marketplace; its compromise produces
  correctly attested artifacts.
- The sandbox runs only in the workflow. A local `kapitan compile` of the
  same project runs the generator with your credentials.

Which checks are implemented is recorded per requirement (`Since:`) in the
[spec](specs/marketplace.md).
