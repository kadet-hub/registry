# Kapitan generator marketplace: Gate

Status: Approved
Code: `gate/`, `scan/`, `sandbox/`, `policy/`, `tests/samples/`, `tests/selftest`, `.github/workflows/{gate,selftest,scheduled}.yml`, `.github/actions/setup-gate/`, `.github/CODEOWNERS`, `.github/ruleset.json`
Verified against: main @ 970a5d4

Related: [marketplace.md](marketplace.md) holds the problem, threat model, decisions,
acceptance criteria, residual risks, open questions and the implementation inventory.

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
  - Test: manual: AC-9 run on #9 (2026-10-08)
  - Since: #8

- GI-2: A pull request from a non-maintainer MUST add or modify exactly one
  file, `generators/<name>.yaml` with `<name>` equal to the entry's `name`.
  Deletions and renames are maintainer pull requests.
  - Test: `gate/test_check_entry.py::Files`
  - Since: #8

- GI-2a: A pull request from Renovate, identified as in REG-5, MAY instead
  modify only pin files: `sandbox/Dockerfile`, the `requirements.in` and
  `requirements.txt` under `sandbox/`, `sandbox/krab/` and `scan/`,
  `scan/static-scan`, `sandbox/gitlab-ci.yml`, `.github/workflows/*.yml`
  and `.github/actions/*/action.yml`.

  The gate then passes without an entry; the merge still needs a
  maintainer's approval and code owner review (REV-1), and the selftests
  run the bumped tools. `renovate.json`, `policy/` and the gate's scripts
  stay maintainer pull requests.

  - Test: `gate/test_check_entry.py::Files`
  - Since: #38

- GI-3: Gate jobs MUST run with `permissions: contents: read`, no secrets and
  no `id-token` permission, and MUST pass no runner environment into the
  sandbox.
  - Test: none (partial: `gate.yml` permissions, which zizmor audits in `workflow-lint`)
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

  `tests/workflow-policy` checks that every `uses:` other than `./` and
  `$/` ends in a 40-character SHA, that every `curl` in `.github/` is
  followed by a `sha256sum -c` or `sha512sum -c`, and that every `ADD` from
  a URL in `sandbox/Dockerfile` carries `--checksum`.

  - Test: workflow job `workflow-lint`
  - Since: #27

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
  runs on `main`. `tests/workflow-policy` fails on `actions/cache` and on a
  `cache` or `cache-dependency-path` input anywhere in `.github/`.

  - Test: workflow job `workflow-lint`
  - Since: #27

- GI-11: zizmor and actionlint MUST pass on `.github/` for every pull request
  that changes it.

  The `workflows` workflow runs both, pinned by sha256, with GI-6 and GI-10
  on pull requests that change `.github/`, `sandbox/Dockerfile` or the
  policy script. actionlint 1.7.12 rejects the self-repository syntax `$/`,
  so that one message is ignored; zizmor's `self-repository` finding is
  suppressed where the workspace is the main checkout. The job is not a
  required check: REV-1 requires the gate only, and code owner review
  covers `.github/`.

  - Test: workflow job `workflow-lint`
  - Since: #27

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

  `gate/fetch-charts` pulls with the sandbox image's pinned helm, the only
  step besides the source fetch that has network, compares the `.tgz` with
  `sha256` and unpacks it at `output_path` below the fixture project, which
  replaces whatever the fixture holds there. The static scan runs over the
  unpacked charts as over the tree. The release build job fetches and
  compares again before its compile (CMP-4), without scanning: the digest
  pins the bytes the gate scanned.

  - Test: workflow job `gate-selftest` (`pass-declared-chart`, `fail-chart-sha`)
  - Since: #26

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
  arguments. krab 2.0.0-alpha.5 starts `/opt/krab-python/bin/python` for
  two version probes and then for its kadet runner in its cache under
  `/tmp`; `sandbox/check.py` allows exactly these three calls, and only in
  the krab compile (CMP-4).

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

  On a version bump the gate fetches `previous_sha` from the same `repo`
  and `path`, with its charts, and compiles its fixture once in the same
  sandbox on the first backend; findings of that compile are shown, not
  judged, since the version was approved. `gate/output_diff.py` compares
  the two outputs file by file, puts files with a SEC-12 match of the new
  version first, and writes the first 150 lines of at most 200 characters
  into the report and the full diff as `output.diff` into the
  `gate-report` artifact the comment's run link leads to. A new entry or a
  previous version that cannot be fetched or compiled is stated as such.

  Run on 2026-10-10 in the rehearsal fork: a bump pull request from 0.1.0
  to 0.2.0 passed the gate, and the comment showed one file and one hunk,
  the added label; `output.diff` was in the artifact.

  - Test: `gate/test_output_diff.py`; manual: fork rehearsal (2026-10-10)
  - Since: #30

