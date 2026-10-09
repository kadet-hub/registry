# Kapitan generator marketplace

Status: Approved
Code: `generators/`, `gate/`, `policy/`, `sandbox/`, `scan/`, `release/`, `consumer/`, `catalog/`, `tests/`, `docs/consumers.md`, `docs/authors.md`, `README.md`, `.github/`, `renovate.json`
Verified against: none (new repository)

## Problem

Kapitan generators are Python modules that `kapitan compile` imports and runs
with the rights of the compiling user: CI tokens, cloud credentials, the ref
backends that decrypt secrets. Their output is applied with the deployer's
rights. Sharing a generator today means pointing `kapitan.dependencies` at
someone's repository and trusting it. Nothing between the author's tag and the
consumer's compile looks for malicious code or output, and nothing records
whether a generator compiles on krab.

The marketplace is the public repository `kadet-hub/registry` with one entry
per generator. An entry is added by pull request; a gate defined on `main`
runs the security, compile and quality checks; a maintainer reviews and
merges; the release workflow republishes the checked tree as an attested OCI
artifact. Consumers fetch by digest, verify, and compile in the marketplace's
sandbox.

## Threat model

Attackers: a hostile submitter, a hostile later maintainer of a benign
generator, a hostile chart repository, a pull request against the
marketplace's own CI, an attacker between registry and consumer, and a
compromised marketplace maintainer account.

The design does not claim to be uncompromisable. It aims at three properties:
no single bypassed check ships malicious code, damage at the consumer is
bounded, and a bad version is revoked quickly.

Trust boundaries, from outside in:

1. Pull request content is data. The gate reads one entry file and never runs
   anything from the pull request (GI-1, GI-2).
2. Generator code runs only inside the sandbox (SEC-9). Every other runtime
   check is detection.
3. Gate checks see only what the fixtures trigger. Static rules are review
   aids, not a boundary: a kadet generator can reach `os` through modules it
   legitimately imports. At the consumer only the consumer sandbox (CON-1)
   bounds such code (RISK-2, RISK-3).
4. Publishing credentials exist only in the release workflow on `main` (GI-8).
   Consumers trust a digest only together with that workflow's attestation
   (PUB-3, CON-2).

## Decisions

- DEC-1: The marketplace republishes vetted artifacts, so consumers fetch the
  bytes the gate scanned rather than a third-party repository.
- DEC-2: Anyone can register a generator.
- DEC-3: Every new entry and every version bump needs a maintainer's approval.
  Renovate opens bump pull requests; nothing merges automatically.
- DEC-4: Kapitan compile is a release gate. The krab result is recorded only,
  until krab has a non-prerelease 2.x version. Security findings under krab
  fail the gate regardless (CMP-4).
- DEC-5: No marketplace CLI or runtime library. Registration is an entry
  file plus a manifest, consumption a standard `kapitan.dependencies` OCI
  entry, the index a generated JSON file. The consumer sandbox (DEC-11)
  reuses the gate's sandbox image. The only web UI is the static catalog at
  `https://kadet-hub.org`, generated from the index (Catalog); ratings,
  accounts and a backend stay out of scope.
- DEC-6: The author's own test suite is not run; fixture compiles in the
  sandbox exercise the generator instead.
- DEC-7: The marketplace lives in the GitHub organization `kadet-hub`. Gate
  jobs that touch submitted code run on GitHub-hosted runners only.
- DEC-8: Artifacts are attested keyless with GitHub artifact attestations
  (Sigstore public-good).
- DEC-9: A generator may run external programs only if the manifest declares
  them (`binaries:`) and `policy/binaries.txt` allows each binary with its
  subcommand. The declaration is enforced on the syscall trace (SEC-10).
- DEC-10: Version 1 accepts no Python dependencies beyond Kapitan's own
  runtime dependencies and its `omegaconf` and `reclass-rs` extras.
- DEC-11: The marketplace ships a consumer sandbox: a container image and
  reusable CI definitions that fetch and verify, then compile without network
  and without credentials.
- DEC-12: Output is policy-checked with conftest, which parses YAML, HCL2 and
  Dockerfiles.
- DEC-13: The marketplace starts with one maintainer (RISK-1) and without
  first-party entries; the gate is validated with the samples in
  `tests/samples/`.
- DEC-14: Pull requests merge only when up to date with `main`, so the gate
  verdict reflects the current policy. There is no merge queue: its
  `merge_group` checks run the workflow from the queued branch, which breaks
  GI-1. Authors update their own branches; a maintainer who updates a branch
  becomes the last pusher and cannot approve it (REV-1).

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
  - Test: `gate/test_check_entry.py::Entry.test_bump`
  - Since: #8

- REG-7: Renovate MUST open a pull request updating `tag` and `sha` when the
  source repository publishes a newer matching tag.

  A regex manager in `renovate.json` reads `repo`, `path`, `tag` and `sha`
  in this order, so the entry schema fixes the order. Tags are compared
  within their prefix: `argocd-v1.4.0` only moves to a newer `argocd-v*`.
  Renovate also bumps the tool pins; versions pinned together with a
  checksum (helm, gitleaks, gVisor) fail CI until the maintainer updates
  the checksum on the Renovate branch.

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

## Gate integrity

The gate runs as a `pull_request_target` workflow, so its definition comes
from `main`. That event carries a write token; the requirements below keep it
away from anything the pull request controls. It runs without approval,
unlike `pull_request` workflows from forks such as the selftest, which
require maintainer approval that a maintainer never gives.

Maintainers are the GitHub numeric user IDs in `policy/maintainers.txt`,
which only a maintainer pull request changes (GI-2, REV-1).

