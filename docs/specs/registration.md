# Kapitan generator marketplace: Registration

Status: Approved
Code: `generators/`, `policy/entry.schema.json`, `policy/reserved-names.txt`, `gate/check_entry.py`
Verified against: main @ 970a5d4

Related: [marketplace.md](marketplace.md) holds the problem, threat model, decisions,
acceptance criteria, residual risks, open questions and the implementation inventory.

## Registration

The source repository carries a manifest `kapitan-generator.yaml` in the
generator directory. The marketplace carries `generators/<name>.yaml`: where
the source lives, which commit is approved and who owns the entry. Owners are
GitHub numeric user IDs, because logins can be renamed and reclaimed.

```yaml
# generators/<name>.yaml (marketplace)
source:
  repo: https://github.com/<owner>/<repo>.git   # public github.com or gitlab.com
  path: <generator dir>          # "." for a single-generator repo
  tag: <tag>                     # semver suffix, e.g. v1.4.0 or argocd-v1.4.0
  sha: <40-character commit SHA>
owners: [<GitHub user ID>, ...]
exceptions: []                   # SEC-14
yanked: {}                       # <version>: <reason>
advisories: {}                   # <version>: [GHSA-…], maintainer only (INC-1)
```

```yaml
# <path>/kapitan-generator.yaml (source repository)
name: <name>
description: <one sentence>
tags: []                         # optional, from the list in the schema (CAT-4)
license: <SPDX identifier>
owners: [<GitHub user ID>, ...]
kapitan: ">=0.36.3,<0.37"
dependencies: []                 # must stay empty in version 1 (DEC-10)
binaries: []                     # e.g. "helm template" (DEC-9)
output_capabilities: []          # SEC-12
unparsed_outputs: []             # output globs SEC-12 cannot parse, e.g. "*.md"
charts: []                       # repo, name, version, sha256 of the .tgz, output_path
inventory_backends: [reclass-rs] # each one is compiled
fixtures: tests/consumer         # relative to the generator dir
schemas: schemas                 # optional, relative to the generator dir (QA-7)
```

The fixture project is an ordinary Kapitan project inside the generator
directory, so every check that scans the tree scans it too. Its compile
entries load the generator from `lib/<name>`, where the gate places the
fetched tree; this is the layout consumers use.

- REG-1: An entry MUST pin `source.sha` to a full commit SHA, and the gate MUST
  fail when `source.tag` does not resolve to that SHA.
  - Test: none (partial: `gate/run` checks it; no sample yet)
  - Since: #8

- REG-2: `name` MUST match `^[a-z][a-z0-9-]{1,38}$`, MUST equal the entry's
  file name and MUST NOT be on `policy/reserved-names.txt`.
  - Test: `gate/test_check_entry.py` (`test_reserved_and_similar_names`, `test_bad_path_fails`)
  - Since: #8

- REG-3: The gate MUST fail a new entry whose name equals an existing or
  reserved name after removing `-` and `_`, and MUST flag it for the reviewer
  when it is within edit distance 1 of one.
  - Test: `gate/test_check_entry.py::Entry.test_reserved_and_similar_names`
  - Since: #8

- REG-4: A pull request adding an entry MUST be authored by one of the
  manifest's `owners` at `source.sha`, and the entry's `owners` MUST equal
  them.

  A mirror of someone else's repository with an edited manifest is caught by
  review, not by this check.

  - Test: `gate/test_check_entry.py::Manifest.test_failures`
  - Since: #8

- REG-5: A pull request changing an existing entry MUST be authored by one of
  its owners, by a maintainer, or by Renovate identified by the user ID of
  `renovate[bot]` with the head branch in the marketplace repository.
  - Test: `gate/test_check_entry.py` (`test_bump_by_stranger_and_repo_change`, `test_renovate_bump_needs_same_repo_branch`)
  - Since: #8

- REG-6: A version bump MUST increase the semver parsed from `source.tag`.

  A change that keeps `tag` and `sha`, such as a yank, is not a bump; a new
  `sha` under the same tag is.

  - Test: `gate/test_check_entry.py::Entry.test_bump`
  - Since: #8

