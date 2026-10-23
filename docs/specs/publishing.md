# Kapitan generator marketplace: Publishing

Status: Approved
Code: `release/`, `.github/workflows/release.yml`, `docs/incident.md`
Verified against: main @ 970a5d4

Related: [marketplace.md](marketplace.md) holds the problem, threat model, decisions,
acceptance criteria, residual risks, open questions and the implementation inventory.

## Publishing

On a push to `main`, and on `workflow_dispatch` from `main`, the release
workflow reconciles every entry on `main`: the entry's current version gets
an artifact, an attestation and a `<version>` tag unless it is yanked or
already has them. The workflow takes the registry namespace and the
certificate identity from its own repository, so the same file runs in the
rehearsal fork (AC-6); the documented verification names `kadet-hub`.

The build job has `contents: read` and `packages: read` only. It fetches
each source without checkout or submodules (`gate/fetch_tree.py`), validates entry and manifest
(GI-9), repeats REG-2 and REG-3 across all entries on `main`, and writes a
normalized tar of the tree `source.sha:source.path` with its metadata: the
manifest fields the index lists, the source, and the tree ID computed from the
files. It runs the checks in the sandbox image without network, and the
compile gate under gVisor for versions without a published tag (CMP-4).

The sign job runs once per entry in the `release` environment. It fetches
`source.sha` itself, blobless, compares the git tree of `source.path` with
the tree ID of the tar's contents and with the metadata, writes the OCI
manifest itself, pushes config and layer to `ghcr.io/kadet-hub/<name>` by
digest, attests the digest, and then sets the `<version>` tag. The krab
result is the build job's (CMP-4).

The artifact is an OCI image manifest with artifact type
`application/vnd.kadet-hub.generator.v1`, the metadata as config blob
(`application/vnd.kadet-hub.generator.config.v1+json`) and one layer
`application/vnd.oci.image.layer.v1.tar` titled `<name>.tar`. The tar holds
the tree at its root: sorted entries, mode 0644, mtime 0, owner 0. Kapitan
0.36.3 pulls it with oras-py and extracts the tar into `output_path`.

```yaml
# consumer inventory
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/<name>:<version>@sha256:<digest>
        output_path: lib/<name>
```

GitHub documents new packages as private. The first release in `kadet-hub`
created `index` as private; in the rehearsal fork under a user account,
packages pushed by the workflow were public. A package that is not public
fails consumer pulls; the index job prints a warning for every such package,
the index included, and a maintainer changes the visibility in the web UI,
since the documented package API has no visibility call.

