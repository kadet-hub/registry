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
  Renovate also bumps the tool pins; versions pinned together with a
  checksum (helm, gitleaks, gVisor) fail CI until the maintainer updates
  the checksum on the Renovate branch. `omegaconf` stays at `2.4.0.dev4`:
  Kapitan 0.36.3's omegaconf backend needs `ListMergeMode`, which later
  pre-releases removed. Runners stay on `ubuntu-24.04`: the scanner
  locks are for its Python, and actionlint 1.7.12 does not know newer
  labels.

  Renovate opens pull requests on Mondays before 06:00 Europe/Berlin
  (`schedule`, cron syntax), so they wait as one batch at the start of the
  week. Vulnerability fixes and the Dependency Dashboard's manual
  checkboxes are not bound to the schedule.

  - Test: manual: `renovate --platform=local --dry-run=lookup` with sample
    entries (partial: no CI check)
  - Since: #6

- REG-8: `source.repo` and `source.path` MUST NOT change after registration
  unless the pull request is authored by a maintainer.
  - Test: `gate/test_check_entry.py::Entry.test_bump_by_stranger_and_repo_change`
  - Since: #8

- REG-9: A removed entry's name MUST be added to `policy/reserved-names.txt`.
  - Test: `gate/test_check_entry.py::Entry.test_removal_reserves_name`
  - Since: #8