- SEC-14: An exception MUST name the rule ID, the file path and the sha256 of
  that file's content, and lapses when the content changes. SEC-9, SEC-10,
  SEC-11 and GI-* findings MUST NOT be excepted; SEC-12 findings are handled
  through `output_capabilities` only.

  Exceptions cover the static findings that name one file of the generator
  tree. Rule IDs:

  | Rule | Finding |
  |---|---|
  | `gitleaks:<rule>` | a gitleaks finding (SEC-1) |
  | `semgrep:<rule>` | a blocking semgrep finding (SEC-3) |
  | `imports`, `template` | the import and template checks (SEC-3) |
  | `ruff:<code>` | a ruff finding (QA-3) |
  | `tree:executable`, `tree:banned`, `tree:large` | executable, banned or oversized files (SEC-5) |

  ClamAV and GuardDog findings, symlinks and the other tree findings, and
  every finding in a fetched chart have no exception. `scan/exceptions.py`
  applies the entry's exceptions to the static scan report in the gate and
  in the rescan (SEC-15): a matching finding is printed as `excepted:` and
  does not fail; an exception whose file changed is reported as lapsed and
  the finding stands. The entry's owners write exceptions in their pull
  request; the maintainer decides in review, and the gate comment shows
  every exception that was used.

  - Test: `scan/test_exceptions.py`
  - Since: #29

## Rescans

- SEC-15: A scheduled workflow MUST re-run SEC-1, SEC-2, the blocking rules of
  SEC-3, SEC-5 and SEC-6 against the latest version of every listed generator
  daily and open or update one issue per finding rule. A finding does not
  yank automatically (INC-1).

  `scheduled.yml` runs `scan/rescan` for every entry on `main` whose
  version is not yanked: it fetches `source.sha:source.path` without
  checkout and runs `scan/static-scan`, which adds QA-3; review and warning
  lines are not findings. A rule is the tool and, for gitleaks, semgrep and
  GuardDog, the rule ID; `tree`, `imports`, `template`, `ruff` and `clamav`
  findings group by tool. The issue title is `rescan: <name> <version>:
  <rule>`; an open issue with that title gets the current finding lines,
  otherwise a new one is opened.

  The scan job has `contents: read` only and writes its findings to a file.
  A second job with `issues: write` reads nothing else and renders finding
  lines in a code fence, as the gate comment does (GI-4).

  Run on 2026-10-10 in the rehearsal fork with a clean entry and one whose
  `sha` the tag does not point to: the first run opened `tag drift:` and
  `rescan: ... fetch` issues and none for the clean entry, the second run
  updated both instead of opening new ones.

  - Test: `scan/test_rescan_issues.py`; manual: fork rehearsal (2026-10-10)
  - Since: #28

- SEC-16: The scheduled workflow MUST open an issue when an entry's
  `source.tag` no longer resolves to `source.sha`.

  The scan job compares with `git ls-remote`, as REG-1 does, and the issue
  title is `tag drift: <name> <tag>`.

  - Test: `scan/test_rescan_issues.py`; manual: fork rehearsal (2026-10-10)
  - Since: #28

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

  krab evaluates kadet components in `/opt/krab-python`, a venv in the
  sandbox image with only `kadet` and `jinja2`, so a component that imports
  a Kapitan internal krab's `kapitan` shim lacks fails under krab instead of
  finding the real Kapitan. It compiles with `--no-daemon` and one worker,
  and is compared with the first backend's Kapitan output. A krab compile
  that exits non-zero without a trace or output finding is `incompatible`.

  The release build job repeats the gate compile, including krab, for every
  version not yet published and writes the result into the metadata; a
  finding fails the build. Published versions keep their metadata, since
  the sign job skips them.

  Run on 2026-10-09 in the rehearsal fork: the build job compiled a new
  entry under gVisor with Kapitan and krab, the artifact config and the
  index recorded `compatible`, and a second run reported the version as
  published without compiling it.

  - Test: workflow job `gate-selftest` (AC-5); manual: fork rehearsal (2026-10-09)
  - Since: #24

