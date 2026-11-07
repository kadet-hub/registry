---
title: cosign verify-attestation vs gh attestation verify
date: 2026-10-21
topics: [supply chain, sigstore, verification]
description: Verify SLSA provenance attestations on OCI artifacts with gh and cosign, using kadet-hub's signed index, real digests and the failures that matter.
---

To verify an [OCI artifact](/glossary/#oci-artifact) that carries GitHub [artifact attestations](/glossary/#attestation), run
`gh attestation verify` or `cosign verify-attestation` with the exact
workflow identity. gh reads the Sigstore bundles from GitHub's attestation
API, which has them for every kadet-hub [generator](/glossary/#generator) version. cosign reads
them from the registry, where the release workflow has pushed them since
17 October 2026. This post walks through both on a real generator, shows
the failures you want to see, and ends with a script that does it in one
call. Why a generator needs this at all is covered in
[supply-chain security for Kapitan generators](/guides/supply-chain-security-for-kapitan-generators/).

Everything below ran on 2026-10-19 with gh 2.102.0, cosign v3.1.3 (sha256
`4629c757…7f71` against the release's `cosign_checksums.txt`), jq 1.8.2 and
oras 1.3.4.

## What kadet-hub attests

The [release workflow](/guides/how-kadet-hub-works/) pushes each generator
as an OCI artifact to `ghcr.io/kadet-hub/<name>` and attests its [digest](/glossary/#digest)
up to three times: [SLSA provenance](/glossary/#provenance) (`https://slsa.dev/provenance/v1`), an SPDX 2.3
[SBOM](/glossary/#sbom) (`https://spdx.dev/Document/v2.3`) and the diff of its fixture output
against the previous version (`https://kadet-hub.org/output-diff/v1`). It
also attests the [index](/glossary/#index) that lists every version with its digest, and
publishes that index as a GitHub release `index-<serial>` with a Sigstore
bundle next to it.

Each attestation of a digest also goes to ghcr.io as an OCI referrer of
that digest, which is where cosign looks.

All of them are signed by one identity:

```
https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
```

A workflow on another branch of the same repository can still get a valid
signature, but its certificate names its own file and ref. Matching this
string exactly is what rejects it.

The worked example is `mutate` 0.1.0 from index 48, the first version
published with referrers. It is mutate's first version, so there is
nothing to diff against: the index records `"base": null` with
`"error": "no earlier listed version"`, and the release attested
provenance and SBOM only.

## Start from the signed index

The digest you pin should come from a verified index, not from a tag:

```sh
ID=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh release download index-48 --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json \
  --owner kadet-hub --cert-identity "$ID"
jq -r '.serial, .generators.mutate["0.1.0"].digest' index.json
```

```
48
sha256:428e548bb10c6dda0105220c3a9f135d3a964a419303e30849a06f6d9e194a15
```

When stdout is not a terminal, `gh attestation verify` prints nothing on
success: 0 bytes on stdout and stderr, exit code 0. In CI the exit code is
your only signal unless you ask for JSON. On a TTY it prints a summary
that starts with the policy it enforced:

```
The following policy criteria will be enforced:
- Predicate type must match:............. https://slsa.dev/provenance/v1
- Source Repository Owner URI must match: https://github.com/kadet-hub
- Subject Alternative Name must match:... https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
- OIDC Issuer must match:................ https://token.actions.githubusercontent.com
```

Also check `yanked` is null for the version, and that `serial` is not lower
than the last one you accepted. The serial is the rollback protection.

## Verify the artifact with gh

```sh
D=sha256:428e548bb10c6dda0105220c3a9f135d3a964a419303e30849a06f6d9e194a15
gh attestation verify "oci://ghcr.io/kadet-hub/mutate@$D" \
  --owner kadet-hub --cert-identity "$ID" --format json \
  | jq -r '.[].verificationResult.statement.predicateType'
```

```
https://slsa.dev/provenance/v1
```

Only provenance, the predicate type of the policy above, unless you pass
`--predicate-type` ([manual](https://cli.github.com/manual/gh_attestation_verify)).
With the SPDX URI it also exits 0. With the output-diff URI it fails with
an HTTP 404 from the attestations API, since mutate 0.1.0 has none.
`--bundle-from-oci` reads the bundles from ghcr.io instead of the API and
prints the same result. To see every attestation for a digest, download
them:

```sh
gh attestation download "oci://ghcr.io/kadet-hub/mutate@$D" --owner kadet-hub
jq -r '.dsseEnvelope.payload | @base64d | fromjson | .predicateType' "$D.jsonl"
```

```
https://spdx.dev/Document/v2.3
https://slsa.dev/provenance/v1
```

The file holds one Sigstore bundle (`application/vnd.dev.sigstore.bundle.v0.3+json`)
per line, each with a Rekor entry.

## The same with cosign

The registry lists the same two bundles as referrers of the digest:

```
$ oras discover "ghcr.io/kadet-hub/mutate@$D"
ghcr.io/kadet-hub/mutate@sha256:428e548bb10c6dda0105220c3a9f135d3a964a419303e30849a06f6d9e194a15
└── application/vnd.dev.sigstore.bundle.v0.3+json
    ├── sha256:d197b25d45961fe128b5294f3d3741f941b77395195109b20e89d948a3db1afa
    │   └── [annotations]
    │       ├── org.opencontainers.image.created: "2026-10-19T16:59:12.130Z"
    │       ├── dev.sigstore.bundle.content: dsse-envelope
    │       └── dev.sigstore.bundle.predicateType: https://slsa.dev/provenance/v1
    └── sha256:b928bfd9c69cb04e9675212a21f6ef0bcff2b4a9420a8721a19a281f23957ae6
        └── [annotations]
            ├── org.opencontainers.image.created: "2026-10-19T16:59:18.390Z"
            ├── dev.sigstore.bundle.content: dsse-envelope
            └── dev.sigstore.bundle.predicateType: https://spdx.dev/Document/v2.3
```

cosign verifies them in place:

```sh
cosign verify-attestation --type slsaprovenance1 \
  --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "ghcr.io/kadet-hub/mutate@$D" > provenance.json
```

```
Verification for ghcr.io/kadet-hub/mutate@sha256:428e548bb10c6dda0105220c3a9f135d3a964a419303e30849a06f6d9e194a15 --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - Existence of the claims in the transparency log was verified offline
  - The code-signing certificate was verified using trusted certificate authority certificates
```

That summary goes to stderr. stdout gets the verified DSSE envelope:

```sh
jq -r '.payload | @base64d | fromjson | .predicateType, .subject[0].name' provenance.json
```

```
https://slsa.dev/provenance/v1
ghcr.io/kadet-hub/mutate
```

`slsaprovenance1` is cosign's short name for the provenance URI. For the
SBOM, pass the URI itself, `--type https://spdx.dev/Document/v2.3`. The
short name `spdxjson` fails here, and the error lists what the digest
carries:

```
Error: none of the attestations matched the predicate type: spdxjson, found: https://slsa.dev/provenance/v1,https://spdx.dev/Document/v2.3
```

`cosign verify` with the same identity and issuer also exits 0. kadet-hub signs nothing
with `cosign sign`; cosign v3 accepts the two attestation bundles as
signatures and prints one entry per bundle with its predicate type as
`critical.type`. It checks no predicate type, so use `verify-attestation`
with `--type`.

Versions published before 17 October 2026 have no referrers: on
kubernetes 1.2.0, `oras discover` lists none and `cosign verify-attestation`
fails with `no matching attestations:`. For those, cosign verifies the
bundles that gh downloads, one bundle per file. The approach is the one
from the [Sigstore blog](https://blog.sigstore.dev/cosign-verify-bundles/)
(cosign v2.4.0), with two changes v3.1.3 needed here. On mutate's
downloaded bundles it gives the same answer as the registry:

```sh
sed -n 2p "$D.jsonl" > provenance.sigstore.json   # the line with slsa.dev/provenance/v1
cosign verify-blob-attestation --bundle provenance.sigstore.json \
  --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --type https://slsa.dev/provenance/v1 \
  --digest "${D#sha256:}" --digestAlg sha256
```

```
Verified OK
```

Passing the whole two-bundle `.jsonl` fails with `invalid character '{'
after top-level value`. `--type` must match the predicate URI: the default
`custom` fails with `invalid predicate type, expected custom got
https://slsa.dev/provenance/v1`. Instead of `--digest`, you can pass the
manifest itself as the blob, since its sha256 is the digest:
`oras manifest fetch "ghcr.io/kadet-hub/mutate@$D" > manifest.json`.
The index works directly with its release bundle:
`cosign verify-blob-attestation --bundle index.json.sigstore.json … --type slsaprovenance1 index.json`.
The `index.json.intoto.jsonl` asset does not, because it carries no
certificate.

cosign fetched the Sigstore public good trusted root through TUF.
`gh attestation trusted-root` prints two roots: public good, and GitHub's
own instance, which GitHub uses for private repositories
([docs](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline)).
Passing the first as `--trusted-root` to `cosign verify-attestation`
verifies. The second fails with `not enough verified log entries from
transparency log: 0 < 1`, since it has no Rekor log.

cosign also checks individual GitHub claims, for example
`--certificate-github-workflow-repository kadet-hub/registry
--certificate-github-workflow-ref refs/heads/main`. Do not pin
`--certificate-github-workflow-trigger push`: kadet-hub's release workflow
also runs on a schedule and on manual dispatch.

## Failures you want to see

| Case | gh | cosign |
|---|---|---|
| identity `@refs/heads/dev` | `verifying with issuer "sigstore.dev"` | `expected SAN value ".../release.yml@refs/heads/dev", got ".../release.yml@refs/heads/main"` |
| index with `serial` changed | `verifying with issuer "sigstore.dev"` | `provided artifact digests do not match digests in statement` |
| another generator's digest under `ghcr.io/kadet-hub/mutate` | `MANIFEST_UNKNOWN` from ghcr.io | `no matching attestations:` |
| repository `kadet-hub/generators`, gh with `--bundle-from-oci` | `expected SourceRepositoryURI to be https://github.com/kadet-hub/generators, got https://github.com/kadet-hub/registry` | `expected GithubWorkflowRepository to be "kadet-hub/generators", got "kadet-hub/registry"` |
| issuer `https://accounts.google.com` | `expected Issuer to be https://accounts.google.com, got https://token.actions.githubusercontent.com` | `expected issuer value "https://accounts.google.com", got "https://token.actions.githubusercontent.com"` |

All exit 1. gh's message for a wrong identity or a tampered file is the
same, so it tells you that verification failed, not why. Without
`--bundle-from-oci`, `--repo kadet-hub/generators` fails earlier with an
HTTP 404 from the attestations API. cosign finds no referrers for another
generator's digest; with mutate's downloaded bundle and that digest,
`verify-blob-attestation` reports `provided artifact digest does not match
any digest in statement`.

One case passes that should worry you: `--certificate-identity-regexp
'^https://github.com/kadet-hub/'` verifies and exits 0. That pattern
accepts any workflow on any branch in the organization. Use the exact
identity.

## Read the provenance

Verification proves who signed. The predicate tells you what ran.
Abridged, from `jq '.payload | @base64d | fromjson | .predicate' provenance.json`:

```json
"externalParameters": {"workflow": {"ref": "refs/heads/main",
  "repository": "https://github.com/kadet-hub/registry", "path": ".github/workflows/release.yml"}},
"internalParameters": {"github": {"event_name": "push", "runner_environment": "github-hosted"}},
"resolvedDependencies": [{"uri": "git+https://github.com/kadet-hub/registry@refs/heads/main",
  "digest": {"gitCommit": "c043c5ab78befe28cfab9a0698b5735cb39799fe"}}],
"runDetails": {"builder": {"id": "https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main"},
  "metadata": {"invocationId": "https://github.com/kadet-hub/registry/actions/runs/39288368802/attempts/1"}}
```

| Field | Check |
|---|---|
| `externalParameters.workflow` | path, ref and repository match the identity you trust |
| `resolvedDependencies[].digest.gitCommit` | the registry commit; read the workflow at that commit if you audit it |
| `internalParameters.github.event_name` | what started the run (`push` here); the release workflow also runs on `schedule` and `workflow_dispatch`, so record it rather than require one value |
| `runner_environment` | `github-hosted`; a self-hosted runner is a different trust boundary |
| `invocationId` | the run, with its logs; the index attestation of serial 48 names the same run |

The commit here is the registry's, the merge that listed mutate, not the
generator's. The generator source (`925525b…` in `kadet-hub/generators`)
appears in the index and in the SBOM's `downloadLocation`,
`git+https://github.com/kadet-hub/generators.git@925525b2fabb1c2fb33c00f1b00b0d2495edce06#mutate`.
Those are statements by the same signed workflow, not something Sigstore
checks.

## One script

[`verify-oci/verify`](https://github.com/kadet-hub/examples/tree/main/verify-oci)
needs gh, jq and sha256sum. It downloads the latest index release,
verifies it, enforces a minimum serial, rejects [yanked](/glossary/#yanked) versions, verifies
provenance, SBOM and [output diff](/glossary/#output-diff) for the digest, checks the diff hash
against the index, and confirms that a tampered index, another branch,
another repository and another workflow are rejected. Any failure exits
non-zero.

```
$ ./verify mutate 0.1.0 48
index.json: https://slsa.dev/provenance/v1
serial: 48
mutate 0.1.0: sha256:428e548bb10c6dda0105220c3a9f135d3a964a419303e30849a06f6d9e194a15
https://slsa.dev/provenance/v1: https://github.com/kadet-hub/registry/actions/runs/39288368802/attempts/1
https://spdx.dev/Document/v2.3: https://github.com/kadet-hub/registry/actions/runs/39288368802/attempts/1
rejected as expected: tampered index
rejected as expected: branch other than main
rejected as expected: wrong source repository
rejected as expected: workflow other than release.yml
OK: mutate 0.1.0 verified against index 48
```

The output diff is checked only when the index records one, which is why
mutate 0.1.0 stops at two predicates. Versions published before the SBOM
existed, such as keda 1.0.0, are checked for provenance only.
