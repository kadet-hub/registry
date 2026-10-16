---
title: How kadet-hub works
layout: prose
description: How a Kapitan generator is gate-checked, published as an attested OCI artifact, verified by consumers, kept current and withdrawn when needed.
---

A generator lives in its author's repository. kadet-hub lists it through a
pull request that adds one entry file to kadet-hub/registry, checks the
pinned commit in a gate and, after a maintainer's review, publishes the
checked tree as an attested OCI artifact on ghcr.io. Consumers pin that
artifact by digest, verify it and compile it in a sandbox. Renovate bump
pull requests and a daily rescan keep the listings current, and a yank
withdraws a version.

{{< diagram name="overview" title="How kadet-hub works" desc="Overview: author repository, pull request, gate, review, release, ghcr.io and kadet-hub.org, consumer CI, with the Renovate bump and the rescan feeding back into the pull request." >}}

## Listing a new generator

{{< diagram name="listing" title="Listing a new generator" desc="Flowchart: the author's steps, the entry pull request, five gate stages that can each fail the check, the output diff, the report comment, review and merge." >}}

1. The author creates a repository from
   [kadet-hub/generator-template](https://github.com/kadet-hub/generator-template).
   For an operator's custom resources, `./scaffold <name> <crd-url>...`
   writes a generator with the upstream schemas and CRDs, a README, a
   CHANGELOG and a `minimal` fixture target. `./check <dir>` runs the
   gate's static scans and its sandbox compile from the registry's `main`
   with docker. It has no gVisor, so only the gate judges the syscall
   trace.
2. The author tags a semver at a commit, optionally with a prefix such as
   `argocd-v1.4.0`, and opens a pull request that adds only
   `generators/<name>.yaml` with repository, path, tag, commit SHA and
   owners. The author must be one of the owners the manifest names.
3. The gate runs as `pull_request_target`, so its definition comes from
   `main`, with a read-only token and no secrets. It never checks out the
   pull request: it reads the entry file through the API and fetches the
   pinned commit as data.
4. Each stage in the table below can fail the required `gate` check.
   Generator code runs only in the sandbox compile: gVisor without
   network, with decoy credentials and a syscall trace. An undeclared
   program, a network attempt or a read of a decoy fails the gate.
5. On every run a separate job posts or updates one comment with the
   report, including the diff of the fixture output against the version
   approved before. That diff is shown, not judged.
6. A maintainer reviews the code and the output, not only the verdict.
   The pull request merges with one approval from someone other than the
   last pusher, a passing gate and a branch up to date with `main`.

[Adding a generator](https://github.com/kadet-hub/registry/blob/main/docs/authors.md)
has the manifest, the fixture project and the entry format.

### What the gate checks

| Stage and requirements | Fails the gate when |
|---|---|
| Registration ([GI-1, GI-2](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#gate-integrity), [REG-1 to REG-6, REG-8](https://github.com/kadet-hub/registry/blob/main/docs/specs/registration.md#registration)) | the pull request changes more than one entry file, the entry or its name breaks the rules, the author is not an owner, the tag does not resolve to the pinned SHA, or a bump does not raise the version or moves the source |
| Source and charts ([QA-1, QA-2, QA-5](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate), [CMP-3](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#compile-gate), [SEC-7, SEC-8](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#dependencies-binaries-and-charts)) | the manifest breaks its schema or licence rules, its Kapitan range excludes the pinned version, it declares a program that is not allowed, or a chart differs from its sha256 |
| Static scans ([SEC-1 to SEC-6](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#static-checks), [SEC-14](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection), [QA-3](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate)) | gitleaks, GuardDog, the import allowlist and semgrep rules, the file tree rules, ClamAV or ruff report a finding that no exception bound to the file's content covers |
| Sandbox compile ([SEC-9 to SEC-11](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection), [CMP-1, CMP-2, CMP-4, CMP-5](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#compile-gate), [QA-4](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate)) | a target fails or writes nothing on an inventory backend, the output changes with `CI` set or with `--cache`, the trace shows a forbidden call, or a decoy value appears in the output; the krab result is recorded, not judged |
| Output checks ([SEC-12](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection), [QA-6 to QA-8, QA-10 to QA-12](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#quality-gate)) | the output uses a capability the manifest does not declare, carries a tag without evidence, fails the JSON Schemas the generator ships, or a throwaway kube-apiserver rejects it in a dry run |
| Output diff ([SEC-13](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md#sandbox-and-runtime-detection)) | never; the diff goes into the comment for review |

## Publishing a release

{{< diagram name="release" title="Publishing a release" desc="Flowchart of the release jobs build, sign, index and catalog, with the two points where a failure stops publishing and the one where it stops the site deploy." >}}

1. The release workflow runs on a push to `main` that changes what it
   reads, once a day and on manual dispatch. It reconciles every entry: a
   version without an attested tag on ghcr.io is built, a published one is
   skipped.
2. The build job holds read permissions only and cannot sign. It fetches
   each source by SHA without checkout and rebuilds the tree as a
   reproducible tar. For every unpublished version it reruns the static
   scans and the sandbox compile, and a finding fails the release before
   anything is pushed. It records the scan, the output diff against the
   newest listed version that is not yanked, the kinds the fixture renders
   and the inventory backends it compiled on in the artifact's metadata.
3. The sign job runs in the `release` environment, which only `main` can
   use. It fetches the commit again and fails when its git tree differs
   from the tar. It pushes the artifact to `ghcr.io/kadet-hub/<name>` by
   digest and attests SLSA provenance, an SPDX SBOM and the output diff
   with GitHub artifact attestations, signed keyless through Sigstore and
   logged in its public transparency log. Only then does it set the
   version tag, which is never moved.
4. The index job publishes `ghcr.io/kadet-hub/index` with the next serial
   when anything changed, and attests it. A GitHub release
   `index-<serial>` carries the same `index.json` with its Sigstore and
   in-toto bundles; a published release cannot be changed.
5. The catalog is built from that index. Every page is checked for title,
   description, headings and canonical URL before the deploy, and a
   finding stops the deploy, so the previous site stays live.

The same run publishes the sandbox image the consumer workflow uses,
tagged with the git tree of the registry's `sandbox/` directory.

## Using a generator

{{< diagram name="consuming" title="Using a generator" desc="Flowchart: a Renovate pull request updates the pinned inventory entry, consumer CI runs the five steps of consumer.yml, four of which can fail it, then the output is reviewed." >}}

1. The inventory pins the generator as an OCI dependency,
   `ghcr.io/kadet-hub/<name>:<version>@sha256:<digest>`. The digest
   selects what is fetched. The tag is for reviewers and Renovate and must
   name the version the index lists for that digest. The Renovate preset
   `kadet-hub/renovate-config` opens one pull request per update that
   changes tag and digest together.
2. The consumer's CI calls the reusable workflow `consumer.yml`, pinned
   by commit, with a policy file `.kapitan-sandbox.yaml`: the lowest index
   serial it accepts, the allowed hosts per dependency type, the programs
   its own inputs run and the output capabilities it accepts per path.
   The workflow uses the sandbox image built from its own commit, verified
   like an artifact.
3. It runs `kapitan inventory` in the sandbox, since the inventory backend
   can import code from the project.
4. It checks every dependency against the policy and every kadet-hub
   artifact against the index. The index must carry the release
   workflow's attestation and at least the policy's serial, and it must
   list the digest under that name, not yanked, with the matching tag.
5. It verifies each artifact's attestation, fetches it by digest outside
   the sandbox, and compiles in the same sandbox the gate uses: no
   network, decoy credentials, a syscall trace, and the output rules with
   the capabilities the policy accepts.
6. It uploads the compiled output as a workflow artifact. Review it
   before you apply it: a listing does not make a generator's output
   right for your cluster.

Kapitan's own `--fetch` checks neither digests nor attestations and runs
the generator with your environment. GitLab CI has a template with the
same steps; GitLab's hosted runners cannot run gVisor, so the syscall trace
is missing there.
[Using marketplace generators](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
has the workflow call, the policy file and how to verify by hand.

## Keeping generators current

{{< diagram name="upstream" title="Keeping generators current" desc="Decision flowchart: the weekly upstream check of kadet-hub/generators ends in an update pull request or an issue; a new tag from any author becomes a Renovate bump." >}}

1. A new version starts as a newer tag in the author's repository, with
   the same prefix as the listed one. Renovate in the registry opens a
   pull request that updates tag and SHA on Monday mornings (Europe/Berlin),
   and the author can open the same pull request at any time. Nothing
   merges on its own.
2. The bump runs the full gate. The version must increase, repository and
   path stay fixed, and the comment adds the code diff since the approved
   commit and the schema versions before and after. A maintainer approves
   it as for a new entry, and the release publishes it.
3. For the generators in kadet-hub/generators, a workflow checks every
   Monday at 03:00 UTC whether the software they render has a newer stable
   release. It regenerates schemas and CRDs only where regenerating at the
   pinned release reproduces the committed files byte for byte, and opens
   one pull request per generator when `./check` passes. Everything else
   becomes an issue for a person.
4. That pull request changes schemas, CRDs and the README's "Built for",
   never the version. A reviewer checks the defaults, sets the version and
   CHANGELOG, merges and tags; from there step 1 applies.
5. After the release, consumers who use the Renovate preset get their own
   pull request with the new tag and digest.

## Withdrawing a version

{{< diagram name="withdraw" title="Withdrawing a version" desc="Flowchart: a report or a rescan issue, the maintainer's confirmation, advisory and yank pull request or the owner's own yank, the release, deletion and advisory." >}}

1. A version is withdrawn by listing it under `yanked` in its entry with a
   reason, which the owners can do in their own pull request. The artifact
   stays on ghcr.io, and the next release marks the version yanked in the
   index.
2. From then on the catalog shows the reason instead of the inventory
   entry, and the consumer workflow rejects the digest. Renovate can still
   propose a yanked version, because it reads the tags and not the index;
   the workflow fails that pull request.
3. The daily rescan runs the static scans again on the latest version of
   every listed generator and checks that every tag still points to its
   pinned commit. A finding or a moved tag opens an issue; nothing is
   yanked automatically.
4. Malicious behaviour is reported privately as
   [SECURITY.md](https://github.com/kadet-hub/registry/blob/main/SECURITY.md)
   describes. Once a maintainer confirms a version malicious, the
   [incident runbook](https://github.com/kadet-hub/registry/blob/main/docs/incident.md)
   applies, with a target of 24 hours: a draft security advisory, a
   maintainer pull request that sets `yanked` and the advisory, the
   release, the deletion of the artifact and the publication of the
   advisory.
5. After the deletion the index keeps the version with its digest, reason
   and advisory, so a consumer whose pinned digest fails still learns why.

## What the diagrams leave out

The diagrams show the checks, not their limits. The gate sees only what
the fixtures trigger, and code that acts only on values from your own
inventory stays inert there; the consumer sandbox bounds such code when
you compile. [What a listing covers](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#what-a-listing-covers)
lists the limits, and the
[threat model](https://github.com/kadet-hub/registry/blob/main/docs/specs/marketplace.md#threat-model)
and the [residual risks](https://github.com/kadet-hub/registry/blob/main/docs/specs/marketplace.md#residual-risk)
name the attackers and what stays accepted.
