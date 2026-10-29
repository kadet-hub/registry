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

The build job has `contents: read`, `packages: read` and
`attestations: read` only. It fetches
each source without checkout or submodules (`gate/fetch_tree.py`), validates entry and manifest
(GI-9), repeats REG-2 and REG-3 across all entries on `main`, and writes a
normalized tar of the tree `source.sha:source.path`, with a LICENSE added
when the tree has none (PUB-15), and its metadata: the manifest fields the
index lists, the source, and the tree ID computed from the files of the
tree. It runs the checks in the sandbox image without network, and the
compile gate under gVisor for versions without a published tag (CMP-4).

The sign job runs once per entry in the `release` environment. It fetches
`source.sha` itself, blobless, compares the git tree of `source.path` with
the tree ID of the tar's contents (PUB-15) and with the metadata, writes the OCI
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
  `source.sha:source.path` and the LICENSE of PUB-15 alone, reproducibly
  (normalized tar, no timestamp in the manifest), MUST NOT use files
  produced by the gate, and MUST NOT hold `id-token` or any write
  permission. The sign job MUST fail when the tree ID of the tar differs
  from the tree of `source.sha:source.path` read by its own fetch, with the
  LICENSE of PUB-15 added.

  The build job holds `packages: read` to tell which versions are
  published (CMP-4) and to read the latest index for the output diff
  (PUB-9). Until this change the requirement forbade any `packages`
  permission while the workflow granted read. The output diff in
  `meta.json` comes from the build job's own compiles, not from the gate's
  `output.diff`.

  It holds `attestations: read` for `gh attestation verify` in the checks
  of a recipe version (REC-12), which verify the index, the pinned
  generators and the included and required recipes.

  - Test: `release/test_release.py` (partial: reproducibility and tree ID;
    the sign job's comparison by AC-6)
  - Since: #13, #226; `attestations: read`: this change; the LICENSE of PUB-15: this change

- PUB-15: When the shipped tree has no `LICENSE` at its root, the build job
  MUST add the source repository's root `LICENSE` at `source.sha` to the
  root of the tar, and MUST fail when neither exists. The sign job MUST
  compare the tar with the tree of its own fetch plus that blob, and the
  metadata's tree ID with the tree of its own fetch alone.

  The shipped tree is `source.sha:source.path`, for a recipe without its
  `tests` entry (REC-11). On 2026-10-29 all 37 generator entries came from
  kadet-hub/generators, which keeps one LICENSE at the repository root, and
  QA-1 accepts that one. Their artifacts therefore carried no license text.
  Every version in index serial 73 declares Apache-2.0, whose section 4(a)
  requires a copy of the license with every redistribution, and the
  marketplace redistributes (DEC-1).

  Recipes get the same. kadet-hub/recipes keeps its LICENSE at the root,
  which REC-4 matches against `policy/licenses.txt`, and REC-4's layout
  allows no LICENSE in a recipe directory, so every recipe artifact gets
  the root LICENSE. A class is a `.yml` file, so the LICENSE in
  `inventory/classes/recipes/<name>/` is never loaded as one.

  `tree` in the metadata and the index stays the tree ID of the shipped
  tree without the added LICENSE. REC-16 looks up an included recipe by
  that ID, computed from the directory at the parent's commit, which holds
  no LICENSE. With the LICENSE in the ID, no recipe version published after
  this change would be found. Nothing else compares a tree ID: `consumer/`
  checks digests and attestations against the index (CON-2, CON-5), the
  catalog does not show the ID, and `docs/consumers.md` verifies digests.
  So `tree` means the same for versions published before and after this
  change. The build job rebuilds the tar of an already published version
  as well, and the sign job compares it under the same rule before it
  finds the existing tag (PUB-2). Published artifacts are not touched.

  QA-1 and REC-4 fail a version without either LICENSE in the gate, so the
  release meets one only for an entry that bypassed the gate. Like the
  other findings of `release/build.py` it then fails the build of every
  entry: `PUB-15: <name>: no LICENSE in the tree or at the repository root`.

  `release/build-all` writes the root LICENSE from its fetch next to the
  tree, as `<name>.LICENSE` for a generator and as `recipes/<name>/LICENSE`
  for a recipe (as `gate/recipe-checks` does), and `release/build.py` adds
  it with mode 0644 like every file of the tar. The sign job reads the
  blob ID with `git rev-parse <sha>:LICENSE`, which its blobless fetch
  resolves without the blob, and writes the tree with `git mktree
  --missing` as REC-11 does.

  - Test: `release/test_build.py` (`Build.test_root_license`);
    `release/test_release.py` (`Recipe.test_sign`, `Recipe.test_sign_generator`,
    `BuildAll.test_root_license_next_to_the_tree`)
  - Since: this change

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

- PUB-14: For every sandbox image it publishes (PUB-6), the release
  workflow MUST attest an SPDX 2.3 SBOM of the pushed image for the same
  digest.

  `release/publish-sandbox` runs syft on the OCI layout it pushes, with
  `ghcr.io/kadet-hub/sandbox` as name and the tree as version, and
  `actions/attest` stores the document with the predicate type
  `https://spdx.dev/Document/v2.3`, as PUB-8 does for artifacts. syft lists
  the Debian packages, the Python packages of both venvs and the Go
  modules of helm, conftest, etcd and kube-apiserver: 609 packages for the
  image of this change, 3.2 MB, which pyspdxtools accepts. syft records
  no license for a Go binary or its modules; PUB-14a covers the programs'
  own texts.

  - Test: `release/test_release.py` (`PublishSandbox`); manual: the first
    release run after the merge, `gh attestation verify
    oci://ghcr.io/kadet-hub/sandbox:<tree> --owner kadet-hub
    --predicate-type https://spdx.dev/Document/v2.3`
  - Since: this change

- PUB-14a: The sandbox image MUST carry the license text of every program
  it bundles outside the Python venvs at `/usr/share/doc/<program>/LICENSE`.

  helm, conftest and krab ship the text in their release archives. etcd's
  archive and the kube-apiserver image do not, so `sandbox/Dockerfile`
  fetches it from the release tag by checksum. None of the five has a
  NOTICE file at its tag. The Python packages keep their license files in
  their `dist-info` directories and the Debian packages theirs in
  `/usr/share/doc/<package>/copyright`. The licenses of the Go modules
  compiled into the four Go programs are not in the image.

  - Test: `sandbox/test_image.py` (`Image.test_licence_texts`), run in the
    image by workflow job `gate-selftest`
  - Since: this change

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
  pushes, for the same digest. Each schema group a generator ships in its
  `schemas` directory MUST be a package of its own in that SBOM, holding
  the group's files, with name, version, download location, declared
  license and copyright from the group's `sources.yaml` entry where it
  has them, and NOASSERTION where it has not.

  The SBOM is written from the pushed tar (`release/sbom.py`): one package
  with the manifest's license as declared license, the source repository
  at `source.sha` as download location and a `pkg:oci` purl with the
  digest, and every file with its SHA-256 and SHA-1. Generators have no
  dependencies (DEC-10), so the SBOM is the reviewed file list. A recipe's
  dependencies are REC-12's.
  `actions/attest` with `sbom-path` stores it with the predicate type
  `https://spdx.dev/Document/v2.3`.

  In the same rehearsal `gh attestation verify --predicate-type
  https://spdx.dev/Document/v2.3` verified keda's SBOM (8 files, purl with
  the pushed digest); `pyspdxtools` validates the document written for
  the published keda 1.0.0 tar.

  A schema group is third-party content: CRDs and JSON Schemas of the
  software the generator renders for, under that software's license
  (QA-7, QA-8). Inside the generator's package it would be declared under
  the generator's license. The group's package takes `software` as name
  (the group key when the entry has none), `version`, `source` as download
  location, `license` as declared license and `copyright`, one line per
  list item. A `source` with more than one URL, such as the rabbitmq
  generator's, is no valid download location. The package then gives
  NOASSERTION there and the URLs as source information. The generator's
  package keeps the files directly in the `schemas` directory, such as
  `sources.yaml`, and every file outside it. The top-level `files` list
  still holds every file of the tar, which the catalog reads (CAT-29).

  A file belongs to the entry that QA-7 or QA-8 applies to it:
  `<group>/<version>` for `<group>/<kind>_<version>.json` when
  `sources.yaml` has that key, `terraform/<namespace>/<type>` for
  `terraform/<namespace>_<type>_<version>.json`, and `<group>` for any
  other file below `<group>/`. A group without an entry, and every group of
  a version without `sources.yaml`, is a package named after its directory
  with NOASSERTION fields. One package per directory was considered. It
  would declare the talos generator's Talos schemas (`core/v1alpha1`,
  MPL-2.0) under the Kubernetes entry (`core`, Apache-2.0), and the
  terraform generators' `terraform/` directory would match no entry,
  since their keys name the provider.

  The generator's package `CONTAINS` each group's package. The schema
  files are inside the artifact, and SPDX 2.3 has no relationship for
  vendored content. `DEPENDS_ON` would claim the generator needs the
  schemas to run, while only the gate's QA-7 and QA-8 read them.

  The sign job parses no YAML from the tree, so a YAML parser bug cannot
  reach the job that holds `id-token: write`. `release/build.py` reads
  `sources.yaml` together with the manifest in the sandbox image and
  writes the manifest's `schemas` directory and the parsed entries to
  `schemas.json` next to `meta.json`. A file it cannot read as a mapping
  counts as missing. The entries are therefore claims of the build job
  (RISK-10), while the files and their checksums come from the compared
  tar.

  On 2026-10-29 `pyspdxtools` validated the documents `release/sbom.py`
  wrote for the published kyverno, rabbitmq and terraform-aws tars, with
  their `schemas.json` written by `release/build.py`.

  - Test: `release/test_release.py::Sbom`, `release/test_release.py`
    (`Recipe.test_sign_generator`), `release/test_build.py`
    (`Build.test_schemas`); manual: fork rehearsal (2026-10-11),
    `pyspdxtools` on the kyverno, rabbitmq and terraform-aws SBOMs
    (2026-10-29)
  - Since: #47, this change

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
  same commit, which a maintainer then resolves by hand. The tag on
  ghcr.io is the durable record, and consumers pin
  `ghcr.io/kadet-hub/mirror/<name>:<tag>@sha256:<digest>`.

  - Test: `release/test_release.py::Mirror`; manual: the first release run
    after the merge tags `mirror/kubevirt-csi-driver:3a1a099330045754011803e3d53cd8276ff21723`
    at `sha256:44c98353e6137455d6a393ad13e04f60e10ee49fdcd00cf078f7f7084714f409`
  - Since: #337

