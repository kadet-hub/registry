# Kapitan generator marketplace: Recipes

Status: Draft
Code: `recipes/`, `policy/reserved-names.txt`, `gate/`, `sandbox/`, `release/`, `scan/rescan`, `.github/workflows/{gate,release,scheduled}.yml`, `.github/actions/{setup-gate,setup-check,setup-kind}/`
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
  exactly those (CON-4). Decided with #350, formerly OQ-12.

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

  - Test: `gate/test_check_entry.py` (`Recipe.test_source_and_exceptions`, `Recipe.test_changes_follow_reg5`, `Files.test_recipe_entry`) (partial: REG-1 runs in `gate/run` without a test, as for generators)
  - Since: #377

- REC-2: A recipe name MUST pass REG-2 and REG-3 against the recipe names on
  `main` and `policy/reserved-names.txt`, not against generator names. A
  removed recipe's name MUST go on `policy/reserved-names.txt` (REG-9).
  `recipes` MUST be on that list.

  A reserved name blocks both namespaces, so a removed recipe name cannot
  be reused as a generator name and the other way round.

  - Test: `gate/test_check_entry.py` (`Recipe.test_names`, `Recipe.test_removal_reserves_name`)
  - Since: #377

- REC-3: A pull request adding a recipe entry MUST be a maintainer pull
  request (DEC-18). Changes to an existing entry follow REG-5.

  This replaces REG-4, which compares the author with the manifest's
  `owners`; a recipe has no manifest. `owners` names who may open bumps
  and yanks besides the maintainer and Renovate. That answers RCP OQ-4.

  - Test: `gate/test_check_entry.py` (`Recipe.test_new_entry_needs_a_maintainer`, `Recipe.test_changes_follow_reg5`)
  - Since: #377

## Gate

The gate fetches `source.sha` as data with `gate/fetch_tree.py --recipe`,
which writes every recipe directory of the commit without its `tests/`
(REC-4). It then runs, in this order: the tree and scanner
checks (REC-4), `check lint` on the files (REC-5), the generator pins
(REC-6), the included and required recipes against the index (REC-16,
REC-17), the chart (REC-7), the sandboxed compile (REC-8, REC-17) and, in
a job of its own, the `renders` proof (REC-9). The previous version, on a
bump, goes through the same checks for the output diff (REC-10). Only the
source fetch, the index and generator pulls, the attestation checks and
the chart pull or manifest download have network.

The gate job runs REC-1 to REC-8, REC-10, REC-15 to REC-17 and REG-1 on a
recipe entry. `gate/recipe-checks` fetches the recipe and runs
`gate/recipe-static` from REC-4 on and `gate/recipe-compile` from REC-7
on. The `renders` job runs REC-9 after it. The release build job runs the
same scripts on every recipe version it publishes (REC-12).

Until this change the gate job failed every recipe entry after its checks
with `REC-11: the release publishes no recipe yet (REC-11 to REC-13), so
no recipe entry passes the gate`. The release read only
`generators/*.yaml`, so a recipe entry that passed would have merged
without being published. No check replaces the stop line: the gate job's
result is that of its checks, and the release publishes what merges
(REC-11 to REC-13).

`check` comes from a `check-vX.Y.Z` release of kadet-hub/recipes (RCP-22),
pinned by commit SHA in `.github/actions/setup-check/` like the other gate
tools (GI-6), and Renovate proposes its bumps (REG-7). `setup-check`, which
`setup-gate` and the `renders` job call, writes the release's `check/`
directory to `gate/.check/` with `gate/fetch_tree.py`. The recipe's own
copy of `check` at `source.sha` is not used, so a recipe tag cannot weaken
the rules it is judged by.