- PUB-1: The build job MUST build the artifact from the git tree
  `source.sha:source.path` alone, reproducibly (normalized tar, no timestamp
  in the manifest), MUST NOT use files produced by the gate, and MUST NOT
  hold `id-token` or any write permission. The sign job MUST fail when the
  tree ID of the tar differs from the tree of `source.sha:source.path` read by
  its own fetch.

  The build job holds `packages: read` to tell which versions are
  published (CMP-4) and to read the latest index for the output diff
  (PUB-9). Until this change the requirement forbade any `packages`
  permission while the workflow granted read. The output diff in
  `meta.json` comes from the build job's own compiles, not from the gate's
  `output.diff`.

  - Test: `release/test_release.py` (partial: reproducibility and tree ID;
    the sign job's comparison by AC-6)
  - Since: #13, #226

- PUB-2: The sign job MUST attest a digest before tagging it, MUST NOT move an
  existing `<version>` tag, MUST fail when an existing tag points to a digest
  without a marketplace attestation, MUST complete every version left
  untagged by an earlier run, MUST NOT tag a version that is not newer than
  the newest tagged version of the package, and MUST NOT build, attest or
  tag a yanked version.

  The last ordering rule replaces REG-6 at release time: the gate compares
  against the previous entry, the sign job against what consumers can
  already pull.

  - Test: manual: AC-6
  - Since: #13

- PUB-3: Every published artifact MUST carry a GitHub artifact attestation
  (SLSA provenance) from the release workflow. The documented verification
  MUST match the certificate identity
  `https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main`
  exactly.
  - Test: manual: AC-6
  - Since: #13

- PUB-3a: Every attestation whose subject is an OCI digest (the
  artifact's provenance, SBOM and output diff, the sandbox image and the
  index manifest) MUST also be pushed to ghcr.io as an OCI referrer of
  that digest.

  Without it the attestations live only in GitHub's attestation store.
  `gh attestation verify` finds them there, but `cosign
  verify-attestation` looks for referrers in the registry and fails with
  `no matching attestations`; `oras discover` listed none (checked
  2026-10-17 on kubernetes 1.2.0). `actions/attest` pushes the bundle with
  `push-to-registry: true`. `create-storage-record` stays off, since it
  needs `artifact-metadata: write` and records nothing a consumer checks.
  Versions published before this change keep their attestations in the
  attestation store only.

  The referrers are untagged manifests in the same package. The index
  reads versions from semver tags only (PUB-4), so they are not taken for
  versions.

  Run on 2026-10-19 against mutate 0.1.0 from index 48
  (`sha256:428e548bb10c6dda0105220c3a9f135d3a964a419303e30849a06f6d9e194a15`),
  the first version published with referrers, using the commands of the
  blog post from #301: `cosign verify-attestation` with the identity
  `https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main`
  and the issuer `https://token.actions.githubusercontent.com` verified
  `slsaprovenance1` and `https://spdx.dev/Document/v2.3`, and exited 1
  for another branch, source repository, issuer or digest. mutate 0.1.0
  has no output diff; the sandbox image and the index manifest were not
  part of the run.

  - Test: `release/test_release.py` (`test_oci_attestations_are_pushed_to_the_registry`); manual: `cosign verify-attestation` on mutate 0.1.0 (2026-10-19)
  - Since: #275

- PUB-4: The release workflow MUST publish an attested index as
  `ghcr.io/kadet-hub/index` with a `serial` that increases with every
  publication, listing per version: name, version, digest, tree ID,
  description, tags, license, Kapitan range, krab result, output
  capabilities, unparsed outputs, binaries, chart digests, owners, source
  repository and SHA, the output diff summary (PUB-9), the kinds of its
  fixture output (PUB-10), the inventory backends its fixture compiled on
  (PUB-11), the time it was first published, `yanked` with its reason, and
  advisories (INC-1).

  The index job reads the versions from the registry tags, each version's
  metadata from its config blob, and accepts only digests with a marketplace
  attestation. A failed attestation lookup is tried three times, 5 and 15
  seconds apart, before the digest counts as unattested: on 2026-10-22 a
  single failed lookup for an attested multus version stopped the index job,
  and with it the catalog deploy, until the next release. Versions of a removed entry stay listed as yanked with reason
  `entry removed`. The index is tagged `<serial>` and `latest`; the serial
  is the verified `latest` serial plus one, and an index whose content
  equals `latest` apart from the serial is not published. Advisories stay
  empty until INC-1 is implemented.

  `published` is the index job's time when a version first appears and is
  carried over from the previous index afterwards; the artifact itself holds
  no timestamp, so its digest stays reproducible. Versions built before
  description and tags entered the metadata list neither.

  - Test: `release/test_release.py` (partial: content and serial; publishing
    by AC-6)
  - Since: #13, #226, #235, #242

- PUB-5: Setting a version in `yanked` MUST mark it in the index and keep the
  artifact; deleting it is INC-1's call.
  - Test: `release/test_release.py::Index.test_yanked_and_removed`
  - Since: #13

- PUB-6: The release workflow MUST publish the sandbox image as
  `ghcr.io/kadet-hub/sandbox:<tree>`, where `<tree>` is the git tree ID of
  `sandbox/` on `main`, attest its digest before tagging, and never move the
  tag.

  The consumer workflow derives `<tree>` from its own commit (CON-1), so the
  scripts and the image it runs always come from the same tree. A tree that
  is already tagged with an attested digest is not rebuilt.

  - Test: manual: AC-6 consumer run (2026-10-09)
  - Since: #15

- PUB-7: For every version it publishes, the build job MUST rerun the
  static checks with the entry's exceptions and the compile gate, fail on
  any finding, and record the run in the artifact's `meta.json` as `scan`.

  The record holds the time, the registry commit and the release run,
  every check with the tool and version that ran it, and the number of
  exceptions applied. It is part of the attested artifact, so the catalog
  shows what the publishing run itself checked, not what a pull request
  run reported. Versions published before this requirement have no
  record; the catalog says so instead of implying a result.

  Run on 2026-10-11 in the rehearsal fork with external-secrets and keda
  1.0.0 unpublished there: the build job reran the static checks and the
  compile gate for both, and keda's config blob carried the record with
  nine checks and their tool versions, the run and the registry commit.

  - Test: manual: fork rehearsal (2026-10-11)
  - Since: #47

- PUB-8: The sign job MUST attest an SPDX 2.3 SBOM for every artifact it
  pushes, for the same digest.

  The SBOM is written from the pushed tar (`release/sbom.py`): one package
  with the manifest's license as declared license, the source repository
  at `source.sha` as download location and a `pkg:oci` purl with the
  digest, and every file with its SHA-256 and SHA-1. Generators have no
  dependencies (DEC-10), so the SBOM is the reviewed file list.
  `actions/attest` with `sbom-path` stores it with the predicate type
  `https://spdx.dev/Document/v2.3`.

  In the same rehearsal `gh attestation verify --predicate-type
  https://spdx.dev/Document/v2.3` verified keda's SBOM (8 files, purl with
  the pushed digest); `pyspdxtools` validates the document written for
  the published keda 1.0.0 tar.

  - Test: `release/test_release.py::Sbom`; manual: fork rehearsal (2026-10-11)
  - Since: #47