- GI-1: The gate workflow MUST NOT check out or execute pull request content.
  It reads the changed entry file through the API, parses it with a safe YAML
  loader and validates it against `policy/entry.schema.json`.
  - Test: none (partial: `gate.yml` checks out `main` only; AC-9 pending)
  - Since: #8

- GI-2: A pull request from a non-maintainer MUST add or modify exactly one
  file, `generators/<name>.yaml` with `<name>` equal to the entry's `name`.
  Deletions and renames are maintainer pull requests.
  - Test: `gate/test_check_entry.py::Files`
  - Since: #8

- GI-3: Gate jobs MUST run with `permissions: contents: read`, no secrets and
  no `id-token` permission, and MUST pass no runner environment into the
  sandbox.
  - Test: none (partial: `gate.yml` permissions; AC-9 pending)
  - Since: #8

- GI-4: The job that posts the review comment (REV-2) MUST run separately with
  `pull-requests: write` only and consume nothing but the gate's result file,
  rendered as escaped text.
  - Test: none (partial: `gate.yml` job permissions)
  - Since: #12

- GI-5: The required status check MUST be the `pull_request_target` gate job
  with GitHub Actions as expected source, and a fork workflow reporting a
  check of the same name MUST NOT satisfy it (AC-9).
  - Test: manual: AC-9 run on #9 (2026-10-08)
  - Since: #8

- GI-6: Every third-party action MUST be pinned by full commit SHA and every
  downloaded tool binary by sha256.
  - Test: none
  - Since: not implemented

- GI-7: Any gate tool error, timeout or missing result MUST fail the gate. The
  gate job has a 30-minute timeout and the compile output a 50 MiB limit.
  - Test: none (partial: `gate/run` runs with `set -e`; job timeout in `gate.yml`)
  - Since: #8

- GI-8: Only the release workflow, triggered by a push or `workflow_dispatch`
  on `main` and bound to a `release` environment that admits only `main`, MAY
  hold `packages: write`, `id-token: write` and `attestations: write`; its
  Pages deploy job, bound to the `github-pages` environment, MAY hold
  `pages: write` and `id-token: write` (CAT-1).
  - Test: none (partial: `release.yml` permissions; the environment's
    branch policy is set with `gh api`)
  - Since: #13

- GI-9: `policy/entry.schema.json` MUST restrict `source.repo` to
  `^https://(github|gitlab)\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.git$`,
  `source.path` to `^[A-Za-z0-9._/-]+$` without `..`, `source.tag` to
  `^[A-Za-z0-9._-]+$` ending in a semver, and `source.sha` to 40 hex
  characters. `policy/manifest.schema.json` MUST restrict chart `repo` to
  `^(https|oci)://`, chart `name` to `^[a-z0-9][a-z0-9-]*$`, versions to
  semver, `sha256` to 64 hex characters, `fixtures` and `output_path` to
  relative paths without `..`, and globs to `[A-Za-z0-9._*/-]`.

  Workflows pass entry and manifest values to steps only through `env:` and
  quoted shell variables, never through `${{ }}`, end options with `--`
  before positional arguments, and build JSON with `jq --arg`. The release
  workflow validates both schemas again. `git check-ref-format` accepts tags
  such as `v1.0.0-$(id)`.

  - Test: `gate/test_check_entry.py::Entry.test_schema_rejects_injection_and_bad_sha` (partial: workflow review by hand)
  - Since: #8

- GI-10: No workflow MAY use `actions/cache` or the cache options of `setup-*`
  actions; gate tools come from images pinned by digest.

  Cache entries written by a `pull_request_target` run are read by `push`
  runs on `main`.

  - Test: none
  - Since: not implemented

- GI-11: zizmor and actionlint MUST pass on `.github/` for every pull request
  that changes it.
  - Test: none
  - Since: not implemented

## Static checks

The gate fetches the source at `source.sha` without executing it. A finding
fails the gate, apart from exceptions under SEC-14. Findings marked for
review go into the review comment and do not fail the gate.

- SEC-1: The gate MUST fail on any gitleaks finding in the generator tree.
  - Test: workflow job `gate-selftest`
  - Since: #4

- SEC-2: The gate MUST fail on any GuardDog `threat-*` finding from a local
  scan of the generator tree, and MUST list `capability-*` findings for
  review.

  `capability-process-spawn` matches every generator that wraps a declared
  binary, and `capability-filesystem-read` every generator that reads a
  template.

  - Test: workflow job `gate-selftest`
  - Since: #4

- SEC-3: The gate MUST fail when a Python file in the generator tree does not
  parse, imports a module or name `policy/imports.txt` does not allow, or
  matches a rule in `policy/semgrep/blocking/`, and when a non-Python file
  contains `__globals__`, `__builtins__`, `__subclasses__`, `__mro__`,
  `__base__` or `__class__`. Matches of `policy/semgrep/review/` are listed
  for review.

  The import allowlist is checked on the syntax tree, because a semgrep
  pattern cannot express "nothing else". It holds a stdlib subset, `yaml`
  with its safe functions, `jinja2.sandbox`'s sandboxed environments,
  `omegaconf`, `box` and `jsonschema`, and from `kapitan.inputs.kadet` only
  `BaseObj`, `BaseModel`, `Dict`, `CompileError`, `inventory`,
  `inventory_global`, `current_target`, `search_paths`, `topics` and
  `load_from_search_paths`. That module also exposes `cached` (the ref
  revealer), `os`, `sys` and `module_from_spec`. `subprocess` is allowed
  only when the manifest declares a binary. Relative imports and absolute
  imports of a module in the importing file's directory or the tree root
  are in-tree and allowed.

  Blocking semgrep rules cover what the allowlist cannot see: calls of
  `eval`, `exec`, `compile`, `__import__` and `breakpoint`, the process
  functions of `os` (`system`, `popen`, `exec*`, `spawn*`, `posix_spawn*`,
  `fork*`), the attributes `__globals__`, `__builtins__`, `__subclasses__`,
  `__mro__`, `__bases__` and `__code__`, and `yaml` loading without a safe
  loader. Review rules flag `getattr` and `setattr` with computed names,
  `globals()` and `vars()`, `os.environ` and `os.getenv` reads, file
  access through absolute or home paths, and
  `kapitan.utils.render_jinja2_file`, which renders without a sandbox.

  - Test: workflow job `gate-selftest`
  - Since: #4