- REC-4: The shipped tree, `source.path` without `tests/`, MUST hold only
  `README.md`, class files `*.yml` at its root with their `.LICENSE` and
  `.NOTICE` files, and below `vendor/` files that are not `*.py`, of which
  `*.yml` and `*.yaml` only as inputs of a `copy` entry. Every vendored
  file MUST have its license next to it (REC-15). The gate MUST run SEC-1,
  SEC-5 and SEC-6 over the shipped tree and `tests/target.yml` and
  `tests/values.yaml`. It MUST NOT read any other file below `tests/`
  except `tests/target.yml` of each recipe the recipe includes or
  requires. Above level `renders`, the recipe directory the gate checks
  MUST hold `tests/smoke`.

  `check lint` lints every YAML file of a recipe as a class, except
  `tests/` and the inputs of `copy` entries, and fails a class that
  includes a `copy` input (RCP-33, RCP-36 in kadet-hub/recipes). A
  `vendor/x.yml` that no `copy` entry names is loadable as `.vendor.x` and
  passes the lint as a class outside the root. A class file that carries
  text a chart renders has the upstream license next to it as
  `<file>.LICENSE` (RCP-42), as in cnpg, postgresql, strimzi and valkey.
  Revised in #382: the first version allowed nothing at the root besides
  `README.md` and the class files and no YAML below `vendor/`, which would
  fail those four and keycloak-operator, whose vendored CRDs are `*.yml`.

  SEC-2, SEC-3 and QA-3 inspect Python and do not apply, and the shipped
  tree contains no Python file. The gate runs `scan/static-scan` all the
  same, so GuardDog and the template check of SEC-3 run too. Neither
  reports anything on the 16 recipes of kadet-hub/recipes at `8a20838`.
  SEC-5's limit of 1 MiB applies to recipes unchanged. cnpg vendors one
  file per CRD since kadet-hub/recipes#44 (merge `0c0ab12`), and its
  largest, `vendor/poolers.postgresql.cnpg.io.yml`, has 678,686 bytes.
  Decided with #389, formerly OQ-15. QA-1 does not apply: a recipe has no
  CHANGELOG, and the gate comment shows the output diff (REC-10). The
  license is the one whose `policy/licenses.txt` pattern matches the
  repository root's `LICENSE`, as QA-2 matches it, and the gate fails when
  none does.

  Of the recipe's `tests/`, `gate/fetch_tree.py --recipe` writes
  `tests/target.yml`, `tests/values.yaml` and, when the commit has
  `tests/smoke`, an empty file of that name, which `check lint` requires
  above level `renders` (RCP-1). The gate never runs it (DEC-20). It
  writes the other recipe directories of `source.sha` next to the recipe
  for REC-5, and the gate scans none of them. `--targets` then writes
  `tests/target.yml` of each recipe that `gate/check_recipe.py` lists as
  included or required, for REC-8 and REC-17. Revised
  in #385: the first version read no other recipe's `tests/target.yml`,
  which `check` needs to tell an included recipe's objects from the
  parent's (RCP-49).

  - Test: workflow job `gate-selftest`, samples under `tests/samples/recipes/` (`fail-recipe-python`, `fail-recipe-vendor-class`, `fail-recipe-token`); `gate/test_check_recipe.py` (`Recipe.test_passes`, `Recipe.test_layout`, `Recipe.test_license`); `gate/test_fetch_tree.py` (`FetchTree.test_recipe_reads_only_its_tests_files`)
  - Since: #382; `tests/target.yml` of included recipes: #385; SEC-5 for cnpg: #389; `tests/target.yml` of required recipes: #390

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

  The command `check lint` does more: it compiles the recipe with Kapitan
  on the host and pulls the generators and the chart. The gate therefore
  calls `lint.lint_files` of the pinned release in the sandbox image, the
  function behind the file rules. The include and `Requires` rules read
  the other recipes. They are the directories REC-4's fetch writes from
  `source.sha`, the trees REC-16 looks up among the published versions.

  - Test: workflow job `gate-selftest` (`fail-recipe-oc-env`, `fail-recipe-include`); `gate/test_check_recipe.py` (`Recipe.test_includes`)
  - Since: #382; the included recipe resolved (REC-16): #390

