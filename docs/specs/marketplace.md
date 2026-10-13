# Kapitan generator marketplace

Status: Approved
Code: `generators/`, `gate/`, `policy/`, `sandbox/`, `scan/`, `release/`, `consumer/`, `catalog/`, `tests/`, `docs/consumers.md`, `docs/authors.md`, `docs/incident.md`, `README.md`, `.github/`, `renovate.json`
Verified against: main @ 970a5d4

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
  `https://kadet-hub.org`, generated from the index (Catalog). Accounts, a
  backend and ratings of its own stay out of scope; the only rating is a
  👍 count read from GitHub Discussions (CAT-20).
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
- DEC-15: The marketplace lists no generator that renders a chart named in
  the consumer's inventory. SEC-8 pins and scans only the charts a manifest
  declares, so the gate cannot vouch for a chart it never fetched, and the
  generator would mostly rename the chart's values. `docs/authors.md` shows
  instead how to render a pinned chart with the `helm` input and patch the
  output in a kadet step of the consumer's own project (#104).

## Area specs

Requirements live in the spec of their area; IDs are unchanged by the split.

| Spec | Sections | IDs |
|---|---|---|
| [registration.md](registration.md) | Registration | REG |
| [gate.md](gate.md) | Gate integrity; Static checks; Dependencies, binaries and charts; Sandbox and runtime detection; Rescans; Compile gate; Quality gate; Review | CMP, GI, QA, REV, SEC |
| [publishing.md](publishing.md) | Publishing; Incident response | INC, PUB |
| [consumers.md](consumers.md) | Consumers | CON |
| [catalog.md](catalog.md) | Catalog | CAT |
| [legal.md](legal.md) | Legal | LEG |

## Verification

A pull request runs only the test jobs whose inputs it changes. Before
this, any change under `catalog/` or `release/` started the gate and
consumer selftests, 16 to 27 minutes of gVisor runs for checks that
cover none of the changed files.

- CI-1: Each pull request test job MUST run exactly when the change
  touches one of its inputs below, and MUST NOT run otherwise; the
  required `gate` check runs on every pull request (GI-1).

  The inputs are the job's own files plus every file outside them that
  its scripts call or read, taken from the scripts themselves. A script
  that starts using another area's file MUST add it here and to the
  workflow's `paths` in the same pull request. Each job is its own
  workflow, because `paths` filters whole workflows; none of them is a
  required check, so a skipped workflow blocks no merge.

  | Job | Workflow | Inputs |
  |---|---|---|
  | `gate-selftest` | `selftest.yml` | `sandbox/`, `scan/`, `gate/`, `policy/`, `consumer/unpack.py`, `tests/selftest`, `tests/samples/`, actions `setup-gate`, `setup-gvisor` |
  | `consumer-selftest` | `consumer-selftest.yml` | `consumer/`, `sandbox/`, `gate/fetch_tree.py`, `policy/output/`, `policy/binaries.txt`, `tests/consumer-selftest`, `tests/consumers/`, action `setup-gvisor` |
  | `catalog-tests` | `catalog-tests.yml` | `catalog/`, `policy/tags.yaml`, action `setup-hugo` |
  | `release-tests` | `release-tests.yml` | `release/` |
  | `workflow-lint` | `workflows.yml` | `.github/`, `sandbox/Dockerfile`, `tests/workflow-policy` |

  Every workflow also lists its own file. `workflow_dispatch` runs a job
  regardless of the change.

  - Test: manual: the checks of the pull request that introduced this
  - Since: #58

- CI-2: A push to `main` MUST NOT start the release workflow when it
  changes only files that no release job reads: `docs/`, `tests/`,
  Markdown files at the repository root, `renovate.json`, issue and pull
  request templates, `CODEOWNERS`, `.github/ruleset.json`, and the
  test-only workflows of CI-1.

  This list ignores paths instead of listing them, so a new file a release
  job reads still triggers a release; the daily scheduled run (CAT-20)
  catches up on anything a skipped push left out.

  - Test: manual: the release run after the merge of the pull request that introduced this
  - Since: #58

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
  computed name (flagged for review, not failed). Check: `gate-selftest`
  and `gate/test_check_entry.py` (QA-1, QA-2, QA-5).