- REG-7: Renovate MUST open a pull request updating `tag` and `sha` when the
  source repository publishes a newer matching tag.

  A regex manager in `renovate.json` reads `repo`, `path`, `tag` and `sha`
  in this order, so the entry schema fixes the order. Tags are compared
  within their prefix: `argocd-v1.4.0` only moves to a newer `argocd-v*`.
  `omegaconf` stays at `2.4.0.dev4`:
  Kapitan 0.36.3's omegaconf backend needs `ListMergeMode`, which later
  pre-releases removed. Runners stay on `ubuntu-24.04`: the scanner
  locks are for its Python, and actionlint 1.7.12 does not know newer
  labels.

  Renovate also bumps the tool pins and, where the source allows it, the
  checksum in the same pull request. Each pin uses one of three
  mechanisms:

  - Release asset: oras, gh, actionlint, zizmor, Hugo, gitleaks, conftest,
    krab and etcd are GitHub release assets. Their comment names
    `datasource=github-release-attachments`, which hashes the matching
    asset of the new release. The pinned value MUST be the exact release
    tag, because the datasource looks the release up by it; URLs that need
    the bare number strip the `v` with `${X#v}`, which BuildKit also
    expands in `ADD`. The sha256 MUST be that of the downloaded file, not
    of a file inside it, or Renovate keeps the old hash without an error.
  - Image: kube-apiserver comes from the Kubernetes project's image on
    registry.k8s.io, Terraform from `hashicorp/terraform` on Docker Hub
    (verified publisher HashiCorp), both pinned as `tag@sha256:digest`.
    `sandbox/Dockerfile` copies kube-apiserver with `COPY --from`, which
    Renovate's dockerfile manager updates; `tf-schema-verify` copies
    terraform out with `docker create` and `docker cp`. Both binaries are
    identical to the dl.k8s.io and releases.hashicorp.com downloads.
  - Check: helm (`sandbox/Dockerfile`, `sandbox/gitlab-ci.yml`) and gVisor
    have neither a release asset nor an image published by the project.
    Renovate bumps the version only. On pull requests from `renovate/`
    branches the `checksum-pins` workflow runs `tests/checksum-pins` with
    `contents: read` and no secrets; it compares each checksum with the
    publisher's checksum file (helm `.sha256sum`, gVisor `.sha512`) and
    fails with the line to paste.

  The release-asset comments have their own match string: `github-releases`
  also returns digests, a commit SHA, which it would write into a
  `_SHA256` field.

  Renovate opens pull requests on Mondays before 06:00 Europe/Berlin
  (`schedule`, cron syntax), so they wait as one batch at the start of the
  week. Vulnerability fixes and the Dependency Dashboard's manual
  checkboxes are not bound to the schedule.

  Renovate proposes a version only once it has been published for three
  days (`minimumReleaseAge`), and `internalChecksFilter: strict` holds back
  the branch and the pull request until then. The age counts from the
  datasource's release timestamp: the publish time on PyPI and of GitHub
  releases and their assets, also for actions whose tag has a GitHub
  release; the last push of the tag on Docker Hub; the date GitHub
  announced a runner label. A version without a timestamp is held
  (`minimumReleaseAgeBehaviour: timestamp-required`), so a failed Docker
  Hub lookup delays the update instead of letting it through.

  Two kinds of update never carry a timestamp and go through at once
  (`timestamp-optional`): the entry bumps themselves, because `git-tags`
  reads no dates, and images outside Docker Hub, whose registries list
  tags without dates. Security updates are not delayed (RISK-11).

  - Test: manual: `renovate --platform=local --dry-run=lookup` with sample
    entries (partial: no CI check). On 2026-10-16 the lookup with
    Renovate 44.161.2 held codeql-action 4.39.0, ruff 0.17.1 and semgrep
    1.181.0, each released less than three days before, and proposed the
    argocd and cilium entry bumps. On 2026-10-20 Renovate 44.171.1 held
    oras 1.3.5 and the clamav digest, proposed the external-secrets entry
    bump and kube-apiserver v1.37.1 from one release back, and held docker
    29.9.1 when the anonymous Docker Hub tag list failed, which
    `timestamp-optional` proposed. Checksums: lookup with tool pins set
    one release back; `checksum-pins` workflow.
  - Since: #6; release age: #259; checksums: #292; timestamps required:
    #306

- REG-8: `source.repo` and `source.path` MUST NOT change after registration
  unless the pull request is authored by a maintainer.
  - Test: `gate/test_check_entry.py::Entry.test_bump_by_stranger_and_repo_change`
  - Since: #8

- REG-9: A removed entry's name MUST be added to `policy/reserved-names.txt`.
  - Test: `gate/test_check_entry.py::Entry.test_removal_reserves_name`
  - Since: #8