- REC-6: Every `oci` dependency of a recipe and of each recipe it
  includes or requires (REC-17) MUST name a generator as
  `ghcr.io/kadet-hub/<generator>:<version>@sha256:<digest>` with
  `output_path: lib/<generator>`. The latest index MUST verify as CON-2
  describes and list that digest under that generator and version, not
  yanked, and the generator's own attestation MUST verify.

  This is RCP-27 on the gate's side. The generators' `binaries` from the
  index extend the SEC-10 policy of the compile, as CON-1 step 4 does for a
  consumer. The release records the pins (REC-13), so a later yank of a
  pinned generator shows on the recipe's page (CAT-38). An included
  recipe's pins count, because REC-8 compiles its classes. `postgresql`
  pins the `cloudnative-pg` generator, and `nextcloud` and `keycloak`,
  which include it, do not. A required recipe's pins count too, because
  REC-17 compiles it. It compiles in a project of its own with its
  generators below `requires/<recipe>/lib/`, since it may pin another
  version of a generator: `rabbitmq-cluster-operator` pins the
  `kubernetes` generator 1.9.0 and requires `cert-manager`, which pins
  1.7.0.

  The gate checks the listing with `check_index` of `consumer/plan.py`, the
  consumer workflow's CON-2 check, and runs the `gh attestation verify` of
  CON-2 on the index and each generator. A dependency of another type
  fails as well, as RCP-17 bans it. The gate has no `index_serial`, so the
  serial check of CON-2 does not apply. The gate job holds
  `attestations: read`, and `gate/run` hands its token to
  `gate/recipe-static`, which passes it to `gh attestation verify` only.

  - Test: workflow job `gate-selftest` (`pass-recipe`, `fail-recipe-unlisted-digest`, `fail-recipe-yanked`); `gate/test_check_recipe.py` (`Recipe.test_pins`, `Recipe.test_included`, `Recipe.test_required`)
  - Since: #382; included recipes and the `binaries` in the compile: #385; required recipes: #390

- REC-7: The gate MUST pull the chart of the README's `Source` line with
  `helm pull` by digest, fail unless its `Chart.yaml` version is the
  line's version, and render it in the sandbox with
  `helm template <name> <chart> --namespace=<namespace> -f tests/values.yaml --include-crds`,
  with the release name and namespace of RCP-23. It MUST keep that output
  whole, hooks included. For a release manifest (RCP-23, RCP-59) it MUST instead
  download the release asset of the line and fail unless its SHA-256 is
  the line's digest. The manifest's documents then take the rendered
  chart's place in REC-9, and helm does not run. For a chart from an HTTP
  repository (RCP-23) it MUST download the archive that the repository's
  `index.yaml` names for the line's chart and version, and fail unless the
  archive's SHA-256 is the line's digest and its `Chart.yaml` names that
  chart and version, before it renders the archive as above.

  `helm pull` by digest works only for an OCI chart. An HTTP repository's
  index can change under the same version, and helm 4.3.1 uses the
  index entry's `digest` as a cache key without comparing it with the
  archive. So the gate checks the archive itself, as `check` does.

  `check` reads the render as `helm template`'s own output (RCP-34). It
  leaves the hooks out and lists them itself (RCP-25), and the CRDs are
  part of the comparison. The output rules of REC-8 take the chart's
  object names from it. A compose source or a designed recipe has nothing
  to render, and `check` proves either at `renders` without a comparison
  (REC-9).

  The gate pulls, downloads and compares with `fetch_chart`,
  `fetch_http_chart` and `fetch_manifest` of the pinned `check`, in the
  sandbox image with network, as SEC-8 pulls a generator's charts.
  `helm template` is the program of `sandbox/run`, so it runs under the
  SEC-10 trace with `helm template` allowed, and SEC-11 looks for the
  decoys in its output.

  The chart or manifest is not scanned (SEC-8) and not shipped. It never
  reaches a consumer: it is only the other side of the comparison. DEC-15 is
  therefore unaffected, since a recipe renders no chart at compile time.

  - Test: workflow job `gate-selftest` (`pass-recipe`, `fail-recipe-chart-version`, `fail-recipe-manifest-digest`)
  - Since: #385

