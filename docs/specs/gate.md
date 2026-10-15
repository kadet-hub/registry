# Kapitan generator marketplace: Gate

Status: Approved
Code: `gate/`, `scan/`, `sandbox/`, `policy/`, `tests/samples/`, `tests/selftest`, `tests/fuzz/`, `.clusterfuzzlite/`, `.github/workflows/{gate,selftest,scheduled,scorecard,codeql,fuzz}.yml`, `.github/actions/setup-gate/`, `.github/CODEOWNERS`, `.github/ruleset.json`
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
  modify only pin files: the `Dockerfile` under `sandbox/` and
  `.clusterfuzzlite/`, the `requirements.in` and `requirements.txt` under
  `sandbox/`, `sandbox/krab/`, `scan/` and `.clusterfuzzlite/`,
  `scan/static-scan`, `sandbox/gitlab-ci.yml`, `.github/workflows/*.yml`
  and `.github/actions/*/action.yml`.

  The gate then passes without an entry; the merge still needs a
  maintainer's approval and code owner review (REV-1), and the selftests
  run the bumped tools. `renovate.json`, `policy/` and the gate's scripts
  stay maintainer pull requests.

  - Test: `gate/test_check_entry.py::Files`
  - Since: #38, #243

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
  `pages: write` and `id-token: write` (CAT-1). The Scorecard job MAY
  hold `id-token: write` (GI-12). Only the release workflow's
  `github-release` job, bound to the `release` environment, MAY hold
  `contents: write`, and that job MUST NOT check out or run repository
  code (PUB-12).
  - Test: none (partial: `release.yml` permissions; the environment's
    branch policy is set with `gh api`)
  - Since: #13, #233, this change

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

- GI-12: OpenSSF Scorecard MUST run on every push to `main` and weekly,
  MUST publish its result to the Scorecard API and MUST upload its SARIF
  to code scanning.

  The published result feeds the badge in `README.md` and replaces the
  Scorecard team's own weekly scan of the repository. The `scorecard`
  workflow has `permissions: {}`; its one job holds `contents: read`,
  `actions: read`, `security-events: write` for the SARIF upload and
  `id-token: write`, with which the action proves to the API which
  workflow produced the result. That token names `scorecard.yml`, so it
  cannot pass the release identity check of PUB-3.

  The API accepts a result only from the default branch, from a workflow
  without `env` or `defaults` and without workflow-level write
  permissions, and from a job on a GitHub-hosted Ubuntu runner whose steps
  all use an action from the API's allowlist, which holds the three this
  job runs: `actions/checkout`, `ossf/scorecard-action` and
  `github/codeql-action/upload-sarif`. Otherwise the run fails.
  scorecard-action supports `push` and `schedule` and calls
  `workflow_dispatch` experimental, so the workflow has no manual trigger.

  - Test: workflow job `workflow-lint` (partial: pins and caches; zizmor
    audits the permissions); manual: the first run on `main` after the
    merge shows a score at the badge URL
  - Since: #233

- GI-13: CodeQL MUST analyze `python`, `actions` and `javascript-typescript`
  on every pull request,
  every push to `main` and weekly, and MUST upload its results to code
  scanning.

  Scorecard's SAST check (GI-12) scores the share of recent commits on
  `main` that a SAST tool checked, so the workflow has no `paths` filter.
  Fork pull requests run it only after a maintainer approves the run. The
  `codeql` workflow has `permissions: {}`; its one job holds
  `contents: read` and `security-events: write` for the upload, and all
  three languages are extracted without a build. `javascript-typescript`
  covers the catalog's `site.js`, which reads the `?tags=` query, and
  `theme.js`; the vendored `count.js` is scanned as well.

  On GitHub-hosted runners the CodeQL action keeps TRAP caches in the
  Actions cache by default, and so does overlay analysis, which GitHub
  enables by feature flag, for its base database. GI-10 rules both out:
  the init step sets `trap-caching: false` and
  `CODEQL_OVERLAY_DATABASE_MODE=none`. Dependency caching is off by
  default outside default setup.

  - Test: workflow job `workflow-lint` (partial: pins; zizmor audits the
    permissions); manual: the init step log of the pull request that
    introduced this shows both caches off
  - Since: #237, #239