- SEC-4: Every scanner MUST run with its configuration from `main` and with
  in-tree suppressions disabled: gitleaks with `--config`,
  `--gitleaks-ignore-path` outside the tree and `--ignore-gitleaks-allow`;
  semgrep with `--disable-nosem`, `--no-git-ignore`,
  `--max-target-bytes=0` and every Python file passed as an explicit
  target; ruff with `--isolated --ignore-noqa`.

  Without explicit targets semgrep skips `tests/` and `vendor/` directories
  and files above 1,000,000 bytes, so a payload in the fixture tree would go
  unseen.

  - Test: workflow job `gate-selftest`
  - Since: #4

- SEC-5: The generator tree MUST NOT contain symlinks, git submodules, LFS
  pointers, `.gitattributes`, compiled Python (`.pyc`, `.so`, `.pyd`),
  executables, `sitecustomize.py`, `usercustomize.py`, `*.pth`,
  `.gitleaks.toml`, `.gitleaksignore`, `.semgrepignore`, files above 1 MiB,
  non-ASCII paths, or paths that collide after case folding or Unicode
  normalization.
  - Test: workflow job `gate-selftest`
  - Since: #4

- SEC-6: The gate MUST fail when ClamAV `clamscan` reports a detection in the
  generator tree. A signature database older than two days MUST produce a
  warning for review, not a failure.

  The gate runs `freshclam` in the digest-pinned `clamav/clamav` image,
  which updates incrementally from the database the image ships. When the
  update fails, for example because ClamAV rate limits cloud IP ranges, the
  scan uses the shipped database and the age check warns.

  - Test: workflow job `gate-selftest`
  - Since: #4

## Dependencies, binaries and charts

- SEC-7: The manifest's `dependencies` MUST be empty (DEC-10), and every
  declared binary with its subcommand MUST be on `policy/binaries.txt`.

  `binaries.txt` lists allowed subcommands and forbidden flags: `helm
  template` without `--post-renderer`, `--post-renderer-args` or `plugin`,
  `helm version`, and `cue export`, `cue eval`, `cue vet`.

  - Test: `gate/test_check_entry.py::Manifest.test_failures`
  - Since: #8

- SEC-8: Every declared chart MUST be fetched by the gate with `helm pull`,
  match its `sha256`, and pass SEC-1, SEC-2, SEC-5 and SEC-6; the index lists
  the digests.
  - Test: none
  - Since: not implemented

## Sandbox and runtime detection

- SEC-9: Fixture compiles MUST run in a gVisor (`runsc`) container without
  network, as a non-root user, on a read-only root filesystem with only the
  output, temp and `/dev/shm` directories writable and mounted `noexec`, with
  `PYTHONDONTWRITEBYTECODE=1`, `GIT_PYTHON_REFRESH=quiet`, `HELM_PLUGINS`
  empty, `KUBECONFIG=/dev/null` and no environment from the runner. The
  image contains no `git`. The gate MUST call Kapitan with fixed flags and
  ignore a `.kapitan` file in the fixture project. Declared charts are
  mounted read-only at their `output_path`.
  - Test: workflow job `gate-selftest` (partial: AC-4 samples only)
  - Since: #3

- SEC-10: The gate MUST fail when the gVisor syscall trace of a fixture
  compile shows any of:

  - an `execve` attempt other than the Python interpreter, Kapitan's own
    probes and the declared binaries, matched by exact path, or a declared
    binary called with a subcommand or flag `policy/binaries.txt` does not
    allow;
  - any `execveat`, `symlink`, `sendmmsg` or `io_uring_setup`, and a hard
    link with a path outside the directories SEC-9 makes writable;
  - a `connect` or `sendto` outside `AF_UNIX`, a `sendmsg` with an
    `AF_INET` or `AF_INET6` destination (`namelen` 16 or 28), or a `bind`
    other than loopback port 0;
  - an `open` of a decoy file (SEC-11) or through `/proc/*/environ`,
    `/proc/*/root` or `/proc/*/cwd`, or an `open` for writing outside the
    writable directories.

  A trace log above its size cap and a trace line the policy cannot parse
  MUST fail the gate as well.

  gVisor writes the trace outside the sandbox, so the generator can neither
  disable nor forge it, and it follows child processes. A Python audit hook
  is no substitute: `_posixsubprocess.fork_exec` starts a process without
  raising the `subprocess.Popen` event.

  The trace has limits the policy works around. The exit line of `execve`
  reports 0 even when the call failed, so the policy judges attempts. A
  `sendmsg` destination is shown only by its length. Paths are printed
  unquoted, which is why an unparseable line fails; relative paths come
  with the resolved directory, so they are resolved before matching.
  Symlinks are not resolved, hence the ban on creating them; glibc creates
  multiprocessing semaphores with a hard link inside `/dev/shm`.

  Kapitan 0.36.3 itself, in every worker process, tries `git version` along
  `PATH`, runs `uname -p`, and creates an `AF_INET6` socket bound to `::1`
  port 0. `policy/binaries.txt` lists these probes with their exact
  arguments.

  - Test: workflow job `gate-selftest` (partial: AC-4 samples only)
  - Since: #3