- REC-8: The gate MUST compile a project of the shipped tree at
  `inventory/classes/recipes/<name>/`, the directory at `source.sha` of
  each included recipe, whose tree REC-16 finds among the published
  versions, at `inventory/classes/recipes/<other>/`, and the
  verified generators of all of them (REC-6) at their `output_path`, in
  the sandbox, with the omegaconf backend. Its targets MUST be
  `tests/target.yml` as `<name>` and each included recipe's own
  `tests/target.yml` as `<other>`. CMP-1, CMP-2, CMP-5, SEC-9 to SEC-11
  and QA-10 apply, and the output rules of `check lint` (RCP-3, RCP-6)
  MUST pass on the objects of each recipe. SEC-12 matches MUST be
  recorded and MUST NOT fail the gate (DEC-23).

  `check` gives an object to an included recipe when that recipe's own
  `tests/target.yml` renders one of the same kind and name (RCP-49), so it
  reads `compiled/<other>/` next to `compiled/<name>/` (RCP-34). The gate
  applies the output rules with `owned` and `lint_output` of the pinned
  `check` in the sandbox image without network, with the object names of
  the REC-7 render as the chart's, as `check lint` does. The SEC-12
  matches are lines of the gate report, and the release records them
  (REC-13).

  Recipes are written for omegaconf (RCP DEC-3), so `inventory_backends`
  has no counterpart. krab (CMP-4) is not run: whether krab reads omegaconf
  inventories has not been checked, and no requirement depends on the
  result. QA-7, QA-11 and QA-12 need a `schemas` directory, which a recipe
  does not have; vendored CRDs are output and go through QA-10.

  - Test: workflow job `gate-selftest` (`pass-recipe`, `fail-recipe-unpinned-image`); `gate/test_check_recipe.py` (`Recipe.test_included`); `gate/test_fetch_tree.py` (`FetchTree.test_recipe_reads_only_its_tests_files`)
  - Since: #385; the included recipe resolved (REC-16): #390

- REC-9: The gate MUST run the pinned `check` as
  `check <name> --level renders` on the outputs of REC-7 and REC-8
  (RCP-34) in the job `renders` of `gate.yml`, and fail when `check`
  fails. That job MUST hold `contents: read` and no other permission, read
  no secret, and fetch or compile nothing of the pull request.

  At `renders` the kind clusters apply only Namespaces, CRDs,
  ServiceAccounts and RBAC objects for real and dry-run the rest (RCP-26),
  so nothing from the recipe or the chart runs as a pod. For a chart or a
  release manifest `check` compares both sides, each on its own cluster
  (RCP-8). A compose source or a designed recipe has nothing to compare
  with, so `check` lints its output and dry-runs it on one cluster
  (RCP-38, RCP-44).

  kind needs Docker on the runner, so the job runs outside the sandbox and
  receives data only (DEC-21). Once every check before REC-9 has passed,
  the gate job hands over the artifact `recipe-proof`: a tar of the
  recipes directory of REC-4, the output path of REC-8's compile and the
  render of REC-7. A tar keeps the empty `tests/smoke`, which `check`
  requires above `renders` (RCP-1). With these inputs `check` pulls
  nothing (RCP-34). A cluster object that makes the API server call out,
  such as a CRD conversion webhook, reaches the runner's network but no
  secret.

  The `renders` job checks out `main`, fetches `check` with
  `.github/actions/setup-check/` and installs kind v0.33.0, kubectl v1.37.1,
  uv 0.13.5 and cloud-provider-kind v0.12.0 (REC-17) with
  `.github/actions/setup-kind/`, each pinned by sha256 (GI-6). The node
  image is the one `check` pins,
  `kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5`,
  which the release notes of kind v0.33.0 list. For a chart or a release
  manifest `gate/recipe-renders` runs

  ```sh
  uv run --quiet --locked --project gate/.check gate/.check/check.py <recipes>/<name> \
    --level renders --compiled <out> --rendered <render>
  ```

  and for a compose source or a designed recipe the same without
  `--rendered`. `<recipes>` is what `gate/fetch_tree.py` wrote for REC-4
  and REC-8, `<out>` holds `compiled/<name>/` and `compiled/<other>/` of
  each included and each required recipe (REC-17), and `<render>` is
  `helm template`'s output or the downloaded manifest.

  The job prints `check`'s report under `## Renders`, and the gate
  comment shows it after the gate job's report (REV-2). `check` exits 1
  when the proof fails, after the report lines that name each failure,
  such as `only in the chart: <object>`. The finding is then
  `REC-9: check <name> --level renders failed`. `check` exits 2 with
  `error: <message>` when a step fails, such as a dry run the API server
  rejects. The finding is then `REC-9: <message>`, with the message's
  further lines below it. When a check before REC-9 fails, the gate job
  reports `REC-9: not run, a check before it failed`, and the `renders`
  job is skipped.

  - Test: workflow job `gate-selftest` (`pass-recipe`, `pass-recipe-chart`, `fail-recipe-object-diff`, `fail-recipe-dry-run`) (partial: the `renders` job itself runs only from `main`)
  - Since: #389; required recipes and `gateway-api` (REC-17): #390