- GI-14: The parsers that read submitter files in the gate, and the
  consumer's dependency check, MUST be fuzzed with atheris through
  ClusterFuzzLite on every pull request that changes them and weekly.

  Each target in `tests/fuzz/` passes the fuzzer's bytes to the code below
  as the file it names, and any exception that code does not catch is a
  finding:

  | Target | Code | Input |
  |---|---|---|
  | `fuzz_entry` | `check_entry.step_entry` | `generators/<name>.yaml`, new or a bump, from an owner, a stranger, a maintainer or Renovate |
  | `fuzz_manifest` | `check_entry.step_manifest`, `schema_diff.sources` | `kapitan-generator.yaml`, for a new entry and a bump |
  | `fuzz_plan` | `plan.dependencies`, `plan.check_index` | `kapitan inventory` output, including the tag before the digest |
  | `fuzz_documents` | `tag_check.kinds`, `schema_check.check`, `schema_diff.sources` | a compiled output file, as YAML and as JSON, and `schemas/sources.yaml` |

  The callers exit non-zero on an uncaught exception (GI-7, CON-1), so a
  finding prints a traceback in place of a finding or blocks a valid
  submission; it does not pass a check. `schema_diff.py` only loses its
  review lines.

  `apiserver_check.crd_files` is not fuzzed: importing it needs
  cryptography, which RISK-8 holds at a version with advisories, and a
  second lock would report them again.

  The `fuzz` workflow runs code-change mode for 300 seconds on pull
  requests that touch a target's inputs (CI-1) and batch mode for 1800
  seconds on Wednesdays; ClusterFuzzLite splits the time across the
  targets.

  On GitHub, ClusterFuzzLite keeps corpora, builds and coverage as
  `cifuzz-*` workflow artifacts. It downloads the first unexpired artifact
  of a name from the repository's artifact list and unpacks it without
  path checks. That list holds the artifacts of every run, fork pull
  requests included. GI-10 rules this out like a cache, so the job sets
  `NO_CLUSTERFUZZ_DEPLOYMENT=true`, which replaces the store with a no-op. Every run starts from the seeds in `tests/fuzz/seeds/`, and every
  reproducible crash fails it, including one the pull request did not
  introduce. Without the store ClusterFuzzLite calls no API and clones the
  public repository anonymously, so the workflow has `permissions: {}` and
  passes no token.

  The actions are pinned by commit (GI-6), but the images they run,
  `gcr.io/oss-fuzz-base/clusterfuzzlite-build-fuzzers:v1` and
  `clusterfuzzlite-run-fuzzers:v1`, are tags that Google rebuilds from
  `google/oss-fuzz`, and the commit does not pin them.
  `.clusterfuzzlite/Dockerfile` pins `base-builder-python` by digest. The job holds no token or secret
  and nothing reads its result, so a changed image can fail the job or hide
  a crash, nothing more.

  `base-builder-python` runs Python 3.11, the sandbox image 3.13. atheris
  3.0.0 is the newest release with a cp311 wheel; 3.1.0 has only cp312 to
  cp314 wheels and no sdist, and `renovate.json` holds it back.
  `.clusterfuzzlite/requirements.txt` is compiled with
  `sandbox/requirements.txt` as constraints, so the libraries are the
  gate's versions.

  Scorecard's Fuzzing check (GI-12) scores 10 when the default branch has
  `.clusterfuzzlite/Dockerfile` with a command, or Python is a prominent
  language and a `*.py` file has a line with `import atheris`; otherwise 0.

  - Test: workflow job `fuzz` (partial: a parser added without a target
    goes unnoticed); workflow job `workflow-lint` (pins and caches)
  - Since: #243, #244

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

  Related: [PUB-9](publishing.md) computes the same diff at release,
  against the newest listed version that is not yanked, and attests it.

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