- PUB-9: For every version it publishes, the build job MUST diff the
  version's fixture output against that of the newest listed version of
  the same generator that is not yanked, and MUST record the summary in
  `meta.json` as `output_diff`. The sign job MUST attest the diff for the
  same digest with the predicate type `https://kadet-hub.org/output-diff/v1`.
  A missing base and a failed fetch or compile of the base MUST be
  recorded and MUST NOT fail the release.

  The base is the newest version the latest index lists (PUB-4) that
  neither the index nor the entry on `main` marks yanked. The build job
  fetches the base's `source.sha` from its `source.repo` and `source.path`
  with its charts, and compiles its fixture once in the same sandbox on the
  first backend with `COMPILE_ONLY`, as `gate/run` does for SEC-13. The new
  version's side is the output of the compile gate it has just passed.
  `gate/output_diff.py` compares the two with files that have a SEC-12
  match first, and cuts the diff after the last whole line within 1 MiB,
  closing it with a line that names the cut. `release/output-diff` runs
  these steps.

  The record is `{base, files, hunks, sha256}`: files and hunks count the
  whole diff, `sha256` is the hash of the attested text. It enters the
  index with the rest of `meta.json`. When no base is listed, the index
  cannot be read, the base cannot be fetched or its compile exits non-zero,
  the record is `{base, error}`, with `base` null when no base was chosen,
  and no diff is attested. Versions published before this requirement have
  no record, and none is added later.

  The sign job writes the predicate `{base, files, hunks, sha256, diff}` and
  attests it with `actions/attest` and `predicate-path`, next to the SBOM
  of PUB-8. JSON escaping at most sextuples the 1 MiB text, which stays
  below the 16 MB predicate limit of `actions/attest`.

  The build job reads the latest index without verifying its attestation,
  as it reads the tags for CMP-4. Whoever can push a forged index can make
  the diff compare with a wrong base; that base's code still runs only in
  the sandbox.

  - Test: `release/test_release.py::OutputDiff`, `gate/test_output_diff.py`;
    manual: fork rehearsal (pending)
  - Since: #226

- PUB-10: For every version it publishes, the build job MUST record in
  `meta.json` as `kinds` the group, version and kind of every document
  with `apiVersion` and `kind` in the first backend's fixture output, once
  each, sorted.

  The catalog lists generators by the kinds they render (CAT-29). Until
  this change no field named them: `compatibility` (CAT-15) names the
  software of the schemas used, not the kinds. The record is
  `[{group, version, kind}]` with `group` empty for the core group and
  for Talos documents, whose `apiVersion: v1alpha1` has no group; kinds
  keep their case, such as `HTTPRoute`.

  The compile gate writes the list in its QA-6 step, where
  `sandbox/tag_check.py` already parses that output in the sandbox image
  without network; `--kinds` writes it, and `gate-compile` copies it to
  `$KINDS_RESULT` as it copies the QA-7 result to `$SCHEMA_RESULT`.
  `release/build-all` sets both and merges the list into `meta.json` with
  the krab result and the scan record. Only the build job sets
  `$KINDS_RESULT`; the gate prints the same findings as before.

  The kinds are those of the fixture, so a kind the generator can render
  but its fixture does not is missing. Versions published before this
  requirement have no record, and none is added later: published versions
  are not compiled again (CMP-4).

  - Test: `sandbox/test_tag_check.py` (`test_kinds_of_the_output`);
    `release/build-all` has no unit test, manual: next release run
  - Since: #235