## Quality gate

- QA-1: The generator tree MUST contain `README.md` with at least one
  inventory example and `CHANGELOG.md` with an entry for the tagged version,
  and the tree or the repository root MUST contain `LICENSE`.

  An inventory example is a fenced code block containing `parameters:`. An
  entry is a Markdown heading that contains the version from `source.tag`
  as a whole word, such as `## 1.4.0` or `## [1.4.0] - 2026-10-09`. The
  repository root is read from the fetched commit, without checkout.

  - Test: `gate/test_check_entry.py` (`Quality`)
  - Since: #25

- QA-2: `license` MUST be the SPDX identifier of an OSI-approved license
  (`policy/licenses.txt`), and `LICENSE` MUST match it.

  `policy/licenses.txt` lists Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause,
  ISC, MPL-2.0 and the `-only` and `-or-later` forms of LGPL-3.0, GPL-3.0
  and AGPL-3.0; a maintainer pull request adds more. Each line carries a
  pattern for the license's own wording, matched against the first 4 KiB
  of `LICENSE` with whitespace collapsed. This catches a mismatched or
  missing license, not an edited text. The `-only` and `-or-later` forms
  share a text and are not told apart.

  - Test: `gate/test_check_entry.py` (`Quality`)
  - Since: #25

- QA-3: `ruff check` with the pinned version and `policy/ruff.toml` MUST pass
  on the generator tree.

  `policy/ruff.toml` selects `E9` and `F`: syntax errors and pyflakes
  findings such as undefined names and unused imports, no style rules. It
  excludes nothing; the tree's own ruff configuration and `noqa` comments
  are ignored.

  - Test: workflow job `gate-selftest` (`fail-ruff-undefined-name`)
  - Since: #25

- QA-4: The fixture project MUST contain a `minimal` target.
  - Test: workflow job `gate-selftest` (`fail-no-minimal`)
  - Since: #25

- QA-5: The manifest MUST validate against `policy/manifest.schema.json` and
  the entry against `policy/entry.schema.json`.
  - Test: `gate/test_check_entry.py` (`Entry`, `Manifest`)
  - Since: #8

- QA-6: The gate MUST fail when the manifest carries `kubernetes`, `helm` or
  `terraform` without the evidence `policy/tags.yaml` names for it, and
  MUST list every other tag for review.

  `kubernetes` needs a document with `apiVersion` and `kind` in the
  compiled output, `terraform` a `*.tf.json` or `*.tf` file there, `helm`
  a chart in `charts` or `helm template` in `binaries`. The check runs on
  the first backend's output in the sandbox image without network, like
  SEC-12. The other tags describe purpose, which no file shows; the gate
  comment names them as `review:` lines, and the reviewer checks them
  against `/tags/` (CAT-13). Evidence for a tag the manifest does not
  carry is a `review:` line, not a finding.

  - Test: `sandbox/test_tag_check.py`; workflow job `gate-selftest`
    (`fail-tag-without-evidence`)
  - Since: #49