- REC-10: The gate comment MUST show, on a bump, the output diff against the
  previous version as SEC-13 does, and the SEC-12 matches, generator pins,
  included recipes, chart or manifest source and level before and after.

  A chart update with an unchanged object diff can still bring a new
  admission webhook or `hostPath`. RCP-21 shows that to the reviewer of the
  recipe change in kadet-hub/recipes; this shows it to the reviewer of the
  registry bump.

  The previous version is the one the entry on `main` pins, as for
  SEC-13. `gate/run` fetches its commit and runs REC-4 to REC-8 and REC-15
  to REC-17 on it as on the new version. When one of them fails, the first
  20 lines of their report without headings and SEC-12 lines follow
  `REC-10: the approved version's checks reported, not judged:`, and they
  do not fail the gate. `gate/output_diff.py` then compares the two compiles
  without the required recipes' (REC-17) and prints, after the diff, each
  of the five items for both versions. A line only the previous version
  has is marked `-`, one only the new version has `+`. The items come
  from `gate/check_recipe.py`'s output and the SEC-12 lines of each
  compile, which is what REC-13 records. The previous version's index
  record holds the same items, but the output diff needs the previous
  compile in any case. A new entry, or a change that keeps tag and SHA,
  shows none of this.

  - Test: `gate/test_output_diff.py` (`OutputDiff.test_recipe_before_and_after`) (partial: `gate/run` on a bump pull request first runs once a recipe entry is on `main`, after REC-11 to REC-13); manual: `gate/run` on bumps of valkey from `e54cf9f` and of cnpg from `dc9ea15` to `a4c9945` of kadet-hub/recipes, with `gh` and `git ls-remote` stubbed (2026-10-26)
  - Since: #390

- REC-14: The scheduled workflow MUST cover recipe entries: SEC-15 with the
  scans of REC-4 and SEC-16 for their tags.

  `scan/rescan` fetches a recipe entry's `source.sha` with
  `gate/fetch_tree.py --recipe` and runs `scan/static-scan` over the
  directory REC-4 scans: the shipped tree with `tests/target.yml`,
  `tests/values.yaml` and the empty `tests/smoke`. A recipe and a generator
  may have the same name (DEC-19), so the findings name a recipe as
  `recipe <name>`. Its issues are titled `rescan: recipe <name> <version>:
  <rule>` and `tag drift: recipe <name> <tag>`.

  - Test: `scan/test_rescan.py` (`Rescan.test_recipe_entry`)
  - Since: #391

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

  - Test: workflow job `gate-selftest` (`fail-recipe-no-license`); `gate/test_check_recipe.py` (`Recipe.test_vendored_license`)
  - Since: #382