- CMP-5: The fixture project MUST compile to identical output in a further
  run with Kapitan's `--cache` on every backend in `inventory_backends`. A
  difference MUST name the first differing path.

  Users turn the compile cache on because compiles are slow
  (kapicorp/kapitan#839), and kadet generators break under it.
  kapicorp/generators failed with `ModuleNotFoundError` on a cached
  recompile (kapicorp/kapitan#1405). With Kapitan 0.36.3,
  `inventory(lazy=True)` returns a Dict without default boxing once
  `--cache` is set, because the cache key reads the inventory before the
  module runs (kapicorp/kapitan#1620); a generator that looks up optional
  keys lazily then fails with `BoxKeyError`.

  Kapitan keeps the cache in `$XDG_CACHE_HOME/kapitan`, which the sandbox
  image points into the per-run `/tmp` tmpfs (SEC-9), so the run starts
  with an empty cache. It computes the cache key of every kadet input and
  pickles each result into the cache, which covers #1620's lazy inventory
  and output that does not pickle. The only other cache holds kadet
  `HelmChart` renders, which SEC-3 does not let a generator import.

  The run does not cover a cache hit, which needs a second run on the same
  cache. In 0.36.3 a hit whose pickle names a missing kadet module counts
  as a miss and is recomputed (`kapitan/inputs/cache.py`), so #1405 no
  longer fails a compile. Covering hits would need a cache directory that
  outlives one sandbox run, a writable mount SEC-9 does not have, and a
  third compile per backend. Files a generator reads outside its input
  paths are not in the cache key (#1620); with unchanged inputs a stale
  key does not show.

  The run goes through `sandbox/run` with the manifest's binaries allowed,
  so SEC-10 and SEC-11 judge it like the first compile. `diff -r` compares
  it with the same backend's first compile; the finding reads `CMP-5:
  output differs with --cache on <backend>:` followed by the first 20 lines
  of the diff, whose first line names the first differing path. A compile
  that fails under `--cache` shows its exit status and the end of its
  stderr, and its diff reads `Only in out-<backend>: compiled`.

  The run covers every backend because the inventory the cache key hashes
  and the output that gets pickled both depend on the backend. Running it
  on the first backend only, as CMP-2 does, would save the `omegaconf`
  compile, 6.5 of the 10.8 s median below.

  The release build job repeats the gate compile, and CMP-5 with it, for
  versions not yet published (CMP-4); published versions are not compiled
  again, so CMP-5 applies to versions published after it. On 2026-10-13
  all 35 listed versions were published. Compiled as `release/build-all`
  fetches them, all 35 passed CMP-5 on both of their backends,
  `reclass-rs` and `omegaconf`, and the whole gate compile passed. No
  listed version is affected.

  Measured on 2026-10-13 on a 24-core workstation without gVisor, over the
  35 listed versions: CMP-5 took 10.4 to 11.7 s per gate compile (median
  10.8 s; `reclass-rs` 4.2 s, `omegaconf` 6.5 s), on top of 22.3 to
  32.3 s for the rest of it (median 25.9 s), 42 % more over all 35. On
  the `ubuntu-24.04` runner of #159, under gVisor, the `gate-selftest`
  step took 1360 and 1408 s in two runs against 999 s in the last run
  before them (#154). Each sample with one backend took a median 7.2 and
  8.1 s longer, and `pass-backends`, which uses `reclass-rs` and
  `omegaconf` like every listed generator, 15.3 and 17.8 s longer. That
  compares with one baseline run, and the step varied between 843 and
  1425 s over the ten runs before QA-10. The whole Gate step of #155, a
  registration, took 58 s.

  - Test: workflow job `gate-selftest` (`fail-cache-lazy-inventory`)
  - Since: #159

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

- QA-5a: The manifest's `description` MUST NOT contain control or
  bidirectional formatting characters.

  The catalog shows the description on cards and pages, in `llms.txt`
  and in the Atom feed. A C0 control character such as ESC makes the
  feed invalid XML, and bidirectional overrides can make a description
  read differently from what reviewers saw. The set is the one the
  catalog strips from submitter text (CAT-27), so versions listed before
  this rule still render; the feed strips them as well (CAT-18).

  - Test: `gate/test_check_entry.py` (`Manifest.test_description_without_control_characters`)
  - Since: #232

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
  carry is a `review:` line, not a finding. With `--kinds` the check also
  writes the group, version and kind of every document with `apiVersion`
  and `kind`, which the release records (PUB-10).

  - Test: `sandbox/test_tag_check.py`; workflow job `gate-selftest`
    (`fail-tag-without-evidence`)
  - Since: #49, #235

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

  An entry keyed `<group>/<version>` applies to that version of the
  group and takes precedence over the `<group>` entry. Talos machine
  config documents carry `apiVersion: v1alpha1` without a group, so their
  schemas sit under `core/` next to Kubernetes ones; `core/v1alpha1`
  names Talos, `core` names Kubernetes, and each shows with its own
  source and licence.

  The check runs on the first backend's output in the sandbox image
  without network, like SEC-12 and QA-6. A document of a group without
  schemas is a `review:` line, a group without a `sources.yaml` entry is
  a finding. The schemas are part of the reviewed tree, so they pass the
  same scans and the reviewer sees the pinned source. Kapitan's own
  `kapitan validate` was considered, but it downloads schemas at compile
  time, which the sandbox does not allow.

  `pattern` is matched with the `regex` module, which Kapitan already
  installs, not with Python's `re`: CRDs use Unicode property classes such
  as `^\PC*$` (Cilium's `spec.log.value`), which `re` cannot compile, so
  the check crashed on any output that set such a field.

  The schemas live in the generator's tree, so each version is validated
  against the schemas of its own commit and the catalog shows each
  version's own result. A version that moves to a newer upstream release
  must bring the newer schemas in the same commit; on a bump the gate
  report lists every group's software and version before and after
  (`gate/schema_diff.py`), so the reviewer sees schemas that stayed behind
  the code.

  - Test: `sandbox/test_schema_check.py`, `gate/test_schema_diff.py`;
    workflow job `gate-selftest` (`fail-schema-invalid`)
  - Since: #50, #110, #139

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
  result, for example "hashicorp/aws 6.68.0". On a bump the gate report lists
  each provider's version before and after, as QA-7 does for schema
  groups (`gate/schema_diff.py`).

  - Test: `sandbox/test_tf_schema.py`, `gate/test_schema_diff.py`;
    workflow job `gate-selftest` (`fail-tf-schema-invalid`)
  - Since: #72

- QA-9: A maintainer MUST be able to check, before approving, that every
  Terraform schema extract (QA-8) in a pull request's generator equals the
  schema of the provider version it names.

  QA-8 trusts the extract the author ships, as QA-7 trusts CRD extracts,
  and an extract that was edited by hand would let wrong arguments pass.
  The `tf-schema-verify` workflow takes a pull request number, is started
  by hand (`workflow_dispatch`) and runs with `contents: read` and no
  secrets. Like the gate (GI-1) it reads the entry through the API and
  fetches the generator tree as data with `gate/fetch_tree.py`; it never
  runs generator code. For each extract it runs `terraform init` for the
  named provider and version, which downloads the provider from its
  registry and checks the release signature, then `terraform providers
  schema -json`, and compares the provider block and every resource and
  data source type in the extract with the original
  (`sandbox/tf_schema.py compare`). A difference fails the run and names
  the type. The provider binary runs here, but in a job without the
  submitted code and without write permissions.

  A required check on every pull request was considered; it would put a
  network download and a third-party binary into every gate run, which
  the gate avoids by design (QA-8), while the extract only changes when a
  generator raises its pin.

  - Test: `sandbox/test_tf_schema.py` (compare); manual: workflow run on
    a bump pull request
  - Since: #80

- QA-10: Every document of a built-in Kubernetes kind in the first
  backend's compiled output MUST be accepted by a real kube-apiserver of
  the pinned version on create with `dryRun=All`. Each rejection is a
  finding.

  QA-7 checks the output against JSON Schemas, which describe types and
  required fields but not the API server's validation and decoding code.
  A generator of about 4000 lines passed QA-7, and a Kubernetes 1.37 API
  server rejected every workload it rendered: probes without a handler, a
  Service without ports, Secret `data` that was not base64.

  The sandbox image carries kube-apiserver and etcd, pinned in
  `sandbox/Dockerfile` as `KUBERNETES_VERSION` (v1.37.1, from dl.k8s.io)
  and `ETCD_VERSION` (v3.7.2, from the etcd GitHub release), each checked
  against the sha256 its publisher lists. Kubernetes 1.37.1 names etcd
  3.7.0 in `build/dependencies.yaml`; 3.7.2 is the newest patch of that
  minor. Renovate proposes both versions independently, and the reviewer
  of a bump updates the checksums and keeps etcd on the minor the
  Kubernetes release names. envtest from kubernetes-sigs/controller-tools
  was considered: one archive instead of two, but it publishes 1.37.0 only
  and ships kubectl, which the check does not need.

  `sandbox/apiserver_check.py` starts etcd and kube-apiserver on loopback
  in the sandbox image without network, like SEC-12, QA-6 and QA-7, with
  their state in a 512 MiB tmpfs at `/tmp`. The client is Python's
  `http.client`, authenticated with a random static token as a member of
  `system:masters` under `AlwaysAllow` authorization, so RBAC escalation
  checks pass. Each document is POSTed to its collection with
  `dryRun=All&fieldValidation=Strict`, the request `kubectl create
  --dry-run=server` sends with kubectl's default `--validate=strict`, so
  unknown fields are rejected as well. An output without any document
  with `apiVersion` and `kind` starts no server.

  A kind is built in when the server, which runs without CRDs or
  aggregated APIs, serves it in some version; discovery at the start of
  the check decides. That covers the core group and the `*.k8s.io` groups
  kube-apiserver serves itself, including CustomResourceDefinitions and
  APIServices. Custom resources are skipped; QA-7 covers them when the
  generator ships their schemas. A built-in kind in a version the server
  no longer serves, such as `batch/v1beta1` CronJob, is a finding. A kind
  the server does not serve in any version is skipped: removed kinds such
  as `policy/v1beta1` PodSecurityPolicy and `extensions/v1beta1` Ingress,
  client-side kinds such as `v1` Config and `v1` List, and Talos machine
  config with `apiVersion: v1alpha1`.

  Nothing of the output is persisted, so admission that looks up other
  objects would reject references the output itself satisfies.
  Namespaces are therefore created for real, without labels, before the
  first object in them: NamespaceLifecycle and PodSecurity look them up,
  and PodSecurity admits everything in an unlabelled namespace. The
  ServiceAccount, Priority and RuntimeClass plugins are disabled; with
  1.37.1 each rejects a Pod whose service account, priority class or
  runtime class does not exist in the server. A `409 AlreadyExists`, for
  objects the server creates itself such as `kube-system` or
  `cluster-admin`, counts as accepted, because the server validates before
  it looks for an existing object. The server runs with
  `--allow-privileged`, as kubeadm configures it; without it every
  privileged container is rejected. Service IPs come from `10.96.0.0/12`
  and `fd00:10:96::/108`, the kubeadm IPv4 default plus an IPv6 range, so
  a fixed `clusterIP` outside them is a finding, as on a cluster with
  these ranges.

  A finding reads `QA-10: <file>: <kind> <name>: <message>` with the
  server's message cut at 1000 characters. The result line reads `QA-10:
  validated against kube-apiserver v1.37.1: <n> built-in documents, <m>
  skipped`. A server that is not ready within 90 seconds fails the gate
  with the last ten lines of its log (GI-7).

  The release build job repeats the gate compile, and QA-10 with it, for
  versions not yet published (CMP-4); published versions are not compiled
  again, so a later Kubernetes bump applies to versions published after
  it. On 2026-10-12 all 30 listed versions were published. Compiled as
  `release/build-all` fetches them, all 30 passed QA-10: 13 documents of
  built-in kinds in prometheus-operator 1.1.0 (9), rabbitmq 1.0.0 (3) and
  talos 1.0.0 (1) were accepted; the other 27 render only custom
  resources or no Kubernetes documents. No listed version is affected.

  Measured on 2026-10-12 on a 24-core workstation without gVisor: the
  check took 2.9 to 4.3 s per gate compile on outputs with Kubernetes
  documents and 0.8 to 0.9 s on outputs without, over the 30 listed
  versions. On the `ubuntu-24.04` runner of #154, the unit test that
  starts the server and sends 13 documents took 2.4 s; the
  `gate-selftest` step took 1341 s, within the 843 to 1425 s of the ten
  runs before it, so its total does not resolve the check's share. The
  image's unpacked root filesystem grew from 599.7 MB to
  720.6 MB (kube-apiserver 95.9 MB, etcd 24.9 MB), its layers compressed
  with `docker save | gzip -6` from 230.9 MB to 292.0 MB, which includes
  the etcd archive that stays in its `ADD` layer. The consumer sandbox
  (CON-1) uses the same image. Generator code that starts either binary in
  the compile sandbox fails SEC-10 like any undeclared program.

  - Test: `sandbox/test_apiserver_check.py`; workflow job `gate-selftest`
    (`fail-service-without-ports`)
  - Since: #154

- QA-11: Every custom resource in the first backend's compiled output
  whose kind a CRD shipped with the generator (QA-12) defines MUST be
  accepted on create with `dryRun=All` by the QA-10 kube-apiserver with
  the shipped CRDs installed. Each rejection is a finding, and so is a
  custom resource in a version its CRD does not serve.

  QA-7 validates custom resources against JSON Schemas taken from the
  CRDs' `openAPIV3Schema`. A JSON Schema validator does not evaluate what
  only the API server evaluates: CEL rules (`x-kubernetes-validations`),
  the uniqueness of `x-kubernetes-list-type` `set` and `map` lists, and
  the server's metadata checks. The schemas of 21 of the 28 listed
  versions that ship Kubernetes schemas carry 850 CEL rules QA-7 skips.
  Reviews of flux, crossplane and kyverno found output that passed QA-7
  and that the API server rejects. With the upstream CRDs installed in
  the prototype measured below, the server rejects three documents QA-7
  accepts: a HelmRelease that sets
  both `chart` and `chartRef` ("either chart or chartRef must be set"), a
  Crossplane Provider whose `package` names no registry ("must be a fully
  qualified image name") and a Composition in `Pipeline` mode without
  `pipeline`. A `helm.toolkit.fluxcd.io/v2beta1` HelmRelease, a version
  the CRD of helm-controller 1.6.5 no longer defines, gets only a
  `review:` line from QA-7.

  The check extends `sandbox/apiserver_check.py` and uses QA-10's server
  in the same container without network; `sandbox/gate-compile` mounts the
  `schemas` directory into it read-only. Discovery decides which kinds are
  built in before any CRD exists, as under QA-10. The check then creates
  every shipped CRD for real, waits until each is `Established` and
  discovery lists its served versions, and POSTs each custom resource of a
  kind and version a shipped CRD serves to its collection with
  `dryRun=All&fieldValidation=Strict`, creating its namespace first as
  QA-10 does. Strict field validation rejects unknown fields, as QA-7's
  closed schemas do. Transition rules, which compare with `oldSelf`, do
  not run on create; the immutable `compositeTypeRef` of a Composition is
  one.

  Each CRD is installed with `spec.conversion` set to `strategy: None`. A
  conversion webhook cannot run in the sandbox, and with `None` a custom
  resource in any served version is validated against the schema and
  rules of its own version. None of the 147 upstream CRDs measured below
  declares a webhook; KServe adds one to LLMInferenceService and
  LLMInferenceServiceConfig through patch files next to the CRDs, which
  are not CRDs and are not shipped.

  Validation in an operator's admission webhooks and controllers is not
  covered, for example CloudNativePG's validating webhook, cert-manager's
  webhook, Kyverno's admission controller and KubeVirt's virt-api.
  Running them would mean executing the operator next to submitted
  output, which QA-8 rejects for Terraform providers for the same reason.
  That stays with the author's own tests, such as the Kyverno CLI, and
  with the cluster.

  A document that is neither built in nor of a kind a shipped CRD defines
  is skipped and counted. That covers generators that ship no CRD, kinds
  of aggregated API servers such as IronCore's, which have no CRD, and
  documents no API server serves: Talos machine config (`v1alpha1`; a CRD
  group needs a dot), k3d's `Simple` and kind's `Cluster`. Each
  `apiVersion` with skipped documents gets one line `review: QA-11:
  <apiVersion>: no CRD, <n> documents skipped`, which puts the question
  whether a CRD is missing to the reviewer; a bump that drops a CRD the
  previous version shipped shows the same line. Requiring the CRD of every
  kind with a JSON Schema, with an opt-out such as `crds: none` and a
  reason in the group's `sources.yaml` entry, was considered; it moves the
  argument about exemptions into a field the gate has to validate.

  Decided in #170 (OQ-6): kinds without a shipped CRD are skipped with one
  `review:` line per `apiVersion`.

  A finding reads `QA-11: <file>: <kind> <name>: <message>`, with the
  server's message cut at 1000 characters as under QA-10; for a version
  the CRD does not serve, the message reads `<apiVersion> <kind> is not
  served by CRD <crd name>`. When the generator ships CRDs, the result
  line reads `QA-11: validated against <n> CRDs: <m> custom resources,
  <k> skipped`, with `<n>` the established CRDs. QA-10's line keeps
  counting every document of a kind that is not built in as skipped. The
  CRDs share their group's `sources.yaml` entry, so the "Built for" of
  CAT-15 does not change.

  Measured on 2026-10-13 on a 24-core workstation without gVisor, with a
  prototype of the check in the sandbox image (kube-apiserver v1.37.1),
  over the first backend's output of the 35 listed versions, each with the
  upstream CRDs of the kinds it ships JSON Schemas for. All 147 CRDs of 23
  generators were accepted, and each generator's set was established 0.2
  to 4.0 s after its first create (KServe's 11 CRDs took the 4.0 s). The
  server accepted all 302 custom
  resources. 114 documents of seven generators had no CRD (Talos 51,
  IronCore 17, KubeVirt and CDI 15, Linkerd 14, Loki 11, k3d 3, kind 3)
  and 57 were built in. A run of the check, container start included, took
  5.7 to 10.4 s (median 6.2 s) for the 23 versions with CRDs and 2.9 to
  4.5 s (median 3.6 s) for the 12 without. QA-10 and QA-11 share the
  server, so QA-11 adds the difference, 2.6 s at the median and 6.8 s for
  kserve.

  Measured again with the implementation on the same host and outputs,
  with the 147 CRDs as QA-12 lays them out (123 upstream files, 24 compact
  JSON) next to the generators' `sources.yaml`: all 147 were established
  and all 302 custom resources accepted, without a finding. A run of
  `sandbox/apiserver_check.py` as `sandbox/gate-compile` starts it took
  5.8 to 11.0 s (median 6.4 s), 2.4 to 8.0 s (median 3.1 s) more than the
  same version without CRD files; kserve's 11 CRDs make the 8.0 s. On the
  versions as they are, without CRD files, the run took a median 0.04 s
  longer than QA-10 alone, and its QA-10 lines did not change.

  On the `ubuntu-24.04` runner of #170, under gVisor, the `gate-selftest`
  step took 1630 s against 1614 s in the last run of #159. The 45 samples
  both runs share took a median 0.4 s less each, `fail-cr-cel` added
  38.4 s, and the unit tests of `sandbox/test_apiserver_check.py` took
  9.2 s instead of 2.4 s.

  The release build job repeats the gate compile, and QA-11 with it, for
  versions not yet published (CMP-4); published versions are not compiled
  again. The listed versions ship no CRD files, so QA-11 skips their
  custom resources until a later version brings them, and the measurement
  above shows that none of those custom resources would be rejected. Over
  the 35 versions measured above with their own `schemas` directories,
  the check found nothing and printed 58 `review: QA-11` lines for 30 of
  them. The versions `main` listed after that are bumps built from
  kadet-hub/generators 9166cb3, which has no CRD files; the 22 of them on
  `main` at cb64712 pass the whole gate compile of #170 with review lines
  of the same kind. No listed version is affected.

  Evaluating the CEL rules in the JSON Schemas within QA-7 with a Python
  CEL implementation was considered. It adds a dependency, lacks the
  Kubernetes CEL libraries (quantities, IP addresses, CIDRs, formats) and
  still misses list types, defaulting and the metadata checks, while the
  server that runs all of them is already in the image for QA-10.
  Building CRDs from the shipped JSON Schemas was considered too: scope,
  names and the other versions of a CRD are not in them, and QA-7's
  closing would have to be undone.

  - Test: `sandbox/test_apiserver_check.py`
    (`test_custom_resources_against_shipped_crds`); workflow job
    `gate-selftest` (`fail-cr-cel`)
  - Since: #170

- QA-12: Every file under `<group>/crds/` in the manifest's `schemas`
  directory MUST hold exactly one `apiextensions.k8s.io/v1`
  CustomResourceDefinition of `<group>`, named `<plural>.yaml` or
  `<plural>.json` after its `spec.names.plural`. Its group MUST have a
  `sources.yaml` entry and MUST NOT be one kube-apiserver serves without
  CRDs. A file that breaks this, or whose CRD the server rejects or does
  not establish within 60 seconds, is a finding, and QA-11 does not use it.

  The CRDs sit next to the JSON Schemas of their group, so one
  `sources.yaml` entry names software, version, source and licence for
  both, and the reviewer finds them where QA-7 already points. A flat
  `schemas/crds/` with files named `<plural>.<group>.yaml` would separate
  a CRD from the schemas and the `sources.yaml` entry of its group; a
  `crds/` directory at the generator root would need a new key in
  `policy/manifest.schema.json` and a second provenance file for the same
  upstream source.

  Decided in #170 (OQ-4): CRD files live in `schemas/<group>/crds/`.

  A file holds one CRD because upstream files often hold several, or other
  documents: Calico's `v3_projectcalico_org.yaml` holds every
  projectcalico.org CRD in 3.5 MB, Rook's `crds.yaml` every Rook CRD,
  Multus's `multus-daemonset-thick.yml` its DaemonSet too, and the VPA's
  file two CRDs. The file name follows from the CRD, so the reviewer and
  `tools/upstream.py` of kadet-hub/generators find each CRD without a
  mapping.

  `<plural>.yaml` is the upstream file byte for byte, when that file holds
  only this CRD and is at most 1 MiB (SEC-5). Otherwise `<plural>.json`
  holds the CRD document as compact JSON with keys in upstream order: the
  data are unchanged, the encoding is not. Of the 147 CRDs measured
  under QA-11, 123 are upstream files as they are and 24 need the JSON
  form, 17 because their file holds other documents and 7 because they
  exceed 1 MiB as YAML: Argo CD's ApplicationSet (1.39 MB), Tigera's
  Installation (1.55 MB), KServe's InferenceService, LLMInferenceService
  and LLMInferenceServiceConfig (1.96 to 2.75 MB) and Kyverno's
  ClusterPolicy and Policy (1.42 MB each). The largest as compact JSON is
  LLMInferenceService with 879 KB, which also stays below the 1.5 MiB
  request limit of the server's etcd. The 147 CRDs add 26.2 MB to the
  trees of the 23 generators, whose JSON Schemas take 27.2 MB; the most is
  prometheus-operator's 4.6 MB next to 4.3 MB of schemas.

  Always compact JSON would be one rule, but then no file can be compared
  with upstream by checksum or read in review. Dropping the `description`
  fields, 6.8 MB instead of 26.2 MB for the 147, changes the content for
  size alone, and the reproduction in kadet-hub/generators would have to
  repeat it. A `tree:large` exception (SEC-14) per file above 1 MiB lapses
  on every bump, a higher SEC-5 limit under `schemas/` loosens a scan rule
  for size, and neither handles files with several documents.

  Decided in #170 (OQ-5): the upstream file byte for byte when it holds
  only this CRD and fits 1 MiB, compact JSON otherwise.

  A CRD file copies a CRD document that exists as a YAML file at the
  group's `source`. KubeVirt's virt-operator assembles its CRDs in Go
  (`crds.go`) from the schemas in `validations_generated.go` (2.0 MB), CDI
  keeps its 12 CRDs as YAML in Go string literals (`crds_generated.go`),
  and Linkerd's are Helm templates in `charts/linkerd-crds`. These
  generators ship no CRDs, and their kinds, 29 of the 114 skipped
  documents measured under QA-11, stay with QA-7. Deriving CRDs
  mechanically, CDI's literals extracted or Linkerd's chart rendered with
  `helm template` at the tag and its default values, with the derivation
  named in the `sources.yaml` comment and reproduced by
  `tools/upstream.py`, is a later change in kadet-hub/generators; the gate
  treats a derived file like any other. KubeVirt has no such path short of
  running virt-operator.

  Decided in #170 (OQ-7): only CRD documents that exist as YAML files at
  the `source` for now.

  Only the CRDs of kinds the output uses need shipping, as with JSON
  Schemas: Crossplane's provider-upjet-aws 2.9.0 has 2131 CRD files with
  107 MB, of which the crossplane generator uses ProviderConfig and
  ClusterProviderConfig.

  The gate reads CRD files with the safe YAML loader, extended so that a
  plain `=` is a string, as `tools/upstream.py` does. Prometheus
  Operator's AlertmanagerConfig lists `=` among its matcher types, and
  PyYAML's safe loader reads it as the YAML 1.1 value key and fails.

  A CRD of a group the server serves before any CRD is installed, such as
  `rbac.authorization.k8s.io` or `apiextensions.k8s.io`, would let a
  generator add a version or kind to a built-in group, which the check
  would then treat as served.
  Groups under `k8s.io` that kube-apiserver does not serve, such as
  `gateway.networking.k8s.io` and `autoscaling.k8s.io`, are allowed; their
  upstream CRDs carry the `api-approved.kubernetes.io` annotation the
  server requires there.

  A file that breaks the layout is a finding that names the rule, with
  `<file>` its path in the `schemas` directory, for example `QA-12:
  example.com/crds/widget.yaml: not named example.com/crds/widgets.yaml or
  .json`. A CRD the pinned server rejects, for example for a CEL rule
  above the cost limit, is a finding `QA-12: <file>: <message>` with the
  server's message. A CRD whose names another shipped CRD already holds
  (`NamesAccepted` is `False`) is a finding at once, and one that is not
  `Established` 60 seconds after the CRDs were created is one then; both
  read `QA-12: <file>: not established within 60 s:` followed by the
  condition's message. The generator then ships a
  CRD the pinned server accepts, or none, which leaves its kinds to QA-7.
  All 147 measured CRDs were accepted by v1.37.1. CRDs in the compiled
  output are not installed; QA-10 dry-runs them as built-in documents, and
  no listed version emits one.

  The CRD files are part of the tree and pass the static scans, as the
  JSON Schemas do, whose descriptions they repeat. gitleaks 8.30.1 with
  `policy/gitleaks.toml` found nothing in the 147 CRDs as JSON, and none
  contains a string SEC-3 bans in non-Python files. The gate does not
  check the licence of schema files. A CRD file is a copy under the
  licence of its group's `sources.yaml` entry (Apache-2.0, MPL-2.0 for
  rabbitmq.com); for the JSON form the `sources.yaml` comment states the
  re-encoding, as it does today for JSON Schemas written without
  indentation.

  The gate does not compare a CRD file with upstream, as it does not for
  JSON Schemas: the reviewer checks the `sources.yaml` entry, and the
  reproduction of UPD-2 in kadet-hub/generators covers its own
  generators. An edited CRD only loosens or tightens the check of its own
  generator, as an edited JSON Schema does, and consumers do not apply it.
  Fetching upstream in the gate would put network into it. A
  maintainer-started workflow like `tf-schema-verify` (QA-9) that fetches
  each `source` at its ref and compares every CRD file as data follows
  once a generator from outside kadet-hub/generators ships CRDs.

  Decided in #170 (OQ-8): CRD files get the same trust as JSON Schemas.

  - Test: `sandbox/test_apiserver_check.py`
    (`test_crd_files_that_break_the_layout_are_findings`; the `=` loader
    and conversion `None` in `test_custom_resources_against_shipped_crds`)
  - Since: #170

  QA-11 and QA-12 need no change to `./check` in kadet-hub/generators,
  which runs `sandbox/gate-compile` from the registry's `main` (CHK-3).
  Follow-ups outside this repository:

  - kadet-hub/generators `tools/upstream.py` and its spec (UPD-2 to
    UPD-4): regenerate each `schemas/<group>/crds/` file from the source
    at the new release, trusted only if regenerating at the current ref
    reproduces the committed file byte for byte; a CRD missing at the new
    release becomes an issue. Go code and Helm templates stay not
    regenerable.
  - kadet-hub/generators: CRD files for the 23 generators whose sources
    hold CRD files, in their next versions.
  - kadet-hub/generator-template `AGENTS.md`: the "Schemas" rule names the
    CRD files, their location and their form.

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