- QA-7: When the manifest names a `schemas` directory, every document with
  `apiVersion` and `kind` in the compiled output for which it holds a
  schema MUST validate against it, and the result MUST name the software
  and version of each schema group used.

  The directory holds JSON Schemas as `<group>/<kind>_<version>.json`
  (`core` for the core group), the layout of the
  [kubernetes-json-schema](https://github.com/yannh/kubernetes-json-schema)
  and CRD extracts, and `sources.yaml`, which maps each group to the
  software, its version and the upstream URL the schemas come from:

  ```yaml
  external-secrets.io:
    software: External Secrets Operator
    version: 2.11.0
    source: https://github.com/external-secrets/external-secrets/tree/v2.11.0/config/crds/bases
  ```

  The check runs on the first backend's output in the sandbox image
  without network, like SEC-12 and QA-6. A document of a group without
  schemas is a `review:` line, a group without a `sources.yaml` entry is
  a finding. The schemas are part of the reviewed tree, so they pass the
  same scans and the reviewer sees the pinned source. Kapitan's own
  `kapitan validate` was considered, but it downloads schemas at compile
  time, which the sandbox does not allow.

  The schemas live in the generator's tree, so each version is validated
  against the schemas of its own commit and the catalog shows each
  version's own result. A version that moves to a newer upstream release
  must bring the newer schemas in the same commit; on a bump the gate
  report lists every group's software and version before and after
  (`gate/schema_diff.py`), so the reviewer sees schemas that stayed behind
  the code.

  - Test: `sandbox/test_schema_check.py`, `gate/test_schema_diff.py`;
    workflow job `gate-selftest` (`fail-schema-invalid`)
  - Since: #50

- QA-8: When the manifest names a `schemas` directory that holds a
  Terraform provider schema, every provider block, resource and data
  source of that provider in the compiled `*.tf.json` MUST validate
  against it, and the result MUST name the provider and version.

  QA-7 covers only documents with `apiVersion` and `kind`, so Terraform
  output was checked only for its file names (QA-6). The terraform
  generators (kadet-hub/generators#3) were validated with `terraform
  validate` by their author, which the gate cannot reproduce.

  The schema is the output of `terraform providers schema -json` for the
  version the generator pins, reduced to the provider configuration and
  the resource and data source types its output uses, stored as
  `schemas/terraform/<namespace>_<type>_<version>.json`, for example
  `schemas/terraform/hashicorp_aws_6.68.0.json`. The full schema exceeds
  the 1 MiB file limit (SEC-5): for `hashicorp/aws` 6.68.0 it is 19.7 MB,
  the extract of the 15 resource types terraform-aws emits 56 KB (both
  measured with Terraform 1.16.5). `sandbox/tf_schema.py extract` produces
  the extract from the full schema and the compiled output. `sources.yaml`
  gets one entry per provider, keyed `terraform/<namespace>/<type>`, with
  `software`, `version` and `source` (the registry page of that version).

  Each directory of `*.tf.json` files is one Terraform module. The check
  takes the provider pins from its `required_providers`; a provider
  without an exact version (`6.68.0` or `= 6.68.0`) or without a schema
  for that version is a `review:` line, as a kind without schema is under
  QA-7. A resource or data source belongs to the provider named by its
  `provider` argument, otherwise to the local name before the first `_`
  of its type. The check reports: a type missing from the schema, an
  unknown argument or nested block, a missing required argument or block,
  a read-only (computed) attribute that is set, a block given more often
  than `max_items` or less often than `min_items`, and a literal whose
  type does not convert to the attribute type, including missing or
  unknown attributes of object values. Values containing `${` are not
  type-checked, and meta-arguments (`count`, `for_each`, `depends_on`,
  `provider`, `lifecycle`, `dynamic`) are skipped. It runs with QA-7 on
  the first backend's output in the sandbox image without network and
  without Terraform or provider binaries.

  Running `terraform validate` in the gate was considered. It needs the
  provider binary, which means a download per provider version and
  executing a third-party plugin next to submitted code; the schema
  extract gives the same argument-level check without either. What it
  does not cover is provider-side validation (value ranges, regular
  expressions, conflicts between arguments); that stays with the
  author's `terraform validate` and with plan time.

  The catalog's "Built for" (CAT-15) lists the provider from the same
  result, for example "AWS provider (hashicorp/aws) 6.68.0".

  - Test: `sandbox/test_tf_schema.py`; workflow job `gate-selftest`
    (`fail-tf-schema-invalid`)
  - Since: tbd

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

  - Test: none (partial: results, review and warning lines, the compare
    link, the krab result, SEC-12 matches, used exceptions and the output
    diff; capability changes are visible only through the SEC-12 lines)
  - Since: #12