- AC-3 (REG-3, REG-4, REG-5, REG-8, GI-2, GI-9, SEC-8): an entry named
  `kubernet-es` next to a reserved `kubernetes`, an entry or bump authored by
  a non-owner, a bump changing `source.repo`, a non-maintainer deletion or
  rename, a tag `v1.0.0-$(id)`, a chart name `--untardir=/x` and a chart whose
  bytes differ from its `sha256` each fail. Check: `gate/test_check_entry.py`
  and `gate-selftest` (the chart digest).
- AC-4 (SEC-9, SEC-10, SEC-11): samples that connect a TCP socket and swallow
  the error, start a process through `_posixsubprocess`, run `helm template
  --post-renderer` through a variable, hide `--post-renderer` behind a
  padding argument longer than the trace's string limit, run helm through a
  symlink in `/tmp`, read `~/.aws/credentials` after `chdir`, and run an
  undeclared binary each fail. Check:
  `gate-selftest`.
- AC-5 (CMP-4): a sample whose inventory uses reclass reference syntax, which
  krab does not render, is recorded `incompatible` and passes; `pass-plain`
  is recorded `compatible`; a sample whose payload fires only under krab
  fails. Check: `gate-selftest`.

  The SEC-3 import allowlist names only modules krab's shim provides, so no
  sample can import a missing Kapitan internal and still pass.
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
  cache. Check: manual: test fork; `workflow-lint` (`tests/workflow-policy`)
  for the cache.

  Run on 2026-10-08 with #9 from a test fork: the fork's
  own push workflow reported a successful `gate` check run from GitHub
  Actions (app 15368) on the head commit, the gate in `kadet-hub/registry`
  failed on GI-2 and REG-1, and with a maintainer approval the pull request
  stayed `BLOCKED`; the status check rollup listed only the base
  repository's `gate` as required.
- AC-10 (CON-1, CON-1b): the consumer workflow compiles a sample consumer with its own
  helm input without network, and the recipe of `docs/authors.md` (DEC-15):
  a public chart pinned by version, pulled outside the sandbox, rendered
  with the helm input and patched in a kadet step, with a patch from the
  class and one from the target in the output. It fails on a generator that
  reads a decoy credential, on a vendored `resolvers.py` that opens a socket
  during `kapitan inventory`, on a dependency URL built from `oc.env`, and
  on a `hostPath` in a target the policy's `output_capabilities` does not
  cover while accepting it in the target it covers. Check:
  `consumer-selftest` over `tests/consumers/`; a `pass-*` sample with an
  `expect` file passes only when every line of it appears in its output.
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

## Test gaps

These requirements have no check that fails on a violation; the partial
coverage is named at each:

- REG-1: no sample whose tag points elsewhere; the fork rehearsals passed it.
- GI-3, GI-4, GI-8: job permissions are reviewed, not tested.
- GI-7: no sample that makes a gate tool error or time out.
- REV-2: the comment is rendered, not asserted.
- CON-3: documentation content.
- CAT-5: URL stability.

## Open questions

- OQ-1: A lawyer reviews LEG-1 to LEG-4: whether republishing reviewed code
  under the marketplace's namespace counts as adopting it, whether the DSA
  applies to an unpaid service, whether the operator is a controller of
  GitHub Pages' access logs, and whether an imprint is required.
- OQ-2: The operator supplies the name for the imprint and the privacy
  notice, and the serviceable postal address of an address service that
  holds a written power to accept service (Zustellungsvollmacht) for the
  imprint; a mail-forwarding address or PO box does not suffice, and the
  operator's private address is not published. § 18(1) MStV requires the
  real full name; a pseudonym or group name does not satisfy it. Until then
  the name reads `tbd` and the imprint says the address follows. The e-mail
  addresses are decided: `contact@`, `privacy@`, `abuse@` and
  `security@kadet-hub.org`, role addresses the operator routes.

## Implementation inventory