- SEC-11: Fixture compiles MUST run with decoy credentials, and the gate MUST
  fail when a decoy value appears in the output, plain, base64- or
  hex-encoded.

  The sandbox `HOME` holds decoy `~/.aws/credentials`, `~/.kube/config`,
  `~/.ssh/id_ed25519` and `~/.gnupg/`, and the environment decoy
  `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN` and `VAULT_TOKEN`, each random per
  run. This catches untargeted credential stealers, not code written against
  the gate.

  - Test: workflow job `gate-selftest` (partial: AC-4 samples only)
  - Since: #3

- SEC-12: The gate MUST run conftest with `policy/output/` over the fixture
  output and fail on every match whose capability the manifest does not
  declare in `output_capabilities`. Files map to parsers by extension
  (`.yml`, `.yaml`, `.json`, `.tf`, `.tf.json`, `Dockerfile`); a file without
  a parser MUST match `unparsed_outputs`.

  Capabilities come from the enum in `policy/manifest.schema.json`:

  | Capability | Matches |
  |---|---|
  | `privileged` | `securityContext.privileged: true` |
  | `added-capabilities` | a non-empty `securityContext.capabilities.add` |
  | `host-path` | any `hostPath` |
  | `host-namespaces` | `hostNetwork`, `hostPID` or `hostIPC` set to true |
  | `rbac-admin` | a `roleRef` to `cluster-admin`, or a Role or ClusterRole rule with `*` in verbs, resources or API groups |
  | `admission-webhook` | a Validating- or MutatingWebhookConfiguration |
  | `tf-provisioner` | a `local-exec` or `remote-exec` provisioner |
  | `tf-external` | the `external` data source |
  | `dockerfile-remote` | `ADD` from a URL, or a `RUN` that pipes `curl` or `wget` into a shell |

  The Kubernetes rules apply to YAML and JSON files and match at any depth,
  so pod specs inside `List` items or custom resources count. Terraform
  rules apply to `.tf` and `.tf.json`, the Dockerfile rule to `Dockerfile`.
  A file that does not parse, or is not a regular file, fails the gate
  (GI-7). Values inside strings, such as a manifest in a ConfigMap, are not
  parsed (RISK-3). Matches of declared capabilities and files under
  `unparsed_outputs` go into the gate report, and the manifest fields into
  the index.

  - Test: `sandbox/test_output_check.py`; workflow job `gate-selftest` (AC-8)
  - Since: #19

- SEC-13: The review comment MUST state the size of the fixture output diff
  against the previously approved version in files and hunks, show hunks with
  SEC-12 matches first, and link the full diff as a workflow artifact.
  - Test: none
  - Since: not implemented

- SEC-14: An exception MUST name the rule ID, the file path and the sha256 of
  that file's content, and lapses when the content changes. SEC-9, SEC-10,
  SEC-11 and GI-* findings MUST NOT be excepted; SEC-12 findings are handled
  through `output_capabilities` only.
  - Test: none
  - Since: not implemented

## Rescans

- SEC-15: A scheduled workflow MUST re-run SEC-1, SEC-2, the blocking rules of
  SEC-3, SEC-5 and SEC-6 against the latest version of every listed generator
  daily and open or update one issue per finding rule. A finding does not
  yank automatically (INC-1).
  - Test: none
  - Since: not implemented

- SEC-16: The scheduled workflow MUST open an issue when an entry's
  `source.tag` no longer resolves to `source.sha`.
  - Test: none
  - Since: not implemented

## Compile gate

- CMP-1: Every target of the fixture project MUST compile with the pinned
  Kapitan version on every backend in `inventory_backends`, exit 0 and produce
  at least one file per target.

  A manifest without `inventory_backends` is compiled with `reclass`,
  Kapitan's default. Targets are the file names below `inventory/targets/`
  without extension, as Kapitan names them without `--compose-target-name`.
  Each backend's output goes through SEC-11 and SEC-12.

  - Test: workflow job `gate-selftest` (AC-2, AC-8)
  - Since: #23

- CMP-2: The fixture project MUST compile to identical output in a second run
  with `CI`, `GITHUB_ACTIONS` and `GITLAB_CI` set.

  This detects payloads keyed on running in CI. Fixtures set values that
  charts would otherwise randomize (`randAlphaNum`, `genCA`). The second run
  uses the first backend in `inventory_backends`, with all three set to
  `true`.

  - Test: workflow job `gate-selftest` (AC-8)
  - Since: #23

- CMP-3: The manifest's `kapitan` range MUST include the pinned Kapitan
  version.
  - Test: `gate/test_check_entry.py::Manifest.test_failures`
  - Since: #8

- CMP-4: The fixture project MUST also be compiled with the pinned krab
  version under the same sandbox and the SEC-10, SEC-11 and SEC-12 checks,
  which fail the gate. Whether the output equals Kapitan's, apart from
  `.krab-manifest.json`, MUST be recorded in the index as `compatible` or
  `incompatible` and MUST NOT fail the gate while DEC-4 holds.
  - Test: none
  - Since: not implemented

## Quality gate

- QA-1: The generator tree MUST contain `README.md` with at least one
  inventory example and `CHANGELOG.md` with an entry for the tagged version,
  and the tree or the repository root MUST contain `LICENSE`.
  - Test: none
  - Since: not implemented