- PUB-11: For every version it publishes, the build job MUST record in
  `meta.json` as `backends` the inventory backends the compile gate
  compiled the fixture on, in the order it compiled them.

  The compatibility page (CAT-30) states which backends a version was
  checked on. Until this change only the manifest in the tar named them, as
  `inventory_backends` with `reclass` as the default, and nothing recorded
  what the release compiled. The compile gate compiles on every backend
  (CMP-1) and again with `--cache` on every backend (CMP-5), and any
  finding fails the build before `meta.json` is written, so each recorded
  backend passed both. The Kapitan version is in the scan record (PUB-7);
  the krab version is not recorded.

  `sandbox/gate-compile` writes the backends it compiled on, one per line,
  to `$BACKENDS_RESULT`, as it writes the krab result to `$KRAB_RESULT`.
  `release/build-all` sets it and merges the list into `meta.json` with the
  other results.

  Deriving the backends of published versions was considered. The scan
  record's `gate` commit tells whether that gate ran CMP-5 (#159): on
  2026-10-15 it did for 27 of the 35 listed latest versions. The manifest in
  each tar names the backends. The catalog job would need the registry's
  history and every version's tar, and its page would depend on how the
  gate behaved at each commit. Versions published before this requirement
  therefore have no record, none is added later (CMP-4), and the catalog
  says "not recorded".

  - Test: `release/test_release.py` (`BuildAll`, with a fake
    `gate-compile`); manual: `gate-compile` with `BACKENDS_RESULT` set
  - Since: #242

- PUB-12: Every release run that publishes a new index serial MUST create
  a GitHub release tagged `index-<serial>` at the run's commit, with the
  assets `index.json`, its Sigstore bundle `index.json.sigstore.json` and
  its in-toto bundle `index.json.intoto.jsonl`, and with notes that name
  the serial and the versions added and yanked since the previous serial.

  OpenSSF Scorecard (GI-12) scores Signed-Releases from release assets
  alone, so the attested index on ghcr.io left the check at "no releases
  found". At ossf/scorecard 5a3ebf2 (`probes/releasesAreSigned`,
  `probes/releasesHaveProvenance`, `checks/evaluation/signed_releases.go`)
  the check reads the five newest releases with assets. A release with an
  asset ending in `.asc`, `.minisig`, `.sig`, `.sign`, `.sigstore` or
  `.sigstore.json` scores 8, one with an asset ending in `.intoto.jsonl`
  scores 10, and the check is the average. It matches names and verifies
  nothing. The index is the file to release because it is what consumers
  verify first (CON-2); each artifact it lists keeps its own attestation
  on ghcr.io.

  The PUB-4 attestation's subject is the OCI manifest digest, which a
  downloaded `index.json` cannot be checked against. The index job
  therefore attests `index.json` itself with `subject-path`, SLSA
  provenance as in PUB-3, after the manifest's attestation and before the
  `latest` tag. A run that fails there leaves `latest` on the old serial,
  and the next run publishes the serial again.

  `index.json.sigstore.json` is the bundle `actions/attest` writes for that
  step. `index.json.intoto.jsonl` is the bundle's DSSE envelope on one
  line, the in-toto attestation bundle format named after the file it
  covers. The envelope carries no certificate, so consumers verify with
  the Sigstore bundle (`docs/consumers.md`).

  A separate job, `github-release`, creates the release after the index
  job. It runs in the `release` environment with `contents: write` only
  (GI-8), checks out nothing and runs `gh release create` on the files the
  index job uploaded. gh creates the release as a draft, uploads the
  assets, then publishes it, and fails when a published release with the
  tag exists. A failed job is completed by re-running it while the
  workflow artifacts exist (one day); a serial whose release is never
  created stays without one.

  `release/index.py` writes the notes from the previous and the new index:
  added are versions the previous index does not list, yanked are
  versions whose `yanked` was empty there. The first index lists every
  version as added.

  Immutable releases are enabled for the repository (decided 2026-10-15,
  formerly OQ-9): once a release is published, GitHub keeps its tag from
  moving and its assets from being replaced or deleted, and adds its own
  release attestation. `gh release create` uploads to a draft and
  publishes afterwards, which immutability requires. Independently, a
  replaced `index.json` fails verification unless it carries an
  attestation from the release workflow on `main`.

  - Test: `release/test_release.py::Index.test_release_notes`; manual: the
    first release run after the merge creates `index-<serial>` and the
    documented verification passes on its assets
  - Since: #249