| Path | Content |
|---|---|
| `generators/<name>.yaml` | Marketplace entry (Registration) |
| `policy/entry.schema.json`, `policy/manifest.schema.json` | QA-5, GI-1, GI-9 |
| `policy/reserved-names.txt` | REG-2, REG-3, REG-9 |
| `policy/maintainers.txt` | maintainer user IDs (Gate integrity) |
| `gate/` | GI-1, GI-2, REG-1 to REG-6, REG-8, REG-9, SEC-8, QA-1, QA-2, QA-5: `run`, `check_entry.py`, `fetch_tree.py`, `fetch-charts`, `output_diff.py` (SEC-13) |
| `.github/actions/setup-gate/` | gVisor, scanners and sandbox image for `gate.yml` and `selftest.yml` |
| `policy/semgrep/blocking/`, `policy/semgrep/review/`, `policy/imports.txt` | SEC-3 |
| `policy/gitleaks.toml` | SEC-1, SEC-4 |
| `scan/` | SEC-1 to SEC-6: `static-scan` runner, `tree_check.py`, scanner requirements |
| `policy/binaries.txt` | SEC-7, SEC-10 |
| `policy/output/` | SEC-12 rego rules |
| `policy/licenses.txt` | QA-2 |
| `policy/ruff.toml` | QA-3 |
| `sandbox/schema_check.py`, `sandbox/tf_schema.py` | QA-7, QA-8 |
| `sandbox/apiserver_check.py` | QA-10 |
| `.github/workflows/tf-schema-verify.yml`, `gate/tf-schema-verify` | QA-9 |
| `sandbox/` | SEC-9 to SEC-12: image, `gate-compile` runner, `check.py`, `output_check.py`; reused by CON-1 |
| `tests/samples/` | AC-1 to AC-5, AC-8 |
| `tests/consumers/` | AC-10 |
| `.github/workflows/gate.yml` | GI-*, REG, SEC, CMP, QA, REV-2 |
| `.github/workflows/selftest.yml` | `gate-selftest`, on maintainer pull requests |
| `.github/workflows/{consumer-selftest,catalog-tests,release-tests}.yml` | CI-1: `consumer-selftest`, `catalog-tests`, `release-tests` |
| `.github/workflows/release.yml` | PUB-1 to PUB-8, GI-8, CAT-1, CAT-7, CAT-14, index and catalog |
| `release/` | PUB-1, PUB-4, PUB-5: `build.py`, `tree.py`, `index.py` |
| `.github/workflows/scheduled.yml`, `scan/rescan`, `scan/rescan_issues.py` | SEC-15, SEC-16 |
| `.github/workflows/consumer.yml`, `consumer/`, `consumer-selftest` | CON-1, CON-2 |
| `sandbox/gitlab-ci.yml` | CON-1a |
| `policy/consumer.schema.json` | consumer policy `.kapitan-sandbox.yaml` |
| `docs/consumers.md` | CON-2, CON-3 |
| `.github/ISSUE_TEMPLATE/` | CAT-12 |
| `policy/tags.yaml` | CAT-4, CAT-13 |
| `TERMS.md`, `SECURITY.md`, `catalog/site/content/{privacy,imprint}.md` | LEG-1 to LEG-5 |
| `release/scan-record`, `release/sbom.py` | PUB-7, PUB-8 |
| `catalog/` | CAT-1 to CAT-14: Hugo site, `build` script, `test_catalog.py`; icons from lucide-static 1.55.0 (ISC) |
| `docs/authors.md`, `README.md` | CAT-6 |
| `docs/incident.md` | INC-1 |
| `.github/CODEOWNERS`, `.github/ruleset.json` | REV-1; the ruleset is applied with `gh api` |
| `.github/workflows/workflows.yml`, `tests/workflow-policy` | GI-6, GI-10, GI-11 |
| `renovate.json` | REG-7, tool and action pins |

Tool versions (Kapitan, krab, gVisor, gitleaks, GuardDog, semgrep, ruff,
ClamAV, conftest, oras, helm, kube-apiserver, etcd, gh, zizmor, actionlint,
Hugo) are pinned in
`sandbox/Dockerfile`, the requirements files, `.github/actions/` and
`sandbox/gitlab-ci.yml`; Renovate proposes updates (REG-7).
