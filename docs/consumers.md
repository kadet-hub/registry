# Using marketplace generators

A marketplace generator is an OCI artifact `ghcr.io/kadet-hub/<name>`. You
pin it by version and digest in your inventory and compile with the
reusable consumer workflow, which verifies what it fetches and runs Kapitan
in the gVisor sandbox the gate uses.

## Kapitan's `--fetch` is not enough

Kapitan 0.36.3 checks neither attestations nor digests when it fetches
dependencies, and runs generator code with your environment, your
credentials and network access. `kapitan compile --fetch` therefore gives no
integrity check and no sandbox. Use the workflow below, or perform its steps
yourself.

For a local compile, install Kapitan the way the sandbox does:

```sh
uv tool install --with omegaconf==2.4.0.dev4 'kapitan[omegaconf,reclass-rs]==0.36.3'
```

omegaconf 2.4.0 removed `ListMergeMode`, so without the pin the OmegaConf
backend fails with `ImportError: cannot import name 'ListMergeMode'`
(kapicorp/kapitan#1621). The `omegaconf` and `reclass-rs` extras do not
install `oras`, which Kapitan's `oci` dependencies need;
`kapitan compile --fetch` then stops with `The 'oras' package is required
for OCI dependencies`. Rather than adding the `oci` extra, fetch by digest
after verifying (see Verifying by hand) and compile without `--fetch`:

```sh
oras pull -o "$tmp" "ghcr.io/kadet-hub/<name>@sha256:<digest>"
mkdir -p lib/<name> && tar -xf "$tmp/<name>.tar" -C lib/<name> --no-same-owner
```

## Inventory

Copy the entry from the generator's page on the catalog, or take name,
version and digest from the index (see Verifying by hand):

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/<name>:<version>@sha256:<digest>
        output_path: lib/<name>
```

The digest decides what is fetched and verified. The tag must be the version
the index lists for that digest, otherwise the workflow fails; without a tag,
`ghcr.io/kadet-hub/<name>@sha256:<digest>` still works. Consumer workflow
commits before kadet-hub/registry#234 reject the tag with `source must be
<host>/<repository>@sha256:<digest>`, so move your workflow pin to a later
commit before you add tags.

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
belong to that commit. The workflow compiles the Kapitan project at the
repository root; a project in a subdirectory needs its own repository. The compiled output is uploaded as the artifact
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
   listed under its name in an attested index with the version its tag
   names, not yanked, charts with the digest the index records;
4. compiles in the sandbox without network, with decoy credentials and a
   syscall trace that fails on any program not declared by the generators or
   your policy;
5. checks the output against the marketplace's output rules (privileged
   containers, `hostPath`, `cluster-admin` bindings, admission webhooks,
   Terraform provisioners and others; the list is under SEC-12 in the
   [spec](specs/gate.md#sandbox-and-runtime-detection)) and fails on
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

## Updates with Renovate

The preset [kadet-hub/renovate-config](https://github.com/kadet-hub/renovate-config)
finds tagged marketplace sources in `**/inventory/**/*.yml` and
`**/inventory/**/*.yaml`, so in an `inventory/` directory at the repository
root or in a nested Kapitan project, and opens a pull request per update
that changes tag and digest together. It does not merge on its own.

```json
{
  "extends": ["github>kadet-hub/renovate-config"]
}
```

Renovate reads the tags on ghcr.io, not the index, so it can propose a
version that was yanked after its release. The workflow fails that pull
request because the index lists the version as yanked. Close it: Renovate
does not propose a closed version again, and a closed major update skips
that whole major line.

## Picking a version by what it is built for

Each version records the software and versions whose schemas its compiled
output was checked against. On the catalog, the generator page lists them
for every listed version, and the compatibility page for every listed
version of every generator. Both have a selector "I run <software>
<version>". When no listed version is built for exactly your version, it
shows the versions built for the nearest newer one and says that they were
not checked against yours.

Tools read the same records from `https://kadet-hub.org/catalog.json`, the
data the catalog is built from:

- `generators[].name`: the generator.
- `generators[].versions[]`: every version, newest first, with `version`,
  `digest`, `yanked` (the reason, or `null` while listed) and
  `compatibility`, a list of `software`, `version` and the schema `source`.
  Versions published before the record existed have no `compatibility`;
  the catalog shows them as "not recorded".
- `kinds`: the Kubernetes kinds of each generator's latest listed version,
  keyed by section and then by kind in lower case. A section is the API
  group, `core` for `v1` without a group, and the version for any other
  apiVersion without a group, such as `v1alpha1` for Talos machine config.
  Keys of `kinds` are therefore not always API groups. Each entry holds the
  kind's `name`, the generators whose fixture output renders it
  (`rendered`), those that only ship a schema for it (`schema`), its
  `versions` as apiVersion to generators, and `page`, true when the kind
  has its own page at `/kinds/<section>/<kind>/`.
- `sections`: the section names, split into `builtin` (served by
  kube-apiserver without CRDs) and `custom`.

The listed certmanager versions built for cert-manager 1.21.2, one
`<version> <digest>` line each, newest first:

```sh
curl -fsSL https://kadet-hub.org/catalog.json | jq -r --arg name certmanager --arg software cert-manager --arg version 1.21.2 '
  .generators[] | select(.name == $name) | .versions[]
  | select(.yanked == null and any(.compatibility[]?; .software == $software and .version == $version))
  | "\(.version) \(.digest)"'
```

The generators that render a ConfigMap, one `<section> <generators>` line
per section:

```sh
curl -fsSL https://kadet-hub.org/catalog.json | jq -r --arg kind configmap '
  .kinds | to_entries[] | select(.value[$kind]) | "\(.key) \(.value[$kind].rendered | join(" "))"'
```

To have Renovate propose only versions built for your upstream line,
replace the preset's lookup for that generator with a custom datasource that
filters `catalog.json`. This configuration proposes certmanager versions
built for cert-manager 1.21.x:

```json
{
  "extends": ["github>kadet-hub/renovate-config"],
  "customDatasources": {
    "kadet-hub-certmanager": {
      "defaultRegistryUrlTemplate": "https://kadet-hub.org/catalog.json",
      "transformTemplates": [
        "{\"releases\": [generators[name = 'certmanager'].versions[$not(yanked) and compatibility[software = 'cert-manager' and $contains(version, /^1\\.21\\./)]].{\"version\": version, \"digest\": digest}]}"
      ]
    }
  },
  "customManagers": [
    {
      "customType": "regex",
      "managerFilePatterns": ["**/inventory/**/*.yml", "**/inventory/**/*.yaml"],
      "matchStrings": ["source:\\s*[\"']?(?<depName>ghcr\\.io/kadet-hub/certmanager):(?<currentValue>[0-9.]+)@(?<currentDigest>sha256:[0-9a-f]{64})"],
      "datasourceTemplate": "custom.kadet-hub-certmanager",
      "versioningTemplate": "semver"
    }
  ],
  "packageRules": [
    {"matchDatasources": ["docker"], "matchPackageNames": ["ghcr.io/kadet-hub/certmanager"], "enabled": false}
  ]
}
```

The package rule turns off the preset's lookup on ghcr.io for certmanager,
so only the filtered datasource proposes updates. Renovate takes the new
digest from `releases[].digest`, so a pull request changes tag and digest
together, as the preset's do. When you move to another cert-manager line,
change the filter.

`catalog.json` is not signed. GitHub Pages serves it, and whoever can change
the site or its domain can change it. That is acceptable for proposals: the
consumer workflow still verifies the digest against the attested index and
fails when the index does not list it or lists it as yanked (CON-2 in the
[spec](specs/consumers.md)). Do not fetch what `catalog.json` names without
that check; the signed records are in `index.json` (see Verifying by hand).

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

Index serials published since kadet-hub/registry#249 are also GitHub
releases `index-<serial>` of the registry. The release's `index.json`
verifies against its Sigstore bundle with the same identity:

```sh
gh release download index-<serial> --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json --owner kadet-hub \
  --cert-identity https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
jq .serial index.json
```

`gh attestation verify` prints its result only on a terminal; in a script
or CI it is silent and only the exit status tells pass from fail. Add
`--format json` to see what was verified. Without `--predicate-type` it
checks the SLSA provenance only. Versions published since
kadet-hub/registry#47 also carry an SBOM, and those since #226 that follow
an earlier listed version an output diff:

```sh
for type in https://spdx.dev/Document/v2.3 https://kadet-hub.org/output-diff/v1; do
  gh attestation verify "oci://ghcr.io/kadet-hub/<name>@sha256:<digest>" --owner kadet-hub \
    --predicate-type "$type" \
    --cert-identity https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
done
```

`index.json.intoto.jsonl` holds the same signed provenance in the in-toto
bundle format, without the certificate; verify with the Sigstore bundle.

Tags such as `1.2.0` and `index-<serial>` are a convenience; organization
owners can move them.
Only the digest, checked against the attested index, identifies what the
gate scanned.

## Mirrored images

The release workflow copies a few third-party images into
`ghcr.io/kadet-hub/mirror/<name>`, because upstream keeps no stable tag.
kadet-hub does not modify or rebuild them. A mirror tag is the image's
source commit and its digest is the upstream digest. The run summary of the
release run that pushed a tag records the upstream reference and digest
and the source links for that tag.

`ghcr.io/kadet-hub/mirror/kubevirt-csi-driver` copies
`quay.io/kubevirt/kubevirt-csi-driver:latest`. The first mirrored tag is
`3a1a099330045754011803e3d53cd8276ff21723` at
`sha256:44c98353e6137455d6a393ad13e04f60e10ee49fdcd00cf078f7f7084714f409`.
Each tag is a commit of
[kubevirt/csi-driver](https://github.com/kubevirt/csi-driver), taken from
the image label `multi.GIT_SHA`, so its source is
`https://github.com/kubevirt/csi-driver/tree/<tag>`. The base image is
CentOS Stream 9, whose packages are partly GPLv2. Their source RPMs are
published by CentOS in the
[BaseOS](https://mirror.stream.centos.org/9-stream/BaseOS/source/tree/Packages/)
and
[AppStream](https://mirror.stream.centos.org/9-stream/AppStream/source/tree/Packages/)
source trees.

## What a listing covers

The marketplace is offered free of charge, as is and on a best-effort basis
by volunteers. Using a generator is at your own risk; review the compiled
output before you apply it ([terms](../TERMS.md#no-warranty)).

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