## Mirrored images

quay.io/kubevirt/kubevirt-csi-driver is published only as `latest`, and
quay.io deletes the previous digest once `latest` moves (kubevirt generator
README, Driver image). The kubevirt generator's CSI fixtures and a KubeVirt
CSI end-to-end run need a digest that stays pullable. The release workflow
therefore copies the image into `ghcr.io/kadet-hub/mirror/<name>`.

The copy is a job of the release workflow, because GI-8 allows
`packages: write` only there. The workflow's daily schedule and its runs on
`main` also run the mirror job, and a run where upstream has not moved
changes nothing. The job uses oras from `setup-oras`, pinned by version and
sha256 like every other push. `oras cp` by digest copies the manifest bytes
unchanged, so the mirror has the upstream digest. Checked on 2026-10-23 with
oras 1.3.5: `sha256:44c98353...f409` copied to an OCI layout resolves to
the same digest.

The `mirror/` prefix keeps the names apart from generators, which publish
to `ghcr.io/kadet-hub/<name>` (PUB-1). `mirror` is on
`policy/reserved-names.txt`, so no entry can take it (REG-2).

The mirror carries no attestation. A provenance attestation from this
workflow would claim a build it did not run. The digest is the pin, and it
equals upstream's.

- PUB-13: The mirror job MUST copy the digest an upstream tag points to
  into `ghcr.io/kadet-hub/mirror/<name>` and tag it there, and MUST NOT
  move an existing tag.

  The tag is the image's source commit, read from its config label
  `org.opencontainers.image.revision`, else `multi.GIT_SHA`, which the
  KubeVirt CSI driver's build sets. Without either label the tag is the
  image's `created` date as `YYYYMMDD`. A tag that already points to the
  same digest leaves the job green. A tag that points to another digest
  fails the job and stays as it is. That happens when upstream rebuilds the
  same commit, which a maintainer then resolves by hand. The job writes
  the upstream reference, the digest and the mirror tag to the run
  summary. The tag on ghcr.io is the durable record, and consumers pin
  `ghcr.io/kadet-hub/mirror/<name>:<tag>@sha256:<digest>`.

  - Test: `release/test_release.py::Mirror`; manual: the first release run
    after the merge tags `mirror/kubevirt-csi-driver:3a1a099330045754011803e3d53cd8276ff21723`
    at `sha256:44c98353e6137455d6a393ad13e04f60e10ee49fdcd00cf078f7f7084714f409`
  - Since: this change

The first push creates the package as private. A maintainer sets it to
public once in the organisation's package settings, so the generator
fixtures and the end-to-end runs can pull it without credentials.

- OQ-10: The image's base layers are CentOS Stream 9 (label
  `org.label-schema.license: GPLv2`). Whether redistributing it on ghcr.io
  needs a source offer beyond pointing to CentOS and kubevirt/csi-driver is
  open, together with OQ-1.

## Incident response

- INC-1: A version confirmed malicious MUST be yanked, its artifact deleted,
  and a GitHub security advisory published and listed in the index. The
  target is 24 hours from confirmation, best effort with one maintainer.

  `docs/incident.md` is the runbook. The entry records advisories as
  `advisories: {<version>: [GHSA-…]}`; only a maintainer pull request may
  add or change them (the gate fails otherwise), and the release copies
  them into the version's index record. The maintainer deletes the
  artifact by hand after the yank is merged, since the deletion cannot be
  undone. The index then keeps the version: a yanked version whose
  artifact is gone is carried over from the previous attested index with
  its digest, reason and advisories, so consumers still find why their
  pinned digest is rejected (CON-2) and the catalog shows the advisory.
  GitHub refuses to delete the last tagged version of a package; the
  runbook deletes the package then.

  Run on 2026-10-10 in the rehearsal fork with a draft advisory: the yank
  with the advisory raised the index serial and the catalog showed both;
  after the package was deleted, a release run reported the index
  unchanged, still listing the version with digest, reason and advisory.

  - Test: `release/test_release.py`, `gate/test_check_entry.py`,
    `catalog/test_catalog.py`; manual: fork rehearsal (2026-10-10)
  - Since: #32
