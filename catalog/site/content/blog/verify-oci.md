---
title: Verify a signed OCI artifact with cosign and gh
date: 2026-11-10
topics: [supply chain, sigstore, verification]
description: Verify SLSA provenance attestations on OCI artifacts with gh and cosign, using kadet-hub's signed index, real digests and the failures that matter.
---

To verify an OCI artifact that carries GitHub artifact attestations, run
`gh attestation verify` with the exact workflow identity. cosign v3 checks
the same Sigstore bundles with `cosign verify-blob-attestation`, but only
after you download them: `cosign verify-attestation` on the image finds
nothing, because the attestations live in GitHub's attestation API and not
in the registry. This post walks through both on a real kadet-hub
generator, shows the failures you want to see, and ends with a script that
does it in one call. Why a generator needs this at all is covered in
[supply-chain security for Kapitan generators](/guides/supply-chain-security-for-kapitan-generators/).

Everything below ran on 2026-10-17 with gh 2.102.0, cosign v3.1.3 (sha256
`4629c757…7f71` against the release's `cosign_checksums.txt`), jq 1.8.2 and
oras 1.3.4.

## What kadet-hub attests

The [release workflow](/guides/how-kadet-hub-works/) pushes each generator
as an OCI artifact to `ghcr.io/kadet-hub/<name>` and attests its digest
three times: SLSA provenance (`https://slsa.dev/provenance/v1`), an SPDX 2.3
SBOM (`https://spdx.dev/Document/v2.3`) and the diff of its fixture output
against the previous version (`https://kadet-hub.org/output-diff/v1`). It
also attests the index that lists every version with its digest, and
publishes that index as a GitHub release `index-<serial>` with a Sigstore
bundle next to it.

All of them are signed by one identity:

```
https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
```

A workflow on another branch of the same repository can still get a valid
signature, but its certificate names its own file and ref. Matching this
string exactly is what rejects it. The worked example is `kubernetes` 1.2.0
from index 47.

## Start from the signed index

The digest you pin should come from a verified index, not from a tag:

```sh
ID=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh release download index-47 --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json \
  --owner kadet-hub --cert-identity "$ID"
jq -r '.serial, .generators.kubernetes["1.2.0"].digest' index.json
```

```
47
sha256:52017626e77dd5bf7293ce465ff0c3dc7a61dae1ae8353a56a53ffebe1bfb67c
```

When stdout is not a terminal, `gh attestation verify` prints nothing on
success: 0 bytes on stdout and stderr, exit code 0. In CI the exit code is
your only signal unless you ask for JSON. The human-readable summary with
the enforced policy appears only on a TTY.

Also check `yanked` is null for the version, and that `serial` is not lower
than the last one you accepted. The serial is the rollback protection.

## Verify the artifact with gh

```sh
D=sha256:52017626e77dd5bf7293ce465ff0c3dc7a61dae1ae8353a56a53ffebe1bfb67c
gh attestation verify "oci://ghcr.io/kadet-hub/kubernetes@$D" \
  --owner kadet-hub --cert-identity "$ID" --format json \
  | jq -r '.[].verificationResult.statement.predicateType'
```

```
https://slsa.dev/provenance/v1
```

Only provenance, because `gh` enforces that predicate type unless you pass
`--predicate-type` ([manual](https://cli.github.com/manual/gh_attestation_verify)).
Running it with the SPDX and output-diff URIs also exits 0. To see every
attestation for a digest, download them:

```sh
gh attestation download "oci://ghcr.io/kadet-hub/kubernetes@$D" --owner kadet-hub
jq -r '.dsseEnvelope.payload | @base64d | fromjson | .predicateType' "$D.jsonl"
```

```
https://kadet-hub.org/output-diff/v1
https://spdx.dev/Document/v2.3
https://slsa.dev/provenance/v1
```

The file holds one Sigstore bundle (`application/vnd.dev.sigstore.bundle.v0.3+json`)
per line, each with a Rekor entry.

## The same with cosign

The first attempt fails:

```
$ cosign verify-attestation --type slsaprovenance1 \
    --certificate-identity "$ID" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    "ghcr.io/kadet-hub/kubernetes@$D"
Error: no matching attestations:
```

Adding `--new-bundle-format` changes nothing except a deprecation warning;
in v3 it is the default. `oras discover` lists no referrers for the digest,
and `gh attestation verify --bundle-from-oci` fails with "no attestations
found in the OCI registry". `actions/attest` only pushes to the registry
with `push-to-registry`, which [defaults to false](https://github.com/actions/attest),
and kadet-hub does not set it.

cosign verifies the downloaded bundles, one bundle per file. The approach
is the one from the [Sigstore blog](https://blog.sigstore.dev/cosign-verify-bundles/)
(cosign v2.4.0), with two changes v3.1.3 needed here:

```sh
sed -n 3p "$D.jsonl" > provenance.sigstore.json   # the line with slsa.dev/provenance/v1
cosign verify-blob-attestation --bundle provenance.sigstore.json \
  --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --type https://slsa.dev/provenance/v1 \
  --digest "${D#sha256:}" --digestAlg sha256
```

```
Verified OK
```

Passing the whole three-bundle `.jsonl` fails with `invalid character '{'
after top-level value`. `--type` must match the predicate URI: the default
`custom` and the `spdxjson` shorthand both fail with `invalid predicate
type`. Instead of `--digest`, you can pass the manifest itself as the blob,
since its sha256 is the digest: `oras manifest fetch … > manifest.json`.
The index works directly with its release bundle:
`cosign verify-blob-attestation --bundle index.json.sigstore.json … --type slsaprovenance1 index.json`.
The `index.json.intoto.jsonl` asset does not, because it carries no
certificate.

cosign fetched the Sigstore public good trusted root through TUF.
`gh attestation trusted-root` prints two roots: public good, and GitHub's
own instance, which GitHub uses for private repositories
([docs](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline)).
Passing the first as `--trusted-root` verifies. The second fails with
`not enough verified log entries from transparency log: 0 < 1`, since it
has no Rekor log.

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
| another generator's digest | `MANIFEST_UNKNOWN` from ghcr.io | `provided artifact digest does not match any digest in statement` |
| `--repo kadet-hub/generators`, bundle | `expected SourceRepositoryURI to be https://github.com/kadet-hub/generators, got https://github.com/kadet-hub/registry` | `expected GithubWorkflowRepository to be "kadet-hub/generators", got "kadet-hub/registry"` |
| issuer `accounts.google.com` | | `expected issuer value "https://accounts.google.com", got "https://token.actions.githubusercontent.com"` |

All exit 1. gh's message for a wrong identity or a tampered file is the
same, so it tells you that verification failed, not why. Online,
`--repo kadet-hub/generators` fails earlier with an HTTP 404 from the
attestations API.

One case passes that should worry you: `--certificate-identity-regexp
'^https://github.com/kadet-hub/'` returns `Verified OK`. That pattern
accepts any workflow on any branch in the organization. Use the exact
identity.

## Read the provenance

Verification proves who signed. The predicate tells you what ran.
Abridged, for `kubernetes` 1.2.0:

```json
"externalParameters": {"workflow": {"path": ".github/workflows/release.yml",
  "ref": "refs/heads/main", "repository": "https://github.com/kadet-hub/registry"}},
"internalParameters": {"github": {"event_name": "push", "runner_environment": "github-hosted"}},
"resolvedDependencies": [{"uri": "git+https://github.com/kadet-hub/registry@refs/heads/main",
  "digest": {"gitCommit": "6dc7f2ff4751f116f48fbffe1ef48f6611423c21"}}],
"runDetails": {"builder": {"id": "https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main"},
  "metadata": {"invocationId": "https://github.com/kadet-hub/registry/actions/runs/38951646777/attempts/1"}}
```

| Field | Check |
|---|---|
| `externalParameters.workflow` | path, ref and repository match the identity you trust |
| `resolvedDependencies[].digest.gitCommit` | the registry commit; read the workflow at that commit if you audit it |
| `internalParameters.github.event_name` | what started the run (`push` here); the release workflow also runs on `schedule` and `workflow_dispatch`, so record it rather than require one value |
| `runner_environment` | `github-hosted`; a self-hosted runner is a different trust boundary |
| `invocationId` | the run, with its logs; the index attestation of serial 47 names the same run |

The commit here is the registry's, not the generator's. The generator
source (`7cd44eb…` in `kadet-hub/generators`) appears in the index and in
the SBOM's `downloadLocation`. Those are statements by the same signed
workflow, not something Sigstore checks.

The output-diff predicate is the one to read on a version bump. For 1.2.0
it records base 1.1.1, 11 files and 11 hunks, and the sha256 of the diff
text matches the index entry. The first hunk adds a ClusterRole.

## One script

[`verify-oci/verify`](https://github.com/kadet-hub/examples/tree/main/verify-oci)
needs gh, jq and sha256sum. It downloads the latest index release,
verifies it, enforces a minimum serial, rejects yanked versions, verifies
provenance, SBOM and output diff for the digest, checks the diff hash
against the index, and confirms that a tampered index, another branch,
another repository and another workflow are rejected. Any failure exits
non-zero.

```
$ ./verify kubernetes 1.2.0 47
index.json: https://slsa.dev/provenance/v1
serial: 47
kubernetes 1.2.0: sha256:52017626e77dd5bf7293ce465ff0c3dc7a61dae1ae8353a56a53ffebe1bfb67c
https://slsa.dev/provenance/v1: https://github.com/kadet-hub/registry/actions/runs/38951646777/attempts/1
https://spdx.dev/Document/v2.3: https://github.com/kadet-hub/registry/actions/runs/38951646777/attempts/1
https://kadet-hub.org/output-diff/v1: https://github.com/kadet-hub/registry/actions/runs/38951646777/attempts/1
output diff matches index: {"base":"1.1.1","files":11,"hunks":11}
rejected as expected: tampered index
rejected as expected: branch other than main
rejected as expected: wrong source repository
rejected as expected: workflow other than release.yml
OK: kubernetes 1.2.0 verified against index 47
```

Versions published before the SBOM existed, such as keda 1.0.0, are
checked for provenance only.