- REC-16: For each recipe `<other>` that a recipe includes, the gate MUST
  compute the tree ID of `source.sha:<other>` without its `tests` entry, as
  REC-11 does, and fail unless the latest index lists a version of
  `<other>` with that tree ID that is not yanked. It MUST verify that
  version's attestation as CON-5 describes.

  kadet-hub/recipes tags a parent only on a commit where each included
  recipe equals one of its tags (RCP-53), so the lookup finds the version
  that CI proved together with the parent. Several versions with the same
  tree have the same content, and the gate takes the oldest. An included
  recipe that includes recipes itself fails `check lint` (RCP-47) and
  therefore REC-5. The artifact has no `tests/` (DEC-22), so REC-8
  compiles it from `<other>/tests/target.yml` at `source.sha`.

  `gate/check_recipe.py` computes the tree ID with `release/tree.py` over
  the directory that `gate/fetch_tree.py` wrote from `source.sha`. That is
  the ID `git mktree` writes for the listing without `tests`, and the gate
  looks it up in the records' `tree` (REC-13). `gate/recipe-static` then
  runs `gh attestation verify` on
  `ghcr.io/kadet-hub/recipes/<other>@<digest>` with the identity of CON-2.
  The findings are `REC-16: the index lists no version of <other> with
  tree <tree>`, `REC-16: the index lists <other> <versions> with tree
  <tree> only yanked` and `REC-16: <ref> has no marketplace attestation
  (CON-5)`.

  Revised in #390: the first version also pulled that version by
  digest. The compile uses the directory at `source.sha`, and the release
  compared the artifact with that tree before it signed the artifact and
  the index (REC-11), so a pull would check what the attestation already
  covers.

  No recipe is published yet, so until the first releases every recipe
  that includes one fails here: `external-dns-powerdns`, `keycloak` and
  `nextcloud`.

  - Test: workflow job `gate-selftest` (`fail-recipe-include-unpublished`; `pass-recipe-published` and `fail-recipe-include-yanked` against an index and attestations that `tests/selftest` stubs); `gate/test_check_recipe.py` (`Recipe.test_published`); `gate/test_fetch_tree.py` (`FetchTree.test_recipe_tree_without_tests`) (partial: the lookup of a real published version first runs with the first release of a recipe that includes one, such as `nextcloud`)
  - Since: #390

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
  cloud-provider-kind, which `.github/actions/setup-kind/` pins next to
  kind for the `renders` job (REC-9). The required recipe is not
  recorded, since the consumer installs it in a target of its own.

  The list is `requirement_order` of the pinned `check`, which
  `gate/recipe-static` calls in the sandbox image without network, so the
  `Requires:` lines are read by `check`'s own parser. Each required
  recipe compiles in a project of its own, with the generators it pins
  verified as REC-6 describes. The compile runs under `sandbox/run`, so
  SEC-9 to SEC-11 apply, and CMP-1 fails a target that writes no file. The output rules,
  SEC-12, QA-10, CMP-2 and CMP-5 do not run on it: it is a published
  version and passed them at its own gate. A required recipe that
  includes recipes compiles without them and fails. `gate/recipe-compile`
  writes the output to `requires/<recipe>/` of the proof directory, and
  `gate/recipe-renders` copies it next to the recipe's in `compiled/`,
  where `check` reads it (RCP-34).

  `.github/actions/setup-kind/` pins cloud-provider-kind v0.12.0, the
  version kadet-hub/recipes CI pins for `check` 0.10.0, by the SHA-256
  that the release's `cloud-provider-kind_0.12.0_checksums.txt` lists
  for `cloud-provider-kind_0.12.0_linux_amd64.tar.gz`. It manages every
  kind cluster on the Docker host, so a proof that requires `gateway-api`
  runs only on a CI runner.

  - Test: workflow job `gate-selftest` (`fail-recipe-requires-unpublished`, `pass-recipe-gateway-api`; `pass-recipe-published` against the stubbed index of REC-16, which reaches a recipe with a CRD through its included recipe's `Requires:` line and a required recipe's); `gate/test_check_recipe.py` (`Recipe.test_required`) (partial: the lookup of a real published version first runs with the first release of a recipe that requires one, such as `nextcloud` through `postgresql`)
  - Since: #390

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

  `release/build.py` writes the tar from the recipe directory that
  `gate/fetch_tree.py --recipe` wrote, without `tests/`, so the release
  reads no file below `tests/` that the gate does not read. The sign job
  fetches blobless, as for a generator, and passes `--missing` to `git
  mktree`, because the listing names blobs it did not fetch. The build and
  sign jobs name a recipe `recipes/<name>` in the matrix and in their
  directories. No generator can take that path, since `recipes` is
  reserved (REC-2).

  The first push creates the package `recipes/<name>` as private, as for a
  generator. The index job warns about every package that is not public,
  and a maintainer makes it public in the organisation's package settings.

  - Test: `release/test_release.py` (`Recipe.test_sign`); `release/test_build.py` (`Build.test_recipe_artifact`, `Build.test_recipe_names`, `Build.test_yanked_recipe_is_not_built`)
  - Since: #391

