# Kapitan generator marketplace: Recipes

Status: Draft
Code: `recipes/`, `policy/reserved-names.txt`, `gate/`, `sandbox/`, `release/`, `.github/workflows/{gate,release}.yml`, `.github/actions/setup-gate/` (none implemented yet)
Verified against: main @ aa7e00c

Related: [marketplace.md](marketplace.md) holds the threat model, acceptance
criteria and open questions; [consumers.md](consumers.md) (CON-4, CON-5) and
[catalog.md](catalog.md) (CAT-38 to CAT-38b) hold the recipe requirements of
their areas; kadet-hub/recipes
[`docs/specs/recipes.md`](https://github.com/kadet-hub/recipes/blob/main/docs/specs/recipes.md)
defines a recipe and its proof (`RCP-`).

## Problem

A recipe is a Kapitan class directory that rebuilds what a Helm chart
renders with listed generators, proven against that chart by the `check`
script of kadet-hub/recipes. That repository's DEC-1 publishes recipes
through this registry like generators, and its OQ-3 asks what the gate
checks for one.

Most of the generator gate has nothing to look at. RCP-17 limits a recipe to
parameters, `kadet` compile entries on generators it pins by digest, `copy`
entries of vendored files with their SHA-256, and `oci` dependencies on
`ghcr.io/kadet-hub/`. There is no Python for GuardDog, semgrep, the import
allowlist or ruff, and no manifest.

The risks lie elsewhere. A recipe's classes merge into the consumer's
inventory, so a recipe that writes outside its own keys changes another
application, for example its image, and no output rule notices (RCP-18).
Vendored files reach the compiled output byte for byte. A recipe pins
generators, and each of them has to be listed, attested and not yanked.
Kapitan 0.36.3 loads the inventory before it fetches dependencies, so a
recipe cannot be fetched the way a generator is (kapicorp/kapitan#1638).

## Decisions

- DEC-17: Recipes are registered in this repository as `recipes/<name>.yaml`
  and published by the same release workflow, under the same signing
  identity, into the same index and catalog.

  A separate registry repository for recipes was considered. It would
  repeat the gate integrity, the rulesets, the `release` environment and the
  release workflow, and consumers would verify a second certificate
  identity.

- DEC-18: In version 1 every recipe comes from kadet-hub/recipes, and new
  recipe entries are maintainer pull requests. Decided with #341, formerly
  OQ-10.

  The gate runs its pinned `check` on whatever repository a recipe comes
  from, so the layout of RCP-1 is not the obstacle. Two other things are.
  REG-4 proves ownership from a manifest, which a recipe does not have. A
  level above `renders` (DEC-20) is a claim that only kadet-hub/recipes CI
  backs. Registration from other repositories (DEC-2) needs both solved
  first and is out of scope for version 1.

- DEC-19: Recipe names are a namespace of their own. Generators publish to
  `ghcr.io/kadet-hub/<name>` (PUB-1), recipes to
  `ghcr.io/kadet-hub/recipes/<name>`.

  The `cert-manager` recipe and the `certmanager` generator are the same
  name after REG-3 removes `-`. A recipe and the generator for the same
  software are expected, so REG-2, REG-3 and REG-9 compare a recipe name
  with recipe names only. `recipes` goes on `policy/reserved-names.txt`, so
  no generator takes the package name above the recipes.

- DEC-20: The gate proves level `renders` and no higher level. `deploys` and
  `migrates` start the recipe's pods and run `tests/smoke`, a script from the
  source repository, which the gate does not run. The README's level is
  recorded as kadet-hub/recipes' claim (RCP-13), next to the `renders`
  result of the release run.

- DEC-21: Kapitan and helm run only in the SEC-9 sandbox. `check` compares
  their outputs and runs neither.

  `check` compiles the recipe with Kapitan on the host and renders the chart
  with `helm template` there. Boundary 2 of the threat model rules out
  generator code on the host, and RCP OQ-7 leaves open whether a chart can
  attack `helm template`. The gate compiles in the sandbox, renders the chart
  in the sandbox, and passes both outputs to `check` (RCP-34). The kind
  clusters of the proof then receive data only.

- DEC-22: The artifact holds the recipe directory without `tests/`.

  Consumers include classes, not the proof. `tests/smoke` is an executable,
  which SEC-5 bans, and `tests/target.yml` would become a class
  `recipes.<name>.tests.target`.

- DEC-23: A recipe's output capabilities are recorded, not declared.

  A generator declares `output_capabilities` because its output depends on
  the consumer's inventory. A recipe's output is fixed by its classes,
  apart from the values a target sets, so the SEC-12 matches of the gate's
  compile of `tests/target.yml` are the record. The consumer still accepts
  each of them per output path (CON-1b). Options that `tests/target.yml`
  does not include are not compiled and not recorded.

- DEC-28: A recipe may include other recipes of kadet-hub/recipes by class
  (DEC-4 and DEC-12 there), and the parent's `source.sha` pins them. The
  gate looks up the tree of each included recipe at that commit among the
  published versions (REC-16), and the parent's record lists the versions
  it found. The consumer workflow checks that the fetch inventory pins
  exactly those (CON-4). Decided with this change, formerly OQ-12.

  A pin line in the parent's README was considered. It would repeat what
  the commit already fixes, and the two could disagree. A dependency in the
  parent's classes is fetched too late (CON-4). Pinning a range of versions
  per included recipe was considered too. The gate would then publish
  combinations that no CI run compiled together.

## Registration

```yaml
# recipes/<name>.yaml (marketplace)
source:
  repo: https://github.com/kadet-hub/recipes.git
  path: <name>
  tag: <name>-v<X.Y.Z>
  sha: <40-character commit SHA>
owners: [<GitHub user ID>, ...]
exceptions: []
yanked: {}                       # <version>: <reason>
advisories: {}                   # <version>: [GHSA-…], maintainer only (INC-1)
```

The entry has the generator entry's shape, so `policy/entry.schema.json`,
GI-9 and the Renovate regex manager of REG-7 apply unchanged. Renovate
compares tags within their prefix, so `cert-manager-v1.0.0` moves only to a
newer `cert-manager-v*`. The source repository carries no manifest: the
recipe's README and class files hold what the index lists (REC-13).

- REC-1: A recipe entry MUST set `source.repo` to
  `https://github.com/kadet-hub/recipes.git`, `source.path` to its name,
  `source.tag` to `<name>-vX.Y.Z` and `exceptions` to an empty list. The
  gate MUST apply REG-1, REG-5, REG-6, REG-8, GI-1 and GI-2 to
  `recipes/<name>.yaml` as to `generators/<name>.yaml`.

  A non-maintainer pull request still changes exactly one entry file.
  SEC-14 exceptions cover scanner findings in code, which a recipe does not
  have.

  - Test: `gate/test_check_entry.py` (not written)
  - Since: not implemented

- REC-2: A recipe name MUST pass REG-2 and REG-3 against the recipe names on
  `main` and `policy/reserved-names.txt`, not against generator names. A
  removed recipe's name MUST go on `policy/reserved-names.txt` (REG-9).
  `recipes` MUST be on that list.

  A reserved name blocks both namespaces, so a removed recipe name cannot
  be reused as a generator name and the other way round.

  - Test: `gate/test_check_entry.py` (not written)
  - Since: not implemented

- REC-3: A pull request adding a recipe entry MUST be a maintainer pull
  request (DEC-18). Changes to an existing entry follow REG-5.

  This replaces REG-4, which compares the author with the manifest's
  `owners`; a recipe has no manifest. `owners` names who may open bumps
  and yanks besides the maintainer and Renovate. That answers RCP OQ-4.

  - Test: `gate/test_check_entry.py` (not written)
  - Since: not implemented

## Gate

The gate fetches `source.sha:source.path` as data with `gate/fetch_tree.py`,
as for a generator. It then runs, in this order: the tree and scanner
checks (REC-4), `check lint` on the files (REC-5), the generator pins
(REC-6) and the chart (REC-7), the sandboxed compile (REC-8) and the
`renders` proof (REC-9). The previous version, on a bump, is compiled for
the output diff (REC-10). Only the source fetch, the index and generator
pulls and the chart pull or manifest download have network.

`check` comes from a `check-vX.Y.Z` release of kadet-hub/recipes (RCP-22),
pinned by commit SHA in `.github/actions/setup-gate/` like the other gate
tools (GI-6), and Renovate proposes its bumps (REG-7). The recipe's own copy
of `check` at `source.sha` is not used, so a recipe tag cannot weaken the
rules it is judged by.

- REC-4: The shipped tree, `source.path` without `tests/`, MUST hold only
  `README.md`, class files `*.yml` at its root, and below `vendor/` files
  that are neither `*.yml` nor `*.py`, and every vendored file MUST have
  its license next to it (REC-15). The gate MUST run SEC-1, SEC-5 and
  SEC-6 over the shipped tree and `tests/target.yml` and
  `tests/values.yaml`, and MUST NOT read any other file below `tests/`.

  `check lint` reads only the `*.yml` files at the root (RCP-1). A
  `vendor/x.yml` would still be loadable as `.vendor.x` from a class, and
  RCP-17 would never see it. SEC-2, SEC-3 and QA-3 inspect Python and do
  not apply, and the shipped tree contains no Python file. QA-1 does not
  apply: a recipe has no CHANGELOG, and the gate comment shows the output
  diff (REC-10). The license is the one whose `policy/licenses.txt` pattern
  matches the repository root's `LICENSE`, as QA-2 matches it, and the gate
  fails when none does.

  - Test: workflow job `gate-selftest`, samples under `tests/samples/recipes/` (not written)
  - Since: not implemented

- REC-5: `check lint`'s file rules MUST pass on the recipe, run in the
  sandbox image without network. Every class a recipe file includes MUST
  start with `.` or `recipes.<name>.`, or name an included recipe as
  `recipes.<other>` or `recipes.<other>.<option>` that REC-16 resolves.

  The file rules are RCP-1, RCP-2, RCP-4, RCP-7 and RCP-17 to RCP-19, the
  `Source` and `Level` lines of RCP-23, and the include and pin rules
  RCP-47, RCP-48 and RCP-54. They read the files only. The include rule is
  stricter than `check lint`, which accepts every `recipes.` class of its
  own repository, because the included recipe must also be a published
  version (REC-16).

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-6: Every `oci` dependency of a recipe MUST name a generator as
  `ghcr.io/kadet-hub/<generator>:<version>@sha256:<digest>` with
  `output_path: lib/<generator>`. The latest index MUST verify as CON-2
  describes and list that digest under that generator and version, not
  yanked, and the generator's own attestation MUST verify.

  This is RCP-27 on the gate's side. The generators' `binaries` from the
  index extend the SEC-10 policy of the compile, as CON-1 step 4 does for a
  consumer. The release records the pins (REC-13), so a later yank of a
  pinned generator shows on the recipe's page (CAT-38).

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-7: The gate MUST pull the chart of the README's `Source` line with
  `helm pull` by digest, fail unless its `Chart.yaml` version is the
  line's version, and render it with `helm template` and
  `tests/values.yaml` in the sandbox, with the release name and namespace
  of RCP-23. For a release manifest (RCP-23, RCP-59) it MUST instead
  download the release asset of the line and fail unless its SHA-256 is
  the line's digest. The manifest's documents then take the rendered
  chart's place in REC-9, and helm does not run.

  The chart or manifest is not scanned (SEC-8) and not shipped. It never
  reaches a consumer: it is only the other side of the comparison. DEC-15 is
  therefore unaffected, since a recipe renders no chart at compile time. `helm template`
  runs under the SEC-10 trace with `helm template` allowed as for a declared
  binary.

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-8: The gate MUST compile a project of the shipped tree at
  `inventory/classes/recipes/<name>/`, the artifact of each included recipe
  that REC-16 resolves at `inventory/classes/recipes/<other>/`,
  `tests/target.yml` as its only target and the verified generators at
  their `output_path` in the sandbox, with the omegaconf backend. CMP-1,
  CMP-2, CMP-5, SEC-9 to SEC-11 and QA-10 apply, and the output rules of
  `check lint` (RCP-3, RCP-6) MUST pass on the output. SEC-12 matches MUST
  be recorded and MUST NOT fail the gate (DEC-23).

  Recipes are written for omegaconf (RCP DEC-3), so `inventory_backends`
  has no counterpart. krab (CMP-4) is not run: whether krab reads omegaconf
  inventories has not been checked, and no requirement depends on the
  result. QA-7, QA-11 and QA-12 need a `schemas` directory, which a recipe
  does not have; vendored CRDs are output and go through QA-10.

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-9: The gate MUST run `check <name> --level renders` with the outputs of
  REC-7 and REC-8 (RCP-34), in a job with `contents: read` and no secrets,
  and fail when `check` fails.

  At `renders` the kind clusters apply only Namespaces, CRDs,
  ServiceAccounts and RBAC objects for real and dry-run the rest (RCP-26),
  so nothing from the recipe or the chart runs as a pod. The job needs
  Docker on the GitHub-hosted runner for kind, which is why it runs outside
  the sandbox.

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-10: The gate comment MUST show, on a bump, the output diff against the
  previous version as SEC-13 does, and the SEC-12 matches, generator pins,
  included recipes, chart or manifest source and level before and after.

  A chart update with an unchanged object diff can still bring a new
  admission webhook or `hostPath`. RCP-21 shows that to the reviewer of the
  recipe change in kadet-hub/recipes; this shows it to the reviewer of the
  registry bump.

  - Test: `gate/test_output_diff.py` (not written for recipes)
  - Since: not implemented

- REC-14: The scheduled workflow MUST cover recipe entries: SEC-15 with the
  scans of REC-4 and SEC-16 for their tags.

  - Test: `scan/test_rescan_issues.py` (not written for recipes)
  - Since: not implemented

- REC-15: For every file a recipe's `copy` entries vendor, the shipped tree
  MUST hold the upstream license as `vendor/<file>.LICENSE`, and the
  upstream NOTICE as `vendor/<file>.NOTICE` when the upstream source has
  one. The gate MUST fail on a vendored file without `.LICENSE`.

  The artifact redistributes vendored files, such as the cert-manager
  CRDs under Apache-2.0, whose section 4 requires a copy of the license
  and the NOTICE with every redistribution. The SHA-256 comment names the
  source, not the terms. A file per vendored file keeps the rule
  mechanical: the gate and `check lint` (RCP-35 in kadet-hub/recipes) see
  the pair without a mapping. Whether the upstream source has a NOTICE is
  a review question, since neither can fetch upstream. Decided with #341,
  formerly OQ-11.

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-16: For each recipe `<other>` that a recipe includes, the gate MUST
  compute the tree ID of `source.sha:<other>` without its `tests` entry, as
  REC-11 does, and fail unless the latest index lists a version of
  `<other>` with that tree ID that is not yanked. It MUST pull that version
  by digest and verify it as CON-5 describes.

  kadet-hub/recipes tags a parent only on a commit where each included
  recipe equals one of its tags (RCP-53), so the lookup finds the version
  that CI proved together with the parent. Several versions with the same
  tree have the same content, and the gate takes the oldest. An included
  recipe that includes recipes itself fails `check lint` (RCP-47) and
  therefore REC-5.

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

- REC-17: For each recipe on a recipe's `Requires:` line (RCP-54), on
  those of its included recipes and, in turn, on those of the required
  recipes, the gate MUST resolve the required recipe at `source.sha` as
  REC-16 does, compile it from its own `tests/target.yml` in the sandbox
  as REC-8 does, and pass that output to `check`, which applies the CRDs
  before the proof in the order of RCP-55.

  A dry run of a CloudNativePG Cluster or an HTTPRoute fails without its
  CRD. The RabbitMQ operator's Certificates need cert-manager's CRDs, and
  `rabbitmq` reaches `cert-manager` only through `rabbitmq-cluster-operator`.
  `gateway-api` is no recipe: `check` installs it with its pinned
  cloud-provider-kind, which `.github/actions/setup-gate/` pins with the
  other gate tools. The required recipe is not recorded, since the
  consumer installs it in a target of its own.

  - Test: workflow job `gate-selftest` (not written)
  - Since: not implemented

## Artifact and index

```yaml
# consumer fetch inventory (CON-4)
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/<name>:<version>@sha256:<digest>
        output_path: inventory/classes/recipes/<name>
```

- REC-11: A recipe artifact MUST be an OCI image manifest with artifact type
  `application/vnd.kadet-hub.recipe.v1`, a config blob
  `application/vnd.kadet-hub.recipe.config.v1+json` and one layer
  `application/vnd.oci.image.layer.v1.tar` titled `<name>.tar`, pushed to
  `ghcr.io/kadet-hub/recipes/<name>` and tagged `<X.Y.Z>`. The tar MUST hold
  the shipped tree (REC-4) at its root, normalized as PUB-1 describes. The
  sign job MUST compare the tar with the tree of `source.sha:source.path`
  without its `tests` entry.

  That tree ID is the one `git mktree` writes for `git ls-tree
  <sha>:<path>` with the `tests` line removed, so the sign job's own fetch
  still decides (PUB-1). The layer media type is the generators', because
  Kapitan's `oci` dependency extracts it into `output_path` the same way.
  The tag drops the `<name>-v` prefix, as generator tags drop theirs.

  - Test: `release/test_release.py` (not written)
  - Since: not implemented

- REC-12: For every recipe version it publishes, the release workflow MUST
  rerun REC-4 to REC-9 in the build job, record the run as `scan` (PUB-7),
  and apply PUB-1 to PUB-3a, PUB-8 and PUB-9 as for a generator.

  The `renders` proof of the release run is the one the catalog shows
  (DEC-20), since PUB-7 records what the publishing run checked. kind runs in
  the build job, which holds `contents: read` and `packages: read` only. The
  SBOM lists the tar's files; the vendored files keep the source URL from
  their SHA-256 comment, which RCP-17 requires.

  - Test: manual: fork rehearsal (not run)
  - Since: not implemented

- REC-13: The index MUST list recipes under a top-level `recipes` key,
  `{<name>: {<version>: <record>}}`, with the same `serial`. A record MUST
  hold digest, tree ID, description, license, owners, source repository,
  tag and SHA, `level` from the README, `chart` (`repo`, `version`,
  `digest`), or for a release manifest `manifest` (`url`, `digest`), from
  its `Source` line, `generators` (`name`, `version`,
  `digest`) for each pin, `includes` (`name`, `version`, `digest`) for each
  included recipe (REC-16), `output_capabilities` (the SEC-12 matches,
  DEC-23), `kinds` (PUB-10), `scan`, `output_diff`, `published`, `yanked`
  and `advisories`.

  `generators` stays as it is, so a consumer workflow or `check` that reads
  only that key keeps working. The description is the first paragraph of
  the README (RCP-32), with QA-5a applied. PUB-5 (yanking), INC-1 and the
  release notes of PUB-12 apply to recipe versions, named `recipe <name>
  <version>` in the notes.

  A yanked generator does not yank the recipes that pin it. The consumer
  workflow rejects that generator in the main inventory anyway (CON-2), so
  each such recipe fails closed, and the catalog marks it (CAT-38).

  - Test: `release/test_release.py` (not written)
  - Since: not implemented

Consumer workflow commits from before CON-4 reject a
`ghcr.io/kadet-hub/recipes/<name>` source with `is not a marketplace
generator`, because `consumer/plan.py` only accepts a name that matches
REG-2. They fail closed.

## Implementation inventory

| Path | Content |
|---|---|
| `recipes/<name>.yaml` | Recipe entry (REC-1 to REC-3) |
| `policy/reserved-names.txt` | `recipes` (REC-2) |
| `gate/check_entry.py`, `gate/run` | REC-1 to REC-7, REC-10, REC-15 to REC-17 |
| `scan/rescan`, `.github/workflows/scheduled.yml` | REC-14 |
| `sandbox/gate-compile` | REC-7, REC-8, REC-17 |
| `.github/actions/setup-gate/` | `check` pin (REC-5, REC-9) |
| `.github/workflows/gate.yml` | REC-9 job |
| `release/build-all`, `release/build.py`, `release/tree.py`, `release/index.py` | REC-11 to REC-13 |
| `tests/samples/recipes/` | AC-12 |

| Value | Setting |
|---|---|
| Source repository | `https://github.com/kadet-hub/recipes.git` |
| Tag in the source repository | `<name>-vX.Y.Z` |
| Package | `ghcr.io/kadet-hub/recipes/<name>`, tag `X.Y.Z` |
| Artifact type | `application/vnd.kadet-hub.recipe.v1` |
| Config media type | `application/vnd.kadet-hub.recipe.config.v1+json` |
| Consumer path | `inventory/classes/recipes/<name>/` |
| Inventory backend | omegaconf |