The first push creates the package as private. A maintainer sets it to
public once in the organisation's package settings, so the generator
fixtures and the end-to-end runs can pull it without credentials.

- DEC-16: The mirror references the upstream sources and ships no source
  offer of its own.

  The image's base layers are CentOS Stream 9, labelled
  `org.label-schema.license: GPLv2`. kadet-hub copies the image by digest
  and does not modify or rebuild it. The corresponding sources are
  published upstream: the CSI driver at the commit the tag names, and the
  source RPMs of the base packages in the CentOS Stream 9 BaseOS and
  AppStream source trees on mirror.stream.centos.org. On 2026-10-23 all 120
  source RPMs recorded in the rpm database of
  `sha256:44c98353e6137455d6a393ad13e04f60e10ee49fdcd00cf078f7f7084714f409`
  were listed there.

  Whether a reference to sources someone else hosts satisfies GPLv2
  section 3 for a redistributor is not settled. CentOS can remove older
  source RPMs from the mirror while a mirrored tag still exists. The
  maintainer accepted this risk. A lawyer's answer on it belongs to OQ-1.
  Hosting the sources next to the image was the alternative, and it would
  need the source RPMs fetched and pushed for every mirrored tag.

- PUB-13a: For each tag it mirrors or finds in place, the mirror job MUST
  write to the run summary the upstream reference and digest, the mirror
  tag, the source repository at the tag's commit and the locations of the
  base image's source RPMs (DEC-16).

  The workflow passes the source repository and the source RPM locations
  as arguments. A tag from the `created` fallback is no commit, so the
  summary names the repository without a commit and says so.

  - Test: `release/test_release.py::Mirror`
  - Since: #337

- PUB-13b: `docs/consumers.md` MUST state for each mirrored image the
  upstream image, the source repository, where the base image's source RPMs
  are published, and that kadet-hub does not modify or rebuild it (DEC-16).

  - Test: none
  - Since: #337

## Incident response

- INC-1: A version confirmed malicious MUST be yanked, its artifact deleted,
  and a GitHub security advisory published and listed in the index. The
  target is 24 hours from confirmation, best effort with one maintainer.

  The 24 hours are the maintainer's internal target, not a commitment to
  reporters or consumers. Report handling has no SLA and no response time
  ([SECURITY.md](../../SECURITY.md)). `docs/incident.md` and the catalog
  guide "How kadet-hub works" call the target internal; the runbook refers
  here.

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