- REC-12: For every recipe version it publishes, the release workflow MUST
  rerun REC-4 to REC-9 in the build job, record the run as `scan` (PUB-7),
  and apply PUB-1 to PUB-3a, PUB-8 and PUB-9 as for a generator.

  The `renders` proof of the release run is the one the catalog shows
  (DEC-20), since PUB-7 records what the publishing run checked. kind runs in
  the build job, which holds `contents: read`, `packages: read` and
  `attestations: read` only. The SBOM lists the tar's files; the vendored
  files keep the source URL from their SHA-256 comment, which RCP-17
  requires.

  For each recipe version without a published tag, `release/build-all`
  runs `gate/recipe-checks` and `gate/recipe-renders`, the scripts of the
  gate job and the `renders` job, and fails the build with `REC-12: recipe
  <name> <version>: the checks failed` or `... the renders proof failed`.
  `.github/actions/setup-kind/` installs kind for it, as in the `renders`
  job. The job's timeout is 60 minutes instead of 30, since each recipe
  version adds about what a gate run takes. The rehearsal in the Test line
  took 126 seconds for cert-manager without gVisor; the time on a runner
  is not measured yet.

  `attestations: read` serves `gh attestation verify` of the index, the
  generators and the included and required recipes (REC-6, REC-16,
  REC-17). `release/build-all` unsets `GH_TOKEN` and hands it to
  `gate/recipe-checks`, which passes it to `gh attestation verify` only,
  as `gate/run` does. The registry login of `setup-oras` is read-only like
  the token and stays on the runner's disk, which neither the sandbox nor
  the kind node containers mount. An object of the proof that makes the
  API server call out reaches the runner's network, as in the `renders`
  job.

  The scan record has the checks of a generator's record and adds `lint`
  (REC-5, REC-8) and `renders` (REC-9), with the versions of `check` and
  kind. The output diff's base is the newest version the latest index
  lists under `recipes` that neither the index nor the entry marks yanked.
  `release/output-diff` runs `gate/recipe-checks` on it and compares the two
  compiles before the renders proof copies the required recipes' output
  next to the recipe's, so neither side holds it (REC-10). A base whose
  checks fail is still compared once `gate/recipe-compile` wrote its
  output, as REC-10 does. Without that output the record is `{base,
  error}` with `base did not compile`.

  - Test: `release/test_release.py` (`BuildAll.test_recipe_record`, `BuildAll.test_recipe_checks_and_renders_fail_the_build`, `ScanRecord.test_recipe_checks`, `OutputDiff.test_recipe_base`); manual: `release/build-all`, `release/sign` and `release/publish-index` on cert-manager at kadet-hub/recipes `a4c9945` against a local registry, with the attestations of its artifacts stubbed, then a bump to 1.1.0 on the same commit and a second run of each (2026-10-26)
  - Since: #391

- REC-13: The index MUST list recipes under a top-level `recipes` key,
  `{<name>: {<version>: <record>}}`, with the same `serial`. A record MUST
  hold digest, tree ID as `tree`, description, license, owners, `source`
  (`repo`, `path`, `tag`, `sha`), `level` from the README, `chart` (`repo`, `version`,
  `digest`), or for a release manifest `manifest` (`url`, `digest`), from
  its `Source` line, `generators` (`name`, `version`,
  `digest`) for each pin, `includes` (`name`, `version`, `digest`) for each
  included recipe (REC-16), `output_capabilities` (the SEC-12 matches,
  DEC-23), `kinds` (PUB-10), `scan`, `output_diff`, `published`, `yanked`
  and `advisories`.

  For a chart from an HTTP repository `repo` is the line's
  `https://<repository>/<chart>` with its scheme, so a reader tells it from
  an OCI reference, and `digest` is the SHA-256 of the archive. An OCI
  chart's `repo` is the reference without `oci://`. A compose source or a
  designed recipe has neither key; its `Source` line is in the artifact's
  README.

  `generators` stays as it is, so a consumer workflow or `check` that reads
  only that key keeps working. PUB-5 (yanking), INC-1 and the
  release notes of PUB-12 apply to recipe versions, named `recipe <name>
  <version>` in the notes.

  The record's `generators` are the pins of the recipe and of the recipes
  it includes, which REC-10 shows as `generator pins`, since the
  consumer's compile fetches all of them. `output_capabilities` lists the
  capabilities of the SEC-12 matches below `compiled/<name>/`, the output
  of the recipe's own target, once each and sorted, in the shape of a
  generator's. The paths depend on the gate's target name and are not
  recorded. `kinds` are those of the same directory. The Source and Level
  lines are read by `lint.readme_fields` of the pinned `check`, as REC-7
  reads them.

  The description is the first paragraph after the README's heading
  (RCP-32), with its whitespace collapsed, and the license is the
  identifier on `policy/licenses.txt` whose pattern REC-4 matched.
  `gate/check_recipe.py` takes both, in the gate as in the build job, so
  the gate fails what would stop the release: `REC-13: README.md has no
  paragraph after its heading for the description (RCP-32)` and `QA-5a:
  README.md: the first paragraph holds a control or bidirectional
  formatting character` and `REC-13: README.md: the description has <n>
  characters, RCP-32 allows 300`. `check lint` checks RCP-32 as well, so
  the limit is enforced before the recipe is tagged.

  The index carries `recipes` also when it lists no recipe, as `{}`. An
  index without the key counts as equal to one with an empty `recipes`,
  so the first release run after this change publishes no new serial
  unless a generator version changes.

  A yanked generator does not yank the recipes that pin it. The consumer
  workflow rejects that generator in the main inventory anyway (CON-2), so
  each such recipe fails closed, and the catalog marks it (CAT-38).

  - Test: `release/test_release.py` (`Index.test_recipes`, `Index.test_release_notes`, `BuildAll.test_recipe_record`); `gate/test_check_recipe.py` (`Recipe.test_passes`, `Recipe.test_description`, `Recipe.test_license`)
  - Since: #391