- QA-2: `license` MUST be the SPDX identifier of an OSI-approved license
  (`policy/licenses.txt`), and `LICENSE` MUST match it.
  - Test: none
  - Since: not implemented

- QA-3: `ruff check` with the pinned version and `policy/ruff.toml` MUST pass
  on the generator tree.
  - Test: none
  - Since: not implemented

- QA-4: The fixture project MUST contain a `minimal` target.
  - Test: none
  - Since: not implemented

- QA-5: The manifest MUST validate against `policy/manifest.schema.json` and
  the entry against `policy/entry.schema.json`.
  - Test: `gate/test_check_entry.py` (`Entry`, `Manifest`)
  - Since: #8

## Review

The gate posts one comment: results, the krab result, REG-3 flags,
exceptions, capability changes, the output diff (SEC-13) and a compare link
from the previously approved SHA to the new one. The maintainer reviews the
code diff and the output diff, not only the verdict.

- REV-1: A ruleset on `main` MUST require a pull request with one approval
  from someone other than the last pusher, dismiss approvals on new pushes,
  require code owner review for `.github/`, `policy/`, `gate/`, `scan/` and
  `sandbox/`, require the gate check (GI-5) on a branch up to date with
  `main` (DEC-14), and block force pushes and deletion. The organization
  MUST require two-factor authentication. The maintainer's own pull
  requests use the admin bypass (RISK-1).
  - Test: manual: `gh api repos/kadet-hub/registry/rulesets` matches `.github/ruleset.json`
  - Since: #10

- REV-2: The gate MUST post the comment described above on every pull request
  that adds or changes an entry.

  The comment job keeps one comment per pull request and edits it on every
  run. It renders the gate's report in a code fence longer than any
  backtick run in the report, so text from the entry or the generator tree
  cannot add markup, links or mentions.

  - Test: none (partial: results, review and warning lines and the compare
    link; krab result, exceptions, capability changes and the output diff
    follow with CMP-4, SEC-14, SEC-12 and SEC-13)
  - Since: #12

## Publishing

On a push to `main`, and on `workflow_dispatch` from `main`, the release
workflow reconciles every entry on `main`: the entry's current version gets
an artifact, an attestation and a `<version>` tag unless it is yanked or
already has them. The workflow takes the registry namespace and the
certificate identity from its own repository, so the same file runs in the
rehearsal fork (AC-6); the documented verification names `kadet-hub`.

The build job has `contents: read` only. It fetches each source without
checkout or submodules (`gate/fetch_tree.py`), validates entry and manifest
(GI-9), repeats REG-2 and REG-3 across all entries on `main`, and writes a
normalized tar of the tree `source.sha:source.path` with its metadata: the
manifest fields the index lists, the source, and the tree ID computed from the
files. It runs the checks in the sandbox image without network.