Consumer workflow commits from before CON-4 reject a
`ghcr.io/kadet-hub/recipes/<name>` source with `is not a marketplace
generator`, because `consumer/plan.py` only accepts a name that matches
REG-2. They fail closed.

## Implementation inventory

| Path | Content |
|---|---|
| `recipes/<name>.yaml` | Recipe entry (REC-1 to REC-3) |
| `policy/reserved-names.txt` | `recipes` (REC-2) |
| `gate/check_entry.py`, `gate/run` | REC-1 to REC-3, REC-10, the hand-over to REC-9 |
| `gate/recipe-checks` | REC-4 to REC-8 and REC-15 to REC-17 on one version, for the gate job, the build job and the output diff (REC-10, REC-12) |
| `gate/fetch_tree.py`, `gate/recipe-static`, `gate/check_recipe.py`, `release/tree.py` | REC-4 to REC-6, REC-15 to REC-17, the included and required recipes' targets and generators (REC-8, REC-17), the description and license (REC-13) |
| `gate/recipe-compile`, `sandbox/run` | REC-7, REC-8, REC-17 |
| `gate/recipe-renders` | REC-9, the required recipes' output next to the recipe's (REC-17) |
| `gate/output_diff.py` | REC-10 |
| `consumer/plan.py` | `check_index`, the CON-2 check REC-6 runs |
| `scan/rescan`, `.github/workflows/scheduled.yml` | REC-14 |
| `.github/actions/setup-check/` | `check` pin (REC-5, REC-7 to REC-9) |
| `.github/actions/setup-kind/` | kind, kubectl and uv (REC-9), cloud-provider-kind (REC-17) |
| `.github/workflows/gate.yml` | `attestations: read` (REC-6), the `renders` job (REC-9) |
| `release/build-all`, `release/build.py`, `release/tree.py`, `release/sign`, `release/publish-index`, `release/index.py`, `release/output-diff`, `release/scan-record` | REC-11 to REC-13 |
| `.github/workflows/release.yml` | The build job's `attestations: read` and kind (REC-12) |
| `tests/samples/recipes/`, `tests/selftest` | AC-12, AC-14 |

| Value | Setting |
|---|---|
| Source repository | `https://github.com/kadet-hub/recipes.git` |
| Tag in the source repository | `<name>-vX.Y.Z` |
| Package | `ghcr.io/kadet-hub/recipes/<name>`, tag `X.Y.Z` |
| Name in the release matrix and directories | `recipes/<name>` |
| Artifact type | `application/vnd.kadet-hub.recipe.v1` |
| Config media type | `application/vnd.kadet-hub.recipe.config.v1+json` |
| Consumer path | `inventory/classes/recipes/<name>/` |
| Inventory backend | omegaconf |
| `check` | kadet-hub/recipes `check-v0.12.0`, commit `50d2b645ab68bdf701d1f06c70e8584964298af2`, in `gate/.check/` |
| cloud-provider-kind | v0.12.0 in `.github/actions/setup-kind/` (REC-17) |