The sign job runs once per entry in the `release` environment. It fetches
`source.sha` itself, blobless, compares the git tree of `source.path` with
the tree ID of the tar's contents and with the metadata, writes the OCI
manifest itself, pushes config and layer to `ghcr.io/kadet-hub/<name>` by
digest, attests the digest, and then sets the `<version>` tag. The krab
result comes from the gate's krab check of the merged pull request once
CMP-4 exists and is `null` until then.

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
        source: ghcr.io/kadet-hub/<name>@sha256:<digest>
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
  hold `id-token` or `packages` permissions. The sign job MUST fail when the
  tree ID of the tar differs from the tree of `source.sha:source.path` read by
  its own fetch.
  - Test: `release/test_release.py` (partial: reproducibility and tree ID;
    the sign job's comparison by AC-6)
  - Since: #13

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

- PUB-4: The release workflow MUST publish an attested index as
  `ghcr.io/kadet-hub/index` with a `serial` that increases with every
  publication, listing per version: name, version, digest, tree ID,
  description, tags, license, Kapitan range, krab result, output
  capabilities, unparsed outputs, binaries, chart digests, owners, source
  repository and SHA, the time it was first published, `yanked` with its
  reason, and advisories (INC-1).

  The index job reads the versions from the registry tags, each version's
  metadata from its config blob, and accepts only digests with a marketplace
  attestation. Versions of a removed entry stay listed as yanked with reason
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
  - Since: #13

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

## Consumers

Kapitan 0.36.3 verifies neither attestations nor digests on OCI fetch, and
fetches only as part of `compile`. The consumer flow therefore fetches with
native tools first and compiles offline. Compiling without `--reveal` needs no
ref backend credentials, except when a `||func` ref is created or gpg
recipients lack a fingerprint; the consumer creates missing refs in a
separate step before the sandboxed compile.

A consumer repository calls the reusable workflow
`kadet-hub/registry/.github/workflows/consumer.yml` pinned by commit SHA and
commits a policy file `.kapitan-sandbox.yaml`, defined by
`policy/consumer.schema.json`:

```yaml
index_serial: 12              # lowest accepted index serial (CON-2)
inventory_backend: omegaconf   # passed to inventory and compile; default reclass
hosts:                        # allowed dependency hosts per type
  oci: [ghcr.io]
  helm: [charts.example.org]
  git: [github.com]
  https: []
binaries: ["helm template"]   # run by the consumer's own inputs
output_capabilities:          # accepted SEC-12 capabilities per output path glob (CON-1b)
  "compiled/logging/*": [host-path]
```

The workflow runs its scripts from its own commit through the
self-repository syntax (`$/`) and the sandbox image of that commit's
`sandbox/` tree (PUB-6). Its `owner` input, default `kadet-hub`, names the
registry namespace and the certificate identity; a rehearsal fork sets its
own.

- CON-1: The reusable workflow MUST, in this order:

  1. run `kapitan inventory` in the SEC-9 sandbox with the SEC-10 trace and an
     empty environment, because the inventory backend imports
     `resolvers.py`;
  2. fail on a dependency in the inventory whose type or host the policy does
     not allow, an `http` dependency, an OCI dependency without a digest or
     with `insecure`, `tls_verify: false`, `subpath` or `media_type`, a helm
     dependency without an exact `version` or with `helm_path`, a git
     dependency whose `ref` is not a full commit SHA or with `submodules`, and
     two dependencies sharing an `output_path`;
  3. fetch the dependencies outside the sandbox (`oras pull` by digest,
     `helm pull`, `git` at the commit) and verify marketplace artifacts and
     their charts (CON-2);
  4. compile in the SEC-9 sandbox with decoys (SEC-11) and the SEC-10 trace
     policy, extended by the policy's `binaries` and the binaries the index
     lists for the fetched generators;
  5. upload the compiled output as the workflow artifact `compiled`.

  The project is the checkout (`persist-credentials: false`) without `.git`
  and `.kapitan`, mounted read-only together with the fetched dependencies,
  which replace whatever the checkout holds at their `output_path`. Kapitan
  runs with fixed flags and without `--fetch`; the policy's
  `inventory_backend` is the only flag the consumer chooses. git
  dependencies are written with `gate/fetch_tree.py`, so its symlink and
  size limits apply. A dependency URL built
  from `oc.env` resolves against the empty environment, so it either fails
  the inventory or names a host the policy has to allow.

  - Test: `consumer-selftest` (AC-10)
  - Since: #15

- CON-1a: The marketplace MUST publish a GitLab CI template that runs the
  same steps with the published sandbox image.

  GitLab-hosted runners cannot run gVisor; the template uses `--network none`
  with the default runtime and documents that SEC-10 is not enforced there.

  - Test: none
  - Since: not implemented

- CON-1b: The compile step MUST run SEC-12 over the output and fail on every
  match the policy's `output_capabilities` does not accept for that path.

  Globs match the path below the output directory, such as
  `compiled/<target>/...`, and `*` also matches `/`. Capabilities come from
  the SEC-12 enum. Files without a parser are listed in the report and do
  not fail: the consumer has no `unparsed_outputs`, and reviews the output
  before applying it (CON-3).

  - Test: `sandbox/test_output_check.py`; `consumer-selftest` (AC-10)
  - Since: #22

- CON-2: Verification MUST check the artifact attestation with
  `gh attestation verify oci://ghcr.io/kadet-hub/<name>@sha256:<digest>
  --owner kadet-hub --cert-identity
  https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main`,
  verify the index the same way, reject an index whose `serial` is lower than
  the policy's `index_serial`, and reject a digest the index does not list
  under the same name or lists as yanked, and a chart whose digest differs
  from the index. The documentation MUST state that Kapitan's `--fetch`
  provides no integrity check.

  A higher serial is accepted and reported, so the consumer raises
  `index_serial` in a reviewed commit. Every OCI dependency under
  `ghcr.io/<owner>/` counts as a marketplace artifact.

  - Test: `consumer/test_consumer.py`; manual: AC-6 consumer run (2026-10-09)
  - Since: #15

- CON-3: The consumer documentation MUST state what listing covers and what it
  does not, referring to the threat model.
  - Test: none
  - Since: #15

## Catalog

The catalog at `https://kadet-hub.org` lets people find a generator and
copy a pinned inventory entry. It is a view on the index: the release
workflow generates it with Hugo from the `index.json` the index job just
published or verified unchanged, and deploys it with GitHub Pages from
`kadet-hub/registry`. The site has no backend, no accounts and no data of
its own, so a later platform with ratings can read the same index instead
of migrating site data.

Each generator has a card with name, description, tags, license, latest
version, owners, source stars and the time of the latest version, and a
page at `/generators/<name>/` with every version. Search and tag filter run
in the browser over the rendered cards. Owner logins and stars
come from the GitHub API at build time; they are display data only, and a
failed lookup shows the user ID or no stars.

- CAT-1: The release workflow MUST build the catalog from the index it
  published or verified in the same run, and deploy it from a job bound to
  the `github-pages` environment, which admits only `main`.

  Run on 2026-10-09 in the rehearsal fork: one release run published the
  artifact and the index and deployed the catalog under a project path;
  the version page showed the attested digest and the owner's login.

  - Test: manual: fork rehearsal (2026-10-09)
  - Since: #16

- CAT-2: A version page MUST show the inventory entry with the digest and the
  CON-2 verification commands; a yanked version MUST show its reason and no
  inventory entry.
  - Test: `catalog/test_catalog.py`
  - Since: #16

- CAT-3: The site MUST render every value from the index and the GitHub API
  through Hugo's contextual escaping and MUST NOT load scripts, styles or
  fonts from another origin.

  Description, tags and owners come from submitters; a description with
  markup is shown as text.

  - Test: `catalog/test_catalog.py`
  - Since: #16

- CAT-4: `tags` in the manifest MUST come from the enum in
  `policy/manifest.schema.json`: `kubernetes`, `helm`, `operators`,
  `terraform`, `cloud`, `observability`, `security`, `networking`,
  `database`, `ci`, at most five per manifest.
  - Test: `gate/test_check_entry.py` (`Manifest`)
  - Since: #16

- CAT-5: URLs `/` and `/generators/<name>/` MUST stay stable.
  - Test: none
  - Since: #16

- CAT-6: The home page MUST link to `docs/consumers.md` and
  `docs/authors.md`, and MUST say so when no generator is listed.

  `docs/authors.md` describes registration for authors: manifest, fixture
  project, entry and what the gate and the review check. The root
  `README.md` points to the catalog and both documents.

  - Test: `catalog/test_catalog.py`
  - Since: #18

## Incident response

- INC-1: A version confirmed malicious MUST be yanked, its artifact deleted,
  and a GitHub security advisory published and listed in the index. The
  target is 24 hours from confirmation, best effort with one maintainer.
  - Test: manual: incident runbook rehearsal
  - Since: not implemented

## Verification

- AC-1 (SEC-1 to SEC-6): planted samples, one per rule, fail the gate:
  hardcoded token, also with `# gitleaks:allow`, base64-decoded `exec`,
  `exec` under `tests/` and in a file above 1,000,000 bytes, `# nosemgrep`,
  `import _posixsubprocess`, `from kapitan.inputs.kadet import cached`,
  `from jinja2.sandbox import Environment`, `jinja2.Template` rendering
  `{{ cycler.__init__.__globals__ }}`, `yaml.load` with `UnsafeLoader`,
  `os.system`, `subprocess` without a declared binary, a Python file that
  does not parse, a `.j2` template using `__globals__`, a `.so` file,
  `.gitattributes`, a symlink, an executable, case-colliding paths and the
  EICAR test file. Samples that cannot live in this repository (token,
  EICAR, collisions, symlink) are generated at test time. Check: workflow
  job `gate-selftest` over `tests/samples/`.
- AC-2 (CMP-1, CMP-2, QA-1 to QA-5, SEC-9, SEC-10): the benign samples pass,
  including one that wraps `helm template` with a declared chart and one
  compiled on `reclass-rs` and `omegaconf` that calls `getattr` with a
  computed name (flagged for review, not failed). Check: `gate-selftest` (partial: QA-1 to QA-4 not
  implemented).
- AC-3 (REG-3, REG-4, REG-5, REG-8, GI-2, GI-9, SEC-8): an entry named
  `kubernet-es` next to a reserved `kubernetes`, an entry or bump authored by
  a non-owner, a bump changing `source.repo`, a non-maintainer deletion or
  rename, a tag `v1.0.0-$(id)`, a chart name `--untardir=/x` and a chart whose
  bytes differ from its `sha256` each fail. Check: `gate-selftest`.
- AC-4 (SEC-9, SEC-10, SEC-11): samples that connect a TCP socket and swallow
  the error, start a process through `_posixsubprocess`, run `helm template
  --post-renderer` through a variable, hide `--post-renderer` behind a
  padding argument longer than the trace's string limit, run helm through a
  symlink in `/tmp`, read `~/.aws/credentials` after `chdir`, and run an
  undeclared binary each fail. Check:
  `gate-selftest`.
- AC-5 (CMP-4): a sample importing a Kapitan internal missing from krab's shim
  is recorded `incompatible` and passes; a sample whose payload fires only
  under krab fails. Check: `gate-selftest`.
- AC-6 (PUB-1 to PUB-5, CON-2): after a merge, the documented verification
  passes for artifact and index, and a second run pushes nothing. An artifact
  attested from another branch fails verification, and so does an index with
  a lower serial. A run that fails between push and attest is completed by
  the next run. A yanked and deleted version stays deleted after the next
  push. Check: manual: release rehearsal in a fork of the registry,
  whose workflow identity differs from `kadet-hub`'s only by the owner.

  Run on 2026-10-08 with a test generator. The first push to the
  fork's `main` published 0.1.0 and index serial 1; `gh attestation verify`
  passed for both with the `main` identity and failed with the identity of
  another branch. A dispatched second run pushed nothing. Yanking 0.1.0
  skipped its build, kept the tag and published serial 2 with the reason. A
  0.2.0 manifest pushed by digest without attestation or tag was attested and
  tagged at the same digest by the next push, with serial 3. After 0.1.0 was
  deleted from the package, the next push did not rebuild it and serial 4
  lists only 0.2.0.

  Run on 2026-10-09 for the consumer, in the same fork with a consumer
  repository calling the reusable workflow pinned by commit: the release
  published the sandbox image once and skipped it on the next run, the
  consumer verified image, index and artifact and compiled the expected
  ConfigMap in the sandbox. `index_serial` above the index serial failed,
  a digest the index does not list failed, and an index newer than
  `index_serial` passed with a notice.
- AC-7 (SEC-15, SEC-16): moving a tag of a listed sample repository produces
  an issue on the next scheduled run. Check: manual: scheduled run in a test
  organization.
- AC-8 (SEC-11, SEC-12, CMP-2): samples that copy a decoy value into a
  ConfigMap, emit an undeclared `cluster-admin` binding, emit a `.tf.json`
  with a `local-exec` provisioner, and change output when `CI` is set each
  fail, and so does a target that produces no file; a sample that emits a
  `hostPath` and declares `host-path` passes. Check: `gate-selftest`.
- AC-9 (GI-1, GI-2, GI-5, GI-10): a fork pull request that edits the gate
  workflow, edits `policy/`, or adds a workflow reporting a check named like
  the gate cannot make the pull request mergeable, and no workflow uses a
  cache. Check: manual: test fork; `gate-selftest` greps `.github/` for
  `actions/cache` and `setup-*` steps without `cache: false`.

  Run on 2026-10-08 with #9 from a test fork: the fork's
  own push workflow reported a successful `gate` check run from GitHub
  Actions (app 15368) on the head commit, the gate in `kadet-hub/registry`
  failed on GI-2 and REG-1, and with a maintainer approval the pull request
  stayed `BLOCKED`; the status check rollup listed only the base
  repository's `gate` as required.
- AC-10 (CON-1, CON-1b): the consumer workflow compiles a sample consumer with its own
  helm input without network, and fails on a generator that reads a decoy
  credential, on a vendored `resolvers.py` that opens a socket during
  `kapitan inventory`, on a dependency URL built from `oc.env`, and on a
  `hostPath` in a target the policy's `output_capabilities` does not cover
  while accepting it in the target it covers. Check: `consumer-selftest`
  over `tests/consumers/`.
- AC-11 (SEC-9, SEC-10): gVisor installs on a GitHub-hosted `ubuntu-24.04`
  runner, runs Kapitan's multiprocessing compile with `--network none`, and
  its trace records `execve` of a helm child process. Hostile probes that
  swallow their errors appear in the trace: `connect` and `sendto` to an
  external address, `sendmsg` with an `AF_INET` destination, a process
  started through `_posixsubprocess.fork_exec`, and an attempt to execute a
  file written to `/tmp`, which `noexec` blocks. Check: `gate-selftest`;
  first passed in the spike workflow with gVisor release-20260928.0.

## Residual risk

- RISK-1 (accepted, DEC-13): one maintainer account controls rulesets, policy
  and the release workflow; its compromise defeats every gate and produces
  correctly attested artifacts. Mitigation: hardware-key 2FA, no long-lived
  admin tokens.
- RISK-2: payloads keyed on consumer inventory values or on detecting the
  sandbox stay inert in the gate. CON-1 bounds them at the consumer.
- RISK-3: output that is harmful only in the consumer's context, or within a
  declared capability, passes SEC-12. The consumer reviews compiled output
  before applying it (CON-3).
- RISK-4: consumers using Kapitan's `--fetch` instead of CON-1 get no
  integrity check and no sandbox.
- RISK-5: GHCR tags are mutable by organization owners; only consumers who
  pin digests and verify (CON-2) are protected.
- RISK-6: a Sigstore outage delays releases (PUB-2).
- RISK-7: GitHub disables scheduled workflows in public repositories after 60
  days without activity, which silently stops SEC-15 and SEC-16. The maintainer re-enables them from GitHub's notification.

## Out of scope

- Ratings, download counts and install telemetry.
- Output schema validation (kubeconform and similar).
- OpenSSF Scorecard.
- Index expiry (TUF freeze protection); the serial (PUB-4) prevents rollback
  only.
- Python dependencies beyond Kapitan's own (DEC-10).
- Author-side provenance.
- Restricted runtimes (Starlark, Wasm, CUE-only generators).
- A Kapitan version matrix.

## Open questions

None.

## Implementation inventory

| Path | Content |
|---|---|
| `generators/<name>.yaml` | Marketplace entry (Registration) |
| `policy/entry.schema.json`, `policy/manifest.schema.json` | QA-5, GI-1, GI-9 |
| `policy/reserved-names.txt` | REG-2, REG-3, REG-9 |
| `policy/maintainers.txt` | maintainer user IDs (Gate integrity) |
| `gate/` | GI-1, GI-2, REG-1 to REG-6, REG-8, REG-9, QA-5: `collect`, `check_entry.py`, `fetch_tree.py` |
| `.github/actions/setup-gate/` | gVisor, scanners and sandbox image for `gate.yml` and `selftest.yml` |
| `policy/semgrep/blocking/`, `policy/semgrep/review/`, `policy/imports.txt` | SEC-3 |
| `policy/gitleaks.toml` | SEC-1, SEC-4 |
| `scan/` | SEC-1 to SEC-6: `static-scan` runner, `tree_check.py`, scanner requirements |
| `policy/binaries.txt` | SEC-7, SEC-10 |
| `policy/output/` | SEC-12 rego rules |
| `policy/licenses.txt` | QA-2 |
| `policy/ruff.toml` | QA-3 |
| `sandbox/` | SEC-9 to SEC-12: image, `gate-compile` runner, `check.py`, `output_check.py`; reused by CON-1 |
| `tests/samples/` | AC-1 to AC-5, AC-8 |
| `tests/consumers/` | AC-10 |
| `.github/workflows/gate.yml` | GI-*, REG, SEC, CMP, QA, REV-2 |
| `.github/workflows/selftest.yml` | `gate-selftest`, on maintainer pull requests |
| `.github/workflows/release.yml` | PUB-1 to PUB-6, GI-8, CAT-1, index and catalog |
| `release/` | PUB-1, PUB-4, PUB-5: `build.py`, `tree.py`, `index.py` |
| `.github/workflows/scheduled.yml` | SEC-15, SEC-16 |
| `.github/workflows/consumer.yml`, `consumer/`, `consumer-selftest` | CON-1, CON-2 |
| `sandbox/gitlab-ci.yml` | CON-1a |
| `policy/consumer.schema.json` | consumer policy `.kapitan-sandbox.yaml` |
| `docs/consumers.md` | CON-2, CON-3 |
| `catalog/` | CAT-1 to CAT-6: Hugo site, `build` script, `test_catalog.py` |
| `docs/authors.md`, `README.md` | CAT-6 |
| `.github/CODEOWNERS`, `.github/ruleset.json` | REV-1; the ruleset is applied with `gh api` |
| `renovate.json` | REG-7, tool and action pins |

Tool versions (Kapitan, krab, gVisor, gitleaks, GuardDog, semgrep, ruff,
ClamAV, conftest, oras, helm, zizmor, actionlint) are pinned when the jobs
are written.
